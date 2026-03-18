"""
Fetch 2026 midterm election markets from Polymarket's Gamma API.
No authentication required.

Gamma API: https://gamma-api.polymarket.com
Docs: https://docs.polymarket.com/market-data/overview

STRATEGY:
  1. Fetch events by tag ("midterms") — returns event objects with nested markets
  2. Also fetch individual events by known slugs for races we're tracking
  3. Parse each market, keeping only those that resolve to real race IDs

The key insight: the /events endpoint returns objects with a "title" field
(e.g., "Georgia Senate Election Winner") and a nested "markets" array.
Each market has "question", "outcomePrices", "outcomes", etc.
"""
import json
import time
import re
import requests
from datetime import date, datetime
from config import (
    POLYMARKET_GAMMA_BASE, USER_AGENT, REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

# Tags to search
TAGS = ["midterms", "senate-elections", "house-elections", "governor-midterms"]

# Known event slugs for races we want to track
# (These are the URL slugs from polymarket.com/event/<slug>)
KNOWN_SLUGS = [
    "which-party-will-win-the-senate-in-2026",
    "which-party-will-win-the-house-in-2026",
    "balance-of-power-2026-midterms",
    "georgia-senate-election-winner",
    "michigan-senate-election-winner",
    "north-carolina-senate-election-winner",
    "maine-senate-election-winner",
    "alaska-senate-election-winner",
    "new-hampshire-senate-election-winner",
    "texas-senate-election-winner",
    "nebraska-senate-election-winner",
    "west-virginia-senate-election-winner",
    "new-york-governor-winner-2026",
    "new-mexico-governor-winner-2026",
    "alaska-governor-election-winner",
    "rhode-island-governor-winner-2026",
    "blue-wave-in-2026",
    "georgia-republican-senate-primary-winner",
    "maine-democratic-senate-primary-winner",
    "michigan-democratic-senate-primary-winner",
]

# State mapping for race ID inference
STATE_MAP = {
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


def fetch_events_by_tag(tag, limit=100):
    """Fetch events by tag. Returns list of event objects."""
    url = f"{POLYMARKET_GAMMA_BASE}/events"
    params = {"tag": tag, "closed": "false", "limit": limit}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception as e:
        print(f"  [PM] Error fetching tag '{tag}': {e}")
        return []


def fetch_event_by_slug(slug):
    """Fetch a single event by its slug."""
    url = f"{POLYMARKET_GAMMA_BASE}/events/slug/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # API may return a single event object or a list
        if isinstance(data, list):
            return data[0] if data else None
        return data
    except Exception as e:
        # Slug may not exist or may have changed
        return None


def extract_markets_from_event(event):
    """
    Extract market records from an event object.
    
    An event looks like:
    {
      "title": "Georgia Senate Election Winner",
      "slug": "georgia-senate-election-winner",
      "markets": [
        {"question": "Will the Democrats win...", "outcomePrices": "[\"0.81\",\"0.19\"]", ...},
        {"question": "Will the Republicans win...", "outcomePrices": "[\"0.19\",\"0.81\"]", ...}
      ]
    }
    """
    event_title = (event.get("title") or "").lower()
    event_slug = event.get("slug") or ""
    markets_list = event.get("markets") or []

    # If no nested markets, treat the event itself as a market
    if not markets_list:
        markets_list = [event]

    results = []
    for m in markets_list:
        question = (m.get("question") or m.get("title") or "").strip()
        slug = m.get("slug") or event_slug
        
        # Parse prices
        prices_raw = m.get("outcomePrices") or "[]"
        if isinstance(prices_raw, str):
            try:
                prices = json.loads(prices_raw)
            except json.JSONDecodeError:
                prices = []
        else:
            prices = prices_raw or []

        outcomes_raw = m.get("outcomes") or "[]"
        if isinstance(outcomes_raw, str):
            try:
                outcomes = json.loads(outcomes_raw)
            except json.JSONDecodeError:
                outcomes = []
        else:
            outcomes = outcomes_raw or []

        yes_price = float(prices[0]) if len(prices) > 0 else None
        no_price = float(prices[1]) if len(prices) > 1 else None

        # Determine party
        dem_price, rep_price = None, None
        text = (question + " " + event_title + " " + " ".join(outcomes)).lower()
        
        if "democrat" in text:
            dem_price = yes_price
            rep_price = no_price
        elif "republican" in text:
            rep_price = yes_price
            dem_price = no_price

        # Infer race ID from the event title + question
        combined = (event_title + " " + question + " " + event_slug).lower()
        race_id = infer_race_id(combined, event_slug)

        results.append({
            "race_id": race_id,
            "question": question,
            "slug": event_slug,
            "condition_id": m.get("conditionId") or "",
            "dem_price": dem_price,
            "rep_price": rep_price,
            "yes_price": yes_price,
            "no_price": no_price,
            "outcomes": outcomes,
            "volume_24h": m.get("volume24hr") or m.get("volume") or 0,
            "active": m.get("active", True),
        })

    return results


def infer_race_id(text, slug):
    """Infer a canonical race_id from combined event/market text."""
    # Explicit slug overrides — prevents compound/unrelated markets from
    # hijacking control race IDs via the generic inference logic below.
    SLUG_OVERRIDES = {
        "which-party-will-win-the-senate-in-2026": "senate-control-2026",
        "which-party-will-win-the-house-in-2026":  "house-control-2026",
    }
    if slug in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[slug]

    # Reject compound/multi-race markets that would otherwise map to control IDs
    SLUG_BLOCKLIST = {
        "will-democrats-win-all-core-four-senate-races",
        "balance-of-power-2026-midterms",
        "blue-wave-in-2026",
    }
    if slug in SLUG_BLOCKLIST:
        return f"pm-blocked-{slug[:40]}"

    t = text.lower()

    # Find chamber
    chamber = None
    if "senate" in t:
        chamber = "senate"
    elif "house" in t:
        chamber = "house"
    elif "governor" in t:
        chamber = "governor"
    elif "balance of power" in t or "trifecta" in t or "sweep" in t:
        chamber = "congress"

    # Find state — sort longest-first so "west virginia" matches before "virginia",
    # "north carolina" before "carolina", "new mexico" before "mexico", etc.
    state_code = None
    for name, code in sorted(STATE_MAP.items(), key=lambda x: -len(x[0])):
        if name in t:
            state_code = code
            break

    # District for house
    district = None
    if chamber == "house":
        dist_match = re.search(r'district\s*(\d+)', t)
        if dist_match:
            district = dist_match.group(1)

    if chamber and state_code:
        if district:
            return f"{chamber}-{state_code}-{district}-2026"
        return f"{chamber}-{state_code}-2026"
    elif chamber and state_code is None and chamber in ("senate", "house"):
        return f"{chamber}-control-2026"
    elif chamber == "congress":
        return f"congress-control-2026"

    # No match — return None-like value that will be filtered out
    return f"pm-{slug[:60]}" if slug else "pm-unknown"


def fetch_all_midterm_markets():
    """
    Main entry point.
    1. Fetch events by known tags
    2. Fetch events by known slugs (catches ones tags might miss)
    3. Parse and deduplicate
    4. Keep only markets with valid race IDs
    """
    print("[Polymarket] Fetching 2026 midterm markets...")
    seen_conditions = set()
    all_records = []

    # Method 1: Fetch by tags
    for tag in TAGS:
        events = fetch_events_by_tag(tag)
        for event in events:
            markets = extract_markets_from_event(event)
            for record in markets:
                cid = record.get("condition_id", "")
                key = cid or record["race_id"] + record.get("question", "")
                if key and key not in seen_conditions:
                    seen_conditions.add(key)
                    all_records.append(record)
        time.sleep(0.5)

    # Method 2: Fetch by known slugs
    for slug in KNOWN_SLUGS:
        event = fetch_event_by_slug(slug)
        if event:
            markets = extract_markets_from_event(event)
            for record in markets:
                cid = record.get("condition_id", "")
                key = cid or record["race_id"] + record.get("question", "")
                if key and key not in seen_conditions:
                    seen_conditions.add(key)
                    all_records.append(record)
        time.sleep(0.3)

    # Filter: keep only general-election markets with valid race IDs.
    # Primary/nominee sub-markets (e.g. "Will X be the nominee?", "Will X win
    # the primary?") map to the same race_id as the general election but carry
    # unrelated prices that would corrupt general-election charts.
    valid_prefixes = ("senate-", "house-", "governor-", "congress-")
    primary_keywords = ("primary", "nominee", "be the ", "runoff")

    records = []
    for r in all_records:
        if not r["race_id"].startswith(valid_prefixes):
            continue
        q = r.get("question", "").lower()
        if any(kw in q for kw in primary_keywords):
            continue
        records.append(r)

    raw = all_records  # archive everything for debugging

    print(f"  Found {len(all_records)} raw markets, kept {len(records)} general-election markets")
    return records, raw


if __name__ == "__main__":
    records, raw = fetch_all_midterm_markets()
    for r in records[:15]:
        print(f"  {r['race_id']:30s}  D:{r['dem_price']}  R:{r['rep_price']}  "
              f"Q:{r['question'][:50]}")
    print(f"\nTotal: {len(records)} markets")
