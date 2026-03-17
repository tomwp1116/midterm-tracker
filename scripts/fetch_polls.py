"""
Scrape new 2026 polls from RealClearPolling.

URLs:
  https://www.realclearpolling.com/latest-polls/2026
  https://www.realclearpolling.com/latest-polls/senate
  https://www.realclearpolling.com/latest-polls/house

The page renders a table with columns:
  Date | Race Name | Pollster | Results (Candidate %, Candidate %) | Spread

We parse this table to extract individual poll results, then match
each poll to a canonical race_id.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from config import (
    RCP_LATEST_2026, RCP_SENATE_POLLS, RCP_HOUSE_POLLS,
    RCP_GOVERNOR_POLLS, USER_AGENT, REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT
)

HEADERS = {"User-Agent": USER_AGENT}

STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY"
}


def fetch_page(url):
    """Fetch and parse an RCP page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [RCP] Error fetching {url}: {e}")
        return None


def parse_polls_table(soup, page_url):
    """
    Parse the RealClearPolling latest polls table.
    
    The page structure (as of March 2026):
    - Polls are grouped by date headers
    - Each poll row contains:
      - Race name (linked to RCP average page)
      - Pollster name (linked to pollster site)
      - Results: "Candidate1 XX Candidate2 YY"
      - Spread: "Candidate1 +N"
    """
    polls = []
    current_date = None
    
    # RCP renders the table; we look for rows in the main content area
    # The table structure varies, so we try multiple selectors
    
    # Try to find table rows
    rows = soup.select("table tr, .poll-row, [class*='poll']")
    
    # Also look for the text content pattern
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Parse by looking for date headers followed by poll entries
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for date headers (e.g., "Monday, March 9", "Thursday, March 5")
        date_match = re.match(
            r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
            r'(January|February|March|April|May|June|July|August|September|'
            r'October|November|December)\s+(\d{1,2})',
            line
        )
        if date_match:
            month_str = date_match.group(2)
            day = int(date_match.group(3))
            year = 2026  # Assumed from context
            try:
                current_date = datetime.strptime(
                    f"{month_str} {day} {year}", "%B %d %Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                pass
            i += 1
            continue
        
        # Check for race patterns like "2026 Georgia Senate" or "2026 Maine Senate"
        race_match = re.match(
            r'2026\s+([\w\s]+?)\s+(Senate|House|Governor)\s*[-–—]\s*(.*)',
            line
        )
        if not race_match:
            # Also check for patterns without "2026" prefix
            race_match = re.match(
                r'([\w\s]+?)\s+(Senate|House|Governor)\s*[-–—]\s*(.*)',
                line
            )
        
        if race_match:
            state_name = race_match.group(1).strip().lower()
            chamber = race_match.group(2).strip().lower()
            matchup = race_match.group(3).strip()
            
            state_code = STATE_MAP.get(state_name)
            if not state_code:
                # Try partial match
                for name, code in STATE_MAP.items():
                    if name in state_name or state_name in name:
                        state_code = code
                        break
            
            # Build race_id
            race_id = f"{chamber}-{state_code}-2026" if state_code else None
            
            # Look ahead for pollster, results, spread
            pollster = None
            results = {}
            spread_label = None
            
            # Check next few lines for pollster and results
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j]
                
                # Pollster line (usually a known pollster name)
                if any(p in next_line for p in [
                    "Emerson", "Quantus", "Quinnipiac", "Marist",
                    "SurveyUSA", "PPP", "Trafalgar", "Rasmussen",
                    "Morning Consult", "YouGov", "CNN", "Fox News",
                    "Monmouth", "Siena", "Mason-Dixon", "Mitchell",
                    "Suffolk", "Data for Progress", "Echelon", "TIPP",
                    "InsiderAdvantage", "co/efficient"
                ]):
                    pollster = next_line.strip()
                
                # Results pattern: "Name XX Name YY" or "Name XX, Name YY"
                result_match = re.findall(
                    r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(\d{1,2})',
                    next_line
                )
                if len(result_match) >= 2:
                    for name, pct in result_match:
                        results[name] = float(pct)
                
                # Spread pattern: "Name +N"
                spread_match = re.match(r'(\w+)\s*\+(\d+)', next_line)
                if spread_match:
                    spread_label = f"{spread_match.group(1)} +{spread_match.group(2)}"
            
            if race_id and (results or pollster):
                candidates = list(results.items())
                poll_record = {
                    "race_id": race_id,
                    "poll_date": current_date or date.today().isoformat(),
                    "pollster": pollster or "Unknown",
                    "candidate_1": candidates[0][0] if len(candidates) > 0 else None,
                    "candidate_1_pct": candidates[0][1] if len(candidates) > 0 else None,
                    "candidate_2": candidates[1][0] if len(candidates) > 1 else None,
                    "candidate_2_pct": candidates[1][1] if len(candidates) > 1 else None,
                    "candidate_3": candidates[2][0] if len(candidates) > 2 else None,
                    "candidate_3_pct": candidates[2][1] if len(candidates) > 2 else None,
                    "spread_label": spread_label,
                    "spread": (
                        candidates[0][1] - candidates[1][1]
                        if len(candidates) >= 2 else None
                    ),
                    "matchup_description": matchup,
                    "source_url": page_url,
                }
                polls.append(poll_record)
        
        i += 1
    
    return polls


def parse_rcp_structured(soup, page_url):
    """
    Parse RealClearPolling's poll table by reading the <tbody> as a token
    stream.  The page renders each poll as a flat sequence of text nodes
    inside one big <tbody>:

        Monday, March 16          ← date header
        2026 Ohio Senate … - …   ← race title (contains /polls/ link)
        Poll                      ← literal marker
        Quantus Insights          ← pollster name
        Results                   ← literal marker
        Husted                    ← candidate 1
        46                        ← pct 1
        Brown                     ← candidate 2
        44                        ← pct 2
        Spread                    ← literal marker
        Husted                    ← spread winner
        +2                        ← margin

    Walking the tokens in order lets us capture date, pollster, and results
    correctly instead of chasing individual links.
    """
    polls = []
    current_date = None

    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    DATE_RE = re.compile(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
        r'(January|February|March|April|May|June|July|August|September|'
        r'October|November|December)\s+(\d{1,2})',
        re.IGNORECASE,
    )

    def href_to_race_id(href):
        """Convert an RCP poll URL to a canonical race_id."""
        parts = [p for p in href.split("/") if p]
        chamber = None
        state = None
        if "senate" in parts:
            chamber = "senate"
        elif "house" in parts:
            chamber = "house"
        elif "governor" in parts:
            chamber = "governor"
        for part in parts:
            lp = part.lower()
            if lp in STATE_MAP:
                state = STATE_MAP[lp]
                break
            for name, code in STATE_MAP.items():
                if name.replace(" ", "-") == lp:
                    state = code
                    break
            if state:
                break
        if not (chamber and state):
            return None
        rid = f"{chamber}-{state}-2026"
        if "primary" in href.lower():
            rid += "-primary-D" if "democratic" in href.lower() else "-primary-R"
        return rid

    # Collect all text tokens from every <tbody> on the page, preserving
    # which tokens are /polls/ links so we can anchor the race.
    for tbody in soup.find_all("tbody"):
        tokens = []
        for node in tbody.descendants:
            if node.name == "a":
                href = node.get("href", "")
                txt = node.get_text(strip=True)
                tokens.append(("link", href, txt))
            elif not node.name and node.string and node.string.strip():
                tokens.append(("text", node.string.strip()))

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            # Date header
            if tok[0] == "text":
                m = DATE_RE.match(tok[1])
                if m:
                    month_num = MONTH_MAP[m.group(2).lower()]
                    day = int(m.group(3))
                    current_date = f"2026-{month_num:02d}-{day:02d}"
                    i += 1
                    continue

            # Race link — anchor for a new poll entry
            if tok[0] == "link" and "/polls/" in tok[1] and "/2026/" in tok[1]:
                race_id = href_to_race_id(tok[1])
                rcp_url = ("https://www.realclearpolling.com" + tok[1]
                           if tok[1].startswith("/") else tok[1])
                if not race_id:
                    i += 1
                    continue

                # Scan ahead for: Poll marker → pollster → Results marker →
                # candidate/pct pairs → Spread marker → winner → +N
                pollster = None
                candidates = []
                spread_label = None
                expecting = "poll_marker"

                j = i + 1
                while j < min(i + 20, len(tokens)):
                    t = tokens[j]
                    val = t[1] if t[0] == "text" else t[2]

                    if expecting == "poll_marker":
                        if val.lower() == "poll":
                            expecting = "pollster"
                    elif expecting == "pollster":
                        if val.lower() not in ("results", "spread", "poll"):
                            pollster = val
                            expecting = "results_marker"
                    elif expecting == "results_marker":
                        if val.lower() == "results":
                            expecting = "candidates"
                    elif expecting == "candidates":
                        if val.lower() == "spread":
                            expecting = "spread_winner"
                        elif re.match(r'^\d{1,2}$', val):
                            if candidates and candidates[-1][1] is None:
                                candidates[-1] = (candidates[-1][0], float(val))
                        elif re.match(r'^[A-Z]', val) and not re.match(r'^\d', val):
                            candidates.append((val, None))
                    elif expecting == "spread_winner":
                        if re.match(r'^\+\d', val):
                            # Use the spread winner name if captured, else first candidate
                            winner = locals().get("spread_winner_name") or (
                                candidates[0][0].split()[0] if candidates else "")
                            spread_label = f"{winner} {val}"
                            break
                        # Spread-winner name token — extract just the first word
                        # (the token may be a concatenated cell; we only need the name)
                        name_match = re.match(r'^([A-Z][a-z]+)', val)
                        if name_match:
                            spread_winner_name = name_match.group(1)
                    j += 1

                # Only emit if we have at least one candidate with a pct
                filled = [(n, p) for n, p in candidates if p is not None]
                if filled:
                    polls.append({
                        "race_id": race_id,
                        "poll_date": current_date or date.today().isoformat(),
                        "pollster": pollster or "Unknown",
                        "candidate_1": filled[0][0] if len(filled) > 0 else None,
                        "candidate_1_pct": filled[0][1] if len(filled) > 0 else None,
                        "candidate_2": filled[1][0] if len(filled) > 1 else None,
                        "candidate_2_pct": filled[1][1] if len(filled) > 1 else None,
                        "candidate_3": filled[2][0] if len(filled) > 2 else None,
                        "candidate_3_pct": filled[2][1] if len(filled) > 2 else None,
                        "spread_label": spread_label,
                        "spread": (
                            filled[0][1] - filled[1][1]
                            if len(filled) >= 2 else None
                        ),
                        "rcp_url": rcp_url,
                        "source_url": page_url,
                    })
                i = j
                continue

            i += 1

    return polls


def fetch_all_polls():
    """
    Main entry point: scrape all latest 2026 polls from RealClearPolling.
    Returns (polls_list, raw_html_for_archive).
    """
    print("[RealClearPolling] Scraping latest 2026 polls...")
    all_polls = []
    raw_pages = {}
    
    urls = [
        ("2026 All", RCP_LATEST_2026),
        ("Senate", RCP_SENATE_POLLS),
        ("House", RCP_HOUSE_POLLS),
        ("Governor", RCP_GOVERNOR_POLLS),
    ]
    
    for label, url in urls:
        print(f"  Fetching {label} polls from {url}...")
        soup = fetch_page(url)
        if soup:
            raw_pages[label] = str(soup)[:50000]  # Truncate for archive
            
            # Try structured parser first, fall back to text parser
            polls = parse_rcp_structured(soup, url)
            if not polls:
                polls = parse_polls_table(soup, url)
            
            all_polls.extend(polls)
            print(f"    Found {len(polls)} polls")
        
        time.sleep(REQUEST_DELAY_SECONDS)
    
    # Deduplicate by (race_id, pollster, poll_date)
    seen = set()
    unique_polls = []
    for p in all_polls:
        key = (p["race_id"], p["pollster"], p["poll_date"])
        if key not in seen:
            seen.add(key)
            unique_polls.append(p)
    
    print(f"  Total unique polls found: {len(unique_polls)}")
    return unique_polls, raw_pages


if __name__ == "__main__":
    polls, raw = fetch_all_polls()
    for p in polls[:10]:
        print(f"  {p['poll_date']}  {p['race_id']:25s}  {p['pollster']:20s}  "
              f"{p.get('candidate_1','?')} {p.get('candidate_1_pct','')} vs "
              f"{p.get('candidate_2','?')} {p.get('candidate_2_pct','')}")
