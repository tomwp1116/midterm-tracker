"""
Backfill historical Polymarket daily prices for all tracked races.

Pipeline per race:
  1. Look up the event slug from the races table.
  2. GET gamma-api.polymarket.com/events?slug={slug} → list of sub-markets + conditionIds.
  3. Find the Democratic-win sub-market (question contains "Democratic" / "Democrat").
     If not found, use the only binary market and treat Yes=Dem.
  4. GET clob.polymarket.com/markets/{conditionId} → tokens[].token_id.
     The Yes token is the one labelled "Yes" (= Dem wins).
  5. GET clob.polymarket.com/prices-history?market={token_id}&interval=max&fidelity=1440
     → daily close prices.
  6. Insert into market_snapshots (does not overwrite existing real data).
"""
import sys
import time
import sqlite3
import requests
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY_SECONDS

DB_PATH = Path(__file__).parent.parent / "data" / "midterms.db"
GAMMA   = "https://gamma-api.polymarket.com"
CLOB    = "https://clob.polymarket.com"

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

END_DATE = date.today() - timedelta(days=1)


def get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def ts_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def is_dem_question(question: str) -> bool:
    q = question.lower()
    return "democrat" in q or "democratic" in q or "blue" in q


def find_dem_token(slug: str):
    """
    Return (token_id, is_dem_yes) for the Democratic side of the PM event.
    Returns (None, None) on failure.
    """
    events = get(f"{GAMMA}/events", params={"slug": slug})
    if not events:
        return None, None

    event = events[0]
    markets = event.get("markets") or []
    if not markets:
        return None, None

    # Prefer a market whose question explicitly mentions Democratic
    dem_market = next(
        (m for m in markets if is_dem_question(m.get("question", ""))),
        None
    )
    # Fall back to the first binary market
    if dem_market is None:
        dem_market = markets[0]

    condition_id = dem_market.get("conditionId")
    if not condition_id:
        return None, None

    clob_data = get(f"{CLOB}/markets/{condition_id}")
    if not clob_data:
        return None, None

    tokens = clob_data.get("tokens") or []
    yes_token = next((t for t in tokens if t.get("outcome", "").lower() == "yes"), None)
    if not yes_token:
        return None, None

    # If the question was a Dem-wins question, Yes = Dem price
    is_dem_yes = is_dem_question(dem_market.get("question", ""))
    return yes_token["token_id"], is_dem_yes


def fetch_price_history(token_id: str):
    """Return list of (date_str, price_float) sorted ascending."""
    data = get(
        f"{CLOB}/prices-history",
        params={"market": token_id, "interval": "max", "fidelity": 1440}
    )
    if not data:
        return []
    history = data.get("history") or []
    results = []
    for pt in history:
        ts = pt.get("t")
        p  = pt.get("p")
        if ts is None or p is None:
            continue
        d = ts_to_date(int(ts))
        if d <= END_DATE.isoformat():
            results.append((d, float(p)))
    # Deduplicate by date (keep last for each day)
    by_date = {}
    for d, p in results:
        by_date[d] = p
    return sorted(by_date.items())


def backfill_race(conn: sqlite3.Connection, race_id: str, slug: str) -> int:
    token_id, is_dem_yes = find_dem_token(slug)
    if not token_id:
        print(f"    [{race_id}] Could not find DEM token for slug {slug!r}")
        return 0

    history = fetch_price_history(token_id)
    if not history:
        print(f"    [{race_id}] No price history returned")
        return 0

    c = conn.cursor()
    inserted = 0
    for snap_date, yes_price in history:
        # Check for existing real PM data on this date
        c.execute(
            "SELECT pm_dem_price FROM market_snapshots WHERE race_id=? AND snapshot_date=?",
            (race_id, snap_date)
        )
        row = c.fetchone()
        if row and row[0] is not None:
            continue  # already have real data

        dem_price = round(yes_price, 4) if is_dem_yes else round(1.0 - yes_price, 4)
        rep_price = round(1.0 - dem_price, 4)

        c.execute("""
            INSERT INTO market_snapshots
                (race_id, snapshot_date, pm_dem_price, pm_rep_price, pm_event_slug)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(race_id, snapshot_date) DO UPDATE SET
                pm_dem_price  = COALESCE(excluded.pm_dem_price,  market_snapshots.pm_dem_price),
                pm_rep_price  = COALESCE(excluded.pm_rep_price,  market_snapshots.pm_rep_price),
                pm_event_slug = COALESCE(excluded.pm_event_slug, market_snapshots.pm_event_slug)
        """, (race_id, snap_date, dem_price, rep_price, slug))
        inserted += 1

    conn.commit()
    return inserted


def main():
    print(f"Polymarket history backfill → {END_DATE}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT race_id, polymarket_slug FROM races
        WHERE polymarket_slug IS NOT NULL AND polymarket_slug <> ''
        ORDER BY race_id
    """)
    races = c.fetchall()
    print(f"Found {len(races)} races with Polymarket slugs\n")

    total = 0
    for i, (race_id, slug) in enumerate(races):
        n = backfill_race(conn, race_id, slug)
        if n > 0:
            print(f"  [{i+1:2d}/{len(races)}] {race_id:35s}  +{n} rows")
        time.sleep(REQUEST_DELAY_SECONDS)

    conn.close()
    print(f"\nDone. Inserted {total} historical PM snapshots across {len(races)} races.")


if __name__ == "__main__":
    main()
