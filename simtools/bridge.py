"""Run the Stage 3 HTML simulation from Python.

The simulator is the JavaScript inside stage3_two_lane_merge/two_lane_merge.html.
`run_stage3` sends settings to simtools/sim_runner.js (Node.js), which runs that same
JavaScript without a browser and returns the results. Nothing is re-implemented in Python,
so every test runs the real model.

Requires Node.js 18 or newer on your PATH (`node --version`). On a Mac: `brew install node`.

Units: the HTML works in feet, mph and veh/h. Helper functions below add metric columns.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
STAGE3_HTML = REPO / "stage3_two_lane_merge" / "two_lane_merge.html"
RUNNER = Path(__file__).resolve().parent / "sim_runner.js"

FT_PER_M = 3.28084
M_PER_FT = 0.3048
MPS_PER_MPH = 0.44704
KMH_PER_MPH = 1.609344

# Slider names in the HTML (P = {...}) and what they mean. Code units.
SLIDERS = {
    "flow": "main road demand q_A, veh/h (both lanes together)",
    "mean": "mean desired speed v0, mph",
    "sd": "std. dev. of desired speed, mph",
    "headway": "IDM time gap T, s",
    "crash": "crash rate R, crashes per million vehicle-miles (0 = off)",
    "clear": "crash clearance time t_inc, h",
    "ppc": "people per car",
    "ramp": "ramp demand q_B, veh/h",
    "rampm": "merge location, m",
    "rampL": "ramp length, m",
    "rlen": "acceleration lane length, ft",
    "brake": "braking cap, ft/s^2",
    "meter": "ramp meter: seconds per car",
    "nmax": "ramp storage n_max, cars",
    "bsafe": "MOBIL b_safe, ft/s^2",
    "lc": "lane changing on/off",
}
# Hard-coded constants that sim_runner.js can patch. Code units.
CONSTS = {
    "IA": "IDM max acceleration a, ft/s^2 (code: 5)",
    "IB": "IDM comfortable deceleration b, ft/s^2 (code: 9)",
    "S0": "IDM standstill gap s0, ft (code: 8)",
    "CL": "car length l, ft (code: 15)",
    "POL": "MOBIL politeness p (code: 0.2)",
    "ATHR": "MOBIL threshold, ft/s^2 (code: 0.33)",
    "DT": "time step, s (code: 0.1)",
    "XA_m": "detector A position, m (code: 1500)",
    "XD_m": "detector D position, m (code: 3300)",
}


def node_path() -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js not found. Install it (Mac: `brew install node`) and restart the notebook kernel.")
    return node


def run_stage3(params: dict | None = None, consts: dict | None = None, duration_s: float = 3600, seed: int = 1,
               record_traj: bool = False, traj_every_s: float = 5, traj_from_s: float = 0,
               pulse: dict | None = None, idm_samples: list | None = None, html: str | Path | None = None,
               timeout_s: float = 600) -> dict:
    """Run the Stage 3 HTML model headless and return its results as a dict.

    params: slider values, e.g. {"flow": 2400, "ramp": 600, "meter": 4.5}. See SLIDERS.
    consts: hard-coded constants to patch, e.g. {"IA": 3.28, "DT": 0.05}. See CONSTS.
    pulse:  braking pulse, e.g. {"t_s": 900, "x_m": 1800, "decel_mps2": 3, "dur_s": 3, "lane": 0}.
    """
    cfg = {
        "html": str(html or STAGE3_HTML), "duration_s": duration_s, "seed": seed,
        "params": params or {}, "consts": consts or {},
        "record_traj": record_traj, "traj_every_s": traj_every_s, "traj_from_s": traj_from_s,
        "pulse": pulse, "idm_samples": idm_samples,
    }
    p = subprocess.run([node_path(), str(RUNNER)], input=json.dumps(cfg), capture_output=True, text=True, timeout=timeout_s)
    if p.returncode != 0:
        raise RuntimeError(f"Simulation failed:\n{p.stderr[-3000:]}")
    out = json.loads(p.stdout)
    out["input"] = {k: v for k, v in cfg.items() if k != "idm_samples"}
    return out


def run_many(configs: list[dict], workers: int | None = None) -> list[dict]:
    """Run several configurations in parallel. Each item is a dict of run_stage3 keyword arguments."""
    workers = workers or max(1, (os.cpu_count() or 2))
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda c: run_stage3(**c), configs))


def detectors_df(out: dict) -> pd.DataFrame:
    """30 s detector records as a table, with metric columns added."""
    df = pd.DataFrame(out["detectors"])
    if df.empty:
        return df
    df["x_m"] = df["x_ft"] * M_PER_FT
    for c in ("tmean_mph", "smean_mph"):
        if c in df:
            df[c.replace("mph", "kmh")] = df[c] * KMH_PER_MPH
    if "density_vpm" in df:
        df["density_vpkm"] = df["density_vpm"] / KMH_PER_MPH
    df["t_mid_min"] = (df["t0"] + df["t1"]) / 2 / 60
    return df


def traj_df(out: dict) -> pd.DataFrame:
    """Sampled vehicle positions (requires record_traj=True): t (s), lane (0 right, 1 left), x (m), v (km/h), id."""
    return pd.DataFrame(out.get("traj") or [], columns=["t_s", "lane", "x_m", "v_kmh", "id"])


def summary_row(out: dict, **labels) -> dict:
    """One flat row per run, handy for building comparison tables."""
    s, c = out["summary"], out["checks"]
    det = detectors_df(out)
    warm = det[det["t0"] >= 600] if not det.empty else det
    hours = max(1e-9, (out["duration_s"] - 600) / 3600)
    flowD = warm[(warm.sensor == "D")]["count"].sum() / hours if not warm.empty else None
    flowA = warm[(warm.sensor == "A")]["count"].sum() / hours if not warm.empty else None
    row = dict(labels)
    row.update(seed=out["seed"], flow_A_vph=flowA, flow_D_vph=flowD, exited=s["exited"],
               mean_trip_s=s["mean_trip_s"], trip_speed_mph=s["mean_trip_speed_mph"],
               ramp_wait_s=s["mean_ramp_wait_s"], ramp_turned_away=s["ramp_turned_away"],
               breakdowns=len(out["breakdowns"]), wave_right_mph=out["wave_xcorr_mph"]["right"],
               neg_gaps=c["negative_gap_events"], main_balance=c["main_balance"], ramp_balance=c["ramp_balance"],
               runtime_s=out["runtime_ms"] / 1000)
    return row
