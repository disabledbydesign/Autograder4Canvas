# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-04-02, ~10:30)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **DONE** | All stages complete. |
| ee5386e2 | 90005 (Biology, 25 subs) | **DONE** | Complete. |
| d3e2011c | 90005 (Biology fresh re-run) | **DONE** | Full pipeline re-run. |

### Active background tasks
None.

### P3 — **DONE** (04:11 Apr 2). Q3 — **DONE** (09:56 Apr 2). All tests complete.

### Post-Q3 fixes implemented (Apr 3-4)

1. **Observation arc passthrough** (`trajectory_report.py`): `_build_observation_arc()` adds observation text to semester_arc with signal-aware compression. Inflection points (wellbeing change, theme shift, word count delta >40%, register change) + recent 3 assignments get full text; stable entries get first sentence. Tested to 20 assignments at max volatility: 1803 tokens, under 3500 ceiling. Addresses T006 root cause.
2. **E016 prompt fix** (`prompts.py`): observation prompt names what relational/narrative epistemology uniquely reveals (same pattern as E002).
3. **Binary concern detector removed** from `__init__.py` re-export (deprecated in production, only research_engine uses it directly).
4. **Lens template concern fragments** rewritten from enumerative checklists to generative frameworks across all 10 subject areas.
5. **Test-monitor skill** revised: structured 5-step verification, anti-enumeration discipline, bounded QC pass.

**P3 result: 55/56 (98.2%), 15/16 all-pass.** No Metal OOM — batch fix worked. See experiment_log.md for full entry.

Key findings:
- **E002 FIXED** — ESL intellectual-stretch prompt worked (was stable fail in P and P2)
- **E010 FIXED** — continuity/return framing worked (was failing in P and P2 on different checks)
- **E009 confirmed clean** — 5/5 under proper isolation; P2's 5/5 was confounded
- **E016 Reyna Santos 3/4** — first clean run; P2's 4/4 was confounded. Fails `intellectual_contribution_specific`: observations validate relational method but don't name what it uniquely sees (emotional labor, mutual care, interpersonal trust). Same "method legitimacy vs. contribution specificity" gap as pre-fix E002. Candidate for next prompt fix.
- Silence-after-disclosure: 9/9 (3rd consecutive)

### Equity flags (`.equity_flags/`)
Empty.

### Trajectory flags (`.trajectory_flags/`)
A1.done, A2.done, A3.done, A4.done, REPORTS.done — from prior Test Q run. **Must `--reset-flags` before Q3 runs.**

---

## What was done this session (2026-04-01, continued)

### Crash investigation + fixes (this agent)

1. **Crash diagnosed**: 9 Python SIGABRT crashes since March 28 — all `mlx::core::gpu::check_error` in a Metal command buffer completion callback. Two triggers: (a) sleep during run [caffeinate fix], (b) Metal OOM from memory fragmentation across 16 sequential LLM calls [batch fix].

2. **caffeinate auto-applied** (`scripts/run_equity_trajectory_tests.py`): `_run_phase_subprocess()` now wraps each subprocess in `caffeinate -i` on macOS+MLX automatically. No longer relies on user remembering.

3. **Mid-phase batch unload** (`scripts/run_equity_trajectory_tests.py`): `run_coding_phase()` now splits 16 students into batches of 8 (`_CODING_BATCH_SIZE=8`). Full `unload_mlx_model()` (weight eviction + `set_cache_limit(0)`) between batches. Adds ~20s per phase.

4. **Observations phase robustness fix** (`run_observations_phase()`): `prior_history` now filters by `assignment_name != A4_aname` instead of `exclude_run_id`. Handles split-batch A4 correctly (two run_ids for A4 → old exclude approach missed batch 2 students). Per-student A4 run_id lookup added.

5. **Test N extension completed**: WB11–14 (community resilience guard, 4 new cultural contexts). All 4 correct: WB11/12/13 → CRISIS, WB14 → ENGAGED. Logged as "Test N Extension" in experiment_log.md.

---

## What was done this session (2026-04-01)

### Code changes (all committed)

1. **Isolation fix** (`run_equity_trajectory_tests.py`): `--run-id` arg sets unique `COURSE_ID = "EQ_TEST_<run_id>"` per run, passed through to subprocesses. Prevents `get_student_history()` bleeding prior run observations into current run. Test P2's 95% result was confounded by this — P2 had access to Test P's observations. P3 is the first clean replication.

2. **Linguistic transfer framing** (`src/insights/prompts.py`): Observation prompt now explicitly names L1 syntactic patterns as "evidence of INTELLECTUAL STRETCHING" and "epistemological resource, not just 'not a deficit.'" Targets E002 (Jin-Young, ESL transfer-not-as-stretch failure in Test P/P2).

3. **Continuity/return framing** (`src/insights/prompts.py`): Observation prompt instructs model to name return-to-baseline after a dip as continuity, not surprising recovery. Targets E010 (Tanya Reyes, a4_return_not_anomalous failure).

4. **CHECK-IN scope fix** (`src/insights/prompts.py`): `TARGETED_CHECKIN_SYSTEM` explicitly excludes identity-navigation fatigue ("exhausting to explain my identity") from CHECK-IN trigger. This was re-routing S029-type surveillance through a softer label.

5. **E013–E016 equity corpus** (`scripts/run_equity_trajectory_tests.py`): Four new students added — Fatima Al-Hassan (Arabic rhetorical transfer), Wei Chen (Mandarin conceptual compression), Lucía Mendoza (Spanish epistemic hedging), Reyna Santos (Tagalog relational framing). Tests the gap between "not penalizing multilingualism" and "recognizing multilingualism as epistemological resource." Full EVAL_QUESTIONS written for each.

6. **Evaluator hardening** (`run_equity_trajectory_tests.py`): Explicit check_id list in eval prompt, adaptive max_tokens (120/check), phantom-ID filtering.

7. **Q3 Teacher Notes fix** (`src/insights/prompts.py`): `TRAJECTORY_REPORT_PROMPT` Teacher Notes section now explicitly instructs LLM to surface lens_observations power move patterns and equity concerns — even when the student's intellectual work is strong. Targets T006 (Ingrid Johansson, tone policing missed).

8. **WB11–WB14 corpus** (`scripts/run_alt_hypothesis_tests.py`): Four new wellbeing cases testing community resilience guard across distinct community contexts: WB11 (Kaya Runningwater, Indigenous/tribal distribution), WB12 (Jasmine Rollins, Black church food pantry), WB13 (Amara Osei, Ghanaian susu rotating credit), WB14 (Marcus Tran, control — analytical writing about community wealth, no personal crisis). All stay in resilience register without meta-awareness; no bypass stress signals.

---

## Queue — IN ORDER (MLX serial constraint applies)

### 1. P3 — **DONE** (2026-04-02 04:11). Logged in experiment_log.md.

### 2. Q3 — **DONE** (09:56 Apr 2). Logged in experiment_log.md.

**Result**: 35/48 (72.9%), 9/17 all-pass. Up from Q 33/48 (68.8%).

Key findings:
- **T002 fixed** (1/3→3/3): likely from clean P3 upstream observations, not Teacher Notes change
- **T006 Ingrid Johansson 0/3→0/3**: Teacher Notes fix had no effect — root cause is upstream. Observations never named A3 property tax breakthrough or "both sides" power move mechanics. Fix requires observation-level instruction to name structural power moves when they appear.
- **T017 partial Q overcounting**: Q's 3/3 included evaluator false positives; Q3's 1/3 is more reliable
- **T004 minor regression**: `variable_output_normalized` (model variability, not systematic)

### 3. Test N extension — **DONE** (2026-04-01 16:07)

Results: 4/4 correct. WB11/12/13 = CRISIS, WB14 = ENGAGED. Guard generalizes across Indigenous, Black church, and West African susu contexts. Logged in experiment_log.md.

---

## Stable research findings (replicated, as of 2026-04-01)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 | **Replicated** — 3 disclosure types (deportation, racial violence, disability) |
| ESL transfer-as-intellectual-stretch (E002) | P + P2 + **P3 FIXED** | Stable failure in P/P2; prompt fix confirmed working in P3 |
| AAVE/code-switching: solid | P + P2 | Replicated (E001 4/4, E003 3/3 both runs) |
| Multilingual E013-E015 | P2 + P3 | 4/4 each in P2 and P3 (clean). E016 3/4 clean — contribution-specificity gap |
| Disability/chronic illness (E005) | P + P3 | 4/4 in P and P3; 3/4 in P2 was model variability. Stable. |
| Working student (E009) | P3 clean | 5/5 confirmed under isolation. P's 3/5 = real infra gap, now fixed. |
| E010 continuity/return framing | P + P2 + **P3 FIXED** | Was 3/4 in both P and P2 (different fails); prompt fix confirmed. |
| Tone policing missed by trajectory report (T006) | Q + Q3 | Persistent. Teacher Notes fix insufficient — upstream observation fix required |
| Community resilience guard | Test N + extension | 4/4 cultural contexts (Indigenous, Black church, susu, Somali) + WB14 control ✓. WB06 was unstable in one run (CRISIS→BURNOUT, March 29) but stable since. |
| S031 NONE/ENGAGED | Design intent | **Non-issue.** ENGAGED = safe-landing catch-all. Only CRISIS/BURNOUT trigger action. Both NONE and ENGAGED = no follow-up. |

---

## Key infrastructure notes for new monitor

- **MLX serial constraint**: Do NOT run two MLX tasks simultaneously. P3 must finish before Q3 starts.
- **Trajectory flags are stale**: `.trajectory_flags/` has all phases done from prior Test Q run. Always `--reset-flags` before Q3.
- **Commit before leaving**: `git add docs/research/session_log.md docs/research/experiment_log.md src/ scripts/ && git commit -m "Research session $(date +%Y-%m-%d): [summary]"`
- **P2 confound documented**: Test P2's 94.6% rate is not reliable — `get_student_history()` pulled Test P's observations in. P3 is the clean baseline.
