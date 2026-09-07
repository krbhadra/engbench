"""Power-electronics cooling chain grader (electronics + thermal + fluids).

The model picks a switching frequency, an inductor, a heat sink, and a fan (or
none) for a synchronous buck converter. The grader recomputes the whole chain
from the task's own parameters and checks every constraint. Four decisions,
three physical loops:

  fsw + inductor  -> ripple, inductor saturation, FET switching loss, inductor loss
  fan             -> airflow Q (fan curve vs enclosure system curve)
  Q + total heat  -> enclosure air temperature (with fan: convective; no fan: R_encl)
  Q + heat sink   -> Rsa(v); with FET loss and air temperature -> Tj
  Tj              -> Rds(on) -> FET conduction loss (fixed point)
  fan power       -> counts against system efficiency

Physics model (stated verbatim in the task so every solver uses the same one):
  D        = Vout / Vin
  Rds(Tj)  = Rds25 * (1 + alpha * (Tj - 25))
  P_cond   = Iout^2 * Rds(Tj)                 (both FETs together carry Iout)
  P_sw     = 0.5 * Vin * Iout * (tr + tf) * fsw
  P_gate   = 2 * Qg * Vgs * fsw
  P_fet    = P_cond + P_sw + P_gate
  dI       = Vout * (1 - D) / (L * fsw);  I_peak = Iout + dI / 2 <= Isat
  dV       = dI / (8 * C * fsw)
  P_L      = Iout^2 * DCR
  P_fan    = fan electrical power (0 without a fan)
  P_total  = P_fet + P_L + P_fan               (all dissipated inside the enclosure)
  Q        : fan static pressure(Q) = k * Q^2  (Q in m^3/h; 0 without a fan)
  Ta_int   = Ta_ext + P_total / (rho_cp_air * Q / 3600)   with a fan
           = Ta_ext + P_total * R_encl                     without a fan
  v        = Q / 3600 / A_duct
  Tj       = Ta_int + P_fet * (RthJC + RthCS + Rsa(v))
  eta      = Pout / (Pout + P_total)

Objective: minimize heat sink + fan + inductor price. A design passes only if it
meets every constraint AND its price is within task["objective"]["tolerance"] of
the brute-force optimum stored in task["objective"]["optimum"].

Sources: Kunzi, "Thermal Design of Power Electronic Circuits", CERN-2015-003 (CC BY 4.0);
TI SPRA953D package thermal metrics; Boyd board-level heat sink selection method;
fan-curve / system-curve operating point (ebm-papst application note).
"""
from __future__ import annotations

RHO_CP_AIR = 1206.0  # J/(m^3 K) at ~40 C


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


def _find(items, id_):
    return next(x for x in items if x["id"] == id_)


def evaluate(task: dict, design: dict) -> dict:
    """Full chain for one design. Raises StopIteration on unknown catalog ids."""
    p = task["params"]
    fsw = float(design["fsw_hz"])
    sink = _find(task["heatsinks"], design["heatsink"])
    ind = _find(task["inductors"], design["inductor"])
    fan = None if design.get("fan") in (None, "", "none") else _find(task["fans"], design["fan"])

    if fan:
        q = fan_operating_point([tuple(pt) for pt in fan["curve"]], p["k_system"])
        v = q / 3600.0 / p["duct_area_m2"]
        p_fan = fan["power_w"]
    else:
        q, v, p_fan = 0.0, 0.0, 0.0
    rsa = _interp([tuple(pt) for pt in sink["rsa_vs_v"]], v)

    d = p["vout"] / p["vin"]
    d_i = p["vout"] * (1 - d) / (ind["l_h"] * fsw)
    d_v = d_i / (8 * p["c_f"] * fsw)
    p_l = p["iout"] ** 2 * ind["dcr_ohm"]
    p_sw = 0.5 * p["vin"] * p["iout"] * p["tr_tf_s"] * fsw
    p_gate = 2 * p["qg_c"] * p["vgs"] * fsw

    tj = p["ta_ext"] + 30.0  # ponytail: fixed-point iteration; converges quickly for realistic alpha
    for _ in range(100):
        rds = p["rds25"] * (1 + p["alpha"] * (tj - 25))
        p_fet = p["iout"] ** 2 * rds + p_sw + p_gate
        p_total = p_fet + p_l + p_fan
        ta_int = p["ta_ext"] + (p_total / (RHO_CP_AIR * q / 3600.0) if fan else p_total * p["r_encl"])
        tj_new = ta_int + p_fet * (p["rth_jc"] + p["rth_cs"] + rsa)
        if abs(tj_new - tj) < 1e-7:
            tj = tj_new
            break
        tj = 0.5 * (tj + tj_new)  # damped for stability at high alpha
    pout = p["vout"] * p["iout"]
    return {
        "fsw_hz": fsw, "q_m3h": q, "v_ms": v, "rsa": rsa, "ta_int": ta_int, "p_fet": p_fet, "p_sw": p_sw,
        "p_l": p_l, "p_fan": p_fan, "p_total": p_total, "tj": tj, "eta": pout / (pout + p_total),
        "d_i": d_i, "d_v": d_v, "i_peak": p["iout"] + d_i / 2, "isat": ind["isat_a"],
        "cost": sink["price"] + ind["price"] + (fan["price"] if fan else 0.0),
        "noise_dba": fan["dba"] if fan else 0.0, "height_mm": sink["height_mm"],
    }


def grade(task: dict, output: dict) -> dict:
    p, lim = task["params"], task["limits"]
    design = {k: output.get(k) for k in ("fsw_hz", "heatsink", "fan", "inductor")}
    missing = [k for k in ("fsw_hz", "heatsink", "inductor") if design[k] in (None, "")]
    if missing:
        return {"passed": False, "violations": [f"missing fields: {missing}"]}
    try:
        design["fsw_hz"] = float(design["fsw_hz"])
    except (TypeError, ValueError):
        return {"passed": False, "violations": ["fsw_hz is not a number"]}
    for key, cat in (("heatsink", "heatsinks"), ("inductor", "inductors")):
        if not any(x["id"] == design[key] for x in task[cat]):
            return {"passed": False, "violations": [f"unknown {key} id '{design[key]}'"]}
    if design["fan"] not in (None, "", "none") and not any(f["id"] == design["fan"] for f in task["fans"]):
        return {"passed": False, "violations": [f"unknown fan id '{design['fan']}'"]}

    m = evaluate(task, design)
    v = []
    if not (p["fsw_min_hz"] <= m["fsw_hz"] <= p["fsw_max_hz"]):
        v.append(f"fsw {m['fsw_hz']:.0f} Hz outside controller range {p['fsw_min_hz']:.0f}-{p['fsw_max_hz']:.0f} Hz")
    if m["d_i"] > lim["ripple_i_max_a"] + 1e-9:
        v.append(f"inductor ripple {m['d_i']:.2f} A exceeds {lim['ripple_i_max_a']:.2f} A")
    if m["i_peak"] > m["isat"] + 1e-9:
        v.append(f"peak inductor current {m['i_peak']:.1f} A exceeds saturation {m['isat']:.1f} A")
    if m["d_v"] > lim["ripple_v_max_v"] + 1e-9:
        v.append(f"output ripple {m['d_v']*1e3:.1f} mV exceeds {lim['ripple_v_max_v']*1e3:.1f} mV")
    if m["tj"] > lim["tj_max_c"] + 1e-9:
        v.append(f"junction temperature {m['tj']:.1f} C exceeds {lim['tj_max_c']:.1f} C "
                 f"(P_fet={m['p_fet']:.2f} W, Ta_int={m['ta_int']:.1f} C, Rsa={m['rsa']:.2f} C/W, v={m['v_ms']:.2f} m/s)")
    if m["eta"] < lim["eta_min"] - 1e-9:
        v.append(f"efficiency {m['eta']*100:.2f}% below {lim['eta_min']*100:.2f}% "
                 f"(P_fet={m['p_fet']:.2f}, P_L={m['p_l']:.2f}, P_fan={m['p_fan']:.2f} W)")
    if m["noise_dba"] > lim["noise_max_dba"] + 1e-9:
        v.append(f"fan noise {m['noise_dba']:.0f} dBA exceeds {lim['noise_max_dba']:.0f} dBA")
    if m["height_mm"] > lim["height_max_mm"] + 1e-9:
        v.append(f"heatsink height {m['height_mm']:.0f} mm exceeds {lim['height_max_mm']:.0f} mm")
    if m["cost"] > lim["cost_max"] + 1e-9:
        v.append(f"cost {m['cost']:.2f} exceeds budget {lim['cost_max']:.2f}")
    obj = task.get("objective")  # {"minimize": "cost", "optimum": <brute-force best>, "tolerance": 0.05}
    if obj and not v and m["cost"] > obj["optimum"] * (1 + obj["tolerance"]) + 1e-9:
        # ponytail: the optimum is not echoed back, so agentic feedback says "search harder", not "the answer is X"
        v.append(f"cost {m['cost']:.2f} is not within {obj['tolerance']*100:.0f}% of the cheapest design that meets every constraint")
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
