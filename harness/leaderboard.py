"""Read results/*.json and print the leaderboard: single-shot vs agentic, side by side.

    python harness/leaderboard.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def summarize(records):
    """pass rate, pass^k, mean attempts to first pass, mean cost. Skipped (None) records excluded."""
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
        "pass_k": sum(len(v) == k and all(r["passed"] for r in v) for v in by_task.values()) / len(by_task),
        "k": k,
        "attempts": sum(first_pass) / len(first_pass) if first_pass else float("nan"),
        "cost": sum(r["usage"].get("cost", 0) for r in recs) / len(recs),
    }


def pct(x):
    return f"{x * 100:5.1f}%" if x is not None else "    -"


def main():
    table = defaultdict(dict)
    for p in sorted(RESULTS_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        table[d["model"]][d["track"]] = summarize(d["records"])

    if not table:
        print("no results yet")
        return

    hdr = (f"{'model':40} {'single':>7} {'agentic':>8} {'gap':>6} "
           f"{'ss pass^k':>10} {'ag pass^k':>10} {'attempts':>9} {'$/task':>8}")
    print(hdr)
    print("-" * len(hdr))
    for model, tracks in sorted(table.items()):
        ss, ag = tracks.get("single-shot"), tracks.get("agentic")
        gap = f"{(ag['pass_rate'] - ss['pass_rate']) * 100:+5.1f}" if ss and ag else "     -"
        attempts = ag["attempts"] if ag else float("nan")
        cost = (ag or ss)["cost"] if (ag or ss) else 0.0
        print(f"{model:40} {pct(ss and ss['pass_rate']):>7} {pct(ag and ag['pass_rate']):>8} {gap:>6} "
              f"{pct(ss and ss['pass_k']):>10} {pct(ag and ag['pass_k']):>10} "
              f"{attempts:>9.2f} {cost:>8.4f}")


if __name__ == "__main__":
    main()
