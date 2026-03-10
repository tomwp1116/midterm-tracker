# 2026 Midterm Election Tracker

**Prediction Markets vs. the Polls** — A journalism project tracking Polymarket and Kalshi odds alongside public polling for every competitive 2026 Senate, House, and Governor race.

## What this does

1. **Collects data daily** from three sources:
   - **Polymarket** (Gamma API, no auth) — individual Senate races, governor races, control markets
   - **Kalshi** (public REST API, no auth) — all 35 Senate seats, ~34 competitive House districts, governor races
   - **RealClearPolling** (web scrape) — every new poll as released

2. **Stores everything** in a SQLite database with daily market snapshots, individual poll results, and computed summaries. Raw API responses are archived as JSON.

3. **Exports `dashboard_data.json`** — the single file that powers the frontend.

4. **Displays a dashboard** with market odds, polling, trend sparklines, expandable detail views with charts, external links, and a completed-races archive with winner banners.

## Project structure

```
midterm-tracker/
├── config.py                     # Paths, API endpoints, settings
├── setup_db.py                   # Initialize SQLite database
├── seed_data.py                  # Seed DB with sample data (testing)
├── real_inventory.py             # Populate DB with real 2026 races
├── build_dashboard_json.py       # Export DB → dashboard_data.json
├── scripts/
│   ├── fetch_polymarket.py       # Polymarket Gamma API fetcher
│   ├── fetch_kalshi.py           # Kalshi public API fetcher
│   ├── fetch_polls.py            # RealClearPolling scraper
│   └── daily_snapshot.py         # Orchestrator: fetch + store + export
├── dashboard/
│   └── midterm_dashboard.jsx     # React dashboard component
├── data/                         # Created at runtime (gitignored)
│   ├── midterms.db
│   └── dashboard_data.json
└── archive/                      # Daily raw JSON snapshots (gitignored)
```

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/midterm-tracker.git
cd midterm-tracker
pip install -r requirements.txt
python setup_db.py
python real_inventory.py
python scripts/daily_snapshot.py
```

That last command fetches live data from all three sources, populates the database, and exports `data/dashboard_data.json`.

## Automate with cron

```bash
crontab -e
# Add this line — runs nightly at 11 PM Eastern:
0 23 * * * cd /path/to/midterm-tracker && python scripts/daily_snapshot.py >> data/cron.log 2>&1
```

## The dashboard

`dashboard/midterm_dashboard.jsx` is a self-contained React component that works two ways:

**As a Claude artifact:** Upload the `.jsx` file to Claude. Data is embedded as a fallback.

**As a standalone web page:** The component tries to `fetch("dashboard_data.json")` on load. Serve both files from any static host and it uses live data. A minimal HTML wrapper:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>2026 Midterms — Markets vs. Polls</title>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/recharts@2/umd/Recharts.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel" src="midterm_dashboard.jsx"></script>
  <script type="text/babel">
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
  </script>
</body>
</html>
```

For production, use Vite or Next.js instead of in-browser Babel.

## How new races appear automatically

The fetcher scripts discover markets dynamically — they search by tags and keywords, not from a fixed list. When Kalshi opens a new House district market or Polymarket launches a new Senate race, the next daily run picks it up, writes it to the database, and exports it. No manual updates needed.

## Completed races

Any race with a `result` field is removed from the main feed and shown in a "Completed Races" section with a winner banner and historical chart. The result shape:

```json
{ "winner": "James Talarico", "party": "D", "date": "Mar 3",
  "pct": 58.2, "runner_up": "Jasmine Crockett", "runner_up_pct": 41.8 }
```

Currently, marking races complete is manual. A future improvement: detect resolved markets automatically via Kalshi's `status: "settled"` and Polymarket's `active: false`.

## Methodology

Market odds = Democratic win probability. Polymarket prices read directly; Kalshi cents converted to percentages. Polls record topline results with a `matchup` field describing what was tested. Race IDs follow `{chamber}-{state}-{year}` format. Raw JSON archives preserve exact API responses.
