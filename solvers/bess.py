"""Grid-connected LFP battery energy storage system: knowledge-required systems chain.

Level 2 (bess) NAMES the methods and standards and gives the data; level 3 (bess3) names
nothing and adds hidden requirements. This module is the reference implementation of the
rules for both. Every check reports the computed value and the limit.

Design returned by the model (all ids from the task catalogs, counts are integers):
  cells_series, strings_parallel (one string per rack), pcs, pcs_count, transformer,
  string_fuse, string_contactor, dc_cable, dc_cables_parallel, cooling_unit, cooling_count
  (+ mv_switchgear at level 3)

Rules, as implemented (sources in docs/sources/bess.md and bess-vde.md):

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
    total price = cells + PCS + transformer + fuses + contactors + cables + cooling
    (+ switchgear), within task["objective"]["tolerance"] of the brute-force optimum

Level 3 (bess3), switched on by the task's own data; level-2 tasks carry none of it:

  Life (task["duty"]): SOH and resistance growth at end of service life are read from the cell's
    ageing tables at cycles = cycles_per_day x 365 x service_years, replacing the given 80 % / k_eol.
  Auxiliaries (task["aux"]): fed from the MV bus behind the connection point, so the plant must
    deliver P_net + P_aux, P_aux = rack_w N_p + site_kw + Q_heat / EER (fixed point with the string
    current); energy at the connection point is net: E_poi - P_aux x duration. The transformer
    carries the gross active power plus the connection-point reactive power.
  Voltage band (task["grid"]["u_min_pu"]): a current-limited PCS delivers S_rated x U/U_n, so
    S_pcs_site x u_min_pu >= S_pcs_needed.
  Winter (task["winter"]): the cell temperature needed to charge at rated power (net, after losses, nominal
    cell voltage: the least strict defensible reading) is read
    from the cell's charge-rate table; heating x count >= UA_rack N_p (T_needed - T_site_min).
  FCR (task["fcr"], PQ-Bedingungen v1.06 sec. 3.1.6, symmetric): power at the connection point
    >= 1.25 P_FCR and usable energy >= (1/2 + 1/4 + 1/6) h x P_FCR, each with the project margin.
  Deviations (task["deviations_allowed"]): string-cable overload coordination may be omitted when the design
    records a deviation citing IEC 60364-4-43 / DIN VDE 0100-430 clause 433.3 and the corrected ampacity covers
    the cell continuous limit the BMS enforces (the cable cannot be overloaded); otherwise the violation stands.
  MV switchgear (task["mv_switchgear"]): U_r >= highest system voltage; I_k = S_k / (sqrt3 U_n)
    + PCS AC fault contribution <= rated short-time current; kappa sqrt2 I_k <= making current,
    kappa = 1.02 + 0.98 exp(-3 R/X); rated current >= connection-point current.
"""
from __future__ import annotations

import math
import re

from objective import check_objective

FIELDS = ("cells_series", "strings_parallel", "pcs", "pcs_count", "transformer", "string_fuse",
          "string_contactor", "dc_cable", "dc_cables_parallel", "cooling_unit", "cooling_count")
INTS = ("cells_series", "strings_parallel", "pcs_count", "dc_cables_parallel", "cooling_count")
CATALOG = {"pcs": "pcs_catalog", "transformer": "transformers", "string_fuse": "fuses",
           "string_contactor": "contactors", "dc_cable": "cables", "cooling_unit": "cooling_units"}
SQ3 = math.sqrt(3)


def fields(task):
    return FIELDS + (("mv_switchgear",) if "mv_switchgear" in task else ())


def catalogs(task):
    return {**CATALOG, **({"mv_switchgear": "mv_switchgear"} if "mv_switchgear" in task else {})}


def _interp(points, x):
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _inverse(points, y):
    """Smallest x where a non-decreasing table reaches y; inf if it never does."""
    pts = sorted(points)
    if y <= pts[0][1]:
        return pts[0][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0) if y1 > y0 else x0
    return float("inf")


def _table(d):
    """{'35': 0.94, ...} -> [(35.0, 0.94), ...]"""
    return [(float(k), float(v)) for k, v in d.items()]


def _find(items, id_):
    return next(x for x in items if x["id"] == id_)


FCR_ENERGY_H = 0.5 + 0.25 + 1 / 6  # PQ-Bedingungen v1.06 sec. 3.1.6, symmetric: endangered state + max(prior call, lag) + reserve-mode bridging


def power_required(task):
    """Active power at the connection point incl. margin; FCR prequalification needs 1.25 x the FCR power."""
    p = task["params"]
    base = max(p["p_req_mw"], 1.25 * task["fcr"]["p_mw"]) if "fcr" in task else p["p_req_mw"]
    return base * 1e6 * (1 + p["margin_p"])


def energy_required(task):
    """Usable energy at the connection point incl. margin; FCR reserves FCR_ENERGY_H x the FCR power."""
    p = task["params"]
    base = max(p["e_req_mwh"], FCR_ENERGY_H * task["fcr"]["p_mw"]) if "fcr" in task else p["e_req_mwh"]
    return base * 1e6 * (1 + p["margin_e"])


def life(task):
    """(SOH, resistance factor) at end of life: given at level 2, from the ageing tables at level 3."""
    p, c = task["params"], task["cell"]
    if "duty" not in task:
        return p["soh_eol"], c["k_r_eol"]
    cycles = task["duty"]["cycles_per_day"] * 365 * p["service_years"]
    return _interp(_table(c["retention"]), cycles), _interp(_table(c["r_growth"]), cycles)


def string_point(ns, np_, p_dc, v_ocv, r_string):
    """String voltage under load and string current at the SOC floor (fixed point on the IR drop)."""
    v_load, i_s = ns * v_ocv, p_dc / (np_ * ns * v_ocv)
    for _ in range(50):
        v_new = ns * v_ocv - i_s * r_string
        if v_new <= 0:
            return 0.0, float("inf")
        i_new = p_dc / (np_ * v_new)
        if abs(i_new - i_s) < 1e-6:
            return v_new, i_new
        v_load, i_s = v_new, 0.5 * (i_s + i_new)
    return v_load, i_s


def aux_power(task, np_, q_heat):
    a = task.get("aux")
    return a["rack_w"] * np_ + a["site_kw"] * 1e3 + q_heat / a["eer"] if a else 0.0


def operating_point(task, ns, np_, pcs):
    """(gross AC power, aux power, v_load, i_string, q_heat): aux and string current solved together."""
    p, c = task["params"], task["cell"]
    _, k_r = life(task)
    p_net = power_required(task)
    r_string = ns * c["r_bol_ohm"] * k_r
    p_aux = 0.0
    for _ in range(30):
        p_ac = p_net + p_aux
        v_load, i_s = string_point(ns, np_, p_ac / pcs["eta"], c["v_ocv_soc_min"], r_string)
        q_heat = np_ * ns * i_s ** 2 * c["r_bol_ohm"] * k_r
        new = aux_power(task, np_, q_heat) if math.isfinite(q_heat) else 0.0
        if abs(new - p_aux) < 1e-3:
            break
        p_aux = new
    return p_ac, p_aux, v_load, i_s, q_heat


def grid_side(task, p_ac, tx):
    """(S at the connection point, Q there, transformer flow, Q_tx, PCS apparent power needed)."""
    p = task["params"]
    p_net = power_required(task)
    q_nap = p_net * math.tan(math.acos(p["cos_phi_min"]))
    s_nap = math.hypot(p_net, q_nap)
    s_tx_flow = math.hypot(p_ac, q_nap)  # aux on the MV bus behind the connection point
    q_tx = tx["u_k"] * s_tx_flow ** 2 / (tx["s_kva"] * 1e3)
    return s_nap, q_nap, s_tx_flow, q_tx, math.hypot(p_ac, q_nap + q_tx)


def charge_current(task, ns, np_, pcs):
    """String current charging at rated power: the least strict defensible reading (net power after the PCS and
    DC losses, nominal cell voltage). Hidden checks fail only designs that are wrong under every reasonable method."""
    c, p = task["cell"], task["params"]
    return power_required(task) * pcs["eta"] * p["eta_dc"] / (np_ * ns * c["v_nom"])


def heating_needed(task, ns, np_, pcs):
    """(cell temperature needed to charge at rated power, heating power needed)."""
    w = task.get("winter")
    if not w:
        return None, 0.0
    t_need = _inverse(_table(task["cell"]["charge_c_by_temp"]), charge_current(task, ns, np_, pcs) / task["cell"]["q_ah"])
    return t_need, w["ua_rack_w_per_k"] * np_ * max(0.0, t_need - task["site"]["t_min_c"])


def mv_fault(task, pcs, n_pcs, s_nap):
    """(I_k at the connection point, peak current, connection-point current), amperes."""
    g, u = task["grid"], task["site"]["grid_kv"] * 1e3
    i_k = g["s_k_mva"] * 1e6 / (SQ3 * u) + pcs["i_sc_ac_pu"] * pcs["s_kva_25"] * 1e3 * n_pcs / (SQ3 * u)
    kappa = 1.02 + 0.98 * math.exp(-3 * g["r_x"])
    return i_k, kappa * math.sqrt(2) * i_k, s_nap / (SQ3 * u)


OVERLOAD_STANDARD = re.compile(r"60364-?4-?43|0100-?430")  # IEC/HD/EN 60364-4-43 = DIN VDE 0100-430
OVERLOAD_EXEMPTION_CLAUSE = "433.3"  # omission of devices for protection against overload


def overload_deviation(task, output, m):
    """A recorded deviation from string-cable overload coordination (level 3). None when none is recorded,
    "" when it is accepted, otherwise why not: the clause must permit omitting overload protection and the
    cable must carry the most current the string can carry, the cell continuous limit the BMS enforces."""
    if not task.get("deviations_allowed"):
        return None
    cited = [x for x in output.get("deviations") or [] if isinstance(x, dict)
             and OVERLOAD_STANDARD.search(str(x.get("standard", "")).replace(" ", ""))]
    if not cited:
        return None
    if not any(str(x.get("clause", "")).strip().lstrip("§ ").startswith(OVERLOAD_EXEMPTION_CLAUSE) for x in cited):
        return "the cited clause does not permit omitting overload protection"
    i_limit = task["cell"]["c_cont"] * task["cell"]["q_ah"]
    if m["i_z_a"] < i_limit - 1e-9:
        return (f"the corrected cable ampacity {m['i_z_a']:.1f} A is below the {i_limit:.0f} A the string can carry "
                f"(cell continuous limit), so the cable can be overloaded")
    return ""


def evaluate(task: dict, d: dict) -> dict:
    p, c, s = task["params"], task["cell"], task["site"]
    ns, np_ = d["cells_series"], d["strings_parallel"]
    pcs, tx = _find(task["pcs_catalog"], d["pcs"]), _find(task["transformers"], d["transformer"])
    fu, ct = _find(task["fuses"], d["string_fuse"]), _find(task["contactors"], d["string_contactor"])
    cb, cu = _find(task["cables"], d["dc_cable"]), _find(task["cooling_units"], d["cooling_unit"])
    n_pcs, n_cab, n_cool = d["pcs_count"], d["dc_cables_parallel"], d["cooling_count"]
    soh, _ = life(task)

    p_ac, p_aux, v_min_load, i_string, q_heat = operating_point(task, ns, np_, pcs)
    # energy at the point of connection, end of life, net of auxiliaries
    e_poi = (ns * np_ * c["v_nom"] * c["q_ah"] * (c["soc_max"] - c["soc_min"]) * soh
             * p["eta_dc"] * pcs["eta"] * tx["eta"]) - p_aux * p["duration_h"]
    e_req = energy_required(task)
    v_max = ns * c["v_max"]

    u_min = task.get("grid", {}).get("u_min_pu", 1.0)
    s_pcs_site = _interp([(25.0, pcs["s_kva_25"]), (40.0, pcs["s_kva_40"]), (50.0, pcs["s_kva_50"])],
                         s["t_max_c"]) * 1e3 * n_pcs * u_min
    cooling = _interp([(35.0, cu["kw_35"]), (45.0, cu["kw_45"])], s["t_max_c"]) * 1e3 * n_cool
    t_need, heat_need = heating_needed(task, ns, np_, pcs)

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
    s_nap, q_nap, s_tx_flow, q_tx, s_pcs_needed = grid_side(task, p_ac, tx)
    k_amb_tx = _interp(_table(task["k_tx_ambient"]), s["t_annual_mean_c"])
    s_tx_site = tx["s_kva"] * 1e3 * k_amb_tx

    cost = (ns * np_ * c["price"] + n_pcs * pcs["price"] + tx["price"] + np_ * (fu["price"] + ct["price"])
            + np_ * n_cab * 2 * s["dc_route_m"] * cb["price_per_m"] + n_cool * cu["price"])
    m = {
        "e_poi_mwh": e_poi / 1e6, "e_req_mwh": e_req / 1e6, "p_ac_mw": p_ac / 1e6, "p_aux_kw": p_aux / 1e3,
        "soh_eol": soh, "i_string_a": i_string,
        "v_string_min_load": v_min_load, "v_string_max": v_max, "s_pcs_site_kva": s_pcs_site / 1e3,
        "s_pcs_needed_kva": s_pcs_needed / 1e3, "i_dc_total_a": np_ * i_string, "q_heat_kw": q_heat / 1e3,
        "cooling_kw": cooling / 1e3, "heating_kw": cu.get("heating_kw", 0.0) * n_cool, "heat_need_kw": heat_need / 1e3,
        "i_k_string_ka": i_k_string / 1e3, "i_fault_bus_ka": i_fault_bus / 1e3,
        "i_fuse_req_a": i_fuse_req, "i_z_a": i_z, "circuits": circuits, "v_drop_frac": v_drop_frac,
        "s_nap_kva": s_nap / 1e3, "s_tx_flow_kva": s_tx_flow / 1e3, "q_tx_kvar": q_tx / 1e3,
        "s_tx_site_kva": s_tx_site / 1e3,
    }
    if t_need is not None:
        m["t_cell_needed_c"] = t_need
    if "mv_switchgear" in task:
        i_k, i_p, i_nap = mv_fault(task, pcs, n_pcs, s_nap)
        m.update({"i_k_mv_ka": i_k / 1e3, "i_p_mv_ka": i_p / 1e3, "i_nap_a": i_nap})
        cost += _find(task["mv_switchgear"], d["mv_switchgear"])["price"]
    m["cost"] = cost
    return m


# Test-lab feedback for the agentic track: each check reports what a test or review on a real project would
# observe, never the rule, the cause or the numbers. Order matters: the first matching prefix wins.
SYMPTOMS = [
    ("usable energy", "End-of-life capacity test: the plant delivered less energy at the connection point than guaranteed."),
    ("string current", "Rated-power discharge test: the battery management system derated the plant because cell current exceeded the cell rating."),
    ("string voltage at end of life", "End-of-life discharge test at low state of charge: the PCS tripped on DC undervoltage before the rated energy was delivered."),
    ("string voltage at full charge", "Full-charge test: the PCS tripped on DC overvoltage."),
    ("total DC current", "Rated-power test: the PCS limited its DC input current and the plant could not reach rated power."),
    ("PCS apparent power", "Grid compliance and prequalification tests: the PCS could not deliver the active and reactive power required at the connection point under every test condition."),
    ("cooling capacity", "Summer heat-run at maximum ambient: cell temperatures exceeded the limit and the plant derated."),
    ("heating", "Winter commissioning at the site minimum temperature: the battery management system blocked charging at rated power because the cells were too cold."),
    ("string fuse class", "Protection review: the string fuses are not suited to clearing every overcurrent in a DC battery circuit."),
    ("fuse DC voltage rating", "Short-circuit test on a string: the fuse could not extinguish the DC arc."),
    ("fuse rated time constant", "Short-circuit test on a string: the fuse failed to interrupt and the arc persisted."),
    ("fuse breaking capacity", "Short-circuit test at the DC bus: a string fuse failed to interrupt and ruptured."),
    ("fuse rating", None),  # two different checks share this prefix; resolved below
    ("fuse conventional fusing current", "Overload trial: a string cable overheated before its fuse operated."),
    ("contactor rating", "Rated-power soak test: the string contactors overheated."),
    ("contactor DC voltage rating", "Switching test: a string contactor could not break the DC string voltage."),
    ("contactor maximum breaking current", "Fault test at moderate overcurrent: a string contactor opened but could not break the current before the fuse operated."),
    ("cable DC voltage rating", "Insulation test: a DC string cable is not rated for the string voltage."),
    ("DC cable voltage drop", "Rated-power test: the voltage drop on the DC string cables exceeded the project specification."),
    ("transformer", "Heat-run at rated power: the step-up transformer overheated."),
    ("switchgear rated voltage", "Type-test review: the medium-voltage switchgear is not rated for this network's voltage."),
    ("switchgear short-time current", "Network fault study: the medium-voltage switchgear cannot withstand the fault current at the connection point."),
    ("switchgear making current", "Network fault study: the medium-voltage switchgear cannot safely close onto a fault at the connection point."),
    ("switchgear rated current", "Heat-run: the medium-voltage switchgear overheated at rated current."),
    ("cost", "Commercial review: a competing design meets the same requirements for significantly less."),
]
DEVIATION_REJECTED = "Design review: a recorded deviation was not accepted for this design."


def symptom(violation: str) -> str | None:
    """The test-lab observation for one violation; None for format errors, which pass through unchanged."""
    if re.match(r"\d+ strings exceed", violation):
        return "Installation check: there are more battery strings than PCS DC inputs to connect them to."
    for prefix, text in SYMPTOMS:
        if violation.startswith(prefix):
            if prefix == "fuse rating":
                text = ("Overload trial: a string cable overheated before its fuse operated." if "exceeds the corrected cable"
                        in violation else "Rated-power soak test: string fuses operated during continuous full-power operation.")
            return text
    return None


def report(violations):
    """Deduplicated test report for the agentic track."""
    out = []
    for v in violations:
        s = symptom(v) or v
        extra = [DEVIATION_REJECTED] if "recorded deviation not accepted" in v else []
        out += [x for x in [s] + extra if x not in out]
    return out


def grade(task: dict, output: dict) -> dict:
    d = {k: output.get(k) for k in fields(task)}
    missing = [k for k in d if d[k] in (None, "")]
    if missing:
        return {"passed": False, "violations": [f"missing fields: {missing}"]}
    for k in INTS:
        try:
            d[k] = int(d[k])
        except (TypeError, ValueError):
            return {"passed": False, "violations": [f"{k} must be an integer"]}
        if d[k] < 1:
            return {"passed": False, "violations": [f"{k} must be >= 1"]}
    for k, cat in catalogs(task).items():
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
                 f"{m['e_req_mwh']:.3f} MWh required (E_req x (1 + margin))"
                 + (f"; state of health {m['soh_eol']:.3f}, auxiliaries {m['p_aux_kw']:.1f} kW" if "duty" in task else ""))
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
        band = f" at {task['grid']['u_min_pu']:g} pu grid voltage" if "grid" in task else ""
        v.append(f"PCS apparent power at site {s['t_max_c']:.0f} C{band} {m['s_pcs_site_kva']:.0f} kVA is below "
                 f"{m['s_pcs_needed_kva']:.0f} kVA needed for cos phi {p['cos_phi_min']} at the connection point "
                 f"including transformer reactive consumption {m['q_tx_kvar']:.0f} kvar")
    if m["cooling_kw"] < m["q_heat_kw"] * (1 + p["margin_p"]) * (1 - T):
        v.append(f"cooling capacity at site {s['t_max_c']:.0f} C {m['cooling_kw']:.1f} kW is below heat "
                 f"{m['q_heat_kw']:.1f} kW x (1 + margin) at end-of-life resistance")
    if m["heating_kw"] < m["heat_need_kw"] * (1 - T):
        v.append(f"heating {m['heating_kw']:.1f} kW is below {m['heat_need_kw']:.1f} kW needed to hold the cells at "
                 f"{m['t_cell_needed_c']:.1f} C (charge rate at rated charging power) at site minimum {s['t_min_c']:g} C")
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
    overload = []
    if fu["i_n"] > m["i_z_a"] + T:
        overload.append(f"fuse rating {fu['i_n']:.0f} A exceeds the corrected cable ampacity I_z {m['i_z_a']:.1f} A "
                        f"({d['dc_cables_parallel']} x {cb['i_z_base']} A x k_T x k_G for {m['circuits']} circuits)")
    elif 1.6 * fu["i_n"] > 1.45 * m["i_z_a"] + T:
        overload.append(f"fuse conventional fusing current 1.6 x {fu['i_n']:.0f} A = {1.6 * fu['i_n']:.0f} A exceeds "
                        f"1.45 x I_z = {1.45 * m['i_z_a']:.0f} A (IEC 60364-4-43 overload coordination)")
    if overload:
        why = overload_deviation(task, output, m)
        if why is None:
            v += overload
        elif why:
            v += [o + f"; recorded deviation not accepted: {why}" for o in overload]
    if m["v_drop_frac"] > p["v_drop_max"] + T:
        v.append(f"DC cable voltage drop {m['v_drop_frac'] * 100:.2f}% exceeds {p['v_drop_max'] * 100:.1f}%")
    # transformer
    if m["s_tx_site_kva"] < m["s_tx_flow_kva"] * (1 - T):
        v.append(f"transformer {tx['s_kva']:.0f} kVA x ambient factor = {m['s_tx_site_kva']:.0f} kVA is below "
                 f"{m['s_tx_flow_kva']:.0f} kVA through it (cos phi {p['cos_phi_min']} at the connection point)")
    # MV switchgear
    if "mv_switchgear" in task:
        sw, g = _find(task["mv_switchgear"], d["mv_switchgear"]), task["grid"]
        if sw["u_r_kv"] < g["u_max_kv"] - T:
            v.append(f"switchgear rated voltage {sw['u_r_kv']:g} kV is below the highest system voltage {g['u_max_kv']:g} kV")
        if sw["i_k_ka"] < m["i_k_mv_ka"] - T:
            v.append(f"switchgear short-time current {sw['i_k_ka']:g} kA is below the fault current {m['i_k_mv_ka']:.2f} kA "
                     f"(network short-circuit power plus PCS contribution)")
        if sw["i_ma_ka"] < m["i_p_mv_ka"] - T:
            v.append(f"switchgear making current {sw['i_ma_ka']:g} kA is below the peak fault current {m['i_p_mv_ka']:.2f} kA")
        if sw["i_r_a"] < m["i_nap_a"] - T:
            v.append(f"switchgear rated current {sw['i_r_a']:g} A is below the connection current {m['i_nap_a']:.0f} A")
    check_objective(task, m, v)
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
