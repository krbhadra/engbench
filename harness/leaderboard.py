"""Read results/*.json and print the leaderboard: single-shot vs agentic, side by side.

    python harness/leaderboard.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
PRIVATE_DIR = RESULTS_DIR.parent / "results_private"  # held-out seeds; only pass/fail leaves this folder
TRACKS = ("single-shot", "agentic")
# The ladder (VISION.md): each level's published points; score = sum of points x pass rate at that level.
LEVEL_POINTS = {1: 15, 2: 20, 3: 15, 4: 20, 5: 15, 6: 15}
LEVEL_OF_FAMILY = {"mech": 1, "elec": 1, "comb": 1, "pe_cooling": 1, "coolant_loop": 1, "bess": 2, "bess3": 3, "bms4": 4}


def family(task_id):
    return task_id.rsplit("_", 1)[0]


def passed_for_score(r, track):
    """Both tracks score a pass: single-shot its only answer, agentic within its test rounds."""
    return r["passed"] is True


def held_out(results_file):
    """Records on the private held-out seeds for the same model and track, if that run exists."""
    p = PRIVATE_DIR / Path(results_file).name
    return json.loads(p.read_text())["records"] if p.exists() else []


def score(records, track, private=()):
    """(score out of 100, {level: pass rate}). A level with held-out runs is scored on those only;
    the public tasks stay for reproduction. Levels with no runs earn 0 points."""
    rates = {}
    for lvl in LEVEL_POINTS:
        at = [r for r in private if r["passed"] is not None and LEVEL_OF_FAMILY.get(family(r["task"])) == lvl] or              [r for r in records if r["passed"] is not None and LEVEL_OF_FAMILY.get(family(r["task"])) == lvl]
        if at:
            rates[lvl] = sum(passed_for_score(r, track) for r in at) / len(at)
    return sum(LEVEL_POINTS[l] * v for l, v in rates.items()), rates


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
    table, raw, private = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for p in sorted(RESULTS_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        table[d["model"]][d["track"]] = summarize(d["records"])
        raw[d["model"]][d["track"]] = d["records"]
        private[d["model"]][d["track"]] = held_out(p)

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

    print(f"{'score out of 100 (levels run, held-out L3)':40} {'single-shot':>22} {'agentic':>22}")
    for model, tracks in sorted(raw.items()):
        cells = []
        for tr in ("single-shot", "agentic"):
            if tr in tracks:
                sc, rates = score(tracks[tr], tr, private[model][tr])
                cells.append(f"{sc:5.1f} (L{','.join(map(str, sorted(rates)))})")
            else:
                cells.append("-")
        print(f"{model:40} {cells[0]:>22} {cells[1]:>22}")
    print()

    hdr = (f"{'model':40} {'single':>7} {'ag pass':>8} {'gap':>6} {'ag first':>9} {'ag pass^k':>10} "
           f"{'rounds':>7} {'$/task':>8}")
    print(hdr)
    print("-" * len(hdr))
    print("ag pass = agentic, passes within 3 test rounds (headline); gap = ag pass - single on shared tasks; "
          "ag first = first design passes")
    for model, tracks in sorted(table.items()):
        ss, ag = tracks.get("single-shot"), tracks.get("agentic")
        shared = {r["task"] for r in raw[model].get("agentic", [])}  # gap only over tasks both tracks ran
        ss_same = summarize([r for r in raw[model].get("single-shot", []) if r["task"] in shared])
        ag_same = summarize([r for r in raw[model].get("agentic", []) if r["task"] in {x["task"] for x in raw[model].get("single-shot", [])}])
        gap = f"{(ag_same['pass_rate'] - ss_same['pass_rate']) * 100:+5.1f}" if ss_same and ag_same else "     -"
        rounds = ag["attempts"] if ag else float("nan")
        cost = (ag or ss)["cost"] if (ag or ss) else 0.0
        print(f"{model:40} {pct(ss and ss['pass_rate']):>7} {pct(ag and ag['pass_rate']):>8} {gap:>6} {pct(ag and ag['first']):>9} "
              f"{pct(ag and ag['pass_k']):>10} {rounds:>7.2f} {cost:>8.4f}")

if __name__ == "__main__":
    main()
