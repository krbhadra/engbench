"""Battery module coolant-loop grader (thermal + fluids).

The model picks a coolant, a pump, a pump speed, a cold-plate channel diameter,
and the number of parallel channels. The grader recomputes the loop from the
task's own parameters and checks every constraint, then the objective.

Physics model (stated verbatim in the task so every solver uses the same one):
  q_cell   = I^2 * R_cell                               (per cell)
  Q_heat   = N_cells * q_cell                           (all into the cold plate)
  properties rho, cp, mu, k: linear interpolation in the task's table at T_mean,
             clamped outside it; T_mean = (T_in + T_out) / 2
  channels : n_par identical channels of diameter d and length L_ch in parallel,
             each carrying Qv / n_par and Q_heat / n_par
  v        = (Qv / n_par) / (pi d^2 / 4);  Re = rho v d / mu
  f        = 64 / Re            if Re < 2300  (laminar)
           = 0.316 Re^-0.25     otherwise     (Blasius, smooth tube)
  dP_ch    = f (L_ch / d) rho v^2 / 2
  pipe     : one supply+return run of diameter d_pipe, length L_pipe, fittings K,
             carrying the whole flow: dP_pipe = (f_p L_pipe / d_pipe + K) rho v_p^2 / 2
  dP_sys   = dP_ch + dP_pipe
  pump     : at speed fraction s, dP_pump(Qv) = s^2 * curve(Qv / s)  (affinity laws),
             P_pump = P_rated * s^3; operating point where dP_pump = dP_sys
  T_out    = T_in + Q_heat / (rho Qv cp)
  Nu       = 4.36               if Re < 2300  (laminar, constant heat flux)
           = 0.023 Re^0.8 Pr^0.4 otherwise     (Dittus-Boelter), Pr = mu cp / k
  h        = Nu k / d;  q'' = (Q_heat / n_par) / (pi d L_ch)
  T_cell   = T_out + q'' / h + q_cell * R_cp                (hottest cell, at the outlet)
  channel Re must not fall in the transition band (default 2000-3000): the
  correlations above are not valid there and the f/Nu switch at 2300 is a cliff.
  cost     = pump price + n_par * L_ch * tube price per metre(d)

Objective: minimize task["objective"]["minimize"] (pump electrical power). A design
passes only if it meets every constraint AND that metric is within
task["objective"]["tolerance"] of the brute-force optimum in task["objective"]["optimum"].

Sources: NREL/CP-540-40446 Kim & Pesaran 2006 (channel cooling archetype, property
table pattern); DOE "Improving Pumping System Performance" (affinity laws); CoolProp
INCOMP::MEG (property tables, MIT); Dittus-Boelter 1930 and Blasius correlations.
"""
from __future__ import annotations

import math

from objective import check_objective


def _interp(points, x):
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def _props(table, t):
    """table rows: [T_C, rho, cp, mu, k]. Returns (rho, cp, mu, k) at t."""
    return tuple(_interp([(r[0], r[i]) for r in table], t) for i in (1, 2, 3, 4))


def _find(items, id_):
    return next(x for x in items if x["id"] == id_)


def _friction(re):
    return 64.0 / re if re < 2300 else 0.316 * re ** -0.25


def _dp_system(qv, p, d, n_par, rho, mu):
    v = (qv / n_par) / (math.pi * d * d / 4)
    re = rho * v * d / mu
    dp_ch = _friction(re) * (p["l_ch_m"] / d) * rho * v * v / 2
    vp = qv / (math.pi * p["d_pipe_m"] ** 2 / 4)
    rep = rho * vp * p["d_pipe_m"] / mu
    dp_pipe = (_friction(rep) * p["l_pipe_m"] / p["d_pipe_m"] + p["k_fittings"]) * rho * vp * vp / 2
    return dp_ch + dp_pipe, v, re


def _operating_point(curve_lpm_pa, s, p, d, n_par, rho, mu):
    """Qv (m^3/s) where s^2 * curve(Q/s) = dP_sys(Q). Bisection; curve in L/min vs Pa."""
    lo, hi = 1e-9, s * curve_lpm_pa[-1][0] / 60000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        pump = s * s * _interp(curve_lpm_pa, mid * 60000.0 / s)
        if pump > _dp_system(mid, p, d, n_par, rho, mu)[0]:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(task: dict, design: dict) -> dict:
    p = task["params"]
    cool = _find(task["coolants"], design["coolant"])
    pump = _find(task["pumps"], design["pump"])
    s = float(design["speed"])
    d = float(design["channel_d_mm"]) / 1000.0
    n_par = int(design["n_parallel"])
    curve = [tuple(pt) for pt in pump["curve"]]
    q_cell = p["i_cell_a"] ** 2 * p["r_cell_ohm"]
    q_heat = p["n_cells"] * q_cell

    t_mean = p["t_in_c"] + 2.0
    for _ in range(200):  # ponytail: damped fixed point; properties <-> flow <-> outlet temperature
        rho, cp, mu, k = _props(cool["props"], t_mean)
        qv = _operating_point(curve, s, p, d, n_par, rho, mu)
        t_out = p["t_in_c"] + q_heat / (rho * qv * cp)
        new = (p["t_in_c"] + t_out) / 2
        if abs(new - t_mean) < 1e-7:
            t_mean = new
            break
        t_mean = 0.5 * (t_mean + new)
    rho, cp, mu, k = _props(cool["props"], t_mean)
    dp, v, re = _dp_system(qv, p, d, n_par, rho, mu)
    pr = mu * cp / k
    nu = 4.36 if re < 2300 else 0.023 * re ** 0.8 * pr ** 0.4
    h = nu * k / d
    q_flux = (q_heat / n_par) / (math.pi * d * p["l_ch_m"])
    t_cell = t_out + q_flux / h + q_cell * p["r_cp_kw"]
    tube = _interp([(float(k_), v_) for k_, v_ in sorted(task["tube_price_per_m"].items(), key=lambda kv: float(kv[0]))], d * 1000)
    return {
        "q_lpm": qv * 60000.0, "dp_pa": dp, "re": re, "v_ms": v, "h": h, "nu": nu, "t_out": t_out, "t_mean": t_mean,
        "t_cell": t_cell, "q_heat_w": q_heat, "pump_power_w": pump["power_w"] * s ** 3,
        "cost": pump["price"] + n_par * p["l_ch_m"] * tube, "freeze_c": cool["freeze_c"],
    }


def grade(task: dict, output: dict) -> dict:
    p, lim = task["params"], task["limits"]
    keys = ("coolant", "pump", "speed", "channel_d_mm", "n_parallel")
    design = {k: output.get(k) for k in keys}
    missing = [k for k in keys if design[k] in (None, "")]
    if missing:
        return {"passed": False, "violations": [f"missing fields: {missing}"]}
    for key, cat in (("coolant", "coolants"), ("pump", "pumps")):
        if not any(x["id"] == design[key] for x in task[cat]):
            return {"passed": False, "violations": [f"unknown {key} id '{design[key]}'"]}
    try:
        s = float(design["speed"]); dmm = float(design["channel_d_mm"]); n_par = int(design["n_parallel"])
    except (TypeError, ValueError):
        return {"passed": False, "violations": ["speed, channel_d_mm, n_parallel must be numbers"]}
    if not (p["speed_min"] - 1e-9 <= s <= 1.0 + 1e-9):
        return {"passed": False, "violations": [f"speed {s} outside {p['speed_min']}-1.0"]}
    if str(int(dmm)) not in task["tube_price_per_m"] or dmm != int(dmm):
        return {"passed": False, "violations": [f"channel_d_mm {dmm} not in catalog {sorted(task['tube_price_per_m'])}"]}
    if not (1 <= n_par <= p["n_parallel_max"]):
        return {"passed": False, "violations": [f"n_parallel {n_par} outside 1-{p['n_parallel_max']}"]}

    m = evaluate(task, design)
    v = []
    if m["freeze_c"] > p["t_site_min_c"] + 1e-9:
        v.append(f"coolant freeze point {m['freeze_c']:.1f} C is above the site minimum {p['t_site_min_c']:.1f} C")
    lo, hi = p["re_transition_band"]
    if lo < m["re"] < hi:
        v.append(f"channel Re {m['re']:.0f} is in the transition band {lo:.0f}-{hi:.0f} (laminar or turbulent only)")
    if m["t_cell"] > lim["t_cell_max_c"] + 1e-9:
        v.append(f"hottest cell {m['t_cell']:.2f} C exceeds {lim['t_cell_max_c']:.1f} C "
                 f"(T_out={m['t_out']:.2f} C, h={m['h']:.0f} W/m2K, Re={m['re']:.0f}, Q={m['q_lpm']:.2f} L/min)")
    if m["t_out"] - p["t_in_c"] > lim["dt_coolant_max_c"] + 1e-9:
        v.append(f"coolant temperature rise {m['t_out'] - p['t_in_c']:.2f} C exceeds {lim['dt_coolant_max_c']:.1f} C")
    if m["v_ms"] > lim["v_max_ms"] + 1e-9:
        v.append(f"channel velocity {m['v_ms']:.2f} m/s exceeds {lim['v_max_ms']:.1f} m/s")
    if m["pump_power_w"] > lim["pump_power_max_w"] + 1e-9:
        v.append(f"pump power {m['pump_power_w']:.2f} W exceeds {lim['pump_power_max_w']:.1f} W")
    if m["cost"] > lim["cost_max"] + 1e-9:
        v.append(f"cost {m['cost']:.2f} exceeds budget {lim['cost_max']:.2f}")
    check_objective(task, m, v)
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
