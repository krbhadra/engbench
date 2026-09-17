# EngBench — Vision

## The question

Can a language model do real engineering work that an engineer would trust?
Not recite formulas, not pass a physics quiz: take requirements, bring the
knowledge a practising engineer carries, and produce a design that closes
across every discipline it touches.

Software got its answer from SWE-bench and its descendants: real repos, real
tests, pass or fail. Engineering has nothing comparable. Existing benchmarks
are single-discipline, school-level, and graded by another model deciding
whether the answer "looks right".

## What we measure

Models produce **design artifacts**: a chosen set of parts, a sizing, a
set of operating points. Those artifacts are graded by **deterministic
solvers**, never by an LLM judge. A design either meets every requirement
or it names the one it misses.

Three properties make a task worth having:

1. **Knowledge is required, not supplied.** The task gives the requirements
   and the data (catalogs, datasheet values, site conditions) and *names* the
   method or standard to design to. It does not restate the method. An
   engineer knows IPC-2221, knows what a manufacturer's derating curve means,
   knows a contactor must be rated above the protection setting. A model that
   does not carry this fails single-shot. Whether it can recover from grader
   feedback is the second thing we measure.
2. **Systems, not components.** Requirements flow down through a
   multi-discipline chain and every level must close: energy, power, voltage
   window, current, thermal, mass, cost, protection coordination, with a
   stated margin policy. The grader also checks **interface consistency**
   between the parts of the design, because a pack whose current limit
   exceeds its contactor rating is a mistake that ships.
3. **The optimum, not just a feasible point.** Every generated task carries an
   objective and a brute-force optimum. A feasible design far from the optimum
   fails. Feasibility alone was saturated by every frontier model the moment
   the physics was stated.

Difficulty comes from the engineering, never from arithmetic. Reference
methods are cited by name, parameters are perturbed per seed, and the grader
recomputes everything from the task's own numbers.

## Two tracks

| Track | What the model gets | What it measures |
|---|---|---|
| **Single-shot** | The task. One response. | Whether the model carries the engineering knowledge and can apply it cold. |
| **Agentic** | The task plus one tool, `grade(artifact)`, returning the violation list. Up to 5 calls. | Whether it can converge on a trustworthy design with deterministic feedback: the assistant workflow. |

The gap between the tracks is a first-class result. The agentic tool is the
grader itself, so the no-judge rule holds on both tracks.

## Scope and order

Disciplines first, industries later. Mechanical, electrical, electronics,
thermal, fluids, controls, structural, materials, and the systems-engineering
layer that ties them together. Industry is a tag once there is enough
coverage to slice by.

The first knowledge-required systems chain is a battery energy storage
system: cells to module to pack to power conversion to grid connection, with
thermal, protection, and mechanical closure. Chosen because the author can
validate the engineering practice directly, not because the benchmark is
about storage.

Earlier families stay in the set as a floor: box-packing and DC-circuit tasks
(saturated), and two cross-discipline physics chains (converter cooling,
battery coolant loop) where the method is stated and only the optimum is hard.

## Sources and honesty

- Every task cites the published method, standard, dataset, or datasheet it
  rests on. Depth never comes from either the author's or the model's memory.
- Copyrighted standards are cited, never reproduced. Public-domain carriers
  (NASA, DOE, NREL, Sandia, PNNL, IEEE open papers, manufacturer datasheets)
  are preferred.
- Every task has a golden solution that passes and broken solutions that fail
  with a named violation. A grader that cannot fail a wrong answer is not a
  grader.
- Tasks, graders, harness, raw model outputs, and the results page all ship
  in the repo under MIT. Anyone can rerun it.

## Budget and metrics

- 5 grader calls per task on the agentic track; 15-minute wall clock as a
  safety net only; 3 trials per task per model per track.
- Reported per model, per track, per family: mean pass rate, pass^3, mean
  attempts to first pass, tokens and cost. Token budgets are never a cutoff.
- Model calls go through OpenRouter with the serving provider pinned and
  logged, or through the `claude` CLI on a subscription, labeled separately.
  Providers that train on prompts are excluded.
