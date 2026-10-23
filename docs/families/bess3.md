# bess3: storage system, level 3 (DRAFT for answer-key review)

Level 2 (`bess`) with the scaffolding removed. Same plant, same chain from
cells to the 20 kV connection, but:

- **Nothing is named.** No standard, method or rule appears in the prompt.
  The brief reads like a project brief: requirements, site, duty, and
  datasheets. Datasheets keep the tables a real datasheet carries (ambient and
  grouping factors, fuse ambient factors), without saying what to do with
  them. Knowing that VDE-AR-N 4110, IEC 60269-7, IEC 61660-1, DIN VDE 0298-4,
  IEC 60364-4-43 and IEC 60076-11 apply is part of the test.
- **The first design is final** (`max_grades: 1`). Python stays available.
- **Hidden requirements.** The grader checks everything level 2 checks, plus
  the items below, which the prompt never mentions. A senior team anticipates
  them.
- **Private seeds** for the official score. The generator is public.

## Hidden requirements (for the author's review)

Each item lists what the senior team must know, what data the task provides,
and the deterministic check. Status: **?** = awaiting the author's decision.

| # | Hidden requirement | Data in the task | Check | Status |
|---|---|---|---|---|
| H1 | **Size for capacity at end of service life.** The energy requirement holds for the whole service life; the brief does not state an end-of-life state of health. | Duty (equivalent full cycles per day), service life, cell datasheet table of capacity retention and resistance growth against equivalent full cycles. | State of health = retention at (cycles/day × 365 × years), interpolated; energy, voltage window and heat use it. Replaces level 2's given 80%. | ? |
| H2 | **Requirements at the connection point are net of auxiliaries.** Cooling compressors, fans, battery management, fire system and lighting draw from the plant. | Cooling unit datasheet: electrical input at rated thermal output (or EER). Per-container auxiliary load. | P_net = PCS output − auxiliaries ≥ P_req (1 + m); E_net = E_poi − P_aux × duration ≥ E_req (1 + m). | ? |
| H3 | **Reactive power over the voltage band.** The grid code requires the reactive capability across the connection-point voltage range, and a current-limited inverter delivers less apparent power at low voltage. | PCS datasheet: rated AC current and apparent power; connection letter: voltage band. | S_pcs(site T) × U_min/U_n ≥ S_needed. Exact band per VDE-AR-N 4110 to confirm. | ? |
| H4 | **MV switchgear rated for the grid's fault level.** | Connection letter: network short-circuit power S_k″ at the connection point. Ring-main-unit catalog: rated current, short-time withstand current, making current, price. | I_k″ = S_k″ / (√3 U_n) plus the PCS contribution ≤ short-time withstand; κ √2 I_k″ ≤ making; rated current ≥ connection current. New output field `mv_switchgear`. | ? |
| H5 | **Winter: cells must be warm enough to charge.** LFP cannot charge at rated rate when cold. | Cell datasheet: allowed charge C-rate against temperature. Site minimum ambient. Enclosure heat-loss coefficient. Cooling unit datasheet: heating capacity. | Heating capacity × count ≥ UA × (T_cell_min_for_rated_charge − T_site_min). | ? |
| H6 | **Frequency containment reserve prequalification** (only when the brief names FCR as the use case). | Brief: FCR power to prequalify. | Inverter power ≥ 1.25 × FCR power; energy for full activation for the required period in both directions inside the SOC window. Exact German PQ rules to confirm. | ? |

## Questions for the author

1. H1: is sizing to capacity at the end of the service life, from the
   datasheet retention table, how your projects do it, rather than a fixed
   80%?
2. H2: are connection-point requirements net of auxiliaries in your
   contracts, or are auxiliaries fed separately?
3. H3: what voltage band does VDE-AR-N 4110 require the reactive capability
   over, and is a current-limited reduction at low voltage the right model?
4. H4: anything else on the MV side a senior team would check (protection
   relay settings, transformer inrush)?
5. H5: realistic, or do your containers handle it in a way this misses?
6. H6: include FCR? If so, the current power and duration rules.
7. What else would your team check on a real project that is missing here?
