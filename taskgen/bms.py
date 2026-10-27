"""Generate bms4 tasks: a level-3 plant handed over, the BMS and DC protection to design around it.

    python taskgen/bms.py --seeds 1 2 3 [--private]

The plant is the level-3 optimum of the same draft plus one rack (the system team's allowance for
measurement error). Catalogs are synthetic, datasheet-shaped and perturbed per seed. The optimizer
brute-forces the BMS design with the grader's own physics; a seed is kept only when at least three
hidden requirements bind (the optimum without each one fails the real grader). Spec: docs/families/bms4.md.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
import bess  # noqa: E402
import bms  # noqa: E402

_spec = importlib.util.spec_from_file_location("bessgen", ROOT / "taskgen" / "bess.py")
bessgen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bessgen)

TOLERANCE = 0.05
MIN_HIDDEN_BINDING = 4
CHAINS_MAX = 4

# Archetypes; every number is perturbed per seed. Plausible datasheet figures, not any vendor's.
AFES = [  # id, cell channels, error mV at 25 C, error mV over -40..105 C, conversion ms, readout ms per chip, max chain, temp inputs, internal balancing mA, price
    ("AFE-1", 12, 2.0, 6.0, 1.5, 0.6, 32, 6, 60, 7.0), ("AFE-2", 14, 1.2, 4.5, 2.0, 0.8, 24, 8, 100, 10.0),
    ("AFE-3", 16, 1.5, 3.5, 2.5, 1.0, 20, 8, 150, 13.0), ("AFE-4", 18, 0.8, 2.2, 3.0, 1.2, 16, 9, 200, 17.0),
    ("AFE-5", 16, 1.0, 1.5, 1.5, 0.5, 40, 10, 300, 24.0),
]
SENSORS = [  # id, type, range A, residual offset A, gain error %, 24 V power W, price
    ("CS-1", "shunt + isolated amplifier", 1500, 0.04, 0.3, 1.2, 75), ("CS-2", "shunt + isolated amplifier", 3000, 0.08, 0.3, 1.2, 95),
    ("CS-3", "shunt + isolated amplifier", 6000, 0.16, 0.3, 1.2, 130), ("CS-4", "open-loop Hall", 1500, 0.6, 1.0, 0.6, 25),
    ("CS-5", "open-loop Hall", 3000, 1.2, 1.0, 0.6, 32), ("CS-6", "open-loop Hall", 6000, 2.4, 1.0, 0.6, 45),
    ("CS-7", "closed-loop Hall", 1500, 0.12, 0.3, 2.5, 110), ("CS-8", "closed-loop Hall", 3000, 0.25, 0.3, 4.5, 160),
    ("CS-9", "dual-channel Hall, 500 A fine channel", 3000, 0.15, 0.5, 0.8, 60),
    ("CS-10", "dual-channel Hall, 500 A fine channel", 6000, 0.15, 0.5, 0.8, 75),
    ("CS-11", "fluxgate", 1500, 0.012, 0.05, 3.0, 300), ("CS-12", "fluxgate", 3000, 0.025, 0.05, 5.0, 420),
]
CONTACTORS = [  # id, rated A, DC V, breaking A at 1500 V DC, opening ms, coil hold W (economized), price
    ("K-1", 250, 1500, 1500, 25, 4, 150), ("K-2", 400, 1500, 3000, 30, 6, 210), ("K-3", 500, 1500, 4000, 35, 8, 290),
    ("K-4", 630, 1500, 5000, 40, 10, 380), ("K-5", 400, 1500, 6000, 20, 7, 520), ("K-6", 800, 1500, 8000, 50, 14, 600),
]
MCUS = [  # id, daisy-chain ports, CAN ports, ADC channels, control cycle ms, board W, price
    ("MCU-1", 1, 2, 8, 10, 2.5, 6.0), ("MCU-2", 2, 2, 16, 10, 3.0, 9.0), ("MCU-3", 2, 3, 24, 5, 4.0, 14.0),
    ("MCU-4", 4, 3, 32, 5, 5.0, 22.0),
]
HOLD_UPS = [("HB-1", 20, 15.0), ("HB-2", 50, 25.0), ("HB-3", 100, 40.0), ("HB-4", 250, 70.0)]  # id, usable J, price per rack
IMDS = [("IMD-1", 50, 2.0, 280.0), ("IMD-2", 150, 2.0, 420.0), ("IMD-3", 500, 3.0, 650.0),  # id, max system uF, W, price
        ("IMD-4", 1000, 3.0, 980.0), ("IMD-5", 3000, 4.0, 1600.0)]
RESISTOR_OHMS = (10, 15, 22, 33, 47, 68, 100, 150, 220)
RESISTOR_KJ = {3: 9.0, 8: 16.0, 20: 30.0, 50: 62.0, 100: 110.0}  # single-pulse energy class kJ -> price
BALANCING = [("BAL-1", 200, 18.0), ("BAL-2", 500, 30.0), ("BAL-3", 1000, 48.0)]  # id, mA, price per module
OCV = {0: 2.95, 5: 3.17, 10: 3.21, 20: 3.25, 30: 3.275, 40: 3.285, 50: 3.29, 60: 3.295, 70: 3.315, 80: 3.33,
       85: 3.333, 90: 3.334, 95: 3.345, 100: 3.40}  # LFP shape: flat plateau, steep ends
PULSE_LIMIT = {2: 60, 3: 10, 5: 2, 10: 0.2, 20: 0.02, 50: 0.002}  # cell short-time current, C multiple -> s
FUSE_CURVE = {1.6: 3600, 2: 300, 3: 30, 4: 6, 5: 1.5, 7: 0.25, 10: 0.04, 15: 0.008, 20: 0.003}  # gBat pre-arc, x I_n -> s
HIDDEN = {  # naive flag -> the mistake a team makes when it does not anticipate the requirement
    "soc": "SOC accuracy not budgeted against the energy margin",
    "recal": "SOC drift budgeted for a daily recalibration the FCR duty never gives",
    "afe_temp": "monitoring accuracy taken at 25 C, not over temperature",
    "chain": "reaction time without the daisy-chain readout",
    "coord": "contactor breaking current at 2 x fuse rating, cell short-time limits ignored",
    "short": "precharge resistor sized for normal precharge only, not into a shorted DC link",
    "selfdis": "balancing sized for self-discharge at 25 C",
    "mcu": "MCU chosen without counting chain ports",
    "ride": "rack control supply not bridged through grid faults",
    "reclose": "hold-up sized for one dip, not the reclose onto the fault",
    "coil": "hold-up sized for the controller only, without contactor coil and sensor",
    "imd_rack": "an insulation monitor in every rack",
    "imd_cap": "insulation monitor rated for the rack capacitance only",
}
REQUIREMENT_OF = {"soc": "H1", "recal": "H1", "afe_temp": "H2", "chain": "H3", "coord": "H4", "short": "H5",
                  "selfdis": "H6", "mcu": "H7", "ride": "H8", "reclose": "H8", "coil": "H8",
                  "imd_rack": "H9", "imd_cap": "H9"}  # several mistakes against one requirement count once


def _sig(x, n=3):
    return float(f"{x:.{n}g}")


def _r(rng, lo, hi, nd=3):
    return round(rng.uniform(lo, hi), nd)


def _pert(rng, x, lo=0.9, hi=1.1, nd=2):
    return round(x * rng.uniform(lo, hi), nd)


def plant(seed):
    """The level-3 optimum plus one rack, as the system team hands it over. None if it does not close."""
    rng = random.Random(f"bms4-{seed}")
    t3 = bessgen.draft(rng, seed, 3)
    best = bessgen._optimize(t3)[0]
    if best is None:
        return None, None, rng
    d = {**best[1], "strings_parallel": best[1]["strings_parallel"] + 1}
    pcs = bess._find(t3["pcs_catalog"], d["pcs"])
    if d["strings_parallel"] > pcs["dc_inputs"] * d["pcs_count"]:
        return None, None, rng
    r = bess.grade(t3, d)
    if [x for x in r["violations"] if not x.startswith("cost")]:
        return None, None, rng
    return t3, d, rng


def make_task(seed: int) -> dict | None:
    t3, d, rng = plant(seed)
    if t3 is None:
        return None
    m = bess.evaluate(t3, d)
    c3, p3 = t3["cell"], t3["params"]
    pcs = bess._find(t3["pcs_catalog"], d["pcs"])
    fuse = bess._find(t3["fuses"], d["string_fuse"])
    soh, _ = bess.life(t3)
    fcr = "fcr" in t3
    ns = d["cells_series"]
    pl = {
        "cells_series": ns, "strings_parallel": d["strings_parallel"], "module_cells": bessgen.MODULE,
        "modules_per_string": ns // bessgen.MODULE, "ntc_per_module": rng.choice([4, 6, 8]),
        "can_needed": rng.choice([2, 3]), "adc_needed": rng.choice([6, 8, 10, 12]),
        "i_string_a": round(m["i_string_a"], 1), "v_string_max": round(m["v_string_max"], 1),
        "q_eol_ah": round(c3["q_ah"] * soh, 1), "soc_window_pct": round((c3["soc_max"] - c3["soc_min"]) * 100, 1),
        "e_poi_mwh": round(m["e_poi_mwh"], 4), "e_aux_mwh": round(m["p_aux_kw"] * p3["duration_h"] / 1e3, 4),
        "e_req_mwh": round(m["e_req_mwh"], 4), "duration_h": p3["duration_h"],
        "pcs": pcs["id"], "pcs_count": d["pcs_count"], "pcs_kva": pcs["s_kva_25"],
        "dc_link_mf": round(pcs["s_kva_25"] / 1000 * rng.uniform(2, 6), 1),
        "fuse": fuse["id"], "fuse_i_n": fuse["i_n"], "dc_route_m": t3["site"]["dc_route_m"],
        "fuse_curve_s": {str(k): _sig(v * rng.uniform(0.8, 1.25)) for k, v in FUSE_CURVE.items()},
    }
    if fcr:
        pl["fcr_mw"] = t3["fcr"]["p_mw"]
    cell = {
        "chemistry": c3["chemistry"], "v_nom": c3["v_nom"], "v_max": c3["v_max"], "q_ah": c3["q_ah"],
        "c_cont": c3["c_cont"], "soc_min": c3["soc_min"], "soc_max": c3["soc_max"],
        "ocv": {str(k): round(v + rng.uniform(-0.002, 0.002), 3) for k, v in OCV.items()},
        "ov_disconnect_ms": rng.choice([100, 150, 200]), "v_ov_limit": 3.75,
        "pulse_limit_s": {str(k): _sig(v * rng.uniform(0.8, 1.25)) for k, v in PULSE_LIMIT.items()},
    }
    sd = _r(rng, 0.4, 1.5, 2)
    cell["self_discharge_spread_pct_month"] = {"25": sd, "35": round(2 * sd, 2), "45": round(4 * sd, 2)}
    ops = {
        "recal_soc_pct": round(c3["soc_max"] * 100), "recal_interval_h": 24 * (rng.choice([3, 5, 7, 10, 14]) if fcr else 1),
        "cell_temp_c": float(rng.choice([25, 30, 35])), "balancing_h_per_day": float(rng.choice([2, 4, 6, 8])),
    }
    fw = {
        "filter_samples": rng.choice([3, 4, 5]), "oc_trip_a": round(1.1 * c3["c_cont"] * c3["q_ah"]),
        "precharge_delta": rng.choice([0.02, 0.05]), "precharge_check_s": rng.choice([0.5, 1.0, 1.5]),
        "precharge_relay_peak_a": rng.choice([30, 50, 80]), "startup_overhead_s": rng.choice([0.5, 1.0]),
    }
    grid_fault = {"u_ret_pu": rng.choice([0.0, 0.05, 0.1, 0.15]), "t_fault_s": rng.choice([0.15, 0.2, 0.25]),
                  "t_recover_s": rng.choice([1.5, 2.0, 3.0]), "t_dead_s": rng.choice([0.3, 0.5, 1.0, 3.0])}
    aux_supply = {"u_min_pu": rng.choice([0.4, 0.5, 0.6, 0.7]), "hold_up_s": 0.02}
    earthing = {"rack_uf": _r(rng, 0.5, 2.0, 2), "pcs_uf": float(rng.choice([10, 20, 30, 45])),
                "cable_nf_per_m": _r(rng, 0.15, 0.35, 2)}
    task = {
        "id": f"bms4_{seed:03d}", "domain": "bms", "mode": "hidden", "level": 4, "plant": pl, "cell": cell,
        "operations": ops, "firmware": fw, "needs": {"dc_ready_s": float(rng.choice([5, 8, 10]))},
        "grid_fault": grid_fault, "aux_supply": aux_supply, "earthing": earthing,
        "afes": [{"id": i, "channels": ch, "err_25_mv": _pert(rng, e25), "err_full_mv": _pert(rng, ef), "t_conv_ms": _pert(rng, tc),
                  "t_read_ms": _pert(rng, tr), "max_chain": mc, "temp_inputs": ti, "bal_internal_ma": bal, "price": _pert(rng, pr, 0.85, 1.15)}
                 for i, ch, e25, ef, tc, tr, mc, ti, bal, pr in AFES],
        "current_sensors": [{"id": i, "type": ty, "range_a": rg, "offset_a": _pert(rng, off, 0.85, 1.15, 4), "gain_pct": g,
                             "w": w, "price": _pert(rng, pr, 0.85, 1.15)} for i, ty, rg, off, g, w, pr in SENSORS],
        "contactors": [{"id": i, "i_rated_a": ir, "u_dc": u, "i_break_a": ib, "t_open_ms": to, "hold_w": hw,
                        "price": _pert(rng, pr, 0.85, 1.15)} for i, ir, u, ib, to, hw, pr in CONTACTORS],
        "mcus": [{"id": i, "chain_ports": cp, "can_ports": can, "adc_channels": adc, "cycle_ms": cy, "w": w,
                  "price": _pert(rng, pr, 0.85, 1.15)} for i, cp, can, adc, cy, w, pr in MCUS],
        "hold_ups": [{"id": i, "j": j, "price": _pert(rng, pr, 0.85, 1.15)} for i, j, pr in HOLD_UPS],
        "imds": [{"id": i, "max_uf": uf, "w": w, "price": _pert(rng, pr, 0.85, 1.15)} for i, uf, w, pr in IMDS],
        "precharge_resistors": [{"id": f"PR-{n}", "ohm": ohm, "pulse_j": kj * 1000, "price": _pert(rng, pr, 0.85, 1.15)}
                                for n, (ohm, (kj, pr)) in enumerate(((o, k) for o in RESISTOR_OHMS for k in RESISTOR_KJ.items()), 1)],
        "balancing_stages": [{"id": i, "i_ma": ma, "price": _pert(rng, pr, 0.85, 1.15)} for i, ma, pr in BALANCING],
    }
    best, feasible = optimize(task)
    if best is None:
        return None
    task["objective"] = {"minimize": "cost", "optimum": round(best[0], 2), "tolerance": TOLERANCE}
    golden = best[1]
    r = bms.grade(task, golden)
    if not r["passed"]:
        raise RuntimeError(f"seed {seed}: optimizer golden fails the grader: {r['violations']}")
    hidden = hidden_broken(task)
    if len({REQUIREMENT_OF[b["flag"]] for b in hidden}) < MIN_HIDDEN_BINDING:
        return None
    broken = [b for b in broken_candidates(task, golden, feasible) if not bms.grade(task, b["output"])["passed"]] + hidden
    for b in broken:
        b["expect"] = bms.grade(task, b["output"])["violations"][0].split(" ")[0]
    task["_golden"], task["_broken"], task["_stats"] = golden, broken, {"feasible": len(feasible)}
    return task


def golden_requirements(task):
    want = bms.derived(task)
    return [{"id": rid, "parent": sorted(bms.parents(task)[rid])[0], "value": round(want[rid], 4),
             "unit": bms.REQUIREMENTS[rid][1], "basis": bms.REQUIREMENTS[rid][0]} for rid in bms.REQUIREMENTS]


def optimize(task, naive=frozenset()):
    """Cheapest BMS design, with the grader's physics. naive: hidden requirements the designer missed."""
    pl, c, fw, ops = task["plant"], task["cell"], task["firmware"], task["operations"]
    t = json.loads(json.dumps(task))
    if "recal" in naive:
        t["operations"]["recal_interval_h"] = 24
    if "afe_temp" in naive:
        for a in t["afes"]:
            a["err_full_mv"] = a["err_25_mv"]
    if "chain" in naive:
        for a in t["afes"]:
            a["t_read_ms"] = 0.0
    if "selfdis" in naive:
        t["operations"]["cell_temp_c"] = 25.0
    e_allowed = float("inf") if "soc" in naive else bms.soc_error_allowed(t)
    need_brk = 2 * pl["fuse_i_n"] if "coord" in naive else bms.breaking_needed(t)
    sensor_need = fw["oc_trip_a"] if "coord" in naive else need_brk
    bal_need = bms.balancing_needed_ma(t)
    c_dc, v = pl["dc_link_mf"] * 1e-3, pl["v_string_max"]
    t_ride = 0.0 if "ride" in naive else bms.ride_time(t, reclose="reclose" not in naive)
    c_sys = t["earthing"]["rack_uf"] if "imd_cap" in naive else bms.system_capacitance_uf(t)
    imd_loc = "rack" if "imd_rack" in naive else "plant"
    imd = min((x for x in t["imds"] if x["max_uf"] >= c_sys), key=lambda x: x["price"], default=None)
    if imd is None:
        return None, []

    res = min((r for r in t["precharge_resistors"]
               if r["ohm"] * c_dc * math.log(1 / fw["precharge_delta"]) <= bms.precharge_time_allowed(t) + 1e-9
               and v / r["ohm"] <= fw["precharge_relay_peak_a"] + 1e-9 and 0.5 * c_dc * v ** 2 <= r["pulse_j"] + 1e-9
               and ("short" in naive or v ** 2 / r["ohm"] * fw["precharge_check_s"] <= r["pulse_j"] + 1e-9)),
              key=lambda r: r["price"], default=None)
    if res is None:
        return None, []
    feasible, best = [], None
    for afe in t["afes"]:
        apm = max(math.ceil(pl["module_cells"] / afe["channels"]), math.ceil(pl["ntc_per_module"] / afe["temp_inputs"]))
        if afe["bal_internal_ma"] >= bal_need:
            bal = ("internal", 0.0)
        else:
            bal = min(((b["id"], b["price"]) for b in t["balancing_stages"] if b["i_ma"] >= bal_need), key=lambda x: x[1], default=None)
            if bal is None:
                continue
        sensors = [s for s in t["current_sensors"] if s["range_a"] >= sensor_need
                   and bms.soc_error(t, afe, s)[0] <= e_allowed + 1e-9]
        if not sensors:
            continue
        for chains in range(1, CHAINS_MAX + 1):
            for mcu in t["mcus"]:
                if mcu["can_ports"] < pl["can_needed"] or mcu["adc_channels"] < pl["adc_needed"]:
                    continue
                if "mcu" not in naive and mcu["chain_ports"] < chains:
                    continue
                for ct in t["contactors"]:
                    if ct["i_rated_a"] < pl["i_string_a"] or ct["u_dc"] < v or ct["i_break_a"] < need_brk:
                        continue
                    t_react, per_chain = bms.trip_time(t, afe, chains, apm, mcu, ct)
                    if per_chain > afe["max_chain"] or t_react > c["ov_disconnect_ms"] + 1e-9:
                        continue
                    if "coord" not in naive and bms.coordination(t, ct, mcu, need_brk):
                        continue
                    for sensor in sensors:  # the sensor's power now matters for the hold-up, so no shortcut
                        design = {"requirements": golden_requirements(task), "afe": afe["id"], "afe_per_module": apm,
                                  "chains_per_rack": chains, "current_sensor": sensor["id"], "mcu": mcu["id"],
                                  "string_contactor": ct["id"], "precharge_resistor": res["id"], "balancing": bal[0],
                                  "imd_location": imd_loc, "imd": imd["id"]}
                        need_j = bms.rack_power_w(t, design, with_coil="coil" not in naive) * t_ride
                        hold = "none" if need_j <= 1e-9 else min((x for x in t["hold_ups"] if x["j"] >= need_j),
                                                                    key=lambda x: x["price"], default=None)
                        if hold is None:
                            continue
                        design["hold_up"] = hold if hold == "none" else hold["id"]
                        cost = bms.cost(task, design)
                        feasible.append((cost, design))
                        if best is None or cost < best[0]:
                            best = (cost, design)
    return best, feasible


def hidden_broken(task):
    out = []
    for flag, note in HIDDEN.items():
        if flag == "recal" and "fcr_mw" not in task["plant"]:
            continue
        best = optimize(task, frozenset([flag]))[0]
        if best is None:
            continue
        r = bms.grade(task, best[1])
        if not r["passed"]:
            out.append({"output": best[1], "note": note, "flag": flag})
    return out


def broken_candidates(task, g, feasible):
    out = []
    reqs = g["requirements"]

    def add(note, **kw):
        cand = {**g, **kw}
        if cand != g:
            out.append({"output": cand, "note": note})

    add("requirement R-BRK not written down", requirements=[r for r in reqs if r["id"] != "R-BRK"])
    add("R-SOC traced to the start-up need", requirements=[{**r, "parent": "SN-3"} if r["id"] == "R-SOC" else r for r in reqs])
    pl = task["plant"]
    no_aux = pl["soc_window_pct"] / 2 * (1 - pl["e_req_mwh"] / pl["e_poi_mwh"])
    add("R-SOC without the auxiliary energy", requirements=[{**r, "value": round(no_aux, 4)} if r["id"] == "R-SOC" else r for r in reqs])
    c = task["cell"]
    bal25 = c["self_discharge_spread_pct_month"]["25"] / 100 * c["q_ah"] / 30 / task["operations"]["balancing_h_per_day"] * 1e3
    add("R-BAL at 25 C", requirements=[{**r, "value": round(bal25, 4)} if r["id"] == "R-BAL" else r for r in reqs])
    cheap = lambda cat: min(task[cat], key=lambda x: x["price"])["id"]  # noqa: E731
    add("requirement R-RIDE for a single dip", requirements=[{**r, "value": round(bms.ride_time(task, reclose=False), 4)}
                                                            if r["id"] == "R-RIDE" else r for r in reqs])
    add("R-IMD from the racks only", requirements=[{**r, "value": round(task["earthing"]["rack_uf"] * pl["strings_parallel"], 4)}
                                                   if r["id"] == "R-IMD" else r for r in reqs])
    add("cheapest part everywhere", afe=cheap("afes"), afe_per_module=2, chains_per_rack=1, current_sensor=cheap("current_sensors"),
        mcu=cheap("mcus"), string_contactor=cheap("contactors"), precharge_resistor=cheap("precharge_resistors"), balancing="internal")
    worst = max(feasible, key=lambda x: x[0])[1]
    if worst != g:
        out.append({"output": worst, "note": "feasible but most expensive"})
    return out


def _cat(rows, fmt):
    return "\n".join("  " + fmt(r) for r in rows)


def describe(t):
    pl, c, o, fw, n = t["plant"], t["cell"], t["operations"], t["firmware"], t["needs"]
    e, a, g = t["earthing"], t["aux_supply"], t["grid_fault"]
    k = lambda d, unit="": ", ".join(f"{x}{unit}: {y}" for x, y in d.items())  # noqa: E731
    fcr = "fcr_mw" in pl
    return (
        "Work package: battery management system (BMS) and DC string protection for a grid-connected lithium iron "
        "phosphate storage plant in Germany. The system team has closed the plant design and hands it over; the plant "
        "itself cannot change. Your team designs the rack BMS (one per string, identical for every rack) and writes down "
        "the requirements it derives.\n\n"
        "Stakeholder needs:\n"
        f"  SN-1: usable energy {pl['e_req_mwh']:.3f} MWh at the connection point (requirement including the project "
        f"margin) at end of service life, {pl['duration_h']} h duration, within the cell manufacturer's recommended SOC window.\n"
        + (f"  SN-2: prequalification for frequency containment reserve (FCR) in Germany with {pl['fcr_mw']:g} MW, symmetric.\n" if fcr else "")
        + f"  SN-3: DC bus of a PCS ready within {n['dc_ready_s']:g} s of a start command.\n"
        "  SN-4: cells operated within the cell manufacturer's safety limits at all times, including faults.\n"
        "  SN-5: lowest BMS and protection cost for the plant.\n"
        "  SN-6: compliance with the network operator's connection letter and technical connection rules.\n\n"
        "Handover from the system team (end of life where it matters):\n"
        f"  {pl['strings_parallel']} strings (one per rack) of {pl['cells_series']} cells in series: {pl['modules_per_string']} "
        f"modules of {pl['module_cells']} cells, {pl['ntc_per_module']} temperature sensors per module.\n"
        f"  String current at rated power {pl['i_string_a']} A; string voltage at full charge {pl['v_string_max']} V.\n"
        f"  Cell capacity at end of life {pl['q_eol_ah']} Ah. SOC window {c['soc_min'] * 100:.0f}-{c['soc_max'] * 100:.0f}%.\n"
        f"  Usable energy at the connection point at end of life over the full window, net of auxiliaries: {pl['e_poi_mwh']} MWh; "
        f"auxiliary energy during a full {pl['duration_h']} h discharge: {pl['e_aux_mwh']} MWh.\n"
        f"  PCS: {pl['pcs_count']} x {pl['pcs']} ({pl['pcs_kva']} kVA), strings on one PCS share its DC bus; DC-link "
        f"capacitance {pl['dc_link_mf']} mF per PCS.\n"
        f"  String fuse {pl['fuse']}: gBat, {pl['fuse_i_n']} A. Pre-arcing time by multiple of rated current: {k(pl['fuse_curve_s'], ' x')} s.\n"
        f"  DC cable route rack to PCS {pl['dc_route_m']} m per string (two conductors).\n"
        f"  The PCS units are transformerless; their AC outputs share one low-voltage winding of the step-up transformer, "
        f"whose star point is not earthed. Earth capacitance (Y-capacitors and stray): {e['rack_uf']} uF per rack, "
        f"{e['pcs_uf']:g} uF per PCS, {e['cable_nf_per_m']} nF per metre per DC conductor.\n"
        f"  Auxiliary supply: from the plant's medium-voltage busbar through an auxiliary transformer; each rack's 24 V "
        f"control supply (MCU, contactor coil, current sensor and anything else in the rack) comes from a power supply "
        f"that works down to {a['u_min_pu'] * 100:.0f}% of nominal input voltage and holds up {a['hold_up_s'] * 1e3:.0f} ms "
        f"after that.\n"
        f"  Rack controller interfaces: {pl['can_needed']} CAN buses (PCS, energy management" + (", fire system" if pl["can_needed"] > 2 else "")
        + f"), {pl['adc_needed']} analogue channels (current, voltages on both sides of the contactor, insulation monitoring, spares).\n\n"
        f"Cell datasheet ({c['chemistry']}, {c['q_ah']:g} Ah, {c['v_nom']} V nominal, charge to {c['v_max']} V, continuous {c['c_cont']:g} C):\n"
        f"  Open-circuit voltage by SOC %: {k(c['ocv'])} V.\n"
        f"  Safety limit: above {c['v_ov_limit']} V the cell must be disconnected within {c['ov_disconnect_ms']} ms.\n"
        f"  Short-time current limit by multiple of 1 C: {k(c['pulse_limit_s'], ' C')} s.\n"
        f"  Cell-to-cell spread in self-discharge, % of capacity per month, by cell temperature: {k(c['self_discharge_spread_pct_month'], ' C')}.\n\n"
        "Network operator's connection letter (extract): the plant must stay connected through the following fault "
        "sequence, a fault on a neighbouring feeder with an unsuccessful automatic reclose. At t = 0 the voltage at the "
        f"connection point falls to {g['u_ret_pu'] * 100:.0f}% for {g['t_fault_s'] * 1e3:.0f} ms; the faulted feeder's breaker "
        f"then opens and the voltage recovers linearly from {g['u_ret_pu'] * 100:.0f}% towards 90% over {g['t_recover_s']:g} s. "
        f"The breaker recloses {g['t_dead_s']:g} s after opening, onto the fault, which is still present: the voltage falls to "
        f"{g['u_ret_pu'] * 100:.0f}% again for {g['t_fault_s'] * 1e3:.0f} ms and recovers the same way, and the breaker then "
        "opens for good.\n\n"
        "Operations:\n"
        + (f"  The plant runs FCR; the operator schedules a charge to the top of the window every {o['recal_interval_h'] / 24:g} days "
           "for SOC recalibration.\n" if fcr else
           "  The plant cycles daily and reaches the top of its window every day.\n")
        + f"  Recalibration: the plant rests 30 min at {o['recal_soc_pct']}% SOC and the BMS resets SOC from the open-circuit voltage.\n"
        f"  Between recalibrations the BMS counts charge. Current sensors are auto-zeroed while the contactor is open.\n"
        f"  The HVAC holds the cells at {o['cell_temp_c']:g} C. Balancing can run {o['balancing_h_per_day']:g} h per day.\n\n"
        "Firmware team (fixed):\n"
        f"  Cell over-voltage is confirmed after {fw['filter_samples']} consecutive scans of the whole daisy chain, then the MCU "
        "opens the string contactor in its next control cycle.\n"
        f"  Overcurrent trip at {fw['oc_trip_a']} A from the current sensor (no daisy chain in this path); above the "
        "contactor's breaking capability the BMS keeps it closed and leaves interruption to the fuse.\n"
        f"  Precharge: the main contactor closes when the DC bus is within {fw['precharge_delta'] * 100:g}% of the string voltage. "
        f"The BMS checks the bus voltage {fw['precharge_check_s']:g} s after starting precharge and aborts if it has not risen. "
        f"The precharge relay is rated {fw['precharge_relay_peak_a']} A peak. The start sequence before precharge takes "
        f"{fw['startup_overhead_s']:g} s.\n\n"
        "Cell monitoring chips (id: cell channels, voltage error mV at 25 C / over -40 to 105 C, conversion ms (all cells at "
        "once), readout ms per chip on the daisy chain, max chips per chain, temperature inputs, internal balancing mA, price; "
        "a chip monitors cells of one module only):\n"
        + _cat(t["afes"], lambda x: f"{x['id']}: {x['channels']}, {x['err_25_mv']} / {x['err_full_mv']} mV, {x['t_conv_ms']} ms, "
                                    f"{x['t_read_ms']} ms, {x['max_chain']}, {x['temp_inputs']}, {x['bal_internal_ma']} mA, {x['price']:.2f}")
        + "\n\nCurrent sensors (id: type, highest current measured A, residual offset A after auto-zero over temperature (fine "
        "channel for dual-channel sensors), gain error %, power W at 24 V, price):\n"
        + _cat(t["current_sensors"], lambda x: f"{x['id']}: {x['type']}, {x['range_a']} A, {x['offset_a']} A, {x['gain_pct']}%, "
                                               f"{x['w']} W, {x['price']:.2f}")
        + "\n\nString contactors (id: rated current A, rated DC voltage V, breaking current A at 1500 V DC, opening time ms, "
        "coil holding power W at 24 V, price):\n"
        + _cat(t["contactors"], lambda x: f"{x['id']}: {x['i_rated_a']} A, {x['u_dc']} V, {x['i_break_a']} A, {x['t_open_ms']} ms, "
                                          f"{x['hold_w']} W, {x['price']:.2f}")
        + "\n\nRack MCUs (id: daisy-chain ports, CAN ports, ADC channels, control cycle ms, board power W at 24 V, price):\n"
        + _cat(t["mcus"], lambda x: f"{x['id']}: {x['chain_ports']}, {x['can_ports']}, {x['adc_channels']}, {x['cycle_ms']} ms, {x['w']} W, {x['price']:.2f}")
        + "\n\nPrecharge resistors (id: ohm, single-pulse energy J, price):\n"
        + _cat(t["precharge_resistors"], lambda x: f"{x['id']}: {x['ohm']} ohm, {x['pulse_j']:.0f} J, {x['price']:.2f}")
        + "\n\nExternal balancing stages, one per module (id: balancing current mA, price per module); or use the chip's "
        "internal balancing:\n"
        + _cat(t["balancing_stages"], lambda x: f"{x['id']}: {x['i_ma']} mA, {x['price']:.2f}")
        + "\n\n24 V hold-up modules, one per rack, or none (id: usable energy J, price):\n"
        + _cat(t["hold_ups"], lambda x: f"{x['id']}: {x['j']} J, {x['price']:.2f}")
        + "\n\nInsulation monitoring devices, fitted in every rack or once for the plant (id: maximum system leakage "
        "capacitance uF, power W at 24 V, price):\n"
        + _cat(t["imds"], lambda x: f"{x['id']}: {x['max_uf']} uF, {x['w']} W, {x['price']:.2f}")
        + "\n\nDerived requirements to write down, each traced to the stakeholder need it comes from, with a value that "
        "follows from the data: R-SOC (maximum SOC error, %), R-TRIP (maximum over-voltage disconnect time, ms), R-PRE "
        "(maximum precharge time, s), R-BAL (minimum balancing current, mA), R-BRK (minimum DC breaking current of the "
        "string contactor, A), R-RIDE (minimum time the rack's 24 V must be bridged by its hold-up, s), R-IMD (minimum "
        "system leakage capacitance rating of the insulation monitoring, uF).\n\n"
        "Objective: minimize the BMS and protection price for the plant (monitoring chips, balancing stages, current sensor, "
        "MCU, contactor, precharge resistor and hold-up for every rack, and the insulation monitoring). The design must meet every stakeholder need, and every "
        "requirement that follows from them and from the data, whether or not it is listed here; its price must be within "
        f"{t['objective']['tolerance'] * 100:.0f}% of the cheapest design that does. Return " + OUTPUT_SHAPE
    )


OUTPUT_SHAPE = ('{"requirements": [{"id": "R-SOC", "parent": "SN-<n>", "value": <number>, "unit": "%", "basis": "<one line>"}, ...], '
                '"afe": "<id>", "afe_per_module": <int>, "chains_per_rack": <int>, "current_sensor": "<id>", "mcu": "<id>", '
                '"string_contactor": "<id>", "precharge_resistor": "<id>", "balancing": "internal" or "<id>", '
                '"hold_up": "none" or "<id>", "imd_location": "rack" or "plant", "imd": "<id>"}')
SOURCES = [
    "German TSOs, PQ-Bedingungen v1.06 (2026-10-07), sec. 3.1.6: FCR limited-energy reserve, regelleistung.net",
    "IEC 60269-7 gBat battery fuse time-current behaviour as described in SIBA, Mersen and ETI battery-fuse catalogs",
    "LFP open-circuit voltage plateau and top-of-charge recalibration as described in public BMS application notes (TI, ADI)",
    "Precharge circuit design (time constant, resistor pulse energy, fault abort) as described in Sensata/GIGAVAC and TE application notes",
    "Cell monitoring chip, current sensor, contactor and MCU catalogs patterned on public datasheets; every value synthetic and perturbed per seed",
    "VDE-AR-N 4110 dynamic grid support for type 2 units and storage (ride through faults, including repeated faults and automatic reclosing) as summarised in VDE FNN, TCR medium voltage overview (2017)",
    "Fault-sequence shape patterned on Commission Regulation (EU) 2016/631 (RfG), Art. 14(3), Table 3.2 ranges for power park modules",
    "Insulation monitoring of unearthed (IT) DC systems, one active device per galvanically connected system, as described in IEC 61557-8 manufacturer application notes (Bender)",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--private", action="store_true", help="held-out seeds: write to tasks_private/ (not committed)")
    ap.add_argument("--count", type=int, help="stop after this many tasks are kept")
    args = ap.parse_args()
    out_dir = ROOT / ("tasks_private" if args.private else "tasks")
    out_dir.mkdir(exist_ok=True)
    sol_path = out_dir / "solutions.json" if args.private else ROOT / "solvers" / "solutions.json"
    solutions = json.loads(sol_path.read_text()) if sol_path.exists() else {}
    made = 0
    for seed in args.seeds:
        if args.count and made >= args.count:
            break
        t = make_task(seed)
        if t is None:
            print(f"seed {seed}: skipped (plant does not close, no feasible BMS, or hidden requirements do not bind)")
            continue
        golden, broken, stats = t.pop("_golden"), t.pop("_broken"), t.pop("_stats")
        t.update({"title": "Battery management and DC protection for a storage plant", "description": describe(t),
                  "output_shape": OUTPUT_SHAPE, "sources": SOURCES, "seed": seed,
                  "disciplines": ["electronics", "embedded", "electrical", "battery", "systems"]})
        (out_dir / f"{t['id']}.json").write_text(json.dumps(t, indent=2) + "\n")
        solutions[t["id"]] = {"golden": golden, "broken": [{"output": b["output"], "expect": b["expect"]} for b in broken]}
        made += 1
        print(f"{t['id']}: feasible {stats['feasible']}, optimum {t['objective']['optimum']:,.0f}, hidden binding "
              f"{sorted({REQUIREMENT_OF[b['flag']] for b in broken if 'flag' in b})}, {len(broken)} broken: {[b['note'] for b in broken]}")
        sol_path.write_text(json.dumps(solutions, indent=1) + "\n")
    print(f"{made} tasks written to {out_dir.name}/")


if __name__ == "__main__":
    main()
