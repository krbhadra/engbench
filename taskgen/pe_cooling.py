"""Generate pe_cooling tasks: perturbed parameters, brute-forced golden, derived broken cases.

    python taskgen/pe_cooling.py --seeds 1 2 3 4 5

Each seed produces tasks/pe_cooling_<seed>.json and merges golden/broken into
solvers/solutions.json. Seeds whose problem is trivial or infeasible are skipped.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
import pe_cooling  # noqa: E402

# Catalog archetypes (perturbed per seed).
SINKS = [  # id, Rsa at v = 0,1,2,4 m/s (C/W), height mm, price
    ("HS-1", [12.0, 6.0, 4.2, 3.0], 15, 2.0),
    ("HS-2", [8.0, 4.0, 2.8, 2.0], 25, 4.0),
    ("HS-3", [5.5, 2.6, 1.8, 1.3], 35, 7.0),
    ("HS-4", [3.8, 1.8, 1.25, 0.9], 45, 11.0),
    ("HS-5", [2.6, 1.2, 0.85, 0.6], 60, 18.0),
    ("HS-6", [1.8, 0.85, 0.6, 0.45], 80, 29.0),
]
FANS = [  # id, size, Qmax m3/h, Pmax Pa, power W, dBA, price
    ("FAN-A", "40x40x10 mm", 15, 30, 1.0, 28, 3.0),
    ("FAN-B", "60x60x25 mm", 40, 45, 2.4, 32, 6.0),
    ("FAN-C", "80x80x25 mm", 70, 40, 2.6, 30, 8.0),
    ("FAN-D", "80x80x38 mm", 110, 90, 6.0, 42, 14.0),
    ("FAN-E", "92x92x38 mm", 160, 110, 9.0, 46, 19.0),
]
INDUCTORS = [  # id, L uH, DCR mOhm, Isat A, price
    ("IND-1", 4.7, 2.0, 30, 1.5),
    ("IND-2", 6.8, 2.8, 32, 1.9),
    ("IND-3", 10.0, 4.0, 35, 2.4),
    ("IND-4", 15.0, 6.5, 38, 3.2),
    ("IND-5", 22.0, 9.5, 45, 4.5),
    ("IND-6", 33.0, 14.0, 55, 6.5),
]
FSW_GRID = list(range(50_000, 500_001, 10_000))
MIN_FEASIBLE_FRACTION = 0.002
MAX_FEASIBLE_FRACTION = 0.03
COST_TOLERANCE = 0.05  # pass if price <= (1 + this) * brute-force optimum
# stored values are rounded to exactly what describe() prints, so the model and the grader compute from the same numbers
MAX_NEAR_OPT_FRACTION = 0.25  # reject seeds where more than this share of feasible designs is near-optimal


def _r(rng, lo, hi, nd=3):
    return round(rng.uniform(lo, hi), nd)


def make_task(seed: int) -> dict | None:
    rng = random.Random(seed)
    vin = rng.choice([24.0, 36.0, 48.0])
    vout = rng.choice([5.0, 12.0]) if vin > 24 else 5.0
    iout = float(rng.choice(range(15, 41, 5)))
    p = {
        "vin": vin, "vout": vout, "iout": iout,
        "rds25": _r(rng, 0.0030, 0.0080, 5), "alpha": _r(rng, 0.0035, 0.0055, 4),
        "tr_tf_s": _r(rng, 25e-9, 60e-9, 9), "qg_c": _r(rng, 40e-9, 90e-9, 9), "vgs": 10.0,
        "rth_jc": _r(rng, 0.4, 0.9, 2), "rth_cs": _r(rng, 0.2, 0.5, 2),
        "ta_ext": float(rng.choice([25, 30, 35, 40])), "r_encl": _r(rng, 1.2, 3.0, 2),
        "c_f": _r(rng, 100e-6, 330e-6, 6),
        "fsw_min_hz": 50_000.0, "fsw_max_hz": 500_000.0,
        "duct_area_m2": _r(rng, 0.004, 0.008, 4), "k_system": _r(rng, 0.008, 0.02, 4),
    }
    ripple_i = round(iout * rng.choice([0.2, 0.25, 0.3, 0.35]), 2)
    ripple_v = rng.choice([0.05, 0.1, 0.15])
    sf = _r(rng, 0.9, 1.1, 3)  # one catalog-wide performance scale per seed
    sinks = [{"id": i, "rsa_vs_v": [[0, round(a * sf, 2)], [1, round(b * sf, 2)], [2, round(c * sf, 2)], [4, round(d * sf, 2)]],
              "height_mm": h, "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)} for i, (a, b, c, d), h, pr in SINKS]
    fans = []
    for i, size, qmax, pmax, w, dba, pr in FANS:
        qs, ps = qmax * sf, pmax * sf
        fans.append({"id": i, "size": size, "curve": [[0, round(ps, 1)], [round(0.5 * qs, 1), round(0.6 * ps, 1)],
                                                        [round(0.8 * qs, 1), round(0.3 * ps, 1)], [round(qs, 1), 0]],
                     "power_w": w, "dba": dba, "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)})
    isf = _r(rng, 0.85, 1.1, 3)
    inductors = [{"id": i, "l_h": round(l * 1e-6 * _r(rng, 0.9, 1.1, 3), 8), "dcr_ohm": round(dcr * 1e-3 * _r(rng, 0.9, 1.2, 3), 5),
                  "isat_a": round(isat * isf, 1), "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)} for i, l, dcr, isat, pr in INDUCTORS]
    task = {"id": f"pe_cooling_{seed:03d}", "domain": "pe_cooling", "params": p, "limits": {},
            "heatsinks": sinks, "fans": fans, "inductors": inductors}

    # Evaluate every design once; keep those meeting the physical (non-tunable) constraints.
    pool = []
    for fsw in FSW_GRID:
        for ind in inductors:
            for s in sinks:
                for f in [None] + fans:
                    design = {"fsw_hz": fsw, "inductor": ind["id"], "heatsink": s["id"], "fan": f["id"] if f else None}
                    m = pe_cooling.evaluate(task, design)
                    if m["d_i"] <= ripple_i and m["d_v"] <= ripple_v and m["i_peak"] <= m["isat"]:
                        pool.append((design, m))
    total = len(FSW_GRID) * len(inductors) * len(sinks) * (len(fans) + 1)
    if len(pool) < 50:
        return None

    # Calibrate the tunable limits so the feasible fraction lands in the target band.
    etas = sorted(m["eta"] for _, m in pool)
    tjs = sorted(m["tj"] for _, m in pool)
    costs = sorted(m["cost"] for _, m in pool)
    lim = feasible = None
    for _ in range(40):
        cand = {
            "tj_max_c": float(rng.choice([95, 100, 105, 110, 115, 120, 125])),
            "eta_min": round(etas[int(len(etas) * rng.uniform(0.80, 0.995))] // 0.001 * 0.001, 3),
            "ripple_i_max_a": ripple_i, "ripple_v_max_v": ripple_v,
            "noise_max_dba": float(rng.choice([32, 35, 40, 46])),
            "height_max_mm": float(rng.choice([35, 45, 60])),
            "cost_max": float(round(costs[int(len(costs) * rng.uniform(0.05, 0.6))] + 0.5)),
        }
        ok = [(m["cost"], m["p_total"], d) for d, m in pool
              if m["tj"] <= cand["tj_max_c"] and m["eta"] >= cand["eta_min"] and m["noise_dba"] <= cand["noise_max_dba"]
              and m["height_mm"] <= cand["height_max_mm"] and m["cost"] <= cand["cost_max"]]
        if ok and MIN_FEASIBLE_FRACTION <= len(ok) / total <= MAX_FEASIBLE_FRACTION:
            lim, feasible = cand, ok
            break
    if lim is None:
        return None
    task["limits"] = lim
    feasible.sort(key=lambda t: (t[0], t[1]))
    golden = feasible[0][2]
    task["objective"] = {"minimize": "cost", "optimum": round(feasible[0][0], 2), "tolerance": COST_TOLERANCE}
    near_opt = sum(1 for c, _, _ in feasible if c <= feasible[0][0] * (1 + COST_TOLERANCE))
    if near_opt > MAX_NEAR_OPT_FRACTION * len(feasible):
        return None  # objective is trivial: most feasible designs already pass it

    cheapest_sink = min(sinks, key=lambda s: s["price"])["id"]
    cheapest_ind = min(inductors, key=lambda x: x["price"])["id"]
    broken = []
    for cand, note in [
        ({**golden, "fan": None}, "no fan"),
        ({**golden, "heatsink": cheapest_sink}, "cheapest sink"),
        ({**golden, "inductor": cheapest_ind}, "cheapest inductor"),
        ({**golden, "fsw_hz": p["fsw_max_hz"]}, "max switching frequency"),
        ({**golden, "fsw_hz": p["fsw_min_hz"]}, "min switching frequency"),
        ({**golden, "heatsink": "HS-6", "fan": "FAN-E", "inductor": "IND-6"}, "biggest everything"),
        (feasible[-1][2], "feasible but most expensive"),
    ]:
        if cand == golden:
            continue
        r = pe_cooling.grade(task, cand)
        if not r["passed"]:
            broken.append({"output": cand, "expect": r["violations"][0].split(" ")[0], "note": note})
    if len(broken) < 2:
        return None
    task["_golden"], task["_broken"] = golden, broken
    task["_stats"] = {"feasible": len(feasible), "near_opt": near_opt, "total": total}
    return task


def describe(t: dict) -> str:
    p, lim = t["params"], t["limits"]
    sinks = "\n".join(f"  {s['id']}: Rsa = {s['rsa_vs_v'][0][1]} / {s['rsa_vs_v'][1][1]} / {s['rsa_vs_v'][2][1]} / {s['rsa_vs_v'][3][1]} C/W at v = 0 / 1 / 2 / 4 m/s, height {s['height_mm']} mm, price {s['price']:.2f}"
                      for s in t["heatsinks"])
    fans = "\n".join(f"  {f['id']} ({f['size']}): static pressure vs flow points {f['curve']} (m3/h, Pa), electrical power {f['power_w']} W, {f['dba']} dBA, price {f['price']:.2f}"
                     for f in t["fans"])
    inds = "\n".join(f"  {i['id']}: L = {i['l_h']*1e6:.2f} uH, DCR = {i['dcr_ohm']*1e3:.2f} mOhm, Isat = {i['isat_a']} A, price {i['price']:.2f}"
                     for i in t["inductors"])
    return (
        f"Design the power stage cooling for a synchronous buck converter inside a sealed-except-for-the-fan enclosure: "
        f"Vin = {p['vin']:g} V, Vout = {p['vout']:g} V, Iout = {p['iout']:g} A, D = Vout / Vin. Choose the switching frequency fsw, "
        f"an inductor, a heat sink, and a fan (or no fan) from the catalogs below.\n\n"
        f"MOSFETs (both identical): Rds(on) = {p['rds25']*1e3:.2f} mOhm at 25 C with Rds(Tj) = Rds25 * (1 + alpha * (Tj - 25)), alpha = {p['alpha']} per C; "
        f"tr + tf = {p['tr_tf_s']*1e9:.0f} ns; Qg = {p['qg_c']*1e9:.0f} nC at Vgs = {p['vgs']:g} V. "
        f"Loss model: P_cond = Iout^2 * Rds(Tj) (the two FETs together carry Iout), P_sw = 0.5 * Vin * Iout * (tr + tf) * fsw, "
        f"P_gate = 2 * Qg * Vgs * fsw, P_fet = P_cond + P_sw + P_gate.\n\n"
        f"Inductor: dI = Vout * (1 - D) / (L * fsw); peak current Iout + dI / 2 must not exceed the inductor's Isat; "
        f"inductor loss P_L = Iout^2 * DCR (ignore the ripple term). Output capacitor C = {p['c_f']*1e6:.0f} uF: dV = dI / (8 * C * fsw). "
        f"Limits: dI <= {lim['ripple_i_max_a']} A, dV <= {lim['ripple_v_max_v']*1e3:.0f} mV.\n\n"
        f"Enclosure air: everything dissipates inside, P_total = P_fet + P_L + P_fan where P_fan is the fan's electrical power (0 without a fan). "
        f"Outside ambient Ta_ext = {p['ta_ext']:g} C. With a fan, Ta_int = Ta_ext + P_total / (1206 * Q / 3600) where Q (m3/h) is the fan operating point "
        f"and 1206 J/(m3 K) is the volumetric heat capacity of air. Without a fan, Ta_int = Ta_ext + P_total * R_encl with R_encl = {p['r_encl']} C/W.\n\n"
        f"Fan operating point: the flow Q at which the fan's static pressure (interpolate linearly between its curve points) equals the enclosure "
        f"system curve dP = k * Q^2, k = {p['k_system']} Pa/(m3/h)^2. Air velocity through the heat sink v = Q / 3600 / A_duct, A_duct = {p['duct_area_m2']} m2 (v = 0 without a fan).\n\n"
        f"Heat sink: both FETs share it. Tj = Ta_int + P_fet * (RthJC + RthCS + Rsa(v)) with RthJC = {p['rth_jc']} C/W, RthCS = {p['rth_cs']} C/W; "
        f"Rsa(v) is interpolated linearly between the catalog points and clamped outside them. Rds depends on Tj and Ta_int depends on P_total, so solve self-consistently.\n\n"
        f"Efficiency: eta = Pout / (Pout + P_total), Pout = Vout * Iout.\n\n"
        f"Constraints: fsw between {p['fsw_min_hz']/1e3:.0f} and {p['fsw_max_hz']/1e3:.0f} kHz; Tj <= {lim['tj_max_c']:g} C; eta >= {lim['eta_min']*100:.1f}%; "
        f"fan noise <= {lim['noise_max_dba']:g} dBA (no fan = 0 dBA); heat sink height <= {lim['height_max_mm']:g} mm; "
        f"heat sink + fan + inductor price <= {lim['cost_max']:g}.\n\n"
        f"Heat sink catalog:\n{sinks}\n\nFan catalog (or no fan):\n{fans}\n\nInductor catalog:\n{inds}\n\n"
        f"Objective: minimize heat sink + fan + inductor price. A design passes only if it meets every constraint AND its price is "
        f"within {t['objective']['tolerance']*100:.0f}% of the cheapest design that meets every constraint. Return {{\"fsw_hz\": <number>, \"inductor\": \"<id>\", \"heatsink\": \"<id>\", \"fan\": \"<id>\" or null}}."
    )


OUTPUT_SHAPE = '{"fsw_hz": <switching frequency in Hz>, "inductor": "<catalog id>", "heatsink": "<catalog id>", "fan": "<catalog id> or null"}'
SOURCES = [
    "Kunzi, Thermal Design of Power Electronic Circuits, CERN-2015-003 / arXiv:1607.01578 (CC BY 4.0): loss model and Rth chain",
    "TI SPRA953D Semiconductor and IC Package Thermal Metrics: RthJC / RthCS chain",
    "Boyd Board-Level Cooling catalog: heat-sink selection method, Rsa vs airflow",
    "ebm-papst, Fan curves and optimum operating points: fan curve vs system curve",
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
        t.update({"title": "Buck converter cooling chain", "description": describe(t),
                  "output_shape": OUTPUT_SHAPE, "sources": SOURCES, "seed": seed,
                  "disciplines": ["electronics", "thermal", "fluids"]})
        (ROOT / "tasks" / f"{t['id']}.json").write_text(json.dumps(t, indent=2) + "\n")
        solutions[t["id"]] = {"golden": golden, "broken": [{"output": b["output"], "expect": b["expect"]} for b in broken]}
        made += 1
        print(f"{t['id']}: feasible {stats['feasible']}/{stats['total']} ({100*stats['feasible']/stats['total']:.2f}%), "
              f"near-optimal {stats['near_opt']}, golden {golden}, {len(broken)} broken")
    sol_path.write_text(json.dumps(solutions, indent=1) + "\n")
    print(f"{made} tasks written")


if __name__ == "__main__":
    main()
