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

# Catalog archetypes (perturbed per seed). Rsa vs air velocity, m/s -> C/W.
SINKS = [  # id, rsa at v = 0,1,2,4 m/s, height mm, price
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
FSW_GRID = list(range(50_000, 500_001, 10_000))


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
        "tr_tf_s": _r(rng, 25e-9, 60e-9, 11), "qg_c": _r(rng, 40e-9, 90e-9, 11), "vgs": 10.0,
        "rth_jc": _r(rng, 0.4, 0.9, 2), "rth_cs": _r(rng, 0.2, 0.5, 2),
        "ta": float(rng.choice([35, 40, 45, 50])),
        "l_h": _r(rng, 6e-6, 15e-6, 8), "c_f": _r(rng, 100e-6, 330e-6, 7),
        "fsw_min_hz": 50_000.0, "fsw_max_hz": 500_000.0,
        "duct_area_m2": _r(rng, 0.004, 0.008, 4), "k_system": _r(rng, 0.008, 0.02, 4),
    }
    tj_abs = 150.0
    lim = {
        "tj_max_c": tj_abs - rng.choice([25, 30, 35, 40]),
        "eta_min": rng.choice([0.955, 0.96, 0.965, 0.97, 0.975]),
        "ripple_i_max_a": round(iout * rng.choice([0.2, 0.25, 0.3]), 2),
        "ripple_v_max_v": rng.choice([0.05, 0.1, 0.15]),
        "noise_max_dba": float(rng.choice([32, 35, 40, 46])),
        "height_max_mm": float(rng.choice([35, 45, 60])),
        "cost_max": float(rng.choice([12, 15, 18, 22, 28, 35])),
    }
    sf = _r(rng, 0.9, 1.1, 3)  # one catalog-wide performance scale per seed
    sinks = [{"id": i, "rsa_vs_v": [[0, round(a * sf, 2)], [1, round(b * sf, 2)], [2, round(c * sf, 2)], [4, round(d * sf, 2)]],
              "height_mm": h, "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)} for i, (a, b, c, d), h, pr in SINKS]
    fans = []
    for i, size, qmax, pmax, w, dba, pr in FANS:
        qs, ps = qmax * sf, pmax * sf
        fans.append({"id": i, "size": size, "curve": [[0, round(ps, 1)], [round(0.5 * qs, 1), round(0.6 * ps, 1)],
                                                        [round(0.8 * qs, 1), round(0.3 * ps, 1)], [round(qs, 1), 0]],
                     "power_w": w, "dba": dba, "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)})
    task = {"id": f"pe_cooling_{seed:03d}", "domain": "pe_cooling", "params": p, "limits": lim,
            "heatsinks": sinks, "fans": fans}

    # brute force the design space
    feasible, total = [], 0
    for fsw in FSW_GRID:
        for s in sinks:
            for f in [None] + fans:
                total += 1
                design = {"fsw_hz": fsw, "heatsink": s["id"], "fan": f["id"] if f else None}
                r = pe_cooling.grade(task, design)
                if r["passed"]:
                    feasible.append((r["metrics"]["cost"], r["metrics"]["p_loss"], design))
    if not feasible or len(feasible) / total > 0.25:
        return None  # infeasible or too easy
    feasible.sort(key=lambda t: (t[0], t[1]))
    golden = feasible[0][2]

    # broken: derived from the golden by breaking one decision each
    cheapest = min(sinks, key=lambda s: s["price"])
    broken = []
    for cand, note in [
        ({**golden, "fan": None}, "no fan"),
        ({**golden, "heatsink": cheapest["id"], "fan": None}, "cheapest sink, no fan"),
        ({**golden, "fsw_hz": p["fsw_max_hz"]}, "max switching frequency"),
        ({**golden, "fsw_hz": p["fsw_min_hz"]}, "min switching frequency"),
        ({**golden, "heatsink": "HS-6", "fan": "FAN-E"}, "biggest everything"),
    ]:
        r = pe_cooling.grade(task, cand)
        if not r["passed"] and cand != golden:
            broken.append({"output": cand, "expect": r["violations"][0].split(" ")[0], "note": note})
    if len(broken) < 2:
        return None
    task["_golden"], task["_broken"], task["_stats"] = golden, broken, {"feasible": len(feasible), "total": total}
    return task


def describe(t: dict) -> str:
    p, lim = t["params"], t["limits"]
    sinks = "\n".join(f"  {s['id']}: Rsa = {s['rsa_vs_v'][0][1]} / {s['rsa_vs_v'][1][1]} / {s['rsa_vs_v'][2][1]} / {s['rsa_vs_v'][3][1]} C/W at 0 / 1 / 2 / 4 m/s, height {s['height_mm']} mm, price {s['price']:.2f}"
                      for s in t["heatsinks"])
    fans = "\n".join(f"  {f['id']} ({f['size']}): static pressure vs flow points {f['curve']} (m3/h, Pa), {f['dba']} dBA, price {f['price']:.2f}"
                     for f in t["fans"])
    return (
        f"Design the cooling for a synchronous buck converter: Vin = {p['vin']:g} V, Vout = {p['vout']:g} V, Iout = {p['iout']:g} A. "
        f"Both MOSFETs are identical: Rds(on) = {p['rds25']*1e3:.2f} mOhm at 25 C with temperature coefficient alpha = {p['alpha']} per C, "
        f"i.e. Rds(Tj) = Rds25 * (1 + alpha * (Tj - 25)); switching transition tr + tf = {p['tr_tf_s']*1e9:.0f} ns; gate charge Qg = {p['qg_c']*1e9:.0f} nC at Vgs = {p['vgs']:g} V. "
        f"Use this loss model: P_cond = Iout^2 * Rds(Tj) (the two FETs together conduct the full output current), P_sw = 0.5 * Vin * Iout * (tr + tf) * fsw, "
        f"P_gate = 2 * Qg * Vgs * fsw, P = P_cond + P_sw + P_gate. Efficiency eta = Pout / (Pout + P) with Pout = Vout * Iout.\n\n"
        f"Both FETs share one heat sink: Tj = Ta + P * (RthJC + RthCS + Rsa), with RthJC = {p['rth_jc']} C/W, RthCS = {p['rth_cs']} C/W, "
        f"Ta = {p['ta']:g} C inside the enclosure. Note Rds depends on Tj, so solve the thermal loop self-consistently. "
        f"Rsa depends on the air velocity v through the sink; interpolate linearly between the catalog points and clamp outside them. "
        f"Air velocity v = Q / 3600 / A_duct with A_duct = {p['duct_area_m2']} m2, where Q (m3/h) is the fan operating point: "
        f"the flow at which the fan's static pressure (interpolate linearly between its curve points) equals the enclosure system curve dP = k * Q^2 with k = {p['k_system']} Pa/(m3/h)^2. "
        f"With no fan, v = 0.\n\n"
        f"Ripple: inductor L = {p['l_h']*1e6:.1f} uH, output capacitor C = {p['c_f']*1e6:.0f} uF, D = Vout / Vin. "
        f"dI = Vout * (1 - D) / (L * fsw) must not exceed {lim['ripple_i_max_a']} A and dV = dI / (8 * C * fsw) must not exceed {lim['ripple_v_max_v']*1e3:.0f} mV.\n\n"
        f"Constraints: fsw between {p['fsw_min_hz']/1e3:.0f} and {p['fsw_max_hz']/1e3:.0f} kHz; Tj <= {lim['tj_max_c']:g} C; eta >= {lim['eta_min']*100:.1f}%; "
        f"fan noise <= {lim['noise_max_dba']:g} dBA (no fan = 0 dBA); heat sink height <= {lim['height_max_mm']:g} mm; heat sink price + fan price <= {lim['cost_max']:g}.\n\n"
        f"Heat sink catalog:\n{sinks}\n\nFan catalog (or use no fan):\n{fans}\n\n"
        f"Any design satisfying every constraint passes. Return {{\"fsw_hz\": <number>, \"heatsink\": \"<id>\", \"fan\": \"<id>\" or null}}."
    )


OUTPUT_SHAPE = '{"fsw_hz": <switching frequency in Hz>, "heatsink": "<catalog id>", "fan": "<catalog id> or null"}'
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
        print(f"{t['id']}: feasible {stats['feasible']}/{stats['total']} ({100*stats['feasible']/stats['total']:.1f}%), "
              f"golden {golden}, {len(broken)} broken")
    sol_path.write_text(json.dumps(solutions, indent=1) + "\n")
    print(f"{made} tasks written")


if __name__ == "__main__":
    main()
