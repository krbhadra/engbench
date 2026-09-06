"""Electrical grader: runs a model-produced SPICE netlist through ngspice
and checks node voltages / voltage drop against the task's constraints.

Requires the `ngspice` CLI on PATH (choco/apt/brew install ngspice).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def _ngspice_available() -> bool:
    return shutil.which("ngspice") is not None


def _run_ngspice(netlist: str) -> dict:
    """Runs an .op analysis and returns {node_name: voltage}."""
    control = "\n.control\nop\nprint all\n.endc\n"
    deck = netlist.rstrip() + control + "\n.end\n"

    with tempfile.TemporaryDirectory() as tmp:
        deck_path = Path(tmp) / "circuit.cir"
        deck_path.write_text(deck)
        result = subprocess.run(
            ["ngspice", "-b", str(deck_path)],
            capture_output=True, text=True, timeout=30,
        )

    voltages = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^\s*v\(([\w.]+)\)\s*=\s*([-\d.eE+]+)", line, re.IGNORECASE)
        if m:
            voltages[m.group(1)] = float(m.group(2))
    return voltages


def grade(task: dict, output: dict) -> dict:
    violations = []
    netlist = output.get("netlist")
    if not netlist:
        return {"passed": False, "violations": ["no netlist in output"]}

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
        node = rule["node"]
        if node not in voltages:
            violations.append(f"node '{node}' not found in simulation output")
            continue
        v = voltages[node]
        if "min" in rule and v < rule["min"]:
            violations.append(f"V({node})={v:.3f} below minimum {rule['min']}")
        if "max" in rule and v > rule["max"]:
            violations.append(f"V({node})={v:.3f} above maximum {rule['max']}")

    for rule in task.get("drop_checks", []):
        a, b = rule["between"]
        if a not in voltages or b not in voltages:
            violations.append(f"cannot compute drop {a}-{b}: missing node")
            continue
        drop = abs(voltages[a] - voltages[b])
        if drop > rule["max_drop"]:
            violations.append(
                f"voltage drop {a}-{b} = {drop:.3f} exceeds max {rule['max_drop']}"
            )

    return {"passed": len(violations) == 0, "violations": violations}
