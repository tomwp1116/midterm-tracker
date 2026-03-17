"""
Backfill historical Kalshi daily prices for all tracked races.

Uses the Kalshi candlesticks API:
  GET /series/{series}/markets/{ticker}/candlesticks
    ?period_interval=1440  (daily candles)
    &start_ts={unix}
    &end_ts={unix}

Fetches from START_DATE to yesterday (does not overwrite existing rows).
Run once after setup; afterwards daily_snapshot.py keeps things current.
"""
import sys
import time
import re
import sqlite3
import requests
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import KALSHI_BASE, USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY_SECONDS

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

# Fetch history starting from this date (when midterm markets got active)
START_DATE = date(2025, 11, 5)   # day after 2024 election — midterm markets ramped up
END_DATE   = date.today() - timedelta(days=1)  # up to yesterday (today captured by snapshot)

DB_PATH = Path(__file__).parent.parent / "data" / "midterms.db"


def date_to_ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def series_from_ticker(ticker: str):
    """
    Derive series ticker and side (D/R) from a Kalshi market ticker.

    Examples:
      CONTROLS-2026-D  →  series=CONTROLS,   side=D
      SENATEGA-26-R    →  series=SENATEGA,   side=R
      CONTROLH-2026-D  →  series=CONTROLH,   side=D
      HOUSECA13-26-D   →  series=HOUSECA13,  side=D
    """
    m = re.match(r'^(.+?)-(?:26|2026)-([DR])$', ticker, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2).upper()
    # Fallback: split on last two dashes
    parts = ticker.rsplit('-', 2)
    if len(parts) == 3:
        return parts[0], parts[2].upper()
    return ticker, None


def fetch_candlesticks(series: str, ticker: str, start_ts: int, end_ts: int):
    url = f"{KALSHI_BASE}/series/{series}/markets/{ticker}/candlesticks"
    params = {"period_interval": 1440, "start_ts": start_ts, "end_ts": end_ts}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return None, "404"
        resp.raise_for_status()
        return resp.json().get("candlesticks", []), None
    except Exception as e:
        return None, str(e)


def midpoint_from_candle(candle: dict):
    """Extract close-of-day midpoint from a candlestick record."""
    # Prefer (bid_close + ask_close) / 2; fall back to price.close
    try:
        bid = float(candle["yes_bid"]["close_dollars"])
        ask = float(candle["yes_ask"]["close_dollars"])
        return round((bid + ask) / 2, 4)
    except (KeyError, TypeError, ValueError):
        pass
    try:
        return float(candle["price"]["close_dollars"])
    except (KeyError, TypeError, ValueError):
        return None


def volume_from_candle(candle: dict):
    try:
        return float(candle.get("volume_fp", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def ts_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def backfill(conn: sqlite3.Connection, race_id: str, ticker: str):
    """
    Fetch and insert daily historical prices for one race/ticker.
    Figures out whether the ticker is the DEM or REP side, then
    populates the appropriate column.  Also tries to fetch the paired
    side so we don't have to rely on 1-complement arithmetic.
    """
    series, side = series_from_ticker(ticker)
    if not side:
        print(f"    [{race_id}] Cannot parse side from ticker {ticker!r} — skipping")
        return 0

    start_ts = date_to_ts(START_DATE)
    end_ts   = date_to_ts(END_DATE + timedelta(days=1))  # inclusive end

    # Fetch this ticker and its paired counterpart
    paired_side   = "R" if side == "D" else "D"
    paired_ticker = re.sub(r'-([DR])$', f'-{paired_side}', ticker, flags=re.IGNORECASE)

    candles_main,  err1 = fetch_candlesticks(series, ticker,        start_ts, end_ts)
    candles_paired, err2 = fetch_candlesticks(series, paired_ticker, start_ts, end_ts)

    if candles_main is None and candles_paired is None:
        if err1 != "404":
            print(f"    [{race_id}] Error: {err1}")
        return 0

    # Build a dict keyed by date string
    by_date: dict[str, dict] = {}

    def record(candles, is_dem: bool):
        if not candles:
            return
        for c in candles:
            ts  = c.get("end_period_ts")
            if not ts:
                continue
            d = ts_to_date(ts)
            if d not in by_date:
                by_date[d] = {"k_ticker": ticker}
            price = midpoint_from_candle(c)
            vol   = volume_from_candle(c)
            if is_dem:
                by_date[d]["k_dem_price"] = price
                by_date[d]["k_volume_24h"] = vol
            else:
                by_date[d]["k_rep_price"] = price
                by_date[d].setdefault("k_volume_24h", vol)

    record(candles_main,   side == "D")
    record(candles_paired, paired_side == "D")

    c = conn.cursor()
    inserted = 0
    for snap_date, vals in sorted(by_date.items()):
        # Skip dates we already have data for
        c.execute(
            "SELECT k_dem_price, k_rep_price FROM market_snapshots "
            "WHERE race_id=? AND snapshot_date=?",
            (race_id, snap_date)
        )
        row = c.fetchone()
        if row and (row[0] is not None or row[1] is not None):
            continue  # existing real data — don't overwrite

        dem = vals.get("k_dem_price")
        rep = vals.get("k_rep_price")
        vol = vals.get("k_volume_24h", 0)

        # Derive missing side from complement (binary market: dem + rep ≈ 1)
        if dem is None and rep is not None:
            dem = round(1.0 - rep, 4)
        elif rep is None and dem is not None:
            rep = round(1.0 - dem, 4)

        if dem is None and rep is None:
            continue

        c.execute("""
            INSERT INTO market_snapshots
                (race_id, snapshot_date, k_dem_price, k_rep_price, k_volume_24h, k_ticker)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(race_id, snapshot_date) DO UPDATE SET
                k_dem_price  = COALESCE(excluded.k_dem_price,  market_snapshots.k_dem_price),
                k_rep_price  = COALESCE(excluded.k_rep_price,  market_snapshots.k_rep_price),
                k_volume_24h = COALESCE(excluded.k_volume_24h, market_snapshots.k_volume_24h),
                k_ticker     = COALESCE(excluded.k_ticker,     market_snapshots.k_ticker)
        """, (race_id, snap_date, dem, rep, vol, vals.get("k_ticker", ticker)))
        inserted += 1

    conn.commit()
    return inserted


def main():
    print(f"Kalshi history backfill: {START_DATE} → {END_DATE}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT race_id, kalshi_ticker FROM races
        WHERE kalshi_ticker IS NOT NULL AND kalshi_ticker <> ''
        ORDER BY chamber, state
    """)
    races = c.fetchall()
    print(f"Found {len(races)} races with Kalshi tickers\n")

    total_inserted = 0
    errors = 0
    for i, (race_id, ticker) in enumerate(races):
        n = backfill(conn, race_id, ticker)
        if n > 0:
            print(f"  [{i+1:3d}/{len(races)}] {race_id:35s} {ticker:25s} → +{n} rows")
        total_inserted += n
        time.sleep(0.4)  # polite delay

    conn.close()
    print(f"\nDone. Inserted {total_inserted} historical snapshots across {len(races)} races.")
    if errors:
        print(f"  ({errors} races had errors)")


if __name__ == "__main__":
    main()
