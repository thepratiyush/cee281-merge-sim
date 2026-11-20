"""Hypothesis sweeps for the midterm report (Section 3), run on the Stage 3 HTML model.

Each sweep is a list of runs (slider settings x seeds). `load_or_run(name)` returns one row per run and caches the
rows in tables/sweep_<name>.csv, so the figures can be redrawn without re-running. Delete a CSV (or pass
rerun=True) to run that sweep again. One 1 h run takes about 5-10 s; the full set (~160 runs) about 10-15 min
on a 2-core machine.

Every row has the safety and merge measures of Section 2.9, counted over the 3,000 s window after the 600 s warm-up:
people_vph (people delivered at the exit), tet_per_1000vmi (TET*, veh-s with TTC < 2 s per 1,000 veh-mi),
hard_per_1000vmi / severe_per_1000vmi (braking events), forced_pct / tight_pct (merge indicators).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from simtools import bridge as st  # noqa: E402

TABLES = HERE / "tables"
SEEDS = (1, 2, 3)
BASE = dict(crash=0)                     # crashes off except in the incident sweep
DESIGN = dict(flow=2800, ramp=600)       # congested design point used for H2, H6 and the grid


def _cfg(seed, label, **params):
    return dict(params={**BASE, **params}, seed=seed, _label=label)


def configs(name: str) -> list[dict]:
    c = []
    if name == "demand":            # H1 plateau: main-road demand sweep, ramp 200 veh/h
        for q in (1200, 1800, 2400, 3000, 3600, 4400):
            c += [_cfg(s, dict(qA=q, qB=200), flow=q, ramp=200) for s in SEEDS]
    elif name == "ramp":            # H1 displacement: ramp sweep at q_A = 3,200 veh/h
        for q in (0, 300, 600, 900, 1200):
            c += [_cfg(s, dict(qA=3200, qB=q), flow=3200, ramp=q) for s in SEEDS]
    elif name == "oneway":          # H2 (T) and H6 (b_safe, geometry) one-factor sweeps at 2,800 + 600 veh/h
        runs = [("default", "-", {})]
        runs += [("T", v, dict(headway=v)) for v in (0.8, 1.5, 2.0)]
        runs += [("bsafe", v, dict(bsafe=v)) for v in (6, 9, 20)]
        runs += [("rlen", v, dict(rlen=v)) for v in (200, 700, 1000)]
        runs += [("rampm", v, dict(rampm=v)) for v in (2000, 3000)]
        runs += [("lc", "off", dict(lc=False))]
        for f, v, p in runs:
            c += [_cfg(s, dict(factor=f, value=v), **DESIGN, **p) for s in SEEDS]
    elif name == "grid":            # H6 geometry x meter grid at 2,800 + 600 veh/h
        for L in (200, 400, 700, 1000):
            for m in (2, 3, 4, 6):
                c += [_cfg(s, dict(rlen=L, meter=m), **DESIGN, rlen=L, meter=m) for s in SEEDS]
    elif name == "meter":           # H4 meter sweep, ramp 900 veh/h
        for q in (2800, 3200):
            for m in (2, 6, 8, 12, 20):
                c += [_cfg(s, dict(qA=q, meter=m), flow=q, ramp=900, meter=m) for s in SEEDS]
    elif name == "incident":        # H7: one lane blocked at t = 1,800 s, 2,000 + 300 veh/h, 4 seeds
        xs = {1: 1600, 2: 2200, 3: 2800, 4: 3400}
        for clear in (0, 0.25, 0.5):
            for s in (1, 2, 3, 4):
                cfg = _cfg(s, dict(clear_h=clear, crash_x_m=xs[s] if clear else None), flow=2000, ramp=300, clear=clear or 1.0)
                if clear:
                    cfg["crash_at"] = dict(t_s=1800, x_m=xs[s], lane=s % 2)
                c.append(cfg)
    else:
        raise ValueError(name)
    return c


def _row(out, label):
    r = st.summary_row(out, **label)
    r.update(out["safety"])
    r["crash_x_m_actual"] = (out.get("crash_event") or {}).get("x_m")
    return r


def run(name: str, workers: int | None = None) -> pd.DataFrame:
    cfgs = configs(name)
    labels = [c.pop("_label") for c in cfgs]
    outs = st.run_many(cfgs, workers=workers)
    return pd.DataFrame([_row(o, l) for o, l in zip(outs, labels)])


def load_or_run(name: str, rerun: bool = False, workers: int | None = None) -> pd.DataFrame:
    TABLES.mkdir(exist_ok=True)
    f = TABLES / f"sweep_{name}.csv"
    if f.exists() and not rerun:
        return pd.read_csv(f)
    df = run(name, workers)
    df.to_csv(f, index=False)
    return df


ALL = ("demand", "ramp", "oneway", "grid", "meter", "incident")

if __name__ == "__main__":
    for n in (sys.argv[1:] or ALL):
        d = load_or_run(n, rerun=True)
        print(n, len(d), "runs")
