"""EngBench harness: run one model on one track, write results/<model>__<track>.json.

    python harness/run_eval.py --model anthropic/claude-sonnet-4 --track agentic
    python harness/run_eval.py --model meta-llama/llama-3.3-70b-instruct --provider fireworks --track single-shot
    python harness/run_eval.py --transport claude-cli --model sonnet --track agentic

Stdlib only. Two transports:
  openrouter  - OpenRouter's OpenAI-compatible endpoint, native tool calls (default)
  claude-cli  - the `claude` CLI in headless mode on a Claude subscription. Built-in
                tools, MCP servers, skills and settings are all disabled so the model
                sees only our prompt. The agentic loop is a text protocol (submit
                artifact -> receive grader result) rather than native tool calls.
Resumable: (task, trial) pairs already in the results file are skipped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
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

SYSTEM_AGENTIC_TEXT = (
    "You are an engineer producing a design artifact. Reply with ONLY a JSON artifact "
    "(no prose, no code fences) to submit it for grading; you will receive the grader's "
    f"result as the next message. You may submit at most {MAX_ATTEMPTS} times. If it "
    "reports violations, fix them and submit again. When it reports passed: true, reply "
    "with the single word DONE. The artifact must be a JSON object in this exact shape:\n{shape}"
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


# ---------- claude-cli transport ----------

CLI_FLAGS = ["--tools", "", "--strict-mcp-config", "--disable-slash-commands",
             "--setting-sources", "", "--output-format", "json"]


def _claude_exe() -> str:
    found = shutil.which("claude") or "claude"
    if found.lower().endswith(".cmd"):
        # npm's batch wrapper mangles empty-string args like `--tools ""`; call the real binary
        native = Path(found).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
        if native.exists():
            return str(native)
    return found


def make_cli_chat():
    """One closure per task: holds the CLI session id so turns share context via --resume."""
    session = {"id": None}

    def chat_cli(model: str, messages: list, tools=None, *, opts: dict) -> dict:
        system = messages[0]["content"]
        if tools:  # text protocol replaces the tool protocol; keep the shape line
            system = SYSTEM_AGENTIC_TEXT.format(shape=system.rsplit("\n", 1)[1])
        prompt = messages[1]["content"] if session["id"] is None else \
            "Grader result: " + messages[-1]["content"]

        cmd = [_claude_exe(), "-p", "--model", model, "--system-prompt", system, *CLI_FLAGS]
        cmd += ["--resume", session["id"]] if session["id"] else []
        cmd += ["--effort", opts["reasoning"]] if opts.get("reasoning") else []
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}  # allow nesting

        backoff = [15, 60, 300, 900, 1800]  # subscription rate limits reset on a long window
        for attempt in range(len(backoff) + 1):
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  env=env, timeout=TASK_TIMEOUT)  # prompt on stdin: no cmdline length limit
            try:
                d = json.loads(proc.stdout)
            except json.JSONDecodeError:
                d = {"is_error": True, "result": (proc.stdout + proc.stderr)[-500:]}
            if not d.get("is_error"):
                break
            if attempt == len(backoff):
                raise RuntimeError(f"claude cli: {d.get('result')}")
            print(f"  cli error ({str(d.get('result'))[:80]}), retry in {backoff[attempt]}s", flush=True)
            time.sleep(backoff[attempt])

        session["id"] = d.get("session_id")
        text = d.get("result") or ""
        usage = d.get("modelUsage") or {}
        canonical = next(iter(usage.values()), {}).get("canonicalModel", model)
        msg = {"role": "assistant", "content": text}
        if tools and (art := parse_artifact(text)) is not None and text.strip().upper() != "DONE":
            # a JSON reply is a submission: present it as a grade tool call
            msg = {"role": "assistant", "content": None, "tool_calls": [{
                "id": f"cli{len(messages)}", "type": "function",
                "function": {"name": "grade", "arguments": json.dumps({"artifact": art})}}]}
        return {
            "choices": [{"message": msg}],
            "usage": {"prompt_tokens": sum(u.get("inputTokens", 0) + u.get("cacheReadInputTokens", 0)
                                           + u.get("cacheCreationInputTokens", 0) for u in usage.values()),
                      "completion_tokens": sum(u.get("outputTokens", 0) for u in usage.values()),
                      "cost": d.get("total_cost_usd") or 0.0},  # list price; subscription absorbs it
            "provider": "claude-cli (subscription)",
            "model": canonical,
        }

    return chat_cli


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
    ap.add_argument("--model", required=True, help="OpenRouter model id, or a claude-cli model (haiku, sonnet, opus, ...)")
    ap.add_argument("--track", choices=RUNNERS, required=True)
    ap.add_argument("--transport", choices=["openrouter", "claude-cli"], default="openrouter")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--tasks", nargs="*", help="task ids to run (default: all)")
    ap.add_argument("--provider", help="pin an OpenRouter host, fallbacks disabled (open-weight models)")
    ap.add_argument("--reasoning", choices=["low", "medium", "high"])
    ap.add_argument("--temperature", type=float)
    args = ap.parse_args()

    cli = args.transport == "claude-cli"
    if not cli:
        load_env()
        if "OPENROUTER_API_KEY" not in os.environ:
            sys.exit("OPENROUTER_API_KEY not set (put it in .env at the repo root)")

    opts = {"provider": args.provider, "reasoning": args.reasoning, "temperature": args.temperature}
    tasks = [json.loads(p.read_text()) for p in sorted(TASKS_DIR.glob("*.json"))]
    if args.tasks:
        tasks = [t for t in tasks if t["id"] in args.tasks]

    label = f"{args.model} [claude-cli]" if cli else args.model
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{slug(label)}__{args.track}.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else {
        "model": label, "transport": args.transport, "track": args.track, "settings": opts,
        "max_attempts": MAX_ATTEMPTS, "records": [],
    }
    done = {(r["task"], r["trial"]) for r in results["records"]}
    runner = RUNNERS[args.track]

    for task in tasks:
        for trial in range(1, args.trials + 1):
            if (task["id"], trial) in done:
                continue
            t0 = time.time()
            try:
                rec = runner(args.model, task, opts, chat=make_cli_chat() if cli else chat)
            except Exception as e:  # leave the record undone so a re-run resumes it
                print(f"ERROR {task['id']} trial {trial}: {type(e).__name__}: {str(e)[:200]}", flush=True)
                continue
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
