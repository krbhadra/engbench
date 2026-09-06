"""Self-check: every task's golden solution must pass its grader and every broken
solution must fail with the expected violation. Solutions live in solutions.json.

Run with: python solvers/test_solvers.py

Electrical/combined voltage checks are skipped when ngspice is missing; mechanical
violations in combined tasks are still checked.
"""
import json
from pathlib import Path

import grade

HERE = Path(__file__).parent
TASKS_DIR = HERE.parent / "tasks"
SOLUTIONS = json.loads((HERE / "solutions.json").read_text())


def main():
    tasks = sorted(p.stem for p in TASKS_DIR.glob("*.json"))
    missing = [t for t in tasks if t not in SOLUTIONS]
    assert not missing, f"tasks without solutions: {missing}"

    checked = skipped = 0
    for tid in tasks:
        task = json.loads((TASKS_DIR / f"{tid}.json").read_text())
        sol = SOLUTIONS[tid]

        r = grade.grade(task, sol["golden"])
        if r["passed"] is None:
            skipped += 1
        else:
            assert r["passed"], f"{tid} golden failed: {r['violations']}"
            checked += 1

        for i, b in enumerate(sol["broken"]):
            r = grade.grade(task, b["output"])
            hit = any(b["expect"] in v for v in r["violations"])
            if r["passed"] is None and not hit:
                skipped += 1
                continue
            assert r["passed"] is not True, f"{tid} broken #{i} passed unexpectedly"
            assert hit, f"{tid} broken #{i}: expected '{b['expect']}' in {r['violations']}"
            checked += 1
        print(f"OK   {tid}  (golden + {len(sol['broken'])} broken)")

    print(f"\n{len(tasks)} tasks, {checked} checks passed, {skipped} skipped (ngspice missing)")


if __name__ == "__main__":
    main()
