"""
Fetch NBC News 2026 Primary Elections Calendar.

Hits the public NBC Firecracker API and returns the set of race_ids
that NBC has marked as "Race to Watch". No authentication required.

Matching logic:
  - Senate label  → senate-{STATE}-2026 + primary-{STATE}-senate-{D,R}-2026
  - House label   → house-{STATE}-{ZZ}-2026  (district zero-padded to 2 digits)
  - Governor label → governor-{STATE}-2026 + primary-{STATE}-governor-{D,R}-2026
"""
import requests
from config import USER_AGENT, REQUEST_TIMEOUT

NBC_CALENDAR_URL = (
    "https://www.nbcnews.com/firecracker/api/v2"
    "/national-results/2026-primary-elections/calendar"
)

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Referer": "https://www.nbcnews.com/politics/2026-primary-elections/calendar",
}

_STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def _label_to_race_ids(state_code, office, house_number):
    """Map a single NBC calendar label to the race_ids it covers in our system."""
    o = office.lower()
    if o == "senate":
        return [
            f"senate-{state_code}-2026",
            f"primary-{state_code}-senate-R-2026",
            f"primary-{state_code}-senate-D-2026",
        ]
    if o == "house" and house_number:
        try:
            district = str(int(house_number)).zfill(2)
        except (ValueError, TypeError):
            district = str(house_number)
        return [f"house-{state_code}-{district}-2026"]
    if o in ("governor", "gubernatorial"):
        return [
            f"governor-{state_code}-2026",
            f"primary-{state_code}-governor-R-2026",
            f"primary-{state_code}-governor-D-2026",
        ]
    return []


def _iter_date_entries(data):
    """Yield every date-entry dict from the NBC API response."""
    # Data lives under data['page'], not at the top level
    page = data.get("page", data)
    for month in page.get("months", []):
        yield from month.get("dates", [])
    rbd = page.get("racesByCurrentDate", {})
    yield from rbd.get("upcoming", [])
    yield from rbd.get("past", [])


def fetch_nbc_races_to_watch():
    """
    Return a set of race_ids that NBC News has flagged as "Race to Watch".
    Returns an empty set on any network/parse error (safe default — won't
    wipe existing flags in the database).
    """
    try:
        resp = requests.get(NBC_CALENDAR_URL, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[NBC Calendar] Fetch failed: {e}")
        return set()

    races_to_watch = set()
    for date_entry in _iter_date_entries(data):
        for state_entry in date_entry.get("states", []):
            state_code = _STATE_CODES.get(state_entry.get("name", ""))
            if not state_code:
                continue
            for label in state_entry.get("labels", []):
                if not label.get("raceToWatch"):
                    continue
                for rid in _label_to_race_ids(
                    state_code,
                    label.get("office", ""),
                    label.get("houseNumber"),
                ):
                    races_to_watch.add(rid)
                    print(f"[NBC] Race to Watch: {rid}")

    print(f"[NBC Calendar] {len(races_to_watch)} race_ids flagged")
    return races_to_watch
