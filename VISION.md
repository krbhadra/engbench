# EngBench — Vision

## The question

Can an AI do the engineering that brings a real product into the world, and
can an engineer trust the answer?

The bar is not one engineer. It is the collective intelligence of a whole
engineering organisation: the systems engineering, programme management and
every department of a company like SpaceX, Tesla or BYD, taking a product from
stakeholder needs to a design that closes across every discipline. A good AI
should act like that organisation does, unprompted: find the requirements
nobody wrote down, choose the architecture with a reason, and make every
department's numbers agree.

Software got its answer from SWE-bench and its descendants: real repos, hidden
tests, pass or fail. Engineering has nothing comparable. Existing benchmarks
are single-component, school-level, or graded by another model deciding
whether the answer "looks right".

## The score

One number out of 100, built so that the lower ranges are easy and the top is
nearly out of reach. Tasks sit on a ladder of six levels. Each level roughly
doubles the expert effort of the one below. Each level is worth a fixed,
published number of points; a model earns that level's points times its pass
rate on that level's tasks, and the score is the sum. Anyone can recompute it
from the raw results with a calculator.

| Score | Level | Points | Expert effort | What a model in this range can be trusted with |
|---|---|---|---|---|
| 0–15 | 1 | 15 | ~15 min | Component calculations when the physics is given |
| 15–35 | 2 | 20 | ~1 h | A full system chain when the standards are named |
| 35–50 | 3 | 15 | ~4 h | A system designed right first time, finding its own requirements |
| 50–70 | 4 | 20 | ~1 day | A product subsystem across disciplines, e.g. battery management + inverter controls + grid code |
| 70–85 | 5 | 15 | ~1 week | A product programme across several departments |
| 85–100 | 6 | 15 | ~1 month+ | A whole engineering organisation's programme |

The "trusted with" column is a target until it is validated: experienced
engineers take sample tasks at each level under the same rules, and a level's
claim stands only if they score where we say. Expert effort is likewise
measured, not guessed, once human baselines exist.

The same score must mean the same thing over time. Each level keeps enough
tasks, and a private held-out set of seeds for the official score, so that a
60 next year means what a 60 means today.

## What makes a level harder

Difficulty comes from scope and coupling, never from arithmetic or tricks.
Moving up the ladder means:

- **More of the organisation.** Level 1 is one component. Level 6 couples
  stakeholder needs, requirements flow-down, architecture trade studies,
  cells and DC side, power electronics and controls, embedded hardware and
  firmware, grid connection and certification, thermal, fire safety,
  mechanical, cost, verification and risk. An error in one department must
  break the others, the way it does in a real programme.
- **More knowledge required, less supplied.** At level 2 the task names the
  standards to design to. From level 3 it names nothing: knowing that VDE-AR-N
  4110, IEC 62619 or IEC 60364-4-43 applies is part of the test.
- **Hidden requirements.** The grader checks requirements the prompt never
  states, the way hidden tests do in software benchmarks: a grid fault at
  0.3 pu, a cold start at full power, a rack in thermal runaway. A senior team
  anticipates them.
- **The optimum, not just a feasible point.** Generated tasks carry an
  objective and a brute-force optimum. A feasible design far from it fails.
- **Messier inputs.** Datasheets with conflicting values, missing data the
  model must flag or bound, site data in the units the source used.
- **Less help from the grader.** At level 3 and above the first submitted
  design is the one that counts.

Deliverables stay machine-checkable at every level: structured requirement
records, architecture graphs with rated interfaces, sizing, bills of material.
Prose that a solver cannot check is not scored.

## Two tracks

| Track | What the model gets | What it measures |
|---|---|---|
| **Single-shot** | The task. One response. | Whether the model carries the engineering knowledge and can apply it cold. |
| **Agentic** | The task plus two tools: `run_python` (standard library, no network, no files, up to 15 calls) to compute and self-check, and `grade(artifact)` (up to 5 calls) which reports *which* checks failed, without the numbers. | Whether it can engineer at a desk: build its own checks, use a verifier, converge on a trustworthy design. |

On the agentic track the **first graded design** is what scores; passing
within five grader calls is reported beside it, because with the checker's
pointer strong models pass almost everything (three of four Claude models
reached 100% on the level-2 storage tasks, October 2026). The grader is a
deterministic solver on both tracks, so the no-judge rule holds.

An earlier loop (grader only, full numeric feedback, no compute tool) is kept
in the results as the `feedback` track, marked superseded.

## Scope and order

Disciplines first, industries later. Industry is a tag once there is enough
coverage to slice by. The first product on the ladder is a grid-connected
battery energy storage system, because the author can validate the
engineering practice directly, not because the benchmark is about storage.

- Level 1: the component families (packing, DC circuits, converter cooling,
  coolant loop), where the physics is stated.
- Level 2: the storage chain from cells to the 20 kV connection, standards
  named (`bess`).
- Level 3: the same chain with nothing named, hidden requirements and one
  submission.
- Level 4 and up: the storage product's subsystems, then its programme.

## Sources and honesty

- Every task cites the published method, standard, dataset, or datasheet it
  rests on. Depth never comes from either the author's or the model's memory.
- Copyrighted standards are cited, never reproduced. Public-domain carriers
  (NASA, DOE, NREL, Sandia, PNNL, IEEE open papers, manufacturer datasheets)
  are preferred.
- Every task has a golden solution that passes and broken solutions that fail
  with a named violation. A grader that cannot fail a wrong answer is not a
  grader.
- A hidden requirement is checked with its least strict defensible reading,
  so a design fails only when it is wrong under every reasonable method.
- Answer keys for levels 3 and up are written or reviewed by practising
  engineers in that discipline; a department is scored only once its key has
  a reviewer.
- Tasks, graders, harness, raw model outputs, and the results page ship in the
  repo under MIT, except the held-out seeds. Anyone can rerun the public set.

## Budget and metrics

- 5 grader calls and 15 Python runs per task on the agentic track; a
  30-minute wall clock as a safety net only; 3 trials per task per model per
  track.
- Headline: the score out of 100, per track. Also reported per model, per
  level, per family: pass rate, first-design rate, pass^3, grader calls to
  pass, tokens and cost. Token budgets are never a cutoff.
- Model calls go through an API with the serving provider pinned and logged,
  or through the `claude` CLI on a subscription, labeled separately. Providers
  that train on prompts are excluded.
- Adaptive serving (harder tasks after correct answers, as in adaptive exams)
  is a later cost optimisation, once every level has a calibrated task bank.
