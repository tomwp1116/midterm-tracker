"""
Initialize the SQLite database for the 2026 Midterm Election Tracker.
Run once: python setup_db.py
"""
import sqlite3
from config import DB_PATH, DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ── 1. Races: canonical list of tracked races ─────────
c.execute("""
CREATE TABLE IF NOT EXISTS races (
    race_id         TEXT PRIMARY KEY,   -- e.g. 'senate-GA-2026'
    chamber         TEXT NOT NULL,      -- 'senate', 'house', 'governor'
    state           TEXT NOT NULL,      -- two-letter state code
    district        TEXT,               -- NULL for senate/gov, number for house
    year            INTEGER DEFAULT 2026,
    race_type       TEXT,               -- 'general', 'primary-D', 'primary-R'
    incumbent       TEXT,               -- name of incumbent if any
    description     TEXT,               -- human-readable label
    polymarket_slug TEXT,               -- slug/event ID on Polymarket
    kalshi_ticker   TEXT,               -- market ticker on Kalshi
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── 2. Market Snapshots: daily prediction market odds ──
c.execute("""
CREATE TABLE IF NOT EXISTS market_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id         TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    -- Polymarket data
    pm_dem_price    REAL,    -- Democratic candidate price (0-1 probability)
    pm_rep_price    REAL,    -- Republican candidate price
    pm_volume_24h   REAL,    -- 24-hour trading volume in USD
    pm_event_slug   TEXT,    -- Polymarket event slug for verification
    -- Kalshi data
    k_dem_price     REAL,    -- Kalshi Democratic price (0-1, converted from cents)
    k_rep_price     REAL,    -- Kalshi Republican price
    k_volume_24h    REAL,    -- 24-hour volume
    k_ticker        TEXT,    -- Kalshi market ticker for verification
    -- Metadata
    captured_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, snapshot_date),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
)
""")

# ── 3. Polls: individual poll results ─────────────────
c.execute("""
CREATE TABLE IF NOT EXISTS polls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id         TEXT NOT NULL,
    poll_date       DATE NOT NULL,       -- date poll was released/published
    pollster        TEXT NOT NULL,
    sample_size     INTEGER,
    margin_of_error REAL,
    -- Results: stored as candidate_name: percentage pairs
    candidate_1     TEXT,
    candidate_1_pct REAL,
    candidate_2     TEXT,
    candidate_2_pct REAL,
    candidate_3     TEXT,                -- for primaries with 3+ candidates
    candidate_3_pct REAL,
    spread          REAL,                -- candidate_1_pct - candidate_2_pct
    spread_label    TEXT,                -- e.g. 'Ossoff +5'
    source_url      TEXT,                -- link to pollster's release
    rcp_url         TEXT,                -- link on RealClearPolling
    -- Metadata
    detected_date   DATE,                -- when our scraper first found it
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, poll_date, pollster),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
)
""")

# ── 4. Daily Summary: aggregated per-race per-day ─────
c.execute("""
CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id         TEXT NOT NULL,
    summary_date    DATE NOT NULL,
    -- Market consensus (average of Polymarket + Kalshi where available)
    market_dem_pct  REAL,    -- consensus Dem win probability
    market_rep_pct  REAL,    -- consensus Rep win probability
    pm_dem_pct      REAL,    -- Polymarket Dem price
    k_dem_pct       REAL,    -- Kalshi Dem price
    -- Polling average
    poll_avg_dem    REAL,    -- rolling average of recent polls (Dem %)
    poll_avg_rep    REAL,    -- rolling average (Rep %)
    poll_count      INTEGER, -- number of polls in the average
    -- Divergence
    market_poll_gap REAL,    -- market_dem_pct - poll_avg_dem (positive = markets more bullish on Dem)
    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, summary_date),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
)
""")

# ── 5. Scrape Log: track each run ─────────────────────
c.execute("""
CREATE TABLE IF NOT EXISTS scrape_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date        DATE NOT NULL,
    source          TEXT NOT NULL,        -- 'polymarket', 'kalshi', 'rcp'
    status          TEXT NOT NULL,        -- 'success', 'partial', 'error'
    markets_found   INTEGER DEFAULT 0,
    records_saved   INTEGER DEFAULT 0,
    error_message   TEXT,
    duration_secs   REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Indexes ────────────────────────────────────────────
c.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_date ON market_snapshots(snapshot_date)")
c.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_race ON market_snapshots(race_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_polls_race ON polls(race_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_polls_date ON polls(poll_date)")
c.execute("CREATE INDEX IF NOT EXISTS idx_summary_race ON daily_summary(race_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summary(summary_date)")

conn.commit()
conn.close()

print(f"Database initialized at: {DB_PATH}")
print("Tables created: races, market_snapshots, polls, daily_summary, scrape_log")
