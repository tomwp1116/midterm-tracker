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

# ── RealClearPolling ───────────────────────────────────
RCP_BASE = "https://www.realclearpolling.com"
RCP_LATEST_2026 = f"{RCP_BASE}/latest-polls/2026"
RCP_SENATE_POLLS = f"{RCP_BASE}/latest-polls/senate"
RCP_HOUSE_POLLS = f"{RCP_BASE}/latest-polls/house"
RCP_GOVERNOR_POLLS = f"{RCP_BASE}/latest-polls/governor"

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
