// Runs the Stage 3 simulation headless (no browser) using the HTML file's own JavaScript.
// Python calls this through simtools/bridge.py. Input: one JSON object on stdin. Output: one JSON object on stdout.
//
// How it works
//  1. Read the HTML and pull out its <script> block (the simulator).
//  2. Optionally patch a few hard-coded constants (IDM a, b, s0, car length, time step, detector positions).
//  3. Replace the browser (document, canvas, window) with do-nothing stubs, so only the physics runs.
//  4. Replace Math.random with a seeded generator, so runs are reproducible.
//  5. Step the model for the requested time, checking for overlapping cars every step,
//     and return detector records, breakdown events, wave speeds and run totals.
'use strict';
const fs = require('fs');

function readStdin() { return fs.readFileSync(0, 'utf8'); }
const cfg = JSON.parse(readStdin() || '{}');
const htmlPath = cfg.html;
const duration = cfg.duration_s ?? 3600;
const seed = cfg.seed ?? 1;

// ---------- seeded random numbers (mulberry32) ----------
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
Math.random = mulberry32(seed * 2654435761 >>> 0);

// ---------- pull the simulator out of the HTML ----------
const html = fs.readFileSync(htmlPath, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (!scripts.length) throw new Error('No <script> block found in ' + htmlPath);
let src = scripts[scripts.length - 1];

const patched = [];
function patch(re, repl, label, required = true) {
  const before = src; src = src.replace(re, repl);
  if (src === before) { if (required) throw new Error('Patch did not apply: ' + label + ' (has the HTML changed?)'); }
  else patched.push(label);
}

// constants the sliders cannot change (code units: ft, s, ft/s²)
const C = cfg.consts || {};
if (C.IA != null || C.IB != null || C.S0 != null)
  patch(/const IA=([\d.]+),IB=([\d.]+),S0=([\d.]+);/, (m, a, b, s) => `const IA=${C.IA ?? a},IB=${C.IB ?? b},S0=${C.S0 ?? s};`, 'IA/IB/S0');
if (C.CL != null) patch(/CL=15,/, `CL=${C.CL},`, 'CL');
if (C.POL != null || C.ATHR != null)
  patch(/const POL=([\d.]+),ATHR=([\d.]+);/, (m, p, t) => `const POL=${C.POL ?? p},ATHR=${C.ATHR ?? t};`, 'POL/ATHR');
if (C.XA_m != null || C.XD_m != null)
  patch(/const XA=(\d+)\*M2F,XD=(\d+)\*M2F;/, (m, a, d) => `const XA=${C.XA_m ?? a}*M2F,XD=${C.XD_m ?? d}*M2F;`, 'XA/XD');
if (C.DT != null) {
  // The code counts steps for its 1 s, 2 s, 30 s and 60 s timers, which assumes DT = 0.1 s.
  // Rewrite those step counts as times so a different DT keeps the same intervals.
  patch(/DT=0\.1,/, `DT=${C.DT},`, 'DT');
  patch(/stepN%300===0/g, 'stepN%Math.round(30/DT)===0', 'DT: 30 s detector interval');
  patch(/stepN%600===0/g, 'stepN%Math.round(60/DT)===0', 'DT: 60 s timers');
  patch(/stepN%20===0/g, 'stepN%Math.round(2/DT)===0', 'DT: 2 s trajectory samples');
  patch(/stepN%10===0/g, 'stepN%Math.round(1/DT)===0', 'DT: 1 s samples');
  patch(/\(c\.id\+stepN\)%10/g, '(c.id+stepN)%Math.round(1/DT)', 'DT: 1 s lane-change checks');
}
// hook right after accelerations are computed (used for the braking-pulse test)
patch(/  mainAcc\(\);\n/, '  mainAcc();if(globalThis.__afterAcc)globalThis.__afterAcc();\n', 'after-acceleration hook');
// do not start the animation loop
patch(/reset\(\);resize\(\);requestAnimationFrame\(frame\);/, 'reset();', 'no animation loop');
// expose internal state
patch(/\}\)\(\);\s*$/, `globalThis.__S={P,step,reset,idm,idmEq,geom,startCrash,
  consts:{M2F,FT,MPH,CL,DT,DINT,XA,XD,IA,IB,S0,POL,ATHR},
  st:()=>({lanes,alane,rampQ,queue,t,stepN,entered,exited,people,nCrash,crash,merged,waitSum,rampDemand,rampBlocked,lcCount,
           detLog,bdEvents,wave,tripSum,tripN,tripD,gen})};
})();`, 'export state');

// ---------- browser stubs ----------
const stub = new Proxy(function () {}, {
  get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : k === 'clientWidth' ? 800 : stub),
  set: () => true, apply: () => stub, construct: () => stub,
});
const win = { devicePixelRatio: 1, addEventListener() {} };
new Function('document', 'window', 'getComputedStyle', 'requestAnimationFrame', 'devicePixelRatio', src)(stub, win, () => stub, () => 0, 1);
const S = globalThis.__S;
const K = S.consts;

// ---------- apply slider parameters (same names as P in the HTML) ----------
Object.assign(S.P, cfg.params || {});
S.reset();

// ---------- optional braking pulse (proposal 2.2: lead car brakes at -3 m/s² for 3 s at x = 1,800 m) ----------
// pulse = {t_s, x_m, decel_mps2, dur_s, lane (0 right, 1 left), n_followers, window_s, apply}
// With apply:false the same car and followers are tracked but nothing brakes: run once each way with the same
// seed and the difference in speeds is caused by the pulse alone.
const pulse = cfg.pulse || null;
let pulseCar = null, pulseRec = null;
if (pulse) {
  globalThis.__afterAcc = () => {
    const st = S.st(), t = st.t;
    if (!pulseCar && t >= pulse.t_s) {
      const arr = st.lanes[pulse.lane ?? 0], xft = pulse.x_m * K.M2F;
      let idx = -1;
      for (let i = 0; i < arr.length; i++) if (arr[i].x <= xft) { idx = i; break; } // first car at or behind x
      if (idx >= 0) {
        pulseCar = arr[idx];
        const fol = arr.slice(idx + 1, idx + 1 + (pulse.n_followers ?? 15));
        pulseRec = { t_start: t, x_start_m: pulseCar.x / K.M2F, applied: pulse.apply !== false,
                     ids: [pulseCar.id, ...fol.map(c => c.id)], t: [], v_mph: [] };
      }
    }
    if (pulseCar && pulse.apply !== false && t - pulseRec.t_start <= pulse.dur_s && !pulseCar.crashed)
      pulseCar.a = -(pulse.decel_mps2 * K.M2F);
  };
}

// ---------- run ----------
const traj = cfg.record_traj ? [] : null;
const trajEvery = Math.max(1, Math.round((cfg.traj_every_s ?? 5) / K.DT));
const trajFrom = cfg.traj_from_s ?? 0;
let negGap = 0, minGap = Infinity, orderErr = 0, steps = Math.round(duration / K.DT);
const t0 = Date.now();
for (let n = 0; n < steps; n++) {
  S.step();
  const st = S.st();
  for (let L = 0; L < 2; L++) {
    const arr = st.lanes[L];
    for (let i = 1; i < arr.length; i++) {
      const g = arr[i - 1].x - K.CL - arr[i].x;
      if (g < minGap) minGap = g;
      if (g < -1e-6) negGap++;
      if (arr[i - 1].x < arr[i].x) orderErr++;
    }
  }
  for (let i = 1; i < st.alane.length; i++) { const g = st.alane[i - 1].x - K.CL - st.alane[i].x; if (g < -1e-6) negGap++; }
  if (pulseRec && st.t - pulseRec.t_start <= (pulse.window_s ?? 120) && st.stepN % Math.max(1, Math.round(0.5 / K.DT)) === 0) {
    const byId = new Map(); for (const arr of st.lanes) for (const c of arr) byId.set(c.id, c);
    pulseRec.t.push(+(st.t - pulseRec.t_start).toFixed(2));
    pulseRec.v_mph.push(pulseRec.ids.map(id => { const c = byId.get(id); return c ? +(c.v / K.MPH).toFixed(3) : null; }));
  }
  if (traj && st.stepN % trajEvery === 0 && st.t >= trajFrom)
    for (let L = 0; L < 2; L++) for (const c of st.lanes[L]) traj.push([+st.t.toFixed(1), L, +(c.x / K.M2F).toFixed(1), +(c.v / K.MPH * 1.609344).toFixed(2), c.id]);
}
const st = S.st();
const onRoad = st.lanes[0].length + st.lanes[1].length;
const crashRemoved = st.nCrash - (st.crash ? 1 : 0);
const out = {
  ok: true,
  runtime_ms: Date.now() - t0,
  seed, duration_s: duration,
  patched,
  consts: K,
  params: S.P,
  summary: {
    t_s: st.t, entered_main: st.entered, waiting_to_enter: st.queue, exited: st.exited, on_road: onRoad, people_exited: st.people,
    ramp_arrivals: st.rampDemand, ramp_turned_away: st.rampBlocked, ramp_in_storage: st.rampQ.length, ramp_on_ramp_road: st.alane.length,
    merged: st.merged, mean_ramp_wait_s: st.merged ? st.waitSum / st.merged : null,
    lane_changes: st.lcCount, crashes: st.nCrash, crash_active: !!st.crash,
    mean_trip_s: st.tripN ? st.tripSum / st.tripN : null, mean_trip_speed_mph: st.tripSum ? st.tripD / st.tripSum / K.MPH : null,
  },
  checks: {
    negative_gap_events: negGap, min_gap_ft: isFinite(minGap) ? minGap : null, order_errors: orderErr,
    // every car that entered the main road or merged from the ramp has exited, is still on the road, or was a cleared crash
    main_balance: st.entered + st.merged - (st.exited + onRoad + crashRemoved),
    // every ramp arrival was turned away, is in storage, is on the ramp road, or has merged
    ramp_balance: st.rampDemand - (st.rampBlocked + st.rampQ.length + st.alane.length + st.merged),
  },
  detectors: st.detLog,
  breakdowns: st.bdEvents.map(e => ({ start_s: e.t, end_s: e.end, breakdown_flow_vph: e.pre, discharge_flow_vph: e.qdf, capacity_drop_pct: e.drop, shockwave_mph: e.w, crash: e.crash })),
  wave_xcorr_mph: { right: st.wave[0] && st.wave[0].w, left: st.wave[1] && st.wave[1].w },
  idm_eq: S.idmEq(),
  pulse: pulseRec,
  traj,
};
// idm() samples so Python can check the code matches the lecture equation
if (cfg.idm_samples) out.idm_samples = cfg.idm_samples.map(([v, v0, s, dv]) => S.idm(v, v0, s, dv));
process.stdout.write(JSON.stringify(out));
