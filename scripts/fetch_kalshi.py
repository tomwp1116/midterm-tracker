"""
Fetch 2026 midterm election markets from Kalshi's public REST API.
No authentication required for reading market data.

Kalshi API docs: https://docs.kalshi.com
Base URL: https://api.elections.kalshi.com/trade-api/v2

Key endpoints:
  GET /markets?status=open                → all open markets
  GET /markets?event_ticker=<TICKER>      → markets for a specific event
  GET /events?status=open                 → event listings
  GET /series/<TICKER>                    → series info
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

# Known Kalshi election-related series/event ticker prefixes
ELECTION_PREFIXES = [
    "KXSENATE", "KXHOUSE", "KXGOV",
    "KXCONGRESS", "KXMIDTERM",
    # State-specific patterns: KXSENATE-GA, etc.
]

# Keywords to identify 2026 election markets in titles
ELECTION_KEYWORDS = [
    "senate", "house", "congress", "midterm", "2026",
    "governor", "representative", "congressional"
]


def fetch_markets_page(cursor=None, limit=200, status="open", event_ticker=None,
                       series_ticker=None, tickers=None):
    """Fetch a page of Kalshi markets."""
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if status:
        params["status"] = status
    if event_ticker:
        params["event_ticker"] = event_ticker
    if series_ticker:
        params["series_ticker"] = series_ticker
    if tickers:
        params["tickers"] = tickers
    
    try:
        resp = requests.get(KALSHI_MARKETS_URL, params=params,
                           headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("markets", []), data.get("cursor", None)
    except Exception as e:
        print(f"  [Kalshi] Error fetching markets: {e}")
        return [], None


def fetch_all_open_markets():
    """Paginate through all open Kalshi markets."""
    all_markets = []
    cursor = None
    page = 0
    while True:
        page += 1
        markets, next_cursor = fetch_markets_page(cursor=cursor, limit=1000)
        all_markets.extend(markets)
        print(f"  [Kalshi] Page {page}: fetched {len(markets)} markets (total: {len(all_markets)})")
        if not next_cursor or not markets:
            break
        cursor = next_cursor
        time.sleep(REQUEST_DELAY_SECONDS)
    return all_markets


def is_election_market(market):
    """Check if a Kalshi market is related to 2026 elections."""
    ticker = (market.get("ticker", "") + " " + market.get("event_ticker", "")).upper()
    title = (market.get("title", "") + " " + market.get("subtitle", "")).lower()
    
    # Check ticker prefixes
    for prefix in ELECTION_PREFIXES:
        if prefix in ticker:
            return True
    
    # Check title keywords — must match '2026' AND an election term
    has_2026 = "2026" in title or "2026" in ticker
    has_election_term = any(kw in title for kw in ELECTION_KEYWORDS)
    
    return has_2026 and has_election_term


def parse_kalshi_market(market):
    """
    Convert a Kalshi market object to a standardized record.
    
    Kalshi market fields:
      - ticker: "KXSENATE-GA-26-DEM"
      - title: "Will Democrats win the 2026 Georgia Senate race?"
      - yes_bid, yes_ask, last_price: in cents (0-100)
      - volume_24h: in contracts
      - event_ticker: "KXSENATE-GA-26"
    """
    ticker = market.get("ticker", "")
    event_ticker = market.get("event_ticker", "")
    title = market.get("title", "")
    subtitle = market.get("subtitle", "")
    
    # Convert cent prices to probabilities (0-1)
    last_price = market.get("last_price")
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")
    
    # Use midpoint of bid/ask if available, else last_price
    if yes_bid is not None and yes_ask is not None:
        midpoint = (yes_bid + yes_ask) / 2.0 / 100.0
    elif last_price is not None:
        midpoint = last_price / 100.0
    else:
        midpoint = None
    
    # Determine which party this market represents
    dem_price, rep_price = None, None
    combined = (title + " " + subtitle + " " + ticker).lower()
    
    if "democrat" in combined or "-dem" in ticker.lower():
        dem_price = midpoint
    elif "republican" in combined or "-rep" in ticker.lower() or "-gop" in ticker.lower():
        rep_price = midpoint
    else:
        # Generic "party wins" market — store as yes_price
        pass
    
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
    """
    Infer a canonical race_id from Kalshi market identifiers.
    
    Kalshi tickers follow patterns like:
      KXSENATE-GA-26-DEM  → senate-GA-2026
      KXHOUSE-CA45-26     → house-CA-45-2026
    """
    state_map = {
        "AL": "AL", "AK": "AK", "AZ": "AZ", "AR": "AR", "CA": "CA",
        "CO": "CO", "CT": "CT", "DE": "DE", "FL": "FL", "GA": "GA",
        "HI": "HI", "ID": "ID", "IL": "IL", "IN": "IN", "IA": "IA",
        "KS": "KS", "KY": "KY", "LA": "LA", "ME": "ME", "MD": "MD",
        "MA": "MA", "MI": "MI", "MN": "MN", "MS": "MS", "MO": "MO",
        "MT": "MT", "NE": "NE", "NV": "NV", "NH": "NH", "NJ": "NJ",
        "NM": "NM", "NY": "NY", "NC": "NC", "ND": "ND", "OH": "OH",
        "OK": "OK", "OR": "OR", "PA": "PA", "RI": "RI", "SC": "SC",
        "SD": "SD", "TN": "TN", "TX": "TX", "UT": "UT", "VT": "VT",
        "VA": "VA", "WA": "WA", "WV": "WV", "WI": "WI", "WY": "WY"
    }
    
    combined = (ticker + " " + event_ticker).upper()
    title_lower = title.lower()
    
    # Determine chamber
    chamber = None
    if "SENATE" in combined or "senate" in title_lower:
        chamber = "senate"
    elif "HOUSE" in combined or "house" in title_lower:
        chamber = "house"
    elif "GOV" in combined or "governor" in title_lower:
        chamber = "governor"
    elif "CONGRESS" in combined:
        chamber = "congress"  # generic control market
    
    # Find state code in ticker (e.g., "-GA-")
    state_code = None
    for code in state_map:
        if f"-{code}-" in combined or f"-{code}" == combined[-3:] or combined.startswith(f"KX{code}"):
            state_code = code
            break
    
    # If not found in ticker, search title
    if not state_code:
        state_names = {
            "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
            "california": "CA", "colorado": "CO", "georgia": "GA", "illinois": "IL",
            "iowa": "IA", "kansas": "KS", "kentucky": "KY", "maine": "ME",
            "michigan": "MI", "minnesota": "MN", "montana": "MT", "nebraska": "NE",
            "new hampshire": "NH", "north carolina": "NC", "ohio": "OH",
            "oregon": "OR", "south carolina": "SC", "texas": "TX",
            "virginia": "VA", "florida": "FL", "massachusetts": "MA",
            "new jersey": "NJ", "tennessee": "TN", "mississippi": "MS",
        }
        for name, code in state_names.items():
            if name in title_lower:
                state_code = code
                break
    
    # Find district number for house races
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
    Main entry point: gather all Kalshi 2026 election markets.
    Returns (records_list, raw_data_for_archive).
    """
    print("[Kalshi] Fetching 2026 election markets...")
    
    # Fetch all open markets and filter for elections
    all_markets = fetch_all_open_markets()
    election_markets = [m for m in all_markets if is_election_market(m)]
    
    print(f"  Filtered to {len(election_markets)} election-related markets")
    
    records = [parse_kalshi_market(m) for m in election_markets]
    
    return records, election_markets


if __name__ == "__main__":
    records, raw = fetch_all_election_markets()
    for r in records[:15]:
        print(f"  {r['race_id']:30s}  ticker:{r['ticker']:25s}  "
              f"D:{r['dem_price']}  R:{r['rep_price']}  "
              f"last:{r['last_price_cents']}¢")
    print(f"\nTotal: {len(records)} election markets")
