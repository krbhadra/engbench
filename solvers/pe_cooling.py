"""Power-electronics cooling chain grader (electronics + thermal + fluids).

The model picks a switching frequency, a heat sink, and a fan (or none) for a
synchronous buck converter. The grader recomputes the whole chain from the
task's own parameters and checks every constraint:

  losses(fsw, Tj)  -> junction temperature via Rth chain and Rsa(airflow)
  airflow          <- fan PQ curve intersected with the enclosure system curve
  ripple limits    -> lower bound on fsw
  efficiency, noise, height, cost limits

Physics model (stated verbatim in the task so every solver uses the same one):
  Rds(Tj)  = Rds25 * (1 + alpha * (Tj - 25))
  P_cond   = Iout^2 * Rds(Tj)                (D + (1-D) = 1, both FETs identical)
  P_sw     = 0.5 * Vin * Iout * (tr + tf) * fsw
  P_gate   = 2 * Qg * Vgs * fsw
  P        = P_cond + P_sw + P_gate
  Tj       = Ta + P * (RthJC + RthCS + Rsa(v))
  v        = Q / 3600 / A_duct                 (m/s through the sink)
  Q        : fan curve dP_fan(Q) = k * Q^2      (system curve), Q in m^3/h
  dI       = Vout * (1 - D) / (L * fsw),  dV = dI / (8 * C * fsw),  D = Vout / Vin
  eta      = Pout / (Pout + P)

Sources: Kunzi, "Thermal Design of Power Electronic Circuits", CERN-2015-003 (CC BY 4.0);
TI SPRA953D package thermal metrics; Boyd board-level heat sink selection method;
fan-curve / system-curve operating point (ebm-papst application note).
"""
from __future__ import annotations


def _interp(points, x):
    """Piecewise-linear interpolation over sorted (x, y) points; clamps outside the range."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def fan_operating_point(fan_curve, k):
    """Q (m^3/h) where the fan's static pressure equals the system curve k*Q^2. Bisection."""
    lo, hi = 0.0, fan_curve[-1][0]
    for _ in range(60):
        mid = (lo + hi) / 2
        if _interp(fan_curve, mid) > k * mid * mid:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(task: dict, design: dict) -> dict:
    """Full chain for one design. Returns metrics; raises KeyError on unknown catalog ids."""
    p = task["params"]
    fsw = float(design["fsw_hz"])
    sink = next(s for s in task["heatsinks"] if s["id"] == design["heatsink"])
    fan = None if design.get("fan") in (None, "", "none") else next(f for f in task["fans"] if f["id"] == design["fan"])

    if fan:
        q = fan_operating_point([tuple(pt) for pt in fan["curve"]], p["k_system"])
        v = q / 3600.0 / p["duct_area_m2"]
    else:
        q, v = 0.0, 0.0
    rsa = _interp([tuple(pt) for pt in sink["rsa_vs_v"]], v)

    d = p["vout"] / p["vin"]
    tj = p["ta"] + 20.0  # ponytail: fixed-point iteration; converges in a few steps for realistic alpha
    for _ in range(50):
        rds = p["rds25"] * (1 + p["alpha"] * (tj - 25))
        p_cond = p["iout"] ** 2 * rds
        p_sw = 0.5 * p["vin"] * p["iout"] * p["tr_tf_s"] * fsw
        p_gate = 2 * p["qg_c"] * p["vgs"] * fsw
        ploss = p_cond + p_sw + p_gate
        tj_new = p["ta"] + ploss * (p["rth_jc"] + p["rth_cs"] + rsa)
        if abs(tj_new - tj) < 1e-6:
            break
        tj = tj_new
    tj = tj_new

    d_i = p["vout"] * (1 - d) / (p["l_h"] * fsw)
    d_v = d_i / (8 * p["c_f"] * fsw)
    pout = p["vout"] * p["iout"]
    return {
        "fsw_hz": fsw, "q_m3h": q, "v_ms": v, "rsa": rsa, "p_loss": ploss, "p_cond": p_cond,
        "p_sw": p_sw, "tj": tj, "eta": pout / (pout + ploss), "d_i": d_i, "d_v": d_v,
        "cost": sink["price"] + (fan["price"] if fan else 0.0),
        "noise_dba": fan["dba"] if fan else 0.0, "height_mm": sink["height_mm"],
    }


def grade(task: dict, output: dict) -> dict:
    p, lim = task["params"], task["limits"]
    design = {k: output.get(k) for k in ("fsw_hz", "heatsink", "fan")}
    missing = [k for k in ("fsw_hz", "heatsink") if design[k] in (None, "")]
    if missing:
        return {"passed": False, "violations": [f"missing fields: {missing}"]}
    try:
        design["fsw_hz"] = float(design["fsw_hz"])
    except (TypeError, ValueError):
        return {"passed": False, "violations": ["fsw_hz is not a number"]}
    if not any(s["id"] == design["heatsink"] for s in task["heatsinks"]):
        return {"passed": False, "violations": [f"unknown heatsink id '{design['heatsink']}'"]}
    if design["fan"] not in (None, "", "none") and not any(f["id"] == design["fan"] for f in task["fans"]):
        return {"passed": False, "violations": [f"unknown fan id '{design['fan']}'"]}

    m = evaluate(task, design)
    v = []
    if not (p["fsw_min_hz"] <= m["fsw_hz"] <= p["fsw_max_hz"]):
        v.append(f"fsw {m['fsw_hz']:.0f} Hz outside controller range {p['fsw_min_hz']:.0f}-{p['fsw_max_hz']:.0f} Hz")
    if m["d_i"] > lim["ripple_i_max_a"] + 1e-9:
        v.append(f"inductor ripple {m['d_i']:.2f} A exceeds {lim['ripple_i_max_a']:.2f} A")
    if m["d_v"] > lim["ripple_v_max_v"] + 1e-9:
        v.append(f"output ripple {m['d_v']*1e3:.1f} mV exceeds {lim['ripple_v_max_v']*1e3:.1f} mV")
    if m["tj"] > lim["tj_max_c"] + 1e-9:
        v.append(f"junction temperature {m['tj']:.1f} C exceeds {lim['tj_max_c']:.1f} C (P={m['p_loss']:.2f} W, Rsa={m['rsa']:.2f} C/W, v={m['v_ms']:.2f} m/s)")
    if m["eta"] < lim["eta_min"] - 1e-9:
        v.append(f"efficiency {m['eta']*100:.2f}% below {lim['eta_min']*100:.2f}% (P={m['p_loss']:.2f} W)")
    if m["noise_dba"] > lim["noise_max_dba"] + 1e-9:
        v.append(f"fan noise {m['noise_dba']:.0f} dBA exceeds {lim['noise_max_dba']:.0f} dBA")
    if m["height_mm"] > lim["height_max_mm"] + 1e-9:
        v.append(f"heatsink height {m['height_mm']:.0f} mm exceeds {lim['height_max_mm']:.0f} mm")
    if m["cost"] > lim["cost_max"] + 1e-9:
        v.append(f"cost {m['cost']:.2f} exceeds budget {lim['cost_max']:.2f}")
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
