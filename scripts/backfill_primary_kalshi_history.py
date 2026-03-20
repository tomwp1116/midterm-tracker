"""
Backfill historical Kalshi daily prices for completed primary races.

For each completed primary race that has a kalshi_series in PRIMARY_RACES:
  1. Fetch all markets in the series (including resolved ones)
  2. Pull daily candlesticks for each candidate market
  3. Insert into primary_candidate_snapshots

Uses the same candlesticks endpoint as backfill_kalshi_history.py but
writes per-candidate rows rather than binary D/R rows.

Run once after primaries complete. Safe to re-run — skips existing rows.
"""
import json
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    KALSHI_BASE, KALSHI_MARKETS_URL, PRIMARY_RACES, PRIMARY_RESULTS_PATH,
    USER_AGENT, REQUEST_TIMEOUT,
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
DB_PATH = Path(__file__).parent.parent / "data" / "midterms.db"
START_DATE = date(2025, 11, 5)   # earliest meaningful date for 2026 markets

_PLACEHOLDER_RE = re.compile(r"^person [abc]$", re.IGNORECASE)


def date_to_ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def ts_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def extract_candidate_name(title: str) -> str:
    m = re.match(
        r"[Ww]il(?:l)?\s+(.+?)\s+(?:be|win)\s+(?:the\s+)?(?:republican|democratic|dem|rep|gop|\d{4})\s",
        title, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    m2 = re.match(r"[Ww]il(?:l)?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", title)
    if m2:
        return m2.group(1).strip()
    return title[:40]


def midpoint_from_candle(candle: dict):
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


def fetch_series_markets(series_ticker: str) -> list:
    """Return all markets in a series (including resolved/settled)."""
    try:
        resp = requests.get(
            KALSHI_MARKETS_URL,
            params={"series_ticker": series_ticker, "limit": 200},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("markets", [])
    except Exception as e:
        print(f"  Error fetching series {series_ticker}: {e}")
        return []


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


def backfill_race(conn: sqlite3.Connection, race_id: str, series: str, party: str) -> int:
    end_date = date.today()
    start_ts = date_to_ts(START_DATE)
    end_ts = date_to_ts(end_date + timedelta(days=1))

    markets = fetch_series_markets(series)
    if not markets:
        print(f"  No markets found in series {series}")
        return 0

    c = conn.cursor()
    total = 0

    for market in markets:
        title = market.get("title", "")
        ticker = market.get("ticker", "")
        if not ticker:
            continue
        candidate = extract_candidate_name(title)
        if _PLACEHOLDER_RE.match(candidate):
            continue

        candles, err = fetch_candlesticks(series, ticker, start_ts, end_ts)
        time.sleep(0.3)

        if candles is None:
            if err != "404":
                print(f"    [{candidate}] Candlestick error: {err}")
            continue

        inserted = 0
        for candle in candles:
            ts = candle.get("end_period_ts")
            if not ts:
                continue
            snap_date = ts_to_date(ts)
            price = midpoint_from_candle(candle)
            if price is None:
                continue

            c.execute("""
                INSERT INTO primary_candidate_snapshots
                    (race_id, snapshot_date, candidate_name, party, k_price)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(race_id, snapshot_date, candidate_name) DO UPDATE SET
                    k_price = COALESCE(excluded.k_price, primary_candidate_snapshots.k_price)
            """, (race_id, snap_date, candidate, party, price))
            inserted += 1

        conn.commit()
        if inserted:
            print(f"    {candidate}: +{inserted} days")
        total += inserted

    return total


def main():
    with open(PRIMARY_RESULTS_PATH) as f:
        completed = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    grand_total = 0

    for race_id in completed:
        info = PRIMARY_RACES.get(race_id)
        if not info:
            continue
        series = info.get("kalshi_series")
        if not series:
            print(f"[{race_id}] No Kalshi series — skipping")
            continue
        party = info.get("party", "")

        print(f"\n[{race_id}] series={series}")
        n = backfill_race(conn, race_id, series, party)
        print(f"  → {n} rows total")
        grand_total += n
        time.sleep(0.5)

    conn.close()
    print(f"\nDone. {grand_total} rows inserted across {len(completed)} completed races.")


if __name__ == "__main__":
    main()
