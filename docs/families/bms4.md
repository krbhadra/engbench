# bms4: battery management and protection, level 4

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
  power if any, SN-3 start-up time, SN-4 safety of cells, equipment and
  people, SN-5 cost, SN-6 the network operator's connection rules).
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

Each record needs the right ID, the right parent stakeholder need (one, or a
list when a requirement serves several; every need named must be a valid
parent), and a value
that follows from the data: a maximum may be up to 20 % stricter than the
solver's derivation and 2 % looser (rounding); a minimum up to 25 % stricter
and 2 % looser. A stricter requirement is a defensible engineering choice that
costs money through the design; a looser one is wrong. Missing records fail.
The `basis` text is not graded.

| ID | Quantity | Parent | Derived from |
|---|---|---|---|
| R-SOC | max SOC error, % | SN-1, or SN-2 if FCR | usable-energy margin left by the system team, or the FCR reserve window |
| R-TRIP | max protection reaction time, ms | cell datasheet | allowed exceedance time at the over-voltage limit |
| R-PRE | max precharge time, s | SN-3 | PCS start-up time and availability |
| R-BAL | min balancing current, mA | SN-1 | self-discharge spread at the hottest operating temperature, rest time per day |
| R-BRK | min DC breaking current of the string switch, A | SN-4 | the lowest current from which the fuse alone clears within the cell's short-time limit |
| R-RIDE | min bridging time of the rack's 24 V, s | SN-6 | the operator's fault sequence with a reclose onto the fault, against the power supply's minimum input voltage and hold-up |
| R-IMD | min system capacitance rating of the insulation monitor, uF | SN-4 and/or SN-6 | earth capacitance of every rack, PCS and DC conductor on the one IT system |

## Hidden requirements (author review: accepted 2026-10-27)

| # | Hidden requirement | Data in the task | Check |
|---|---|---|---|
| H1 | SOC drift between recalibrations. An FCR plant seldom reaches full charge, so the coulomb counter runs for days. | Recalibration interval from operations; current sensor offset and drift; capacity at end of life. | SOC error = anchor error + offset × hours between recalibrations / Ah + gain × throughput. The anchor error is the monitoring-chip voltage error / dOCV/dSOC at the recalibration point (OCV table). Must be ≤ R-SOC. |
| H2 | Monitoring accuracy over the whole temperature range, not at 25 °C. | Datasheet gives both; cell operating range given. | The over-temperature figure feeds H1 and the trip margin. |
| H3 | Protection reaction time includes the scan of the whole daisy chain. | Conversion time per chip, chips per chain, filter samples, MCU cycle, contactor opening time. | chips per chain × conversion time × filter samples + MCU cycle + opening time ≤ R-TRIP. Long chains force more chains, and so more MCU ports. |
| H4 | The gap between fuse and contactor. Semiconductor fuses (aR, IEC 60269-4) do not clear low overcurrents quickly; the BMS must open the contactor there. | Fuse time-current table, BMS reaction time, contactor DC breaking current. | The highest current at which the fuse's pre-arcing time exceeds the reaction time from H3 must be ≤ the contactor's breaking current at the maximum string voltage (= R-BRK). |
| H5 | Precharge resistor survives the energy and repeated attempts. | PCS DC-link capacitance, max string voltage, resistor pulse energy, attempts before lockout. | 3RC ≤ R-PRE; attempts × ½ C V² ≤ pulse energy; making current at contactor close ≤ rating. |
| H6 | Balancing sized for end-of-life spread at the hottest temperature. | Self-discharge vs temperature (doubles about every 10 K) and lot spread; rest time per day. | I_bal ≥ spread × Ah / (24 h × rest fraction); internal balancing current if enough, else the external stage. |
| H8 | Ride-through, cross-functional (grid code, auxiliary power, BMS hardware). The auxiliary supply follows the connection-point voltage, so the rack's 24 V (MCU, contactor coil, current sensor) must be bridged through the operator's fault sequence, including the reclose onto the fault. | Connection letter: dip depth, duration, recovery, reclose dead time; power-supply minimum input voltage and hold-up; board, coil and sensor power; hold-up modules. | Hold-up J >= rack 24 V power x R-RIDE. A precise sensor or a large contactor costs hold-up energy. |
| H9 | Insulation monitoring, cross-functional (power electronics, installation, BMS, safety). Transformerless PCS on one unearthed LV winding make the whole DC side one IT system: one active monitor, rated for its whole earth capacitance. | Topology, Y-capacitance per rack and PCS, cable capacitance and route length; monitor catalog. | Monitor at plant level (rack-level monitors interfere); rating >= R-IMD. |
| H7 | MCU resources close. | Chains (from H3), CAN to PCS and EMS, ADC channels for current and the two HV measurements around the contactor. | Ports and channels ≥ need. |

Objective: lowest BMS and protection cost per plant, optimum by brute force;
the strict design within 5 %. A seed is kept only if at least three hidden
requirements bind.

## As implemented (decisions taken while building, 2026-10-27)

- **Plant handover.** The level-3 optimum of a fresh draft plus one rack: the
  system team's allowance for measurement error. Without it the optimum has
  almost no energy slack and no BMS could close. R-SOC follows from that slack:
  (E_poi + E_aux)(W − 2e)/W − E_aux ≥ E_req.
- **SOC error** is the root sum of squares of anchor, offset and gain (the
  least strict defensible combination). The anchor uses the steeper table
  segment at the recalibration SOC, and recalibration is at the top of the
  window after a 30-minute rest, as the brief states.
- **Current sensors** include dual-channel Hall parts (a fine channel for
  coulomb counting, a coarse one for faults), because H4 needs the BMS to
  measure up to R-BRK while H1 needs a small offset.
- **H4, least strict reading.** R-BRK is the lowest current from which the fuse
  alone clears within the cell's short-time limit at every higher current. The
  BMS hands over to the fuse there, so the contactor must break R-BRK, the
  sensor must reach it, and MCU cycle plus contactor opening must be within the
  cell limit at every current from the overcurrent trip up to R-BRK.
- **H5.** The firmware checks the bus voltage a fixed time after precharge
  starts, so a shorted DC link puts V²/R × that time into the resistor. That,
  and ½ C V² for a normal precharge, must fit the resistor's pulse rating; the
  relay peak sets a minimum resistance and the time allowed a maximum.
- **Filter samples, overcurrent trip level and precharge thresholds** are fixed
  by the firmware team in the brief, not chosen by the model.
- **Contactor breaking** uses the manufacturer's DC breaking current at
  1500 V; no IEC 60947-4-1 utilization category on top.
- **FCR recalibration interval** is drawn from 3, 5, 7, 10 or 14 days; energy
  plants recalibrate daily.

## Cross-functional revision (2026-10-27)

The first version (H1-H7) let Opus 5.5 pass 16 of 17 tasks within three test
rounds: each failed test pointed at one part. The author asked for harder,
cross-functional tasks. H8 and H9 couple departments so a symptom has causes in
several of them ("the plant disconnected in the ride-through test": hold-up
energy, the reclose, coil and sensor power), and parts now trade against each
other through the 24 V budget. A third coupling (rack heat from balancing and
BMS electronics feeding back into self-discharge and auxiliary energy) was
checked and dropped: about 2 W per rack and 0.03 % of plant energy, too small
to be honest difficulty. A kept task now needs four distinct hidden
requirements binding (was three). R-BAL may trace to SN-1 or SN-4 (author,
2026-10-27).

Insulation monitoring serves several needs at once: cell and equipment
safety, the safety of people during installation and operation, and the
connection rules and VDE installation standards. The author ruled
(2026-10-28) that all of them are correct parents. SN-4 now names people and
installation explicitly, R-IMD accepts SN-4, SN-6 or both, and every record
may name several parents. Re-graded under that rule, the Opus 5.5 pilot
stays at 12/17 within three rounds; first designs go from 5/17 to 7/17.

Sources for H8: VDE FNN, TCR medium voltage (VDE-AR-N 4110) overview, 2017,
dynamic grid support for type 2 units (ride through repeated faults and
automatic reclosing; active current back within 1 s):
<https://www.vde.com/resource/blob/1708464/47dedcd3571bc7fdbc29fd3704dce88a/tcr-medium-voltage-en-data.pdf>.
The type 2 limit curve itself (VDE-AR-N 4110 Bild 14) is paywalled, so the
task gives the fault sequence in the connection letter, shaped on the public
RfG ranges for power park modules (Regulation (EU) 2016/631, Art. 14(3)).

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
2. **SOC error model.** v1 uses anchor + offset + gain; LFP hysteresis and
   temperature terms are not modelled. Defaults above were taken without the
   author's answer to the SOC, recalibration, filter and contactor questions;
   revisit when reviewing the first tasks.
