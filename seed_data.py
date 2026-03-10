"""
Seed the database with sample data based on real 2026 midterm race data,
so the dashboard and exports have something to display.
"""
import sqlite3
import random
from datetime import date, timedelta
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ── Races ──────────────────────────────────────────────
races = [
    # Senate races
    ("senate-GA-2026", "senate", "GA", None, "Georgia Senate — Ossoff (D-inc) vs. TBD (R)"),
    ("senate-NC-2026", "senate", "NC", None, "North Carolina Senate — Tillis (R-inc) vs. TBD (D)"),
    ("senate-TX-2026", "senate", "TX", None, "Texas Senate — Cornyn (R-inc) vs. TBD (D)"),
    ("senate-ME-2026", "senate", "ME", None, "Maine Senate — Collins (R-inc) vs. TBD (D)"),
    ("senate-MI-2026", "senate", "MI", None, "Michigan Senate — Peters (D-inc) vs. TBD (R)"),
    ("senate-NH-2026", "senate", "NH", None, "New Hampshire Senate — Shaheen (D-open) vs. TBD (R)"),
    ("senate-OH-2026", "senate", "OH", None, "Ohio Senate — Open (R-held)"),
    ("senate-IL-2026", "senate", "IL", None, "Illinois Senate — Durbin (D-open) vs. TBD (R)"),
    ("senate-KY-2026", "senate", "KY", None, "Kentucky Senate — McConnell (R-open)"),
    ("senate-MA-2026", "senate", "MA", None, "Massachusetts Senate — Markey (D-inc) vs. TBD (R)"),
    ("senate-MN-2026", "senate", "MN", None, "Minnesota Senate — Klobuchar (D-inc) vs. TBD (R)"),
    ("senate-FL-2026", "senate", "FL", None, "Florida Senate — Open (R-held)"),
    ("senate-SC-2026", "senate", "SC", None, "South Carolina Senate — Graham (R-inc) vs. TBD (D)"),
    ("senate-VA-2026", "senate", "VA", None, "Virginia Senate — Warner (D-inc) vs. TBD (R)"),
    # House races (competitive)
    ("house-NY-17-2026", "house", "NY", "17", "New York 17th — Lawler (R-inc) vs. TBD (D)"),
    ("house-CA-27-2026", "house", "CA", "27", "California 27th — Garcia (R-inc) vs. TBD (D)"),
    ("house-PA-10-2026", "house", "PA", "10", "Pennsylvania 10th — Perry (R-open) vs. TBD (D)"),
    ("house-MI-7-2026", "house", "MI", "7", "Michigan 7th — Slotkin (D-open) vs. TBD (R)"),
    ("house-AZ-6-2026", "house", "AZ", "6", "Arizona 6th — Ciscomani (R-inc) vs. TBD (D)"),
    ("house-NE-2-2026", "house", "NE", "2", "Nebraska 2nd — Bacon (R-inc) vs. TBD (D)"),
    # Overall control
    ("senate-control-2026", "senate", "US", None, "Senate Control — Democrats vs. Republicans"),
    ("house-control-2026", "house", "US", None, "House Control — Democrats vs. Republicans"),
]

for r in races:
    c.execute("""
        INSERT OR IGNORE INTO races (race_id, chamber, state, district, description)
        VALUES (?, ?, ?, ?, ?)
    """, r)

# ── Market Snapshots (simulate 30 days of data) ───────
start_date = date(2026, 2, 7)
base_odds = {
    "senate-GA-2026":       (0.48, 0.52),
    "senate-NC-2026":       (0.42, 0.58),
    "senate-TX-2026":       (0.28, 0.72),
    "senate-ME-2026":       (0.58, 0.42),
    "senate-MI-2026":       (0.62, 0.38),
    "senate-NH-2026":       (0.55, 0.45),
    "senate-OH-2026":       (0.38, 0.62),
    "senate-IL-2026":       (0.75, 0.25),
    "senate-KY-2026":       (0.22, 0.78),
    "senate-MA-2026":       (0.82, 0.18),
    "senate-MN-2026":       (0.68, 0.32),
    "senate-FL-2026":       (0.35, 0.65),
    "senate-SC-2026":       (0.30, 0.70),
    "senate-VA-2026":       (0.65, 0.35),
    "house-NY-17-2026":     (0.52, 0.48),
    "house-CA-27-2026":     (0.48, 0.52),
    "house-PA-10-2026":     (0.50, 0.50),
    "house-MI-7-2026":      (0.45, 0.55),
    "house-AZ-6-2026":      (0.44, 0.56),
    "house-NE-2-2026":      (0.46, 0.54),
    "senate-control-2026":  (0.85, 0.16),
    "house-control-2026":   (0.58, 0.48),
}

random.seed(42)
for day_offset in range(31):
    snap_date = (start_date + timedelta(days=day_offset)).isoformat()
    for rid, (base_dem, base_rep) in base_odds.items():
        # Add random walk
        drift = random.gauss(0, 0.015)
        pm_dem = round(min(0.99, max(0.01, base_dem + drift + day_offset * 0.001)), 3)
        pm_rep = round(1 - pm_dem, 3)
        # Kalshi slightly different
        k_dem = round(min(0.99, max(0.01, pm_dem + random.gauss(0, 0.02))), 3)
        k_rep = round(1 - k_dem, 3)
        vol_pm = round(random.uniform(5000, 500000), 0)
        vol_k = round(random.uniform(2000, 200000), 0)
        
        c.execute("""
            INSERT OR REPLACE INTO market_snapshots
                (race_id, snapshot_date, pm_dem_price, pm_rep_price,
                 pm_volume_24h, k_dem_price, k_rep_price, k_volume_24h)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (rid, snap_date, pm_dem, pm_rep, vol_pm, k_dem, k_rep, vol_k))

# ── Polls ──────────────────────────────────────────────
sample_polls = [
    ("senate-GA-2026", "2026-03-05", "Emerson", "Ossoff", 48, "Collins", 43, 5),
    ("senate-GA-2026", "2026-03-05", "Emerson", "Ossoff", 47, "Carter", 44, 3),
    ("senate-GA-2026", "2026-02-18", "Quinnipiac", "Ossoff", 50, "Collins", 42, 8),
    ("senate-ME-2026", "2026-03-09", "Quantus Insights", "Platner", 49, "Collins", 42, 7),
    ("senate-ME-2026", "2026-03-09", "Quantus Insights", "Mills", 43, "Collins", 45, -2),
    ("senate-NC-2026", "2026-02-25", "PPP", "Generic D", 44, "Tillis", 47, -3),
    ("senate-NC-2026", "2026-03-02", "SurveyUSA", "Generic D", 46, "Tillis", 45, 1),
    ("senate-TX-2026", "2026-03-01", "Emerson", "Generic D", 38, "Cornyn", 52, -14),
    ("senate-TX-2026", "2026-02-20", "UT-Tyler", "Generic D", 40, "Cruz-replacement", 49, -9),
    ("senate-MI-2026", "2026-02-28", "Mitchell Research", "Peters", 51, "Generic R", 40, 11),
    ("senate-NH-2026", "2026-02-22", "UNH", "Generic D", 48, "Ayotte", 44, 4),
    ("senate-OH-2026", "2026-02-15", "Emerson", "Generic D", 42, "Generic R", 48, -6),
    ("senate-IL-2026", "2026-03-01", "Victory Research", "Pritzker", 55, "Generic R", 32, 23),
    ("house-NY-17-2026", "2026-02-20", "Siena", "Generic D", 49, "Lawler", 46, 3),
    ("house-CA-27-2026", "2026-02-25", "SurveyUSA", "Generic D", 47, "Garcia", 48, -1),
    ("house-AZ-6-2026", "2026-03-03", "OHPI", "Generic D", 46, "Ciscomani", 48, -2),
]

for p in sample_polls:
    c.execute("""
        INSERT OR IGNORE INTO polls
            (race_id, poll_date, pollster, candidate_1, candidate_1_pct,
             candidate_2, candidate_2_pct, spread, detected_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], date.today().isoformat()))

# ── Daily Summaries ────────────────────────────────────
for day_offset in range(31):
    snap_date = (start_date + timedelta(days=day_offset)).isoformat()
    for rid, (base_dem, base_rep) in base_odds.items():
        drift = random.gauss(0, 0.01)
        m_dem = round(min(0.99, max(0.01, base_dem + drift + day_offset * 0.001)), 3)
        m_rep = round(1 - m_dem, 3)
        
        c.execute("""
            INSERT OR REPLACE INTO daily_summary
                (race_id, summary_date, market_dem_pct, market_rep_pct,
                 pm_dem_pct, k_dem_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rid, snap_date, m_dem, m_rep,
              round(m_dem + random.gauss(0, 0.01), 3),
              round(m_dem + random.gauss(0, 0.01), 3)))

conn.commit()
conn.close()
print("Database seeded with sample data.")
print(f"  {len(races)} races")
print(f"  ~{len(base_odds) * 31} market snapshots")
print(f"  {len(sample_polls)} polls")
