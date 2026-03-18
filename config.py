"""
Configuration for 2026 Midterm Election Tracker
"""
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ARCHIVE_DIR = BASE_DIR / "archive"
DB_PATH = DATA_DIR / "midterms.db"
# dashboard_data.json must live inside docs/ so GitHub Pages can serve it
DASHBOARD_JSON = BASE_DIR / "docs" / "data" / "dashboard_data.json"

# ── Polymarket (Gamma API — no auth needed) ────────────
POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"
POLYMARKET_EVENTS_URL = f"{POLYMARKET_GAMMA_BASE}/events"
POLYMARKET_MARKETS_URL = f"{POLYMARKET_GAMMA_BASE}/markets"
# Tags/slugs to search for midterm markets
POLYMARKET_SEARCH_TAGS = ["midterms", "senate", "house-elections"]
POLYMARKET_SEARCH_QUERIES = [
    "2026 senate", "2026 house", "midterm", "2026 governor"
]

# ── Kalshi (Public REST API — no auth for market data) ─
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_MARKETS_URL = f"{KALSHI_BASE}/markets"
KALSHI_EVENTS_URL = f"{KALSHI_BASE}/events"
KALSHI_SERIES_URL = f"{KALSHI_BASE}/series"
# Known series tickers for 2026 elections
KALSHI_ELECTION_SERIES = [
    "KXSENATE26",   # Senate control
    "KXHOUSE26",    # House control
    # Individual state races use event tickers — discovered dynamically
]
# Search terms to find election markets
KALSHI_SEARCH_TERMS = ["senate", "house", "midterm", "2026"]

# ── FiveThirtyEight Polling Data (public CSVs, no auth) ───────────────
FTE_BASE = "https://projects.fivethirtyeight.com/polls-page/data"
FTE_SENATE_CSV = f"{FTE_BASE}/senate_polls.csv"
FTE_HOUSE_CSV = f"{FTE_BASE}/house_polls.csv"
FTE_GOVERNOR_CSV = f"{FTE_BASE}/governor_polls.csv"

# ── General Settings ───────────────────────────────────
USER_AGENT = (
    "MidtermTracker/1.0 (Journalism Research Project; "
    "contact: your-email@example.com)"
)
REQUEST_DELAY_SECONDS = 1.5  # Polite delay between API calls
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# ── Race ID Helpers ────────────────────────────────────
# States with Senate races in 2026 (Class II seats + specials)
SENATE_STATES_2026 = [
    "AL", "AK", "AR", "CO", "DE", "GA", "IA", "ID", "IL", "KS",
    "KY", "LA", "MA", "ME", "MI", "MN", "MS", "MT", "NC", "NE",
    "NH", "NJ", "NM", "OK", "OR", "RI", "SC", "SD", "TN", "TX",
    "VA", "WV", "WY"
]

# ── Primary Market Races (curated list with verified Kalshi/Polymarket sources) ─
# Maps race_id → metadata. Add new races here when discovered.
PRIMARY_RACES = {
    # ── Senate Republican primaries / runoffs ──────────────────────────
    "primary-TX-senate-R-2026": {
        "state": "TX", "chamber": "senate", "party": "R",
        "description": "Texas Senate Republican Primary Runoff",
        "kalshi_series": "KXSENATETXR",
        "pm_slug": None,
        "primary_date": "2026-05-27",
    },
    "primary-GA-senate-R-2026": {
        "state": "GA", "chamber": "senate", "party": "R",
        "description": "Georgia Senate Republican Primary",
        "kalshi_series": "KXSENATEGAR",
        "pm_slug": "georgia-republican-senate-primary-winner",
        "primary_date": "2026-05-19",
    },
    "primary-NJ-senate-R-2026": {
        "state": "NJ", "chamber": "senate", "party": "R",
        "description": "New Jersey Senate Republican Primary",
        "kalshi_series": "KXSENATENJR",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-NH-senate-R-2026": {
        "state": "NH", "chamber": "senate", "party": "R",
        "description": "New Hampshire Senate Republican Primary",
        "kalshi_series": "KXSENATENHR",
        "pm_slug": None,
        "primary_date": "2026-09-08",
    },
    "primary-NC-senate-R-2026": {
        "state": "NC", "chamber": "senate", "party": "R",
        "description": "North Carolina Senate Republican Primary",
        "kalshi_series": "KXSENATENCR",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    # ── Senate Democratic primaries ────────────────────────────────────
    "primary-IL-senate-D-2026": {
        "state": "IL", "chamber": "senate", "party": "D",
        "description": "Illinois Senate Democratic Primary",
        "kalshi_series": "KXSENATEILD",
        "pm_slug": None,
        "primary_date": "2026-03-17",
    },
    "primary-ME-senate-D-2026": {
        "state": "ME", "chamber": "senate", "party": "D",
        "description": "Maine Senate Democratic Primary",
        "kalshi_series": "KXSENATEMED",
        "pm_slug": "maine-democratic-senate-primary-winner",
        "primary_date": "2026-06-09",
    },
    "primary-MI-senate-D-2026": {
        "state": "MI", "chamber": "senate", "party": "D",
        "description": "Michigan Senate Democratic Primary",
        "kalshi_series": "KXSENATEMID",
        "pm_slug": "michigan-democratic-senate-primary-winner",
        "primary_date": "2026-08-04",
    },
    "primary-NH-senate-D-2026": {
        "state": "NH", "chamber": "senate", "party": "D",
        "description": "New Hampshire Senate Democratic Primary",
        "kalshi_series": "KXSENATENHD",
        "pm_slug": None,
        "primary_date": "2026-09-08",
    },
    "primary-NC-senate-D-2026": {
        "state": "NC", "chamber": "senate", "party": "D",
        "description": "North Carolina Senate Democratic Primary",
        "kalshi_series": "KXSENATENCD",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-TX-senate-D-2026": {
        "state": "TX", "chamber": "senate", "party": "D",
        "description": "Texas Senate Democratic Primary",
        "kalshi_series": "KXSENATETXD",
        "pm_slug": None,
        "primary_date": "2026-03-03",
        # Resolved — Talarico won the March 3 primary
        "result": {
            "winner": "James Talarico", "party": "D", "date": "Mar 3",
            "pct": 58.2, "runner_up": "Jasmine Crockett", "runner_up_pct": 41.8,
        },
    },
}
