# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-05-12, updated ~2:15PM)

### Genob a2_no_context n=1 — RUNNING
`caffeinate -id python3 run_genob_full_corpus_test.py --condition a2_no_context --n-runs 1`
Started ~2:14 PM. Part of test chain launched after genob pass 1 killed.

**Genob a2 partial**: `test_variant_a2_FULL_CORPUS_observation_2026-05-12_1057.partial.json` (passes_complete=1, 46 results)
**Remaining queue after a2_no_context n=1 completes**:
1. `--resume-from` a2 partial, n=4 (runs 2–5 for a2 condition, same file)
2. a2_no_context n=4 resume (if partial written after this n=1 run)
3. 4-axis (next chained test — check what was in the original launch chain)

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
