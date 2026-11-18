"""Course formulas used as the "expected" values in the Stage 3 tests. SI units unless named otherwise.

Sources: Intermediate 1 proposal (Sections 1.1-1.3, 2.3) and CEE 181/281 lecture slides
(Lecture 02 speeds, Lecture 03 flow theory A, Lecture 04 flow theory B, Lectures 08A/08B safety).
"""
from __future__ import annotations

import numpy as np

MPS_PER_MPH = 0.44704
KMH_PER_MPH = 1.609344


# ---------- IDM (Lecture 04, slides 37-41; Treiber et al., 2000) ----------
def idm_s_star(v, dv, s0, T, a, b):
    """Desired gap s*(v, dv) = s0 + max(0, vT + v dv / (2 sqrt(ab)))."""
    return s0 + np.maximum(0.0, v * T + v * dv / (2.0 * np.sqrt(a * b)))


def idm_acc(v, v0, s, dv, a, b, T, s0, delta=4.0):
    """IDM acceleration dv/dt = a [1 - (v/v0)^delta - (s*/s)^2]."""
    return a * (1.0 - (v / v0) ** delta - (idm_s_star(v, dv, s0, T, a, b) / s) ** 2)


def idm_equilibrium(v0, T, s0, length, delta=4.0, n=2000):
    """Steady state (Lecture 04, Eq. 10.12-10.16): s_e(v) = (s0 + vT) / sqrt(1 - (v/v0)^delta),
    k = 1 / (s_e + l), Q_e = k v. Returns arrays v (m/s), k (veh/km), q (veh/h). Independent of a and b."""
    v = np.linspace(0, v0 * 0.9995, n)
    se = (s0 + v * T) / np.sqrt(1 - (v / v0) ** delta)
    k = 1000.0 / (se + length)
    return v, k, k * v * 3.6


def idm_capacity(v0, T, s0, length, delta=4.0):
    """Peak of Q_e(k): lane capacity (veh/h/lane) and the density where it occurs (veh/km)."""
    _, k, q = idm_equilibrium(v0, T, s0, length, delta)
    i = int(np.argmax(q))
    return q[i], k[i]


# ---------- Newell (Lecture 04, slides 24-27) ----------
def newell_wave_speed_kmh(l_eff, T):
    """Congested wave speed w = -l_eff / T, in km/h. Lecture range: -20 to -15 km/h."""
    return -l_eff / T * 3.6


# ---------- queues (Lecture 03; proposal 1.1) ----------
def md1(lam, mu):
    """M/D/1 queue with Poisson arrivals (lam) and fixed service (mu), same units.
    Returns rho, Lq (mean number waiting, the proposal's Q-bar), L (number in system = Lq + rho), Wq (mean wait)."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, Lq=np.inf, L=np.inf, Wq=np.inf)
    lq = rho ** 2 / (2 * (1 - rho))
    return dict(rho=rho, Lq=lq, L=lq + rho, Wq=lq / lam)


def dd1_queue(v_demand, c_reduced, t_inc_h):
    """Deterministic queue behind a crash: vehicles queued at the end of the incident (Lecture 03)."""
    return max(0.0, (v_demand - c_reduced) * t_inc_h)


# ---------- gaps and shockwaves (Lecture 03) ----------
def acceptable_gaps_per_hour(V_vph, t_c):
    """Expected number of headways >= t_c per hour with Poisson traffic: V e^(-lambda t_c), lambda = V/3600."""
    return V_vph * np.exp(-V_vph / 3600 * t_c)


def shockwave_speed(qA, kA, qB, kB):
    """omega_AB = (q_A - q_B) / (k_A - k_B). Units follow the inputs (veh/h and veh/km give km/h)."""
    return (qA - qB) / (kA - kB)


# ---------- speeds (Lecture 02) ----------
def time_mean_speed(spot_speeds):
    return float(np.mean(spot_speeds))


def space_mean_speed(spot_speeds):
    """Harmonic mean of spot speeds at a point detector."""
    s = np.asarray(spot_speeds, float)
    return float(len(s) / np.sum(1 / s))


# ---------- demand (proposal 1.1) ----------
def peak_hour_volume(aadt, K=0.10, D=0.55):
    """q_peak = AADT x K x D. K = 0.08-0.12, D = 0.5-0.6."""
    return aadt * K * D


# ---------- safety (Lecture 08A; proposal 1.2) ----------
def crashes_per_year(R_per_mvm, aadt, length_mi):
    """N = R x AADT x L x 365 / 10^6 (R per million vehicle-miles)."""
    return R_per_mvm * aadt * length_mi * 365 / 1e6


def power_model_ratio(v_before, v_after, n):
    """Nilsson Power Model: N2/N1 = (v2/v1)^n; n about 2 for injury, 4 for fatal crashes."""
    return (v_after / v_before) ** n


def spf_hsm(length_mi, aadt, beta0, beta1, cmfs=()):
    """HSM-style SPF: N_pred = L e^beta0 AADT^beta1 x product of CMFs."""
    return length_mi * np.exp(beta0) * aadt ** beta1 * float(np.prod(cmfs) if len(cmfs) else 1.0)


def ttc(gap_m, v_follower, v_leader):
    """Time to collision (s) if neither car changes speed; inf when not closing."""
    dv = v_follower - v_leader
    return gap_m / dv if dv > 0 else np.inf
