"""Stage 3 parameters: value in the code, value planned in the Intermediate 1 proposal, and the plausible range.

All values in SI (m, s, m/s, m/s^2) unless the unit column says otherwise. `code_units` gives the value
as written in the HTML. Ranges come from the proposal's tables, which cite Lecture 04 Table 11.2 and
Treiber et al. (2000). None means the proposal gives no value or range.
"""
from __future__ import annotations

import math

import pandas as pd

FT, MPH = 0.3048, 0.44704

PARAMS = [
    # key, symbol, meaning, unit, code (SI), code as written, proposal (SI), low, high, where in code, source
    ("v0_mean", "v0", "mean desired speed", "m/s", 30 * MPH, "30 mph (slider 'mean')", None, 35 * MPH, 75 * MPH,
     "slider", "Proposal 2.2 grid: speed limit 35/55/75 mph; Lecture 04 Table 11.2"),
    ("v0_sd", "σ_v0", "spread of desired speed", "m/s", 5 * MPH, "5 mph (slider 'sd')", 5 * MPH, None, None,
     "slider", "Proposal 1.3 (Gaussian σ ≈ 5 mph); Lecture 05B"),
    ("T", "T", "desired time gap", "s", 1.0, "1.0 s (slider 'headway')", 1.0, 1.0, 1.6,
     "slider", "Lecture 04 Table 11.2, Fig. 11.2; proposal grid 1.0 and 1.5 s"),
    ("s0", "s0", "standstill gap", "m", 8 * FT, "8 ft (const S0)", 2.0, 1.0, 3.0,
     "const", "Lecture 04 Table 11.2"),
    ("a", "a", "maximum acceleration", "m/s²", 5 * FT, "5 ft/s² (const IA)", 1.0, 0.73, 1.0,
     "const", "Lecture 04 Table 11.2; Treiber et al. (2000)"),
    ("b", "b", "comfortable deceleration", "m/s²", 9 * FT, "9 ft/s² (const IB)", 1.5, 1.5, 1.67,
     "const", "Lecture 04 Table 11.2; Treiber et al. (2000)"),
    ("delta", "δ", "acceleration exponent", "–", 4, "4 (in idm())", 4, 4, 4,
     "const", "Lecture 04 Table 11.2"),
    ("l", "l", "vehicle length", "m", 15 * FT, "15 ft (const CL)", 5.0, None, None,
     "const", "Lecture 04 Table 11.2 (car)"),
    ("occ", "occ", "people per car", "persons", 1.5, "1.5 (slider 'ppc')", 1.5, None, None,
     "slider", "Proposal 1.3, assumed"),
    ("b_safe", "b_safe", "max braking imposed on new follower (MOBIL)", "m/s²", 13 * FT, "13 ft/s² (slider 'bsafe')", 4.0, None, None,
     "slider", "Proposal 1.1 and 2.2; Lecture 04 Eq. 14.4"),
    ("p", "p", "MOBIL politeness", "–", 0.2, "0.2 (const POL)", None, None, None,
     "const", "Kesting et al. (2007)"),
    ("a_thr", "Δa_th", "MOBIL lane-change threshold", "m/s²", 0.33 * FT, "0.33 ft/s² (const ATHR)", None, None, None,
     "const", "Kesting et al. (2007)"),
    ("q_A", "q_A", "main road demand (both lanes)", "veh/h", 2000, "2,000 veh/h (slider 'flow')", 2400, None, None,
     "slider", "Proposal 2.1-2.2"),
    ("q_B", "q_B", "ramp demand", "veh/h", 200, "200 veh/h (slider 'ramp')", None, 300, 1500,
     "slider", "Proposal 2.2 experiment grid"),
    ("mu_meter", "μ", "ramp meter service rate", "veh/h", 3600 / 2.0, "2.0 s/car (slider 'meter')", None, 720, 900,
     "slider", "Proposal 2.2 (one car per green, μ = 720–900 veh/h)"),
    ("n_max", "n_max", "ramp storage", "veh", 20, "20 (slider 'nmax')", 20, None, None,
     "slider", "Proposal 2.2; capping rule, Lecture 05B"),
    ("L_road", "L", "main road length", "m", 4000, "4,000 m", 4000, None, None,
     "const", "Proposal 2.2"),
    ("x_merge", "x_M", "merge location", "m", 2500, "2,500 m (slider 'rampm')", 2500, None, None,
     "slider", "Proposal 2.2"),
    ("L_ramp", "L_B", "ramp length", "m", 500, "500 m (slider 'rampL')", 500, None, None,
     "slider", "Proposal 2.2"),
    ("L_accel", "L_acc", "acceleration lane length", "m", 400 * FT, "400 ft (slider 'rlen')", None, None, None,
     "slider", "Not set in proposal"),
    ("x_A", "x_A", "detector A position", "m", 1500, "1,500 m (const XA)", 1500, None, None,
     "const", "Proposal 2.2"),
    ("x_D", "x_D", "detector D position", "m", 3300, "3,300 m (const XD)", 3300, None, None,
     "const", "Proposal 2.2"),
    ("dt", "Δt", "time step (ballistic update)", "s", 0.1, "0.1 s (const DT)", 0.1, None, None,
     "const", "Proposal 2.2; Lecture 04 Eq. 10.9–10.10"),
    ("t_agg", "–", "detector aggregation interval", "s", 30, "30 s (const DINT)", 30, None, None,
     "const", "Proposal 2.2"),
    ("warmup", "–", "warm-up discarded", "s", 600, "600 s (breakdown detection)", 600, None, None,
     "const", "Proposal 2.2 (first 10 min)"),
    ("R", "R", "crash rate", "per 10⁶ veh-mi", 1.0, "1.0 (slider 'crash')", None, None, None,
     "slider", "Proposal 1.2; Lecture 08A crash rates"),
    ("t_inc", "t_inc", "crash clearance time", "h", 1.0, "1.0 h (slider 'clear')", None, None, None,
     "slider", "Proposal 1.1"),
    ("K", "K", "peak-hour share of AADT", "–", None, "not in code", None, 0.08, 0.12,
     "missing", "Proposal 1.1"),
    ("D", "D", "peak-direction share", "–", None, "not in code", None, 0.5, 0.6,
     "missing", "Proposal 1.1"),
    ("TTC_c", "TTC", "conflict threshold", "s", None, "not in code", 3.0, None, None,
     "missing", "Proposal 1.2; Hayward (1972); Lecture 08B"),
    ("n_inj", "n", "Power Model exponent, injury", "–", None, "not in code", 2, None, None,
     "missing", "Proposal 1.2; Nilsson (2004)"),
    ("n_fat", "n", "Power Model exponent, fatal", "–", None, "not in code", 4, None, None,
     "missing", "Proposal 1.2; Nilsson (2004)"),
]
COLS = ["key", "symbol", "meaning", "unit", "code_si", "code_as_written", "proposal_si", "low", "high", "where", "source"]


def _none(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def status(code, prop, low, high, tol=0.02):
    code, prop, low, high = map(_none, (code, prop, low, high))
    if code is None:
        return "not in code"
    inside = (low is None or code >= low * (1 - 1e-9)) and (high is None or code <= high * (1 + 1e-9))
    has_range = low is not None or high is not None
    if prop is not None and abs(code - prop) <= tol * max(abs(prop), 1e-9):
        return "matches proposal"
    if has_range and not inside:
        return "OUTSIDE range"
    if prop is None and not has_range:
        return "code only (proposal sets no value)"
    if prop is None:
        return "inside range"
    return "differs, inside range" if has_range else "DIFFERS from proposal"


def table() -> pd.DataFrame:
    df = pd.DataFrame(PARAMS, columns=COLS)
    df["status"] = [status(r.code_si, r.proposal_si, r.low, r.high) for r in df.itertuples()]
    return df
