"""
Fetch 2026 midterm election markets from Kalshi's public REST API.
No authentication required for reading market data.

Kalshi API docs: https://docs.kalshi.com
Base URL: https://api.elections.kalshi.com/trade-api/v2

STRATEGY: Instead of downloading ALL markets (100K+) and filtering client-side,
we use targeted series-based fetching:
  1. GET /series → list all series, identify election-related ones by ticker/title
  2. GET /markets?series_ticker=X for each election series
This keeps total API calls under ~80 instead of 100+.
"""
import json
import time
import re
import requests
from datetime import date, datetime
from config import (
    KALSHI_BASE, KALSHI_MARKETS_URL, KALSHI_EVENTS_URL,
    USER_AGENT, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
SERIES_URL = f"{KALSHI_BASE}/series"

# Patterns that indicate an election series (matched against ticker)
# These are tight: SENATE*, HOUSE*, GOV* + state code patterns
ELECTION_TICKER_PATTERNS = [
    r"^SENATE[A-Z]{2}$",    # SENATEGA, SENATEMI, etc.
    r"^SEATE[A-Z]{2}$",     # SEATEAL (Alabama variant)
    r"^HOUSE[A-Z]{2}\d+$",  # HOUSECA13, HOUSENY17, etc.
    r"^GOV[A-Z]{2}$",       # GOVGA, GOVCA, etc.
    r"^CONTROLH$",           # House control
    r"^CONTROLS$",           # Senate control
    r"^INPARTY",             # Balance of power
    r"^KXMIDTERM",           # Midterm-specific
]


def fetch_series_list():
    """Fetch the complete list of Kalshi series. Single API call."""
    try:
        resp = requests.get(SERIES_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("series") or []
    except Exception as e:
        print(f"  [Kalshi] Error fetching series list: {e}")
        return []


def discover_election_series(all_series):
    """From the full series list, identify 2026 midterm election series ONLY.
    Uses strict ticker pattern matching. No tag/category fallbacks —
    those match too broadly (2028 races, attorney generals, mayors, etc.)."""
    tickers = set()
    for s in all_series:
        ticker = s.get("ticker", "")

        # Only match by ticker pattern — these are unambiguous
        for pattern in ELECTION_TICKER_PATTERNS:
            if re.match(pattern, ticker, re.IGNORECASE):
                tickers.add(ticker)
                break

    return tickers


def fetch_markets_for_series(series_ticker, status="open"):
    """Fetch all open markets for one series. Usually 1-2 API calls."""
    all_markets = []
    cursor = None
    while True:
        params = {"series_ticker": series_ticker, "limit": 200}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(KALSHI_MARKETS_URL, params=params,
                               headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)
            cursor = data.get("cursor")
            if not cursor or not markets:
                break
        except Exception as e:
            print(f"  [Kalshi] Error fetching series {series_ticker}: {e}")
            break
    return all_markets


def parse_kalshi_market(market):
    """Convert a Kalshi market object to a standardized record."""
    ticker = market.get("ticker", "")
    event_ticker = market.get("event_ticker", "")
    title = market.get("title", "")
    subtitle = market.get("subtitle", "")

    last_price = market.get("last_price")
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")

    if yes_bid is not None and yes_ask is not None:
        midpoint = (yes_bid + yes_ask) / 2.0 / 100.0
    elif last_price is not None:
        midpoint = last_price / 100.0
    else:
        midpoint = None

    dem_price, rep_price = None, None
    combined = (title + " " + subtitle + " " + ticker).lower()
    if "democrat" in combined or "-dem" in ticker.lower() or "dem " in combined:
        dem_price = midpoint
    elif "republican" in combined or "-rep" in ticker.lower() or "-gop" in ticker.lower() or "rep " in combined:
        rep_price = midpoint

    race_id = infer_kalshi_race_id(ticker, event_ticker, title)

    return {
        "race_id": race_id,
        "ticker": ticker,
        "event_ticker": event_ticker,
        "title": title,
        "subtitle": subtitle,
        "dem_price": dem_price,
        "rep_price": rep_price,
        "yes_price": midpoint,
        "last_price_cents": last_price,
        "yes_bid_cents": yes_bid,
        "yes_ask_cents": yes_ask,
        "volume_24h": market.get("volume_24h", 0),
        "volume_total": market.get("volume", 0),
        "open_interest": market.get("open_interest", 0),
        "status": market.get("status", ""),
        "close_time": market.get("close_time", ""),
    }


def infer_kalshi_race_id(ticker, event_ticker, title):
    """Infer a canonical race_id from Kalshi identifiers."""
    state_codes = [
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
        "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
        "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
        "TX","UT","VT","VA","WA","WV","WI","WY"
    ]

    combined = (ticker + " " + event_ticker).upper()
    title_lower = title.lower()

    chamber = None
    if "SENATE" in combined or "SEATE" in combined or "senate" in title_lower:
        chamber = "senate"
    elif "HOUSE" in combined or "house" in title_lower:
        chamber = "house"
    elif "GOV" in combined or "governor" in title_lower:
        chamber = "governor"
    elif "CONTROL" in combined:
        chamber = "congress"

    state_code = None
    for code in state_codes:
        if f"-{code}-" in combined or combined.endswith(f"-{code}") or f"{code}" in combined[5:9]:
            state_code = code
            break

    if not state_code:
        state_names = {
            "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR",
            "california":"CA","colorado":"CO","georgia":"GA","illinois":"IL",
            "iowa":"IA","kansas":"KS","kentucky":"KY","maine":"ME",
            "michigan":"MI","minnesota":"MN","montana":"MT","nebraska":"NE",
            "new hampshire":"NH","north carolina":"NC","ohio":"OH",
            "oregon":"OR","south carolina":"SC","texas":"TX",
            "virginia":"VA","florida":"FL","massachusetts":"MA",
            "new jersey":"NJ","tennessee":"TN","mississippi":"MS",
        }
        for name, code in state_names.items():
            if name in title_lower:
                state_code = code
                break

    district = None
    if chamber == "house":
        dist_match = re.search(r'(\d+)', ticker.split("HOUSE")[-1] if "HOUSE" in combined else "")
        if dist_match:
            district = dist_match.group(1)

    if chamber and state_code:
        if district:
            return f"{chamber}-{state_code}-{district}-2026"
        return f"{chamber}-{state_code}-2026"
    elif chamber:
        return f"{chamber}-control-2026"

    return f"kalshi-{ticker[:50]}"


def fetch_all_election_markets():
    """
    Main entry point.
    1. Fetch series list (~1 call)
    2. Identify election series (~50-80 tickers)
    3. Fetch markets per series (~1-2 calls each)
    Total: ~60-100 calls instead of 100+ pages of all markets.
    """
    print("[Kalshi] Fetching 2026 election markets...")

    # Step 1: Discover election series
    print("  Step 1: Fetching series list...")
    all_series = fetch_series_list()
    election_series = discover_election_series(all_series)
    print(f"  Found {len(election_series)} election-related series")

    # Step 2: Fetch markets for each series
    print(f"  Step 2: Fetching markets for {len(election_series)} series...")
    all_markets = []
    sorted_series = sorted(election_series)
    for i, series_ticker in enumerate(sorted_series):
        markets = fetch_markets_for_series(series_ticker)
        if markets:
            all_markets.extend(markets)
        if (i + 1) % 20 == 0 or i == len(sorted_series) - 1:
            print(f"    ... {i+1}/{len(sorted_series)} series done, "
                  f"{len(all_markets)} markets so far")
        time.sleep(0.3)  # Light delay — each call returns 1-5 markets

    print(f"  Done: {len(all_markets)} raw markets from {len(election_series)} series")

    # Only keep markets that parsed to a real race ID
    valid_prefixes = ("senate-", "house-", "governor-", "congress-")
    records = []
    for m in all_markets:
        r = parse_kalshi_market(m)
        if r["race_id"].startswith(valid_prefixes):
            records.append(r)

    print(f"  Kept {len(records)} with valid race IDs (filtered {len(all_markets) - len(records)})")
    return records, all_markets


if __name__ == "__main__":
    records, raw = fetch_all_election_markets()
    for r in records[:15]:
        print(f"  {r['race_id']:30s}  ticker:{r['ticker']:25s}  "
              f"D:{r['dem_price']}  R:{r['rep_price']}  "
              f"last:{r['last_price_cents']}¢")
    print(f"\nTotal: {len(records)} election markets")
