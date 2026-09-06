# EngBench — Vision

## The problem

Every existing LLM benchmark for engineering is single-discipline and graded
by an LLM judge or multiple-choice matching:

- **Physics:** UGPhysics, ABench-Physics, PhysReason, GPQA-Diamond
- **Mechanical/CAD:** OmniCAD, Text2CAD-Bench, MechVQA, P3D-Bench
- **Electrical:** CircuitLM, CircuitSense, AnalogAgent, the CIRCUIT dataset

None of them test whether a model can hold constraints from **two
disciplines at once** — the way a real engineer has to. Most grade answers
by having another LLM (or a human) decide if the response "looks right,"
instead of running the design through a real checker. And none of them
separate *knowing the answer* from *being able to iterate toward it with
tool feedback*, which is the skill that actually matters when a model is
used as an engineering assistant.

## What we're building

A benchmark where models don't answer questions — they **produce design
artifacts** (component placements, wiring/netlists), and those artifacts are
graded by deterministic solvers, not an LLM judge:

- **Mechanical grader:** bounding-box fit, collision, and clearance checks
- **Electrical grader:** ngspice-based voltage-drop / power-delivery checks
- **Combined tasks:** one problem, both graders. The grader derives wire
  length from the model's own placements and injects that wire resistance
  into the netlist before simulating — so a bad layout shows up as a
  voltage-drop failure. The model cannot lie about wire length.

A design either satisfies the constraints or it doesn't. No ambiguity, no
judge model to argue with, fully reproducible.

## Two tracks

Every model is scored on the same tasks twice:

| Track | What the model gets | What it measures |
|---|---|---|
| **Single-shot** | The task description. One response. | Raw engineering reasoning — can it get the design right cold. |
| **Agentic** | The task description plus one tool: `grade(artifact)`, which returns the solver's violation list. Up to 5 grader calls. | Whether it can use deterministic feedback to converge — the actual assistant workflow. |

The two tracks are run independently (the agentic track is not "single-shot
plus retries"). The gap between them is a first-class result: a model that
scores low single-shot but closes the gap with feedback is a different tool
from one that plateaus.

The agentic tool is the grader itself, so the no-LLM-judge rule holds on
both tracks.

## Budget and metrics

Following the conventions of SWE-bench, Terminal-Bench, tau-bench and Aider:

- **Attempt cap:** 5 grader calls per task on the agentic track.
- **Wall-clock timeout:** 5 minutes per task, as a safety net only — never a
  scoring mechanism.
- **Trials:** every task is run 3 times per model per track.
- **Reported per model, per track:** mean pass rate, pass^3 (fraction of
  tasks passed in all three trials), mean attempts to first pass (agentic),
  mean tokens and cost per task.
- **Token budgets are not used as a cutoff.** They punish verbose models
  unfairly and are hard to explain. Tokens and cost are recorded and
  reported alongside the score.

## Reproducibility rules

- Model calls go through **OpenRouter** via its OpenAI-compatible endpoint.
  Open-weight models are pinned to a named host and quantization with
  fallbacks disabled. A second transport runs Claude models through the
  `claude` CLI on a subscription; those results are labeled separately
  because the tool protocol and thinking defaults differ.
- Every result record stores: model string, resolved snapshot, serving
  provider, sampling and reasoning settings, tokens, cost, timestamp, and
  the full attempt trajectory (every artifact submitted and every violation
  list returned).
- Providers that log or train on prompts are excluded, so the task set does
  not leak into future training data.
- Tasks, graders, harness, raw model outputs and the leaderboard all ship in
  the repo. Anyone can rerun the whole thing with one key.

## Why this is worth building

- It's a gap, not a rehash — nobody has published a solver-graded,
  cross-domain, two-track engineering benchmark
- It's small enough to actually finish: ~30 tasks, two lightweight solvers,
  no CAD engine or GPU required
- It produces a real artifact: a public leaderboard + writeup showing where
  current models fail at multi-constraint reasoning, and how much of that
  failure tool feedback can recover

## Scope for v1

**In:**
- 2 domains — mechanical + electrical (physics dropped: already the most
  saturated benchmark space, adds a third solver for no differentiation)
- ~30 hand-authored tasks: 12 mechanical, 12 electrical, 6 combined, each
  with a golden solution and at least one broken solution in the self-check
- Two tracks, single-shot and agentic, on every task
- 4-5 models evaluated (Claude, GPT, Gemini, one open-weight model)
- Public GitHub repo: task specs, grader code, harness, raw results,
  leaderboard, writeup

**Out (future work, not v1):**
- Thermal simulation, structural load analysis, full CAD geometry (STEP
  files) — real solvers exist but are heavy to integrate for a first pass
- Component rotation in the mechanical grader — tasks are authored with
  fixed orientations
- Richer agentic tools (code sandbox, direct ngspice access) — the grader
  tool is enough to measure feedback use without a sandboxing problem
- More than 5 models — diminishing value for the extra cost
- Any LLM-as-judge grading, anywhere, ever — the whole point is
  deterministic, reproducible pass/fail

## License / openness

MIT licensed, public from the start. Tasks, graders, harness, and raw model
outputs all ship in the repo so anyone can reproduce or extend the results.
