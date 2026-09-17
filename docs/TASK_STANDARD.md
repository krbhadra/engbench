# Task authoring standard

Every EngBench task, whether hand-written or generated, meets these rules. The
self-check (`python solvers/test_solvers.py`) enforces the mechanical ones.

## 1. Grounded in a citable source

- The task JSON carries a `sources` list: the published material the physics,
  method, or catalog comes from, with license.
- The source is cited and restated in the task's own words. Problem text,
  tables, and figures from copyrighted sources are never reproduced.
- Preferred sources, in order: US government works, CC BY, MIT/BSD code,
  free-to-read papers and datasheets. Non-commercial data is linked, never
  vendored. See `docs/source-survey.md`.

## 2. Perturbed, never the source's numbers

- Generated families sample every parameter per seed from stated ranges and
  record the `seed`. Hand-written tasks use numbers that do not appear in any
  source.
- The answer key is recomputed from the task's own parameters by the grader.
  Nothing is looked up from the source at grading time.

## 3. Fully specified, method named

- The description states every parameter, every requirement, and the exact
  output shape. Units are explicit everywhere.
- **Knowledge-required families** (the default from here on) *name* the
  method, standard, or curve the design must satisfy and cite it in
  `sources`, but do not restate it. The grader implements exactly that named
  method. If two published methods would disagree, the task names one.
- **Physics families** (pe_cooling, coolant_loop) state the model in full so
  only the optimum is hard. They remain as a floor and are labeled
  `"mode": "stated"`; knowledge-required tasks are `"mode": "named"`.
- The task JSON carries the output shape as `output_shape`.

## 4. Deterministically graded

- The grader is a solver, a closed-form computation, or a simulation. No LLM
  anywhere in grading.
- `grade(task, output)` returns `{"passed": bool, "violations": [str, ...]}`.
  Every violation names the constraint, the computed value, and the limit,
  so the agentic track gets actionable feedback.
- The grader accepts any design that satisfies every constraint, not just the
  golden one.
- Tolerances absorb float noise only (see `TOL` in the electrical grader), never
  engineering margin. Margin belongs in the task's limits.

## 5. Objective, not just feasibility

- A task whose only question is "does a feasible design exist" is saturated
  by frontier models as soon as the physics is stated (pe_cooling v2: 36/36
  passes, yet picks cost 1.2-3x the optimum). Generated families therefore
  carry `objective`: `{"minimize": <metric>, "optimum": <brute force>,
  "tolerance": 0.05}`. A design passes only if it is feasible and its metric
  is within the tolerance of the optimum.
- The description states the objective and the tolerance in words. The
  optimum itself is in the task JSON (as is the golden), never in the prompt
  and never in grader feedback.
- Seeds where more than 25% of feasible designs are already near-optimal are
  rejected as trivial.

## 6. Golden and broken

- Every task has a golden solution in `solvers/solutions.json` that passes.
  For generated families the golden is found by brute force or optimization,
  which doubles as the feasibility proof.
- Every task has at least two broken solutions, each expected to fail with a
  named violation substring. One of them is feasible but far from the
  optimum, so the objective check is exercised too. The grader must fail them. A grader that cannot
  fail a wrong answer is not a grader.
- Generated families reject seeds that are infeasible or trivial (a feasible
  fraction of the design space above a stated ceiling).

## 7. Labeled

- `domain`: the grader module name in `solvers/`.
- `disciplines`: the engineering disciplines the task touches, one or more of
  mechanical, thermal, electrical, electronics, controls, fluids, structural,
  materials. Cross-discipline tasks list every one they couple.
- Industry tags are added later when there is enough coverage to slice by.

## Task JSON skeleton

```json
{
  "id": "family_007",
  "domain": "family",
  "disciplines": ["thermal", "fluids"],
  "title": "short name",
  "description": "everything the model needs, in words",
  "output_shape": "{\"...\": ...}",
  "params": {},
  "limits": {},
  "sources": ["..."],
  "seed": 7
}
```

## Adding a generated family

1. `solvers/<family>.py` with `evaluate(task, design)` and `grade(task, output)`.
2. `taskgen/<family>.py` that samples parameters, brute-forces the design
   space using the grader, rejects trivial and infeasible seeds, derives broken
   cases from the golden, and writes `tasks/<family>_<seed>.json` plus the
   `solutions.json` entry.
3. Run the self-check. Run at least one model on the family and confirm it is
   not saturated before generating more seeds.
