"""Render results/*.json into one static page: docs/index.html.

    python harness/report.py

No server, no framework, no dependencies. docs/ is what GitHub Pages serves,
so the same file is the local dashboard today and the public site later.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "index.html"

TRACKS = ("single-shot", "feedback", "agentic")
MARK = {"single-shot": "S", "feedback": "F", "agentic": "A"}
TRACK_NOTE = {"single-shot": "one answer, no tools", "feedback": "superseded: grade tool with full numbers, no compute",
              "agentic": "first graded design passes; run_python + grade (which check failed, no numbers)"}
DISCIPLINES = {"mech": "mechanical", "elec": "electrical", "comb": "mechanical + electrical",
               "pe_cooling": "electronics + thermal + fluids", "coolant_loop": "thermal + fluids"}


def family(task_id):
    return task_id.rsplit("_", 1)[0]


def load():
    runs = []
    for p in sorted((ROOT / "results").glob("*.json")):
        d = json.loads(p.read_text())
        runs.append(d)
    tasks = {p.stem: json.loads(p.read_text()) for p in (ROOT / "tasks").glob("*.json")}
    return runs, tasks


def rate(recs):
    recs = [r for r in recs if r["passed"] is not None]
    return (sum(r["passed"] for r in recs) / len(recs), len(recs)) if recs else (None, 0)


def first_rate(recs):
    """Agentic headline: the first graded design passes."""
    recs = [r for r in recs if r["passed"] is not None]
    return (sum(bool(r["attempts"]) and r["attempts"][0]["passed"] is True for r in recs) / len(recs), len(recs)) if recs else (None, 0)


def cell(r):
    if r is None:
        return '<td class="na">–</td>'
    v, n = r
    if v is None:
        return '<td class="na">–</td>'
    cls = "good" if v >= 0.9 else "mid" if v >= 0.5 else "bad"
    return f'<td class="{cls}"><b>{v*100:.0f}%</b><small>{n}</small></td>'


def esc(x):
    return html.escape(str(x))


def build(runs, tasks):
    models = sorted({d["model"] for d in runs})
    by = {(d["model"], d["track"]): d["records"] for d in runs}
    fams = sorted({family(r["task"]) for d in runs for r in d["records"]})

    # ---- leaderboard
    lb = ['<table><thead><tr><th>model</th><th>single-shot</th><th>agentic<small>first design</small></th><th>gap<small>first design − single-shot, same tasks</small></th>'
          '<th>agentic<small>pass in 5 grader calls</small></th><th>grader calls<small>to pass</small></th>'
          '<th>feedback<small>superseded</small></th><th>tasks</th><th>out tokens / task</th><th>$ / task</th></tr></thead><tbody>']
    for m in models:
        ss, fb, ag = by.get((m, "single-shot"), []), by.get((m, "feedback"), []), by.get((m, "agentic"), [])
        rs, rf, ra, r1 = rate(ss), rate(fb), rate(ag), first_rate(ag)
        both = {r["task"] for r in ss} & {r["task"] for r in ag}  # gap only over tasks both tracks ran
        g_ss, g_ag = rate([r for r in ss if r["task"] in both]), first_rate([r for r in ag if r["task"] in both])
        gap = f"{(g_ag[0]-g_ss[0])*100:+.0f}" if g_ss[0] is not None and g_ag[0] is not None else "–"
        passed = [len(r["attempts"]) for r in ag if r["passed"]]
        calls = f"{sum(passed) / len(passed):.2f}" if passed else "–"
        allr = [r for r in ss + fb + ag if r["passed"] is not None]
        tok = sum(r["usage"].get("completion_tokens", 0) for r in allr) / max(1, len(allr))
        cost = sum(r["usage"].get("cost", 0) for r in allr) / max(1, len(allr))
        lb.append(f"<tr><th>{esc(m)}</th>{cell(rs)}{cell(r1)}<td>{gap}</td>{cell(ra)}<td>{calls}</td>{cell(rf)}<td>{len({r['task'] for r in allr})}</td>"
                  f"<td>{tok:,.0f}</td><td>{cost:.3f}</td></tr>")
    lb.append("</tbody></table>")

    # ---- per family, per track
    fam_tables = []
    for track in TRACKS:
        if not any(d["track"] == track for d in runs):
            continue
        t = [f"<h3>{track}<small>{TRACK_NOTE[track]}</small></h3><table><thead><tr><th>model</th>"]
        t += [f"<th>{esc(f)}<small>{esc(DISCIPLINES.get(f, ''))}</small></th>" for f in fams]
        t.append("</tr></thead><tbody>")
        for m in models:
            recs = by.get((m, track), [])
            score = first_rate if track == "agentic" else rate
            t.append(f"<tr><th>{esc(m)}</th>" + "".join(cell(score([r for r in recs if family(r["task"]) == f])) for f in fams) + "</tr>")
        t.append("</tbody></table>")
        fam_tables.append("".join(t))

    # ---- per task matrix with details
    task_ids = sorted({r["task"] for d in runs for r in d["records"]})
    mt = ['<table class="matrix"><thead><tr><th>task</th>'] + [f"<th>{esc(m)}</th>" for m in models] + ["</tr></thead><tbody>"]
    for tid in task_ids:
        row = [f'<tr><th>{esc(tid)}<small>{esc(tasks.get(tid, {}).get("title", ""))}</small></th>']
        for m in models:
            recs = [r for tr in TRACKS for r in by.get((m, tr), []) if r["task"] == tid]
            if not recs:
                row.append('<td class="na">–</td>')
                continue
            marks = []
            for r in recs:
                track = next(MARK[d["track"]] for d in runs if d["model"] == m and r in d["records"])
                last = r["attempts"][-1]
                status = "pass" if r["passed"] else "fail" if r["passed"] is False else "skip"
                viol = "<br>".join(esc(v) for v in last.get("violations", [])) or "passed"
                marks.append(f'<details class="{status}"><summary>{track}{len(r["attempts"])}</summary>'
                             f'<pre>{esc(json.dumps(last.get("artifact"), indent=1))}</pre><p>{viol}</p></details>')
            row.append("<td>" + "".join(marks) + "</td>")
        mt.append("".join(row) + "</tr>")
    mt.append("</tbody></table>")

    n_tasks = len(tasks)
    n_runs = sum(len(d["records"]) for d in runs)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EngBench Results</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1c19;--muted:#6b6860;--line:#dedbd3;--head:#f1efe8;--good:#dcefd8;--mid:#fbecc4;--bad:#f6d5cf;--accent:#1f5f8b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161614;--fg:#e8e6df;--muted:#9a978e;--line:#33322e;--head:#1f1f1c;--good:#274a2a;--mid:#5a4a1b;--bad:#5e2a24;--accent:#7fb3d9}}}}
:root[data-theme=dark]{{--bg:#161614;--fg:#e8e6df;--muted:#9a978e;--line:#33322e;--head:#1f1f1c;--good:#274a2a;--mid:#5a4a1b;--bad:#5e2a24;--accent:#7fb3d9}}
body{{margin:0;padding:24px 16px 64px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1100px;margin:0 auto}} h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:40px 0 8px}} h3{{font-size:15px;margin:16px 0 6px;color:var(--muted)}}
p.lede{{color:var(--muted);margin:0 0 8px;max-width:65ch}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;font-variant-numeric:tabular-nums;white-space:nowrap}}
th,td{{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}} thead th{{background:var(--head)}} tbody th{{font-weight:500}}
th small,td small{{display:block;color:var(--muted);font-size:11px;font-weight:400}}
td.good{{background:var(--good)}} td.mid{{background:var(--mid)}} td.bad{{background:var(--bad)}} td.na{{color:var(--muted);text-align:center}}
.matrix td{{padding:2px 4px}} details{{display:inline-block;margin:2px}} summary{{cursor:pointer;list-style:none;padding:1px 7px;border-radius:3px;font-size:12px;font-weight:600}}
details.pass summary{{background:var(--good)}} details.fail summary{{background:var(--bad)}} details.skip summary{{background:var(--head)}}
details[open]{{display:block;max-width:520px;white-space:normal}} details pre{{font-size:11px;margin:6px 0;overflow-x:auto}} details p{{font-size:12px;margin:0 0 6px}}
a{{color:var(--accent)}} footer{{margin-top:48px;color:var(--muted);font-size:13px}}
</style></head><body><main>
<h1>EngBench</h1>
<p class="lede">Engineering design tasks graded by deterministic solvers, never by an LLM. <b>Single-shot</b>: one answer, no tools, the engineer answering cold. <b>Agentic</b>: a Python tool to compute and self-check, plus a grader that says which check failed without the numbers, five grader calls: the engineer at a desk with a calculator and a checker. The agentic headline is the <b>first-design</b> rate, whether the first design it submits passes; passing within five grader calls is shown beside it but saturates for strong models. <b>Feedback</b> is the superseded early loop (grader with full numbers, no compute), kept for the record. Cell footnotes are the number of task runs behind each rate.</p>
<p class="lede">{n_tasks} tasks · {n_runs} task runs · {len(models)} models · updated {stamp}</p>
<h2>Leaderboard</h2><div class="wrap">{"".join(lb)}</div>
<h2>By family</h2>
<p class="lede">The first three families (mechanical fit, DC circuits, and their combination) are saturated and stay as a floor. The generated families ask for a design within 5% of the brute-force optimum, not just a feasible one.</p>
<div class="wrap">{"".join(fam_tables)}</div>
<h2>Every task, every model</h2>
<p class="lede">S = single-shot, F = feedback (superseded), A = agentic; the digit is the number of grader attempts. Click a mark to see the model's design and the grader's violations.</p>
<div class="wrap">{"".join(mt)}</div>
<footer>Generated by <code>harness/report.py</code> from the committed <code>results/</code> folder. Source, tasks and graders: <a href="https://github.com/krbhadra/engbench">github.com/krbhadra/engbench</a>.</footer>
</main></body></html>
"""


def main():
    runs, tasks = load()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build(runs, tasks), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
