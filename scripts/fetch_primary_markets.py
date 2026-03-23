"""
Fetch 2026 primary election candidate probabilities from Kalshi and Polymarket.
Uses the curated PRIMARY_RACES list from config.py.
Returns per-candidate records: [{race_id, candidate_name, party, k_price, pm_price}]
"""
import re
import json
import time
import requests
from config import (
    PRIMARY_RACES, USER_AGENT, REQUEST_TIMEOUT,
    POLYMARKET_GAMMA_BASE, KALSHI_MARKETS_URL
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

_PLACEHOLDER_RE = re.compile(r"^person [abc]$", re.IGNORECASE)


def extract_candidate_name(title):
    """Extract candidate name from Kalshi market title.
    'Will John Cornyn be the Republican nominee...' → 'John Cornyn'
    'Wil Mike Collins be the Republican nominee...' → 'Mike Collins'
    """
    m = re.match(
        r"[Ww]il(?:l)?\s+(.+?)\s+(?:be|win)\s+(?:the\s+)?(?:republican|democratic|dem|rep|gop|\d{4})\s",
        title, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    # Fallback: grab words after "Will"
    m2 = re.match(r"[Ww]il(?:l)?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", title)
    if m2:
        return m2.group(1).strip()
    return title[:40]


def _parse_kalshi_price(market):
    """Return yes price (0-1 float) or None.

    Prefers bid/ask midpoint only when the spread is tight (≤ 0.40).
    A wide spread signals an empty order book — the midpoint (e.g. 0.50 from
    bid=0.01/ask=0.99) is a placeholder, not a real probability.  Falls back
    to last-traded price, which reflects actual market activity.
    """
    yb = market.get("yes_bid_dollars")
    ya = market.get("yes_ask_dollars")
    lp = market.get("last_price_dollars")
    if yb is not None and ya is not None:
        try:
            bid, ask = float(yb), float(ya)
            if ask - bid <= 0.40:
                return (bid + ask) / 2.0
        except (ValueError, TypeError):
            pass
    if lp is not None:
        try:
            return float(lp)
        except (ValueError, TypeError):
            pass
    # Legacy integer-cent fields
    yb2 = market.get("yes_bid")
    ya2 = market.get("yes_ask")
    lp2 = market.get("last_price")
    if yb2 is not None and ya2 is not None:
        bid2, ask2 = yb2 / 100.0, ya2 / 100.0
        if ask2 - bid2 <= 0.40:
            return (bid2 + ask2) / 2.0
    if lp2 is not None:
        return lp2 / 100.0
    return None


def fetch_kalshi_candidates(series_ticker, race_id, party):
    """Fetch per-candidate markets from a Kalshi series."""
    try:
        resp = requests.get(
            KALSHI_MARKETS_URL,
            params={"series_ticker": series_ticker, "limit": 200},
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json().get("markets", [])
    except Exception as e:
        print(f"  [Primary/Kalshi] Error fetching {series_ticker}: {e}")
        return []

    # Only price candidates from actively-trading markets.
    # "finalized" markets (resolved or cancelled by Kalshi) return bid=0/ask=1,
    # which gives a misleading 50% midpoint — they must be excluded.
    ACTIVE_STATUSES = {"open", "active"}

    records = []
    for m in markets:
        if m.get("status", "").lower() not in ACTIVE_STATUSES:
            continue
        title = m.get("title", "")
        candidate = extract_candidate_name(title)
        if _PLACEHOLDER_RE.match(candidate):
            continue
        records.append({
            "race_id": race_id,
            "candidate_name": candidate,
            "party": party,
            "k_price": _parse_kalshi_price(m),
            "pm_price": None,
            "k_ticker": m.get("ticker", ""),
        })
    return records


def fetch_polymarket_candidates(pm_slug, race_id, party):
    """Fetch per-candidate markets from a Polymarket event."""
    if not pm_slug:
        return []
    url = f"{POLYMARKET_GAMMA_BASE}/events/slug/{pm_slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        event = resp.json()
    except Exception as e:
        print(f"  [Primary/Polymarket] Error fetching {pm_slug}: {e}")
        return []

    markets = event.get("markets") or []
    records = []
    for m in markets:
        question = (m.get("question") or "").strip()
        # Extract candidate name from question
        m2 = re.match(
            r"[Ww]ill?\s+(.+?)\s+(?:be|win)\s+(?:the\s+)?(?:republican|democratic|dem|rep|gop|\d{4})\s",
            question, re.IGNORECASE,
        )
        if not m2:
            m2 = re.match(r"[Ww]ill?\s+(.+?)\s+(?:be|win)", question, re.IGNORECASE)
        candidate = m2.group(1).strip() if m2 else question[:40]

        if _PLACEHOLDER_RE.match(candidate):
            continue

        prices_raw = m.get("outcomePrices") or "[]"
        if isinstance(prices_raw, str):
            try:
                prices = json.loads(prices_raw)
            except json.JSONDecodeError:
                prices = []
        else:
            prices = prices_raw or []

        if not prices:
            continue
        try:
            pm_price = float(prices[0])
        except (ValueError, TypeError):
            continue

        records.append({
            "race_id": race_id,
            "candidate_name": candidate,
            "party": party,
            "k_price": None,
            "pm_price": pm_price,
            "k_ticker": None,
        })
    return records


def merge_by_last_name(k_records, pm_records):
    """Merge Kalshi and Polymarket records using last-name fuzzy matching."""
    merged = {r["candidate_name"]: r.copy() for r in k_records}

    for pm_r in pm_records:
        pm_name = pm_r["candidate_name"]
        pm_last = pm_name.split()[-1].lower()

        matched_key = None
        if pm_name in merged:
            matched_key = pm_name
        else:
            for k_name in merged:
                k_last = k_name.split()[-1].lower()
                if pm_last == k_last:
                    matched_key = k_name
                    break

        if matched_key:
            merged[matched_key]["pm_price"] = pm_r["pm_price"]
        else:
            merged[pm_name] = pm_r.copy()

    return list(merged.values())


def fetch_all_primary_markets():
    """
    Main entry point. Iterates over PRIMARY_RACES, fetches candidate probabilities
    from Kalshi and Polymarket, and returns merged per-candidate records.
    """
    print("[Primary Markets] Fetching candidate probabilities...")
    all_records = []
    race_count = 0

    for race_id, info in PRIMARY_RACES.items():
        party = info["party"]
        k_series = info.get("kalshi_series")
        pm_slug = info.get("pm_slug")

        k_records = []
        if k_series:
            k_records = fetch_kalshi_candidates(k_series, race_id, party)
            time.sleep(0.3)

        pm_records = []
        if pm_slug:
            pm_records = fetch_polymarket_candidates(pm_slug, race_id, party)
            time.sleep(0.3)

        records = merge_by_last_name(k_records, pm_records)
        print(f"  {race_id}: {len(records)} candidates "
              f"(K:{len(k_records)} PM:{len(pm_records)})")
        all_records.extend(records)
        race_count += 1

    print(f"[Primary Markets] Done: {len(all_records)} candidate records, {race_count} races")
    return all_records


if __name__ == "__main__":
    records = fetch_all_primary_markets()
    for r in records:
        k = f"K:{r['k_price']:.2f}" if r.get('k_price') is not None else "K:—"
        p = f"PM:{r['pm_price']:.2f}" if r.get('pm_price') is not None else "PM:—"
        print(f"  {r['race_id']:35s}  {r['candidate_name']:25s}  {k}  {p}")
