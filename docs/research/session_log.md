# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-04-13)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **DONE** | All stages complete. |
| ee5386e2 | 90005 (Biology, 25 subs) | **DONE** | Complete. |
| d3e2011c | 90005 (Biology fresh re-run) | **DONE** | Full pipeline re-run. |

### Active background tasks
None.

### Test queue
Empty. All scheduled tests (P3, Q3, Test N extension) completed Apr 2. See below for what's next.

---

## What needs to happen next

### 1. Q4 trajectory report validation — **NOT YET RUN**

The observation arc passthrough (`_build_observation_arc()` in trajectory_report.py) was implemented Apr 3-4 but has **not been validated by a test run**. The acid test:

- Re-run trajectory reports on the existing test corpus (same as Q3)
- Compare T006 Ingrid Johansson: does the report now surface the property tax breakthrough, "both sides" power move, and A4 partial regression?
- Compare all 17 students against Q3 baseline (35/48). Students that passed should still pass.

Launch: `caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b --reset-flags`

**Must `--reset-flags`** — `.trajectory_flags/` has stale phase flags from prior runs.

### 2. E016 replication — **NOT YET RUN**

The E016 prompt fix (relational epistemology contribution specificity) was implemented Apr 3. Needs a P4 equity trajectory run to validate.

Launch: `caffeinate -i python3 scripts/run_equity_trajectory_tests.py --model gemma12b --run-id P4`

### 3. Evaluator infrastructure bugs (low priority)

T008 and T010 each have 2 checks that permanently fail as "Not answered by evaluator." T008 also has malformed check IDs ("1", "2" instead of descriptive names). These are in the test script, not the pipeline.

---

## What was done (Apr 1-4 research session)

### Architecture changes

1. **Observation arc passthrough** (`trajectory_report.py`): `_build_observation_arc()` adds observation text to `semester_arc` with signal-aware compression. Inflection points (wellbeing change, theme shift >50%, word count delta >40%, register change) + most recent 3 assignments get full text; stable entries get first sentence only. Tested to 20 assignments at max volatility: 1803 tokens, under 3500 ceiling. Addresses T006 root cause — the report generator can now see the qualitative observations.

2. **Compression bottleneck principle documented** in experiment log: "Don't compress the perception; pass it through." The same structural error as binary concern detection — forcing rich qualitative reading into categories. The observation arc fix follows the same logic as the observation layer itself.

### Prompt fixes

3. **E016 relational epistemology** (`prompts.py`): Observation prompt now names what relational/narrative methods uniquely reveal (emotional labor, mutual care, interpersonal trust) — same "method legitimacy → contribution specificity" pattern as E002.
4. **Lens template concern fragments** (`lens_templates.py`): All 10 subject areas rewritten from enumerative checklists to generative frameworks. -14 net lines.
5. **Binary concern detector** removed from `__init__.py` re-export. Deprecated in production; only `research_engine.py` uses it directly.

### Infrastructure

6. **Metal OOM fix**: Mid-phase batch unload (8 students/batch) + caffeinate auto-applied per subprocess.
7. **Run isolation**: `--run-id` sets unique COURSE_ID per test run. P2's 94.6% was confounded by history bleed; P3 is the clean baseline.
8. **Test-monitor skill**: Revised with 5-step structured verification, anti-enumeration discipline, bounded QC pass.

### Test results (all logged in experiment_log.md)

| Test | Result | Key finding |
|------|--------|-------------|
| P3 (equity observations) | 55/56 (98.2%) | E002 + E010 fixed; E016 3/4 (new gap); first clean run |
| Q3 (trajectory reports) | 35/48 (72.9%) | T006 0/3 persistent (upstream fix needed); T002 fixed from P3 |
| Test N extension | 4/4 | Community resilience guard generalizes across 4 cultural contexts |

### Pipeline audit findings

- Enumerative fragility concentrated in concern detection (deprecated in production). Observation/coding/trajectory layers are already generative.
- Observations are ~250 tokens regardless of submission length (r=-0.03).
- Token budget for 20-assignment courses: tiered compression fits within 12B's 8K context.

---

## Stable research findings (replicated, as of 2026-04-02)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 + P3 | **Replicated** — 3 disclosure types, 3 consecutive clean runs |
| ESL transfer-as-intellectual-stretch (E002) | P + P2 + **P3 FIXED** | Stable failure in P/P2; prompt fix confirmed in P3 |
| AAVE/code-switching (E001, E003) | P + P2 + P3 | Replicated |
| Multilingual E013-E015 | P2 + P3 | 4/4 each (clean). E016 3/4 — contribution-specificity gap |
| Disability/chronic illness (E005) | P + P2 + P3 | 4/4 in P and P3; P2 3/4 was model variability |
| Working student (E009) | P3 clean | 5/5 under isolation |
| E010 continuity/return framing | P + P2 + **P3 FIXED** | Prompt fix confirmed |
| Tone policing in trajectory report (T006) | Q + Q3 | Persistent — observation arc passthrough implemented, awaiting Q4 validation |
| Community resilience guard | Test N + ext | 4/4 cultural contexts + 2 controls |

---

## Key infrastructure notes

- **MLX serial constraint**: Do NOT run two MLX tasks simultaneously.
- **Trajectory flags are stale**: Always `--reset-flags` before new trajectory runs.
- **Uncommitted work**: 13 modified files + 21 untracked (inbox module, OpenSpec skills, live-run fixes). These are feature work, not research pipeline changes.
- **Commit before leaving**: `git add docs/research/session_log.md docs/research/experiment_log.md src/ scripts/ && git commit -m "Research session $(date +%Y-%m-%d): [summary]"`
- **P2 confound documented**: Test P2's 94.6% is not reliable. P3 is the clean baseline.
- **Experiment log**: 6700+ lines. All entries verified against raw JSON. Scholarly connections added (Yosso 2005, Paris & Alim 2017, Tuck 2009, Tuck & Yang 2014, Zheng et al. 2023).
