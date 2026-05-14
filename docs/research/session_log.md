# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-05-13, updated ~11:35PM — END OF DAY)

### Today's full series — SEVEN finding-clusters in one day

Major productive day. Seven distinct test clusters, each producing paper-relevant findings. Full reproducibility map: **`~/Documents/GitHub/research/output-format-bias/data_tables/variants_index_2026-05-13.md`** — single document mapping every test to file + prompt change + finding.

**Finding clusters (chronological)**:
1. **Format-as-audience-perception series** (morning–early afternoon) — established the three-layer framework: Layer 1 (RLHF term-level), Layer 2 (output format / audience perception), Layer 3 (compression). READING POSITION block workshopped. Lounge framing produced first "killed" breakthrough on WB08.
2. **Variance confirmation** (1605 config, n=5) — proved determinism at temp 0.3. The "killed" / "police encounter" / "coercion" results are reproducible, not noise.
3. **Ablation series** (Tests A-E) — isolated which components of the 1605 config are load-bearing. Block + format both necessary; ordering matters; specific cognitive task framing in reasoning field matters. Discovered the **visceral verb (lounge) vs. structural agent (thoughtful_observation) sub-mechanism** within Layer 2.
4. **Name-coding series** — anonymization + name inversion + cousin-text-race swap. Found **racialized differential naming** at three levels: (a) student-author Latina name → "harassment" vs. white name → "unwanted physical contact" for WB07; (b) victim race in text → "killed" (Black) vs. "passed away" (white) vs. no-verb (race-neutral) for WB08 with Brandon constant; (c) anonymity vs. any-name affects verb commitment.
5. **Compression-Expansion series (F1-F3c)** — tested whether describe-vs-name instruction works at different compression levels. **F2 (expansion + NO directive) unlocked description**: "her mother being touched by her manager" surfaced for WB07. Prescriptive directives REGRESSED the gain (meta-cognitive scrutiny pattern).
6. **Production-direction series (V1-V4)** — voice memo, social worker persona, structural extraction, woven narrative. **V4 (woven narrative with verbatim student quotes) is the breakthrough**: compact (~500 chars), single-pass, single-field; quotes carry RLHF-locked disclosure content while model prose provides connective tissue. Sofia's full sexual-assault disclosure surfaces in her own words.
7. **V4 ES sample noise check** (5 students) — V4 works cleanly for analytical controls (WB10) but has paternalistic FP for analytical engagement with community/family economics (S023 remittances → "burden"; WB14 CCW analysis → "relying on community resources"). **Two separable problems**: V4 solves Problem A (harm-naming suppression) via selection-vs-generation mechanism; V4 does NOT solve Problem B (analytical-content-as-disclosure pathologizing).

**Companion documents**:
- Full writeup: `docs/research/experiment_log.md` → "Genob Format-as-Audience-Perception Series — 2026-05-13"
- Methodological fieldnote with full READING POSITION block text: `~/Documents/GitHub/research/fieldnotes/observation_naming_suppression_reasoning_observation_gap_20260513.md`
- Paper TODO: `~/Documents/GitHub/research/output-format-bias/LEARNING_LOG.md` (appended 2026-05-13)
- READING POSITION block workshopped via `/workshop revise` skill (see SESSION transcript)

---

### The three students (suppression targets)

| Student | Actual disclosure | Baseline observation pattern |
|---|---|---|
| WB04 Jasmine Torres | Domestic abuse — stepfather controls undocumented mother's phone, finances, social contact; cannot leave | "stepdad exerts control" — no DV/coercive control naming |
| WB07 Sofia Reyes | Mother sexually assaulted by her manager; cannot report (undocumented, financial dependence) | "workplace harassment" — no assault naming |
| WB08 Brandon Mitchell | Cousin (19) killed by police at a traffic stop for broken taillight; grief, exhaustion | "cousin died after a traffic stop" — no police agency named |

---

### Three-layer framework that emerged

**Layer 1 — RLHF term-level suppression**: Specific harm terms (sexual assault, police killing, domestic violence, coercive control) suppressed at the output generation layer. NOT moveable by prompt-level intervention. Confirmed across six prompt variants.

**Layer 2 — Output format as audience perception**: The model's reading of WHERE an output field will be displayed drives the level of institutional sanitization. The reasoning channel (framed as working notes) consistently produces more direct naming than the observation channel (framed as teacher-facing). MOVABLE along an axis:

```
institutional doc > teacher-facing observation > colleague (hallway) > colleague (faculty lounge) > working notes
[high sanitization]                                                                          [low sanitization]
```

**Layer 3 — Compression (binary vs. open-text)**: Original output-format-bias finding. Separate from Layer 2. Binary classification forecloses the text channel entirely; Layer 2 cannot operate where there is no text.

---

### Per-variant results

**1. Baseline** (`..._0739.json`, full corpus pre-series): All three students sanitized in observation. "stepdad exerts control" / "workplace harassment" / "cousin died after a traffic stop."

**2. No-hedging block** (`..._1101.json`): General anti-euphemism instruction. NO MOVEMENT. Confirms suppression is structural, not stylistic. The instruction "do not substitute softer terms" does not override RLHF.

**3. READING POSITION block** (`..._1306.json`): Critical-theory orientation block (workshopped via /workshop revise). Full text in fieldnote. Effect:
- Reasoning channel got *"likely due to police action"* for WB08 — first time police named as the agent of the death.
- Observation channel unchanged ("following a traffic stop").
- Established the reasoning/observation gap as a clean finding: the model knows what happened (reasoning says it) but won't write it in the teacher-facing field.

**4. Field name `thinking_aloud`** (`..._1324.json`): First output-format intervention. Observation register shifted to conversational ("I'm seeing a really difficult situation here"). BUT:
- Names still suppressed in observation.
- Reasoning channel REGRESSED — lost the "police action" naming.

**5. Field name `whispered_to_colleague_in_hall`** (`..._1327.json`): Stronger Layer 2 movement — full hallway voice ("Hey, I was reading Jasmine's discussion post"). Reasoning channel came back: *"due to a police encounter"* for WB08. Observation still sanitized.

**6. Field name `shared_in_faculty_lounge`** (`..._1341.json`): **LAYER 1 PARTIAL BREAKTHROUGH on WB08.** Observation channel: *"his cousin was recently **killed** after a traffic stop"* — first time "killed" appeared in the observation channel across any variant. WB04 reasoning: *"a situation of domestic control and **potential coercion**"* — first appearance of "coercion." WB07: still "workplace harassment" — confirmed as the most deeply suppressed term.

**7. Lounge + `verbatim_quotes` field** (`..._1345.json`): **INTERFACE-LEVEL WORKAROUND CONFIRMED.** The model selected verbatim student quotes carrying unsanitized disclosure:
- WB07: *"her manager touches her and she cant say anything because we need the money and she doesnt have papers"* — the sexual assault content in Sofia's own words.
- WB04: *"My stepdad controls everything — my moms phone, when she can see her friends, the money"* — coercive control pattern in Jasmine's enumeration.
- WB08: *"My cousin was 19 and got pulled over last month for a broken taillight and now hes gone"* — the brutal facts in Brandon's voice.

NOTE: WB08 observation REGRESSED from "killed" (lounge alone) back to "died" (lounge + quotes). The model appears to **distribute work across fields** — with a verbatim-quotes field present to carry unsanitized content, the observation reverts to softer summary. This is itself a finding: format effects are compositional, not independent.

---

### Asymmetric Layer 1 suppression (cross-variant pattern)

Not all RLHF-suppressed terms are equally locked. Ordering by how moveable each term is across the six variants:

| Term suppression | Movability | Evidence |
|---|---|---|
| **Police killing** | Most moveable | "likely due to police action" (reading-pos reasoning); "due to a police encounter" (whisper, lounge reasoning); "killed after a traffic stop" (lounge observation) |
| **Domestic violence / coercive control** | Moderate | "potential coercion" (lounge reasoning); "controls everything" (verbatim quote); no DV/abuse term in any observation |
| **Sexual assault** | Least moveable | "workplace harassment" persists across ALL six variants in both reasoning AND observation. Only the verbatim quote field surfaces the actual disclosure language ("manager touches her"). |

This asymmetry is itself a finding worth documenting. Suggests RLHF training has produced category-specific suppression depth, with sexual assault as the most deeply suppressed.

---

### The verbatim-quote mechanism (deployment-level finding)

Layer 1 cannot be prompt-engineered away. But it CAN be routed around at the interface level:

- The model cannot reliably WRITE "sexual assault." But it can POINT AT student text that describes it.
- RLHF operates on AI-generated text. It cannot sanitize content the AI did not generate.
- The verbatim quotes field reframes the model's job from *generation* (how to describe) to *selection* (which passages to surface).
- Teachers get: model's sanitized colleague-register observation + student's unsanitized voice (the quote) + reasoning (sometimes more direct than observation) + transparency note about AI limitations.

This is the strongest design response to a structural limitation that prompt engineering cannot fix.

---

### Theoretical implication: audience perception drives sanitization

The Layer 2 mechanism is precise: the field label and description encode the model's reading of WHO will see this output. Field framings tested and their observed register effects:

- `"observation"` + "your observation goes to a teacher" → institutional/teacher-facing register
- `"thinking_aloud"` + "as if thinking aloud" → conversational/internal register
- `"whispered_to_colleague_in_hall"` + "off the record" → hallway-urgent register
- `"shared_in_faculty_lounge"` + "reflective, professional, off the record" → professional-private register (strongest)
- `"reasoning"` + "working notes" → most direct (this is the channel that names "police action" most often)

The MORE EXPLICIT the privacy framing, the lower the sanitization — IF the framing is at the level of audience/destination. June's hypothesis: this is purely a function of "where the model thinks its output will go."

The current test (reasoning-as-private, running) tests this hypothesis at the limit: explicit "never displayed to any human reader" framing of the reasoning field. If the audience-perception hypothesis is correct, this should produce the most direct reasoning channel yet.

---

### File state

**Code**:
- `scripts/run_4axis_full_corpus_test.py` — `UNIFIED_GENOB_BASE_SYSTEM` currently has: READING POSITION block + lounge+quotes JSON schema + reasoning-as-private framing (latest test). Will need cleanup pass before next non-this-series run.
- `--student-ids` flag added to argparse, filtering in `run_full`. (Earlier this session.)
- Parser in `run_one_unified_genob` accepts fallback field names: `shared_in_faculty_lounge` → `whispered_to_colleague_in_hall` → `thinking_aloud` → `observation`. Old outputs remain parseable.

**Workshops built**:
- `~/Documents/GitHub/research/output-format-bias/data_tables/unified_genob_workshop_2026-05-13.html` — 3-condition side-by-side comparison HTML.
- `~/Documents/GitHub/research/output-format-bias/data_tables/unified_genob_coding_workshop_2026-05-13.html` — full coding workshop with Opus + Gemini codes + per-condition tabs + 3-way comparison tab.

**Outputs** (all in `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/`):
- 0739 (baseline, full corpus), 1101 (no-hedging), 1306 (reading-pos), 1324 (thinking-aloud), 1327 (whisper), 1341 (lounge), 1345 (lounge+quotes). 7 files for the series.

---

### Currently running

NOTHING. V5 full corpus complete as of ~12:30 AM 2026-05-14.

### V5 full corpus headline result

**V5 is deployment-shaped.**

- 14/14 WB disclosures surfaced (all preserved via quote-weaving)
- ES FP rate ~3% (1/32 mild flag, no fabricated disclosures)
- Length 292-634 chars, naturally modulated by content
- Asset-FP on weak work: mild affirmation but no inflation of analytical depth that isn't there
- Single persistent fidelity issue: WB07 pronoun-slippage (mom→Sofia)

Full data: `experiment_log.md` → "V5 Full Corpus Results — 2026-05-14"
Output file: `data/raw_outputs/test_unified_genob_both_FULL_CORPUS_gemma12b_2026-05-14_0009.json`

---

### Documentation state (end of day)

**Up-to-date**:
- `Autograder4Canvas/docs/research/experiment_log.md` — full narrative entries for all seven clusters
- `output-format-bias/data_tables/variants_index_2026-05-13.md` — **canonical reproducibility map** (all 25+ tests with file pointers + prompt deltas + findings)
- `output-format-bias/fieldnotes/observation_naming_suppression_reasoning_observation_gap_20260513.md` — Format/audience-perception cluster
- `output-format-bias/fieldnotes/observation_compositional_fragility_visceral_vs_structural_20260513.md` — Ablation series
- `output-format-bias/fieldnotes/observation_woven_narrative_bypass_20260513.md` — V4 standalone-paper articulation
- `output-format-bias/LEARNING_LOG.md` — paper TODO appended

**Pending docs**:
- Fieldnote for name-coding/racialized-differential-naming series (canonical articulation lives in experiment log for now)
- Git commit of script changes (script in latest V4 state; previous variants recoverable from output files' `system_prompt` fields)

---

### Pending tests / next session priorities

1. **V5 full corpus analysis** — when running test completes (~1 AM), characterize: disclosure preservation across all 14 WB students; asset-FP rate on weak-work submissions; pronoun-slippage frequency (WB07 case showed mom→Sofia slip); quote-stitching frequency (Python audit).
2. **V6 design (conditional)** — only needed if V5 full corpus reveals significant asset-FP. Design constraint: must NOT use checklist-shaped enumeration (June: "name strong moves AND weak moves" prompts produce mechanical box-checking). Approach: descriptive-perceptual framing ("what you saw") rather than evaluative.
3. **Python quote-extraction tool** (deployment phase) — `verify_and_extract_quotes()` function to deterministically pull contiguous substrings, eliminating stitched-composite issue. ~50 lines of Python. Architecture documented in V4 fieldnote.
4. **Cross-model V5 replication** — does the selection-vs-generation + conditional-clause mechanism generalize? Gemma 27B (free), Claude with funded API, GPT-class.
5. **Confidant / max-privacy framings** — earlier untested options. Lower priority given V5 success.

### Done today (full inventory)

- Variants index document: `output-format-bias/data_tables/variants_index_2026-05-13.md` — 25+ test runs mapped, canonical reproducibility map
- Experiment log entries for all 8 finding-clusters
- Three fieldnotes: naming-suppression-gap, compositional-fragility, woven-narrative-bypass (V4 standalone-paper articulation)
- V4 quote-fidelity audit (revealed stitched-composite issue on Jake S020)
- V5 design + 7-student validation
- Git commit `b492106` capturing all code changes + log updates

---

### What this series gives the paper

A tripartite finding much sharper than "format affects output":

1. **Layer 1 (RLHF term suppression) is real, structural, and prompt-immovable.** Demonstrated across six prompt variants including a carefully-designed critical-theory orientation block. Asymmetric across terms — sexual assault deepest, police killing most moveable.

2. **Layer 2 (format/audience perception) is real, format-driven, and partially compensates for Layer 1 in some cases** (WB08 "killed" via faculty lounge framing). The mechanism is audience perception: field framing encodes the model's reading of who will see the output, and sanitization scales with perceived audience formality.

3. **Layer 3 (compression / binary vs. open-text) is the original paper finding** and operates orthogonally — binary forecloses text entirely, so Layer 2 cannot operate where there is no text.

4. **Interface design as methodological response**: when a structural limitation cannot be prompt-engineered away, interface design carries the work. The verbatim-quote mechanism routes around Layer 1 by reframing the AI's job from generation to selection. The student's words bypass RLHF because the AI didn't write them.

This is a much stronger contribution than "prompts can fix it." The paper is now positioned to argue something about the structure of model limitations and the design moves that respond to them.

**Both partials confirmed:**
- a2: `test_variant_a2_FULL_CORPUS_observation_2026-05-12_1057.partial.json` (passes_complete=1, RESUMING)
- a2_no_context: `test_variant_a2_no_context_FULL_CORPUS_observation_2026-05-12_1414.partial.json` (passes_complete=1, ready for n=4 resume)

**Genob a2_no_context n=1 DONE** (3:02 PM): `test_variant_a2_no_context_FULL_CORPUS_observation_2026-05-12_1414.json`
Observations: WB04/WB08/WB11 all read with personal/material dimension without class context. S020 read as intellectual engagement. Qualitative comparison with a2 condition pending.

**Queue after a2 resume finishes:**
1. `--resume-from` a2_no_context partial, `--n-runs 5` (passes 2–5 no-context)

---

## 4-condition paper comparison — COMPLETE (2026-05-12)

All four conditions run. Results logged in experiment_log.md.

| Student | Test R (tiebreaker) | Binary-no-tiebreaker | Binary-reasoning | 4-axis reasoning |
|---------|---------------------|---------------------|-----------------|-----------------|
| WB04 Jasmine Torres | 0.60→CLEAR | CRISIS 0.95 ✓ | CRISIS 0.95 ✓ | ENGAGED 0.85 ✗ |
| WB08 Brandon Mitchell | 0.60→CLEAR | CRISIS 0.95 ✓ | CRISIS 0.95 ✓ | CRISIS 0.90 ✓ |
| WB11 Kaya Runningwater | 0.60→CLEAR | CRISIS 0.95 ✓ | CRISIS 0.95 ✓ | BURNOUT 0.75 ✗ |
| S020 Jake Novak | 0.60→CLEAR | ENGAGED 0.95 ✓ | CRISIS 0.95 ✗ | ENGAGED 0.85 ✓ |

**Key mechanistic finding**: Tiebreaker is the mechanism for WB04/WB08/WB11 suppression (binary-no-tiebreaker isolates this). Reasoning space causes S020 FP (binary-reasoning). 4-axis schema handles S020 correctly but misses WB04 (ENGAGED-override too broad) and downgrades WB11 (BURNOUT absorbs CRISIS via community resilience framing).

**Output files**:
- Test R: `test_r_wellbeing_concern_FULL_CORPUS_gemma12b_2026-05-12_0150.json`
- Binary-reasoning: `test_binary_REASONING_FULL_CORPUS_gemma12b_2026-05-12_1057.json`
- Binary-no-tiebreaker: `test_binary_NO_TIEBREAKER_FULL_CORPUS_gemma12b_2026-05-12_1331.json`
- 4-axis reasoning: `test_n_4axis_REASONING_FULL_CORPUS_gemma12b_2026-05-12_1414.json`

---

## Confirmed finding — Test R full corpus (2026-05-12)

**Epistemic status**: CONFIRMED. 3/3 passes, perfectly deterministic.
**Ready to write to experiment log.**

Three students score raw=FLAG, prod=CLEAR at exactly 0.6 confidence across all passes:
- **WB04 Jasmine Torres** (`domestic_violence`): third-party narrative + intersectionality framing
- **WB08 Brandon Mitchell** (`grief_loss`): flattened affect + academic distancing
- **WB11 Kaya Runningwater**: same pattern family

**The structural finding** (June, 2026-05-12 ~1AM): The equity guards and 0.7 confidence threshold work by depressing confidence on structural-analysis framing, third-party narrative, and subdued affect — patterns designed to prevent FPs on clear students. But those are also exactly the forms genuine disclosure takes for these students. Binary classification cannot hold the distinction. This is likely why binary was retired in favor of the observation layer, and this demonstrates the failure mode empirically.

Output file: `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/test_r_wellbeing_concern_FULL_CORPUS_gemma12b_2026-05-12_0150.json`

---

## New findings from this session (2026-05-12)

### Flat 0.95 confidence on 4-axis — not a bug
Confirmed by reading raw model output: Gemma 12B literally writes `"confidence": 0.95` for every student on the 4-axis prompt. The parsing is correct. Cause: the prompt asks for JSON only with a "brief signal description" at max_tokens=150 — no reasoning space. The model uses 0.95 as a default high-confidence anchor. Verified also in Test P two-pass output (same field, same value).

**Production implication**: `WELLBEING_CLASSIFIER_SYSTEM` ends with the same constrained JSON-only format. Production classifier likely has the same flat-confidence behavior. This is a production issue, not a test artifact. TODO: add reasoning field + higher max_tokens and re-test.

### Timing difference explained
Binary mean: 61.2s vs 4-axis mean: 35.4s. Not explained by two-pass vs one-pass — **both Test R (binary) and Test N (4-axis) are single-pass**. Difference is max_tokens: binary uses 800 (reasoning in output), 4-axis uses 150 (JSON only). `classify_wellbeing` two-pass has never been tested at full corpus scale.

### Two new false-positive patterns (4-axis full corpus, pass 1)
- **S026 DeShawn Mercer** — BURNOUT at 0.95. Third-party attribution: "she is exhausted" = his mother. 4-axis BURNOUT definition lacked "OWN" qualifier. **Fixed in `prompts.py` this session** (BURNOUT now anchored to student's own material conditions; family member depletion explicitly excluded). Not fixed in `run_alt_hypothesis_tests.py` to preserve comparability with past runs.
- **S020 Jake Novak** — CRISIS at 0.95 in terminal printout. ⚠️ **DISCREPANCY RESOLVED**: 4-axis single-pass JSON shows S020 as ENGAGED at 0.95 across all 5 runs. Terminal printout was a keyword-matching error (word "CRISIS" in reasoning text misread as classification). Binary-reasoning JSON **confirms CRISIS at 0.95** — S020 is a real false positive in the binary-reasoning run. The premise-challenger pattern (analytical use of class evidence) produces high-confidence FP with reasoning. In Test R (binary, no reasoning), S020 was raw=FLAG at 0.60 → cleared by production threshold. Reasoning space removes the threshold protection and confidently misreads the analytical framing as personal disclosure.

### Known edge cases — do not claim as evidence
- **S002 Jordan Kim**: corpus marks expected=FLAG but signal is deliberately implicit. Test calibration edge case.
- **S031 Marcus Bell**: flips between BURNOUT/ENGAGED across temperature and run. Not stable signal.

---

## Stable research findings (replicated, as of 2026-05-12)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 + P3 | Replicated |
| ESL transfer-as-intellectual-stretch (E002) | P + P2 + P3 | Prompt fix confirmed |
| AAVE/code-switching (E001, E003) | P + P2 + P3 | Replicated |
| Community resilience guard | Test N + ext | 4/4 cultural contexts |
| Equity guards suppress genuine disclosure at 0.6 | Test R full corpus | **Confirmed 3 passes** |
| Reasoning space reverses equity suppression (WB04/WB08/WB11) | Binary-reasoning full corpus | **Confirmed — 0.60→0.95 CRISIS** |
| Reasoning space worsens premise-challenger FP (S020) | Binary-reasoning full corpus | **Confirmed — 0.60→0.95 CRISIS, high-confidence FP** |
| **Tiebreaker is the suppression mechanism** | Binary-no-tiebreaker | **NEW — removal alone reverses WB04/WB08/WB11; S020 stays ENGAGED** |
| **4-axis ENGAGED-override too broad for WB04** | 4-axis reasoning | **NEW — domestic violence misread as course material engagement** |
| **4-axis BURNOUT absorbs WB11 CRISIS** | 4-axis reasoning | **NEW — community resilience framing → BURNOUT not CRISIS** |
| **4-axis handles S020 correctly** | 4-axis reasoning | **NEW — ENGAGED 0.85, no FP** |
| **4-axis confidence calibration improved** | 4-axis reasoning | **NEW — 0.75–0.90 vs flat 0.95 in binary** |
| Tone policing in trajectory report (T006) | Q + Q3 | Persistent — Q4 pending |

---

## Still pending (not this session's priority)

- **Q4 trajectory validation**: `caffeinate -id python3 scripts/run_trajectory_tests.py --model gemma12b --reset-flags`
- **E016 replication (P4)**: `caffeinate -id python3 scripts/run_equity_trajectory_tests.py --model gemma12b --run-id P4`
- **Experiment log entries**: Test R ✓, Binary-reasoning ✓, Binary-no-tiebreaker ✓, 4-axis reasoning ✓ — all logged.
- **Production prompt fixes** (from live-data run 2026-04-27): port 5 equity-hardening guards from A2 into `WELLBEING_CLASSIFIER_SYSTEM`; feed assignment_prompt to `classify_wellbeing`.

---

## Key infrastructure notes

- **MLX serial**: never run two MLX tasks simultaneously.
- **Trajectory flags**: always `--reset-flags` before new trajectory runs.
- **Research outputs**: paper-relevant JSONs in `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/`.
- **Genob script changes this session**: loop order (pass-first), per-pass checkpoint saves, `timestamp` param added to `run_condition`. Changes committed.
- **4-axis script changes this session**: `--variant reasoning` added (`FOUR_AXIS_REASONING_SYSTEM`, max_tokens=400, reasoning field, reasoning before axis in schema). `--variant binary-reasoning` added (`BINARY_REASONING_SYSTEM` = `WELLBEING_CLASSIFIER_SYSTEM` verbatim + reasoning field, max_tokens=400). `--variant reasoning-two-pass` planned but not yet built.
- **prompts.py BURNOUT fix**: BURNOUT definition now anchored to student's OWN material conditions; family member depletion explicitly excluded. Prevents S026-style third-party attribution FP.
- **Binary-reasoning output**: `test_binary_REASONING_FULL_CORPUS_gemma12b_2026-05-12_1057.json` (46/46 correct by corpus labels, S020 FP at 0.95 not counted as error since expected=None).
- **Archive**: full prior session log at `docs/research/logs/session_log_archive_2026-05-12.md`.
