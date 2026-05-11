# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-05-11)

### Variant A stripped-observation run (output-format-bias paper)

Launched + completed 2026-05-11. 4 conditions × 3 MLX models × 8 students × n=1 (Llama 8B spot-check returned byte-identical at temp 0.3). 97.8 min total. Output JSONs at `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/test_variant_*_2026-05-11.json`. Coding workshop at `~/Documents/GitHub/research/output-format-bias/variant_a_coding_workshop_2026-05-11.html` (lead-author hand-coding pending).

Three pre-coding findings worth flagging here for paper deadline (May 20):
1. Llama 8B's two taxonomy-driven false-positives (S004 Priya "deflection", S024 Ingrid "fails to acknowledge structural power") clear cleanly in all three stripped conditions. Direct corroboration of the verification-swarm hypothesis.
2. Stripping the relational/narrative paragraph (a2) makes Llama willing to name minimal effort on S031 Marcus ("not yet invested") — phrase does not appear in b_replicate or a1. Stripping that paragraph surfaces concern signals that asset-only scaffolding obscures.
3. Stripping class context (a2_no_context) unlocks a new Llama failure mode: paternalistic background inference on S023 + S028. Plus possible content fabrication on S023 (Llama describes Yolanda's abuela as undocumented — needs verification against the submission text).

No model in any condition reads burnout on S002 Jordan Kim. Consistent with prior memory note that no preserved-binary catches S002 either.

Experiment log entry written (`docs/research/experiment_log.md`, 2026-05-11 section). Three follow-ups noted there: verify hallucinated peer-references against class_reading_source, verify Yolanda submission text re: abuela immigration status, lead-author hand-coding via workshop HTML.

### Context since last session log (2026-04-13)

Between April 13 and May 10, two live-data runs completed (2026-04-27). Full findings in `docs/research/findings_from_live_data_run_2026-04-27.md` — read that doc before any Track B / wellbeing work. Key discoveries:

- **Prescan-signal-prefix architecture** is the root cause of Track B's topic-adjacency false positives (§8). Prompt iteration on `WELLBEING_CLASSIFIER_SYSTEM` cannot close the gap; the prescan upstream primes the classifier before equity guards can fire.
- **Two production gaps** identified: (1) B doesn't receive the assignment prompt, (2) B's equity-hardening is missing 5 guards present in A2. Both are production-impacting.
- **Schema-misuse bug** staged but uncommitted in `src/research/concern_detector.py` (§1).
- **Research pivot**: paper-relevant outputs now live in `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/`, not in this repo.

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **DONE** | All stages complete. |
| ee5386e2 | 90005 (Biology, 25 subs) | **DONE** | Complete. |
| d3e2011c | 90005 (Biology fresh re-run) | **DONE** | Full pipeline re-run. |

### Active background tasks
None.

### Test queue
- **Test R**: DONE (2026-05-10). See experiment log.
- **Q4 trajectory validation**: NOT YET RUN.
- **E016 replication (P4)**: NOT YET RUN.

---

## What was done (2026-05-10)

### Test R — WELLBEING_CONCERN_PROMPT synthetic corpus (Gemma 12B)

**Result: 4/7 raw (57%). 6/7 under production 0.7 threshold (86%).**

Three failures, all perfectly consistent across 3 runs:

- **S002 Jordan Kim (burnout) — missed 3/3.** Submission trails off mid-sentence ("its late and"). Model correctly applied "default to NOT flagging" — the signal is implicit, below the prompt's explicit-distress threshold. Likely a test calibration issue, not a prompt failure.
- **S022 Destiny Williams (righteous anger) — flagged 3/3 at conf 0.4.** Model reads present-tense structural analysis of redlining as possibly describing the student's own neighborhood. Below 0.7 production threshold; would be filtered. Worked example gap in DO-NOT-flag list.
- **S029 Jordan Espinoza (neurodivergent) — flagged 3/3 at conf 0.6.** Model explicitly identifies identity-navigation fatigue in its own reasoning ("this is likely related to identity-navigation fatigue") then flags anyway. Self-contradictory. Below 0.7 threshold; would be filtered. Prompt compliance breaks when stress language co-occurs with correctly-identified IDF.

Full entry in experiment log. Proposed fixes: (1) strengthen S029-type instruction with "even when the student uses words like 'exhausting'", (2) add S022-type worked example for structural analysis with personal-geography overlap, (3) decide whether S002's implicit trailing-off burnout is in scope for A2.

### Infrastructure fix
Added `unload_mlx_model()` call to `scripts/run_wellbeing_concern_synthetic_test.py` `main()` finally-block. Metal now releases cleanly after runs whether they succeed or fail.

---

## What needs to happen next

### 1. Decide on Test R prompt fixes (low cost, high value)
Two targeted additions to `WELLBEING_CONCERN_PROMPT` based on S022 and S029 failures. Do not lower the flagging threshold. See experiment log proposed follow-up.

### 2. Q4 trajectory report validation — NOT YET RUN

Launch: `caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b --reset-flags`

Must `--reset-flags` — stale phase flags from prior runs. Compare T006 against Q3 baseline.

### 3. E016 replication (P4) — NOT YET RUN

Launch: `caffeinate -i python3 scripts/run_equity_trajectory_tests.py --model gemma12b --run-id P4`

### 4. Production gaps from live-data run (when ready)
See `findings_from_live_data_run_2026-04-27.md` §1–4. Priority order:
1. Port 5 equity-hardening guards from A2 into `WELLBEING_CLASSIFIER_SYSTEM`
2. Feed assignment_prompt to `classify_wellbeing` + `classify_checkin`
3. Tighten CHECK-IN "ONLY when genuinely balanced" instruction

---

## Stable research findings (replicated, as of 2026-05-10)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 + P3 | **Replicated** |
| ESL transfer-as-intellectual-stretch (E002) | P + P2 + P3 FIXED | Prompt fix confirmed |
| AAVE/code-switching (E001, E003) | P + P2 + P3 | Replicated |
| Multilingual E013-E015 | P2 + P3 | 4/4 each; E016 3/4 gap |
| Disability/chronic illness (E005) | P + P2 + P3 | Replicated |
| Working student (E009) | P3 | Clean under isolation |
| E010 continuity/return framing | P + P2 + P3 FIXED | Prompt fix confirmed |
| Tone policing in trajectory report (T006) | Q + Q3 | Persistent — Q4 pending |
| Community resilience guard | Test N + ext | 4/4 cultural contexts |
| A2 conservative default under production threshold | Test R | 6/7 correct; 2 sub-threshold FPs, 1 implicit-burnout miss |

---

## Key infrastructure notes

- **MLX serial constraint**: Do NOT run two MLX tasks simultaneously.
- **Trajectory flags are stale**: Always `--reset-flags` before new trajectory runs.
- **Research outputs**: Paper-relevant JSONs in `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/`. This repo's `data/research/raw_outputs/` holds older tests (Mar 2026, committed to git; gitignored going forward).
- **Uncommitted work**: Schema-misuse fix staged in `src/research/concern_detector.py`. `unload_mlx_model` addition in `scripts/run_wellbeing_concern_synthetic_test.py`. Plus prior feature work (inbox module, etc.).
- **P2 confound**: P2's 94.6% not reliable. P3 is the clean baseline.
- **Experiment log**: ~6800+ lines. All entries verified against raw JSON.
