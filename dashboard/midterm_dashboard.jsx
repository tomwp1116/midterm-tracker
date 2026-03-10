import { useState, useMemo, useCallback, useEffect } from "react";
import { XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, Area, AreaChart, ComposedChart, Line } from "recharts";

const DEM = "#4c72b0";
const REP = "#c44e52";
const S = "'Source Sans 3',Arial,sans-serif";

const isD = s => s && /^(D |Ossoff|Peters|Platner|Mills|Brown|Talarico|Peltola|Generic D|Dem|Craig|Caraveo|Wild|Cartwright|Salinas|Vasquez|Gray)/.test(s);

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
    { race_id:"senate-control-2026", chamber:"senate", state:"US", description:"Senate Control", dem_base:0.35, pm:"which-party-will-win-the-senate-in-2026", kalshi:"controls/senate-winner", rcp:"polls/state-of-the-union/generic-congressional-vote", note:"Rep 66%, Dem 35%." },
    { race_id:"senate-GA-2026", chamber:"senate", state:"GA", description:"Georgia — Ossoff (D-inc) vs. TBD (R)", dem_base:0.52, pm:"georgia-senate-election-winner", kalshi:"senatega/georgia-senate-race/senatega-26", rcp:"polls/senate/general/2026/georgia", note:"R primary May 19.",
      polls:[{date:"Mar 5",pollster:"Emerson",d:48,r:43,spread:"Ossoff +5",matchup:"Ossoff vs. Collins (general)",url:"https://emersoncollegepolling.com/georgia-2026-poll-senator-ossoff-starts-re-election-near-50-and-outpaces-gop-field/"},{date:"Mar 5",pollster:"Emerson",d:47,r:44,spread:"Ossoff +3",matchup:"Ossoff vs. Carter (general)"},{date:"Feb 18",pollster:"Quinnipiac",d:50,r:42,spread:"Ossoff +8",matchup:"Ossoff vs. Collins (general)"}] },
    { race_id:"senate-NC-2026", chamber:"senate", state:"NC", description:"North Carolina — Tillis (R-inc) vs. TBD (D)", dem_base:0.48, pm:"north-carolina-senate-election-winner", kalshi:"senatenc/north-carolina-senate-race/senatenc-26", rcp:"polls/senate/general/2026/north-carolina",
      polls:[{date:"Mar 2",pollster:"SurveyUSA",d:46,r:45,spread:"D +1",matchup:"Generic D vs. Tillis"},{date:"Feb 25",pollster:"PPP",d:44,r:47,spread:"Tillis +3",matchup:"Generic D vs. Tillis"}] },
    { race_id:"senate-MI-2026", chamber:"senate", state:"MI", description:"Michigan — Open (Peters D-retiring)", dem_base:0.77, pm:"michigan-senate-election-winner", kalshi:"senatemi/michigan-senate-race/senatemi-26", rcp:"polls/senate/general/2026/michigan",
      polls:[{date:"Feb 28",pollster:"Mitchell",d:51,r:40,spread:"Peters +11",matchup:"Peters vs. generic R"}] },
    { race_id:"senate-ME-2026", chamber:"senate", state:"ME", description:"Maine — Collins (R-inc) vs. TBD (D)", dem_base:0.58, pm:"maine-senate-election-winner", kalshi:"senateme/maine-senate-race/senateme-26", rcp:"polls/senate/general/2026/maine", note:"D primary June 9.",
      polls:[{date:"Mar 9",pollster:"Quantus",d:49,r:42,spread:"Platner +7",matchup:"Platner (D) vs. Collins (R)",url:"https://quantusinsights.org/f/maine-senate-2026-collins-faces-uncertain-path-to-re-election"},{date:"Mar 9",pollster:"Quantus",d:43,r:45,spread:"Collins +2",matchup:"Mills (D) vs. Collins (R)"},{date:"Mar 9",pollster:"Quantus",d:43,r:38,spread:"Platner +5",matchup:"D primary — Platner vs. Mills vs. Costello LaFlamme"}] },
    { race_id:"senate-AK-2026", chamber:"senate", state:"AK", description:"Alaska — Sullivan (R) vs. Peltola? (D)", dem_base:0.48, pm:"alaska-senate-election-winner", kalshi:"senateak/alaska-senate-race/senateak-26", note:"Ranked-choice. Sullivan 49%, Peltola 48%." },
    { race_id:"senate-NH-2026", chamber:"senate", state:"NH", description:"New Hampshire — Open (Shaheen D-retiring)", dem_base:0.57, kalshi:"senatenh/new-hampshire-senate-race/senatenh-26", rcp:"polls/senate/general/2026/new-hampshire",
      polls:[{date:"Feb 22",pollster:"UNH",d:48,r:44,spread:"D +4",matchup:"Generic D vs. Sununu"}] },
    { race_id:"senate-OH-2026", chamber:"senate", state:"OH", description:"Ohio — Brown (D) vs. Husted (R)", dem_base:0.45, kalshi:"senateoh/ohio-senate-race/senateoh-26", rcp:"polls/senate/general/2026/ohio", note:"Special election.",
      polls:[{date:"Feb 15",pollster:"Emerson",d:42,r:48,spread:"R +6",matchup:"Brown vs. Husted"}] },
    { race_id:"senate-TX-2026", chamber:"senate", state:"TX", description:"Texas — Cornyn/Paxton (R) vs. Talarico (D)", dem_base:0.28, pm:"texas-senate-election-winner", kalshi:"senatetx/texas-senate-race/senatetx-26", rcp:"polls/senate/general/2026/texas",
      polls:[{date:"Mar 1",pollster:"Emerson",d:38,r:52,spread:"Cornyn +14",matchup:"Generic D vs. Cornyn (pre-primary)"}] },
    { race_id:"primary-TX-senate-D-2026", chamber:"senate", state:"TX", description:"Texas Senate — Democratic Primary", dem_base:0.62,
      pm:"texas-senate-democratic-primary", kalshi:"senatetx-d-26", note:"Resolved March 3. $4.8M Kalshi volume.",
      result:{ winner:"James Talarico", party:"D", date:"Mar 3", pct:58.2, runner_up:"Jasmine Crockett", runner_up_pct:41.8 },
      polls:[{date:"Feb 28",pollster:"UT-Tyler",d:52,r:41,spread:"Talarico +11",matchup:"Talarico vs. Crockett (D primary)"}] },
    { race_id:"primary-TX-senate-R-2026", chamber:"senate", state:"TX", description:"Texas Senate — Republican Primary", dem_base:0.45,
      kalshi:"senatetx-r-26", note:"Headed to runoff. No candidate reached 50%.",
      result:{ winner:"Runoff: Cornyn vs. Paxton", party:"R", date:"Mar 3", pct:null, runner_up:null, runner_up_pct:null, note:"Cornyn 38%, Paxton 32%. Runoff TBD." } },
    { race_id:"senate-IA-2026", chamber:"senate", state:"IA", description:"Iowa — Grassley (R-retiring)", dem_base:0.35, kalshi:"senateia/iowa-senate-race/senateia-26" },
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

  // Merge polls into time series
  allRaces.forEach(r => {
    if (!r.polls || !r.time_series) return;
    const MO = {Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12};
    const lookup = {};
    r.polls.forEach(p => { const [m,d] = p.date.trim().split(/\s+/); const k = MO[m] ? `${MO[m]}/${parseInt(d)}` : null; if (k) (lookup[k] ||= []).push(p); });
    r.time_series.forEach(pt => {
      const mp = lookup[pt.date];
      if (mp) { pt.pollDem = mp[0].d; pt.pollRep = mp[0].r; pt.pollster = mp[0].pollster; pt.pollSpread = mp[0].spread; pt.pollMatchup = mp[0].matchup; if (mp.length > 1) pt.pollExtra = mp.slice(1); }
    });
  });

  const nSen = allRaces.filter(r => r.chamber === "senate" && r.state !== "US").length;
  const nHouse = allRaces.filter(r => r.chamber === "house" && r.state !== "US").length;
  return {
    updated: "2026-03-10",
    stats: { senate_rep_pct: 66, house_dem_pct: 78, battleground_senate: 4, battleground_house: nHouse, house_districts_tracked: nHouse, seats_up: 35, polls_tracked: allRaces.reduce((n, r) => n + (r.polls?.length || 0), 0) },
    races: allRaces,
  };
}

// ── Chart components ──
function Spark({data,id}){return(<ResponsiveContainer width={86} height={24}><AreaChart data={data} margin={{top:2,right:0,bottom:2,left:0}}><Area type="monotone" dataKey={data.some(d=>d.polymarket)?"polymarket":"kalshi"} stroke="#888" fill="none" strokeWidth={1.2} dot={false}/><ReferenceLine y={50} stroke="#ddd" strokeWidth={.5}/></AreaChart></ResponsiveContainer>);}

function DDot({cx,cy,payload}){if(!payload?.pollDem||!cx||!cy)return null;return(<g><line x1={cx} y1={8} x2={cx} y2={212} stroke={DEM} strokeWidth={.7} strokeDasharray="3 3" opacity={.25}/><circle cx={cx} cy={cy} r={5} fill={DEM} stroke="#fff" strokeWidth={1.5}/><text x={cx} y={cy-10} textAnchor="middle" fill={DEM} fontSize={9} fontWeight={600}>{payload.pollDem}</text></g>);}
function RDot({cx,cy,payload}){if(!payload?.pollRep||!cx||!cy)return null;return(<g><circle cx={cx} cy={cy} r={4} fill={REP} stroke="#fff" strokeWidth={1.5}/><text x={cx} y={cy+14} textAnchor="middle" fill={REP} fontSize={9} fontWeight={600}>{payload.pollRep}</text></g>);}

function Tip({active,payload}){if(!active||!payload?.length)return null;const pt=payload[0]?.payload;if(!pt)return null;const hp=pt.pollDem!=null;
  return(<div style={{background:"#fff",border:"1px solid #ddd",padding:"10px 14px",fontSize:13,color:"#222",boxShadow:"0 2px 8px rgba(0,0,0,.08)",maxWidth:280,lineHeight:1.5,fontFamily:S}}>
    <div style={{fontWeight:600,marginBottom:4,color:"#999",fontSize:12}}>{pt.date}</div>
    {pt.polymarket!=null&&<div style={{display:"flex",justifyContent:"space-between"}}><span>Polymarket</span><strong>{pt.polymarket}%</strong></div>}
    {pt.kalshi!=null&&<div style={{display:"flex",justifyContent:"space-between"}}><span>Kalshi</span><strong>{pt.kalshi}%</strong></div>}
    {hp&&(<div style={{borderTop:"1px solid #eee",marginTop:8,paddingTop:8}}>
      <div style={{fontWeight:700,fontSize:11,textTransform:"uppercase",letterSpacing:".04em",color:"#999",marginBottom:4}}>Poll released</div>
      <div style={{fontWeight:500}}>{pt.pollster}</div>
      {pt.pollMatchup&&<div style={{fontSize:12,color:"#888"}}>{pt.pollMatchup}</div>}
      <div style={{display:"flex",gap:14,marginTop:3}}><span style={{color:DEM,fontWeight:600}}>Dem {pt.pollDem}%</span><span style={{color:REP,fontWeight:600}}>Rep {pt.pollRep}%</span><span style={{marginLeft:"auto",fontWeight:700,color:isD(pt.pollSpread)?DEM:REP}}>{pt.pollSpread}</span></div>
      {pt.pollExtra?.map((pe,i)=>(<div key={i} style={{marginTop:6,paddingTop:6,borderTop:"1px dashed #e5e5e5"}}><div style={{fontWeight:500}}>{pe.pollster}</div>{pe.matchup&&<div style={{fontSize:12,color:"#888"}}>{pe.matchup}</div>}<div style={{display:"flex",gap:14,marginTop:2}}><span style={{color:DEM}}>Dem {pe.d}%</span><span style={{color:REP}}>Rep {pe.r}%</span></div></div>))}
    </div>)}</div>);}

function Chart({data}){const vs=data.flatMap(d=>[d.polymarket,d.kalshi,d.pollDem,d.pollRep].filter(v=>v!=null));if(!vs.length)return null;const lo=Math.min(...vs),hi=Math.max(...vs);const yMin=Math.max(0,Math.floor((lo-8)/5)*5),yMax=Math.min(100,Math.ceil((hi+8)/5)*5);
  const hasPM=data.some(d=>d.polymarket!=null),hasK=data.some(d=>d.kalshi!=null);
  // Custom label component for the 50% line
  const show50 = yMin < 50 && yMax > 50;
  return(<ResponsiveContainer width="100%" height={230}><ComposedChart data={data} margin={{top:20,right:12,bottom:8,left:0}}>
    <defs>
      <linearGradient id="demZone" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={DEM} stopOpacity={0.06}/><stop offset="100%" stopColor={DEM} stopOpacity={0.02}/></linearGradient>
      <linearGradient id="repZone" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={REP} stopOpacity={0.02}/><stop offset="100%" stopColor={REP} stopOpacity={0.06}/></linearGradient>
    </defs>
    <XAxis dataKey="date" tick={{fontSize:11,fill:"#999"}} tickLine={false} axisLine={{stroke:"#ddd"}} interval={4}/>
    <YAxis domain={[yMin,yMax]} tick={{fontSize:11,fill:"#999"}} tickLine={false} axisLine={false} tickFormatter={v=>`${v}%`} width={34}/>
    <Tooltip content={<Tip/>}/>
    {/* Tinted zones above and below 50% */}
    {show50&&<><ReferenceArea y1={50} y2={yMax} fill="url(#demZone)" /><ReferenceArea y1={yMin} y2={50} fill="url(#repZone)" /></>}
    {/* 50% divider with party labels */}
    {show50&&<ReferenceLine y={50} stroke="#ccc" strokeDasharray="4 4">
      <label value="" />
    </ReferenceLine>}
    {/* Zone labels rendered via customized ReferenceLine labels */}
    {show50&&<ReferenceLine y={yMax - 1} stroke="none" label={{value:"← Dem. favored",position:"insideTopLeft",fill:DEM,fontSize:11,fontWeight:600,fontFamily:S,offset:4}}/>}
    {show50&&<ReferenceLine y={yMin + 1} stroke="none" label={{value:"← Rep. favored",position:"insideBottomLeft",fill:REP,fontSize:11,fontWeight:600,fontFamily:S,offset:4}}/>}
    {hasPM&&<Line type="monotone" dataKey="polymarket" stroke="#222" strokeWidth={2} dot={false}/>}
    {hasK&&<Line type="monotone" dataKey="kalshi" stroke={hasPM?"#aaa":"#222"} strokeWidth={hasPM?1.5:2} dot={false} strokeDasharray={hasPM?"5 3":"0"}/>}
    <Line dataKey="pollDem" stroke="none" connectNulls={false} isAnimationActive={false} dot={<DDot/>} activeDot={false}/>
    <Line dataKey="pollRep" stroke="none" connectNulls={false} isAnimationActive={false} dot={<RDot/>} activeDot={false}/>
  </ComposedChart></ResponsiveContainer>);}

function rat(d){if(d>=.85)return{l:"Safe D.",c:DEM};if(d>=.60)return{l:"Lean D.",c:DEM};if(d>=.40)return{l:"Toss-up",c:"#7c3aed"};if(d>=.15)return{l:"Lean R.",c:REP};return{l:"Safe R.",c:REP};}

// ── Detail panel ──
function Detail({race,onClose}){const data=race.time_series||[];return(
  <tr><td colSpan={6} style={{padding:0,borderBottom:"1px solid #ddd"}}>
    <div style={{borderTop:"2px solid #222",padding:"20px 16px 24px",background:"#fafafa",animation:"so .25s ease"}}>
      <style>{`@keyframes so{from{max-height:0;opacity:0}to{max-height:900px;opacity:1}}`}</style>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:14}}>
        <div>
          <h3 style={{fontSize:20,fontWeight:700,margin:0,fontFamily:"Georgia,'Times New Roman',serif"}}>{race.description}</h3>
          {race.note&&<p style={{fontSize:13,color:"#666",margin:"4px 0 0",fontFamily:S}}>{race.note}</p>}
        </div>
        <button onClick={e=>{e.stopPropagation();onClose();}} style={{background:"none",border:"1px solid #ccc",color:"#666",borderRadius:3,padding:"4px 12px",cursor:"pointer",fontSize:12,fontFamily:S}}>Close</button>
      </div>
      {data.length>0&&<Chart data={data}/>}
      <div style={{display:"flex",gap:18,marginTop:6,marginBottom:16,fontSize:12,color:"#888",flexWrap:"wrap",fontFamily:S}}>
        {race.pm&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,height:2,background:"#222",display:"inline-block"}}/>Polymarket</span>}
        <span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,borderTop:`2px ${race.pm?"dashed":"solid"} ${race.pm?"#aaa":"#222"}`,display:"inline-block"}}/>Kalshi</span>
        <span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:9,height:9,borderRadius:"50%",background:DEM,display:"inline-block"}}/>Poll (Dem.)</span>
        <span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:8,height:8,borderRadius:"50%",background:REP,display:"inline-block"}}/>Poll (Rep.)</span>
      </div>
      {/* Links */}
      <div style={{display:"flex",gap:16,marginBottom:20,fontSize:13,fontFamily:S,flexWrap:"wrap"}}>
        {race.pm&&<a href={`https://polymarket.com/event/${race.pm}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Polymarket ↗</a>}
        {race.kalshi&&<a href={`https://kalshi.com/markets/${race.kalshi}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Kalshi ↗</a>}
        {race.rcp&&<a href={`https://www.realclearpolling.com/${race.rcp}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>RealClearPolling ↗</a>}
      </div>
      {/* Polls */}
      {race.polls?.length>0&&(<div style={{fontFamily:S}}>
        <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"#999",marginBottom:8}}>Polls</div>
        {race.polls.map((p,i)=>(<div key={i} style={{padding:"8px 0",borderTop:i?"1px solid #e8e8e8":"none"}}>
          <div style={{display:"flex",alignItems:"baseline",gap:10,flexWrap:"wrap"}}>
            <span style={{fontSize:13,color:"#999",width:46}}>{p.date}</span>
            {p.url?<a href={p.url} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()} style={{fontSize:13,fontWeight:600,color:"#333",textDecoration:"none",borderBottom:"1px solid #ccc"}}>{p.pollster}</a>:<span style={{fontSize:13,fontWeight:600,color:"#333"}}>{p.pollster}</span>}
            <span style={{fontSize:14,fontWeight:700,color:DEM}}>Dem {p.d}%</span>
            <span style={{color:"#ccc"}}>–</span>
            <span style={{fontSize:14,fontWeight:700,color:REP}}>Rep {p.r}%</span>
            <span style={{fontSize:13,fontWeight:700,marginLeft:"auto",color:isD(p.spread)?DEM:REP}}>{p.spread}</span>
          </div>
          {p.matchup&&<div style={{fontSize:12,color:"#999",marginTop:2,paddingLeft:56}}>{p.matchup}</div>}
        </div>))}
      </div>)}
      {!race.polls?.length&&<p style={{fontSize:13,color:"#aaa",fontStyle:"italic",fontFamily:S}}>No polls have been released for this race yet.</p>}
    </div>
  </td></tr>);}

// ── Completed race detail with winner banner ──
function CompletedDetail({race, onClose}) {
  const data = race.time_series || [];
  const res = race.result;
  const winColor = res.party === "D" ? DEM : res.party === "R" ? REP : "#666";
  const loseColor = res.party === "D" ? REP : res.party === "R" ? DEM : "#aaa";
  const totalPct = (res.pct || 0) + (res.runner_up_pct || 0);
  const winWidth = totalPct > 0 ? (res.pct / totalPct * 100) : 50;

  return (
    <tr><td colSpan={4} style={{padding:0,borderBottom:"1px solid #ddd"}}>
      <div style={{borderTop:`3px solid ${winColor}`,padding:"20px 16px 24px",background:"#fafafa",animation:"so .25s ease"}}>
        <style>{`@keyframes so{from{max-height:0;opacity:0}to{max-height:900px;opacity:1}}`}</style>

        <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:16}}>
          <div>
            <h3 style={{fontSize:20,fontWeight:700,margin:0,fontFamily:"Georgia,'Times New Roman',serif"}}>{race.description}</h3>
            {race.note&&<p style={{fontSize:13,color:"#666",margin:"4px 0 0",fontFamily:S}}>{race.note}</p>}
          </div>
          <button onClick={e=>{e.stopPropagation();onClose();}} style={{background:"none",border:"1px solid #ccc",color:"#666",borderRadius:3,padding:"4px 12px",cursor:"pointer",fontSize:12,fontFamily:S}}>Close</button>
        </div>

        {/* Winner banner */}
        <div style={{background:"#fff",border:"1px solid #e5e5e5",borderRadius:4,padding:"16px 20px",marginBottom:20}}>
          <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".08em",color:"#999",fontFamily:S,marginBottom:8}}>Result — Called {res.date}</div>
          <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:res.pct ? 12 : 0}}>
            <span style={{fontSize:22,fontWeight:700,color:winColor,fontFamily:"Georgia,'Times New Roman',serif"}}>✓ {res.winner}</span>
            {res.pct&&<span style={{fontSize:18,fontWeight:700,color:winColor}}>{res.pct}%</span>}
          </div>
          {res.runner_up && res.runner_up_pct && (
            <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:12}}>
              <span style={{fontSize:16,color:"#888",fontFamily:S}}>{res.runner_up}</span>
              <span style={{fontSize:16,color:"#888"}}>{res.runner_up_pct}%</span>
            </div>
          )}
          {/* Result bar */}
          {res.pct && res.runner_up_pct && (
            <div style={{display:"flex",height:8,borderRadius:4,overflow:"hidden",background:"#eee"}}>
              <div style={{width:`${winWidth}%`,background:winColor,borderRadius:"4px 0 0 4px",transition:"width .5s"}} />
              <div style={{flex:1,background:loseColor,opacity:0.4,borderRadius:"0 4px 4px 0"}} />
            </div>
          )}
          {res.note && !res.pct && (
            <div style={{fontSize:13,color:"#666",fontFamily:S,marginTop:4}}>{res.note}</div>
          )}
        </div>

        {/* Historical chart */}
        <div style={{fontSize:11,textTransform:"uppercase",letterSpacing:".06em",color:"#999",fontFamily:S,marginBottom:6}}>Market odds leading up to the result</div>
        {data.length > 0 && <Chart data={data} />}
        <div style={{display:"flex",gap:18,marginTop:6,marginBottom:16,fontSize:12,color:"#888",flexWrap:"wrap",fontFamily:S}}>
          {race.pm&&<span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,height:2,background:"#222",display:"inline-block"}}/>Polymarket</span>}
          <span style={{display:"flex",alignItems:"center",gap:5}}><span style={{width:16,borderTop:`2px ${race.pm?"dashed":"solid"} ${race.pm?"#aaa":"#222"}`,display:"inline-block"}}/>Kalshi</span>
        </div>

        {/* Links */}
        <div style={{display:"flex",gap:16,marginBottom:16,fontSize:13,fontFamily:S,flexWrap:"wrap"}}>
          {race.pm&&<a href={`https://polymarket.com/event/${race.pm}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Polymarket ↗</a>}
          {race.kalshi&&<a href={`https://kalshi.com/markets/${race.kalshi}`} target="_blank" rel="noopener noreferrer" style={{color:"#222",textDecoration:"none",borderBottom:"1px solid #ccc"}} onClick={e=>e.stopPropagation()}>Kalshi ↗</a>}
        </div>

        {/* Poll history */}
        {race.polls?.length>0&&(<div style={{fontFamily:S}}>
          <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"#999",marginBottom:8}}>Pre-election polls</div>
          {race.polls.map((p,i)=>(<div key={i} style={{padding:"8px 0",borderTop:i?"1px solid #e8e8e8":"none"}}>
            <div style={{display:"flex",alignItems:"baseline",gap:10,flexWrap:"wrap"}}>
              <span style={{fontSize:13,color:"#999",width:46}}>{p.date}</span>
              {p.url?<a href={p.url} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()} style={{fontSize:13,fontWeight:600,color:"#333",textDecoration:"none",borderBottom:"1px solid #ccc"}}>{p.pollster}</a>:<span style={{fontSize:13,fontWeight:600,color:"#333"}}>{p.pollster}</span>}
              <span style={{fontSize:14,fontWeight:700,color:DEM}}>Dem {p.d}%</span>
              <span style={{color:"#ccc"}}>–</span>
              <span style={{fontSize:14,fontWeight:700,color:REP}}>Rep {p.r}%</span>
              <span style={{fontSize:13,fontWeight:700,marginLeft:"auto",color:isD(p.spread)?DEM:REP}}>{p.spread}</span>
            </div>
            {p.matchup&&<div style={{fontSize:12,color:"#999",marginTop:2,paddingLeft:56}}>{p.matchup}</div>}
          </div>))}
        </div>)}
      </div>
    </td></tr>
  );
}

// ══════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════
export default function App(){
  const[data,setData]=useState(FALLBACK);
  const[filter,setF]=useState("senate");
  const[comp,setC]=useState("tossup");
  const[sel,setS]=useState(null);
  const[sort,setO]=useState("competitiveness");
  const toggle=useCallback(id=>setS(p=>p===id?null:id),[]);

  // Try to load live JSON (works in production when served alongside the app)
  useEffect(()=>{
    fetch("dashboard_data.json").then(r=>r.ok?r.json():null).then(d=>{
      if(d?.races?.length){
        // Merge polls into time_series for chart rendering
        d.races.forEach(r=>{
          if(!r.polls||!r.time_series)return;
          const MO={Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12};
          const lk={};
          r.polls.forEach(p=>{const pts=p.date.trim().split(/\s+/);const k=MO[pts[0]]?`${MO[pts[0]]}/${parseInt(pts[1])}`:null;if(k)(lk[k]||=[]).push(p);});
          r.time_series.forEach(pt=>{const mp=lk[pt.date];if(mp){pt.pollDem=mp[0].d;pt.pollRep=mp[0].r;pt.pollster=mp[0].pollster;pt.pollSpread=mp[0].spread;pt.pollMatchup=mp[0].matchup;if(mp.length>1)pt.pollExtra=mp.slice(1);}});
        });
        setData(d);
      }
    }).catch(()=>{});
  },[]);

  const st = data.stats || {};
  const allRaces = data.races || [];
  const completedRaces = allRaces.filter(r => r.result);
  const activeRaces = allRaces.filter(r => !r.result);

  const races=useMemo(()=>{
    let f=activeRaces.filter(r=>{
      if(filter==="senate")return r.chamber==="senate"&&r.state!=="US";
      if(filter==="house")return r.chamber==="house"&&r.state!=="US";
      if(filter==="governor")return r.chamber==="governor";
      if(filter==="control")return r.state==="US";
      return true;
    });
    if(comp==="tossup")f=f.filter(r=>r.dem_base>=.40&&r.dem_base<=.60);
    if(comp==="lean")f=f.filter(r=>(r.dem_base>.15&&r.dem_base<.40)||(r.dem_base>.60&&r.dem_base<.85));
    if(comp==="safe")f=f.filter(r=>r.dem_base<=.15||r.dem_base>=.85);
    if(sort==="competitiveness")f.sort((a,b)=>Math.abs(a.dem_base-.5)-Math.abs(b.dem_base-.5));
    else if(sort==="state")f.sort((a,b)=>(a.state+(a.district||"")).localeCompare(b.state+(b.district||"")));
    else if(sort==="polymarket"||sort==="kalshi")f.sort((a,b)=>(b.dem_base||0)-(a.dem_base||0));
    return f;},[activeRaces,filter,comp,sort]);

  const pill=(act,fn,ch)=>(<button onClick={fn} style={{padding:"4px 12px",borderRadius:3,fontSize:13,fontWeight:act?600:400,border:act?"1px solid #333":"1px solid #ccc",cursor:"pointer",background:act?"#333":"#fff",color:act?"#fff":"#666",fontFamily:S}}>{ch}</button>);

  const senFav = (st.senate_rep_pct||66) > 50;
  const houFav = (st.house_dem_pct||78) > 50;

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
            <span style={{fontSize:32,fontWeight:700,color:senFav?REP:DEM,letterSpacing:"-.02em"}}>{senFav?(st.senate_rep_pct||66):(st.senate_dem_pct||35)}%</span>
            <span style={{fontSize:14,color:senFav?REP:DEM,fontFamily:S}}>{senFav?"Rep.":"Dem."}</span>
          </div>
          <div style={{display:"flex",alignItems:"baseline",gap:8,marginRight:40}}>
            <span style={{fontSize:12,color:"#999",textTransform:"uppercase",letterSpacing:".06em",fontFamily:S}}>House</span>
            <span style={{fontSize:32,fontWeight:700,color:houFav?DEM:REP,letterSpacing:"-.02em"}}>{houFav?(st.house_dem_pct||78):(st.house_rep_pct||23)}%</span>
            <span style={{fontSize:14,color:houFav?DEM:REP,fontFamily:S}}>{houFav?"Dem.":"Rep."}</span>
          </div>
          <div style={{width:1,height:22,background:"#ddd",marginRight:24,alignSelf:"center"}}/>
          <div style={{display:"flex",gap:18,alignItems:"baseline",flexWrap:"wrap",fontFamily:S,fontSize:13,color:"#888"}}>
            <span><strong style={{color:"#555"}}>{st.battleground_senate||4}</strong> battleground Senate</span>
            <span><strong style={{color:"#555"}}>{st.house_districts_tracked||34}</strong> House districts</span>
            <span><strong style={{color:"#555"}}>{st.polls_tracked||16}</strong> polls</span>
          </div>
        </div>
        {/* Filters */}
        <div style={{marginBottom:18,fontFamily:S}}>
          <div style={{display:"flex",gap:6,marginBottom:8,flexWrap:"wrap",alignItems:"center"}}>
            <span style={{fontSize:12,color:"#999",marginRight:2}}>Show:</span>
            {[["senate","Senate"],["house","House"],["governor","Governor"],["control","Control"],["all","All"]].map(([v,l])=><span key={v}>{pill(filter===v,()=>setF(v),l)}</span>)}
          </div>
          <div style={{display:"flex",gap:6,flexWrap:"wrap",alignItems:"center"}}>
            <span style={{fontSize:12,color:"#999",marginRight:2}}>Rating:</span>
            {[["tossup","Toss-up"],["lean","Lean"],["safe","Safe"],["all","All"]].map(([v,l])=><span key={v}>{pill(comp===v,()=>setC(v),l)}</span>)}
          </div>
        </div>
        {/* Table */}
        <table style={{width:"100%",borderCollapse:"collapse",fontFamily:S}}>
          <thead><tr style={{borderBottom:"2px solid #222"}}>
            {[{key:"state",label:"Race"},{key:"competitiveness",label:"Rating"},{key:"polymarket",label:"Polymarket"},{key:"kalshi",label:"Kalshi"},{key:null,label:"Latest Poll"},{key:null,label:"Trend"}].map(col=>(
              <th key={col.label} onClick={col.key?()=>setO(col.key):undefined} style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:sort===col.key?"#222":"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600,cursor:col.key?"pointer":"default",userSelect:"none"}}>
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
                        <div style={{fontSize:14,fontWeight:600,color:"#222"}}>{race.state==="US"?race.description: race.district ? `${race.state}-${race.district}` : race.state}</div>
                        <div style={{fontSize:12,color:"#888",marginTop:1}}>{race.state==="US"?"":race.description}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{padding:"10px"}}><span style={{fontSize:12,fontWeight:600,color:r.c}}>{r.l}</span></td>
                  <td style={{padding:"10px"}}>{pmVal!=null?<span style={{fontSize:15,fontWeight:700,color:pmVal>=50?DEM:REP}}>{pmVal}%</span>:<span style={{color:"#ddd"}}>—</span>}</td>
                  <td style={{padding:"10px"}}>{kVal!=null?<span style={{fontSize:15,fontWeight:700,color:kVal>=50?DEM:REP}}>{kVal}%</span>:<span style={{color:"#ddd"}}>—</span>}</td>
                  <td style={{padding:"10px"}}>{lp?(<div><div style={{fontSize:13,fontWeight:600,color:isD(lp.spread)?DEM:REP}}>{lp.spread}</div><div style={{fontSize:11,color:"#aaa"}}>{lp.pollster}, {lp.date}</div></div>):<span style={{color:"#ddd"}}>—</span>}</td>
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
              <th style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600}}>Race</th>
              <th style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600}}>Winner</th>
              <th style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600}}>Result</th>
              <th style={{padding:"8px 10px",textAlign:"left",fontSize:11,color:"#999",textTransform:"uppercase",letterSpacing:".05em",fontWeight:600}}>Called</th>
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
                  </tr>,
                  open && <CompletedDetail key={`${race.race_id}-cd`} race={race} onClose={() => setS(null)} />,
                ];
              })}
            </tbody>
          </table>
        </div>)}

        <div style={{marginTop:28,paddingTop:16,borderTop:"1px solid #ddd",fontSize:12,color:"#999",lineHeight:1.7,fontFamily:S}}>
          <strong style={{color:"#666"}}>About this tracker</strong> — Market odds from Polymarket and Kalshi, recorded daily. Kalshi covers all 35 Senate seats and {st.house_districts_tracked||34} competitive House districts; Polymarket covers major races. Polls from RealClearPolling. <span style={{color:DEM,fontWeight:600}}>Blue dots</span> = Dem poll result, <span style={{color:REP,fontWeight:600}}>red dots</span> = Rep result. Solid line = Polymarket, dashed = Kalshi. House districts show Kalshi odds only (Polymarket tracks House control, not individual seats). Data loads from <code style={{background:"#f5f5f5",padding:"1px 4px",borderRadius:2}}>dashboard_data.json</code>, exported daily by the snapshot script.
        </div>
      </div>
    </div>);
}
