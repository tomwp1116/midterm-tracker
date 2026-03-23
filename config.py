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
# primary_results.json stores resolved primary outcomes (auto-detected + manually entered)
PRIMARY_RESULTS_PATH = DATA_DIR / "primary_results.json"

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

# ── Wikipedia Polling Data ─────────────────────────────
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia bot policy requires a descriptive User-Agent with contact info
WIKIPEDIA_USER_AGENT = (
    "MidtermTracker/1.0 (https://tomwp1116.github.io/midterm-tracker/) "
    "python-requests/2.x"
)

# ── General Settings ───────────────────────────────────
USER_AGENT = (
    "MidtermTracker/1.0 (https://tomwp1116.github.io/midterm-tracker/) "
    "python-requests/2.x"
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

# States using a nonpartisan "top-two" primary (all candidates on one ballot,
# top N finishers advance regardless of party). In our coverage only CA qualifies.
NONPARTISAN_PRIMARY_STATES = {"CA"}   # map to top_n: {"CA": 2}

# States with gubernatorial races in 2026
GOVERNOR_STATES_2026 = [
    "AL", "AK", "AZ", "CA", "CO", "CT", "FL", "GA", "HI", "ID",
    "IL", "IA", "KS", "ME", "MA", "MI", "MN", "NE", "NH", "NJ",
    "NM", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "VT", "WI", "WY"
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
        "primary_date": "2026-03-03",
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
        "primary_date": "2026-03-03",
    },
    "primary-TX-senate-D-2026": {
        "state": "TX", "chamber": "senate", "party": "D",
        "description": "Texas Senate Democratic Primary",
        "kalshi_series": "KXSENATETXD",
        "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-AR-senate-R-2026": {
        "state": "AR", "chamber": "senate", "party": "R",
        "description": "Arkansas Senate Republican Primary",
        "kalshi_series": None,
        "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-AR-senate-D-2026": {
        "state": "AR", "chamber": "senate", "party": "D",
        "description": "Arkansas Senate Democratic Primary",
        "kalshi_series": None,
        "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    # ── Governor primaries (completed) ─────────────────────────────────────
    "primary-TX-governor-R-2026": {
        "state": "TX", "chamber": "governor", "party": "R",
        "description": "Texas Governor Republican Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-TX-governor-D-2026": {
        "state": "TX", "chamber": "governor", "party": "D",
        "description": "Texas Governor Democratic Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-AR-governor-D-2026": {
        "state": "AR", "chamber": "governor", "party": "D",
        "description": "Arkansas Governor Democratic Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-IL-governor-R-2026": {
        "state": "IL", "chamber": "governor", "party": "R",
        "description": "Illinois Governor Republican Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-17",
    },
    # ── House primaries — NBC Races to Watch (completed) ──────────────────
    "primary-house-NC-01-R-2026": {
        "state": "NC", "chamber": "house", "party": "R", "district": "01",
        "description": "NC-01 Republican Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-house-NC-04-D-2026": {
        "state": "NC", "chamber": "house", "party": "D", "district": "04",
        "description": "NC-04 Democratic Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-house-NC-11-R-2026": {
        "state": "NC", "chamber": "house", "party": "R", "district": "11",
        "description": "NC-11 Republican Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    "primary-house-NC-11-D-2026": {
        "state": "NC", "chamber": "house", "party": "D", "district": "11",
        "description": "NC-11 Democratic Primary",
        "kalshi_series": None, "pm_slug": None,
        "primary_date": "2026-03-03",
    },
    # ── Additional Senate Republican primaries ─────────────────────────────
    "primary-CO-senate-R-2026": {
        "state": "CO", "chamber": "senate", "party": "R",
        "description": "Colorado Senate Republican Primary",
        "kalshi_series": "KXSENATECOR",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-FL-senate-R-2026": {
        "state": "FL", "chamber": "senate", "party": "R",
        "description": "Florida Senate Republican Primary",
        "kalshi_series": "KXSENATEFLR",
        "pm_slug": None,
        "primary_date": "2026-08-18",
    },
    "primary-IA-senate-R-2026": {
        "state": "IA", "chamber": "senate", "party": "R",
        "description": "Iowa Senate Republican Primary",
        "kalshi_series": "KXSENATEIAR",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-KY-senate-R-2026": {
        "state": "KY", "chamber": "senate", "party": "R",
        "description": "Kentucky Senate Republican Primary",
        "kalshi_series": "KXSENATEKYR",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-MA-senate-R-2026": {
        "state": "MA", "chamber": "senate", "party": "R",
        "description": "Massachusetts Senate Republican Primary",
        "kalshi_series": "KXSENATEMAR",
        "pm_slug": None,
        "primary_date": "2026-09-15",
    },
    "primary-ME-senate-R-2026": {
        "state": "ME", "chamber": "senate", "party": "R",
        "description": "Maine Senate Republican Primary",
        "kalshi_series": "KXSENATEMER",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-MI-senate-R-2026": {
        "state": "MI", "chamber": "senate", "party": "R",
        "description": "Michigan Senate Republican Primary",
        "kalshi_series": "KXSENATEMIR",
        "pm_slug": None,
        "primary_date": "2026-08-04",
    },
    "primary-MN-senate-R-2026": {
        "state": "MN", "chamber": "senate", "party": "R",
        "description": "Minnesota Senate Republican Primary",
        "kalshi_series": "KXSENATEMNR",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
    "primary-MS-senate-R-2026": {
        "state": "MS", "chamber": "senate", "party": "R",
        "description": "Mississippi Senate Republican Primary",
        "kalshi_series": "KXSENATEMSR",
        "pm_slug": None,
        "primary_date": "2026-03-10",
    },
    "primary-MT-senate-R-2026": {
        "state": "MT", "chamber": "senate", "party": "R",
        "description": "Montana Senate Republican Primary",
        "kalshi_series": "KXSENATEMTR",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-OR-senate-R-2026": {
        "state": "OR", "chamber": "senate", "party": "R",
        "description": "Oregon Senate Republican Primary",
        "kalshi_series": "KXSENATEORR",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-SC-senate-R-2026": {
        "state": "SC", "chamber": "senate", "party": "R",
        "description": "South Carolina Senate Republican Primary",
        "kalshi_series": "KXSENATESCR",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-VA-senate-R-2026": {
        "state": "VA", "chamber": "senate", "party": "R",
        "description": "Virginia Senate Republican Primary",
        "kalshi_series": "KXSENATEVAR",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-WV-senate-R-2026": {
        "state": "WV", "chamber": "senate", "party": "R",
        "description": "West Virginia Senate Republican Primary",
        "kalshi_series": "KXSENATEWVR",
        "pm_slug": None,
        "primary_date": "2026-05-12",
    },
    "primary-WY-senate-R-2026": {
        "state": "WY", "chamber": "senate", "party": "R",
        "description": "Wyoming Senate Republican Primary",
        "kalshi_series": "KXSENATEWYR",
        "pm_slug": None,
        "primary_date": "2026-08-18",
    },
    # ── Additional Senate Democratic primaries ─────────────────────────────
    "primary-CO-senate-D-2026": {
        "state": "CO", "chamber": "senate", "party": "D",
        "description": "Colorado Senate Democratic Primary",
        "kalshi_series": "KXSENATECOD",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-FL-senate-D-2026": {
        "state": "FL", "chamber": "senate", "party": "D",
        "description": "Florida Senate Democratic Primary",
        "kalshi_series": "KXSENATEFLD",
        "pm_slug": None,
        "primary_date": "2026-08-18",
    },
    "primary-GA-senate-D-2026": {
        "state": "GA", "chamber": "senate", "party": "D",
        "description": "Georgia Senate Democratic Primary",
        "kalshi_series": "KXSENATEGAD",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-IA-senate-D-2026": {
        "state": "IA", "chamber": "senate", "party": "D",
        "description": "Iowa Senate Democratic Primary",
        "kalshi_series": "KXKXSENATEIAD",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-MA-senate-D-2026": {
        "state": "MA", "chamber": "senate", "party": "D",
        "description": "Massachusetts Senate Democratic Primary",
        "kalshi_series": "KXSENATEMAD",
        "pm_slug": None,
        "primary_date": "2026-09-15",
    },
    "primary-MN-senate-D-2026": {
        "state": "MN", "chamber": "senate", "party": "D",
        "description": "Minnesota Senate Democratic Primary",
        "kalshi_series": "KXSENATEMND",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
    "primary-OR-senate-D-2026": {
        "state": "OR", "chamber": "senate", "party": "D",
        "description": "Oregon Senate Democratic Primary",
        "kalshi_series": "KXSENATEORD",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-SC-senate-D-2026": {
        "state": "SC", "chamber": "senate", "party": "D",
        "description": "South Carolina Senate Democratic Primary",
        "kalshi_series": "KXSENATESCD",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-VA-senate-D-2026": {
        "state": "VA", "chamber": "senate", "party": "D",
        "description": "Virginia Senate Democratic Primary",
        "kalshi_series": "KXSENATEVAD",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-WV-senate-D-2026": {
        "state": "WV", "chamber": "senate", "party": "D",
        "description": "West Virginia Senate Democratic Primary",
        "kalshi_series": "KXSENATEWVD",
        "pm_slug": None,
        "primary_date": "2026-05-12",
    },
    # ── Governor Democratic nomination primaries ───────────────────────────
    # California uses a nonpartisan top-two primary: all candidates on one ballot,
    # top 2 advance to the general regardless of party.
    "primary-CA-governor-2026": {
        "state": "CA", "chamber": "governor", "party": None,
        "description": "California Governor Primary",
        "kalshi_series": "KXGOVCAPRIMARY",  # unified top-two market
        "nonpartisan": True,
        "top_n": 2,
        "pm_slug": "who-will-advance-from-the-california-governor-primary",
        "primary_date": "2026-06-02",
    },
    "primary-CO-governor-D-2026": {
        "state": "CO", "chamber": "governor", "party": "D",
        "description": "Colorado Governor Democratic Primary",
        "kalshi_series": "KXGOVCONOMD",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-FL-governor-D-2026": {
        "state": "FL", "chamber": "governor", "party": "D",
        "description": "Florida Governor Democratic Primary",
        "kalshi_series": "KXGOVFLNOMD",
        "pm_slug": None,
        "primary_date": "2026-08-18",
    },
    "primary-GA-governor-D-2026": {
        "state": "GA", "chamber": "governor", "party": "D",
        "description": "Georgia Governor Democratic Primary",
        "kalshi_series": "KXGOVGANOMD",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-ME-governor-D-2026": {
        "state": "ME", "chamber": "governor", "party": "D",
        "description": "Maine Governor Democratic Primary",
        "kalshi_series": "KXGOVMENOMD",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-MI-governor-D-2026": {
        "state": "MI", "chamber": "governor", "party": "D",
        "description": "Michigan Governor Democratic Primary",
        "kalshi_series": "KXGOVMINOMD",
        "pm_slug": None,
        "primary_date": "2026-08-04",
    },
    "primary-MN-governor-D-2026": {
        "state": "MN", "chamber": "governor", "party": "D",
        "description": "Minnesota Governor Democratic Primary",
        "kalshi_series": "KXGOVMNNOMD",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
    "primary-NH-governor-D-2026": {
        "state": "NH", "chamber": "governor", "party": "D",
        "description": "New Hampshire Governor Democratic Primary",
        "kalshi_series": "KXGOVNHNOMD",
        "pm_slug": None,
        "primary_date": "2026-09-08",
    },
    "primary-NJ-governor-D-2026": {
        "state": "NJ", "chamber": "governor", "party": "D",
        "description": "New Jersey Governor Democratic Primary",
        "kalshi_series": "KXGOVNJNOMD",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-NM-governor-D-2026": {
        "state": "NM", "chamber": "governor", "party": "D",
        "description": "New Mexico Governor Democratic Primary",
        "kalshi_series": "KXGOVNMNOMD",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-NY-governor-D-2026": {
        "state": "NY", "chamber": "governor", "party": "D",
        "description": "New York Governor Democratic Primary",
        "kalshi_series": "KXGOVNYNOMD",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-OH-governor-D-2026": {
        "state": "OH", "chamber": "governor", "party": "D",
        "description": "Ohio Governor Democratic Primary",
        "kalshi_series": "KXGOVOHNOMD",
        "pm_slug": None,
        "primary_date": "2026-05-05",
    },
    "primary-PA-governor-D-2026": {
        "state": "PA", "chamber": "governor", "party": "D",
        "description": "Pennsylvania Governor Democratic Primary",
        "kalshi_series": "KXGOVPANOMD",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-WI-governor-D-2026": {
        "state": "WI", "chamber": "governor", "party": "D",
        "description": "Wisconsin Governor Democratic Primary",
        "kalshi_series": "KXGOVWINOMD",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
    # ── Governor Republican nomination primaries ───────────────────────────
    "primary-AZ-governor-R-2026": {
        "state": "AZ", "chamber": "governor", "party": "R",
        "description": "Arizona Governor Republican Primary",
        "kalshi_series": "KXGOVAZNOMR",
        "pm_slug": None,
        "primary_date": "2026-08-25",
    },
    "primary-CO-governor-R-2026": {
        "state": "CO", "chamber": "governor", "party": "R",
        "description": "Colorado Governor Republican Primary",
        "kalshi_series": "KXGOVCONOMR",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-FL-governor-R-2026": {
        "state": "FL", "chamber": "governor", "party": "R",
        "description": "Florida Governor Republican Primary",
        "kalshi_series": "KXGOVFLNOMR",
        "pm_slug": None,
        "primary_date": "2026-08-18",
    },
    "primary-GA-governor-R-2026": {
        "state": "GA", "chamber": "governor", "party": "R",
        "description": "Georgia Governor Republican Primary",
        "kalshi_series": "KXGOVGANOMR",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-ME-governor-R-2026": {
        "state": "ME", "chamber": "governor", "party": "R",
        "description": "Maine Governor Republican Primary",
        "kalshi_series": "KXGOVMENOMR",
        "pm_slug": None,
        "primary_date": "2026-06-09",
    },
    "primary-MI-governor-R-2026": {
        "state": "MI", "chamber": "governor", "party": "R",
        "description": "Michigan Governor Republican Primary",
        "kalshi_series": "KXGOVMINOMR",
        "pm_slug": None,
        "primary_date": "2026-08-04",
    },
    "primary-MN-governor-R-2026": {
        "state": "MN", "chamber": "governor", "party": "R",
        "description": "Minnesota Governor Republican Primary",
        "kalshi_series": "KXGOVMNNOMR",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
    "primary-NJ-governor-R-2026": {
        "state": "NJ", "chamber": "governor", "party": "R",
        "description": "New Jersey Governor Republican Primary",
        "kalshi_series": "KXGOVNJNOMR",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-NM-governor-R-2026": {
        "state": "NM", "chamber": "governor", "party": "R",
        "description": "New Mexico Governor Republican Primary",
        "kalshi_series": "KXGOVNMNOMR",
        "pm_slug": None,
        "primary_date": "2026-06-02",
    },
    "primary-NY-governor-R-2026": {
        "state": "NY", "chamber": "governor", "party": "R",
        "description": "New York Governor Republican Primary",
        "kalshi_series": "KXGOVNYNOMR",
        "pm_slug": None,
        "primary_date": "2026-06-23",
    },
    "primary-OH-governor-R-2026": {
        "state": "OH", "chamber": "governor", "party": "R",
        "description": "Ohio Governor Republican Primary",
        "kalshi_series": "KXGOVOHNOMR",
        "pm_slug": None,
        "primary_date": "2026-05-05",
    },
    "primary-PA-governor-R-2026": {
        "state": "PA", "chamber": "governor", "party": "R",
        "description": "Pennsylvania Governor Republican Primary",
        "kalshi_series": "KXGOVPANOMR",
        "pm_slug": None,
        "primary_date": "2026-05-19",
    },
    "primary-WI-governor-R-2026": {
        "state": "WI", "chamber": "governor", "party": "R",
        "description": "Wisconsin Governor Republican Primary",
        "kalshi_series": "KXGOVWINOMR",
        "pm_slug": None,
        "primary_date": "2026-08-11",
    },
}
