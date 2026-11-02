"""Tokens and cost per model, track and level, public and held-out runs together: the budget of a release check.
Input tokens include cached reads (claude-cli caches the prompt, so they cost far less than fresh input);
cost is what the transport reports (claude-cli: API-equivalent USD, billed to the subscription).
    python harness/usage.py
"""
import json
from collections import defaultdict
from pathlib import Path

from leaderboard import LEVEL_OF_FAMILY, family

ROOT = Path(__file__).resolve().parent.parent


def tally(records):
    """{level or "all": [runs, input tokens, output tokens, USD]} over graded records."""
    rows = defaultdict(lambda: [0, 0, 0, 0.0])
    for r in records:
        if r["passed"] is None:
            continue
        u = r.get("usage") or {}
        for key in (LEVEL_OF_FAMILY.get(family(r["task"]), "?"), "all"):
            x = rows[key]
            x[0] += 1; x[1] += u.get("prompt_tokens", 0); x[2] += u.get("completion_tokens", 0); x[3] += u.get("cost", 0.0)
    return rows


def main():
    runs = defaultdict(list)
    for d in ("results", "results_private"):
        for f in sorted((ROOT / d).glob("*.json")):
            D = json.loads(f.read_text(encoding="utf-8"))
            runs[(D["model"], D["track"])] += D["records"]
    print(f"{'model':34} {'track':11} {'level':>5} {'runs':>5} {'input Mtok':>10} {'output Mtok':>11} {'USD':>8} {'USD/run':>8}")
    for (m, t), recs in sorted(runs.items()):
        for lvl, (n, i, o, c) in sorted(tally(recs).items(), key=lambda kv: str(kv[0])):
            print(f"{m:34} {t:11} {lvl!s:>5} {n:5} {i / 1e6:10.2f} {o / 1e6:11.2f} {c:8.2f} {c / n:8.3f}")


if __name__ == "__main__":
    main()
