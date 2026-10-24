"""Generate bess tasks: perturbed requirements, site, cell and catalogs; brute-forced optimum; derived broken cases.

    python taskgen/bess.py --seeds 1 2 3

The optimizer decomposes the design: for every (N_s, N_p, PCS, PCS count) it computes the string
quantities once, then picks the cheapest fuse + contactor + cable, cooling and transformer that
satisfy the named rules. The golden is re-verified with solvers/bess.grade, so any drift between
this file and the grader shows up in the self-check.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
import bess  # noqa: E402

MODULE = 16  # cells in series per module; N_s is a multiple of this
NS_RANGE = range(MODULE * 12, MODULE * 30 + 1, MODULE)  # 192 .. 480 cells
NP_MAX = 40
PCS_COUNT_MAX = 8
COOL_COUNT_MAX = 12
CABLE_PAR_MAX = 3
TOLERANCE = 0.05
MAX_FEASIBLE_FRACTION = 0.10  # of the (N_s, N_p, PCS, count) grid; feasibility is not the hard part here
MAX_NEAR_OPT_GRID_FRACTION = 0.005  # near-optimal designs as a share of the grid: the real difficulty measure

# Archetypes; every number is perturbed per seed. Values are plausible catalog figures, not any vendor's.
PCS = [  # id, kVA at 25/40/50 C, Vdc min/max, Idc max, DC inputs, eta, short-circuit contribution kA, price
    ("PCS-1", 1000, 900, 800, 900, 1500, 1200, 6, 0.982, 1.6, 95_000),
    ("PCS-2", 1800, 1650, 1450, 1000, 1500, 2000, 8, 0.985, 2.2, 150_000),
    ("PCS-3", 2500, 2300, 2050, 1100, 1500, 2600, 12, 0.986, 2.8, 205_000),
    ("PCS-4", 3600, 3300, 2950, 1200, 1500, 3400, 16, 0.987, 3.5, 280_000),
    ("PCS-5", 4400, 4000, 3600, 1300, 1500, 3800, 16, 0.988, 4.0, 340_000),
]
TX = [  # id, kVA, u_k, eta, price
    ("TX-1", 1000, 0.06, 0.990, 28_000), ("TX-2", 1600, 0.06, 0.991, 38_000), ("TX-3", 2500, 0.06, 0.992, 52_000),
    ("TX-4", 3150, 0.07, 0.992, 62_000), ("TX-5", 4000, 0.07, 0.993, 76_000), ("TX-6", 5000, 0.08, 0.993, 92_000),
    ("TX-7", 6300, 0.08, 0.994, 112_000),
]
FUSES = [  # id, class, I_n, U_dc, tau_ms, breaking kA, price
    ("FU-1", "gG", 250, 440, 0, 50, 18), ("FU-2", "gG", 400, 440, 0, 50, 24),
    ("FU-3", "gBat", 250, 1000, 3, 100, 65), ("FU-4", "gBat", 315, 1500, 3, 100, 88),
    ("FU-5", "gBat", 400, 1500, 3, 150, 96), ("FU-6", "gBat", 500, 1500, 3, 150, 118),
    ("FU-7", "gBat", 630, 1500, 3, 200, 142), ("FU-8", "gBat", 800, 1500, 3, 200, 175),
    ("FU-9", "aBat", 400, 1500, 10, 200, 70), ("FU-10", "gBat", 400, 1500, 10, 200, 130),
    ("FU-11", "gBat", 500, 1500, 3, 260, 165), ("FU-12", "gBat", 630, 1500, 3, 260, 190),
    ("FU-13", "gBat", 250, 1500, 3, 200, 120), ("FU-14", "gBat", 315, 1500, 3, 260, 150),
]
FUSE_K_AMB = {"25": 1.0, "40": 0.9, "50": 0.8}
CONTACTORS = [  # id, I_rated, U_dc, max breaking A, price
    ("CT-1", 250, 1000, 1500, 140), ("CT-2", 300, 1500, 2000, 210), ("CT-3", 400, 1500, 2500, 260),
    ("CT-4", 500, 1500, 3000, 330), ("CT-5", 600, 1500, 4000, 420), ("CT-6", 800, 1500, 6000, 560),
]
CABLES = [  # id, mm2, I_z base (2 loaded conductors, method E, 30 C, XLPE), R ohm/km at 70 C, U_dc, price/m
    ("C-50", 50, 234, 0.462, 1800, 9.5), ("C-70", 70, 297, 0.321, 1800, 13.0), ("C-95", 95, 362, 0.232, 1800, 17.5),
    ("C-120", 120, 419, 0.184, 1800, 22.0), ("C-150", 150, 480, 0.150, 1800, 27.0), ("C-185", 185, 550, 0.121, 1800, 33.0),
    ("C-240", 240, 649, 0.0925, 1800, 43.0), ("C-300", 300, 741, 0.0745, 1800, 54.0),
]
COOLING = [  # id, kW thermal at 35 / 45 C ambient, price
    ("CU-1", 20, 16, 9_000), ("CU-2", 40, 33, 16_000), ("CU-3", 80, 66, 29_000), ("CU-4", 150, 125, 52_000),
]
K_TEMP = {"30": 1.0, "35": 0.96, "40": 0.91, "45": 0.87, "50": 0.82, "55": 0.76}  # XLPE 90 C, air, 30 C base
K_GROUP = {"1": 1.0, "2": 0.88, "3": 0.82, "4": 0.77, "6": 0.72, "9": 0.70, "12": 0.68, "16": 0.66, "20": 0.64}
K_TX_AMBIENT = {"-20": 1.24, "-10": 1.18, "0": 1.12, "10": 1.06, "20": 1.0, "30": 0.93}  # IEC 60076-11 annual mean, dry type


def _r(rng, lo, hi, nd=3):
    return round(rng.uniform(lo, hi), nd)


def _pert(rng, x, lo=0.9, hi=1.1, nd=0):
    return round(x * rng.uniform(lo, hi), nd) if nd else int(round(x * rng.uniform(lo, hi)))


def make_task(seed: int) -> dict | None:
    rng = random.Random(seed)
    duration_h = rng.choice([1, 2, 2, 4])
    p_req = rng.choice([1.0, 1.5, 2.0, 2.5, 3.0, 4.0])
    params = {
        "e_req_mwh": round(p_req * duration_h, 2), "p_req_mw": p_req, "duration_h": duration_h,
        "service_years": rng.choice([10, 15]), "soh_eol": 0.80,
        "margin_e": rng.choice([0.10, 0.15]), "margin_p": rng.choice([0.10, 0.15]), "milestone": "CDR",
        "eta_dc": _r(rng, 0.95, 0.975, 3), "cos_phi_min": 0.95, "k_load_fuse": 0.8,
        "v_drop_max": rng.choice([0.015, 0.02, 0.03]), "module_cells": MODULE,
    }
    cell = {
        "chemistry": "LFP prismatic", "v_nom": 3.2, "v_min": 2.5, "v_max": 3.65,
        "q_ah": float(rng.choice([280, 280, 300, 306, 314])), "r_bol_ohm": _r(rng, 0.00040, 0.00070, 6),
        "k_r_eol": _r(rng, 1.5, 2.0, 2), "c_cont": rng.choice([0.5, 0.5, 1.0]), "soc_min": rng.choice([0.05, 0.10]),
        "soc_max": rng.choice([0.90, 0.95]), "v_ocv_soc_min": _r(rng, 3.04, 3.16, 2), "t_max_c": 55.0, "price": _pert(rng, 75, 0.85, 1.15, 2),
    }
    site = {
        "t_max_c": float(rng.choice([35, 40, 45])), "t_annual_mean_c": float(rng.choice([8, 10, 12, 15, 20])),
        "altitude_m": rng.choice([200, 500, 800]), "t_cable_c": float(rng.choice([35, 40, 45, 50])),
        "dc_route_m": rng.choice([25, 40, 60, 80]), "strings_per_tray": rng.choice([4, 6, 8]),
        "circuit_tau_ms": rng.choice([1, 2, 3, 5]), "grid_kv": rng.choice([10, 20, 30]),
    }
    pcs_cat = [{"id": i, "s_kva_25": _pert(rng, a), "s_kva_40": _pert(rng, b), "s_kva_50": _pert(rng, c),
                "v_dc_min": vmin, "v_dc_max": vmax, "i_dc_max": _pert(rng, idc), "dc_inputs": n, "eta": eta,
                "i_sc_ka": round(isc * rng.uniform(0.9, 1.1), 2), "price": _pert(rng, pr, 0.85, 1.15)}
               for i, a, b, c, vmin, vmax, idc, n, eta, isc, pr in PCS]
    for x in pcs_cat:  # keep the derating monotonic after perturbation
        x["s_kva_40"] = min(x["s_kva_40"], x["s_kva_25"]); x["s_kva_50"] = min(x["s_kva_50"], x["s_kva_40"])
    tx_cat = [{"id": i, "s_kva": kva, "u_k": uk, "eta": eta, "price": _pert(rng, pr, 0.85, 1.15)} for i, kva, uk, eta, pr in TX]
    fuses = [{"id": i, "class": cl, "i_n": i_n, "u_dc": u, "tau_ms": tau, "breaking_ka": ka, "k_amb": FUSE_K_AMB,
              "price": _pert(rng, pr, 0.85, 1.15, 2)} for i, cl, i_n, u, tau, ka, pr in FUSES]
    contactors = [{"id": i, "i_rated": ir, "u_dc": u, "i_break_max": ib, "price": _pert(rng, pr, 0.85, 1.15, 2)}
                  for i, ir, u, ib, pr in CONTACTORS]
    cables = [{"id": i, "mm2": mm, "i_z_base": iz, "r_ohm_per_km": r, "u_dc": u, "price_per_m": _pert(rng, pr, 0.85, 1.15, 2)}
              for i, mm, iz, r, u, pr in CABLES]
    cooling = [{"id": i, "kw_35": a, "kw_45": b, "price": _pert(rng, pr, 0.85, 1.15)} for i, a, b, pr in COOLING]
    task = {"id": f"bess_{seed:03d}", "domain": "bess", "mode": "named", "params": params, "cell": cell, "site": site,
            "pcs_catalog": pcs_cat, "transformers": tx_cat, "fuses": fuses, "contactors": contactors, "cables": cables,
            "cooling_units": cooling, "k_temp": K_TEMP, "k_group": K_GROUP, "k_tx_ambient": K_TX_AMBIENT}

    best, feasible, grid = _optimize(task)
    if best is None:
        return None
    n_feasible = len(feasible)
    if n_feasible / grid > MAX_FEASIBLE_FRACTION:
        return None
    task["objective"] = {"minimize": "cost", "optimum": round(best[0], 2), "tolerance": TOLERANCE}
    near_opt = sum(1 for c, _ in feasible if c <= best[0] * (1 + TOLERANCE))
    if near_opt / grid > MAX_NEAR_OPT_GRID_FRACTION:
        return None
    golden = best[1]
    r = bess.grade(task, golden)
    if not r["passed"]:
        raise RuntimeError(f"seed {seed}: optimizer golden fails the grader: {r['violations']}")

    broken = [b for b in _broken_candidates(task, golden, feasible) if not bess.grade(task, b["output"])["passed"]]
    for b in broken:
        b["expect"] = bess.grade(task, b["output"])["violations"][0].split(" ")[0]
    if len(broken) < 3:
        return None
    task["_golden"], task["_broken"] = golden, broken
    task["_stats"] = {"feasible": n_feasible, "near_opt": near_opt, "grid": grid}
    return task


def _optimize(task):
    """Cheapest design over the decomposed space. Returns (best (cost, design), feasible [(cost, design)], grid size).

    Calls the grader's own physics (operating point, grid side, heating, MV fault) so the two cannot drift;
    level-3 features switch on from the task data exactly as in the grader."""
    p, c, s = task["params"], task["cell"], task["site"]
    soh, _ = bess.life(task)
    k_t = bess._interp(bess._table(task["k_temp"]), s["t_cable_c"])
    k_amb_tx = bess._interp(bess._table(task["k_tx_ambient"]), s["t_annual_mean_c"])
    u_min = task.get("grid", {}).get("u_min_pu", 1.0)
    e_req = p["e_req_mwh"] * 1e6 * (1 + p["margin_e"])
    txs = sorted(task["transformers"], key=lambda t: t["price"])
    cool_at_site = {cu["id"]: bess._interp([(35.0, cu["kw_35"]), (45.0, cu["kw_45"])], s["t_max_c"]) * 1e3 for cu in task["cooling_units"]}
    fuse_k = {f["id"]: bess._interp(bess._table(f["k_amb"]), s["t_max_c"]) for f in task["fuses"]}
    s_nap = bess.grid_side(task, 0.0, txs[0])[0]
    op_cache = {}

    feasible, best, grid = [], None, 0
    for pcs in task["pcs_catalog"]:
        s_site = bess._interp([(25.0, pcs["s_kva_25"]), (40.0, pcs["s_kva_40"]), (50.0, pcs["s_kva_50"])], s["t_max_c"]) * 1e3 * u_min
        for n_pcs in range(1, PCS_COUNT_MAX + 1):
            sw = (None, 0.0)
            if "mv_switchgear" in task:
                i_k, i_p, i_nap = bess.mv_fault(task, pcs, n_pcs, s_nap)
                sw = min(((x["id"], x["price"]) for x in task["mv_switchgear"]
                          if x["u_r_kv"] >= task["grid"]["u_max_kv"] and x["i_k_ka"] * 1e3 >= i_k
                          and x["i_ma_ka"] * 1e3 >= i_p and x["i_r_a"] >= i_nap), key=lambda t: t[1], default=None)
            for ns in NS_RANGE:
                v_max = ns * c["v_max"]
                if v_max > pcs["v_dc_max"]:
                    continue
                for np_ in range(1, NP_MAX + 1):
                    grid += 1
                    if sw is None or np_ > pcs["dc_inputs"] * n_pcs:
                        continue
                    key = (pcs["id"], ns, np_)
                    if key not in op_cache:
                        op_cache[key] = bess.operating_point(task, ns, np_, pcs)
                    p_ac, p_aux, v_load, i_s, q_heat = op_cache[key]
                    if i_s > c["c_cont"] * c["q_ah"] or v_load < pcs["v_dc_min"] or np_ * i_s > pcs["i_dc_max"] * n_pcs:
                        continue
                    e_cells = ns * np_ * c["v_nom"] * c["q_ah"] * (c["soc_max"] - c["soc_min"]) * soh * p["eta_dc"] * pcs["eta"]
                    tx = next((t for t in txs  # cheapest transformer that carries the flow, lets the PCS cover Q, and meets energy
                               if t["s_kva"] * 1e3 * k_amb_tx >= bess.grid_side(task, p_ac, t)[2]
                               and s_site * n_pcs >= bess.grid_side(task, p_ac, t)[4]
                               and e_cells * t["eta"] - p_aux * p["duration_h"] >= e_req), None)
                    if tx is None:
                        continue
                    # cooling (and heating, when the site has a winter): cheapest unit x count
                    _, heat_need = bess.heating_needed(task, np_, i_s)
                    cool = None
                    for cu in task["cooling_units"]:
                        n_c = math.ceil(q_heat * (1 + p["margin_p"]) / cool_at_site[cu["id"]] - 1e-9)
                        if heat_need > 0:
                            n_c = max(n_c, math.ceil(heat_need / (cu["heating_kw"] * 1e3) - 1e-9))
                        n_c = max(1, n_c)
                        if n_c <= COOL_COUNT_MAX and (cool is None or cu["price"] * n_c < cool[0]):
                            cool = (cu["price"] * n_c, cu["id"], n_c)
                    if cool is None:
                        continue
                    # fuse + contactor + cable: joint search
                    r_b = ns * c["r_bol_ohm"]
                    sub = None
                    for fu in task["fuses"]:
                        if fu["class"] != "gBat" or fu["u_dc"] < v_max or fu["tau_ms"] < s["circuit_tau_ms"]:
                            continue
                        if fu["i_n"] < i_s / (fuse_k[fu["id"]] * p["k_load_fuse"]):
                            continue
                        ct = min(((x["price"], x["id"]) for x in task["contactors"]
                                  if x["i_rated"] >= i_s and x["u_dc"] >= v_max and x["i_break_max"] >= 2 * fu["i_n"]), default=None)
                        if ct is None:
                            continue
                        for cb in task["cables"]:
                            if cb["u_dc"] < v_max:
                                continue
                            for n_cab in range(1, CABLE_PAR_MAX + 1):
                                k_g = bess._interp(bess._table(task["k_group"]), s["strings_per_tray"] * n_cab)
                                i_z = n_cab * cb["i_z_base"] * k_t * k_g
                                if fu["i_n"] > i_z or 1.6 * fu["i_n"] > 1.45 * i_z:
                                    continue
                                r_cable = cb["r_ohm_per_km"] * s["dc_route_m"] / 1000.0 * 2 / n_cab
                                if i_s * r_cable / v_load > p["v_drop_max"]:
                                    continue
                                i_k = 0.95 * v_max / (r_b + r_cable)  # 0.9 R_b + R_cable + 0.1 R_b
                                if fu["breaking_ka"] * 1e3 < (np_ - 1) * i_k + pcs["i_sc_ka"] * 1e3 * n_pcs:
                                    continue
                                price = np_ * (fu["price"] + ct[0]) + np_ * n_cab * 2 * s["dc_route_m"] * cb["price_per_m"]
                                if sub is None or price < sub[0]:
                                    sub = (price, fu["id"], ct[1], cb["id"], n_cab)
                    if sub is None:
                        continue
                    cost = ns * np_ * c["price"] + n_pcs * pcs["price"] + tx["price"] + sub[0] + cool[0] + sw[1]
                    design = {"cells_series": ns, "strings_parallel": np_, "pcs": pcs["id"], "pcs_count": n_pcs,
                              "transformer": tx["id"], "string_fuse": sub[1], "string_contactor": sub[2], "dc_cable": sub[3],
                              "dc_cables_parallel": sub[4], "cooling_unit": cool[1], "cooling_count": cool[2]}
                    if sw[0]:
                        design["mv_switchgear"] = sw[0]
                    feasible.append((cost, design))
                    if best is None or cost < best[0]:
                        best = (cost, design)
    return best, feasible, grid


def _broken_candidates(task, g, feasible):
    """Each candidate is the golden with one classic mistake applied. Only those the grader fails are kept."""
    p, c, s = task["params"], task["cell"], task["site"]
    m = bess.evaluate(task, g)
    i_s, v_max = m["i_string_a"], m["v_string_max"]
    pcs = bess._find(task["pcs_catalog"], g["pcs"])
    out = []

    def add(note, **kw):
        cand = {**g, **kw}
        if cand != g:
            out.append({"output": cand, "note": note})

    # nameplate sizing: strings from 100 % SOH, no efficiency chain
    np_nameplate = math.ceil(p["e_req_mwh"] * 1e6 * (1 + p["margin_e"]) / (g["cells_series"] * c["v_nom"] * c["q_ah"] * (c["soc_max"] - c["soc_min"])))
    add("nameplate sizing (100 % SOH, no losses)", strings_parallel=max(1, np_nameplate))
    # series count from nominal voltage against the PCS minimum
    ns_nominal = math.ceil(pcs["v_dc_min"] / c["v_nom"] / MODULE) * MODULE
    add("series count from nominal voltage", cells_series=ns_nominal)
    ns_cutoff = math.ceil(pcs["v_dc_min"] / c["v_min"] / MODULE) * MODULE
    add("series count from the 2.5 V protection cutoff", cells_series=ns_cutoff)
    # PCS count from the 25 C rating
    n25 = math.ceil(m["s_pcs_needed_kva"] / pcs["s_kva_25"])
    add("PCS count from the 25 C rating", pcs_count=max(1, n25))
    # fuse at the string current, no derating; cheapest that fits voltage
    fu = min((f for f in task["fuses"] if f["i_n"] >= i_s and f["u_dc"] >= v_max), key=lambda f: f["price"], default=None)
    if fu:
        add("fuse at string current without derating", string_fuse=fu["id"])
    # cheapest fuse by current only, ignoring class and DC voltage
    fu = min((f for f in task["fuses"] if f["i_n"] >= i_s), key=lambda f: f["price"], default=None)
    if fu:
        add("AC fuse in a DC string", string_fuse=fu["id"])
    # contactor at load current only
    ct = min((x for x in task["contactors"] if x["i_rated"] >= i_s and x["u_dc"] >= v_max), key=lambda x: x["price"], default=None)
    if ct:
        add("contactor sized to load current only", string_contactor=ct["id"])
    # cable without grouping / temperature correction
    fu_g = bess._find(task["fuses"], g["string_fuse"])
    cb = min(((x, n) for x in task["cables"] for n in range(1, CABLE_PAR_MAX + 1) if n * x["i_z_base"] >= fu_g["i_n"]),
             key=lambda t: t[1] * t[0]["price_per_m"], default=None)
    if cb:
        add("cable ampacity without correction factors", dc_cable=cb[0]["id"], dc_cables_parallel=cb[1])
    # transformer at kW
    tx = min((t for t in task["transformers"] if t["s_kva"] * 1e3 >= m["p_ac_mw"] * 1e6), key=lambda t: t["price"], default=None)
    if tx:
        add("transformer sized to kW", transformer=tx["id"])
    # cooling at beginning-of-life resistance
    cu = bess._find(task["cooling_units"], g["cooling_unit"])
    cap = bess._interp([(35.0, cu["kw_35"]), (45.0, cu["kw_45"])], s["t_max_c"]) * 1e3
    n_bol = math.ceil(m["q_heat_kw"] * 1e3 / c["k_r_eol"] * (1 + p["margin_p"]) / cap)
    add("cooling sized at beginning-of-life resistance", cooling_count=max(1, n_bol))
    # feasible but most expensive
    worst = max(feasible, key=lambda t: t[0])[1]
    if worst != g:
        out.append({"output": worst, "note": "feasible but most expensive"})
    return out


def _cat(rows, fmt):
    return "\n".join("  " + fmt(r) for r in rows)


def describe(t: dict) -> str:
    p, c, s = t["params"], t["cell"], t["site"]
    k = lambda d: ", ".join(f"{a} C: {b}" for a, b in d.items())  # noqa: E731
    return (
        f"Design a grid-connected lithium iron phosphate battery energy storage system for a site in Germany. "
        f"Requirements at the point of connection to the {s['grid_kv']} kV network: usable energy {p['e_req_mwh']:g} MWh "
        f"and rated power {p['p_req_mw']:g} MW (charge and discharge, {p['duration_h']} h duration) over a service life of "
        f"{p['service_years']} years. Apply the NASA Systems Engineering Handbook technical margin policy at {p['milestone']}: "
        f"{p['margin_e']*100:.0f}% on energy and {p['margin_p']*100:.0f}% on power. End of life is {p['soh_eol']*100:.0f}% state of health. "
        f"Usable energy follows the PNNL ESGC 2022 definitions (SOC window, state of health, and the DC, PCS and transformer "
        f"efficiencies between cells and the point of connection; DC-side one-way efficiency {p['eta_dc']}).\n\n"
        f"Architecture: one string per rack; every string connects to its own DC input on a PCS unit (no combiner boxes; a PCS "
        f"unit's inputs share one DC bus, and the PCS units are paralleled on the AC side); cells in series in modules of "
        f"{p['module_cells']} (the series count is a multiple of {p['module_cells']}). Each string has one fuse and one contactor and "
        f"runs to the PCS over one DC cable pair (optionally several pairs in parallel) of {s['dc_route_m']} m route length, "
        f"with {s['strings_per_tray']} strings sharing each cable tray. DC circuit time constant L/R {s['circuit_tau_ms']} ms. "
        f"DC cable voltage drop limit {p['v_drop_max']*100:g}%.\n\n"
        f"Site: maximum ambient {s['t_max_c']:g} C, annual mean {s['t_annual_mean_c']:g} C, altitude {s['altitude_m']} m; "
        f"cable ambient inside the enclosure {s['t_cable_c']:g} C.\n\n"
        f"Cell ({c['chemistry']}): {c['v_nom']} V nominal, {c['q_ah']:g} Ah, {c['v_min']}-{c['v_max']} V, DC resistance "
        f"{c['r_bol_ohm']*1e3:.2f} mOhm at beginning of life growing by a factor {c['k_r_eol']} at end of life, continuous "
        f"{c['c_cont']:g} C charge and discharge, operating SOC window {c['soc_min']*100:.0f}-{c['soc_max']*100:.0f}%, "
        f"open-circuit voltage {c['v_ocv_soc_min']} V at {c['soc_min']*100:.0f}% SOC, "
        f"maximum cell temperature {c['t_max_c']:g} C, price {c['price']:.2f} per cell.\n\n"
        f"Design rules to apply, by name: string voltage window against the PCS DC window at end of life; PCS output at site "
        f"ambient per the catalog columns; cooling at site ambient; string fuse selection per IEC 60269-7 (battery fuse class, "
        f"DC voltage rating at the circuit time constant, ambient factor from the catalog, continuous-load factor "
        f"{p['k_load_fuse']}, breaking capacity against the prospective fault current at the DC bus per IEC 61660-1 with the PCS "
        f"contribution from the catalog); contactor coordination with the fuse (no interruption gap); DC cable "
        f"current-carrying capacity per DIN VDE 0298-4 with the temperature and grouping factors below and overload "
        f"coordination per IEC 60364-4-43 (DIN VDE 0100-430); reactive power capability at the point of connection per "
        f"VDE-AR-N 4110 (cos phi {p['cos_phi_min']} under- and over-excited) including the transformer's own reactive "
        f"consumption from its short-circuit impedance; transformer rating per IEC 60076-11 with the annual-mean ambient "
        f"factors below.\n\n"
        f"PCS catalog (id: kVA at 25 / 40 / 50 C, DC window V, max DC current A, DC inputs, efficiency, DC short-circuit "
        f"contribution kA, price):\n"
        + _cat(t["pcs_catalog"], lambda x: f"{x['id']}: {x['s_kva_25']} / {x['s_kva_40']} / {x['s_kva_50']} kVA, {x['v_dc_min']}-{x['v_dc_max']} V, "
                                           f"{x['i_dc_max']} A, {x['dc_inputs']} inputs, {x['eta']}, {x['i_sc_ka']} kA, {x['price']}")
        + "\n\nTransformers (id: kVA, u_k, efficiency, price):\n"
        + _cat(t["transformers"], lambda x: f"{x['id']}: {x['s_kva']} kVA, u_k {x['u_k']}, {x['eta']}, {x['price']}")
        + "\n\nFuses (id: class, I_n A, rated DC voltage V, rated time constant ms, breaking capacity kA, price; "
        f"ambient factor {k(FUSE_K_AMB)}):\n"
        + _cat(t["fuses"], lambda x: f"{x['id']}: {x['class']}, {x['i_n']} A, {x['u_dc']} V DC, {x['tau_ms']} ms, {x['breaking_ka']} kA, {x['price']:.2f}")
        + "\n\nContactors (id: rated current A, rated DC voltage V, maximum breaking current A, price):\n"
        + _cat(t["contactors"], lambda x: f"{x['id']}: {x['i_rated']} A, {x['u_dc']} V DC, {x['i_break_max']} A, {x['price']:.2f}")
        + "\n\nDC cables, copper, XLPE 90 C (id: mm2, base current-carrying capacity A for two loaded conductors in free air at "
        f"30 C, resistance ohm/km at 70 C, rated DC voltage V, price per metre per conductor):\n"
        + _cat(t["cables"], lambda x: f"{x['id']}: {x['mm2']} mm2, {x['i_z_base']} A, {x['r_ohm_per_km']} ohm/km, {x['u_dc']} V DC, {x['price_per_m']:.2f}")
        + f"\n  Ambient correction factors ({k(t['k_temp'])}); grouping factors by number of circuits in the tray "
        f"({', '.join(f'{a}: {b}' for a, b in t['k_group'].items())}).\n\n"
        f"Cooling units (id: kW thermal at 35 / 45 C ambient, price):\n"
        + _cat(t["cooling_units"], lambda x: f"{x['id']}: {x['kw_35']} / {x['kw_45']} kW, {x['price']}")
        + f"\n\nTransformer annual-mean ambient factors ({k(t['k_tx_ambient'])}).\n\n"
        f"Objective: minimize total price (cells + PCS + transformer + fuses + contactors + cables + cooling). A design passes "
        f"only if it meets every requirement above AND its price is within {t['objective']['tolerance']*100:.0f}% of the "
        f"cheapest design that does. Return " + OUTPUT_SHAPE
    )


OUTPUT_SHAPE = ('{"cells_series": <int>, "strings_parallel": <int>, "pcs": "<id>", "pcs_count": <int>, "transformer": "<id>", '
                '"string_fuse": "<id>", "string_contactor": "<id>", "dc_cable": "<id>", "dc_cables_parallel": <int>, '
                '"cooling_unit": "<id>", "cooling_count": <int>}')
SOURCES = [
    "PNNL-33283 ESGC Cost and Performance Assessment 2022 (DOE lab report): usable energy, RTE and end-of-life definitions",
    "NASA/SP-2016-6105-SUPPL Expanded Guidance for NASA SE, sec. 7.8 (public domain): technical margin policy by milestone",
    "IEC 60269-7 battery fuses as described in SIBA, Mersen and ETI battery-fuse catalogs: gBat/aBat, DC rating at time constant, ambient factors, breaking capacity",
    "IEC 61660-1 DC short-circuit method as described in ABB 1SDC007104G0201 Annex B: battery branch peak and quasi-steady current",
    "DIN VDE 0298-4 / IEC 60364-5-52 current-carrying capacity and IEC 60364-4-43 overload coordination as reproduced in ABB 2CDC401002D0106 and Mersen EduPack TM-104",
    "Eaton 'Five factors' OCPD note: fuse and contactor interruption coordination (no gap)",
    "VDE-AR-N 4110 reactive power requirement at the connection point as stated in TEN / Nordhausen Netz TAR-MS guidelines and VDE FNN Hinweis Speicher",
    "IEC 60076-11 dry-type transformer rated conditions and annual-mean ambient factors as stated in Siemens GEAFOL planning notes",
    "NREL/PR-5400-66960 Pesaran, Battery Pack Thermal Design: lumped heat balance",
    "Cell values patterned on public 280-314 Ah LFP prismatic datasheets (EVE LF280K and peers); every value perturbed per seed",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    args = ap.parse_args()
    sol_path = ROOT / "solvers" / "solutions.json"
    solutions = json.loads(sol_path.read_text())
    made = 0
    for seed in args.seeds:
        t = make_task(seed)
        if t is None:
            print(f"seed {seed}: skipped (infeasible or trivial)")
            continue
        golden, broken, stats = t.pop("_golden"), t.pop("_broken"), t.pop("_stats")
        t.update({"title": "Grid-connected LFP battery storage system", "description": describe(t),
                  "output_shape": OUTPUT_SHAPE, "sources": SOURCES, "seed": seed,
                  "disciplines": ["electrical", "electronics", "thermal", "systems"]})
        (ROOT / "tasks" / f"{t['id']}.json").write_text(json.dumps(t, indent=2) + "\n")
        solutions[t["id"]] = {"golden": golden, "broken": [{"output": b["output"], "expect": b["expect"]} for b in broken]}
        made += 1
        print(f"{t['id']}: feasible {stats['feasible']}/{stats['grid']} ({100*stats['feasible']/stats['grid']:.2f}%), "
              f"near-optimal {stats['near_opt']}, optimum {t['objective']['optimum']:,.0f}, golden {golden}, "
              f"{len(broken)} broken: {[b['note'] for b in broken]}")
    sol_path.write_text(json.dumps(solutions, indent=1) + "\n")
    print(f"{made} tasks written")


if __name__ == "__main__":
    main()
