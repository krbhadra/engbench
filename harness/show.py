"""Print what models actually produced, from results/*.json.

    python harness/show.py --task mech_003            # every model's attempts on one task
    python harness/show.py --model sonnet --failed    # only failures for one model
    python harness/show.py --task comb_004 --full     # include raw model text
"""
import argparse
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--model", help="substring of the model label")
    ap.add_argument("--track", choices=["single-shot", "agentic"])
    ap.add_argument("--failed", action="store_true", help="only records that did not pass")
    ap.add_argument("--full", action="store_true", help="print raw model text too")
    a = ap.parse_args()

    for p in sorted(RESULTS_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        if a.model and a.model not in d["model"] or a.track and d["track"] != a.track:
            continue
        for r in d["records"]:
            if a.task and r["task"] != a.task or a.failed and r["passed"]:
                continue
            status = {True: "PASS", False: "FAIL", None: "SKIP"}[r["passed"]]
            print(f"\n=== {status} {r['task']} | {d['model']} | {d['track']} | trial {r['trial']} | "
                  f"{len(r['attempts'])} attempt(s) | {r['usage'].get('completion_tokens', 0)} out tok | {r['seconds']}s")
            for i, at in enumerate(r["attempts"], 1):
                art = at.get("artifact")
                if art is None:
                    print(f"  attempt {i}: unparseable output")
                else:
                    for pl in art.get("placements", []) if isinstance(art, dict) else []:
                        print(f"  attempt {i}: {pl.get('id'):12} at {pl.get('position')}")
                    if isinstance(art, dict) and art.get("netlist"):
                        for line in str(art["netlist"]).splitlines():
                            print(f"  attempt {i}: {line}")
                print(f"  attempt {i}: -> {'passed' if at['passed'] else 'violations: ' + '; '.join(at['violations'])}")
                if a.full and at.get("raw"):
                    print("  raw: " + at["raw"][:2000].replace("\n", "\n       "))


if __name__ == "__main__":
    main()
