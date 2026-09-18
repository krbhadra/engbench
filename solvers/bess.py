"""Grid-connected LFP battery energy storage system: knowledge-required systems chain.

The task NAMES the methods and standards and gives the data; it does not restate the
rules. This module is the reference implementation of those named rules. Every check
reports the computed value and the limit so the agentic track gets actionable feedback.

Design returned by the model (all ids from the task catalogs, counts are integers):
  cells_series, strings_parallel (one string per rack), pcs, pcs_count, transformer,
  string_fuse, string_contactor, dc_cable, dc_cables_parallel, cooling_unit, cooling_count

Named rules, as implemented (sources in docs/sources/bess.md and bess-vde.md):

  Energy (PNNL ESGC 2022 definitions, 80 % SOH end of life)
    E_poi = N_s N_p V_nom Q (SOC_max - SOC_min) SOH_eol eta_dc eta_pcs eta_tx   [Wh]
    require E_poi >= E_req (1 + m_E)
  Power and current
    P_dc  = P_req (1 + m_P) / eta_pcs ;  I_string = P_dc / (N_p V_string_min_load)
    V_string_min_load = N_s V_ocv(SOC_min) - I_string R_string_eol   (solved as a fixed point;
    the open-circuit voltage at the SOC floor, not the 2.5 V protection cutoff)
    R_string_eol = N_s R_cell_bol k_eol
    require I_string <= C_cont Q ; require sum PCS DC current limits >= N_p I_string
    require PCS apparent power at site T_max (linear interpolation of the 25/40/50 C
    columns) >= S_pcs_needed (see grid side)
  Voltage window
    require V_string_min_load >= V_dc_min(PCS) and N_s V_cell_max <= V_dc_max(PCS)
  Thermal
    Q_heat = N_p N_s I_string^2 R_cell_bol k_eol ; cooling capacity at site T_max
    (interpolated) x count >= Q_heat (1 + m_P)
  String fuse (IEC 60269-7 gBat, as described by SIBA / Mersen / ETI)
    class gBat ; U_n_dc >= N_s V_cell_max ; rated time constant >= circuit L/R ;
    I_n >= I_string / (k_amb(T_site_max) k_load) ;
    breaking capacity >= I_fault_bus, where per IEC 61660-1 (ABB carrier)
      R = 0.9 R_b + R_cable ; I_k_string = 0.95 E / (R + 0.1 R_b), E = N_s V_cell_max,
      R_b = N_s R_cell_bol ; I_fault_bus = (N_p - 1) I_k_string + I_sc_pcs (all units)
  Contactor
    I_rated >= I_string ; U_dc >= N_s V_cell_max ; max breaking current >= 2 I_n(fuse)
    (gBat minimum breaking current), so there is no interruption gap
  DC cable (DIN VDE 0298-4 / IEC 60364-5-52 with IEC 60364-4-43 coordination)
    I_b = I_string ; I_z = n_par I_z_base(2 loaded conductors, 30 C air) k_T(T_cable)
    k_G(circuits) with circuits = strings per tray x n_par ;
    require I_b <= I_n <= I_z and 1.6 I_n <= 1.45 I_z (I_2 of a g-type fuse) ;
    U_cable >= N_s V_cell_max ;
    voltage drop 2 I_string R'(70 C) L / n_par / V_string_min_load <= limit
  Grid side (VDE-AR-N 4110 at the connection point, IEC 60076-11 transformer)
    P_ac = P_req (1 + m_P) ; Q_nap = P_ac tan(acos cos_phi_min) ;
    S_nap = sqrt(P_ac^2 + Q_nap^2) ; Q_tx = u_k S_nap^2 / S_tx_rated ;
    S_pcs_needed = sqrt(P_ac^2 + (Q_nap + Q_tx)^2) ;
    require S_tx_rated k_amb(T_annual_mean) >= S_nap
  Interface
    strings <= PCS DC inputs x count ; every count >= 1 ; ids exist
  Objective
    total price = cells + PCS + transformer + fuses + contactors + cables + cooling,
    within task["objective"]["tolerance"] of the brute-force optimum
"""
from __future__ import annotations

import math

from objective import check_objective

FIELDS = ("cells_series", "strings_parallel", "pcs", "pcs_count", "transformer", "string_fuse",
          "string_contactor", "dc_cable", "dc_cables_parallel", "cooling_unit", "cooling_count")
INTS = ("cells_series", "strings_parallel", "pcs_count", "dc_cables_parallel", "cooling_count")
CATALOG = {"pcs": "pcs_catalog", "transformer": "transformers", "string_fuse": "fuses",
           "string_contactor": "contactors", "dc_cable": "cables", "cooling_unit": "cooling_units"}


def _interp(points, x):
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _table(d):
    """{'35': 0.94, ...} -> [(35.0, 0.94), ...]"""
    return [(float(k), float(v)) for k, v in d.items()]


def _find(items, id_):
    return next(x for x in items if x["id"] == id_)


def evaluate(task: dict, d: dict) -> dict:
    p, c, s = task["params"], task["cell"], task["site"]
    ns, np_ = d["cells_series"], d["strings_parallel"]
    pcs, tx = _find(task["pcs_catalog"], d["pcs"]), _find(task["transformers"], d["transformer"])
    fu, ct = _find(task["fuses"], d["string_fuse"]), _find(task["contactors"], d["string_contactor"])
    cb, cu = _find(task["cables"], d["dc_cable"]), _find(task["cooling_units"], d["cooling_unit"])
    n_pcs, n_cab, n_cool = d["pcs_count"], d["dc_cables_parallel"], d["cooling_count"]

    # energy at the point of connection, end of life
    e_poi = (ns * np_ * c["v_nom"] * c["q_ah"] * (c["soc_max"] - c["soc_min"]) * p["soh_eol"]
             * p["eta_dc"] * pcs["eta"] * tx["eta"])
    e_req = p["e_req_mwh"] * 1e6 * (1 + p["margin_e"])

    # power, string current with IR drop at EOL (fixed point)
    p_ac = p["p_req_mw"] * 1e6 * (1 + p["margin_p"])
    p_dc = p_ac / pcs["eta"]
    r_string_eol = ns * c["r_bol_ohm"] * c["k_r_eol"]
    v_min_load = ns * c["v_ocv_soc_min"]
    i_string = p_dc / (np_ * v_min_load)
    for _ in range(50):
        v_new = ns * c["v_ocv_soc_min"] - i_string * r_string_eol
        if v_new <= 0:
            v_min_load, i_string = 0.0, float("inf")
            break
        i_new = p_dc / (np_ * v_new)
        if abs(i_new - i_string) < 1e-6:
            v_min_load, i_string = v_new, i_new
            break
        v_min_load, i_string = v_new, 0.5 * (i_string + i_new)
    v_max = ns * c["v_max"]

    s_pcs_site = _interp([(25.0, pcs["s_kva_25"]), (40.0, pcs["s_kva_40"]), (50.0, pcs["s_kva_50"])], s["t_max_c"]) * 1e3 * n_pcs
    q_heat = np_ * ns * i_string ** 2 * c["r_bol_ohm"] * c["k_r_eol"]
    cooling = _interp([(35.0, cu["kw_35"]), (45.0, cu["kw_45"])], s["t_max_c"]) * 1e3 * n_cool

    # fault current, IEC 61660-1 battery branch
    r_b = ns * c["r_bol_ohm"]
    r_cable = cb["r_ohm_per_km"] * s["dc_route_m"] / 1000.0 * 2 / n_cab
    i_k_string = 0.95 * v_max / (0.9 * r_b + r_cable + 0.1 * r_b)
    i_fault_bus = (np_ - 1) * i_k_string + pcs["i_sc_ka"] * 1e3 * n_pcs

    # fuse and cable
    k_amb_fuse = _interp(_table(fu["k_amb"]), s["t_max_c"])
    i_fuse_req = i_string / (k_amb_fuse * p["k_load_fuse"])
    circuits = s["strings_per_tray"] * n_cab
    k_t = _interp(_table(task["k_temp"]), s["t_cable_c"])
    k_g = _interp(_table(task["k_group"]), circuits)
    i_z = n_cab * cb["i_z_base"] * k_t * k_g
    v_drop_frac = i_string * r_cable / v_min_load if v_min_load > 0 else float("inf")  # r_cable: both poles, / n_cab

    # grid side
    q_nap = p_ac * math.tan(math.acos(p["cos_phi_min"]))
    s_nap = math.hypot(p_ac, q_nap)
    q_tx = tx["u_k"] * s_nap ** 2 / (tx["s_kva"] * 1e3)
    s_pcs_needed = math.hypot(p_ac, q_nap + q_tx)
    k_amb_tx = _interp(_table(task["k_tx_ambient"]), s["t_annual_mean_c"])
    s_tx_site = tx["s_kva"] * 1e3 * k_amb_tx

    cost = (ns * np_ * c["price"] + n_pcs * pcs["price"] + tx["price"] + np_ * (fu["price"] + ct["price"])
            + np_ * n_cab * 2 * s["dc_route_m"] * cb["price_per_m"] + n_cool * cu["price"])
    return {
        "e_poi_mwh": e_poi / 1e6, "e_req_mwh": e_req / 1e6, "p_ac_mw": p_ac / 1e6, "i_string_a": i_string,
        "v_string_min_load": v_min_load, "v_string_max": v_max, "s_pcs_site_kva": s_pcs_site / 1e3,
        "s_pcs_needed_kva": s_pcs_needed / 1e3, "i_dc_total_a": np_ * i_string, "q_heat_kw": q_heat / 1e3,
        "cooling_kw": cooling / 1e3, "i_k_string_ka": i_k_string / 1e3, "i_fault_bus_ka": i_fault_bus / 1e3,
        "i_fuse_req_a": i_fuse_req, "i_z_a": i_z, "circuits": circuits, "v_drop_frac": v_drop_frac,
        "s_nap_kva": s_nap / 1e3, "q_tx_kvar": q_tx / 1e3, "s_tx_site_kva": s_tx_site / 1e3, "cost": cost,
    }


def grade(task: dict, output: dict) -> dict:
    d = {k: output.get(k) for k in FIELDS}
    missing = [k for k in FIELDS if d[k] in (None, "")]
    if missing:
        return {"passed": False, "violations": [f"missing fields: {missing}"]}
    for k in INTS:
        try:
            d[k] = int(d[k])
        except (TypeError, ValueError):
            return {"passed": False, "violations": [f"{k} must be an integer"]}
        if d[k] < 1:
            return {"passed": False, "violations": [f"{k} must be >= 1"]}
    for k, cat in CATALOG.items():
        if not any(x["id"] == d[k] for x in task[cat]):
            return {"passed": False, "violations": [f"unknown {k} id '{d[k]}'"]}

    p, c, s = task["params"], task["cell"], task["site"]
    pcs, tx = _find(task["pcs_catalog"], d["pcs"]), _find(task["transformers"], d["transformer"])
    fu, ct, cb = _find(task["fuses"], d["string_fuse"]), _find(task["contactors"], d["string_contactor"]), _find(task["cables"], d["dc_cable"])
    m = evaluate(task, d)
    v = []
    T = 1e-9
    if m["e_poi_mwh"] < m["e_req_mwh"] * (1 - T):
        v.append(f"usable energy at the connection point at end of life {m['e_poi_mwh']:.3f} MWh is below "
                 f"{m['e_req_mwh']:.3f} MWh required (E_req x (1 + margin))")
    if m["i_string_a"] > c["c_cont"] * c["q_ah"] + T:
        v.append(f"string current {m['i_string_a']:.1f} A exceeds the cell continuous limit {c['c_cont'] * c['q_ah']:.1f} A")
    if m["v_string_min_load"] < pcs["v_dc_min"] - T:
        v.append(f"string voltage at end of life, minimum SOC, full current {m['v_string_min_load']:.1f} V is below "
                 f"the PCS minimum {pcs['v_dc_min']:.0f} V")
    if m["v_string_max"] > pcs["v_dc_max"] + T:
        v.append(f"string voltage at full charge {m['v_string_max']:.1f} V exceeds the PCS maximum {pcs['v_dc_max']:.0f} V")
    if m["i_dc_total_a"] > pcs["i_dc_max"] * d["pcs_count"] + T:
        v.append(f"total DC current {m['i_dc_total_a']:.0f} A exceeds the PCS DC current limit {pcs['i_dc_max'] * d['pcs_count']:.0f} A")
    if d["strings_parallel"] > pcs["dc_inputs"] * d["pcs_count"]:
        v.append(f"{d['strings_parallel']} strings exceed {pcs['dc_inputs'] * d['pcs_count']} PCS DC inputs")
    if m["s_pcs_site_kva"] < m["s_pcs_needed_kva"] * (1 - T):
        v.append(f"PCS apparent power at site {s['t_max_c']:.0f} C {m['s_pcs_site_kva']:.0f} kVA is below "
                 f"{m['s_pcs_needed_kva']:.0f} kVA needed for cos phi {p['cos_phi_min']} at the connection point "
                 f"including transformer reactive consumption {m['q_tx_kvar']:.0f} kvar")
    if m["cooling_kw"] < m["q_heat_kw"] * (1 + p["margin_p"]) * (1 - T):
        v.append(f"cooling capacity at site {s['t_max_c']:.0f} C {m['cooling_kw']:.1f} kW is below heat "
                 f"{m['q_heat_kw']:.1f} kW x (1 + margin) at end-of-life resistance")
    # fuse
    if fu["class"] != "gBat":
        v.append(f"string fuse class {fu['class']} is not gBat (IEC 60269-7 full-range battery fuse)")
    if fu["u_dc"] < m["v_string_max"] - T:
        v.append(f"fuse DC voltage rating {fu['u_dc']:.0f} V is below the string maximum {m['v_string_max']:.1f} V")
    if fu["tau_ms"] < s["circuit_tau_ms"] - T:
        v.append(f"fuse rated time constant {fu['tau_ms']:g} ms is below the circuit L/R {s['circuit_tau_ms']:g} ms")
    if fu["i_n"] < m["i_fuse_req_a"] - T:
        v.append(f"fuse rating {fu['i_n']:.0f} A is below {m['i_fuse_req_a']:.1f} A required "
                 f"(I_string {m['i_string_a']:.1f} A / ambient factor / continuous-load factor {p['k_load_fuse']})")
    if fu["breaking_ka"] < m["i_fault_bus_ka"] - T:
        v.append(f"fuse breaking capacity {fu['breaking_ka']:.0f} kA is below the prospective bus fault current "
                 f"{m['i_fault_bus_ka']:.1f} kA ({d['strings_parallel'] - 1} other strings + PCS contribution)")
    # contactor
    if ct["i_rated"] < m["i_string_a"] - T:
        v.append(f"contactor rating {ct['i_rated']:.0f} A is below the string current {m['i_string_a']:.1f} A")
    if ct["u_dc"] < m["v_string_max"] - T:
        v.append(f"contactor DC voltage rating {ct['u_dc']:.0f} V is below the string maximum {m['v_string_max']:.1f} V")
    if ct["i_break_max"] < 2 * fu["i_n"] - T:
        v.append(f"contactor maximum breaking current {ct['i_break_max']:.0f} A is below the fuse minimum breaking "
                 f"current {2 * fu['i_n']:.0f} A (2 x I_n for gBat): interruption gap")
    # cable
    if cb["u_dc"] < m["v_string_max"] - T:
        v.append(f"cable DC voltage rating {cb['u_dc']:.0f} V is below the string maximum {m['v_string_max']:.1f} V")
    if fu["i_n"] > m["i_z_a"] + T:
        v.append(f"fuse rating {fu['i_n']:.0f} A exceeds the corrected cable ampacity I_z {m['i_z_a']:.1f} A "
                 f"({d['dc_cables_parallel']} x {cb['i_z_base']} A x k_T x k_G for {m['circuits']} circuits)")
    elif 1.6 * fu["i_n"] > 1.45 * m["i_z_a"] + T:
        v.append(f"fuse conventional fusing current 1.6 x {fu['i_n']:.0f} A = {1.6 * fu['i_n']:.0f} A exceeds "
                 f"1.45 x I_z = {1.45 * m['i_z_a']:.0f} A (IEC 60364-4-43 overload coordination)")
    if m["v_drop_frac"] > p["v_drop_max"] + T:
        v.append(f"DC cable voltage drop {m['v_drop_frac'] * 100:.2f}% exceeds {p['v_drop_max'] * 100:.1f}%")
    # transformer
    if m["s_tx_site_kva"] < m["s_nap_kva"] * (1 - T):
        v.append(f"transformer {tx['s_kva']:.0f} kVA x ambient factor = {m['s_tx_site_kva']:.0f} kVA is below "
                 f"{m['s_nap_kva']:.0f} kVA at the connection point (P / cos phi {p['cos_phi_min']})")
    check_objective(task, m, v)
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
