"""Read results/*.json and print the leaderboard: single-shot vs agentic, side by side.

    python harness/leaderboard.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TRACKS = ("single-shot", "feedback", "agentic")


def summarize(records):
    """pass rate, first-design pass rate, pass^k, mean attempts to first pass, mean cost. Skipped (None) excluded."""
    recs = [r for r in records if r["passed"] is not None]
    if not recs:
        return None
    by_task = defaultdict(list)
    for r in recs:
        by_task[r["task"]].append(r)
    k = max(len(v) for v in by_task.values())
    first_pass = [next(i for i, a in enumerate(r["attempts"], 1) if a["passed"])
                  for r in recs if r["passed"]]
    return {
        "tasks": len(by_task),
        "pass_rate": sum(r["passed"] for r in recs) / len(recs),
        "first": sum(bool(r["attempts"]) and r["attempts"][0]["passed"] is True for r in recs) / len(recs),
        "pass_k": sum(len(v) == k and all(r["passed"] for r in v) for v in by_task.values()) / len(by_task),
        "k": k,
        "attempts": sum(first_pass) / len(first_pass) if first_pass else float("nan"),
        "cost": sum(r["usage"].get("cost", 0) for r in recs) / len(recs),
    }


def pct(x):
    return f"{x * 100:5.1f}%" if x is not None else "    -"


def main():
    table, raw = defaultdict(dict), defaultdict(dict)
    for p in sorted(RESULTS_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        table[d["model"]][d["track"]] = summarize(d["records"])
        raw[d["model"]][d["track"]] = d["records"]

    if not table:
        print("no results yet")
        return

    # ponytail: family = task id up to the last underscore (mech, elec, comb, pe_cooling, coolant_loop)
    fams = sorted({r["task"].rsplit("_", 1)[0] for tr in raw.values() for recs in tr.values() for r in recs})
    for track in TRACKS:
        if not any(track in tr for tr in raw.values()):
            continue
        print(f"{track + ' pass rate by family':40} " + " ".join(f"{f:>13}" for f in fams))
        print("-" * (41 + 14 * len(fams)))
        for model, tracks in sorted(raw.items()):
            recs = tracks.get(track, [])
            cells = []
            for f in fams:
                fr = [r for r in recs if r["task"].rsplit("_", 1)[0] == f and r["passed"] is not None]
                cells.append(f"{pct(sum(r['passed'] for r in fr) / len(fr))} ({len(fr):2d})" if fr else f"{'-':>13}")
            print(f"{model:40} " + " ".join(f"{c:>13}" for c in cells))
        print()

    hdr = (f"{'model':40} {'single':>7} {'ag first':>9} {'gap':>6} {'ag pass':>8} {'ag pass^k':>10} "
           f"{'attempts':>9} {'feedback':>9} {'$/task':>8}")
    print(hdr)
    print("-" * len(hdr))
    print("ag first = agentic, first graded design passes (headline); gap = ag first - single on shared tasks; "
          "ag pass = passes within 5 grader calls; feedback = superseded loop")
    for model, tracks in sorted(table.items()):
        ss, fb, ag = tracks.get("single-shot"), tracks.get("feedback"), tracks.get("agentic")
        shared = {r["task"] for r in raw[model].get("agentic", [])}  # gap only over tasks both tracks ran
        ss_same = summarize([r for r in raw[model].get("single-shot", []) if r["task"] in shared])
        ag_same = summarize([r for r in raw[model].get("agentic", []) if r["task"] in {x["task"] for x in raw[model].get("single-shot", [])}])
        gap = f"{(ag_same['first'] - ss_same['pass_rate']) * 100:+5.1f}" if ss_same and ag_same else "     -"
        attempts = ag["attempts"] if ag else float("nan")
        cost = (ag or ss)["cost"] if (ag or ss) else 0.0
        print(f"{model:40} {pct(ss and ss['pass_rate']):>7} {pct(ag and ag['first']):>9} {gap:>6} {pct(ag and ag['pass_rate']):>8} "
              f"{pct(ag and ag['pass_k']):>10} {attempts:>9.2f} {pct(fb and fb['pass_rate']):>9} {cost:>8.4f}")


if __name__ == "__main__":
    main()
