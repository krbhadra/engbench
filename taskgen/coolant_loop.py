"""Generate coolant_loop tasks: perturbed parameters, brute-forced optimum, derived broken cases.

    python taskgen/coolant_loop.py --seeds 1 2 3

Property tables come from CoolProp (INCOMP::Water, INCOMP::MEG-xx%) at generation
time only; the task carries the table and the grader interpolates it.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
import coolant_loop  # noqa: E402

COOLANTS = [("WATER", "INCOMP::Water", 0.0), ("MEG-30", "INCOMP::MEG-30%", None), ("MEG-50", "INCOMP::MEG-50%", None)]
PROP_TEMPS_C = (10.0, 30.0, 50.0)
PUMPS = [  # id, Qmax L/min, dP at shutoff Pa, rated electrical power W, price
    ("PMP-1", 4.0, 12_000, 8.0, 18.0),
    ("PMP-2", 8.0, 20_000, 16.0, 26.0),
    ("PMP-3", 14.0, 35_000, 35.0, 40.0),
    ("PMP-4", 22.0, 55_000, 70.0, 62.0),
    ("PMP-5", 32.0, 80_000, 130.0, 95.0),
]
TUBE_PRICE = {4: 1.0, 6: 1.3, 8: 1.8, 10: 2.4, 12: 3.2}  # per metre
SPEEDS = [round(0.3 + 0.05 * i, 2) for i in range(15)]  # 0.30 .. 1.00
N_PAR_MAX = 4
MIN_FEASIBLE_FRACTION = 0.002
MAX_FEASIBLE_FRACTION = 0.03
TOLERANCE = 0.05
MAX_NEAR_OPT_FRACTION = 0.25


def _r(rng, lo, hi, nd=3):
    return round(rng.uniform(lo, hi), nd)


def _coolant_tables():
    import CoolProp.CoolProp as CP
    out = []
    for cid, fluid, freeze in COOLANTS:
        rows = []
        for t in PROP_TEMPS_C:
            rho, cp, mu, k = (CP.PropsSI(x, "T", t + 273.15, "P", 2e5, fluid) for x in ("D", "C", "V", "L"))
            rows.append([t, round(rho, 1), round(cp, 0), round(mu, 6), round(k, 4)])
        fz = freeze if freeze is not None else round(CP.PropsSI("T_freeze", fluid) - 273.15, 1)
        out.append({"id": cid, "freeze_c": fz, "props": rows})
    return out


_TABLES = None


def make_task(seed: int) -> dict | None:
    global _TABLES
    if _TABLES is None:
        _TABLES = _coolant_tables()
    rng = random.Random(seed)
    n_cells = int(rng.choice([12, 16, 20, 24, 32, 48]))
    p = {
        "n_cells": n_cells, "i_cell_a": float(rng.choice([60, 80, 100, 120, 150])),
        "r_cell_ohm": _r(rng, 0.0004, 0.0012, 5), "r_cp_kw": _r(rng, 0.1, 0.4, 2),
        "t_in_c": float(rng.choice([15, 18, 20, 22, 25])), "t_site_min_c": float(rng.choice([5, -5, -10, -20, -30])),
        "l_ch_m": round(n_cells * _r(rng, 0.025, 0.045, 4), 3), "l_pipe_m": _r(rng, 2.0, 8.0, 2),
        "d_pipe_m": rng.choice([0.008, 0.010, 0.012]), "k_fittings": _r(rng, 4.0, 15.0, 1),
        "speed_min": 0.3, "n_parallel_max": N_PAR_MAX, "re_transition_band": [2000.0, 3000.0],
    }
    pumps = []
    for i, qmax, dp0, w, pr in PUMPS:
        sf = _r(rng, 0.85, 1.15, 3)
        q, h = qmax * sf, dp0 * sf
        pumps.append({"id": i, "curve": [[0, round(h)], [round(0.5 * q, 2), round(0.8 * h)], [round(0.8 * q, 2), round(0.45 * h)], [round(q, 2), 0]],
                      "power_w": round(w * _r(rng, 0.9, 1.1, 3), 1), "price": round(pr * _r(rng, 0.85, 1.15, 2), 2)})
    tube = {str(d): round(v * _r(rng, 0.85, 1.15, 2), 2) for d, v in TUBE_PRICE.items()}
    task = {"id": f"coolant_loop_{seed:03d}", "domain": "coolant_loop", "params": p, "limits": {},
            "coolants": _TABLES, "pumps": pumps, "tube_price_per_m": tube}

    pool = []
    for c, pm, s, d, n in itertools.product(_TABLES, pumps, SPEEDS, TUBE_PRICE, range(1, N_PAR_MAX + 1)):
        if c["freeze_c"] > p["t_site_min_c"]:
            continue
        design = {"coolant": c["id"], "pump": pm["id"], "speed": s, "channel_d_mm": d, "n_parallel": n}
        m = coolant_loop.evaluate(task, design)
        if not (p["re_transition_band"][0] < m["re"] < p["re_transition_band"][1]):
            pool.append((design, m))
    total = len(_TABLES) * len(pumps) * len(SPEEDS) * len(TUBE_PRICE) * N_PAR_MAX
    if len(pool) < 50:
        return None

    cells = sorted(m["t_cell"] for _, m in pool)
    costs = sorted(m["cost"] for _, m in pool)
    lim = feasible = None
    for _ in range(60):
        cand = {
            "t_cell_max_c": round(cells[int(len(cells) * rng.uniform(0.05, 0.5))] // 0.5 * 0.5, 1),
            "dt_coolant_max_c": float(rng.choice([3, 4, 5, 6, 8])),
            "v_max_ms": float(rng.choice([1.0, 1.5, 2.0])),
            "pump_power_max_w": float(rng.choice([10, 15, 20, 30, 50])),
            "cost_max": float(round(costs[int(len(costs) * rng.uniform(0.1, 0.7))] + 0.5)),
        }
        ok = [(m["pump_power_w"], m["cost"], d) for d, m in pool
              if m["t_cell"] <= cand["t_cell_max_c"] and m["t_out"] - p["t_in_c"] <= cand["dt_coolant_max_c"]
              and m["v_ms"] <= cand["v_max_ms"] and m["pump_power_w"] <= cand["pump_power_max_w"] and m["cost"] <= cand["cost_max"]]
        if ok and MIN_FEASIBLE_FRACTION <= len(ok) / total <= MAX_FEASIBLE_FRACTION:
            lim, feasible = cand, ok
            break
    if lim is None:
        return None
    task["limits"] = lim
    feasible.sort(key=lambda t: (t[0], t[1]))
    golden = feasible[0][2]
    task["objective"] = {"minimize": "pump_power_w", "optimum": round(feasible[0][0], 4), "tolerance": TOLERANCE}
    near_opt = sum(1 for w, _, _ in feasible if w <= feasible[0][0] * (1 + TOLERANCE))
    if near_opt > MAX_NEAR_OPT_FRACTION * len(feasible):
        return None

    broken = []
    for cand, note in [
        ({**golden, "coolant": "WATER"}, "plain water"),
        ({**golden, "speed": 1.0}, "full speed"),
        ({**golden, "speed": 0.3}, "minimum speed"),
        ({**golden, "channel_d_mm": 4, "n_parallel": 1}, "one thin channel"),
        ({**golden, "pump": "PMP-5"}, "biggest pump"),
        (feasible[-1][2], "feasible but highest pump power"),
    ]:
        if cand == golden:
            continue
        r = coolant_loop.grade(task, cand)
        if not r["passed"]:
            broken.append({"output": cand, "expect": r["violations"][0].split(" ")[0], "note": note})
    if len(broken) < 2:
        return None
    task["_golden"], task["_broken"] = golden, broken
    task["_stats"] = {"feasible": len(feasible), "near_opt": near_opt, "total": total}
    return task


def describe(t: dict) -> str:
    p, lim = t["params"], t["limits"]
    cools = "\n".join(
        f"  {c['id']}: freeze point {c['freeze_c']:g} C; at T = {', '.join(f'{r[0]:g}' for r in c['props'])} C: "
        f"rho = {' / '.join(f'{r[1]:g}' for r in c['props'])} kg/m3, cp = {' / '.join(f'{r[2]:g}' for r in c['props'])} J/(kg K), "
        f"mu = {' / '.join(f'{r[3]*1e3:.3f}' for r in c['props'])} mPa s, k = {' / '.join(f'{r[4]:g}' for r in c['props'])} W/(m K)"
        for c in t["coolants"])
    pumps = "\n".join(f"  {pm['id']}: pressure vs flow at full speed {pm['curve']} (L/min, Pa), rated electrical power {pm['power_w']} W, price {pm['price']:.2f}"
                      for pm in t["pumps"])
    tube = ", ".join(f"{d} mm at {v:.2f}/m" for d, v in sorted(t["tube_price_per_m"].items(), key=lambda kv: int(kv[0])))
    return (
        f"Design the liquid cooling loop for a battery module of {p['n_cells']} cells on one cold plate. Each cell carries "
        f"I = {p['i_cell_a']:g} A through R_cell = {p['r_cell_ohm']*1e3:.2f} mOhm, so q_cell = I^2 * R_cell and the plate absorbs "
        f"Q_heat = N_cells * q_cell. Choose a coolant, a pump, the pump speed fraction s ({p['speed_min']:g} to 1.0), the cold-plate channel "
        f"inner diameter d, and the number of parallel channels n_par (1 to {p['n_parallel_max']}).\n\n"
        f"Cold plate: n_par identical channels of diameter d and length L_ch = {p['l_ch_m']:g} m in parallel; the flow and the heat split "
        f"equally between them. Loop piping: one run of inner diameter {p['d_pipe_m']*1e3:g} mm, length {p['l_pipe_m']:g} m, total fittings "
        f"loss coefficient K = {p['k_fittings']:g}, carrying the whole flow. Coolant enters the plate at T_in = {p['t_in_c']:g} C (chiller).\n\n"
        f"Hydraulics: v = (Qv / n_par) / (pi d^2 / 4), Re = rho v d / mu. Friction factor f = 64 / Re for Re < 2300, else Blasius f = 0.316 Re^-0.25. "
        f"dP_channel = f (L_ch / d) rho v^2 / 2. dP_pipe = (f_pipe L_pipe / d_pipe + K) rho v_pipe^2 / 2 with the pipe's own Re and f. "
        f"dP_system = dP_channel + dP_pipe. Pump at speed fraction s follows the affinity laws: dP_pump(Qv) = s^2 * curve(Qv / s), electrical "
        f"power P_pump = P_rated * s^3, where curve() is the full-speed pressure vs flow table interpolated linearly. The operating point is "
        f"where dP_pump = dP_system.\n\n"
        f"Thermal: T_out = T_in + Q_heat / (rho Qv cp). Pr = mu cp / k. Nu = 4.36 for Re < 2300, else Dittus-Boelter Nu = 0.023 Re^0.8 Pr^0.4. "
        f"h = Nu k / d. Heat flux per channel q'' = (Q_heat / n_par) / (pi d L_ch). Hottest cell (at the outlet): "
        f"T_cell = T_out + q'' / h + q_cell * R_cp with cell-to-plate resistance R_cp = {p['r_cp_kw']:g} K/W.\n\n"
        f"Properties: evaluate rho, cp, mu, k at T_mean = (T_in + T_out) / 2 by linear interpolation in the table below, clamped outside it. "
        f"T_out depends on the properties, so solve self-consistently.\n\n"
        f"Constraints: coolant freeze point <= site minimum temperature {p['t_site_min_c']:g} C; channel Re must be <= {p['re_transition_band'][0]:g} "
        f"or >= {p['re_transition_band'][1]:g} (no transitional flow); T_cell <= {lim['t_cell_max_c']:g} C; "
        f"T_out - T_in <= {lim['dt_coolant_max_c']:g} C; channel velocity v <= {lim['v_max_ms']:g} m/s; P_pump <= {lim['pump_power_max_w']:g} W; "
        f"cost = pump price + n_par * L_ch * tube price per metre <= {lim['cost_max']:g}.\n\n"
        f"Coolants:\n{cools}\n\nPumps:\n{pumps}\n\nChannel tube (inner diameter, price per metre): {tube}.\n\n"
        f"Objective: minimize pump electrical power P_pump. A design passes only if it meets every constraint AND its P_pump is within "
        f"{t['objective']['tolerance']*100:.0f}% of the lowest P_pump among designs that meet every constraint. Return "
        f"{{\"coolant\": \"<id>\", \"pump\": \"<id>\", \"speed\": <0.3-1.0>, \"channel_d_mm\": <4|6|8|10|12>, \"n_parallel\": <1-{p['n_parallel_max']}>}}."
    )


OUTPUT_SHAPE = '{"coolant": "<catalog id>", "pump": "<catalog id>", "speed": <fraction 0.3-1.0>, "channel_d_mm": <4|6|8|10|12>, "n_parallel": <integer>}'
SOURCES = [
    "NREL/CP-540-40446 Kim & Pesaran 2006, Battery Thermal Management System Design Modeling (US Gov): channel-cooling archetype, property-table pattern",
    "DOE/AMO Improving Pumping System Performance sourcebook (US Gov): pump affinity laws",
    "CoolProp incompressible library (MIT): INCOMP::Water, INCOMP::MEG-30%, INCOMP::MEG-50% property tables and freeze points",
    "Dittus & Boelter 1930 (Univ. California Publ. Eng.) and Blasius 1913: turbulent tube correlations; laminar Nu = 4.36 (constant heat flux)",
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
        t.update({"title": "Battery module coolant loop", "description": describe(t),
                  "output_shape": OUTPUT_SHAPE, "sources": SOURCES, "seed": seed,
                  "disciplines": ["thermal", "fluids"]})
        (ROOT / "tasks" / f"{t['id']}.json").write_text(json.dumps(t, indent=2) + "\n")
        solutions[t["id"]] = {"golden": golden, "broken": [{"output": b["output"], "expect": b["expect"]} for b in broken]}
        made += 1
        print(f"{t['id']}: feasible {stats['feasible']}/{stats['total']} ({100*stats['feasible']/stats['total']:.2f}%), "
              f"near-optimal {stats['near_opt']}, golden {golden}, {len(broken)} broken")
    sol_path.write_text(json.dumps(solutions, indent=1) + "\n")
    print(f"{made} tasks written")


if __name__ == "__main__":
    main()
