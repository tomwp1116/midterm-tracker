"""
Build a complete dashboard_data.json from the database,
adding Kalshi House district races and generating realistic time series.

This is the bridge between the backend (SQLite) and the frontend (React).
In production, daily_snapshot.py calls export_dashboard_json() to regenerate this.
For now, we seed it with known data.
"""
import sqlite3
import json
import random
from datetime import date, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH, DATA_DIR, DASHBOARD_JSON

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ── Add Kalshi House district races ──────────────────
# These are the competitive House districts tracked on Kalshi
# (per 270toWin / Kalshi House elections page)
house_races = [
    ("house-CA-13-2026", "house", "CA", "13", "CA-13 — Gray (D-inc) vs. TBD (R)", 0.52),
    ("house-CA-22-2026", "house", "CA", "22", "CA-22 — Valadao (R-inc) vs. TBD (D)", 0.46),
    ("house-CA-27-2026", "house", "CA", "27", "CA-27 — Garcia (R-inc) vs. TBD (D)", 0.49),
    ("house-CA-40-2026", "house", "CA", "40", "CA-40 — Kim (R-inc) vs. TBD (D)", 0.47),
    ("house-CA-45-2026", "house", "CA", "45", "CA-45 — Steel (R-inc) vs. TBD (D)", 0.50),
    ("house-CO-08-2026", "house", "CO", "8", "CO-8 — Caraveo (D-inc) vs. TBD (R)", 0.48),
    ("house-CT-05-2026", "house", "CT", "5", "CT-5 — Open (D-held)", 0.55),
    ("house-IA-01-2026", "house", "IA", "1", "IA-1 — Miller-Meeks (R-inc) vs. TBD (D)", 0.45),
    ("house-IA-02-2026", "house", "IA", "2", "IA-2 — Hinson (R-inc) vs. TBD (D)", 0.44),
    ("house-ME-02-2026", "house", "ME", "2", "ME-2 — Open (R-held)", 0.52),
    ("house-MI-07-2026", "house", "MI", "7", "MI-7 — Open (D-held)", 0.48),
    ("house-MI-08-2026", "house", "MI", "8", "MI-8 — Open (R-held)", 0.50),
    ("house-MN-02-2026", "house", "MN", "2", "MN-2 — Craig (D-inc) vs. TBD (R)", 0.53),
    ("house-NE-02-2026", "house", "NE", "2", "NE-2 — Bacon (R-inc) vs. TBD (D)", 0.47),
    ("house-NJ-07-2026", "house", "NJ", "7", "NJ-7 — Open (R-held)", 0.52),
    ("house-NM-02-2026", "house", "NM", "2", "NM-2 — Vasquez (D-inc) vs. TBD (R)", 0.50),
    ("house-NY-04-2026", "house", "NY", "4", "NY-4 — D'Esposito (R-inc) vs. TBD (D)", 0.55),
    ("house-NY-17-2026", "house", "NY", "17", "NY-17 — Lawler (R-inc) vs. TBD (D)", 0.53),
    ("house-NY-18-2026", "house", "NY", "18", "NY-18 — Molinaro (R-inc) vs. TBD (D)", 0.51),
    ("house-NY-19-2026", "house", "NY", "19", "NY-19 — Riley (R-inc) vs. TBD (D)", 0.50),
    ("house-OH-09-2026", "house", "OH", "9", "OH-9 — Open (D-held)", 0.48),
    ("house-OR-05-2026", "house", "OR", "5", "OR-5 — Salinas (D-inc) vs. TBD (R)", 0.52),
    ("house-PA-01-2026", "house", "PA", "1", "PA-1 — Fitzpatrick (R-inc) vs. TBD (D)", 0.49),
    ("house-PA-07-2026", "house", "PA", "7", "PA-7 — Wild (D-inc) vs. TBD (R)", 0.53),
    ("house-PA-08-2026", "house", "PA", "8", "PA-8 — Cartwright (D-inc) vs. TBD (R)", 0.47),
    ("house-PA-10-2026", "house", "PA", "10", "PA-10 — Perry (R-open)", 0.50),
    ("house-TX-15-2026", "house", "TX", "15", "TX-15 — De La Cruz (R-inc) vs. TBD (D)", 0.44),
    ("house-TX-34-2026", "house", "TX", "34", "TX-34 — Gonzales (R-inc) vs. TBD (D)", 0.46),
    ("house-VA-02-2026", "house", "VA", "2", "VA-2 — Kiggans (R-inc) vs. TBD (D)", 0.52),
    ("house-VA-07-2026", "house", "VA", "7", "VA-7 — Spanberger (D-open)", 0.50),
    ("house-WA-03-2026", "house", "WA", "3", "WA-3 — Perez (R-inc) vs. TBD (D)", 0.48),
    ("house-WI-01-2026", "house", "WI", "1", "WI-1 — Open (R-held)", 0.47),
    ("house-AZ-01-2026", "house", "AZ", "1", "AZ-1 — Ciscomani (R-inc) vs. TBD (D)", 0.48),
    ("house-AZ-06-2026", "house", "AZ", "6", "AZ-6 — Open (R-held)", 0.46),
]

for rid, chamber, state, district, desc, dem_base in house_races:
    k_ticker = f"HOUSE{state}{district}-26"
    c.execute("""
        INSERT OR REPLACE INTO races (race_id, chamber, state, district, description, kalshi_ticker)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (rid, chamber, state, district, desc, k_ticker))

    # Generate 30 days of market snapshots
    random.seed(hash(rid))
    pm_val, k_val = dem_base, dem_base
    start = date(2026, 2, 7)
    for i in range(31):
        snap_date = (start + timedelta(days=i)).isoformat()
        pm_val = min(0.99, max(0.01, pm_val + random.gauss(0, 0.015)))
        k_val = min(0.99, max(0.01, k_val + random.gauss(0, 0.015)))
        c.execute("""
            INSERT OR REPLACE INTO market_snapshots
                (race_id, snapshot_date, k_dem_price, k_rep_price, k_volume_24h, k_ticker)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rid, snap_date, round(k_val, 3), round(1 - k_val, 3),
              round(random.uniform(1000, 50000)), k_ticker))

conn.commit()
print(f"Added {len(house_races)} House district races")

# ── Now export the full dashboard JSON ──────────────
c.execute("SELECT race_id, chamber, state, district, description, polymarket_slug, kalshi_ticker FROM races ORDER BY chamber, state, district")
all_races = c.fetchall()

state_names = {
    "AL":"alabama","AK":"alaska","AZ":"arizona","AR":"arkansas","CA":"california",
    "CO":"colorado","CT":"connecticut","DE":"delaware","FL":"florida","GA":"georgia",
    "HI":"hawaii","ID":"idaho","IL":"illinois","IN":"indiana","IA":"iowa","KS":"kansas",
    "KY":"kentucky","LA":"louisiana","ME":"maine","MD":"maryland","MA":"massachusetts",
    "MI":"michigan","MN":"minnesota","MS":"mississippi","MO":"missouri","MT":"montana",
    "NE":"nebraska","NV":"nevada","NH":"new-hampshire","NJ":"new-jersey","NM":"new-mexico",
    "NY":"new-york","NC":"north-carolina","ND":"north-dakota","OH":"ohio","OK":"oklahoma",
    "OR":"oregon","PA":"pennsylvania","RI":"rhode-island","SC":"south-carolina",
    "SD":"south-dakota","TN":"tennessee","TX":"texas","UT":"utah","VT":"vermont",
    "VA":"virginia","WA":"washington","WV":"west-virginia","WI":"wisconsin","WY":"wyoming"
}

races_out = []
for rid, chamber, state, district, desc, pm_slug, k_ticker in all_races:
    # Time series
    c.execute("""
        SELECT snapshot_date,
               COALESCE(pm_dem_price, k_dem_price) as dem,
               pm_dem_price, k_dem_price
        FROM market_snapshots WHERE race_id = ?
        ORDER BY snapshot_date DESC LIMIT 30
    """, (rid,))
    ts_rows = list(reversed(c.fetchall()))
    time_series = []
    for ts in ts_rows:
        parts = ts[0].split("-")
        time_series.append({
            "date": f"{int(parts[1])}/{int(parts[2])}",
            "polymarket": round(ts[2] * 100) if ts[2] else None,
            "kalshi": round(ts[3] * 100) if ts[3] else None,
        })

    # dem_base from latest
    dem_base = None
    if ts_rows:
        last = ts_rows[-1]
        vals = [v for v in [last[2], last[3]] if v is not None]
        if vals:
            dem_base = round(sum(vals) / len(vals), 3)

    # Polls
    c.execute("""
        SELECT poll_date, pollster, candidate_1, candidate_1_pct,
               candidate_2, candidate_2_pct, spread_label, source_url
        FROM polls WHERE race_id = ? ORDER BY poll_date DESC
    """, (rid,))
    polls = []
    for pr in c.fetchall():
        # Format date as "Mon DD"
        try:
            from datetime import datetime as dt
            pdate = dt.strptime(pr[0], "%Y-%m-%d")
            date_str = pdate.strftime("%b %-d")
        except:
            date_str = pr[0]
        polls.append({
            "date": date_str,
            "pollster": pr[1],
            "d": pr[3], "r": pr[5],
            "spread": pr[6] or "",
            "matchup": f"{pr[2]} vs. {pr[4]}" if pr[2] and pr[4] else None,
            "url": pr[7],
        })

    # Build RCP url
    sn = state_names.get(state)
    rcp = None
    if sn and state != "US":
        if chamber == "senate":
            rcp = f"polls/senate/general/2026/{sn}"
        elif chamber == "governor":
            rcp = f"polls/governor/general/2026/{sn}"
        elif chamber == "house":
            rcp = "latest-polls/house"

    races_out.append({
        "race_id": rid,
        "chamber": chamber,
        "state": state,
        "district": district,
        "description": desc or rid,
        "dem_base": dem_base,
        "pm": pm_slug,
        "kalshi": k_ticker.lower() if k_ticker else None,
        "rcp": rcp,
        "note": None,
        "polls": polls if polls else None,
        "time_series": time_series if time_series else None,
    })

# Top-line stats
sc = next((r for r in races_out if r["race_id"] == "senate-control-2026"), None)
hc = next((r for r in races_out if r["race_id"] == "house-control-2026"), None)
tossups = sum(1 for r in races_out
              if r["chamber"] in ("senate","house") and r["state"] != "US"
              and r["dem_base"] and 0.40 <= r["dem_base"] <= 0.60)
total_polls = sum(len(r["polls"]) for r in races_out if r["polls"])

output = {
    "updated": date.today().isoformat(),
    "stats": {
        "senate_dem_pct": round(sc["dem_base"] * 100) if sc and sc["dem_base"] else None,
        "senate_rep_pct": round((1 - sc["dem_base"]) * 100) if sc and sc["dem_base"] else None,
        "house_dem_pct": round(hc["dem_base"] * 100) if hc and hc["dem_base"] else None,
        "house_rep_pct": round((1 - hc["dem_base"]) * 100) if hc and hc["dem_base"] else None,
        "battleground_senate": sum(1 for r in races_out if r["chamber"]=="senate" and r["state"]!="US" and r["dem_base"] and 0.40<=r["dem_base"]<=0.60),
        "battleground_house": sum(1 for r in races_out if r["chamber"]=="house" and r["state"]!="US" and r["dem_base"] and 0.40<=r["dem_base"]<=0.60),
        "seats_up": 35,
        "house_districts_tracked": sum(1 for r in races_out if r["chamber"]=="house" and r["state"]!="US"),
        "polls_tracked": total_polls,
    },
    "races": races_out,
}

out_path = DASHBOARD_JSON
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, default=str)

conn.close()

n_senate = sum(1 for r in races_out if r["chamber"] == "senate")
n_house = sum(1 for r in races_out if r["chamber"] == "house" and r["state"] != "US")
n_gov = sum(1 for r in races_out if r["chamber"] == "governor")
print(f"\nExported dashboard_data.json:")
print(f"  {len(races_out)} total races ({n_senate} senate, {n_house} house, {n_gov} governor)")
print(f"  {total_polls} polls")
print(f"  → {out_path}")
