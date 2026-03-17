"""
Daily Snapshot Orchestrator
===========================
Runs all data fetchers, saves results to the SQLite database,
and archives raw API responses as JSON for later verification.

Usage:
  python scripts/daily_snapshot.py              # Normal daily run
  python scripts/daily_snapshot.py --dry-run    # Fetch but don't save
  python scripts/daily_snapshot.py --export     # Also export CSV summary

Schedule with cron:
  0 23 * * * cd /path/to/midterm-tracker && python scripts/daily_snapshot.py
"""
import sys
import os
import json
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path

# Add parent dir to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, ARCHIVE_DIR, DATA_DIR

# Import fetchers
from fetch_polymarket import fetch_all_midterm_markets
from fetch_kalshi import fetch_all_election_markets
from fetch_polls import fetch_all_polls


def ensure_dirs():
    """Create necessary directories."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today_dir = ARCHIVE_DIR / date.today().isoformat()
    today_dir.mkdir(parents=True, exist_ok=True)
    return today_dir


def archive_raw_data(archive_dir, polymarket_raw, kalshi_raw, polls_raw):
    """Save raw API responses as JSON for verification."""
    timestamp = datetime.now().isoformat()
    
    pm_path = archive_dir / "polymarket_raw.json"
    with open(pm_path, "w") as f:
        json.dump({
            "captured_at": timestamp,
            "source": "Polymarket Gamma API",
            "market_count": len(polymarket_raw),
            "data": polymarket_raw
        }, f, indent=2, default=str)
    
    k_path = archive_dir / "kalshi_raw.json"
    with open(k_path, "w") as f:
        json.dump({
            "captured_at": timestamp,
            "source": "Kalshi Public API",
            "market_count": len(kalshi_raw),
            "data": kalshi_raw
        }, f, indent=2, default=str)
    
    polls_path = archive_dir / "polls_raw.json"
    with open(polls_path, "w") as f:
        json.dump({
            "captured_at": timestamp,
            "source": "RealClearPolling",
            "poll_count": len(polls_raw) if isinstance(polls_raw, list) else "N/A",
            "data": polls_raw
        }, f, indent=2, default=str)
    
    print(f"[Archive] Saved raw data to {archive_dir}/")
    return pm_path, k_path, polls_path


def save_races(conn, pm_records, k_records):
    """Upsert race records into the races table."""
    c = conn.cursor()
    
    # Collect all unique race_ids with metadata
    races = {}
    
    for r in pm_records:
        rid = r["race_id"]
        if rid not in races:
            # Parse chamber and state from race_id
            parts = rid.split("-")
            chamber = parts[0] if len(parts) > 0 else "unknown"
            state = parts[1] if len(parts) > 1 else "??"
            district = parts[2] if len(parts) > 3 and parts[2].isdigit() else None
            
            races[rid] = {
                "chamber": chamber,
                "state": state,
                "district": district,
                "description": r.get("question", ""),
                "polymarket_slug": r.get("slug"),
            }
        else:
            races[rid]["polymarket_slug"] = r.get("slug")
    
    for r in k_records:
        rid = r["race_id"]
        if rid not in races:
            parts = rid.split("-")
            chamber = parts[0] if len(parts) > 0 else "unknown"
            state = parts[1] if len(parts) > 1 else "??"
            district = parts[2] if len(parts) > 3 and parts[2].isdigit() else None
            
            races[rid] = {
                "chamber": chamber,
                "state": state,
                "district": district,
                "description": r.get("title", ""),
                "kalshi_ticker": r.get("ticker"),
            }
        else:
            races[rid]["kalshi_ticker"] = r.get("ticker")
    
    for rid, info in races.items():
        c.execute("""
            INSERT INTO races (race_id, chamber, state, district, description,
                             polymarket_slug, kalshi_ticker)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(race_id) DO UPDATE SET
                description = COALESCE(excluded.description, description),
                polymarket_slug = COALESCE(excluded.polymarket_slug, polymarket_slug),
                kalshi_ticker = COALESCE(excluded.kalshi_ticker, kalshi_ticker)
        """, (
            rid, info["chamber"], info["state"], info.get("district"),
            info["description"], info.get("polymarket_slug"),
            info.get("kalshi_ticker")
        ))
    
    conn.commit()
    return len(races)


def save_market_snapshots(conn, pm_records, k_records, snapshot_date):
    """
    Save market snapshots. Merges Polymarket and Kalshi data by race_id.
    """
    c = conn.cursor()
    today = snapshot_date
    
    # Build a lookup by race_id
    snapshots = {}
    
    for r in pm_records:
        rid = r["race_id"]
        if rid not in snapshots:
            snapshots[rid] = {}
        snapshots[rid]["pm_dem_price"] = r.get("dem_price")
        snapshots[rid]["pm_rep_price"] = r.get("rep_price")
        snapshots[rid]["pm_volume_24h"] = r.get("volume_24h")
        snapshots[rid]["pm_event_slug"] = r.get("slug")
    
    for r in k_records:
        rid = r["race_id"]
        if rid not in snapshots:
            snapshots[rid] = {}
        # Multiple markets per race (e.g. -D and -R variants): keep first non-None value
        if r.get("dem_price") is not None:
            snapshots[rid]["k_dem_price"] = r["dem_price"]
        elif "k_dem_price" not in snapshots[rid]:
            snapshots[rid]["k_dem_price"] = None
        if r.get("rep_price") is not None:
            snapshots[rid]["k_rep_price"] = r["rep_price"]
        elif "k_rep_price" not in snapshots[rid]:
            snapshots[rid]["k_rep_price"] = None
        snapshots[rid]["k_volume_24h"] = snapshots[rid].get("k_volume_24h", 0) + (r.get("volume_24h") or 0)
        snapshots[rid]["k_ticker"] = r.get("ticker") or snapshots[rid].get("k_ticker")
    
    saved = 0
    for rid, data in snapshots.items():
        try:
            c.execute("""
                INSERT INTO market_snapshots
                    (race_id, snapshot_date, pm_dem_price, pm_rep_price,
                     pm_volume_24h, pm_event_slug, k_dem_price, k_rep_price,
                     k_volume_24h, k_ticker)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(race_id, snapshot_date) DO UPDATE SET
                    pm_dem_price = COALESCE(excluded.pm_dem_price, pm_dem_price),
                    pm_rep_price = COALESCE(excluded.pm_rep_price, pm_rep_price),
                    pm_volume_24h = COALESCE(excluded.pm_volume_24h, pm_volume_24h),
                    k_dem_price = COALESCE(excluded.k_dem_price, k_dem_price),
                    k_rep_price = COALESCE(excluded.k_rep_price, k_rep_price),
                    k_volume_24h = COALESCE(excluded.k_volume_24h, k_volume_24h),
                    captured_at = CURRENT_TIMESTAMP
            """, (
                rid, today,
                data.get("pm_dem_price"), data.get("pm_rep_price"),
                data.get("pm_volume_24h"), data.get("pm_event_slug"),
                data.get("k_dem_price"), data.get("k_rep_price"),
                data.get("k_volume_24h"), data.get("k_ticker"),
            ))
            saved += 1
        except Exception as e:
            print(f"  [DB] Error saving snapshot for {rid}: {e}")
    
    conn.commit()
    return saved


def save_polls(conn, poll_records):
    """Save new polls to the polls table."""
    c = conn.cursor()
    saved = 0
    
    for p in poll_records:
        try:
            c.execute("""
                INSERT INTO polls
                    (race_id, poll_date, pollster, candidate_1, candidate_1_pct,
                     candidate_2, candidate_2_pct, candidate_3, candidate_3_pct,
                     spread, spread_label, source_url, rcp_url, detected_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(race_id, poll_date, pollster) DO NOTHING
            """, (
                p["race_id"], p["poll_date"], p["pollster"],
                p.get("candidate_1"), p.get("candidate_1_pct"),
                p.get("candidate_2"), p.get("candidate_2_pct"),
                p.get("candidate_3"), p.get("candidate_3_pct"),
                p.get("spread"), p.get("spread_label"),
                p.get("source_url"), p.get("rcp_url"),
                date.today().isoformat()
            ))
            if c.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"  [DB] Error saving poll: {e}")
    
    conn.commit()
    return saved


def compute_daily_summary(conn, snapshot_date):
    """
    Compute daily summary for each race: combined market odds + polling average.
    """
    c = conn.cursor()
    today = snapshot_date
    
    # Get all races with snapshots today
    c.execute("""
        SELECT DISTINCT race_id FROM market_snapshots
        WHERE snapshot_date = ?
    """, (today,))
    race_ids = [row[0] for row in c.fetchall()]
    
    saved = 0
    for rid in race_ids:
        # Get market data
        c.execute("""
            SELECT pm_dem_price, pm_rep_price, k_dem_price, k_rep_price
            FROM market_snapshots
            WHERE race_id = ? AND snapshot_date = ?
        """, (rid, today))
        row = c.fetchone()
        if not row:
            continue
        
        pm_dem, pm_rep, k_dem, k_rep = row
        
        # Compute market consensus (average available prices)
        dem_prices = [p for p in [pm_dem, k_dem] if p is not None]
        rep_prices = [p for p in [pm_rep, k_rep] if p is not None]
        market_dem = sum(dem_prices) / len(dem_prices) if dem_prices else None
        market_rep = sum(rep_prices) / len(rep_prices) if rep_prices else None
        
        # Get polling average (last 30 days of polls)
        c.execute("""
            SELECT candidate_1_pct, candidate_2_pct
            FROM polls
            WHERE race_id = ?
              AND poll_date >= date(?, '-30 days')
            ORDER BY poll_date DESC
        """, (rid, today))
        poll_rows = c.fetchall()
        
        poll_avg_dem = None
        poll_avg_rep = None
        poll_count = len(poll_rows)
        if poll_rows:
            c1_pcts = [r[0] for r in poll_rows if r[0] is not None]
            c2_pcts = [r[1] for r in poll_rows if r[1] is not None]
            poll_avg_dem = sum(c1_pcts) / len(c1_pcts) if c1_pcts else None
            poll_avg_rep = sum(c2_pcts) / len(c2_pcts) if c2_pcts else None
        
        # Compute divergence
        gap = None
        if market_dem is not None and poll_avg_dem is not None:
            # Convert market probability to comparable scale
            gap = round((market_dem * 100) - poll_avg_dem, 2)
        
        try:
            c.execute("""
                INSERT INTO daily_summary
                    (race_id, summary_date, market_dem_pct, market_rep_pct,
                     pm_dem_pct, k_dem_pct, poll_avg_dem, poll_avg_rep,
                     poll_count, market_poll_gap)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(race_id, summary_date) DO UPDATE SET
                    market_dem_pct = excluded.market_dem_pct,
                    market_rep_pct = excluded.market_rep_pct,
                    pm_dem_pct = excluded.pm_dem_pct,
                    k_dem_pct = excluded.k_dem_pct,
                    poll_avg_dem = excluded.poll_avg_dem,
                    poll_avg_rep = excluded.poll_avg_rep,
                    poll_count = excluded.poll_count,
                    market_poll_gap = excluded.market_poll_gap
            """, (
                rid, today, market_dem, market_rep,
                pm_dem, k_dem, poll_avg_dem, poll_avg_rep,
                poll_count, gap
            ))
            saved += 1
        except Exception as e:
            print(f"  [DB] Error computing summary for {rid}: {e}")
    
    conn.commit()
    return saved


def log_scrape(conn, source, status, markets_found, records_saved,
               error_msg=None, duration=0):
    """Log a scrape run."""
    c = conn.cursor()
    c.execute("""
        INSERT INTO scrape_log
            (run_date, source, status, markets_found, records_saved,
             error_message, duration_secs)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (date.today().isoformat(), source, status, markets_found,
          records_saved, error_msg, duration))
    conn.commit()


def export_dashboard_json(conn, output_path):
    """
    Export a single JSON file containing everything the dashboard needs:
    - All races with metadata and external links
    - 30-day time series of market snapshots per race
    - All polls with matchup info and source URLs
    - Top-line control odds
    
    This file is what the dashboard fetches on load, so it must be
    re-exported after every daily snapshot.
    """
    c = conn.cursor()
    today = date.today().isoformat()
    
    # ── Build URL helpers ──
    # Polymarket: slug → https://polymarket.com/event/{slug}
    # Kalshi: ticker → https://kalshi.com/markets/{series}/{slug}/{ticker}
    # RCP: varies by chamber+state
    
    def rcp_url_for(chamber, state):
        """Generate RCP polling page URL for a race."""
        state_names = {
            "AL":"alabama","AK":"alaska","AZ":"arizona","AR":"arkansas",
            "CA":"california","CO":"colorado","CT":"connecticut","DE":"delaware",
            "FL":"florida","GA":"georgia","HI":"hawaii","ID":"idaho",
            "IL":"illinois","IN":"indiana","IA":"iowa","KS":"kansas",
            "KY":"kentucky","LA":"louisiana","ME":"maine","MD":"maryland",
            "MA":"massachusetts","MI":"michigan","MN":"minnesota","MS":"mississippi",
            "MO":"missouri","MT":"montana","NE":"nebraska","NV":"nevada",
            "NH":"new-hampshire","NJ":"new-jersey","NM":"new-mexico","NY":"new-york",
            "NC":"north-carolina","ND":"north-dakota","OH":"ohio","OK":"oklahoma",
            "OR":"oregon","PA":"pennsylvania","RI":"rhode-island","SC":"south-carolina",
            "SD":"south-dakota","TN":"tennessee","TX":"texas","UT":"utah",
            "VT":"vermont","VA":"virginia","WA":"washington","WV":"west-virginia",
            "WI":"wisconsin","WY":"wyoming"
        }
        sn = state_names.get(state)
        if not sn or state == "US":
            return None
        if chamber == "senate":
            return f"polls/senate/general/2026/{sn}"
        elif chamber == "governor":
            return f"polls/governor/general/2026/{sn}"
        elif chamber == "house":
            return f"latest-polls/house"
        return None
    
    # ── Fetch all races ──
    c.execute("""
        SELECT race_id, chamber, state, district, description,
               polymarket_slug, kalshi_ticker
        FROM races ORDER BY chamber, state
    """)
    race_rows = c.fetchall()
    
    races_out = []
    for row in race_rows:
        rid, chamber, state, district, desc, pm_slug, k_ticker = row
        
        # Get latest market snapshot
        c.execute("""
            SELECT pm_dem_price, pm_rep_price, k_dem_price, k_rep_price,
                   pm_volume_24h, k_volume_24h
            FROM market_snapshots
            WHERE race_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (rid,))
        snap = c.fetchone()
        
        # Compute dem_base from latest snapshot; derive dem from rep if needed
        def dem_from_snap(dem, rep):
            if dem is not None:
                return dem
            if rep is not None:
                return round(1 - rep, 3)
            return None

        dem_base = None
        if snap:
            pm_dem = dem_from_snap(snap[0], snap[1])
            k_dem  = dem_from_snap(snap[2], snap[3])
            prices = [p for p in [pm_dem, k_dem] if p is not None]
            if prices:
                dem_base = round(sum(prices) / len(prices), 3)

        # Get 30 days of time series
        c.execute("""
            SELECT snapshot_date, pm_dem_price, pm_rep_price,
                   k_dem_price, k_rep_price
            FROM market_snapshots
            WHERE race_id = ?
            ORDER BY snapshot_date DESC LIMIT 30
        """, (rid,))
        ts_rows = list(reversed(c.fetchall()))
        time_series = []
        for ts in ts_rows:
            pm_d = dem_from_snap(ts[1], ts[2])
            k_d  = dem_from_snap(ts[3], ts[4])
            parts = ts[0].split("-")
            date_str = f"{int(parts[1])}/{int(parts[2])}"
            time_series.append({
                "date": date_str,
                "polymarket": round(pm_d * 100) if pm_d is not None else None,
                "kalshi":     round(k_d  * 100) if k_d  is not None else None,
            })
        
        # Get polls for this race
        c.execute("""
            SELECT poll_date, pollster, candidate_1, candidate_1_pct,
                   candidate_2, candidate_2_pct, spread, spread_label,
                   source_url, rcp_url
            FROM polls
            WHERE race_id = ?
            ORDER BY poll_date DESC
        """, (rid,))
        poll_rows = c.fetchall()
        polls = []
        for pr in poll_rows:
            polls.append({
                "date": pr[0],
                "pollster": pr[1],
                "d": pr[3],
                "r": pr[5],
                "spread": pr[7] or f"{pr[2]} +{abs(int(pr[6]))}" if pr[6] else "",
                "matchup": f"{pr[2]} vs. {pr[4]}" if pr[2] and pr[4] else None,
                "url": pr[8],
            })
        
        # Build external links
        pm_url = f"https://polymarket.com/event/{pm_slug}" if pm_slug else None
        k_url = None
        if k_ticker:
            # Kalshi URL pattern: /markets/{series}/{event}/{ticker}
            # Simplified: just use the ticker as path
            k_url = f"https://kalshi.com/markets/{k_ticker.lower()}"
        rcp = rcp_url_for(chamber, state)
        
        race_obj = {
            "race_id": rid,
            "chamber": chamber,
            "state": state,
            "district": district,
            "description": desc or rid,
            "dem_base": dem_base,
            "pm": pm_slug,
            "kalshi": k_ticker,
            "rcp": rcp,
            "polls": polls if polls else None,
            "time_series": time_series if time_series else None,
            "note": None,
        }
        races_out.append(race_obj)
    
    # ── Compute top-line stats ──
    senate_control = next((r for r in races_out if r["race_id"] == "senate-control-2026"), None)
    house_control = next((r for r in races_out if r["race_id"] == "house-control-2026"), None)
    
    tossup_senate = sum(1 for r in races_out
                        if r["chamber"] == "senate" and r["state"] != "US"
                        and r["dem_base"] is not None
                        and 0.40 <= r["dem_base"] <= 0.60)
    
    total_polls = sum(len(r["polls"]) for r in races_out if r["polls"])
    
    output = {
        "updated": today,
        "stats": {
            "senate_dem_pct": round(senate_control["dem_base"] * 100) if senate_control and senate_control["dem_base"] else None,
            "senate_rep_pct": round((1 - senate_control["dem_base"]) * 100) if senate_control and senate_control["dem_base"] else None,
            "house_dem_pct": round(house_control["dem_base"] * 100) if house_control and house_control["dem_base"] else None,
            "house_rep_pct": round((1 - house_control["dem_base"]) * 100) if house_control and house_control["dem_base"] else None,
            "battleground_senate": tossup_senate,
            "seats_up": 35,
            "polls_tracked": total_polls,
        },
        "races": races_out,
    }
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[Export] Dashboard JSON: {output_path} ({len(races_out)} races, {total_polls} polls)")


def export_csv_summary(conn, output_path):
    """Export current daily summary to CSV for easy viewing."""
    import csv
    c = conn.cursor()
    c.execute("""
        SELECT ds.race_id, r.chamber, r.state, ds.summary_date,
               ds.market_dem_pct, ds.market_rep_pct,
               ds.pm_dem_pct, ds.k_dem_pct,
               ds.poll_avg_dem, ds.poll_avg_rep,
               ds.poll_count, ds.market_poll_gap
        FROM daily_summary ds
        LEFT JOIN races r ON ds.race_id = r.race_id
        ORDER BY ds.summary_date DESC, r.chamber, r.state
    """)

    rows = c.fetchall()
    headers = [
        "race_id", "chamber", "state", "date",
        "market_dem%", "market_rep%",
        "polymarket_dem%", "kalshi_dem%",
        "poll_avg_dem%", "poll_avg_rep%",
        "poll_count", "market_poll_gap"
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"[Export] Saved CSV summary to {output_path}")


def main():
    dry_run = "--dry-run" in sys.argv
    do_export = "--export" in sys.argv
    today = date.today().isoformat()
    
    print(f"{'='*60}")
    print(f"  2026 Midterm Election Tracker — Daily Snapshot")
    print(f"  Date: {today}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")
    
    archive_dir = ensure_dirs()
    
    # ── 1. Fetch Polymarket ────────────────────────────
    t0 = time.time()
    try:
        pm_records, pm_raw = fetch_all_midterm_markets()
        pm_status = "success"
        pm_error = None
    except Exception as e:
        pm_records, pm_raw = [], []
        pm_status = "error"
        pm_error = str(e)
        print(f"  [ERROR] Polymarket fetch failed: {e}")
    pm_duration = time.time() - t0
    
    # ── 2. Fetch Kalshi ────────────────────────────────
    t0 = time.time()
    try:
        k_records, k_raw = fetch_all_election_markets()
        k_status = "success"
        k_error = None
    except Exception as e:
        k_records, k_raw = [], []
        k_status = "error"
        k_error = str(e)
        print(f"  [ERROR] Kalshi fetch failed: {e}")
    k_duration = time.time() - t0
    
    # ── 3. Fetch Polls ─────────────────────────────────
    t0 = time.time()
    try:
        poll_records, polls_raw = fetch_all_polls()
        poll_status = "success"
        poll_error = None
    except Exception as e:
        poll_records, polls_raw = [], {}
        poll_status = "error"
        poll_error = str(e)
        print(f"  [ERROR] RCP fetch failed: {e}")
    poll_duration = time.time() - t0
    
    # ── 4. Archive raw data ────────────────────────────
    archive_raw_data(archive_dir, pm_raw, k_raw, polls_raw)
    
    if dry_run:
        print("\n[DRY RUN] Skipping database writes.")
        print(f"  Polymarket: {len(pm_records)} markets found")
        print(f"  Kalshi: {len(k_records)} markets found")
        print(f"  Polls: {len(poll_records)} polls found")
        return
    
    # ── 5. Save to database ────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    
    # Races
    n_races = save_races(conn, pm_records, k_records)
    print(f"\n[DB] Upserted {n_races} races")
    
    # Market snapshots
    n_snapshots = save_market_snapshots(conn, pm_records, k_records, today)
    print(f"[DB] Saved {n_snapshots} market snapshots")
    
    # Polls
    n_polls = save_polls(conn, poll_records)
    print(f"[DB] Saved {n_polls} new polls")
    
    # Daily summary
    n_summary = compute_daily_summary(conn, today)
    print(f"[DB] Computed {n_summary} daily summaries")
    
    # Log scrape runs
    log_scrape(conn, "polymarket", pm_status, len(pm_records),
               n_snapshots, pm_error, pm_duration)
    log_scrape(conn, "kalshi", k_status, len(k_records),
               n_snapshots, k_error, k_duration)
    log_scrape(conn, "rcp", poll_status, len(poll_records),
               n_polls, poll_error, poll_duration)
    
    # Export CSV if requested
    if do_export:
        export_csv_summary(conn, DATA_DIR / "daily_summary.csv")
    
    # Always export dashboard JSON
    export_dashboard_json(conn, DATA_DIR / "dashboard_data.json")
    
    conn.close()
    
    # ── Summary ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Snapshot complete!")
    print(f"  Polymarket: {len(pm_records)} markets ({pm_status})")
    print(f"  Kalshi:     {len(k_records)} markets ({k_status})")
    print(f"  Polls:      {len(poll_records)} polls, {n_polls} new ({poll_status})")
    print(f"  Archive:    {archive_dir}/")
    print(f"  Database:   {DB_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
