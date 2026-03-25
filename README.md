# 2026 Midterm Election Tracker

**Prediction Markets vs. the Polls** — A journalism project tracking Polymarket and Kalshi odds alongside public polling for every competitive 2026 Senate, House, and Governor race, plus all tracked primary contests.

Live dashboard: [tomwp1116.github.io/midterm-tracker](https://tomwp1116.github.io/midterm-tracker)

---

## What this does

1. **Collects data four times a day** via GitHub Actions (4 AM, 10 AM, 4 PM, 10 PM UTC) from three sources:
   - **Polymarket** (Gamma API, no auth) — Senate, governor, and House control markets
   - **Kalshi** (public REST API, no auth) — all 35 Senate seats, ~90 competitive House districts, governor races, and primary candidate markets
   - **Wikipedia** (web scrape) — individual polls as released

2. **Stores everything** in a SQLite database with daily market snapshots, individual poll results, computed summaries, and per-candidate primary snapshots. Raw API responses are archived as JSON.

3. **Exports `docs/data/dashboard_data.json`** — the single file that powers the frontend, rebuilt on every run.

4. **Displays a live dashboard** hosted on GitHub Pages with:
   - Market odds from Polymarket and Kalshi side by side
   - A **Trend** column showing 7-day market movement (Steady / Moderate Shift / Major Shift / New Leader)
   - Latest poll results with expandable detail views
   - Interactive charts overlaying market odds and rolling poll averages
   - Primary race tracking with per-candidate Kalshi market odds
   - A ★ flag for races where prediction markets and polls disagree
   - A completed-races archive with winner banners and historical charts

---

## Project structure

```
midterm-tracker/
├── config.py                          # Paths, API endpoints, race registry
├── setup_db.py                        # Initialize SQLite schema
├── real_inventory.py                  # Populate DB with known 2026 races
├── build_dashboard_json.py            # Utility: add House district races + export JSON
├── scripts/
│   ├── daily_snapshot.py              # Orchestrator: fetch → store → export
│   ├── fetch_polymarket.py            # Polymarket Gamma API fetcher
│   ├── fetch_kalshi.py                # Kalshi public API fetcher
│   ├── fetch_polls.py                 # Wikipedia poll scraper
│   ├── fetch_primary_markets.py       # Per-candidate primary market fetcher
│   ├── fetch_nbc_calendar.py          # NBC races-to-watch calendar
│   ├── backfill_kalshi_history.py     # Backfill historical Kalshi data
│   ├── backfill_polymarket_history.py # Backfill historical Polymarket data
│   └── backfill_primary_kalshi_history.py
├── src/
│   ├── App.jsx                        # React dashboard (single component)
│   └── main.jsx                       # Vite entry point
├── docs/                              # Built output — served by GitHub Pages
│   ├── index.html
│   ├── assets/                        # Compiled JS bundle
│   └── data/
│       └── dashboard_data.json        # Live data file
├── data/
│   └── midterms.db                    # SQLite database
├── archive/                           # Daily raw JSON snapshots
└── .github/workflows/
    └── daily_snapshot.yml             # GitHub Actions automation
```

---

## How it runs

The GitHub Actions workflow (`.github/workflows/daily_snapshot.yml`) runs four times a day:

```
0 4,10,16,22 * * *
```

Each run:
1. Checks out the repo
2. Runs `setup_db.py` (idempotent schema init)
3. Runs `real_inventory.py` (upserts known race metadata)
4. Runs `scripts/daily_snapshot.py` (fetches all data, writes DB, exports JSON)
5. Commits `data/midterms.db` and `docs/data/dashboard_data.json` back to the repo

GitHub Pages automatically serves the updated `docs/` on every push.

---

## Running locally

```bash
git clone https://github.com/tomwp1116/midterm-tracker.git
cd midterm-tracker
pip install -r requirements.txt
python setup_db.py
python real_inventory.py
python scripts/daily_snapshot.py
```

To run the frontend locally:

```bash
npm install
npm run dev
```

To build for production (outputs to `docs/`):

```bash
npm run build
```

---

## Dashboard features

### Filters
The top navigation filters the race table by chamber: **Primaries**, Senate, House, Governor, Control markets. Each filter is independently sortable.

### Sorting
Click any column header to sort. Available sorts: Race (A→Z), Rating (competitiveness), Polymarket odds, Kalshi odds, Latest Poll date, and Trend (movement level).

### Trend column
Reflects how much a race's prediction market odds have shifted over the past seven days:
- **Steady** — under 3 percentage points of movement
- **Moderate Shift** — 3–7 point move
- **Major Shift** — 7+ point move
- **New Leader** — the previously favored candidate has fallen behind

### Detail view
Click any row to expand a full chart for that race showing the 30-day market history, a rolling poll average overlay, and individual poll release markers. Primary race charts show per-candidate market prices as multi-colored lines.

### Completed races
Resolved primaries and general elections appear in a separate section at the bottom with winner banners, final vote percentages, and ✅/❌ indicators for whether prediction markets and polls called the winner correctly.

---

## How new races appear

The fetcher scripts discover most markets dynamically — searching Kalshi by series ticker patterns and Polymarket by tags and known slugs. When a new competitive district or governor race opens on either platform, the next run picks it up automatically.

Primary races are configured explicitly in `config.py` (`PRIMARY_RACES` dict), which maps each race to its Kalshi series and candidate list. Results are auto-detected when Kalshi settles the market or Polymarket marks it inactive, and written to `data/primary_results.json`.

---

## Methodology

**Market odds** represent the Democratic candidate's win probability (or the leading Dem candidate's probability in primaries). Polymarket prices are read directly from `outcomePrices`. Kalshi prices use the bid/ask midpoint when the spread is tight; otherwise fall back to last trade price.

**Polls** record topline two-way or multi-candidate results with pollster, date, and a `spread` label. A rolling 30-day average is computed at export time.

**Race IDs** follow `{chamber}-{state}-{year}` for general elections (e.g. `senate-GA-2026`) and `primary-{state}-{chamber}-{party}-{year}` for partisan primaries.

**Market/Poll disagreement** (★) is flagged when the prediction market leader and the polling leader differ, based on the most recent poll within the last 90 days.

---

## Tech stack

| Layer | Tech |
|---|---|
| Data collection | Python 3, `requests` |
| Storage | SQLite via `sqlite3` |
| Frontend | React 19, Recharts, Vite |
| Hosting | GitHub Pages (`docs/` folder) |
| Automation | GitHub Actions |
