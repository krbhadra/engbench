# EngBench — Vision

## The problem

Every existing LLM benchmark for engineering is single-discipline and graded
by an LLM judge or multiple-choice matching:

- **Physics:** UGPhysics, ABench-Physics, PhysReason, GPQA-Diamond
- **Mechanical/CAD:** OmniCAD, Text2CAD-Bench, MechVQA, P3D-Bench
- **Electrical:** CircuitLM, CircuitSense, AnalogAgent, the CIRCUIT dataset

None of them test whether a model can hold constraints from **two
disciplines at once** — the way a real engineer has to. And most grade
answers by having another LLM (or a human) decide if the response "looks
right," instead of running the design through a real checker.

## What we're building

A benchmark where models don't answer questions — they **produce design
artifacts** (component placements, wiring/netlists), and those artifacts are
graded by deterministic solvers, not an LLM judge:

- **Mechanical grader:** bounding-box fit, collision, and clearance checks
- **Electrical grader:** ngspice-based voltage-drop / power-delivery checks
- **Combined tasks:** one problem, both graders — e.g. "place these
  components without collision AND keep the wiring run under the voltage
  drop limit"

A design either satisfies the constraints or it doesn't. No ambiguity, no
judge model to argue with, fully reproducible.

## Why this is worth building

- It's a gap, not a rehash — nobody has published a solver-graded,
  cross-domain systems-engineering benchmark
- It's small enough to actually finish: ~30 tasks, two lightweight solvers,
  no CAD engine or GPU required
- It produces a real artifact: a public leaderboard + writeup showing where
  current models fail at multi-constraint reasoning, which is a much
  stronger portfolio piece than "I called an LLM API"

## Scope for v1

**In:**
- 2 domains — mechanical + electrical (physics dropped: already the most
  saturated benchmark space, adds a third solver for no differentiation)
- ~30 hand-authored tasks: 12 mechanical, 12 electrical, 6 combined
- 4-5 models evaluated (Claude, GPT, Gemini, one open-weight model)
- Public GitHub repo: task specs, grader code, harness, raw results,
  leaderboard, writeup

**Out (future work, not v1):**
- Thermal simulation, structural load analysis, full CAD geometry (STEP
  files) — real solvers exist but are heavy to integrate for a first pass
- More than 5 models — diminishing value for the extra cost
- Any LLM-as-judge grading, anywhere, ever — the whole point is
  deterministic, reproducible pass/fail

## License / openness

MIT licensed, public from the start. Tasks, graders, harness, and raw model
outputs all ship in the repo so anyone can reproduce or extend the results.
