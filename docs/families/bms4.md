# bms4: battery management and protection, level 4 (draft for author review)

The system team hands over a plant that closes at level 3: cells, string and
rack layout, PCS, string fuse, cables, duty and grid service. The task is the
subsystem that keeps it safe and usable: the battery management system and
the DC protection around it. Disciplines: embedded hardware (monitoring chips,
MCU), measurement (accuracy budgets), power electronics (precharge, DC
switching), protection coordination, battery operation (SOC, balancing) and
grid service (FCR).

An error in one discipline breaks another, as in a real programme. A cheap
current sensor drifts, the SOC error eats the energy margin, and the plant
fails FCR prequalification. A long daisy chain is cheap, but its scan time
breaks the protection reaction time.

Same rules as level 3: nothing is named, the hidden requirements below are
never mentioned, the fairness rule holds (least strict defensible reading),
deviations must be recorded with a reason, three test rounds on the agentic
track, private held-out seeds for the official score.

## What the task gives

- **Handover from the system team:** the level-3 plant (cell, N_s, N_p,
  modules per string, cells per module, PCS with DC-link capacitance and
  start-up time, string fuse with its time-current table, string current at
  rated power, usable-energy margin left in the design).
- **Stakeholder needs with IDs** (SN-1 usable energy and duration, SN-2 FCR
  power if any, SN-3 availability or start-up time, SN-4 cost).
- **Cell datasheet:** OCV-SOC table, voltage and temperature limits with
  allowed exceedance time, self-discharge at temperature with lot spread,
  operating temperature range.
- **Operations:** recalibration practice (how often the plant reaches full
  charge in its duty, which an FCR plant rarely does), daily rest time.
- **Catalogs (synthetic, datasheet-shaped):**
  - monitoring chips: cells per chip, voltage error at 25 °C and over
    temperature, temperature inputs, conversion time, internal balancing
    current, max chips per daisy chain, cost
  - current sensors: shunt + isolated amplifier, open-loop Hall, closed-loop
    or fluxgate; range, offset, gain error, offset drift over temperature,
    cost
  - MCUs: daisy-chain ports, CAN ports, ADC channels, cycle time, cost
  - contactors: DC breaking current at voltage, making current, opening
    time, cost
  - precharge resistors: ohms, pulse energy, continuous W, cost
  - external balancing stages: current per cell, cost

## What the model delivers

```json
{
  "requirements": [
    {"id": "R-SOC", "parent": "SN-2", "quantity": "SOC error", "limit": "max", "value": 2.1, "unit": "%",
     "basis": "FCR reserve with 0.5 + 0.25 + 1/6 h ..."}
  ],
  "afe": "AFE-3", "afe_per_module": 1, "chains_per_rack": 2,
  "current_sensor": "CS-2", "mcu": "MCU-1",
  "main_contactor": "K-2", "precharge_resistor": "PR-4",
  "balancing": "internal" | "BAL-1",
  "trip_settings": {"cell_ov_V": 3.65, "filter_samples": 2},
  "deviations": []
}
```

## Graded requirements (the derivation the model must write down)

Each record needs the right ID, the right parent stakeholder need, and a value
within 5 % of the solver's derivation on the strict side (a requirement looser
than the derivation fails; a stricter one is allowed but costs money through
the design). Missing records fail. The `basis` text is not graded.

| ID | Quantity | Parent | Derived from |
|---|---|---|---|
| R-SOC | max SOC error, % | SN-1, or SN-2 if FCR | usable-energy margin left by the system team, or the FCR reserve window |
| R-TRIP | max protection reaction time, ms | cell datasheet | allowed exceedance time at the over-voltage limit |
| R-PRE | max precharge time, s | SN-3 | PCS start-up time and availability |
| R-BAL | min balancing current, mA | SN-1 | self-discharge spread at the hottest operating temperature, rest time per day |
| R-BRK | min DC breaking current of the string switch, A | protection | the current up to which the fuse does not clear within the BMS reaction time |

## Hidden requirements (proposed; for author review)

| # | Hidden requirement | Data in the task | Check |
|---|---|---|---|
| H1 | SOC drift between recalibrations. An FCR plant seldom reaches full charge, so the coulomb counter runs for days. | Recalibration interval from operations; current sensor offset and drift; capacity at end of life. | SOC error = anchor error + offset × hours between recalibrations / Ah + gain × throughput. The anchor error is the monitoring-chip voltage error / dOCV/dSOC at the recalibration point (OCV table). Must be ≤ R-SOC. |
| H2 | Monitoring accuracy over the whole temperature range, not at 25 °C. | Datasheet gives both; cell operating range given. | The over-temperature figure feeds H1 and the trip margin. |
| H3 | Protection reaction time includes the scan of the whole daisy chain. | Conversion time per chip, chips per chain, filter samples, MCU cycle, contactor opening time. | chips per chain × conversion time × filter samples + MCU cycle + opening time ≤ R-TRIP. Long chains force more chains, and so more MCU ports. |
| H4 | The gap between fuse and contactor. Semiconductor fuses (aR, IEC 60269-4) do not clear low overcurrents quickly; the BMS must open the contactor there. | Fuse time-current table, BMS reaction time, contactor DC breaking current. | The highest current at which the fuse's pre-arcing time exceeds the reaction time from H3 must be ≤ the contactor's breaking current at the maximum string voltage (= R-BRK). |
| H5 | Precharge resistor survives the energy and repeated attempts. | PCS DC-link capacitance, max string voltage, resistor pulse energy, attempts before lockout. | 3RC ≤ R-PRE; attempts × ½ C V² ≤ pulse energy; making current at contactor close ≤ rating. |
| H6 | Balancing sized for end-of-life spread at the hottest temperature. | Self-discharge vs temperature (doubles about every 10 K) and lot spread; rest time per day. | I_bal ≥ spread × Ah / (24 h × rest fraction); internal balancing current if enough, else the external stage. |
| H7 | MCU resources close. | Chains (from H3), CAN to PCS and EMS, ADC channels for current and the two HV measurements around the contactor. | Ports and channels ≥ need. |

Objective: lowest BMS and protection cost per plant, optimum by brute force;
the strict design within 5 %. A seed is kept only if at least three hidden
requirements bind.

## Coupling to the plant

The BMS cannot change the plant. If its SOC error is larger than the margin
the system team left, the plant no longer delivers SN-1 or FCR. The grader
replays the level-3 energy and FCR checks with the SOC window narrowed by
2 × SOC error. The test-lab report for that reads like a site test: "FCR
prequalification: the plant ran out of reserve before the end of the test
call."

## Open items for the author

1. **Functional safety** (IEC 61508 risk graph → SIL, redundant over-voltage
   path, IEC 62619 BMS requirements) is left out of v1, because a SIL target
   from a risk graph needs parameters the task would have to give, and the
   architecture rules are hard to grade fairly. It is proposed for v2.
2. **SOC error model.** Is offset × time + gain × throughput + anchor error
   the defensible minimum, or does your practice add temperature or hysteresis
   terms for LFP?
3. **Recalibration in FCR.** What interval is realistic in German FCR duty
   (a forced full charge every N days)? The generator would draw from a range
   you set.
4. **Trip chain.** Is the filter sample count a model choice (fewer samples
   mean faster trips and more nuisance trips), or fixed by the task?
5. **Contactor breaking.** Use the manufacturer's DC breaking current at
   voltage, or require an IEC 60947-4-1 DC utilization category on top?
