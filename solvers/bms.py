"""Battery management and DC protection for a storage plant that closes at level 3 (bms4, level 4).

The plant is handed over (task["plant"]); the model designs the BMS around it and writes down the
requirements it derives. Every check reports the computed value and the limit. Spec: docs/families/bms4.md.

Design returned by the model:
  requirements: [{id, parent, value, unit, basis}], afe, afe_per_module, chains_per_rack,
  current_sensor, mcu, string_contactor, precharge_resistor, balancing ("internal" or an external stage id),
  hold_up ("none" or a module id), imd_location ("plant" or "rack"), imd

Rules, as implemented (H = hidden: the brief never states it):

  Monitoring: afe_per_module x channels >= cells per module and x temperature inputs >= sensors per module;
    chips per chain = ceil(modules x afe_per_module / chains) <= the chip's maximum chain length.
  H3 Reaction time: scan = conversion + chips per chain x readout per chip;
    filter samples x scan + MCU cycle + contactor opening <= the cell's over-voltage disconnect time.
  H7 MCU: chain ports >= chains, CAN ports >= the plant's, ADC channels >= the plant's.
  H1 + H2 SOC error at the end of a recalibration interval (root sum of squares, the least strict reading):
    anchor = chip voltage error over its full temperature range / OCV slope at the recalibration SOC
             (the steeper of the two table segments at that point)
    offset = sensor residual offset x hours between recalibrations / end-of-life Ah
    gain   = sensor gain error x the SOC window
    the plant must still deliver its required energy with the window narrowed by 2 x SOC error:
      (E_poi + E_aux) (W - 2 e) / W - E_aux >= E_req
  H4 Fuse, contactor and cells: R-BRK is the lowest current from which the fuse alone clears within the
    cell's short-time current limit at every higher current (to the top of the fuse table). The BMS opens
    the contactor below it (least strict reading: it hands over to the fuse exactly there), so the contactor
    must break R-BRK, the sensor must measure it, and MCU cycle + opening time must be within the cell limit
    at every current from the BMS trip to R-BRK. Contactor rated current >= string current, DC voltage >= string max.
  H5 Precharge: R C ln(1/delta) <= time allowed; V_max / R <= precharge relay peak; 1/2 C V_max^2 and
    V_max^2 / R x the abort check time (precharge into a shorted DC link) both <= the resistor pulse energy.
  H6 Balancing: cell-to-cell self-discharge spread at the operating cell temperature (datasheet table, read geometrically)
    x Ah / 30 days / balancing hours per day <= balancing current.
  Requirements: each record must exist, trace to an allowed parent, and its value must follow from the
    data: a maximum may be up to 20 % stricter and 2 % looser, a minimum up to 25 % stricter and 2 % looser.
  H8 Ride-through (cross-functional: grid code, auxiliary power, BMS hardware): the rack's 24 V comes from the
    auxiliary supply, which follows the connection-point voltage through the operator's fault sequence,
    including a reclose onto the fault. Hold-up energy >= (MCU + contactor coil hold + current sensor
    [+ rack insulation monitor]) W x R-RIDE.
  H9 Insulation monitoring (power electronics, installation, BMS, safety): transformerless PCS on one unearthed
    LV winding make the whole DC side one IT system, so one plant-level monitor, rated for the earth
    capacitance of all racks, PCS and cables (R-IMD). Rack-level monitors interfere.
  Objective: BMS and protection price for the plant within tolerance of the brute-force optimum.
"""
from __future__ import annotations

import math
from functools import lru_cache

from objective import check_objective

FIELDS = ("requirements", "afe", "afe_per_module", "chains_per_rack", "current_sensor", "mcu",
          "string_contactor", "precharge_resistor", "balancing", "hold_up", "imd_location", "imd")
INTS = ("afe_per_module", "chains_per_rack")
CATALOG = {"afe": "afes", "current_sensor": "current_sensors", "mcu": "mcus",
           "string_contactor": "contactors", "precharge_resistor": "precharge_resistors", "imd": "imds"}
REQUIREMENTS = {  # id -> (quantity, unit, "max" or "min")
    "R-SOC": ("SOC error", "%", "max"),
    "R-TRIP": ("over-voltage disconnect time", "ms", "max"),
    "R-PRE": ("precharge time", "s", "max"),
    "R-BAL": ("balancing current", "mA", "min"),
    "R-BRK": ("contactor DC breaking current", "A", "min"),
    "R-RIDE": ("rack control supply bridging time", "s", "min"),
    "R-IMD": ("insulation monitor system capacitance rating", "uF", "min"),
}
STRICTER = {"max": 0.20, "min": 0.25}
LOOSER = 0.02


def _interp(points, x):
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


@lru_cache(maxsize=256)
def _logpts(items):
    return sorted((math.log(float(k)), math.log(float(v))) for k, v in items)


def _loglog(table, x):
    """Time-current tables are straight lines on log-log paper."""
    return math.exp(_interp(_logpts(tuple(table.items())), math.log(x)))


def _table(d):
    return [(float(k), float(v)) for k, v in d.items()]


def _find(items, id_):
    return next(x for x in items if x["id"] == id_)


def ocv_slope(cell, soc_pct):
    """mV per % SOC at the recalibration point: the steeper adjacent table segment (least strict)."""
    pts = sorted(_table(cell["ocv"]))
    slopes = [(v1 - v0) / (s1 - s0) * 1e3 for (s0, v0), (s1, v1) in zip(pts, pts[1:]) if s0 <= soc_pct <= s1]
    return max(slopes)


def soc_error(task, afe, sensor):
    """(total, anchor, offset, gain) SOC error in % at the end of a recalibration interval."""
    pl, c, o = task["plant"], task["cell"], task["operations"]
    anchor = afe["err_full_mv"] / ocv_slope(c, o["recal_soc_pct"])
    offset = sensor["offset_a"] * o["recal_interval_h"] / pl["q_eol_ah"] * 100
    gain = sensor["gain_pct"] / 100 * pl["soc_window_pct"]
    return math.sqrt(anchor ** 2 + offset ** 2 + gain ** 2), anchor, offset, gain


def soc_error_allowed(task):
    """R-SOC: the largest SOC error that still delivers the required energy with the window narrowed by 2e."""
    pl = task["plant"]
    return pl["soc_window_pct"] / 2 * (1 - (pl["e_req_mwh"] + pl["e_aux_mwh"]) / (pl["e_poi_mwh"] + pl["e_aux_mwh"]))


def trip_time(task, afe, chains, n_afe, mcu, contactor):
    """(reaction ms, chips per chain)."""
    per_chain = math.ceil(task["plant"]["modules_per_string"] * n_afe / chains)
    scan = afe["t_conv_ms"] + per_chain * afe["t_read_ms"]
    return task["firmware"]["filter_samples"] * scan + mcu["cycle_ms"] + contactor["t_open_ms"], per_chain


def precharge_time_allowed(task):
    return task["needs"]["dc_ready_s"] - task["firmware"]["startup_overhead_s"]


def balancing_needed_ma(task):
    """Self-discharge doubles about every 10 K, so the table is read geometrically between its points (linear
    interpolation of an exponential overstates it; found in the Opus 5.5 pilot, 2026-10-27)."""
    c, o = task["cell"], task["operations"]
    spread = math.exp(_interp([(t, math.log(x)) for t, x in _table(c["self_discharge_spread_pct_month"])], o["cell_temp_c"]))
    return spread / 100 * c["q_ah"] / 30 / o["balancing_h_per_day"] * 1e3


def breaking_needed(task):
    """R-BRK: the lowest current from which the string fuse alone clears within the cell's short-time limit
    at every higher current (to the top of the fuse table). Below it the contactor must break."""
    pl, c = task["plant"], task["cell"]
    fuse, i_n = pl["fuse_curve_s"], pl["fuse_i_n"]
    lo, hi = task["firmware"]["oc_trip_a"], max(float(k) for k in fuse) * i_n
    ok = lambda i: _loglog(fuse, i / i_n) <= _loglog(c["pulse_limit_s"], i / c["q_ah"])  # noqa: E731
    grid = [lo * (hi / lo) ** (k / 400) for k in range(401)]
    bad = [i for i in grid if not ok(i)]
    if not bad:
        return lo
    a, b = max(bad), next((i for i in grid if i > max(bad)), hi)  # last failing grid point, first passing above it
    for _ in range(60):  # bisect the crossing
        m = (a + b) / 2
        a, b = (m, b) if not ok(m) else (a, m)
    return b


def coordination(task, contactor, mcu, hand_over=None):
    """Currents where the cells are overstressed: [(current, clearing time, cell limit)]. The least strict
    reading: the BMS hands over to the fuse at R-BRK (the lowest current the fuse alone covers), so the
    contactor must break up to there and open fast enough below it."""
    pl, c = task["plant"], task["cell"]
    fuse, i_n = pl["fuse_curve_s"], pl["fuse_i_n"]
    lo, hand_over = task["firmware"]["oc_trip_a"], hand_over or breaking_needed(task)
    t_bms = (mcu["cycle_ms"] + contactor["t_open_ms"]) / 1e3
    bad = []
    for k in range(201):
        i = lo * (hand_over / lo) ** (k / 200)
        limit = _loglog(c["pulse_limit_s"], i / c["q_ah"])
        if t_bms > limit * (1 + 1e-9):
            bad.append((i, t_bms, limit))
    if contactor["i_break_a"] < hand_over * (1 - 1e-9):  # the fuse alone must cover every current above the contactor
        grid = [contactor["i_break_a"] * (hand_over / contactor["i_break_a"]) ** (k / 200) for k in range(201)]
        bad += [(i, _loglog(fuse, i / i_n), lim) for i in grid
                if _loglog(fuse, i / i_n) > (lim := _loglog(c["pulse_limit_s"], i / c["q_ah"])) * (1 + 1e-9)]
    return bad


def ride_time(task, reclose=True):
    """R-RIDE: how long the rack's 24 V must be bridged through the operator's fault sequence. The auxiliary
    supply follows the connection-point voltage; the power supply works above u_min and holds up for its
    hold-up time after that. Buffers do not recharge within a reclose dead time."""
    f, psu = task["grid_fault"], task["aux_supply"]
    low = f["t_fault_s"] + max(0.0, psu["u_min_pu"] - f["u_ret_pu"]) / (0.9 - f["u_ret_pu"]) * f["t_recover_s"]
    if not reclose:
        return max(0.0, low - psu["hold_up_s"])
    second = f["t_fault_s"] + f["t_dead_s"]  # reclose onto the fault: the same dip again
    if second < low:  # the supply never came back between the dips
        return max(0.0, second + low - psu["hold_up_s"])
    return 2 * max(0.0, low - psu["hold_up_s"])


def system_capacitance_uf(task):
    """Earth capacitance of the one galvanically connected DC system (transformerless PCS on a shared,
    unearthed LV winding): every rack, every PCS and every DC cable."""
    pl, e = task["plant"], task["earthing"]
    cables = pl["strings_parallel"] * 2 * pl["dc_route_m"] * e["cable_nf_per_m"] / 1e3
    return pl["strings_parallel"] * e["rack_uf"] + pl["pcs_count"] * e["pcs_uf"] + cables


def rack_power_w(task, d, with_coil=True):
    """24 V load per rack that the hold-up must carry."""
    w = _find(task["mcus"], d["mcu"])["w"]
    if with_coil:
        w += _find(task["contactors"], d["string_contactor"])["hold_w"] + _find(task["current_sensors"], d["current_sensor"])["w"]
    if d["imd_location"] == "rack":
        w += _find(task["imds"], d["imd"])["w"]
    return w


def derived(task):
    """The solver's own derivation of every graded requirement."""
    return {"R-SOC": soc_error_allowed(task), "R-TRIP": task["cell"]["ov_disconnect_ms"],
            "R-PRE": precharge_time_allowed(task), "R-BAL": balancing_needed_ma(task), "R-BRK": breaking_needed(task),
            "R-RIDE": ride_time(task), "R-IMD": system_capacitance_uf(task)}


def parents(task):
    return {"R-SOC": {"SN-1", "SN-2"} if "fcr_mw" in task["plant"] else {"SN-1"}, "R-TRIP": {"SN-4"},
            "R-PRE": {"SN-3"}, "R-BAL": {"SN-1", "SN-4"}, "R-BRK": {"SN-4"}, "R-RIDE": {"SN-6"}, "R-IMD": {"SN-4", "SN-6"}}


# needs a record must name together: insulation monitoring serves safety and the connection and installation rules (author)
ALL_PARENTS = {"R-IMD"}


def check_requirements(task, records):
    v = []
    if not isinstance(records, list):
        return ["requirements must be a list of records"]
    by_id = {str(r.get("id", "")).strip().upper(): r for r in records if isinstance(r, dict)}
    want, allowed = derived(task), parents(task)
    for rid, (quantity, unit, kind) in REQUIREMENTS.items():
        r = by_id.get(rid)
        if r is None:
            v.append(f"requirement {rid} ({quantity}) is missing")
            continue
        p = r.get("parent", "")
        named = {str(x).strip().upper() for x in (p if isinstance(p, list) else [p])}  # one need or several
        join = " and " if rid in ALL_PARENTS else " or "
        if not named or not named <= allowed[rid]:
            v.append(f"requirement {rid} parent '{p}' is not the stakeholder need it derives from "
                     f"({join.join(sorted(allowed[rid]))})")
        elif rid in ALL_PARENTS and named != allowed[rid]:
            v.append(f"requirement {rid} parent '{p}' does not name every stakeholder need it derives from "
                     f"({join.join(sorted(allowed[rid]))})")
        try:
            x = float(r.get("value"))
        except (TypeError, ValueError):
            v.append(f"requirement {rid} value is not a number")
            continue
        d = want[rid]
        lo, hi = (d * (1 - STRICTER[kind]), d * (1 + LOOSER)) if kind == "max" else (d * (1 - LOOSER), d * (1 + STRICTER[kind]))
        if not lo - 1e-9 <= x <= hi + 1e-9:
            v.append(f"requirement {rid} value {x:g} {unit} does not follow from the data (derived {d:.4g} {unit}, "
                     f"{kind}imum)")
    return v


def cost(task, d):
    pl = task["plant"]
    afe = _find(task["afes"], d["afe"])
    bal = 0.0 if d["balancing"] == "internal" else _find(task["balancing_stages"], d["balancing"])["price"]
    hold = 0.0 if d["hold_up"] == "none" else _find(task["hold_ups"], d["hold_up"])["price"]
    imd = _find(task["imds"], d["imd"])["price"]
    per_rack = (pl["modules_per_string"] * (d["afe_per_module"] * afe["price"] + bal) + hold
                + sum(_find(task[CATALOG[k]], d[k])["price"] for k in ("current_sensor", "mcu", "string_contactor", "precharge_resistor"))
                + (imd if d["imd_location"] == "rack" else 0.0))
    return pl["strings_parallel"] * per_rack + (imd if d["imd_location"] == "plant" else 0.0)


def evaluate(task, d):
    pl, c, fw = task["plant"], task["cell"], task["firmware"]
    afe, sensor, mcu = _find(task["afes"], d["afe"]), _find(task["current_sensors"], d["current_sensor"]), _find(task["mcus"], d["mcu"])
    ct, pr = _find(task["contactors"], d["string_contactor"]), _find(task["precharge_resistors"], d["precharge_resistor"])
    t_react, per_chain = trip_time(task, afe, d["chains_per_rack"], d["afe_per_module"], mcu, ct)
    e, anchor, offset, gain = soc_error(task, afe, sensor)
    i_bal = afe["bal_internal_ma"] if d["balancing"] == "internal" else _find(task["balancing_stages"], d["balancing"])["i_ma"]
    c_dc, v = pl["dc_link_mf"] * 1e-3, pl["v_string_max"]
    return {
        "t_react_ms": t_react, "chips_per_chain": per_chain, "soc_error_pct": e, "soc_anchor_pct": anchor,
        "soc_offset_pct": offset, "soc_gain_pct": gain, "soc_error_allowed_pct": soc_error_allowed(task),
        "i_bal_ma": i_bal, "i_bal_needed_ma": balancing_needed_ma(task),
        "t_pre_s": pr["ohm"] * c_dc * math.log(1 / fw["precharge_delta"]), "t_pre_allowed_s": precharge_time_allowed(task),
        "i_pre_peak_a": v / pr["ohm"], "e_pre_j": 0.5 * c_dc * v ** 2, "e_short_j": v ** 2 / pr["ohm"] * fw["precharge_check_s"],
        "rack_w": rack_power_w(task, d), "t_ride_s": ride_time(task),
        "hold_j": 0.0 if d["hold_up"] == "none" else _find(task["hold_ups"], d["hold_up"])["j"],
        "c_system_uf": system_capacitance_uf(task), "cost": cost(task, d),
    }


# Test-lab feedback: what a test or review would observe, never the cause or the numbers. First prefix wins.
SYMPTOMS = [
    ("requirement ", None),  # names the record and what is wrong with it, as a reviewer would; resolved below
    ("monitoring channels", "Module inspection: some cell voltages or temperature sensors are not connected to any monitoring channel."),
    ("daisy chain", "Bench test: the monitoring daisy chain lost communication with the far end of the rack."),
    ("over-voltage reaction", "Overcharge fault-injection test: the string was disconnected too late; a cell stayed above its safety limit longer than the cell manufacturer allows."),
    ("MCU", "Integration test: the rack controller does not have enough interfaces for the monitoring chains, communications and measurements."),
    ("SOC error", None),  # FCR or energy wording; resolved below
    ("overcurrent", "Overcurrent test between the BMS trip level and the fuse range: the cells exceeded their short-time current limit before the circuit was interrupted."),
    ("current sensor range", "Overcurrent test: the current measurement saturated, so the battery management system could not tell whether the contactor could safely open."),
    ("contactor rating", "Rated-power soak test: the string contactors overheated."),
    ("contactor DC voltage", "Switching test: a string contactor could not break the DC string voltage."),
    ("precharge time", "Start-up test: the DC bus was not ready within the required start-up time."),
    ("precharge peak", "Start-up test: the precharge relay welded from the inrush current."),
    ("precharge energy", "Repeated start-up test: the precharge resistor overheated and failed."),
    ("precharge into a short", "Fault-injection test, precharge into a shorted DC link: the precharge resistor burned open."),
    ("balancing", "Long-term operation test (one simulated year): cell voltages drifted apart and usable capacity shrank; balancing could not keep up."),
    ("rack control supply", "Grid-fault ride-through test with automatic reclosing: strings dropped off the DC bus and the plant disconnected."),
    ("insulation monitors", "Commissioning with several strings connected: insulation alarms appeared at random and strings dropped offline."),
    ("insulation monitor rating", "Insulation fault injection on the DC bus: the fault was not detected."),
    ("cost", "Commercial review: a competing design meets the same requirements for significantly less."),
]


def symptom(violation, task=None):
    for prefix, text in SYMPTOMS:
        if violation.startswith(prefix):
            if prefix == "requirement ":
                rid = violation.split()[1]
                what = ("is missing" if "missing" in violation else "does not name every stakeholder need it serves" if "every stakeholder" in violation
                        else "is traced to the wrong stakeholder need" if "parent" in violation
                        else "has a value that does not follow from the data")
                return f"Requirements review: {rid} {what}."
            if prefix == "SOC error":
                return ("FCR prequalification test after a week of operation: the plant ran out of reserve before the end of "
                        "the test call." if "FCR" in violation else
                        "Energy acceptance test after several days of operation: the plant stopped short of its guaranteed "
                        "energy; the state of charge it reported had drifted.")
            return text
    return None


def report(violations):
    out = []
    for v in violations:
        s = symptom(v) or v
        if s not in out:
            out.append(s)
    return out


def grade(task: dict, output: dict) -> dict:
    d = {k: output.get(k) for k in FIELDS}
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
    for k, cat in CATALOG.items():
        if not any(x["id"] == d[k] for x in task[cat]):
            return {"passed": False, "violations": [f"unknown {k} id '{d[k]}'"]}
    if d["balancing"] != "internal" and not any(x["id"] == d["balancing"] for x in task["balancing_stages"]):
        return {"passed": False, "violations": [f"unknown balancing '{d['balancing']}' (internal or a stage id)"]}
    if d["hold_up"] != "none" and not any(x["id"] == d["hold_up"] for x in task["hold_ups"]):
        return {"passed": False, "violations": [f"unknown hold_up '{d['hold_up']}' (none or a module id)"]}
    if d["imd_location"] not in ("rack", "plant"):
        return {"passed": False, "violations": ["imd_location must be 'rack' or 'plant'"]}

    pl, c, fw = task["plant"], task["cell"], task["firmware"]
    afe, sensor, mcu = _find(task["afes"], d["afe"]), _find(task["current_sensors"], d["current_sensor"]), _find(task["mcus"], d["mcu"])
    ct, pr = _find(task["contactors"], d["string_contactor"]), _find(task["precharge_resistors"], d["precharge_resistor"])
    m = evaluate(task, d)
    v = check_requirements(task, d["requirements"])
    T = 1e-9
    # monitoring
    if d["afe_per_module"] * afe["channels"] < pl["module_cells"] or d["afe_per_module"] * afe["temp_inputs"] < pl["ntc_per_module"]:
        v.append(f"monitoring channels: {d['afe_per_module']} x {afe['id']} give {d['afe_per_module'] * afe['channels']} cell and "
                 f"{d['afe_per_module'] * afe['temp_inputs']} temperature inputs for {pl['module_cells']} cells and "
                 f"{pl['ntc_per_module']} sensors per module")
    if m["chips_per_chain"] > afe["max_chain"]:
        v.append(f"daisy chain of {m['chips_per_chain']} chips exceeds the {afe['id']} maximum of {afe['max_chain']}")
    if m["t_react_ms"] > c["ov_disconnect_ms"] + T:
        v.append(f"over-voltage reaction {m['t_react_ms']:.1f} ms (filter x scan of {m['chips_per_chain']} chips + MCU cycle + "
                 f"contactor opening) exceeds the cell limit {c['ov_disconnect_ms']:g} ms")
    if mcu["chain_ports"] < d["chains_per_rack"] or mcu["can_ports"] < pl["can_needed"] or mcu["adc_channels"] < pl["adc_needed"]:
        v.append(f"MCU {mcu['id']} has {mcu['chain_ports']} chain ports, {mcu['can_ports']} CAN, {mcu['adc_channels']} ADC for "
                 f"{d['chains_per_rack']} chains, {pl['can_needed']} CAN, {pl['adc_needed']} ADC")
    # SOC
    if m["soc_error_pct"] > m["soc_error_allowed_pct"] + T:
        v.append(f"SOC error {m['soc_error_pct']:.2f}% after {task['operations']['recal_interval_h']:g} h (anchor "
                 f"{m['soc_anchor_pct']:.2f}, offset {m['soc_offset_pct']:.2f}, gain {m['soc_gain_pct']:.2f}) exceeds "
                 f"{m['soc_error_allowed_pct']:.2f}% the energy margin allows" + (" (FCR reserve)" if "fcr_mw" in pl else ""))
    # protection coordination
    bad = coordination(task, ct, mcu)
    if bad:
        i, t, lim = bad[0]
        v.append(f"overcurrent {i:.0f} A cleared in {t:.3g} s, beyond the cell limit {lim:.3g} s "
                 f"({'contactor' if i <= ct['i_break_a'] else 'fuse; above the contactor breaking current'})")
    if sensor["range_a"] < breaking_needed(task) - T:
        v.append(f"current sensor range {sensor['range_a']:g} A is below {breaking_needed(task):.0f} A, the current up to "
                 f"which the BMS must decide whether the contactor can open")
    if ct["i_rated_a"] < pl["i_string_a"] - T:
        v.append(f"contactor rating {ct['i_rated_a']:g} A is below the string current {pl['i_string_a']:.1f} A")
    if ct["u_dc"] < pl["v_string_max"] - T:
        v.append(f"contactor DC voltage {ct['u_dc']:g} V is below the string maximum {pl['v_string_max']:.1f} V")
    # precharge
    if m["t_pre_s"] > m["t_pre_allowed_s"] + T:
        v.append(f"precharge time {m['t_pre_s']:.2f} s exceeds {m['t_pre_allowed_s']:.2f} s")
    if m["i_pre_peak_a"] > fw["precharge_relay_peak_a"] + T:
        v.append(f"precharge peak {m['i_pre_peak_a']:.1f} A exceeds the relay limit {fw['precharge_relay_peak_a']:g} A")
    if m["e_pre_j"] > pr["pulse_j"] + T:
        v.append(f"precharge energy {m['e_pre_j']:.0f} J exceeds the resistor pulse rating {pr['pulse_j']:g} J")
    if m["e_short_j"] > pr["pulse_j"] + T:
        v.append(f"precharge into a shorted DC link {m['e_short_j']:.0f} J before the {fw['precharge_check_s']:g} s check "
                 f"exceeds the resistor pulse rating {pr['pulse_j']:g} J")
    # balancing
    if m["i_bal_ma"] < m["i_bal_needed_ma"] - T:
        v.append(f"balancing {m['i_bal_ma']:g} mA is below {m['i_bal_needed_ma']:.1f} mA needed for the self-discharge spread "
                 f"at {task['operations']['cell_temp_c']:g} C")
    # grid-fault ride-through of the rack's 24 V (contactor coil, sensor, MCU)
    if m["hold_j"] < m["rack_w"] * m["t_ride_s"] - T:
        v.append(f"rack control supply: hold-up {m['hold_j']:g} J is below {m['rack_w']:.1f} W x {m['t_ride_s']:.2f} s "
                 f"= {m['rack_w'] * m['t_ride_s']:.0f} J through the fault sequence with reclosing")
    # insulation monitoring of the IT DC system
    if d["imd_location"] == "rack" and pl["strings_parallel"] > 1:
        v.append(f"insulation monitors: {pl['strings_parallel']} rack-level monitors on one galvanically connected IT "
                 f"system interfere; only one may be active")
    if _find(task["imds"], d["imd"])["max_uf"] < m["c_system_uf"] - T:
        v.append(f"insulation monitor rating {_find(task['imds'], d['imd'])['max_uf']:g} uF is below the system "
                 f"capacitance {m['c_system_uf']:.0f} uF (racks, PCS and cables)")
    check_objective(task, m, v)
    return {"passed": not v, "violations": v, "metrics": {k: round(x, 4) for k, x in m.items()}}
