"""Electrical grader: runs a model-produced SPICE netlist through ngspice
and checks node voltages / voltage drop against the task's constraints.

Requires the `ngspice` CLI on PATH (choco/apt/brew install ngspice).

Optional task keys beyond voltage_checks/drop_checks:
  required_elements: [{"name", "nodes", "value"}]  netlist must contain this exact
                     element (the fixed load / source the task told the model to keep)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


TOL = 1e-6  # volts; absorbs float noise at a boundary, far below any task tolerance

_SUFFIX = {"t": 1e12, "g": 1e9, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}


def _num(s: str) -> float | None:
    """SPICE number: 4.7k, 1meg, 10m, 12 ..."""
    m = re.match(r"^([-+]?[\d.]+(?:e[-+]?\d+)?)([a-z]*)", s.lower())
    if not m:
        return None
    v, suf = float(m.group(1)), m.group(2)
    if suf.startswith("meg"):
        return v * 1e6
    return v * _SUFFIX.get(suf[:1], 1.0) if suf else v


def _has_element(netlist: str, name: str, nodes, value) -> bool:
    want_nodes = [n.lower() for n in nodes]
    want_val = _num(str(value))
    for line in netlist.splitlines():
        t = line.split()
        if len(t) >= 4 and t[0].lower() == name.lower() and [t[1].lower(), t[2].lower()] == want_nodes:
            got = _num(t[-1])  # last token: handles both "R1 a b 10" and "V1 a b DC 12"
            return got is not None and abs(got - want_val) <= 1e-9 * max(1.0, abs(want_val))
    return False


def _ngspice_bin() -> str | None:
    # Windows ships ngspice_con.exe (console) and ngspice.exe (GUI, prints nothing in batch mode)
    return shutil.which("ngspice_con") or shutil.which("ngspice")


def _ngspice_available() -> bool:
    return _ngspice_bin() is not None


def _run_ngspice(netlist: str) -> dict:
    """Runs an .op analysis and returns {node_name: voltage}."""
    lines = netlist.strip().splitlines()
    # ponytail: SPICE eats line 1 as the title. Drop a model-supplied title (a short
    # non-element, non-directive first line) and always prepend our own.
    if lines and not lines[0].startswith((".", "*")) and len(lines[0].split()) < 3:
        lines = lines[1:]
    # A model-supplied .end or analysis block would pre-empt ours; the grader owns the analysis.
    ours = {".end", ".control", ".endc", ".op", ".print", ".tran", ".dc", ".ac"}
    lines = [l for l in lines if (l.split() or [""])[0].lower() not in ours]
    # numdgt=12: the default 7 significant digits turned a 9.9958mV drop into "0.010" (boundary fail)
    control = "\n.control\nset numdgt=12\nop\nprint all\n.endc\n"
    deck = "EngBench\n" + "\n".join(lines) + control + "\n.end\n"

    with tempfile.TemporaryDirectory() as tmp:
        deck_path = Path(tmp) / "circuit.cir"
        deck_path.write_text(deck)
        result = subprocess.run(
            [_ngspice_bin(), "-b", str(deck_path)],
            capture_output=True, text=True, timeout=30,
        )

    # `print all` after .op emits one line per vector: "vout = 6.000000e+00" (node voltage)
    # or "v1#branch = -6.0e-02" (source current). Older builds wrap names as v(vout).
    voltages = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^\s*(?:v\()?([\w.]+)\)?\s*=\s*([-\d.eE+]+)\s*$", line, re.IGNORECASE)
        if m and "#" not in m.group(1):
            voltages[m.group(1).lower()] = float(m.group(2))
    return voltages


def grade(task: dict, output: dict) -> dict:
    violations = []
    netlist = output.get("netlist")
    if not netlist:
        return {"passed": False, "violations": ["no netlist in output"]}

    for el in task.get("required_elements", []):
        if not _has_element(netlist, el["name"], el["nodes"], el["value"]):
            violations.append(
                f"netlist must contain '{el['name']} {el['nodes'][0]} {el['nodes'][1]} {el['value']}' as specified"
            )

    if not _ngspice_available():
        return {
            "passed": None,
            "violations": ["ngspice not installed — cannot grade"],
        }

    try:
        voltages = _run_ngspice(netlist)
    except subprocess.TimeoutExpired:
        return {"passed": False, "violations": ["ngspice timed out (bad netlist?)"]}

    if not voltages:
        violations.append("ngspice produced no node voltages — netlist likely invalid")
        return {"passed": False, "violations": violations}

    for rule in task.get("voltage_checks", []):
        node = rule["node"].lower()
        if node not in voltages:
            violations.append(f"node '{node}' not found in simulation output")
            continue
        v = voltages[node]
        if "min" in rule and v < rule["min"] - TOL:
            violations.append(f"V({node})={v:.4f} below minimum {rule['min']}")
        if "max" in rule and v > rule["max"] + TOL:
            violations.append(f"V({node})={v:.4f} above maximum {rule['max']}")

    for rule in task.get("drop_checks", []):
        a, b = (n.lower() for n in rule["between"])
        if a not in voltages or b not in voltages:
            violations.append(f"cannot compute drop {a}-{b}: missing node")
            continue
        drop = abs(voltages[a] - voltages[b])
        if "max_drop" in rule and drop > rule["max_drop"] + TOL:
            violations.append(
                f"voltage drop {a}-{b} = {drop:.4f} exceeds max {rule['max_drop']}"
            )
        if "min_drop" in rule and drop < rule["min_drop"] - TOL:
            violations.append(
                f"voltage drop {a}-{b} = {drop:.4f} below min {rule['min_drop']}"
            )

    return {"passed": len(violations) == 0, "violations": violations}
