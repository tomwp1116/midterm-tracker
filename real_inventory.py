"""
Real Market Inventory — compiled March 10, 2026
================================================
This is the actual universe of 2026 midterm prediction markets
available on Polymarket and Kalshi, based on live data.

Run this to populate the database with real race entries.
"""
import sqlite3
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ═══════════════════════════════════════════════════════
# CONTROL / TOP-LINE MARKETS
# Available on BOTH Polymarket and Kalshi
# ═══════════════════════════════════════════════════════
control_markets = [
    # (race_id, chamber, state, district, description, pm_slug, kalshi_ticker, pm_dem, pm_rep, k_dem, k_rep, volume_note)
    ("senate-control-2026", "senate", "US", None,
     "Which party will win the Senate in 2026?",
     "which-party-will-win-the-senate-in-2026",
     "CONTROLS-SENATE-26",
     0.35, 0.66,    # PM: Dem 35%, Rep 66% (as of Mar 9)
     None, None,     # Kalshi: ~33% Dem, ~67% Rep
     "$731K PM / significant Kalshi vol"),

    ("house-control-2026", "house", "US", None,
     "Which party will win the House in 2026?",
     "which-party-will-win-the-house-in-2026",
     "CONTROLS-HOUSE-26",
     0.78, 0.23,    # PM: Dem 78%, Rep 23%
     None, None,
     "$2M PM"),

    ("balance-of-power-2026", "congress", "US", None,
     "Balance of Power: 2026 Midterms (Dem Sweep 35%, R Senate D House 2%, D Senate R House -, R Sweep -)",
     "balance-of-power-2026-midterms",
     None,
     0.35, None,     # "Democrats Sweep" at 35%
     None, None,
     "$1M PM, 5 outcomes"),

    ("blue-wave-2026", "congress", "US", None,
     "Blue wave in 2026?",
     "blue-wave-in-2026",
     None,
     0.55, 0.45,
     None, None,
     "NEW market"),

    ("senate-seats-R-2026", "senate", "US", None,
     "Republican Senate seats after 2026 midterms (11 outcomes: ≤47 through ≥53)",
     "republican-senate-seats-after-the-2026-midterm-elections-927",
     None,
     None, None, None, None,
     "$162K PM, bracket market"),
]

# ═══════════════════════════════════════════════════════
# INDIVIDUAL SENATE RACES — GENERAL ELECTION
# Kalshi has markets for ALL 35 seats (per 270toWin map)
# Polymarket has ~12-15 individual race markets
# ═══════════════════════════════════════════════════════
senate_races = [
    # ── COMPETITIVE / TOSS-UP ──
    ("senate-GA-2026", "senate", "GA", None,
     "Georgia Senate — Ossoff (D-inc) vs. TBD (R)",
     "georgia-senate-election-winner",          # PM: individual candidates
     "SENATEGA-26",                              # Kalshi
     None, None,                                 # PM odds TBD per candidate
     None, None,
     "Core four race. Ossoff won narrowly in 2021. $200K+ PM on primary alone"),

    ("senate-NC-2026", "senate", "NC", None,
     "North Carolina Senate — Tillis (R-inc) vs. TBD (D)",
     "north-carolina-senate-election-winner",
     "SENATENC-26",
     None, None, None, None,
     "Core four race. Competitive open primary on Dem side"),

    ("senate-ME-2026", "senate", "ME", None,
     "Maine Senate — Collins (R-inc) vs. TBD (D)",
     "maine-senate-election-winner",
     "SENATEME-26",
     None, None, None, None,
     "Core four race. Dem primary June 9. Platner +7 in Quantus poll"),

    ("senate-MI-2026", "senate", "MI", None,
     "Michigan Senate — Peters (D-retiring) vs. TBD (R)",
     "michigan-senate-election-winner",
     "SENATEMI-26",
     0.77, 0.23,                                # PM: Dem 77%, Rep 23%
     None, None,
     "Core four. Peters retiring, open Dem primary Aug 4. $92K PM"),

    ("senate-AK-2026", "senate", "AK", None,
     "Alaska Senate — Sullivan (R-inc) vs. Peltola? (D)",
     "alaska-senate-election-winner",
     "SENATEAK-26",
     None, None,                                 # PM: Sullivan 49%, Peltola 48%
     None, None,
     "Ranked-choice voting state. Peltola announcement pending. $200K PM"),

    ("senate-NH-2026", "senate", "NH", None,
     "New Hampshire Senate — Open (Shaheen D-retiring)",
     "new-hampshire-senate-election-winner",
     "SENATENH-26",
     None, None, None, None,
     "Shaheen retiring. John Sununu vs Scott Brown in R primary"),

    ("senate-OH-2026", "senate", "OH", None,
     "Ohio Senate — Brown (D) vs. Husted (R-appointed)",
     None,
     "SENATEOH-26",
     None, None, None, None,
     "Special election. Sherrod Brown running against appointed Sen."),

    ("senate-IA-2026", "senate", "IA", None,
     "Iowa Senate — Grassley (R-retiring) or successor vs. TBD (D)",
     None,
     "SENATEIA-26",
     None, None, None, None,
     "Could be competitive in blue wave scenario"),

    # ── LEAN / LIKELY ──
    ("senate-TX-2026", "senate", "TX", None,
     "Texas Senate — Cornyn/Paxton (R-runoff) vs. Talarico (D)",
     "texas-senate-election-winner",
     "SENATETX-26",
     0.28, 0.73,                                 # PM: Dem 28%, Rep 73%
     None, None,
     "TX primary March 3: Talarico (D) won. R headed to runoff. $1.1M Kalshi, $80K PM on primary"),

    ("senate-IL-2026", "senate", "IL", None,
     "Illinois Senate — Durbin (D-retiring), Dem primary Mar 17",
     None,
     "SENATEIL-26",
     None, None, None, None,
     "Safe D. Primary March 17"),

    ("senate-KY-2026", "senate", "KY", None,
     "Kentucky Senate — McConnell (R-retiring)",
     None,
     "SENATEKY-26",
     None, None, None, None,
     "R primary May 19. Likely R"),

    ("senate-FL-2026", "senate", "FL", None,
     "Florida Senate — Special election (open)",
     None,
     "SENATEFL-26",
     None, None, None, None,
     "Special election"),

    # ── SAFE ──
    ("senate-WV-2026", "senate", "WV", None,
     "West Virginia Senate",
     "west-virginia-senate-election-winner",
     "SENATEWV-26",
     0.07, 0.93,                                 # PM: Dem 7%, Rep 93%
     None, None,
     "Safe R. $3K PM"),

    ("senate-NE-2026", "senate", "NE", None,
     "Nebraska Senate (notable independent candidate)",
     "nebraska-senate-election-winner",
     "SENATENE-26",
     0.05, 0.69,                                 # PM: Dem 5%, Rep 69%, Ind ~26%
     None, None,
     "Three-way race with independent. $44K PM"),

    ("senate-MN-2026", "senate", "MN", None, "Minnesota Senate — Klobuchar (D-inc)", None, "SENATEMN-26", None, None, None, None, "Safe D"),
    ("senate-VA-2026", "senate", "VA", None, "Virginia Senate — Warner (D-inc)", None, "SENATEVA-26", None, None, None, None, "Safe D"),
    ("senate-MA-2026", "senate", "MA", None, "Massachusetts Senate — Markey (D-inc)", None, "SENATEMA-26", None, None, None, None, "Safe D"),
    ("senate-OR-2026", "senate", "OR", None, "Oregon Senate — Merkley (D-inc)", None, "SENATEOR-26", None, None, None, None, "Safe D"),
    ("senate-CO-2026", "senate", "CO", None, "Colorado Senate — Gardner seat (D-held)", None, "SENATECO-26", None, None, None, None, "Safe D"),
    ("senate-DE-2026", "senate", "DE", None, "Delaware Senate", None, "SENATEDE-26", None, None, None, None, "Safe D"),
    ("senate-NJ-2026", "senate", "NJ", None, "New Jersey Senate", None, "SENATENI-26", None, None, None, None, "Likely D"),
    ("senate-SC-2026", "senate", "SC", None, "South Carolina Senate — Graham (R-inc)", None, "SENATESC-26", None, None, None, None, "Safe R"),
    ("senate-AL-2026", "senate", "AL", None, "Alabama Senate — retiring R", None, "SEATEAL-26", None, None, None, None, "Safe R"),
    ("senate-AR-2026", "senate", "AR", None, "Arkansas Senate — Cotton (R-inc)", None, "SENATEAR-26", None, None, None, None, "Safe R"),
    ("senate-ID-2026", "senate", "ID", None, "Idaho Senate — Crapo (R-inc)", None, "SENATEID-26", None, None, None, None, "Safe R"),
    ("senate-KS-2026", "senate", "KS", None, "Kansas Senate — Moran (R-inc)", None, "SENATEKS-26", None, None, None, None, "Safe R"),
    ("senate-LA-2026", "senate", "LA", None, "Louisiana Senate — Cassidy (R-inc)", None, "SENATELA-26", None, None, None, None, "Safe R"),
    ("senate-MS-2026", "senate", "MS", None, "Mississippi Senate — Hyde-Smith (R-inc)", None, "SENATEMS-26", None, None, None, None, "Safe R"),
    ("senate-MT-2026", "senate", "MT", None, "Montana Senate", None, "SENATEMT-26", None, None, None, None, "Safe R"),
    ("senate-OK-2026", "senate", "OK", None, "Oklahoma Senate — Lankford (R-inc)", None, "SENATEOK-26", None, None, None, None, "Safe R"),
    ("senate-SD-2026", "senate", "SD", None, "South Dakota Senate — Rounds (R-inc)", None, "SENATESD-26", None, None, None, None, "Safe R"),
    ("senate-TN-2026", "senate", "TN", None, "Tennessee Senate", None, "SENATETN-26", None, None, None, None, "Safe R"),
    ("senate-WY-2026", "senate", "WY", None, "Wyoming Senate — Lummis (R-inc)", None, "SENATEWY-26", None, None, None, None, "Safe R"),
]

# ═══════════════════════════════════════════════════════
# GOVERNOR RACES (Polymarket has several)
# ═══════════════════════════════════════════════════════
governor_races = [
    ("governor-NY-2026", "governor", "NY", None,
     "New York Governor", "new-york-governor-winner-2026", None,
     0.88, 0.13, None, None, "$43K PM"),

    ("governor-NM-2026", "governor", "NM", None,
     "New Mexico Governor", "new-mexico-governor-winner-2026", None,
     0.80, 0.18, None, None, "$15K PM"),

    ("governor-AK-2026", "governor", "AK", None,
     "Alaska Governor (Begich 26%, Dahlstrom 26%, others)",
     "alaska-governor-election-winner", None,
     None, None, None, None, "$278K PM, candidate-level"),

    ("governor-RI-2026", "governor", "RI", None,
     "Rhode Island Governor", "rhode-island-governor-winner-2026", None,
     0.96, 0.05, None, None, "$40K PM"),

    ("governor-CA-2026", "governor", "CA", None,
     "California Governor (Newsom term-limited, open)", None, None,
     None, None, None, None, "Top-two primary Jun 2. On Kalshi."),

    ("governor-AZ-2026", "governor", "AZ", None,
     "Arizona Governor — Hobbs (D) vs. TBD (R)", None, None,
     None, None, None, None, "Toss-up. On Kalshi."),

    ("governor-GA-2026", "governor", "GA", None,
     "Georgia Governor — Kemp (R) term-limited", None, None,
     None, None, None, None, "R primary May 19. On Kalshi."),

    ("governor-FL-2026", "governor", "FL", None,
     "Florida Governor — DeSantis (R) term-limited", None, None,
     None, None, None, None, "$2M on R primary (Kalshi). On Kalshi."),
]

# ═══════════════════════════════════════════════════════
# PRIMARY MARKETS (both platforms)
# ═══════════════════════════════════════════════════════
primary_markets = [
    ("primary-TX-senate-R-2026", "senate", "TX", None,
     "Texas Senate Republican Primary Runoff — Cornyn vs. Paxton",
     "texas-senate-republican-primary", "SENATETX-R-26",
     None, None, None, None,
     "Cornyn vs Paxton runoff. Paxton leading in markets. $4.8M Kalshi on TX Dem primary."),

    ("primary-GA-senate-R-2026", "senate", "GA", None,
     "Georgia Senate Republican Primary (May 19)",
     None, "SENATEGA-R-26",
     None, None, None, None,
     "Collins 30%, Carter 16%, Dooley 10% per Emerson poll"),

    ("primary-ME-senate-D-2026", "senate", "ME", None,
     "Maine Senate Democratic Primary (June 9)",
     None, "SENATEME-D-26",
     None, None, None, None,
     "Platner 43%, Mills 38% per Quantus poll"),

    ("primary-MI-senate-D-2026", "senate", "MI", None,
     "Michigan Senate Democratic Primary (August 4)",
     None, "SENATEMI-D-26",
     None, None, None, None,
     "Peters retiring. Open primary."),

    ("primary-IL-senate-D-2026", "senate", "IL", None,
     "Illinois Senate Democratic Primary (March 17)",
     None, "SENATEIL-D-26",
     None, None, None, None,
     "Durbin retiring. Likely Pritzker-aligned candidate."),
]

# ═══════════════════════════════════════════════════════
# META / DERIVATIVE MARKETS (Polymarket specialties)
# ═══════════════════════════════════════════════════════
meta_markets = [
    ("core-four-dem-sweep-2026", "senate", "US", None,
     "Will Democrats win all 'core four' senate races? (GA, MI, NC, ME)",
     "will-democrats-win-all-core-four-senate-races", None,
     0.56, 0.44, None, None, "Combo market"),

    ("gop-house-retirements-2026", "house", "US", None,
     "How many Republican House members not running in 2026?",
     "how-many-republican-house-members-not-running-in-2026", None,
     None, None, None, None, "Bracket market, $20K PM"),

    ("gop-trifecta-supermajority-2026", "congress", "US", None,
     "Republicans win Trifecta with Senate Supermajority?",
     "republican-trifecta-with-supermajority-in-the-senate", None,
     0.04, 0.96, None, None, "$17K PM"),

    ("midterms-happen-scheduled-2026", "congress", "US", None,
     "Will the 2026 Midterm Elections happen as scheduled?",
     "will-the-2026-midterm-elections-happen-as-scheduled", None,
     0.88, 0.12, None, None, "$78.6K PM"),
]

# ═══════════════════════════════════════════════════════
# HOUSE RACES — Kalshi has competitive districts
# Polymarket has the overall control + retirement brackets
# ═══════════════════════════════════════════════════════
# Note: Kalshi has individual district markets for ~30-40
# competitive House races. Polymarket mainly tracks House
# control, not individual districts. The Kalshi House seat
# count forecast dropped from ~212R to 203.3R since November.

# ═══════════════════════════════════════════════════════
# INSERT ALL RACES
# ═══════════════════════════════════════════════════════
all_races = control_markets + senate_races + governor_races + primary_markets + meta_markets

inserted = 0
for race in all_races:
    rid, chamber, state, district, desc, pm_slug, k_ticker = race[:7]
    c.execute("""
        INSERT INTO races (race_id, chamber, state, district, description,
                         polymarket_slug, kalshi_ticker)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(race_id) DO UPDATE SET
            description = excluded.description,
            polymarket_slug = COALESCE(excluded.polymarket_slug, polymarket_slug),
            kalshi_ticker = COALESCE(excluded.kalshi_ticker, kalshi_ticker)
    """, (rid, chamber, state, district, desc, pm_slug, k_ticker))
    inserted += 1

conn.commit()

# ═══════════════════════════════════════════════════════
# SUMMARY REPORT
# ═══════════════════════════════════════════════════════
c.execute("SELECT COUNT(*) FROM races")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM races WHERE polymarket_slug IS NOT NULL")
pm_count = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM races WHERE kalshi_ticker IS NOT NULL")
k_count = c.fetchone()[0]

print("=" * 65)
print("  REAL MARKET INVENTORY — 2026 Midterms")
print("  Compiled: March 10, 2026")
print("=" * 65)
print()
print(f"  Total races in database:           {total}")
print(f"  With Polymarket market:            {pm_count}")
print(f"  With Kalshi market:                {k_count}")
print()
print("  POLYMARKET breakdown:")
print(f"    646 total midterm markets (many are derivative/prop bets)")
print(f"    221 Senate-tagged markets")
print(f"    ~15 individual Senate general election races")
print(f"    ~6 governor races")
print(f"    ~5 primary markets (candidate-level)")
print(f"    ~10 meta/derivative markets")
print(f"    House: control only, no individual districts")
print()
print("  KALSHI breakdown:")
print(f"    Markets for ALL 35 Senate seats (per 270toWin)")
print(f"    ~30-40 competitive House district markets")
print(f"    ~8 governor races")
print(f"    Senate/House control markets")
print(f"    Primary markets (TX resolved, GA/ME/MI/IL upcoming)")
print(f"    House seat count bracket (currently 203.3 R)")
print()
print("  KEY COMPETITIVE RACES (both platforms + polls):")
print("    Senate: GA, NC, ME, MI, AK, NH, OH, TX, IA")
print("    'Core four': GA, MI, NC, ME (Dem needs all four)")
print("    Governor: AZ, CA, AK, FL, GA")
print()
print("  NOTES ON CURRENT ODDS (Polymarket, as of Mar 9):")
print("    Senate control:   Rep 66%, Dem 35%")
print("    House control:    Dem 78%, Rep 23%")
print("    Balance of Power: Dem Sweep 35%, R Senate D House 2%")
print("    Core four sweep:  Dem 56%")
print("    Michigan Senate:  Dem 77%")
print("    Texas Senate:     Rep 73%")
print("    Alaska Senate:    Sullivan 49%, Peltola 48%")
print("    West Virginia:    Rep 93%")
print()

conn.close()
