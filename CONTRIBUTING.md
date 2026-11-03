# Contributing

## Run a model that isn't on the board

You need API access to the model, normally an OpenRouter key, and about $25–150 of credit for one model at 1 trial (see the [README](README.md#run-it)).

1. **Set up**, then check that the graders work on your machine:
   ```bash
   pip install -r requirements.txt
   python solvers/test_solvers.py
   ```
2. **Configure OpenRouter.** Put `OPENROUTER_API_KEY=...` in `.env`. Turn on the no-logging provider filter in your OpenRouter settings so the tasks don't end up in anyone's training data.
3. **Start small.** Run 1 trial on a few tasks to check the transport works:
   ```bash
   python harness/run_eval.py --track single-shot --model <openrouter-id> --trials 1 --tasks mech_001 bess_001
   ```
4. **Full public run.** One trial is fine, and so is single-shot only:
   ```bash
   python harness/run_eval.py --track single-shot --model <openrouter-id> --trials 1
   python harness/run_eval.py --track agentic --model <openrouter-id> --trials 1
   ```
   - For an open-weight model, pin a host with `--provider` so the run is reproducible.
   - If the model supports a reasoning effort setting, pass `--reasoning`.
   - Runs can be resumed, so an interrupted run picks up where it stopped.
5. **Open a pull request** with the files from `results/`. In the description, list:
   - the model id;
   - the provider or host;
   - the date;
   - the EngBench commit you ran (`git rev-parse HEAD`);
   - the cost, from `python harness/usage.py`.

Don't edit task files or graders in the same pull request.

## How submissions are checked

Every stored design is re-graded by the solvers (`python harness/regrade.py`), so a submission doesn't need to be trusted. A pass that doesn't re-grade as a pass is rejected.

Submitted runs are scored on the **public** seeds and labelled *community, public set*. The official level 3–4 score uses private held-out seeds that are not in this repository. To get a model an official score, a maintainer runs it on the held-out seeds. Donated API credit makes that possible: open an issue.

## Other ways to help

- **Engineering review.** The level 3–4 answer keys have one author. If you practise power electronics, protection, battery systems or grid connection, review a family spec in `docs/families/` and open an issue for anything you would design differently. Under the fairness rule, a defensible stricter reading is accepted. A defensible looser one means the grader is wrong.
- **Bugs in a grader.** Open an issue with the task id and the design. The fix comes with a golden or broken design that would have caught the bug.
