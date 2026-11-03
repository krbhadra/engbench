# EngBench

**Can an AI do the engineering that brings a real product into the world, and can an engineer trust the answer?**

EngBench is an open benchmark for engineering design: grid-connected battery storage, from component calculations up to the battery management and protection subsystem. Models hand in a design artifact (sizing, part choices, requirement records). **Deterministic solvers grade it, never another LLM.** A design passes only if it meets every requirement: the stated ones, and the hidden ones a senior engineering team would find unprompted.

> **Status: v0.1 preview.** Levels 1–4 of 6 exist, so the highest score reachable today is 70. Only Claude models have been run so far. GPT, Gemini and open-weight models are waiting for funding or contributors ([Support](#support-the-benchmark)).

## Results (v0.1, November 2026)

Score out of 100. Levels 3 and 4 are scored on private held-out tasks the models have never seen.

| Model | Single-shot | Agentic | Levels run |
|---|---:|---:|---|
| Claude Opus 5.5 | 29.6 | **56.0** | 1–4 |
| Claude Sonnet 5.5 | 16.9 | 47.6 | 1–4 |
| Claude Haiku 4.5 | 6.2 | 8.7 | 1–3 |
| Claude Fable 5.1 | – | – | release run pending |
| GPT, Gemini, open-weight | – | – | [needs funding or a contributor](#support-the-benchmark) |

- **Single-shot**: one answer, no tools.
- **Agentic**: the model gets a Python sandbox and a test lab with three rounds. The test lab reports symptoms ("the precharge test timed out"), never causes or numbers.

Full write-up: [docs/RESULTS.md](docs/RESULTS.md). Interactive dashboard, with every design and every violation: [docs/index.html](docs/index.html).

## The ladder

Each level roughly doubles the expert effort of the one below and is worth fixed points. A model earns those points times its pass rate on that level.

| Level | Points | Expert effort | Tasks | What it tests |
|---|---:|---|---|---|
| 1 | 15 | ~15 min | `mech`, `elec`, `comb`, `pe_cooling`, `coolant_loop` | Component calculations, physics stated ([spec](docs/families/level1.md)) |
| 2 | 20 | ~1 h | `bess` | Storage chain from cells to the 20 kV connection, standards named ([spec](docs/families/bess.md)) |
| 3 | 15 | ~4 h | `bess3` | Same chain, nothing named, hidden requirements ([spec](docs/families/bess3.md)) |
| 4 | 20 | ~1 day | `bms4` | Battery management and DC protection subsystem with requirements traced to stakeholder needs ([spec](docs/families/bms4.md)) |
| 5 | 15 | ~1 week | – | Product programme across departments (planned) |
| 6 | 15 | ~1 month+ | – | Whole engineering organisation (planned) |

Why it is built this way: [VISION.md](VISION.md). How tasks are written: [docs/TASK_STANDARD.md](docs/TASK_STANDARD.md).

## How grading stays honest

- **Solvers, not judges.** Every requirement is checked by code that implements the published method: IEC 60269, IEC 61660-1, DIN VDE 0298-4, VDE-AR-N 4110 and others. Standards are cited by number and never reproduced.
- **Every task has a golden solution that must pass and broken solutions that must fail.** Run `python solvers/test_solvers.py` (1,139 checks).
- **Fair hidden checks.** A hidden requirement uses the least strict defensible reading, so a design fails only when it is wrong under every reasonable method.
- **Perturbed parameters.** Generated tasks perturb every number per seed, so a model can't recall the answer.
- **Held-out seeds.** Official level 3–4 scores use private seeds that are not in this repository. The public seeds are for reproduction.

## Run it

```bash
pip install -r requirements.txt
python solvers/test_solvers.py
python harness/test_harness.py
```

The electrical grader needs the [ngspice](https://ngspice.sourceforge.io) CLI on your PATH. Every other grader uses only the Python standard library.

Models are called through one of two transports:

- **OpenRouter** (default): any model. Put `OPENROUTER_API_KEY=sk-or-...` in a `.env` file at the repo root. Turn on OpenRouter's no-logging provider filter so the tasks don't leak into training data.
- **claude-cli**: Claude models on a Claude subscription, through the `claude` CLI in headless mode with all of its own tools disabled. These results are labelled `[claude-cli]`.

```bash
python harness/run_eval.py --track single-shot --model openai/gpt-... --trials 1
python harness/run_eval.py --track agentic --model openai/gpt-... --trials 1
python harness/leaderboard.py        # scores
python harness/usage.py              # tokens and cost
python harness/report.py             # rebuild docs/index.html
```

Runs can be resumed: records already in the results file are skipped. Results land in `results/`, one JSON file per model per track, with the full trajectory of every attempt.

**What a run costs.** API-equivalent prices for one frontier model on all levels, both tracks, 3 trials:
- Opus 5.5: about $513 ($435 agentic, $78 single-shot).
- Sonnet 5.5: about $569.
- With 1 trial: about a third of that.

Almost all of the cost is the agentic track. Measured per run with `harness/usage.py`.

## Contribute results

Have API access to a model that isn't on the board? Run it on the public set and send in the results file. Every stored design is re-graded by the solvers, so a submission doesn't need to be trusted. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Support the benchmark

EngBench is built by one engineer in battery energy storage, in their spare time. Claude models run on a personal subscription. Running GPT, Gemini and open-weight models needs API credit:

| Credit | Runs |
|---:|---|
| ~$25 | One model, single-shot, all levels, 1 trial |
| ~$150 | One model, both tracks, all levels, 1 trial |
| ~$500 | One model, the full official run (3 trials) |

<!-- TODO(author): add the GitHub Sponsors / Ko-fi link once the account is approved -->
**Donate:** link coming soon. Donated OpenRouter credit is just as welcome; open an issue.

Every donation is spent on model runs. The results page states which runs donations paid for.

## Known limitations (v0.1)

- **Levels 5–6 don't exist yet**, so the maximum reachable score is 70.
- **Only Claude models have been run.** Until other vendors are on the board, read this as a calibration of the ladder, not a ranking of vendors.
- **The agentic test lab at level 4 names the requirement record that failed**, a narrower clue than levels 2–3 give. This makes level 4 relatively easy on the agentic track: Opus 5.5 passes 67% of the held-out level-4 tasks and 64% of level 3.
- **The level 3–4 answer keys are written by one engineer** (the author, a power-electronics and battery-storage engineer). The vision calls for a second reviewer per discipline.
- **Expert-effort figures are targets.** They have not yet been measured with human baselines.

## License

MIT. See [LICENSE](LICENSE). The held-out seeds are not distributed.
