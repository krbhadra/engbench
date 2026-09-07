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

## 3. Fully specified

- The description states every parameter, every constraint, and the physics
  model to use, so a correct solver has no free choices except the design
  itself. If two textbooks would give different formulas, the task says which.
- The description states the exact output shape and the task JSON carries it
  as `output_shape`.
- Units are explicit everywhere.

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

## 5. Golden and broken

- Every task has a golden solution in `solvers/solutions.json` that passes.
  For generated families the golden is found by brute force or optimization,
  which doubles as the feasibility proof.
- Every task has at least two broken solutions, each expected to fail with a
  named violation substring. The grader must fail them. A grader that cannot
  fail a wrong answer is not a grader.
- Generated families reject seeds that are infeasible or trivial (a feasible
  fraction of the design space above a stated ceiling).

## 6. Labeled

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
