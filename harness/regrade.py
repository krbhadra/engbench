"""Re-grade every stored artifact in results/ with the current graders (no model calls).

    python harness/regrade.py

Use after a grader fix. Prints every record whose verdict changed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
sys.path.insert(0, str(ROOT / "harness"))
import grade  # noqa: E402
from run_eval import safe_grade  # noqa: E402

tasks = {p.stem: json.loads(p.read_text()) for p in (ROOT / "tasks").glob("*.json")}
changed = 0
for p in sorted((ROOT / "results").glob("*.json")):
    d = json.loads(p.read_text())
    for r in d["records"]:
        for at in r["attempts"]:
            new = safe_grade(tasks[r["task"]], at.get("artifact"))
            if new["passed"] != at["passed"]:
                changed += 1
                print(f"{d['model']} {d['track']} {r['task']} trial {r['trial']}: {at['passed']} -> {new['passed']}  {new['violations']}")
            at.update(new)
        passed = [a["passed"] for a in r["attempts"]]
        r["passed"] = None if None in passed else any(passed)
    p.write_text(json.dumps(d, indent=1))
print(f"{changed} verdicts changed")
