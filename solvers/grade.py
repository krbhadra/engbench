"""Single entry point: grade(task, output) -> {"passed": bool|None, "violations": [...]}.

Dispatches on task["domain"]. Combined tasks couple the two graders: wire
length is measured from the model's own placements, converted to resistance,
and inserted into the netlist before simulation.
"""
from __future__ import annotations

import importlib

import electrical
import mechanical


def _center(pos, size):
    return [p + s / 2 for p, s in zip(pos, size)]


def _wire_lines(task, output):
    sizes = {c["id"]: c["size"] for c in task["components"]}
    pos = {p["id"]: p["position"] for p in output["placements"]}
    lines = []
    for i, w in enumerate(task["wires"]):
        a = _center(pos[w["from"]], sizes[w["from"]])
        b = _center(pos[w["to"]], sizes[w["to"]])
        # ponytail: Manhattan center-to-center — wires route along axes, not diagonals
        length = sum(abs(x - y) for x, y in zip(a, b))
        n1, n2 = w["nodes"]
        lines.append(f"Rwire{i} {n1} {n2} {length * w['ohms_per_mm']:.6g}")
    return lines


def _directly_connected(netlist, n1, n2):
    # ponytail: tokens 1-2 are the nodes of any 2-terminal element; good enough for R/V/I/C/L
    want = {n1.lower(), n2.lower()}
    for line in netlist.splitlines():
        t = line.split()
        if len(t) >= 3 and {t[1].lower(), t[2].lower()} == want:
            return True
    return False


def grade(task: dict, output: dict) -> dict:
    domain = task["domain"]
    if domain == "mechanical":
        return mechanical.grade(task, output)
    if domain == "electrical":
        return electrical.grade(task, output)
    if domain != "combined":
        # any other domain is a grader module of the same name in solvers/
        return importlib.import_module(domain).grade(task, output)

    mech = mechanical.grade(task, output)
    violations = list(mech["violations"])
    if violations and violations[0].startswith("missing placements"):
        return mech  # cannot measure wires without placements

    netlist = output.get("netlist")
    if not netlist:
        return {"passed": False, "violations": violations + ["no netlist in output"]}

    for w in task["wires"]:
        n1, n2 = w["nodes"]
        if _directly_connected(netlist, n1, n2):
            violations.append(
                f"netlist connects {n1}-{n2} directly; the grader inserts that wire"
            )

    coupled = netlist.rstrip() + "\n" + "\n".join(_wire_lines(task, output))
    elec = electrical.grade(task, {"netlist": coupled})
    violations += elec["violations"]
    if elec["passed"] is None:
        return {"passed": None, "violations": violations}
    return {"passed": not violations, "violations": violations}
