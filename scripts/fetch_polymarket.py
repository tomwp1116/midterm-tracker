"""
Fetch 2026 midterm election markets from Polymarket's Gamma API.
No authentication required — all market data is public.

Polymarket Gamma API docs: https://docs.polymarket.com/market-data/overview
Base URL: https://gamma-api.polymarket.com

Key endpoints:
  GET /events?tag=midterms&closed=false   → list of event groups
  GET /markets?closed=false               → individual tradable markets
"""
import json
import time
import re
import requests
from datetime import date, datetime
from config import (
    POLYMARKET_GAMMA_BASE, POLYMARKET_SEARCH_TAGS,
    POLYMARKET_SEARCH_QUERIES, USER_AGENT, REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def fetch_events_by_tag(tag, limit=100):
    """Fetch Polymarket events by tag (e.g., 'midterms')."""
    url = f"{POLYMARKET_GAMMA_BASE}/events"
    params = {"tag": tag, "closed": "false", "limit": limit}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [Polymarket] Error fetching tag '{tag}': {e}")
        return []


def fetch_markets_by_query(query, limit=100):
    """Search Polymarket markets by text query."""
    url = f"{POLYMARKET_GAMMA_BASE}/markets"
    params = {"closed": "false", "limit": limit}
    # The Gamma API supports text search via the 'tag' or by listing active
    # markets and filtering client-side
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        all_markets = resp.json()
        # Client-side filter by query terms
        q_lower = query.lower()
        return [
            m for m in all_markets
            if q_lower in (m.get("question", "") + " " + m.get("description", "")).lower()
        ]
    except Exception as e:
        print(f"  [Polymarket] Error searching '{query}': {e}")
        return []


def parse_market_to_record(market):
    """
    Convert a Polymarket market object to a standardized record.
    
    A market has:
      - question: "Will Democrats win the 2026 Georgia Senate race?"
      - outcomePrices: '["0.62","0.38"]'  (Yes/No probabilities)
      - volume24hr: float
      - slug: URL-friendly identifier
      - conditionId: unique market ID
    """
    question = market.get("question", "")
    slug = market.get("slug", "")
    
    # Parse outcome prices
    prices_raw = market.get("outcomePrices", "[]")
    if isinstance(prices_raw, str):
        try:
            prices = json.loads(prices_raw)
        except json.JSONDecodeError:
            prices = []
    else:
        prices = prices_raw
    
    outcomes_raw = market.get("outcomes", "[]")
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw)
        except json.JSONDecodeError:
            outcomes = []
    else:
        outcomes = outcomes_raw
    
    yes_price = float(prices[0]) if len(prices) > 0 else None
    no_price = float(prices[1]) if len(prices) > 1 else None
    
    # Try to determine party from question/outcomes
    dem_price, rep_price = None, None
    question_lower = question.lower()
    outcomes_lower = [o.lower() for o in outcomes]
    
    if "democrat" in question_lower or "Democratic Party" in question:
        dem_price = yes_price
        rep_price = no_price
    elif "republican" in question_lower or "Republican Party" in question:
        rep_price = yes_price
        dem_price = no_price
    elif len(outcomes) >= 2:
        # Check outcome labels
        if any("dem" in o for o in outcomes_lower):
            dem_idx = next(i for i, o in enumerate(outcomes_lower) if "dem" in o)
            dem_price = float(prices[dem_idx]) if dem_idx < len(prices) else None
        if any("rep" in o for o in outcomes_lower):
            rep_idx = next(i for i, o in enumerate(outcomes_lower) if "rep" in o)
            rep_price = float(prices[rep_idx]) if rep_idx < len(prices) else None

    # Infer race_id from question/slug
    race_id = infer_race_id(question, slug)
    
    return {
        "race_id": race_id,
        "question": question,
        "slug": slug,
        "condition_id": market.get("conditionId", ""),
        "dem_price": dem_price,
        "rep_price": rep_price,
        "yes_price": yes_price,
        "no_price": no_price,
        "outcomes": outcomes,
        "volume_24h": market.get("volume24hr", 0),
        "volume_total": market.get("volumeNum", 0),
        "liquidity": market.get("liquidityNum", 0),
        "end_date": market.get("endDate", ""),
        "active": market.get("active", True),
    }


def infer_race_id(question, slug):
    """
    Attempt to create a canonical race_id from the market question/slug.
    
    Examples:
      "Which party will win the 2026 Georgia Senate race?" → "senate-GA-2026"
      "Who will win Texas House District 23 in 2026?"      → "house-TX-23-2026"
    """
    q = question.lower() + " " + slug.lower()
    
    # State name → abbreviation mapping
    state_map = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
        "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
        "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
        "new mexico": "NM", "new york": "NY", "north carolina": "NC",
        "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
        "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
        "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
        "vermont": "VT", "virginia": "VA", "washington": "WA",
        "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY"
    }
    
    # Find state
    state_code = None
    for name, code in state_map.items():
        if name in q:
            state_code = code
            break
    
    # Find chamber
    chamber = None
    if "senate" in q:
        chamber = "senate"
    elif "house" in q:
        chamber = "house"
    elif "governor" in q:
        chamber = "governor"
    
    # Find district for house races
    district = None
    if chamber == "house":
        dist_match = re.search(r'district\s*(\d+)', q)
        if dist_match:
            district = dist_match.group(1)
    
    if chamber and state_code:
        if district:
            return f"{chamber}-{state_code}-{district}-2026"
        return f"{chamber}-{state_code}-2026"
    
    # Fallback: use slug
    return f"pm-{slug[:60]}" if slug else f"pm-unknown-{hash(question) % 10000}"


def fetch_all_midterm_markets():
    """
    Main entry point: gather all Polymarket 2026 midterm markets.
    Returns (records_list, raw_data_for_archive).
    """
    print("[Polymarket] Fetching 2026 midterm markets...")
    all_raw = []
    seen_conditions = set()
    records = []
    
    # Method 1: Fetch by known tags
    for tag in POLYMARKET_SEARCH_TAGS:
        events = fetch_events_by_tag(tag)
        if isinstance(events, list):
            for event in events:
                markets = event.get("markets", [])
                if not markets and isinstance(event, dict):
                    markets = [event]
                for m in markets:
                    cid = m.get("conditionId", "")
                    if cid and cid not in seen_conditions:
                        seen_conditions.add(cid)
                        all_raw.append(m)
        time.sleep(REQUEST_DELAY_SECONDS)
    
    # Method 2: Search by query terms
    for query in POLYMARKET_SEARCH_QUERIES:
        matches = fetch_markets_by_query(query)
        for m in matches:
            cid = m.get("conditionId", "")
            if cid and cid not in seen_conditions:
                seen_conditions.add(cid)
                all_raw.append(m)
        time.sleep(REQUEST_DELAY_SECONDS)
    
    # Parse all discovered markets
    for raw_market in all_raw:
        record = parse_market_to_record(raw_market)
        records.append(record)
    
    print(f"  Found {len(records)} unique midterm-related markets")
    return records, all_raw


if __name__ == "__main__":
    records, raw = fetch_all_midterm_markets()
    # Pretty-print a sample
    for r in records[:10]:
        print(f"  {r['race_id']:30s}  D:{r['dem_price']}  R:{r['rep_price']}  "
              f"Vol24h:{r['volume_24h']}")
    print(f"\nTotal: {len(records)} markets")
