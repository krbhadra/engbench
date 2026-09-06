"""Self-check: run hand-written golden solutions through each grader.

Run with: python solvers/test_solvers.py
"""
import json
from pathlib import Path

import electrical
import grade
import mechanical

TASKS_DIR = Path(__file__).parent.parent / "tasks"


def load(task_id):
    return json.loads((TASKS_DIR / f"{task_id}.json").read_text())


def test_mech_001_golden_passes():
    task = load("mech_001")
    output = {
        "placements": [
            {"id": "comp_a", "position": [0, 0, 0]},
            {"id": "comp_b", "position": [50, 0, 0]},
            {"id": "comp_c", "position": [0, 40, 0]},
        ]
    }
    result = mechanical.grade(task, output)
    assert result["passed"], result["violations"]


def test_mech_001_overlap_fails():
    task = load("mech_001")
    output = {
        "placements": [
            {"id": "comp_a", "position": [0, 0, 0]},
            {"id": "comp_b", "position": [10, 0, 0]},  # overlaps comp_a
            {"id": "comp_c", "position": [0, 40, 0]},
        ]
    }
    result = mechanical.grade(task, output)
    assert not result["passed"]
    assert any("overlaps" in v for v in result["violations"])


def test_mech_002_golden_passes():
    task = load("mech_002")
    output = {
        "placements": [
            {"id": "comp_x", "position": [0, 0, 0]},
            {"id": "comp_y", "position": [60, 0, 0]},
            {"id": "comp_z", "position": [0, 50, 0]},
        ]
    }
    result = mechanical.grade(task, output)
    assert result["passed"], result["violations"]


def test_mech_002_clearance_violation_fails():
    task = load("mech_002")
    output = {
        "placements": [
            {"id": "comp_x", "position": [0, 0, 0]},
            {"id": "comp_y", "position": [45, 0, 0]},  # only 5mm gap, needs 15
            {"id": "comp_z", "position": [0, 50, 0]},
        ]
    }
    result = mechanical.grade(task, output)
    assert not result["passed"]
    assert any("clearance" in v for v in result["violations"])


def test_elec_001_golden_passes():
    task = load("elec_001")
    output = {
        "netlist": "Voltage divider\nV1 vin 0 DC 12\nR1 vin vout 100\nR2 vout 0 100"
    }
    result = electrical.grade(task, output)
    if result["passed"] is None:
        print("SKIPPED elec_001 golden check:", result["violations"])
        return
    assert result["passed"], result["violations"]


def test_elec_001_bad_divider_fails():
    task = load("elec_001")
    # 12V * 900/1000 = ~10.8V — outside the 5-7V window
    output = {
        "netlist": "Bad divider\nV1 vin 0 DC 12\nR1 vin vout 900\nR2 vout 0 100"
    }
    result = electrical.grade(task, output)
    if result["passed"] is None:
        print("SKIPPED elec_001 bad-divider check:", result["violations"])
        return
    assert not result["passed"]


COMB_NETLIST = "V1 psu_out 0 DC 12" + chr(10) + "Rload load_in 0 10"


def test_comb_001_golden_passes():
    task = load("comb_001")
    output = {
        "placements": [
            {"id": "psu", "position": [0, 0, 0]},
            {"id": "load", "position": [70, 0, 0]},   # 65mm -> 0.13 ohm -> 11.85V
            {"id": "fan", "position": [0, 100, 0]},
        ],
        "netlist": COMB_NETLIST,
    }
    result = grade.grade(task, output)
    if result["passed"] is None:
        print("SKIPPED comb_001 golden check:", result["violations"])
        return
    assert result["passed"], result["violations"]


def test_comb_001_long_wire_fails():
    task = load("comb_001")
    output = {
        "placements": [
            {"id": "psu", "position": [0, 0, 0]},
            {"id": "load", "position": [250, 100, 0]},  # 325mm -> 0.65 ohm -> 11.27V
            {"id": "fan", "position": [0, 100, 0]},
        ],
        "netlist": COMB_NETLIST,
    }
    result = grade.grade(task, output)
    if result["passed"] is None:
        print("SKIPPED comb_001 long-wire check:", result["violations"])
        return
    assert not result["passed"]
    assert any("load_in" in v for v in result["violations"])


def test_comb_001_shorted_wire_fails():
    task = load("comb_001")
    output = {
        "placements": [
            {"id": "psu", "position": [0, 0, 0]},
            {"id": "load", "position": [250, 100, 0]},
            {"id": "fan", "position": [0, 100, 0]},
        ],
        "netlist": COMB_NETLIST + chr(10) + "Rcheat psu_out load_in 0.0001",
    }
    result = grade.grade(task, output)
    assert any("directly" in v for v in result["violations"])


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} checks ran")
