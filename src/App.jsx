import { useState, useMemo, useCallback, useEffect } from "react";
import { XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, Area, AreaChart, ComposedChart, Line } from "recharts";

const DEM = "#4c72b0";
const REP = "#c44e52";
const POLL_AVG = "#6b91c1";
const S = "'Source Sans 3',Arial,sans-serif";

// Color palettes for primaries — all blues/teals for D, all reds/ambers for R.
// Never show red in a D primary or blue in an R primary.
const PRIMARY_PALETTE = {
  D: ["#1d4ed8", "#0891b2", "#7c3aed", "#0f766e", "#0e4ea3"],
  R: ["#b91c1c", "#c2410c", "#d97706", "#92400e", "#7c3aed"],
  I: ["#374151", "#4b5563", "#6b7280"],
};

const isD = s => s && /^(\(D\)|D |Ossoff|Peters|Platner|Mills|Brown|Talarico|Peltola|Generic D|Dem|Craig|Caraveo|Wild|Cartwright|Salinas|Vasquez|Gray)/.test(s);
const spreadColor = (d, r, spread) => {
  if (d != null && r != null) return d > r ? DEM : d < r ? REP : "#888";
  if (!spread) return "#888";
  return isD(spread) ? DEM : /^\(R\)/.test(spread) ? REP : "#888";
};

// Race type helpers
const isPrimary = race => race.race_type === "primary" || race.race_id?.includes("primary");
const primaryParty = race => race.primary_party
  || (race.race_id?.toUpperCase().includes("-D-") ? "D" : race.race_id?.toUpperCase().includes("-R-") ? "R" : null);
const primaryColors = race => PRIMARY_PALETTE[primaryParty(race)] || PRIMARY_PALETTE.D;

function formatPrimaryDate(d) {
  if (!d) return "—";
  const [, m, day] = d.split("-");
  const months = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[+m]} ${+day}`;
}

function primaryKalshiLeader(race) {
  const ts = race.time_series || [];
  if (!ts.length) return null;
  const lastPt = ts[ts.length - 1];
  let best = null, bestVal = -1;
  for (const [k, v] of Object.entries(lastPt)) {
    if (k === "date" || k === "isPollDate" || k === "pollster") continue;
    if (v != null && v > bestVal) { best = k; bestVal = v; }
  }
  return best ? { name: best, pct: bestVal } : null;
}

// Extract unique candidate names from polls in order of first appearance.
function pollCandidates(race) {
  const seen = new Map();
  (race.polls || []).forEach(p => {
    if (p.c1 && !seen.has(p.c1)) seen.set(p.c1, primaryParty(race) || "D");
    if (p.c2 && !seen.has(p.c2)) seen.set(p.c2, primaryParty(race) || "D");
    if (p.c3 && !seen.has(p.c3)) seen.set(p.c3, primaryParty(race) || "D");
  });
  return [...seen.keys()];
}

// Build a time series aligned to market snapshot dates, with one key per candidate.
// Uses candidate-keyed market data from time_series if available; overlays poll data on top.
function buildPrimaryTimeSeries(race) {
  const ts = race.time_series || [];

  // Discover candidate names from time_series keys (candidate-keyed market data)
  const mktCandidates = ts.length > 0
    ? [...new Set(ts.flatMap(pt => Object.keys(pt).filter(k => k !== "date" && k !== "isPollDate" && k !== "pollster")))]
    : [];

  // Also collect from polls
  const pollCands = pollCandidates(race);
  const candidates = mktCandidates.length > 0
    ? mktCandidates
    : pollCands;

  // Index polls by chart-date key ("M/D")
  const pollByDate = {};
  (race.polls || []).forEach(p => {
    const d = parseToDate(p.date);
    if (!d) return;
    const k = `${d.getMonth()+1}/${d.getDate()}`;
    if (!pollByDate[k]) pollByDate[k] = { pollster: p.pollster };
    if (p.c1 && p.d    != null) pollByDate[k][p.c1]  = p.d;
    if (p.c2 && p.r    != null) pollByDate[k][p.c2]  = p.r;
    if (p.c3 && p.c3pct != null) pollByDate[k][p.c3] = p.c3pct;
  });

  // For completed races, exclude election-day and later — market moves on live results
  const electionDate = race.result ? parseToDate(race.result.date) : null;

  const series = ts
    .filter(pt => {
      if (!electionDate) return true;
      const d = parseToDate(pt.date);
      return d == null || d < electionDate;
    })
    .map(pt => {
      const enhanced = { ...pt };
      if (pollByDate[pt.date]) {
        Object.assign(enhanced, pollByDate[pt.date]);
        enhanced.isPollDate = true;
      }
      return enhanced;
    });

  return { series, candidates };
}

// Parse a date string in any of our formats to a Date object (year assumed 2026)
function parseToDate(s) {
  if (!s) return null;
  s = String(s).trim();
  // YYYY-MM-DD (from DB / 538 export)
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  // "Mar 5" or "Mar 05" (display / fallback format)
  const MO = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
  const parts = s.split(/\s+/);
  if (parts.length === 2) {
    const mon = MO[parts[0].toLowerCase().slice(0, 3)];
    const day = parseInt(parts[1]);
    if (mon && day) return new Date(2026, mon - 1, day);
  }
  // "3/5" (chart time-series key format)
  if (/^\d{1,2}\/\d{1,2}$/.test(s)) {
    const [m, d] = s.split("/").map(Number);
    return new Date(2026, m - 1, d);
  }
  return null;
}

// Attach polls to time_series points and compute a rolling 30-day poll average.
// Mutates the race object in place — call after time_series is populated.
function enrichTimeSeries(race) {
  if (!race.time_series) return;
  if (isPrimary(race)) return; // primaries use buildPrimaryTimeSeries for poll overlay
  if (race.polls?.length) {
    // Step 1: attach individual polls to the time-series point on their date
    const lk = {};
    race.polls.forEach(p => {
      const d = parseToDate(p.date);
      if (!d) return;
      const k = `${d.getMonth()+1}/${d.getDate()}`;
      if (!lk[k]) lk[k] = [];
      lk[k].push(p);
    });
    race.time_series.forEach(pt => {
      const mp = lk[pt.date];
      if (mp) {
        pt.pollDem = mp[0].d; pt.pollRep = mp[0].r;
        pt.pollster = mp[0].pollster; pt.pollSpread = mp[0].spread;
        pt.pollMatchup = mp[0].matchup;
        if (mp.length > 1) pt.pollExtra = mp.slice(1);
      }
    });
    // Step 2: rolling 30-day poll average (Dem %) for every time-series point
    race.time_series.forEach(pt => {
      const ptDate = parseToDate(pt.date);
      if (!ptDate) return;
      const cutoff = new Date(ptDate);
      cutoff.setDate(cutoff.getDate() - 30);
      const recent = race.polls.filter(p => {
        const pd = parseToDate(p.date);
        return pd && pd >= cutoff && pd <= ptDate && p.d != null && p.r != null;
      });
      if (recent.length > 0)
        pt.pollAvgDem = Math.round(recent.reduce((s, p) => s + (p.d - p.r), 0) / recent.length);
    });
  }
}

/*
 * ── DATA LOADING ──
 * In production, this fetches dashboard_data.json exported by daily_snapshot.py.
 * The JSON contains: { updated, stats, races[] }
 * Each race has: race_id, chamber, state, district, description, dem_base,
 *   pm (polymarket slug), kalshi (ticker), rcp (url path), note, polls[], time_series[]
 *
 * For the artifact preview, we embed the data inline as a fallback.
 */

// ── Fallback: embedded data matching the real JSON shape ──
// This is used when dashboard_data.json isn't available (e.g., in the artifact preview).
// In production, the useEffect below fetches the live JSON instead.
const FALLBACK = buildFallbackData();

function buildFallbackData() {
  // Senate races
  const senate = [
    { race_id:"senate-control-2026", chamber:"senate", state:"US", description:"Senate Control", dem_base:0.47, pm:"which-party-will-win-the-senate-in-2026", kalshi:"controls/senate-winner", rcp:"polls/state-of-the-union/generic-congressional-vote", note:"Rep 54%, Dem 47%." },
    { race_id:"senate-GA-2026", chamber:"senate", state:"GA", description:"Georgia — Ossoff (D-inc) vs. TBD (R)", dem_base:0.81, pm:"georgia-senate-election-winner", kalshi:"senatega/georgia-senate-race/senatega-26", rcp:"polls/senate/general/2026/georgia", note:"Dem 81% Polymarket / 80% Kalshi. R primary May 19.",
      polls:[{date:"Mar 5",pollster:"Emerson",c1:"Ossoff",d:48,c2:"Collins",r:43,spread:"Ossoff +5",matchup:"Ossoff vs. Collins (general)",url:"https://emersoncollegepolling.com/georgia-2026-poll-senator-ossoff-starts-re-election-near-50-and-outpaces-gop-field/"},{date:"Mar 5",pollster:"Emerson",c1:"Ossoff",d:47,c2:"Carter",r:44,spread:"Ossoff +3",matchup:"Ossoff vs. Carter (general)"},{date:"Feb 18",pollster:"Quinnipiac",c1:"Ossoff",d:50,c2:"Collins",r:42,spread:"Ossoff +8",matchup:"Ossoff vs. Collins (general)"}] },
    { race_id:"senate-NC-2026", chamber:"senate", state:"NC", description:"North Carolina — Tillis (R-inc) vs. TBD (D)", dem_base:0.72, pm:"north-carolina-senate-election-winner", kalshi:"senatenc/north-carolina-senate-race/senatenc-26", rcp:"polls/senate/general/2026/north-carolina", note:"Dem ~72%. Competitive D primary.",
      polls:[{date:"Mar 2",pollster:"SurveyUSA",d:46,r:45,spread:"D +1",matchup:"Generic D vs. Tillis"},{date:"Feb 25",pollster:"PPP",d:44,r:47,spread:"Tillis +3",matchup:"Generic D vs. Tillis"}] },
    { race_id:"senate-MI-2026", chamber:"senate", state:"MI", description:"Michigan — Open (Peters D-retiring)", dem_base:0.77, pm:"michigan-senate-election-winner", kalshi:"senatemi/michigan-senate-race/senatemi-26", rcp:"polls/senate/general/2026/michigan",
      polls:[{date:"Feb 28",pollster:"Mitchell",d:51,r:40,spread:"Peters +11",matchup:"Peters vs. generic R"}] },
    { race_id:"senate-ME-2026", chamber:"senate", state:"ME", description:"Maine — Collins (R-inc) vs. TBD (D)", dem_base:0.74, pm:"maine-senate-election-winner", kalshi:"senateme/maine-senate-race/senateme-26", rcp:"polls/senate/general/2026/maine", note:"Dem ~74%. D primary June 9.",
      polls:[{date:"Mar 9",pollster:"Quantus",d:49,r:42,spread:"Platner +7",matchup:"Platner (D) vs. Collins (R)",url:"https://quantusinsights.org/f/maine-senate-2026-collins-faces-uncertain-path-to-re-election"},{date:"Mar 9",pollster:"Quantus",d:43,r:45,spread:"Collins +2",matchup:"Mills (D) vs. Collins (R)"},{date:"Mar 9",pollster:"Quantus",d:43,r:38,spread:"Platner +5",matchup:"D primary — Platner vs. Mills vs. Costello LaFlamme"}] },
    { race_id:"senate-AK-2026", chamber:"senate", state:"AK", description:"Alaska — Sullivan (R) vs. Peltola? (D)", dem_base:0.48, pm:"alaska-senate-election-winner", kalshi:"senateak/alaska-senate-race/senateak-26", note:"Ranked-choice. Sullivan 49%, Peltola 48%." },
    { race_id:"senate-NH-2026", chamber:"senate", state:"NH", description:"New Hampshire — Open (Shaheen D-retiring)", dem_base:0.68, kalshi:"senatenh/new-hampshire-senate-race/senatenh-26", rcp:"polls/senate/general/2026/new-hampshire", note:"Dem ~68%. Sununu vs. Scott Brown in R primary.",
      polls:[{date:"Feb 22",pollster:"UNH",d:48,r:44,spread:"D +4",matchup:"Generic D vs. Sununu"}] },
    { race_id:"senate-OH-2026", chamber:"senate", state:"OH", description:"Ohio — Brown (D) vs. Husted (R)", dem_base:0.58, kalshi:"senateoh/ohio-senate-race/senateoh-26", rcp:"polls/senate/general/2026/ohio", note:"Dem ~58%. Special election.",
      polls:[{date:"Feb 15",pollster:"Emerson",d:42,r:48,spread:"R +6",matchup:"Brown vs. Husted"}] },
    { race_id:"senate-TX-2026", chamber:"senate", state:"TX", description:"Texas — Cornyn/Paxton (R) vs. Talarico (D)", dem_base:0.28, pm:"texas-senate-election-winner", kalshi:"senatetx/texas-senate-race/senatetx-26", rcp:"polls/senate/general/2026/texas",
      polls:[{date:"Mar 1",pollster:"Emerson",d:38,r:52,spread:"Cornyn +14",matchup:"Generic D vs. Cornyn (pre-primary)"}] },
    { race_id:"primary-TX-senate-D-2026", chamber:"senate", state:"TX", description:"Texas Senate — Democratic Primary", dem_base:0.62, race_type:"primary", primary_party:"D",
      pm:"texas-senate-democratic-primary", kalshi:"senatetx-d-26", note:"Resolved March 3. $4.8M Kalshi volume.",
      result:{ winner:"James Talarico", party:"D", date:"Mar 3", pct:58.2, runner_up:"Jasmine Crockett", runner_up_pct:41.8 },
      polls:[{date:"Feb 28",pollster:"UT-Tyler",c1:"Talarico",d:52,c2:"Crockett",r:41,spread:"Talarico +11",matchup:"Talarico vs. Crockett (D primary)"}] },
    { race_id:"primary-TX-senate-R-2026", chamber:"senate", state:"TX", description:"Texas Senate — Republican Primary", dem_base:0.45, race_type:"primary", primary_party:"R",
      kalshi:"senatetx-r-26", note:"Headed to runoff. No candidate reached 50%.",
      result:{ winner:"Runoff: Cornyn vs. Paxton", party:"R", date:"Mar 3", pct:null, runner_up:null, runner_up_pct:null, note:"Cornyn 38%, Paxton 32%. Runoff TBD." },
      polls:[{date:"Feb 10",pollster:"UT-Tyler",c1:"Cornyn",d:38,c2:"Paxton",r:32,c3:"Abbott",c3pct:18,spread:"Cornyn +6",matchup:"Cornyn vs. Paxton vs. Abbott (R primary)"}] },
    { race_id:"senate-IA-2026", chamber:"senate", state:"IA", description:"Iowa — Grassley (R-retiring)", dem_base:0.42, kalshi:"senateia/iowa-senate-race/senateia-26", note:"Could be competitive in blue wave." },
    { race_id:"senate-IL-2026", chamber:"senate", state:"IL", description:"Illinois — Durbin (D-retiring)", dem_base:0.82, kalshi:"senateil/illinois-senate-race/senateil-26", rcp:"polls/senate/general/2026/illinois",
      polls:[{date:"Mar 1",pollster:"Victory",d:55,r:32,spread:"D +23",matchup:"Generic D vs. generic R"}] },
    ...["VA","MN","NJ","CO"].map(st => ({ race_id:`senate-${st}-2026`, chamber:"senate", state:st, description:{VA:"Virginia — Warner (D)",MN:"Minnesota — Klobuchar (D)",NJ:"New Jersey — Open (D-held)",CO:"Colorado — Hickenlooper (D)"}[st], dem_base:{VA:0.72,MN:0.78,NJ:0.75,CO:0.80}[st], kalshi:`senate${st.toLowerCase()}/senate-race/senate${st.toLowerCase()}-26` })),
    { race_id:"senate-NE-2026", chamber:"senate", state:"NE", description:"Nebraska — Independent candidate", dem_base:0.05, pm:"nebraska-senate-election-winner", kalshi:"senatene/nebraska-senate-race/senatene-26", note:"Rep 69%, Ind ~26%, Dem 5%." },
    { race_id:"senate-FL-2026", chamber:"senate", state:"FL", description:"Florida — Special election", dem_base:0.30, kalshi:"senatefl/florida-senate-race/senatefl-26" },
    { race_id:"senate-KY-2026", chamber:"senate", state:"KY", description:"Kentucky — McConnell (R-retiring)", dem_base:0.15, kalshi:"senateky/kentucky-senate-race/senateky-26" },
    ...["MA","OR","DE"].map(st => ({ race_id:`senate-${st}-2026`, chamber:"senate", state:st, description:{MA:"Massachusetts — Markey (D)",OR:"Oregon — Merkley (D)",DE:"Delaware — Open (D)"}[st], dem_base:{MA:0.92,OR:0.90,DE:0.88}[st], kalshi:`senate${st.toLowerCase()}-26` })),
    ...["WV","SC","AL","AR","ID"].map(st => ({ race_id:`senate-${st}-2026`, chamber:"senate", state:st, description:{WV:"West Virginia (R)",SC:"South Carolina — Graham (R)",AL:"Alabama (R)",AR:"Arkansas — Cotton (R)",ID:"Idaho — Crapo (R)"}[st], dem_base:{WV:0.07,SC:0.10,AL:0.05,AR:0.04,ID:0.03}[st], kalshi:`senate${st.toLowerCase()}-26` })),
  ];
  // House races
  const house_data = [
    ["CA-13",0.52],["CA-22",0.46],["CA-27",0.49],["CA-40",0.47],["CA-45",0.50],["CO-8",0.48],["CT-5",0.55],
    ["IA-1",0.45],["IA-2",0.44],["ME-2",0.52],["MI-7",0.48],["MI-8",0.50],["MN-2",0.53],["NE-2",0.47],
    ["NJ-7",0.52],["NM-2",0.50],["NY-4",0.55],["NY-17",0.53],["NY-18",0.51],["NY-19",0.50],
    ["OH-9",0.48],["OR-5",0.52],["PA-1",0.49],["PA-7",0.53],["PA-8",0.47],["PA-10",0.50],
    ["TX-15",0.44],["TX-34",0.46],["VA-2",0.52],["VA-7",0.50],["WA-3",0.48],["WI-1",0.47],["AZ-1",0.48],["AZ-6",0.46],
  ];
  const house = house_data.map(([d, dem]) => {
    const [st, dist] = d.split("-");
    return { race_id:`house-${st}-${dist}-2026`, chamber:"house", state:st, district:dist, description:`${d}`, dem_base:dem, kalshi:`house${st.toLowerCase()}${dist}-26`, rcp:"latest-polls/house" };
  });
  // Control + governor
  const control = [
    { race_id:"house-control-2026", chamber:"house", state:"US", description:"House Control", dem_base:0.78, pm:"which-party-will-win-the-house-in-2026", kalshi:"controls/house-winner" },
  ];
  const gov = [
    { race_id:"governor-AK-2026", chamber:"governor", state:"AK", description:"Alaska Governor — Begich vs. Dahlstrom", dem_base:0.45, pm:"alaska-governor-election-winner" },
    { race_id:"governor-AZ-2026", chamber:"governor", state:"AZ", description:"Arizona Governor — Hobbs (D) vs. TBD", dem_base:0.52 },
    { race_id:"governor-CA-2026", chamber:"governor", state:"CA", description:"California Governor — Open", dem_base:0.70, note:"Top-two primary June 2." },
    { race_id:"governor-NY-2026", chamber:"governor", state:"NY", description:"New York Governor", dem_base:0.88, pm:"new-york-governor-winner-2026" },
    { race_id:"governor-FL-2026", chamber:"governor", state:"FL", description:"Florida Governor — Open", dem_base:0.35 },
    { race_id:"governor-GA-2026", chamber:"governor", state:"GA", description:"Georgia Governor — Open", dem_base:0.42 },
  ];

  const allRaces = [...senate, ...control, ...house, ...gov];
  // Generate time series for fallback
  allRaces.forEach(r => {
    if (!r.time_series) {
      const ts = []; let v = r.dem_base, k = r.dem_base;
      for (let i = 0; i < 30; i++) {
        const dt = new Date(2026, 1, 7 + i);
        v = Math.min(.99, Math.max(.01, v + (Math.random() - .48) * .03));
        k = Math.min(.99, Math.max(.01, k + (Math.random() - .48) * .03));
        ts.push({ date: `${dt.getMonth()+1}/${dt.getDate()}`, polymarket: r.pm ? Math.round(v * 100) : null, kalshi: Math.round(k * 100) });
      }
      r.time_series = ts;
    }
  });

  // Enrich time series: attach polls + compute rolling averages
  allRaces.forEach(r => enrichTimeSeries(r));

  const nSen = allRaces.filter(r => r.chamber === "senate" && r.state !== "US").length;
  const nHouse = allRaces.filter(r => r.chamber === "house" && r.state !== "US").length;
  return {
    updated: "2026-03-10",
    stats: { senate_rep_pct: 54, senate_dem_pct: 47, house_dem_pct: 78, house_rep_pct: 22, battleground_senate: 4, battleground_house: nHouse, house_districts_tracked: nHouse, seats_up: 35, polls_tracked: allRaces.reduce((n, r) => n + (r.polls?.length || 0), 0) },
    races: allRaces,
  };
}

// ── Chart components ──
function Spark({data,id}){return(<ResponsiveContainer width={86} height={24}><AreaChart data={data} margin={{top:2,right:0,bottom:2,left:0}}><Area type="monotone" dataKey={data.some(d=>d.polymarket)?"polymarket":"kalshi"} stroke="#888" fill="none" strokeWidth={1.2} dot={false}/><ReferenceLine y={50} stroke="#ddd" strokeWidth={.5}/></AreaChart></ResponsiveContainer>);}

function fmtMargin(v){if(v==null)return null;const r=Math.round(v);if(r===0)return{label:"Even",color:"#555"};if(r>0)return{label:`D +${r}`,color:DEM};return{label:`R +${Math.abs(r)}`,color:REP};}

function Tip({active,payload}){if(!active||!payload?.length)return null;const pt=payload[0]?.payload;if(!pt)return null;const hp=pt.pollDem!=null;
  const pm=fmtMargin(pt.polymarket),km=fmtMargin(pt.kalshi),pa=fmtMargin(pt.pollAvgDem);
  return(<div style={{background:"#fff",border:"1px solid #ddd",padding:"10px 14px",fontSize:13,color:"#222",boxShadow:"0 2px 8px rgba(0,0,0,.08)",maxWidth:280,lineHeight:1.5,fontFamily:S}}>
    <div style={{fontWeight:600,marginBottom:4,color:"#999",fontSize:12}}>{pt.date}</div>
    {pm&&<div style={{display:"flex",justifyContent:"space-between",gap:16}}><span>Polymarket</span><strong style={{color:pm.color}}>{pm.label}</strong></div>}
    {km&&<div style={{display:"flex",justifyContent:"space-between",gap:16}}><span>Kalshi</span><strong style={{color:km.color}}>{km.label}</strong></div>}
    {pa&&<div style={{display:"flex",justifyContent:"space-between",gap:16,color:POLL_AVG}}><span>Poll avg. (30d)</span><strong style={{color:pa.color}}>{pa.label}</strong></div>}
    {hp&&(<div style={{borderTop:"1px solid #eee",marginTop:8,paddingTop:8}}>
      <div style={{fontWeight:700,fontSize:11,textTransform:"uppercase",letterSpacing:".04em",color:"#999",marginBottom:4}}>Poll released</div>
      <div style={{fontWeight:500}}>{pt.pollster}</div>
      {pt.pollMatchup&&<div style={{fontSize:12,color:"#888"}}>{pt.pollMatchup}</div>}
      <div style={{display:"flex",gap:14,marginTop:3}}><span style={{color:DEM,fontWeight:600}}>Dem {pt.pollDem}%</span><span style={{color:REP,fontWeight:600}}>Rep {pt.pollRep}%</span><span style={{marginLeft:"auto",fontWeight:700,color:spreadColor(pt.pollDem,pt.pollRep,pt.pollSpread)}}>{pt.pollSpread}</span></div>
      {pt.pollExtra?.map((pe,i)=>(<div key={i} style={{marginTop:6,paddingTop:6,borderTop:"1px dashed #e5e5e5"}}><div style={{fontWeight:500}}>{pe.pollster}</div>{pe.matchup&&<div style={{fontSize:12,color:"#888"}}>{pe.matchup}</div>}<div style={{display:"flex",gap:14,marginTop:2}}><span style={{color:DEM}}>Dem {pe.d}%</span><span style={{color:REP}}>Rep {pe.r}%</span></div></div>))}
    </div>)}</div>);}

// Label rendered at the top of each poll release reference line.
// Shows first word of pollster name + spread so the mark is identifiable at a glance.
function PollLineLabel({ viewBox, pollster, spread, value }) {
  if (!viewBox) return null;
  const { x, y, height } = viewBox;
  const color = value == null ? "#aaa" : value > 0 ? DEM : value < 0 ? REP : "#888";
  const name = (pollster || "Poll").split(/\s+/)[0];
  const txt = spread ? `${name}: ${spread}` : name;
  // Place dot at the poll margin's position on the -100→+100 scale
  const dotY = value != null ? y + height * (100 - value) / 200 : null;
  return (
    <g>
      {dotY != null && <circle cx={x} cy={dotY} r={3.5} fill={color} opacity={0.75} stroke="#fff" strokeWidth={1}/>}
      <text
        x={x + 3} y={y + 4}
        fontSize={8.5} fill={color} opacity={0.8}
        fontFamily="Arial,sans-serif"
        transform={`rotate(-90, ${x + 3}, ${y + 4})`}
        textAnchor="start"
      >{txt}</text>
    </g>
  );
}

// ── General election chart (D/R advantage margin, full -100 to +100 scale) ──
function GeneralChart({data, race}) {
  // Convert Dem win-probability (0–100) → partisan margin (-100 to +100)
  const chartData = data.map(pt=>({
    ...pt,
    polymarket: pt.polymarket!=null ? 2*pt.polymarket-100 : null,
    kalshi:     pt.kalshi    !=null ? 2*pt.kalshi    -100 : null,
    pollAvgDem: pt.pollAvgDem!=null ? pt.pollAvgDem : null,
  }));
  const hasPM=data.some(d=>d.polymarket!=null),hasK=data.some(d=>d.kalshi!=null);
  const hasPollAvg=data.some(d=>d.pollAvgDem!=null);
  if(!hasPM&&!hasK&&!hasPollAvg)return null;
  const pollPoints=chartData.filter(d=>d.pollDem!=null);
  const fmtY=v=>v===0?"Even":v>0?`D+${v}`:`R+${Math.abs(v)}`;
  return(<>
    <ResponsiveContainer width="100%" height={300}><ComposedChart data={chartData} margin={{top:16,right:12,bottom:8,left:0}}>
      <defs>
        <linearGradient id="demZone" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={DEM} stopOpacity={0.10}/><stop offset="100%" stopColor={DEM} stopOpacity={0.02}/></linearGradient>
        <linearGradient id="repZone" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={REP} stopOpacity={0.02}/><stop offset="100%" stopColor={REP} stopOpacity={0.10}/></linearGradient>
      </defs>
      <XAxis dataKey="date" tick={{fontSize:11,fill:"#999"}} tickLine={false} axisLine={{stroke:"#ddd"}} interval="preserveStartEnd"/>
      <YAxis domain={[-100,100]} ticks={[-100,-50,0,50,100]} tick={{fontSize:10,fill:"#999"}} tickLine={false} axisLine={false} tickFormatter={fmtY} width={46}/>
      <Tooltip content={<Tip/>}/>
      <ReferenceArea y1={0} y2={100} fill="url(#demZone)"/>
      <ReferenceArea y1={-100} y2={0} fill="url(#repZone)"/>
      <ReferenceLine y={0} stroke="#bbb" strokeWidth={1.5}/>
      {pollPoints.map(pt=>(
        <ReferenceLine key={`poll-${pt.date}`} x={pt.date} stroke="#c8c8c8" strokeWidth={1} strokeDasharray="3 3"
          label={<PollLineLabel pollster={pt.pollster} spread={pt.pollSpread} value={pt.pollDem!=null&&pt.pollRep!=null?pt.pollDem-pt.pollRep:null}/>}/>
      ))}
      {hasPM&&<Line type="monotone" dataKey="polymarket" stroke="#222" strokeWidth={2} dot={false} connectNulls={true}/>}
      {hasK&&<Line type="monotone" dataKey="kalshi" stroke={hasPM?"#aaa":"#222"} strokeWidth={hasPM?1.5:2} dot={false} strokeDasharray={hasPM?"5 3":"0"} connectNulls={true}/>}
      {hasPollAvg&&<Line type="monotone" dataKey="pollAvgDem" stroke={POLL_AVG} strokeWidth={1.5} dot={false} strokeDasharray="6 3" connectNulls={true}/>}
    </ComposedChart></ResponsiveContainer>
    {/* Legend */}
    <div style={{display:"flex",gap:18,marginTop:6,marginBottom:16,fontSize:12,color:"#888",flexWrap:"wrap",fontFamily:S}}>
      {hasPM&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,height:2,background:"#222",display:"inline-block"}}/>Polymarket</span>}
      {hasK&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,borderTop:`2px ${hasPM?"dashed":"solid"} ${hasPM?"#aaa":"#222"}`,display:"inline-block"}}/>Kalshi</span>}
      {hasPollAvg&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,borderTop:`2px dashed ${POLL_AVG}`,display:"inline-block"}}/>Poll avg. (30d)</span>}
      {pollPoints.length>0&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{display:"inline-block",width:1,height:13,borderLeft:"1px dashed #bbb",marginRight:1}}/>Poll release</span>}
      <span style={{marginLeft:"auto",color:"#bbb",fontSize:11}}>Y-axis = D/R margin (pts)</span>
    </div>
  </>);}

// ── Primary election chart (per-candidate poll support lines, multi-color) ──
function PrimaryTip({active, payload, colorMap}) {
  if(!active||!payload?.length)return null;
  const pt=payload[0]?.payload;
  if(!pt)return null;
  // Sort by current point value descending so leader is always on top
  const sorted = Object.keys(colorMap)
    .filter(c=>pt[c]!=null)
    .sort((a,b)=>pt[b]-pt[a]);
  return(
    <div style={{background:"#fff",border:"1px solid #ddd",padding:"10px 14px",fontSize:13,color:"#222",boxShadow:"0 2px 8px rgba(0,0,0,.08)",maxWidth:260,lineHeight:1.6,fontFamily:S}}>
      <div style={{fontWeight:600,marginBottom:6,color:"#999",fontSize:12}}>{pt.date}</div>
      {sorted.map(c=>(
        <div key={c} style={{display:"flex",justifyContent:"space-between",gap:20}}>
          <span style={{color:colorMap[c],fontWeight:500}}>{c}</span>
          <strong style={{color:colorMap[c]}}>{pt[c]}%</strong>
        </div>
      ))}
      {pt.isPollDate&&<div style={{borderTop:"1px solid #eee",marginTop:6,paddingTop:5,fontSize:11,color:"#aaa"}}>
        {pt.pollster}
      </div>}
    </div>
  );
}

// Shared: compute a stable candidate→color map for a primary race.
// Sorted by: winner first (if result exists), runner-up second, then by last known market price.
function primaryColorMap(race) {
  const party = primaryParty(race) || "D";
  const colors = PRIMARY_PALETTE[party];
  const ts = race.time_series || [];
  const lastPt = ts[ts.length - 1] || {};
  const res = race.result;
  // Candidates from time series keys
  const candidates = ts.length > 0
    ? [...new Set(ts.flatMap(pt => Object.keys(pt).filter(k => k !== "date" && k !== "isPollDate" && k !== "pollster")))]
    : pollCandidates(race);
  const sorted = [...candidates].sort((a, b) => {
    if (res) {
      const ra = a === res.winner ? 0 : a === res.runner_up ? 1 : 2;
      const rb = b === res.winner ? 0 : b === res.runner_up ? 1 : 2;
      if (ra !== rb) return ra - rb;
    }
    return (lastPt[b] ?? -1) - (lastPt[a] ?? -1);
  });
  return Object.fromEntries(sorted.map((c, i) => [c, colors[i % colors.length]]));
}

function PrimaryChart({race}) {
  const {series, candidates} = buildPrimaryTimeSeries(race);
  const colorMap = primaryColorMap(race);
  // Respect the colorMap's insertion order (already sorted)
  const sortedCandidates = Object.keys(colorMap).filter(c => candidates.includes(c));

  const party = primaryParty(race) || "D";
  const colors = PRIMARY_PALETTE[party];

  // Determine y-axis range from poll values
  const allVals = series.flatMap(pt=>sortedCandidates.map(c=>pt[c]).filter(v=>v!=null));
  if(!allVals.length) return(
    <div style={{padding:"20px 0",color:"#aaa",fontSize:13,fontStyle:"italic",fontFamily:S}}>
      No market or poll data for this primary yet.
    </div>
  );

  const lo=Math.min(...allVals),hi=Math.max(...allVals);
  const yMin=Math.max(0,Math.floor((lo-8)/5)*5),yMax=Math.min(100,Math.ceil((hi+8)/5)*5);
  const pollDates = series.filter(pt=>pt.isPollDate);
  const bg = party==="D" ? "#eff6ff" : "#fff5f5";
  const borderClr = colors[0]+"33";

  return(<>
    <ResponsiveContainer width="100%" height={230}><ComposedChart data={series} margin={{top:8,right:12,bottom:8,left:0}}>
      <XAxis dataKey="date" tick={{fontSize:11,fill:"#999"}} tickLine={false} axisLine={{stroke:"#ddd"}} interval={4}/>
      <YAxis domain={[yMin,yMax]} tick={{fontSize:11,fill:"#999"}} tickLine={false} axisLine={false} tickFormatter={v=>`${v}%`} width={34}/>
      <Tooltip content={<PrimaryTip colorMap={colorMap}/>}/>
      {/* Vertical markers at each poll date */}
      {pollDates.map(pt=>(
        <ReferenceLine key={`pp-${pt.date}`} x={pt.date} stroke="#ddd" strokeWidth={1} strokeDasharray="3 3"/>
      ))}
      {/* One line per candidate */}
      {sortedCandidates.map(c=>(
        <Line key={c} type="linear" dataKey={c}
          stroke={colorMap[c]} strokeWidth={2.5}
          dot={false} activeDot={{r:5}} connectNulls={false} isAnimationActive={false}/>
      ))}
    </ComposedChart></ResponsiveContainer>
    {/* Candidate color legend — sorted by final result */}
    <div style={{display:"flex",gap:18,marginTop:6,marginBottom:16,fontSize:12,flexWrap:"wrap",fontFamily:S}}>
      {sortedCandidates.map(c=>(
        <span key={c} style={{display:"flex",alignItems:"center",gap:6}}>
          <span style={{width:14,height:14,borderRadius:"50%",background:colorMap[c],display:"inline-block",flexShrink:0}}/>
          <span style={{color:colorMap[c],fontWeight:600}}>{c}</span>
        </span>
      ))}
      <span style={{marginLeft:"auto",color:"#bbb",fontSize:11}}>Y-axis = poll support %</span>
    </div>
  </>);}

// ── Dispatcher: picks the right chart based on race type ──
function RaceChart({race}) {
  const data = race.time_series || [];
  if(isPrimary(race)) return <PrimaryChart race={race}/>;
  return <GeneralChart data={data} race={race}/>;
}

function rat(d){if(d>=.85)return{l:"Safe D.",c:DEM};if(d>=.60)return{l:"Lean D.",c:DEM};if(d>=.40)return{l:"Toss-up",c:"#7c3aed"};if(d>=.15)return{l:"Lean R.",c:REP};return{l:"Safe R.",c:REP};}

// ── Detail panel ──
function Detail({race,onClose}){
  const data=race.time_series||[];
  const primary=isPrimary(race);

  // For primary races: compute market leader and latest poll leader from shared colorMap
  const cmap = primary ? primaryColorMap(race) : null;
  const sortedCands = cmap ? Object.keys(cmap) : [];

  // Current market leader = candidate with highest value in last pre-election time series point
  const lastPt = data[data.length-1] || {};
  const mktLeader = sortedCands.length ? sortedCands.find(c => lastPt[c] != null) : null;
  const mktLeaderPct = mktLeader ? lastPt[mktLeader] : null;

  // Latest poll leader
  const lp = race.polls?.[0];
  let pollLeader = null, pollLeaderPct = null;
  if (lp && primary && cmap) {
    const pm = {};
    if (lp.c1 && lp.d    != null) pm[lp.c1]  = lp.d;
    if (lp.c2 && lp.r    != null) pm[lp.c2]  = lp.r;
    if (lp.c3 && lp.c3pct!= null) pm[lp.c3]  = lp.c3pct;
    pollLeader = Object.entries(pm).sort((a,b)=>b[1]-a[1])[0]?.[0] || null;
    pollLeaderPct = pollLeader ? pm[pollLeader] : null;
  }

  // Unique poll candidates (sorted by market order for consistent columns)
  const pollCandSet = new Set();
  if (primary) (race.polls||[]).forEach(p=>{
    if(p.c1)pollCandSet.add(p.c1);
    if(p.c2)pollCandSet.add(p.c2);
    if(p.c3)pollCandSet.add(p.c3);
  });
  const pollCols = [...sortedCands.filter(c=>pollCandSet.has(c)),
                    ...[...pollCandSet].filter(c=>!sortedCands.includes(c))].slice(0,4);

  return(
  <tr><td colSpan={7} style={{padding:0,borderBottom:"1px solid #ddd"}}>
    <div style={{borderTop:"2px solid #222",padding:"20px 16px 24px",background:"#fafafa",animation:"so .25s ease"}}>
      <style>{`@keyframes so{from{max-height:0;opacity:0}to{max-height:900px;opacity:1}}`}</style>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:14}}>
        <div>
          <h3 style={{fontSize:20,fontWeight:700,margin:0,fontFamily:"Georgia,'Times New Roman',serif"}}>{race.description}</h3>
          {race.note&&<p style={{fontSize:13,color:"#666",margin:"4px 0 0",fontFamily:S}}>{race.note}</p>}
        </div>
        <button onClick={e=>{e.stopPropagation();onClose();}} style={{background:"none",border:"1px solid #ccc",color:"#666",borderRadius:3,padding:"4px 12px",cursor:"pointer",fontSize:12,fontFamily:S}}>Close</button>
      </div>

      {/* Primary: market leader + latest poll panels */}
      {primary && (mktLeader || lp) && (
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:16}}>
          <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px"}}>
            <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>Market Leader</div>
            {mktLeader ? (
              <>
                <div style={{fontSize:26,fontWeight:700,color:cmap[mktLeader],fontFamily:"Georgia,'Times New Roman',serif",marginBottom:4}}>{mktLeaderPct}%</div>
                <div style={{fontSize:13,color:"#555",fontFamily:S}}>{mktLeader}</div>
              </>
            ) : <div style={{fontSize:13,color:"#aaa",fontFamily:S,fontStyle:"italic"}}>No market data yet</div>}
            <div style={{display:"flex",gap:12,marginTop:10,flexWrap:"wrap"}}>
              {race.pm&&<a href={`https://polymarket.com/event/${race.pm}`} target="_blank" rel="noopener noreferrer" style={{fontSize:12,color:"#555",textDecoration:"none",borderBottom:"1px solid #ccc",fontFamily:S}} onClick={e=>e.stopPropagation()}>Polymarket ↗</a>}
              {race.kalshi&&<a href={race.kalshi_url||`https://kalshi.com/markets/${race.kalshi}`} target="_blank" rel="noopener noreferrer" style={{fontSize:12,color:"#555",textDecoration:"none",borderBottom:"1px solid #ccc",fontFamily:S}} onClick={e=>e.stopPropagation()}>Kalshi ↗</a>}
            </div>
          </div>
          <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px"}}>
            <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>Latest Poll</div>
            {lp && pollLeader ? (
              <>
                <div style={{fontSize:26,fontWeight:700,color:cmap[pollLeader]||"#333",fontFamily:"Georgia,'Times New Roman',serif",marginBottom:4}}>{pollLeaderPct}%</div>
                <div style={{fontSize:13,color:"#555",fontFamily:S,marginBottom:4}}>{pollLeader}</div>
                <div style={{fontSize:12,color:"#aaa",fontFamily:S}}>{lp.pollster}, {lp.date}</div>
              </>
            ) : <div style={{fontSize:13,color:"#aaa",fontFamily:S,fontStyle:"italic"}}>No polls yet</div>}
          </div>
        </div>
      )}

      <RaceChart race={race}/>

      {/* General race links */}
      {!primary && <div style={{display:"flex",gap:16,marginBottom:20,fontSize:13,fontFamily:S,flexWrap:"wrap"}}>
        {race.pm&&<a href={`https://polymarket.com/event/${race.pm}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Polymarket ↗</a>}
        {race.kalshi&&<a href={race.kalshi_url||`https://kalshi.com/markets/${race.kalshi}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Kalshi ↗</a>}
      </div>}

      {/* Primary polls — structured table */}
      {primary && race.polls?.length > 0 && (
        <div style={{fontFamily:S}}>
          <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"#999",marginBottom:8}}>Polls</div>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
            <thead>
              <tr style={{borderBottom:"1px solid #e0e0e0"}}>
                <th style={{padding:"4px 8px",textAlign:"left",color:"#aaa",fontWeight:600,fontSize:11}}>Pollster</th>
                <th style={{padding:"4px 8px",textAlign:"left",color:"#aaa",fontWeight:600,fontSize:11}}>Date</th>
                {pollCols.map(c=>(
                  <th key={c} style={{padding:"4px 8px",textAlign:"right",color:cmap[c]||"#aaa",fontWeight:700,fontSize:11}}>{c.split(" ").pop()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {race.polls.map((p,i)=>{
                const pm={};
                if(p.c1&&p.d    !=null)pm[p.c1]=p.d;
                if(p.c2&&p.r    !=null)pm[p.c2]=p.r;
                if(p.c3&&p.c3pct!=null)pm[p.c3]=p.c3pct;
                return(
                  <tr key={i} style={{borderBottom:"1px solid #f0f0f0"}}>
                    <td style={{padding:"6px 8px"}}>
                      {p.url?<a href={p.url} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()} style={{color:"#333",textDecoration:"none",borderBottom:"1px solid #ccc"}}>{p.pollster}</a>:<span style={{color:"#333"}}>{p.pollster}</span>}
                    </td>
                    <td style={{padding:"6px 8px",color:"#888"}}>{p.date}</td>
                    {pollCols.map(c=>(
                      <td key={c} style={{padding:"6px 8px",textAlign:"right",fontWeight:pm[c]!=null?700:400,color:pm[c]!=null?(cmap[c]||"#333"):"#ddd"}}>
                        {pm[c]!=null?`${pm[c]}%`:"—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {primary && !race.polls?.length && <p style={{fontSize:13,color:"#aaa",fontStyle:"italic",fontFamily:S}}>No polls have been released for this race yet.</p>}

      {/* General race polls — existing flat list */}
      {!primary && race.polls?.length>0&&(<div style={{fontFamily:S}}>
        <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"#999",marginBottom:8}}>Polls</div>
        {race.polls.map((p,i)=>(
          <div key={i} style={{padding:"8px 0",borderTop:i?"1px solid #e8e8e8":"none"}}>
            <div style={{display:"flex",alignItems:"baseline",gap:10,flexWrap:"wrap"}}>
              <span style={{fontSize:13,color:"#999",width:46}}>{p.date}</span>
              {p.url?<a href={p.url} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()} style={{fontSize:13,fontWeight:600,color:"#333",textDecoration:"none",borderBottom:"1px solid #ccc"}}>{p.pollster}</a>:<span style={{fontSize:13,fontWeight:600,color:"#333"}}>{p.pollster}</span>}
              {p.d!=null&&<span style={{fontSize:14,fontWeight:700,color:DEM}}>Dem {p.d}%</span>}
              {p.r!=null&&<><span style={{color:"#ccc"}}>–</span><span style={{fontSize:14,fontWeight:700,color:REP}}>Rep {p.r}%</span></>}
              <span style={{fontSize:13,fontWeight:700,marginLeft:"auto",color:spreadColor(p.d,p.r,p.spread)}}>{p.spread}</span>
            </div>
            {p.matchup&&<div style={{fontSize:12,color:"#999",marginTop:2,paddingLeft:56}}>{p.matchup}</div>}
          </div>
        ))}
      </div>)}
      {!primary&&!race.polls?.length&&<p style={{fontSize:13,color:"#aaa",fontStyle:"italic",fontFamily:S}}>No polls have been released for this race yet.</p>}
    </div>
  </td></tr>);}

// ── Helpers for completed race accuracy analysis ──
function winnerMarketProb(race) {
  const ts = race.time_series || [];
  const res = race.result;
  if (!res || !ts.length) return null;
  // Use last pre-election-day data point — election day itself is polluted by
  // live result flow and settlement, making the midpoint meaningless.
  const electionDate = parseToDate(res.date);
  for (let i = ts.length - 1; i >= 0; i--) {
    const pt = ts[i];
    if (electionDate) {
      const ptDate = parseToDate(pt.date);
      if (ptDate && ptDate >= electionDate) continue;
    }
    if (isPrimary(race)) {
      if (pt[res.winner] != null) return pt[res.winner];
    } else {
      const p = pt.polymarket ?? pt.kalshi;
      if (p != null) return res.party === "D" ? p : Math.round(100 - p);
    }
  }
  return null;
}

function pollVsResult(race) {
  const polls = race.polls || [];
  const res = race.result;
  if (!polls.length || !res || res.pct == null || res.runner_up_pct == null) return null;
  const lp = polls[0];
  const actual = +(res.pct - res.runner_up_pct).toFixed(1);
  let wPct, ruPct;
  if (isPrimary(race)) {
    // Build name→pct map covering all three candidate slots
    const cm = {};
    if (lp.c1 && lp.d    != null) cm[lp.c1]  = lp.d;
    if (lp.c2 && lp.r    != null) cm[lp.c2]  = lp.r;
    if (lp.c3 && lp.c3pct!= null) cm[lp.c3]  = lp.c3pct;
    wPct  = cm[res.winner];
    ruPct = cm[res.runner_up];
  } else {
    wPct  = res.party === "D" ? lp.d : lp.r;
    ruPct = res.party === "D" ? lp.r : lp.d;
  }
  if (wPct == null) return null;
  const predicted = +(wPct - (ruPct || 0)).toFixed(1);
  const error = +(Math.abs(actual - predicted)).toFixed(1);
  return { predicted, actual, error, correct: predicted > 0, pollster: lp.pollster, date: lp.date };
}

// ── Completed race detail ──
function CompletedDetail({race, onClose}) {
  const data = race.time_series || [];
  const res = race.result;
  const winColor = res.party === "D" ? DEM : res.party === "R" ? REP : "#666";
  const totalPct = (res.pct || 0) + (res.runner_up_pct || 0);
  const winWidth = totalPct > 0 ? (res.pct / totalPct * 100) : 50;
  const marketProb = winnerMarketProb(race);
  const pollComp = pollVsResult(race);

  return (
    <tr><td colSpan={5} style={{padding:0,borderBottom:"1px solid #ddd"}}>
      <div style={{borderTop:`3px solid ${winColor}`,padding:"20px 16px 24px",background:"#fafafa",animation:"so .25s ease"}}>
        <style>{`@keyframes so{from{max-height:0;opacity:0}to{max-height:900px;opacity:1}}`}</style>

        {/* Header */}
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:16}}>
          <div>
            <h3 style={{fontSize:20,fontWeight:700,margin:0,fontFamily:"Georgia,'Times New Roman',serif"}}>{race.description}</h3>
            {race.note&&<p style={{fontSize:13,color:"#666",margin:"4px 0 0",fontFamily:S}}>{race.note}</p>}
          </div>
          <button onClick={e=>{e.stopPropagation();onClose();}} style={{background:"none",border:"1px solid #ccc",color:"#666",borderRadius:3,padding:"4px 12px",cursor:"pointer",fontSize:12,fontFamily:S}}>Close</button>
        </div>

        {/* Election result */}
        <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px 20px",marginBottom:16}}>
          <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>Result — Called {res.date}</div>
          <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:res.pct != null ? 12 : 0}}>
            <span style={{fontSize:22,fontWeight:700,color:winColor,fontFamily:"Georgia,'Times New Roman',serif"}}>✓ {res.winner}</span>
            {res.pct != null && <span style={{fontSize:18,fontWeight:700,color:winColor}}>{res.pct}%</span>}
          </div>
          {res.runner_up && res.runner_up_pct != null && (
            <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:12}}>
              <span style={{fontSize:16,color:"#888",fontFamily:S}}>{res.runner_up}</span>
              <span style={{fontSize:16,color:"#888"}}>{res.runner_up_pct}%</span>
            </div>
          )}
          {res.pct != null && res.runner_up_pct != null && (
            <>
              <div style={{display:"flex",height:8,borderRadius:4,overflow:"hidden",background:"#eee",marginBottom:8}}>
                <div style={{width:`${winWidth}%`,background:winColor,borderRadius:"4px 0 0 4px",transition:"width .5s"}} />
                <div style={{flex:1,background:"#ddd",borderRadius:"0 4px 4px 0"}} />
              </div>
              <div style={{fontSize:13,color:"#555",fontFamily:S}}>Won by {+(res.pct - res.runner_up_pct).toFixed(1)} points</div>
            </>
          )}
          {res.note && res.pct == null && (
            <div style={{fontSize:13,color:"#666",fontFamily:S,marginTop:4}}>{res.note}</div>
          )}
        </div>

        {/* Market vs Poll accuracy panels */}
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:20}}>
          {/* Markets */}
          <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px"}}>
            <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>What Markets Said</div>
            {marketProb != null ? (
              <>
                <div style={{fontSize:28,fontWeight:700,color:winColor,marginBottom:4,fontFamily:"Georgia,'Times New Roman',serif"}}>{marketProb}%</div>
                <div style={{fontSize:13,color:"#555",fontFamily:S,marginBottom:10}}>
                  Pre-election odds on {res.winner}
                  <span style={{color:"#aaa",marginLeft:4}}>
                    {marketProb >= 90 ? "— very confident" : marketProb >= 70 ? "— fairly confident" : marketProb >= 55 ? "— leaning" : "— uncertain"}
                  </span>
                </div>
              </>
            ) : (
              <div style={{fontSize:13,color:"#aaa",fontFamily:S,fontStyle:"italic",marginBottom:10}}>Race called before tracking began — no market history available</div>
            )}
            <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
              {race.pm&&<a href={`https://polymarket.com/event/${race.pm}`} target="_blank" rel="noopener noreferrer" style={{fontSize:12,color:"#555",textDecoration:"none",borderBottom:"1px solid #ccc",fontFamily:S}} onClick={e=>e.stopPropagation()}>Polymarket ↗</a>}
              {race.kalshi&&<a href={race.kalshi_url||`https://kalshi.com/markets/${race.kalshi}`} target="_blank" rel="noopener noreferrer" style={{fontSize:12,color:"#555",textDecoration:"none",borderBottom:"1px solid #ccc",fontFamily:S}} onClick={e=>e.stopPropagation()}>Kalshi ↗</a>}
            </div>
          </div>

          {/* Polls */}
          <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px"}}>
            <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>What Polls Said</div>
            {pollComp != null ? (
              <>
                <div style={{fontSize:12,color:"#888",fontFamily:S,marginBottom:10}}>{pollComp.pollster} ({pollComp.date})</div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:10}}>
                  <div>
                    <div style={{fontSize:11,color:"#aaa",fontFamily:S,marginBottom:2}}>Predicted margin</div>
                    <div style={{fontSize:22,fontWeight:700,fontFamily:"Georgia,'Times New Roman',serif",color:pollComp.correct ? winColor : "#888"}}>
                      {pollComp.predicted > 0 ? `+${pollComp.predicted}` : pollComp.predicted}
                    </div>
                  </div>
                  <div>
                    <div style={{fontSize:11,color:"#aaa",fontFamily:S,marginBottom:2}}>Actual margin</div>
                    <div style={{fontSize:22,fontWeight:700,fontFamily:"Georgia,'Times New Roman',serif",color:winColor}}>+{pollComp.actual}</div>
                  </div>
                </div>
                <div style={{fontSize:13,fontFamily:S,color:pollComp.error <= 3 ? "#16a34a" : pollComp.error <= 7 ? "#d97706" : "#dc2626"}}>
                  Off by {pollComp.error} pt{pollComp.error !== 1 ? "s" : ""}
                  {!pollComp.correct && <span style={{color:"#dc2626"}}> — called it wrong</span>}
                </div>
              </>
            ) : (
              <div style={{fontSize:13,color:"#aaa",fontFamily:S,fontStyle:"italic"}}>No polls available for this race</div>
            )}
          </div>
        </div>

        {/* Market history chart */}
        {data.length > 0 && (
          <div style={{marginBottom:20}}>
            <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".06em",color:"#999",fontFamily:S,marginBottom:6}}>Market odds leading up to the result</div>
            <RaceChart race={race}/>
          </div>
        )}

        {/* Pre-election polls table */}
        {race.polls?.length > 0 && (
          <div style={{fontFamily:S}}>
            <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"#999",marginBottom:8}}>Pre-election polls</div>
            <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
              <thead>
                <tr style={{borderBottom:"1px solid #e0e0e0"}}>
                  {["Pollster","Date","Predicted margin","Actual margin","Error"].map(h=>(
                    <th key={h} style={{padding:"4px 8px",textAlign:h==="Pollster"||h==="Date"?"left":"right",color:"#aaa",fontWeight:600,fontSize:11,fontFamily:S}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {race.polls.map((p, i) => {
                  const actual = res.pct != null && res.runner_up_pct != null ? +(res.pct - res.runner_up_pct).toFixed(1) : null;
                  let wPct, ruPct;
                  if (isPrimary(race)) {
                    const cm = {};
                    if (p.c1 && p.d    != null) cm[p.c1]  = p.d;
                    if (p.c2 && p.r    != null) cm[p.c2]  = p.r;
                    if (p.c3 && p.c3pct!= null) cm[p.c3]  = p.c3pct;
                    wPct  = cm[res.winner];
                    ruPct = cm[res.runner_up];
                  } else {
                    wPct  = res.party === "D" ? p.d : p.r;
                    ruPct = res.party === "D" ? p.r : p.d;
                  }
                  const predicted = wPct != null ? +(wPct - (ruPct || 0)).toFixed(1) : null;
                  const error = predicted != null && actual != null ? +(Math.abs(actual - predicted)).toFixed(1) : null;
                  const errColor = error == null ? "#aaa" : error <= 3 ? "#16a34a" : error <= 7 ? "#d97706" : "#dc2626";
                  return (
                    <tr key={i} style={{borderBottom:"1px solid #f0f0f0"}}>
                      <td style={{padding:"6px 8px"}}>
                        {p.url ? <a href={p.url} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()} style={{color:"#333",textDecoration:"none",borderBottom:"1px solid #ccc"}}>{p.pollster}</a> : <span style={{color:"#333"}}>{p.pollster}</span>}
                      </td>
                      <td style={{padding:"6px 8px",color:"#888"}}>{p.date}</td>
                      <td style={{padding:"6px 8px",textAlign:"right",fontWeight:600,color:predicted != null && predicted > 0 ? winColor : "#888"}}>{predicted != null ? (predicted > 0 ? `+${predicted}` : predicted) : "—"}</td>
                      <td style={{padding:"6px 8px",textAlign:"right",fontWeight:600,color:winColor}}>{actual != null ? `+${actual}` : "—"}</td>
                      <td style={{padding:"6px 8px",textAlign:"right",color:errColor,fontWeight:600}}>{error != null ? `${error} pts` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </td></tr>
  );
}

// ══════════════════════════════════════════════
// Convert a 0–100 Dem win-probability to a partisan margin display.
// e.g. 55 → {label:"D +10", color:DEM}   25 → {label:"R +50", color:REP}   50 → {label:"Even", color:"#555"}
function mktMargin(val) {
  const margin = Math.round(2 * val - 100);
  if (margin === 0) return { label: "Even", color: "#555" };
  if (margin > 0)   return { label: `D +${margin}`, color: DEM };
  return               { label: `R +${Math.abs(margin)}`, color: REP };
}

// MAIN APP
// ══════════════════════════════════════════════
export default function App(){
  const[data,setData]=useState(FALLBACK);
  const[filter,setF]=useState("all");
  const[comp,setC]=useState("all");
  const[sel,setS]=useState(null);
  const[sort,setO]=useState("competitiveness");
  const toggle=useCallback(id=>setS(p=>p===id?null:id),[]);

  // Try to load live JSON (works in production when served alongside the app)
  useEffect(()=>{
    // Try multiple paths: works on GitHub Pages, local dev, and alongside the JSX
    const paths = ["data/dashboard_data.json", "dashboard_data.json", "../data/dashboard_data.json"];
    (async () => {
      for (const path of paths) {
        try {
          const r = await fetch(path);
          if (!r.ok) continue;
          const d = await r.json();
          if (d?.races?.length) {
        // Enrich time series: attach polls + compute rolling averages
        d.races.forEach(r => enrichTimeSeries(r));
        setData(d);
            return; // Found valid data, stop trying other paths
          }
        } catch(e) { continue; }
      }
    })();
  },[]);

  const st = data.stats || {};
  const allRaces = data.races || [];
  const completedRaces = allRaces.filter(r => r.result);
  const activeRaces = allRaces.filter(r => !r.result);

  const races=useMemo(()=>{
    let f=activeRaces.filter(r=>{
      if(filter==="senate")return r.chamber==="senate"&&r.state!=="US"&&!isPrimary(r);
      if(filter==="house")return r.chamber==="house"&&r.state!=="US"&&!isPrimary(r);
      if(filter==="governor")return r.chamber==="governor"&&!isPrimary(r);
      if(filter==="control")return r.state==="US";
      if(filter==="primaries")return isPrimary(r);
      if(filter==="watches")return r.race_to_watch;
      return !isPrimary(r);
    });
    if(filter!=="primaries"){
      if(comp==="tossup")f=f.filter(r=>r.dem_base>=.40&&r.dem_base<=.60);
      if(comp==="lean")f=f.filter(r=>(r.dem_base>.15&&r.dem_base<.40)||(r.dem_base>.60&&r.dem_base<.85));
      if(comp==="safe")f=f.filter(r=>r.dem_base<=.15||r.dem_base>=.85);
    }
    if(filter==="primaries")f.sort((a,b)=>(a.primary_date||"9999-99-99").localeCompare(b.primary_date||"9999-99-99"));
    else if(sort==="competitiveness"){const co={senate:0,governor:1,house:2};f.sort((a,b)=>{const cd=(co[a.chamber]??3)-(co[b.chamber]??3);return cd!==0?cd:Math.abs(a.dem_base-.5)-Math.abs(b.dem_base-.5);});}
    else if(sort==="state")f.sort((a,b)=>(a.state+(a.district||"")).localeCompare(b.state+(b.district||"")));
    else if(sort==="polymarket"){const lv=r=>{const ts=r.time_series||[];for(let i=ts.length-1;i>=0;i--)if(ts[i].polymarket!=null)return ts[i].polymarket;return null;};f.sort((a,b)=>{const av=lv(a),bv=lv(b);if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return -1;return Math.abs(av-50)-Math.abs(bv-50);});}
    else if(sort==="kalshi"){const lv=r=>{const ts=r.time_series||[];for(let i=ts.length-1;i>=0;i--)if(ts[i].kalshi!=null)return ts[i].kalshi;return null;};f.sort((a,b)=>{const av=lv(a),bv=lv(b);if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return -1;return Math.abs(av-50)-Math.abs(bv-50);});}
    else if(sort==="latestpoll"){const ld=r=>(r.polls||[]).map(p=>p.date||"").filter(Boolean).sort().pop()||"0";f.sort((a,b)=>ld(b).localeCompare(ld(a)));}
    return f;},[activeRaces,filter,comp,sort]);

  const pill=(act,fn,ch)=>(<button onClick={fn} style={{padding:"4px 12px",borderRadius:3,fontSize:13,fontWeight:act?600:400,border:act?"1px solid #333":"1px solid #ccc",cursor:"pointer",background:act?"#333":"#fff",color:act?"#fff":"#666",fontFamily:S}}>{ch}</button>);

  const senFav = st.senate_rep_pct != null ? st.senate_rep_pct > 50 : null;
  const houFav = st.house_dem_pct != null ? st.house_dem_pct > 50 : null;

  return(
    <div style={{background:"#fff",minHeight:"100vh",color:"#222",fontFamily:"Georgia,'Times New Roman',serif"}}>
      <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet"/>
      <header style={{borderBottom:"3px double #222",padding:"28px 24px 20px",maxWidth:960,margin:"0 auto"}}>
        <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".12em",color:"#999",fontFamily:S,marginBottom:6}}>2026 Midterm Elections</div>
        <h1 style={{fontSize:30,fontWeight:700,margin:"0 0 6px",lineHeight:1.15}}>Prediction Markets vs. the Polls</h1>
        <p style={{fontSize:15,color:"#555",margin:0,fontFamily:S,lineHeight:1.5}}>Tracking daily odds on Polymarket and Kalshi alongside public polling for every competitive race. Updated {data.updated || "daily"}.</p>
      </header>
      <div style={{maxWidth:960,margin:"0 auto",padding:"20px 24px"}}>
        {/* Top line */}
        <div style={{display:"flex",alignItems:"baseline",gap:0,marginBottom:20,paddingBottom:16,borderBottom:"1px solid #ddd",flexWrap:"wrap"}}>
          <div style={{display:"flex",alignItems:"baseline",gap:8,marginRight:36}}>
            <span style={{fontSize:12,color:"#999",textTransform:"uppercase",letterSpacing:".06em",fontFamily:S}}>Senate</span>
            <span style={{fontSize:32,fontWeight:700,color:senFav==null?"#999":senFav?REP:DEM,letterSpacing:"-.02em"}}>{senFav==null?"—":senFav?st.senate_rep_pct:st.senate_dem_pct}%</span>
            <span style={{fontSize:14,color:senFav==null?"#999":senFav?REP:DEM,fontFamily:S}}>{senFav==null?"":senFav?"Rep.":"Dem."}</span>
          </div>
          <div style={{display:"flex",alignItems:"baseline",gap:8,marginRight:40}}>
            <span style={{fontSize:12,color:"#999",textTransform:"uppercase",letterSpacing:".06em",fontFamily:S}}>House</span>
            <span style={{fontSize:32,fontWeight:700,color:houFav==null?"#999":houFav?DEM:REP,letterSpacing:"-.02em"}}>{houFav==null?"—":houFav?st.house_dem_pct:st.house_rep_pct}%</span>
            <span style={{fontSize:14,color:houFav==null?"#999":houFav?DEM:REP,fontFamily:S}}>{houFav==null?"":houFav?"Dem.":"Rep."}</span>
          </div>
          <div style={{width:1,height:22,background:"#ddd",marginRight:24,alignSelf:"center"}}/>
          <div style={{display:"flex",gap:18,alignItems:"baseline",flexWrap:"wrap",fontFamily:S,fontSize:13,color:"#888"}}>
            <span><strong style={{color:"#555"}}>{st.battleground_senate??'—'}</strong> battleground Senate</span>
            <span><strong style={{color:"#555"}}>{st.house_districts_tracked??'—'}</strong> House districts</span>
            <span><strong style={{color:"#555"}}>{st.polls_tracked??'—'}</strong> polls</span>
          </div>
        </div>
        {/* Filters */}
        <div style={{marginBottom:18,fontFamily:S}}>
          <div style={{display:"flex",gap:6,marginBottom:8,flexWrap:"wrap",alignItems:"center"}}>
            <span style={{fontSize:12,color:"#999",marginRight:2}}>Show:</span>
            {[["senate","Senate"],["house","House"],["governor","Governor"],["control","Control"],["all","All"]].map(([v,l])=><span key={v}>{pill(filter===v,()=>setF(v),l)}</span>)}
            <span style={{color:"#ccc",padding:"0 4px",fontSize:14,userSelect:"none"}}>|</span>
            {pill(filter==="primaries",()=>setF("primaries"),"Primaries")}
            {pill(filter==="watches",()=>setF("watches"),"★ Races to Watch")}
          </div>
          {filter!=="primaries"&&<div style={{display:"flex",gap:6,flexWrap:"wrap",alignItems:"center"}}>
            <span style={{fontSize:12,color:"#999",marginRight:2}}>Rating:</span>
            {[["tossup","Toss-up"],["lean","Lean"],["safe","Safe"],["all","All"]].map(([v,l])=><span key={v}>{pill(comp===v,()=>setC(v),l)}</span>)}
          </div>}
        </div>
        {/* Table */}
        <table style={{width:"100%",borderCollapse:"collapse",fontFamily:S}}>
          <thead><tr style={{borderBottom:"2px solid #222"}}>
            {(filter==="primaries"
              ?[{key:"state",label:"Race"},{key:null,label:"Primary Date"},{key:null,label:"Kalshi Leader"},{key:"latestpoll",label:"Latest Poll"},{key:null,label:"Trend"}]
              :[{key:"state",label:"Race"},{key:"competitiveness",label:"Rating"},{key:"polymarket",label:"Polymarket"},{key:"kalshi",label:"Kalshi"},{key:"latestpoll",label:"Latest Poll"},{key:null,label:"Trend"}]
            ).map(col=>(
              <th key={col.label} onClick={col.key?()=>setO(col.key):undefined} title={col.title||""} style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:sort===col.key?"#222":"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600,cursor:col.key?"pointer":"default",userSelect:"none",whiteSpace:"nowrap"}}>
                {col.label}{sort===col.key&&<span style={{marginLeft:4,fontSize:9}}>{sort==="state"?"A→Z":"↕"}</span>}
              </th>))}
          </tr></thead>
          <tbody>
            {races.map(race=>{const ts=race.time_series||[];const latest=ts[ts.length-1]||{};const r=rat(race.dem_base||0.5);const lp=race.polls?.[0];const open=sel===race.race_id;
              const pmVal = latest.polymarket; const kVal = latest.kalshi;
              return[
                <tr key={race.race_id} onClick={()=>toggle(race.race_id)} style={{borderBottom:open?"none":"1px solid #e8e8e8",cursor:"pointer",background:open?"#fafafa":"transparent",transition:"background .1s"}} onMouseEnter={e=>{if(!open)e.currentTarget.style.background="#fafafa";}} onMouseLeave={e=>{e.currentTarget.style.background=open?"#fafafa":"transparent";}}>
                  <td style={{padding:"10px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:7}}>
                      <span style={{fontSize:9,color:open?"#333":"#ccc",transition:"transform .2s",transform:open?"rotate(90deg)":"rotate(0)"}}>▶</span>
                      <div>
                        <div style={{display:"flex",alignItems:"center",gap:7}}>
                          <span style={{fontSize:14,fontWeight:600,color:"#222"}}>{race.state==="US"?race.description: race.district ? `${race.state}-${race.district}` : race.state}</span>
                          {isPrimary(race)&&(()=>{const pp=primaryParty(race);const bg=pp==="D"?"#dbeafe":pp==="R"?"#fee2e2":"#f3f4f6";const fg=pp==="D"?"#1d4ed8":pp==="R"?"#b91c1c":"#374151";return(<span style={{fontSize:10,fontWeight:700,background:bg,color:fg,padding:"2px 6px",borderRadius:3,letterSpacing:".03em",whiteSpace:"nowrap"}}>{pp||""}  Primary</span>);})()}
                          {race.race_to_watch&&<span style={{fontSize:10,fontWeight:700,background:"#fef9c3",color:"#854d0e",padding:"2px 6px",borderRadius:3,letterSpacing:".03em",whiteSpace:"nowrap"}}>★ Watch</span>}
                        </div>
                        <div style={{fontSize:12,color:"#888",marginTop:1}}>{race.state==="US"?"":race.description}</div>
                      </div>
                    </div>
                  </td>
                  {filter==="primaries"
                    ? <td style={{padding:"10px",whiteSpace:"nowrap"}}>
                        <span style={{fontSize:13,color:"#444",fontFamily:S}}>{formatPrimaryDate(race.primary_date)}</span>
                      </td>
                    : <td style={{padding:"10px"}}>
                        <span style={{fontSize:12,fontWeight:600,color:r.c}}>{r.l}</span>
                      </td>
                  }
                  {filter==="primaries"
                    ? (()=>{const leader=primaryKalshiLeader(race);const pp=primaryParty(race);const c=pp==="D"?PRIMARY_PALETTE.D[0]:pp==="R"?PRIMARY_PALETTE.R[0]:"#555";return(
                        <td style={{padding:"10px"}}>
                          {leader
                            ?<div><div style={{fontSize:13,fontWeight:700,color:c}}>{leader.name}</div><div style={{fontSize:12,color:"#888"}}>{leader.pct}%</div></div>
                            :<span style={{color:"#ddd"}}>—</span>}
                        </td>);})()
                    : <>
                        <td style={{padding:"10px"}}>{pmVal!=null?(()=>{const m=mktMargin(pmVal);return<span style={{fontSize:15,fontWeight:700,color:m.color}}>{m.label}</span>;})():<span style={{color:"#ddd"}}>—</span>}</td>
                        <td style={{padding:"10px"}}>{kVal!=null?(()=>{const m=mktMargin(kVal);return<span style={{fontSize:15,fontWeight:700,color:m.color}}>{m.label}</span>;})():<span style={{color:"#ddd"}}>—</span>}</td>
                      </>
                  }
                  <td style={{padding:"10px"}}>
                    {lp?(isPrimary(race)
                      ?(()=>{
                          const pm=[];
                          if(lp.c1&&lp.d!=null)pm.push({name:lp.c1,pct:lp.d});
                          if(lp.c2&&lp.r!=null)pm.push({name:lp.c2,pct:lp.r});
                          if(lp.c3&&lp.c3pct!=null)pm.push({name:lp.c3,pct:lp.c3pct});
                          pm.sort((a,b)=>b.pct-a.pct);
                          const colors=primaryColors(race);
                          return(<div>
                            {pm.slice(0,2).map((c,i)=><div key={c.name} style={{fontSize:13,fontWeight:i===0?600:500,color:colors[i]}}>{c.name} {c.pct}%</div>)}
                            <div style={{fontSize:11,color:"#aaa"}}>{lp.pollster}, {lp.date}</div>
                          </div>);
                        })()
                      :(<div><div style={{fontSize:13,fontWeight:600,color:spreadColor(lp.d,lp.r,lp.spread)}}>{lp.spread}</div><div style={{fontSize:11,color:"#aaa"}}>{lp.pollster}, {lp.date}</div></div>)
                    ):<span style={{color:"#ddd"}}>—</span>}
                  </td>
                  <td style={{padding:"10px"}}><Spark data={ts} id={race.race_id}/></td>
                </tr>,
                open&&<Detail key={`${race.race_id}-d`} race={race} onClose={()=>setS(null)}/>,
              ];})}
          </tbody>
        </table>

        {/* ── Completed Races ── */}
        {completedRaces.length > 0 && (<div style={{marginTop:36}}>
          <h2 style={{fontSize:18,fontWeight:700,margin:"0 0 4px",fontFamily:"Georgia,'Times New Roman',serif"}}>Completed Races</h2>
          <p style={{fontSize:13,color:"#888",margin:"0 0 14px",fontFamily:S}}>Primaries and elections that have been called. Click to see the full history of market odds and polling.</p>
          <table style={{width:"100%",borderCollapse:"collapse",fontFamily:S}}>
            <thead><tr style={{borderBottom:"2px solid #222"}}>
              {["Race","Winner","Result","Called","Markets / Polls"].map(h=>(
                <th key={h} style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {completedRaces.map(race => {
                const res = race.result;
                const open = sel === race.race_id;
                const winColor = res.party === "D" ? DEM : res.party === "R" ? REP : "#666";
                return [
                  <tr key={race.race_id} onClick={() => toggle(race.race_id)} style={{borderBottom:open?"none":"1px solid #e8e8e8",cursor:"pointer",background:open?"#fafafa":"transparent",transition:"background .1s"}} onMouseEnter={e=>{if(!open)e.currentTarget.style.background="#fafafa";}} onMouseLeave={e=>{e.currentTarget.style.background=open?"#fafafa":"transparent";}}>
                    <td style={{padding:"10px"}}>
                      <div style={{display:"flex",alignItems:"center",gap:7}}>
                        <span style={{fontSize:9,color:open?"#333":"#ccc",transition:"transform .2s",transform:open?"rotate(90deg)":"rotate(0)"}}>▶</span>
                        <div>
                          <div style={{fontSize:14,fontWeight:600,color:"#222"}}>{race.state}</div>
                          <div style={{fontSize:12,color:"#888",marginTop:1}}>{race.description}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{padding:"10px"}}>
                      <div style={{display:"flex",alignItems:"center",gap:6}}>
                        <span style={{fontSize:14,fontWeight:700,color:winColor}}>✓ {res.winner}</span>
                      </div>
                    </td>
                    <td style={{padding:"10px"}}>
                      {res.pct != null ? (
                        <span style={{fontSize:14,fontWeight:600,color:"#222"}}>{res.pct}% – {res.runner_up_pct}%</span>
                      ) : (
                        <span style={{fontSize:13,color:"#888"}}>{res.note || "—"}</span>
                      )}
                    </td>
                    <td style={{padding:"10px"}}><span style={{fontSize:13,color:"#888"}}>{res.date}</span></td>
                    <td style={{padding:"10px"}}>
                      {(()=>{
                        const mp = winnerMarketProb(race);
                        const pv = pollVsResult(race);
                        if (mp == null && pv == null) return <span style={{color:"#ddd"}}>—</span>;
                        return (
                          <div style={{fontFamily:S}}>
                            {mp != null && <div style={{fontSize:13,fontWeight:600,color:winColor}}>{mp}% mkt</div>}
                            {pv != null && <div style={{fontSize:12,color:"#666"}}>{pv.predicted > 0 ? `+${pv.predicted}` : pv.predicted} poll</div>}
                          </div>
                        );
                      })()}
                    </td>
                  </tr>,
                  open && <CompletedDetail key={`${race.race_id}-cd`} race={race} onClose={() => setS(null)} />,
                ];
              })}
            </tbody>
          </table>
        </div>)}

        <div style={{marginTop:28,paddingTop:16,borderTop:"1px solid #ddd",fontSize:12,color:"#999",lineHeight:1.7,fontFamily:S}}>
          <strong style={{color:"#666"}}>About this tracker</strong> — Market odds from Polymarket and Kalshi, recorded four times a day. Polls sourced from Wikipedia. General election charts show the leading candidate's prediction market advantage, with a <span style={{color:POLL_AVG,fontWeight:600}}>muted blue dashed line</span> for the 30-day poll average; vertical markers flag poll release dates. Primary charts show per-candidate poll support (%) as multi-colored lines — blues for Dem primaries, reds/oranges for Rep primaries. Use the <strong>Primaries</strong> filter to see all tracked primaries. Created by <a href="mailto:tom.wrightpiersanti@gmail.com" style={{color:"#999",textDecoration:"underline"}}>Tom Wright-Piersanti</a>, built with Claude Code.
          <div style={{marginTop:6}}><strong style={{color:"#666"}}>★ Races to Watch</strong> denotes a race highlighted as notable on NBC News' primary calendar.</div>
        </div>
      </div>
    </div>);
}
