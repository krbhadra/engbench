# EngBench v0.1 results

November 2026. Claude models only, levels 1–4 of 6. Levels 3 and 4 are scored on private held-out tasks: 13 per level, 3 trials each. Raw outputs, every attempt and every grader violation are in `results/` and on the [dashboard](index.html).

## Scores

| Model | Single-shot | Agentic | Agentic gain |
|---|---:|---:|---:|
| Claude Opus 5.5 | 29.6 | **56.0** | +26.4 |
| Claude Sonnet 5.5 | 16.9 | 47.6 | +30.7 |
| Claude Haiku 4.5 (levels 1–3) | 6.2 | 8.7 | +2.5 |

Pass rate per level (levels 3–4 held-out):

| Model, track | L1 (15 pts) | L2 (20) | L3 (15) | L4 (20) |
|---|---:|---:|---:|---:|
| Opus 5.5, single-shot | 92% | 59% | 21% | 5% |
| Opus 5.5, agentic | 100% | 90% | 64% | 67% |
| Sonnet 5.5, single-shot | 72% | 29% | 3% | 0% |
| Sonnet 5.5, agentic | 97% | 92% | 44% | 41% |
| Haiku 4.5, single-shot | 42% | 0% | 0% | – |
| Haiku 4.5, agentic | 53% | 2% | 3% | – |

## What the numbers say

**1. Engineering knowledge applied cold is the bottleneck.** Single-shot falls steeply up the ladder. Opus passes 92% of the component tasks, 59% when the standards are named (level 2), and 21% when it has to work out for itself which rules apply (level 3). Its battery management designs pass first time 5% of the time.

**2. A test lab more than doubles what strong models deliver.** With a Python sandbox and three rounds of symptom-only test reports, Opus goes from 21% to 64% at level 3. Sonnet goes from 3% to 44%. The test lab never gives the cause or the numbers, so the model has to trace a symptom back to the decision that caused it. Strong models can do this. Haiku mostly can't: it gains under 3 points.

**3. The failures look like a junior engineer's, not random noise.** The most common single-shot failures on held-out level 3:
- **Fuse vs cable coordination.** The fuse's conventional fusing current is above the cable's thermal limit (IEC 60364-4-43). Opus failed this in 13 of 39 trials, Sonnet in 23.
- **PCS sized at nameplate.** The power conversion system is rated at nameplate, not at site temperature and minimum grid voltage (Opus 12, Sonnet 21).
- **Fuse breaking capacity below the DC bus fault current** (IEC 61660-1).
- **Transformer and heating sizing** that ignores site ambient conditions or cold charging.

At level 4 the most common miss is **requirements traceability**:
- The 24 V control-supply ride-through requirement derives from three stakeholder needs: the network operator's connection rules, safety, and (on frequency-reserve plants) the reserve service. The models trace it to only one or two of them. That miss accounts for 27 of Opus's 39 single-shot level-4 trials.
- **Sonnet's precharge circuit overheats** when precharging into a shorted DC link (27 of 39). That is a hidden fault case the brief never mentions.

**4. No model passes level 4 on the first design.** The first-design pass rate at level 4 is 0% for both Opus and Sonnet on the agentic track. Every pass comes from the test-lab rounds, and Opus needs 2.5 rounds on average.

## Read with care

- **Only one vendor.** These results calibrate the ladder; they don't rank vendors. GPT, Gemini and open-weight models are waiting for API credit or contributors (see the [README](../README.md#support-the-benchmark)).
- **The maximum today is 70** (levels 1–4). A score of 56 means "56 of 70 points available".
- **Level 4 is too easy on the agentic track.** Its test report names the requirement record that failed, which is a narrower clue than levels 2–3 give. So agentic level 4 (67%) is not harder than level 3 (64%) for Opus, although single-shot shows it clearly is (5% vs 21%). Making the level-4 report symptom-only is planned for v0.2.
- **Level 4 single-shot depends heavily on one traceability rule** (the ride-through requirement above). The rule is a deliberate author ruling. It is documented in [families/bms4.md](families/bms4.md), and the brief contains every fact needed to make the link.
- **The answer keys have one author.** The level 3–4 keys were written by a practising battery-storage engineer, and every grader is checked against golden and broken designs. An independent second reviewer per discipline is still open.
- **The command-line tool for Claude** runs the agentic loop as a text protocol with extended thinking on. API runs use native tool calls. Results from the two transports are labelled and never mixed.

## Cost

API-equivalent, measured with `harness/usage.py`. All levels, both tracks, 3 trials, public plus held-out tasks.

| Model | Input tokens (mostly cached) | Output tokens | Cost |
|---|---:|---:|---:|
| Opus 5.5 | 55 M | 18.7 M | ~$513 |
| Sonnet 5.5 | 110 M | 43 M | ~$569 |

Sonnet writes more than twice as much as Opus, so it costs more per run even though its price per token is lower. The agentic track is about 85% of the cost.
