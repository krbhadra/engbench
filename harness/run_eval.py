"""EngBench harness: run one model on one track, write results/<model>__<track>.json.

    python harness/run_eval.py --model anthropic/claude-sonnet-4 --track agentic
    python harness/run_eval.py --model meta-llama/llama-3.3-70b-instruct --provider fireworks --track single-shot

Stdlib only. Calls OpenRouter's OpenAI-compatible endpoint directly.
Resumable: (task, trial) pairs already in the results file are skipped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solvers"))
import grade as grader  # noqa: E402

TASKS_DIR = ROOT / "tasks"
RESULTS_DIR = ROOT / "results"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_ATTEMPTS = 5      # grader calls per task, agentic track
TASK_TIMEOUT = 300    # seconds, safety net only

OUTPUT_SHAPE = {
    "mechanical": '{"placements": [{"id": "<component id>", "position": [x, y, z]}, ...]}',
    "electrical": '{"netlist": "<SPICE element lines joined with \\n; no title line; comments start with *>"}',
    "combined": '{"placements": [{"id": "<component id>", "position": [x, y, z]}, ...], '
                '"netlist": "<SPICE element lines joined with \\n; no title line; comments start with *>"}',
}

SYSTEM_SINGLE = (
    "You are an engineer producing a design artifact. Reply with ONLY a JSON object "
    "in this exact shape, no prose, no code fences:\n{shape}"
)
SYSTEM_AGENTIC = (
    "You are an engineer producing a design artifact. You have a `grade` tool that "
    "checks a candidate design against the task's constraints and returns the "
    f"violations. You may call it at most {MAX_ATTEMPTS} times. Call it with your "
    "candidate; if it reports violations, fix them and call again. Stop as soon as "
    "it passes. The artifact must be a JSON object in this exact shape:\n{shape}"
)

GRADE_TOOL = {
    "type": "function",
    "function": {
        "name": "grade",
        "description": "Check a candidate design artifact against the task constraints.",
        "parameters": {
            "type": "object",
            "properties": {"artifact": {"type": "object", "description": "The design artifact JSON."}},
            "required": ["artifact"],
        },
    },
}


# ---------- OpenRouter client ----------

def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def chat(model: str, messages: list, tools=None, *, opts: dict) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "usage": {"include": True},
        "provider": {"data_collection": "deny"},  # never route to hosts that train on prompts
    }
    if tools:
        body["tools"] = tools
    if opts.get("provider"):
        body["provider"].update({"order": [opts["provider"]], "allow_fallbacks": False})
    if opts.get("reasoning"):
        body["reasoning"] = {"effort": opts["reasoning"]}
    if opts.get("temperature") is not None:
        body["temperature"] = opts["temperature"]

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/krbhadra/engbench",
            "X-Title": "EngBench",
        },
    )
    for attempt in range(4):  # ponytail: simple backoff on 429/5xx
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 ** attempt * 5)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}") from e


# ---------- helpers ----------

def parse_artifact(text: str | None):
    """Pull the first JSON object out of a model reply; None if unparseable."""
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def safe_grade(task, artifact):
    if not isinstance(artifact, dict):
        return {"passed": False, "violations": ["output was not a JSON object"]}
    try:
        return grader.grade(task, artifact)
    except Exception as e:  # malformed artifact (wrong keys, bad shapes) is the model's fault
        return {"passed": False, "violations": [f"artifact malformed: {type(e).__name__}: {e}"]}


def _accumulate(usage_total, resp):
    u = resp.get("usage") or {}
    for k in ("prompt_tokens", "completion_tokens"):
        usage_total[k] = usage_total.get(k, 0) + (u.get(k) or 0)
    usage_total["cost"] = usage_total.get("cost", 0.0) + (u.get("cost") or 0.0)


def _task_prompt(task):
    return f"Task {task['id']}: {task.get('title', '')}\n\n{task['description']}"


# ---------- tracks ----------

def run_single_shot(model, task, opts, chat=chat):
    messages = [
        {"role": "system", "content": SYSTEM_SINGLE.format(shape=OUTPUT_SHAPE[task["domain"]])},
        {"role": "user", "content": _task_prompt(task)},
    ]
    usage = {}
    resp = chat(model, messages, opts=opts)
    _accumulate(usage, resp)
    content = resp["choices"][0]["message"].get("content")
    artifact = parse_artifact(content)
    result = safe_grade(task, artifact)
    return {
        "passed": result["passed"],
        "attempts": [{"artifact": artifact, "raw": content, **result}],
        "usage": usage,
        "provider": resp.get("provider"),
        "resolved_model": resp.get("model"),
    }


def run_agentic(model, task, opts, chat=chat):
    messages = [
        {"role": "system", "content": SYSTEM_AGENTIC.format(shape=OUTPUT_SHAPE[task["domain"]])},
        {"role": "user", "content": _task_prompt(task)},
    ]
    usage, attempts, provider, resolved = {}, [], None, None
    t0 = time.time()

    while len(attempts) < MAX_ATTEMPTS and time.time() - t0 < TASK_TIMEOUT:
        resp = chat(model, messages, tools=[GRADE_TOOL], opts=opts)
        _accumulate(usage, resp)
        provider, resolved = resp.get("provider"), resp.get("model")
        msg = resp["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []

        if not calls:
            # model stopped talking to the tool; its final message is its answer
            artifact = parse_artifact(msg.get("content"))
            result = safe_grade(task, artifact)
            attempts.append({"artifact": artifact, "raw": msg.get("content"), **result})
            break

        for call in calls:
            if len(attempts) >= MAX_ATTEMPTS:
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps({"error": "attempt budget exhausted"})})
                continue
            args = parse_artifact(call["function"].get("arguments"))
            artifact = args.get("artifact") if isinstance(args, dict) else None
            result = safe_grade(task, artifact)
            attempts.append({"artifact": artifact, **result})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
        if any(a["passed"] for a in attempts):
            break

    passed = None if attempts and attempts[-1]["passed"] is None else any(a["passed"] for a in attempts)
    return {"passed": passed, "attempts": attempts, "usage": usage,
            "provider": provider, "resolved_model": resolved}


RUNNERS = {"single-shot": run_single_shot, "agentic": run_agentic}


# ---------- main ----------

def slug(s):
    return re.sub(r"[^\w.-]", "_", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="OpenRouter model id, e.g. anthropic/claude-sonnet-4")
    ap.add_argument("--track", choices=RUNNERS, required=True)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--tasks", nargs="*", help="task ids to run (default: all)")
    ap.add_argument("--provider", help="pin an OpenRouter host, fallbacks disabled (open-weight models)")
    ap.add_argument("--reasoning", choices=["low", "medium", "high"])
    ap.add_argument("--temperature", type=float)
    args = ap.parse_args()

    load_env()
    if "OPENROUTER_API_KEY" not in os.environ:
        sys.exit("OPENROUTER_API_KEY not set (put it in .env at the repo root)")

    opts = {"provider": args.provider, "reasoning": args.reasoning, "temperature": args.temperature}
    tasks = [json.loads(p.read_text()) for p in sorted(TASKS_DIR.glob("*.json"))]
    if args.tasks:
        tasks = [t for t in tasks if t["id"] in args.tasks]

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{slug(args.model)}__{args.track}.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else {
        "model": args.model, "track": args.track, "settings": opts,
        "max_attempts": MAX_ATTEMPTS, "records": [],
    }
    done = {(r["task"], r["trial"]) for r in results["records"]}
    runner = RUNNERS[args.track]

    for task in tasks:
        for trial in range(1, args.trials + 1):
            if (task["id"], trial) in done:
                continue
            t0 = time.time()
            rec = runner(args.model, task, opts)
            rec.update({"task": task["id"], "trial": trial, "seconds": round(time.time() - t0, 1),
                        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            results["records"].append(rec)
            out_path.write_text(json.dumps(results, indent=1))  # save after every record
            status = {True: "PASS", False: "FAIL", None: "SKIP"}[rec["passed"]]
            print(f"{status} {task['id']} trial {trial} attempts={len(rec['attempts'])} "
                  f"cost=${rec['usage'].get('cost', 0):.4f} provider={rec['provider']}")

    print(f"\nwrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
