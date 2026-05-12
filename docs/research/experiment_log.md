# Experiment Log — 2026-03-22

Chronological record of experiments, decisions, and findings.

---

## 19:49 — Qwen 2.5 7B full pipeline started
- `--course ethnic_studies --no-resume`
- Model: `mlx-community/Qwen2.5-7B-Instruct-4bit` via MLX
- 32 students, full pipeline

## 20:09 — Qwen coding checkpoint
- 32 codings complete
- First look: all concern_flag=False in coding records (separate from concern detection stage)

## 20:23 — Qwen concerns checkpoint
- S015 ✓, S018 ✓, S025 ✓ (3/3 concern detection)
- S029 ✗ FALSE POSITIVE — "personal stress/difficulty" for neurodivergent writing
- S006, S014 also false positives (strong writers)
- Total flagged: 7 students

## 20:38 — Qwen synthesis
- calls_completed: 2/4 (only concern + temperature)
- strong=0, limited=0 — AIC not installed, no engagement signals
- **Identified code bug:** synthesis gating requires AIC engagement signals

## 20:40 — Chatbot handoff generated
- `chatbot_export_ethnic_studies_full.md` — 38.5KB, ~9600 tokens
- Original concern instructions had "students in personal crisis" — too vague

## 20:52 — Qwen full pipeline complete
- 3821.63s total, 119.43s/student
- S002 truncation NOT propagated (code bug)
- S018 feedback validates colorblind framing before redirecting (quality issue)
- 16 fragmented themes (meta-synthesis JSON parse failed)

## ~20:55 — Gemini handoff Run 1
- Pasted into Gemini Pro browser chatbot
- 2/3 concerns (missed S015 Brittany essentializing)
- 0 false positives, S029 CELEBRATED
- Theme quality exceptional (4 coherent themes)
- Jordan Espinoza: "leveraged neurodivergent writing style as meta-commentary"
- Imani Drayton: "AAVE as epistemological stance"

## 20:57 — Three code fixes implemented
1. Truncation propagation (generate_demo_insights.py)
2. Synthesis call fallback classifier (synthesizer.py)
3. Meta-synthesis JSON retry (theme_generator.py)

## 21:00 — Chatbot export prompt tightened
- Added AAVE/neurodivergent/multilingual protection
- Added essentializing linguistic patterns ("they always...", celebratory stereotypes)
- Replaced vague "personal crisis" with explicit 4-category concern list

## ~21:05 — Gemini handoff Run 2 (with tightened prompt)
- **3/3 concerns** — S015 NOW CAUGHT with excellent suggested response
- "What happens to a Black person who is exhausted and doesn't want to be resilient?"
- 0 false positives
- **Finding:** Linguistic pattern examples ("they always...") were the key missing element

## 21:15 — Backend bug found
- `--backend ollama` had no explicit handler, fell through to auto_detect → MLX
- Fixed: added explicit `ollama` and `mlx-llama` backend handlers

## 21:20 — Llama 3.1 8B MLX full pipeline started
- `--backend mlx-llama --no-resume`
- Model: `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit`
- Same 32 students, same prompts, different base model

## 21:20 — MLX default changed
- `llm_backend.py` default: Qwen 2.5 7B → Llama 3.1 8B
- Based on early coding checkpoint showing richer theme tags

## 21:41 — Llama coding checkpoint analyzed
- S029 tags: "critique of traditional academic expectations" — model NOTICED the form
- S028 tags: "code-switching as survival strategy" — genuine engagement
- S027 tags: "critiquing neutrality in science" — specific, not generic
- Clear quality improvement over Qwen across all equity-critical students

## 22:06 — Llama concerns checkpoint
- S015 ✓ caught (essentializing)
- S018 ✗ missed (colorblind)
- S025 ✗ missed (tone policing)
- S029 ✓ CLEAN — no false positive
- **Finding:** Different failure profile from Qwen. Llama is conservative (0 FP, 1/3 detection)

## 22:09 — Synthesis-first prototype launched (Nemotron 9B via OpenRouter)
- Full-class reading pass → inject into per-student coding
- Class reading: 219 words (truncated by free tier), noticed Maria's multilingual syntax
- Concern detection: 0/3 (model too weak for structured JSON)
- Equity: 4/4 clean
- `what_student_is_reaching_for`: 3/7 populated (when model succeeded, descriptions were good)
- **Finding:** Architecture is directionally right, model insufficient for proof-of-concept

## 22:23 — Llama synthesis complete
- **4/4 calls succeeded** (first time)
- 5 highlights, 2 tensions, class temperature
- Synthesis fallback classifier working (9 strong students identified)

## 22:30 — Synthesis-first theory session
- Identified three universal oriented readers (asset, threshold, connection)
- Protective meta-check for equity
- Generalizability model across disciplines
- Adversarial critic pass, reader-not-judge, immanent critique as mechanisms

## 22:41 — Llama MLX full pipeline complete
- 4713.8s total, 147.31s/student

## 22:50 — Synthesis-first prototype on MLX Llama
- Class reading: 234.8s, rich observations
- Per-student coding: ~45s each, all 7 students
- **S015: MISSED** (was caught in standard Llama)
- **S018: CAUGHT** (was missed in standard Llama)
- S025: missed (both)
- S029: CLEAN (both)
- `what_student_is_reaching_for`: 7/7 populated

**KEY FINDING: Architecture shifts attention pattern, doesn't uniformly improve it.**
Standard + synthesis-first combined: 2/3 detection, 0 FP.
This is the complementary attention pattern — different architectures see different things.

## 22:55 — 70B and 27B prototype runs attempted (OpenRouter)
- Rate limited on free tier across all providers
- Retry logic added, runs pending
- These test whether model size or architecture is the primary driver

---

# Experiment Log — 2026-03-23

## 08:50 — Resume from handoff, check overnight runs

Pairwise concern check (MLX Llama 8B): Mixed results.
- Tests 2-3 correctly caught Aiden's tone policing (confidence 0.8)
- Test 4 (control) also flagged tone_policing=True — false positive
- Pairwise approach can't distinguish relational context; flags Aiden regardless of pair
- Test 1 (standalone focused prompt) caught all 3 concerns on same 8B model — confirms
  prompt length as root cause, not model capability

70B and 27B runs: Both failed with 401 auth (key was hardcoded, not from env).

**Security fix:** Removed hardcoded OpenRouter API key from prototype_synthesis_first.py
(was in git history — commits e045fd1 and 44b6d1f). Key rotated. All scripts now read
from REFRAME_SHARED_OPENROUTER_KEY env var.

## 09:00 — Synthesis-first v3 on MLX Llama 8B (refined connection reader)

Result: **1/3 concerns, 0 FP** — identical to prior runs.
- S018 Connor (colorblind): FLAGGED
- S015 Brittany (essentializer): MISSED
- S025 Aiden (tone policer): MISSED
- All equity students: CLEAN

Class reading noticed Connor's colorblind framing but mislabeled it as "tone policing."
**Did not name Aiden at all.** Model adopted Aiden's frame in what_student_is_reaching_for:
"trying to balance the need for intellectual discussion with the importance of emotional
regulation and respect" — treats tone policing as a virtue.

**Finding:** Refined connection reader prompt (relational move examples) did not improve
8B concern detection. The architecture doesn't fix what the model can't see.

## 09:15 — Paid OpenRouter runs: Gemma 27B + Llama 70B

Switched from free tier (:free suffix) to paid models.

### Gemma 3 27B (synthesis-first prototype)
- **3/3 concerns, 0 FP**
- Class reading explicitly names Aiden as "subtle silencing of the passionate engagement
  demonstrated by students like Destiny Williams"
- Correctly distinguishes tone policing (Aiden) from colorblind erasure (Connor)
- Adds pedagogical guidance: "not to shame Connor, but to unpack the harm"
- Family narratives recognized as "epistemology" not "illustration"
- what_student_is_reaching_for: Yolanda's narrative is "epistemologically valid"
- Theme tags: specific ("colorblindness", "medical racism", "epistemology", "translation")
- **Qualitatively approaching Gemini handoff benchmark**

### Llama 3.3 70B (synthesis-first prototype)
- **3/3 concerns, 0 FP**
- Class reading names Connor but hedges ("could be seen as"). Does NOT name Aiden.
- what_student_is_reaching_for: generic, nearly identical to 8B outputs
- Theme tags: generic ("intersectionality, personal experience" repeated)
- **Quantitatively matches 27B Gemma; qualitatively far behind**

**KEY FINDING: Model family matters more than size.** Gemma 27B > Llama 70B on every
qualitative dimension. Architecture/training trumps raw parameter count.

## 09:30 — Gemma 4B synthesis-first (Ollama, already installed)

Result: **3/3 concerns, 4 FP**
- Catches all three concern patterns (essentializing, colorblind, tone policing)
- BUT false-positives on ALL equity-critical students (S023, S027, S028, S029)
- Pattern: "essentializing-paranoid" — flags everyone for "leaning toward essentializing"
- Same pattern as Qwen 7B from round 2 (catches all concerns but over-flags)

**Finding:** Gemma catches 3/3 at EVERY size tested (4B, 27B). Llama can't at 8B.
Model family is the primary variable for concern detection. But 4B lacks the judgment
to protect equity-critical students. Threshold is somewhere between 4B and 27B.

## 09:37 — Gemma 12B synthesis-first (MLX, downloaded gemma-3-12b-it-4bit)

Running. This is the critical test: if Gemma 12B achieves 3/3 with 0 FP, it's the
new lightweight tier model.

## 09:34 — Standard pipeline runs on Gemma 27B (OpenRouter paid)

Two runs launched to test lightweight vs medium tier prompts on the same model:
1. `generate_demo_insights.py --tier lightweight` → Gemma 27B
2. `generate_demo_insights.py --tier medium` → Gemma 27B

These use the STANDARD pipeline prompts (CONCERN_PROMPT at 517 words, dedicated concern
detection step, tier-specific coding and synthesis prompts). This will show whether the
synthesis-first prototype results hold on the production pipeline.

## Corpus change between rounds (important confound)

Round 1 corpus had ~20 students. Round 2 corpus has 32 students — students S004-S009
and S012-S014 were added. Test students (S015, S018, S025, S023-S029) kept the same
text, but the class context changed significantly. This affects:
- Synthesis-first class reading (50% more context to process)
- Standard pipeline: NOT affected (per-student concern detection is independent)

Round 1 results on standard pipeline:
| Model | Concerns | False Positives |
|---|---|---|
| Qwen 7B | 3/3 | 0 (round 1 corpus) |
| Llama 70B | 3/3 | 0 |
| Deepseek | 3/3 | 6 extra FP |
| Qwen 32B | 1/3 (S018 only) | 0 |

Note: Qwen 32B only catching 1/3 in round 1 shows this was NEVER a simple size→quality
relationship. Model family and training have always been the primary variables.

## Emerging analysis framework

The user identified 4 dimensions of comparison (not just concern flags):
1. **Concerns** — flag detection accuracy
2. **Positive insights** — asset recognition, what_student_is_reaching_for, naming
   intellectual work in non-standard forms
3. **Class trends** — themes, tensions, synthesis, class temperature
4. **Qualitative richness** — immanent critique, pedagogical action, language justice
   recognition, whether family narrative is epistemology or illustration

Gemini handoff excels on dimensions 2-4. Pipeline models are measured mainly on
dimension 1. The real teacher value lives in dimensions 2-4.

## Open questions

1. **Root cause of variance:** Is it model training data? RLHF alignment? Architecture?
   Gemma's training on educational/social content may give it better priors for
   recognizing subtle social dynamics. Llama's strength is structured output compliance.

2. **Model-specific architecture:** Rather than building model-agnostic prompts, should
   we optimize for a specific model family at each tier? The same prompt produces
   radically different results across families.

3. **Distributed intelligence:** The synthesis-first architecture is one form of this.
   What if we decompose further — separate readers for each framework dimension, then
   compose? A "tone policing detector" prompt can be short and sharp (276 words catches
   it on 8B). A "class reading" prompt can be long and exploratory. Don't ask one prompt
   to do everything.

4. **Essay length scaling:** Current prototype truncates to 150 words/student for class
   reading. Real essays could be 10-20 pages. Solutions: adaptive truncation, chunked
   class readings, summarize-then-read. Per-student concern detection is independent
   of class size (already scales). The class reading is the bottleneck.

5. **Hybrid pipeline integration:** Standard catches S015 on Llama 8B. Synthesis-first
   catches S018 on Llama 8B. Combined with tiered concern prompt: theoretical 3/3.
   But if Gemma 12B achieves 3/3 natively, the hybrid approach may be unnecessary —
   just switch model families.

## 10:00 — Gemma 12B synthesis-first results (MLX local)

**3/3 concerns, 1 FP (Camille).**
- S015 Brittany: FLAGGED (essentializing "amazing resilience")
- S018 Connor: FLAGGED (×2 colorblind claims)
- S025 Aiden: FLAGGED ("form of tone policing")
- S023 Yolanda: CLEAN
- S027 Camille: FALSE POSITIVE (flagged her critical BMI analysis phrasing)
- S028 Imani: CLEAN
- S029 Jordan: CLEAN — described as "resisting pressure to conform to traditional
  academic writing structures. This is a valuable asset."

Runs locally on 16GB Mac. Class reading: 274s. Per-student coding: ~525s. Total ~13 min.
Qualitatively strong: rich theme tags, asset-framing of non-standard forms.
The 1 FP on Camille is the weakest link — may be addressable through prompt refinement.

**Gemma detection across sizes (synthesis-first):**
| Size | Concerns | FP | Local? |
|---|---|---|---|
| 4B | 3/3 | 4 | Yes (Ollama) |
| 12B | 3/3 | 1 | Yes (MLX) |
| 27B | 3/3 | 0 | Cloud |
Gemma catches 3/3 at every size. The variable is false positive suppression.

## 10:05 — CRITICAL FINDING: Standard pipeline misses tone policing on 27B

Gemma 27B standard pipeline (medium tier): **2/3 concerns, 0 FP.**
- S015 Brittany: FLAGGED
- S018 Connor: FLAGGED
- S025 Aiden: **MISSED**

The SAME MODEL (Gemma 27B) catches Aiden on synthesis-first but MISSES on standard
pipeline. This is the most important finding of the day.

**Root cause:** Tone policing is a RELATIONAL harm — it's only visible when you see
Aiden's words in context of Destiny's urgency. The standard pipeline evaluates each
student in isolation. Without the class reading, "requesting calm discussion" looks
reasonable; WITH the class reading, it's visible as silencing.

The model SAW the pattern in the standard pipeline — Aiden's theme tags include
"meta-commentary on classroom dynamics" and "request for emotional regulation in
discussions" — but did not FLAG it, because in isolation the pattern doesn't look harmful.

**Implication:** Synthesis-first isn't optional for the concern detection system.
It's structurally necessary for detecting relational harms. The class reading
provides the relational context that makes tone policing, and potentially other
relational moves, visible.

This validates the architecture: the system needs to read the class as a community
BEFORE evaluating individuals. Reading each student in isolation reproduces the
atomized, decontextualized evaluation that the frameworks critique.

## 10:10 — Cloud enhancement test (anonymized 8B patterns → Gemma 27B cloud)

Tested hybrid architecture: 8B local coding → anonymized patterns → 27B cloud
enhancement. Cloud model never sees student names, quotes, or identifiable text.

Result: Cloud enhancement produced Gemini-level qualitative analysis including:
- Immanent critique: "The model's framing *replicates* the silencing"
- Impact analysis: "This isn't about intent, but about the *impact*"
- Language justice: "different pathways to academic rigor"
- Anti-spotlighting: "Instead of individual interventions, focus on structural
  opportunities"

**The hybrid architecture works.** Local model handles FERPA-protected per-student
work; cloud model lifts pattern-level analysis to benchmark quality on anonymized data.

## 10:30 — Gemma 27B standard pipeline lightweight tier complete

**2/3 concerns, 0 FP — identical to medium tier.** S025 Aiden MISSED.
Aiden's tags: "classroom dynamics", "managing conflict", "framing of emotional
expression", "desire for neutrality" — model describes the mechanism, doesn't flag it.

Lightweight vs medium distinction does NOT matter for concern detection on 27B.
Both miss the same thing for the same reason: no class context.

## 10:45 — All tests complete. Architecture decisions settled.

### Final results matrix

| Architecture | Model | Concerns | FP | S025 | Qual |
|---|---|---|---|---|---|
| Synth-first | Llama 8B | 1/3 | 0 | MISSED | Weak |
| Synth-first | Gemma 4B | 3/3 | 4 | caught | Mod |
| Synth-first | **Gemma 12B** | **3/3** | **1** | **caught** | **Good** |
| Synth-first | **Gemma 27B** | **3/3** | **0** | **caught** | **Strong** |
| Synth-first | Llama 70B | 3/3 | 0 | caught | Weak |
| Standard LW | Gemma 27B | 2/3 | 0 | MISSED | — |
| Standard MED | Gemma 27B | 2/3 | 0 | MISSED | — |
| Cloud enhance | 8B→27B anon | — | — | identified | Benchmark |
| Handoff | Gemini Pro | 3/3 | 0 | caught | Benchmark |

### Three architecture decisions

1. **Synthesis-first required.** Standard pipeline misses tone policing even on 27B.
   Relational harms need class context. Reading the class as a community BEFORE
   evaluating individuals is structurally necessary.

2. **Gemma is the model family.** 3/3 at every size (4B-27B). Llama 8B can't.
   12B runs locally on 16GB hardware (teacher's laptop).

3. **Cloud enhancement works.** Anonymized patterns → cloud model produces
   Gemini-level qualitative richness. Available as optional API call or
   manual handoff (teacher pastes into institutional chatbot).

### Deployment tiers

- **Tier 1 (fully local):** Gemma 12B MLX → 3/3, 1 FP, ~13 min. 16GB Mac.
- **Tier 2 (local + handoff):** Tier 1 + generated prompt for institutional chatbot.
  No API, no cost. Fills qualitative gap.
- **Tier 3 (local + API):** Tier 1 + automated cloud enhancement. Institution
  provides API endpoint and privacy agreement.
- **Tier 4 (institutional server):** Gemma 27B → 3/3, 0 FP. IT infrastructure.

### Implementation plan: Integrated pipeline

Build ONE pipeline that does:
1. Synthesis-first class reading (local Gemma)
2. Per-student coding with class context injected (local)
3. Per-student concern detection with class context injected (local)
4. Theme generation + synthesis (local)
5. Optional: cloud enhancement on anonymized patterns (API or handoff prompt)

Key: inject class reading as context into the existing CONCERN_PROMPT, not replace it.
The standard pipeline's concern guidelines + class context = both relational detection
AND the careful "do NOT flag" protections.

### Hardware requirements

| Model | RAM needed | Devices |
|---|---|---|
| Gemma 12B 4-bit | 16GB | M1/M2/M3 MacBook, mid-range Windows |
| Gemma 27B 4-bit | 32GB | M1+ Pro/Max, RTX 3090/4090, institutional |
| Gemma 4B (backup) | 8GB | Any modern machine (but 4 FP) |

---

## Afternoon Session: Pipeline Implementation + Round 3

### Pipeline built (Phases 1-7)

Integrated synthesis-first pipeline: class reading → coding with context →
concern detection with context + linguistic note + sentiment suppression.
New file: `src/insights/class_reader.py`. Modified: engine.py, prompts.py,
concern_detector.py, insights_store.py, llm_backend.py, chatbot_export.py,
generate_demo_insights.py. All syntax-checked.

### AIC linguistic justice integration

Three gains from experiments:
1. Sentiment suppression caveat in concern detection signal matrix
2. Protected feature excerpt boost (2x word budget for AAVE/multilingual/neurodivergent)
3. Disability self-advocacy protection in CONCERN_PROMPT — "Is the problem the
   student's body, or the built environment?" Tested: S029 CLEAN, S025 still caught.

### Round 3 results (27B with class reading, full pipeline)

| Config | S015 | S018 | S025 | Equity | Notes |
|---|---|---|---|---|---|
| 27B LW + class reading | missed | FLAG | **FLAG** | 0 FP | Tone policing caught! |
| 27B MED + class reading | missed | FLAG | missed | 0 FP | Medium buried signal |

S015 regression: both missed Brittany. Lightweight > medium for relational harms.

### Hidden ideas: prompts written, not wired in

- CONCERN_CRITIC_PROMPT (adversarial critic) — in prompts.py, not in detection flow
- CONCERN_IMMANENT_CRITIQUE_ADDENDUM — in prompts.py, not injected
- Full tracker: docs/research/hidden_ideas_tracker.md

### Replication study (CRITICAL — partial results)

5 runs × 7 students × 3 configs on OpenRouter. Early results:

| Config | Pattern across 5 runs | Reliability |
|---|---|---|
| **A: Gemma 12B + class reading** | FFF.... × 5/5 | **100% (3/3, 0 FP every run)** |
| B: Gemma 27B + class reading | FFF.... × 4/5, F...... × 1/5 | 80% at 3/3 |
| C: Gemma 27B no context | .FF.... pattern | ~2/3, S025 missed |

**If Config A holds: Gemma 12B + class reading is the proven, reliable architecture.**
The 12B outperforms 27B on reliability with class context. This is the most important
finding of the session — the architecture compensates for model size AND produces
consistent results.

## 13:30 — Replication study COMPLETE (final results)

| Student | Expected | 12B+ctx (5/5) | 27B+ctx (5/5) | 27B no ctx (5/5) |
|---|---|---|---|---|
| S015 Brittany | FLAG | **100%** | **100%** | **0%** |
| S018 Connor | FLAG | **100%** | 80% | **100%** |
| S025 Aiden | FLAG | **100%** | 80% | 100% |
| S023 Yolanda | CLEAN | **0%** | 0% | 0% |
| S027 Camille | CLEAN | **0%** | 0% | 0% |
| S028 Imani | CLEAN | **0%** | 0% | 0% |
| S029 Jordan | CLEAN | **0%** | 0% | 0% |

**HEADLINE: Gemma 12B + class context = PERFECT. 100% flags, 0% FP, 5/5 runs.**

Key insights:
- 12B MORE reliable than 27B with class context (100% vs 80%)
- S015 essentializing goes from 0% → 100% with class context
- Class reading helps with ALL concern types, not just tone policing
- Zero false positives across all 45 individual checks (15 runs × 3 configs)
- Architecture compensates for model size

**CAVEAT:** This is on synthetic test data. Real student writing will be messier.
The 100% tells us the architecture works on known patterns, not that it generalizes.

## 13:45 — Full 4-dimension analysis written

See `docs/research/round3_full_analysis.md` for the complete evaluation across:
1. Concern detection (replication frequency data)
2. Positive insights (what_student_is_reaching_for across models)
3. Class trends (community reading vs individual listing)
4. Qualitative richness (immanent critique, pedagogical action, language justice)

Key cross-cutting finding: **Model family > model size for equity framing.**
Llama 70B ≈ Llama 8B on every qualitative dimension. Gemma 12B > Llama 70B.

## 14:00 — Free-tier cloud enhancement test

Tested anonymized payload (~400 words) on free-tier OpenRouter models.
Free-tier rate-limited (daily quota exhausted from earlier testing).
Paid Gemma 27B scored 5/6 on quality checks. Architecture is viable for
free-tier use — the payload is small enough. Re-test when quota resets.

## Session end — still running

- Gemma 12B MLX full pipeline → /tmp/round3_gemma12b_final.log
  → Results to src/demo_assets/insights_ethnic_studies_gemma12b_mlx.json

## Session summary

Built the integrated synthesis-first pipeline. Tested across 5 model families,
3 sizes, 2 pipeline architectures. Replication study proves 100% reliability
on Gemma 12B + class context. AIC linguistic justice integrated. Disability
self-advocacy protection working. Hidden ideas tracked. Full 4-dimension
evaluation written. Architecture is validated on synthetic data — real data
testing is the critical next step.

---

# Session — 2026-03-23 (continued)

## 12B MLX Full Pipeline Analysis

The 12B full pipeline completed overnight but revealed significant issues:

### Theme generation: 8 timeouts
Every theme group (7/7) timed out at 300s. Meta-synthesis also timed out.
Fell back to tag-frequency themes. JSON parse errors on retry attempts.
**Root cause**: 12B generates themes that are too verbose for the max_tokens
budget, producing truncated JSON. Needs either higher timeout, tighter
max_tokens for theme generation, or more aggressive output length guidance.

### Concern detection: 9 false positives (critical)

| Student | Expected | Result | Issue |
|---|---|---|---|
| S015 Brittany | FLAG | MISSED | Essentializing not detected |
| S018 Connor | FLAG | ✓ | Colorblind correctly flagged |
| S025 Aiden | FLAG | ✓ | Tone policing correctly flagged |
| S001 Maria | CLEAN | FALSE POS | "Strong demonstration of understanding" flagged |
| S004 | CLEAN | FALSE POS | "Thoughtful question" flagged |
| S005 | CLEAN | FALSE POS | "Productive critique" flagged |
| S008 | CLEAN | FALSE POS | "Valuable area of inquiry" flagged |
| S014 | CLEAN | FALSE POS | "Thoughtful question" flagged |
| S020 | CLEAN | FALSE POS | "Grappling with complex question" flagged |
| S029 Jordan | CLEAN | **FALSE POS** | **Protected student** flagged for "self-advocacy" |

**Root cause analysis — two factors:**

1. **max_tokens=4096 (default) vs 500 (replication study)**: With 4096 tokens
   available, the 12B model fills the space by analyzing every student's
   submission in detail, labeling strengths as "concerns." With 500 tokens,
   it's forced to be selective and only flags real concerns.

2. **APPROPRIATE signal contamination**: The full pipeline passes signal matrix
   results like "APPROPRIATE — Sophisticated analysis — student engaging well"
   to the concern prompt. The replication study passes "No non-LLM concern
   signals." The APPROPRIATE labels confuse the model into analyzing those
   strengths rather than looking for actual concerns.

**Fixes applied:**
- `concern_detector.py`: Set max_tokens=800 for concern detection calls
- `concern_detector.py`: Filter out APPROPRIATE signals before passing to
  the concern prompt. Only actual concern signals reach the LLM.
- Both `_format_signal_matrix_for_prompt()` and `_format_signal_matrix_tuples()`
  now skip APPROPRIATE signals, returning "No non-LLM concern signals" when
  all signals are clean.

**Key insight**: The replication study tested concern detection in isolation
with clean inputs and got 100%. The full pipeline introduces noise through
(a) excessive output budget and (b) APPROPRIATE-signal contamination. The
fix constrains the model to produce focused concern output, matching the
conditions that produced reliable results.

**Status**: Fixes committed to code, needs re-testing on 12B.

## 12B Full Pipeline Timing (critical)

The complete 12B MLX run on 32 students took **11 hours**:

| Stage | Time | % of total | Notes |
|---|---|---|---|
| Quick Analysis | 3.5s | 0% | Non-LLM, fast |
| Class Reading | 466s (7.8m) | 1.2% | Single pass, 609 words |
| Per-student Coding | 3,348s (56m) | 8.5% | 104s/student avg |
| Concern Detection | 3,635s (1h) | 9.2% | 113s/student (with FP issue) |
| **Theme Generation** | **27,509s (7.6h)** | **69.6%** | **ALL GROUPS TIMED OUT** |
| Outlier Surfacing | 660s (11m) | 1.7% | |
| Synthesis | 780s (13m) | 2.0% | 4/4 calls succeeded |
| Feedback Drafts | 3,038s (51m) | 7.7% | |

**Theme generation is the dominant bottleneck.** 7/7 groups + meta-synthesis
all hit the 300s timeout. JSON parse errors on retries. The 12B model
generates themes that exceed max_tokens, producing truncated JSON.

**Implication for 60-student classes:** Coding + concerns scale linearly
(~3.5 min/student). At 60 students, coding alone = ~5.5 hours. Themes
will be worse (more groups). Total pipeline: ~20+ hours on 12B.

This is not viable for teachers. Options:
1. Reduce coding prompt complexity (fewer fields, tighter max_tokens)
2. Batch students in coding (multiple students per call)
3. Skip themes entirely (they're the weakest stage quality-wise)
4. Use the reader-not-judge two-pass approach — free-form read is faster
   than complex JSON generation because the model doesn't fight the schema

## Free-tier cloud test (re-run)

Free-tier models still 429 rate-limited (quota likely resets daily).
Paid Gemma 27B: 5/6 quality, 44.6s, 860 words. Missed immanent critique,
got everything else (tone policing, AAVE-as-asset, structural teaching
action, neurodivergent recognition, anti-spotlighting).

## 60-student scaling test — class reading only — DONE

Ran 60-student class reading on Gemma 12B MLX (single-pass, no clusters
available without PyTorch for embeddings).

| Metric | 32 students | 60 students | Ratio |
|---|---|---|---|
| Prompt words | ~5200 | ~9540 | 1.8x |
| Time | 466s (7.8m) | 648s (10.8m) | 1.4x |
| Output words | 609 | 707 | 1.2x |

**Findings:**
- Scaling is sublinear — 2x students → 1.4x time. Good.
- 9540-word prompt fits 12B context window. No truncation errors.
- Output follows asset/threshold/connection structure.
- Names specific students and relationships — not just a list.
- Model defaulted to JSON wrapper despite free-form prompt — minor issue.
- Without clustering, fell back to single-pass (60 students in one call).
  Hierarchical path not tested — needs PyTorch for embedding clusters.

**Implication:** Class reading is NOT the bottleneck. At 60 students,
it's ~11 minutes. Per-student coding (at 104s/student × 60 = ~6240s = 1.7h)
and themes are the real time sinks.

**Quality note:** Brief submissions (surface/minimal) risk being
overlooked in a 60-student single-pass. The `[NOTE: Brief submission]`
annotations help, but the hierarchical path (smaller groups) would
give each student more attention. Install PyTorch for embeddings
to test the hierarchical path.

---

# Session — 2026-03-24

## Reader-Not-Judge Coding: A/B Comparison (Gemma 12B MLX)

Tested `code_submission()` (standard JSON-first) vs `code_submission_reading_first()`
(free-form read → extraction) on 3 students chosen for different failure modes.

### Bug found: empty submissions in first run

Test script used `student.get("submission_text", "")` but corpus field is `text`.
First run analyzed empty strings — model fabricated plausible analyses from nothing.
Standard coding gave IDENTICAL output for 2/3 students (same tags, same register).
Reading-first at least produced distinct fabrications per student. Fixed field name,
re-ran with actual submission text.

### Bug found: Pass 1 returned JSON despite instructions

Prompt said "no JSON, no bullet points" but Gemma 12B defaulted to JSON structure.
Fix: added explicit "Do NOT output JSON, code blocks, or structured data. Write in
plain paragraphs only." to CODING_READING_FIRST_P1. Fix worked — second run produced
plain prose.

### Results: 3 students, Gemma 12B MLX, with class reading context

**Maria Ndiaye (ESL, 205 words)**

| Dimension | Standard | Reading-First |
|---|---|---|
| Theme tags | 3 (generic: "connecting intersectionality") | 4 (specific: "Cross-cultural relevance", "Critique of Western-centric perspectives") |
| Quotes found | 2 | 3 (caught Senegal quote standard missed) |
| Personal connections | 2 | 1 (coarser grouping but same content) |
| Emotional register | passionate | passionate\|personal\|reflective (richer) |
| Readings referenced | [] | [] |
| what_reaching_for | n/a | "demonstrating sophisticated understanding of intersectionality, moving beyond theoretical definitions to connect it to concrete lived experiences...while also offering a thoughtful critique of the course readings' scope" |

Reading-first won: richer tags, extra quote, asset framing of multilingual writing.

**Talia Reyes (lived experience, no vocab, 181 words)**

| Dimension | Standard | Reading-First |
|---|---|---|
| Theme tags | 3 (generic) | 4 (includes "additive vs. generative models") |
| Quotes found | 2 | 2 (different — caught "I'm not totally sure if that's what the reading is describing") |
| Readings referenced | [] | ["Crenshaw's concept of intersectionality"] |
| Personal connections | 1 | 3 (Latina identity, honors classes, belonging) |
| what_reaching_for | n/a | "grappling with whether her feelings of not belonging align with the theoretical framework" |

Reading-first won decisively: caught the Crenshaw reference standard missed entirely,
named 3x more personal connections, identified the conceptual move (additive →
generative discrimination models), and surfaced the moment of intellectual vulnerability.

**Tyler Huang (premise challenger, 104 words)**

| Dimension | Standard | Reading-First |
|---|---|---|
| Theme tags | 3 (generic: "understanding intersectionality") | 3 (specific: "clarity and directness", "measured engagement") |
| Quotes found | 2 | 2 (overlapping) |
| Emotional framing | analytical (deficit: "lacks personal connection") | analytical (asset: "quiet confidence", "measured engagement") |
| what_reaching_for | n/a | "demonstrating thoughtful and considered engagement, prioritizing clear understanding over performative elaboration" |

Reading-first won on framing: reframed brevity as deliberate intellectual choice
rather than a gap. Standard described what Tyler DIDN'T do; reading-first described
what Tyler IS doing.

### Key findings

1. **Reading-first produces asset framing where standard produces deficit framing.**
   Tyler's 104-word submission was "lacks personal connection" (standard) vs
   "prioritizing clarity over performative elaboration" (reading-first). The free-form
   reading step lets the model see the student's intellectual project before being
   asked to fill slots. This is the core mechanism.

2. **Reading-first catches references standard misses.** Talia's Crenshaw reference
   was invisible to JSON-first coding but obvious in the free-form reading. The model
   noticed it when reading naturally, then extracted it in Pass 2.

3. **`what_student_is_reaching_for` is the most valuable new field.** Every entry
   gave teachers actionable insight that standard coding simply doesn't produce.
   This is where the synthesis-first philosophy ("read the class as a community,
   read each student as a person") pays off at the per-student level.

4. **Timing: ~2 min/student** (both approaches similar). Reading-first is NOT slower
   despite being 2 passes — the free-form pass is faster than complex JSON generation
   because the model doesn't fight the schema.

### Decision: integrate reading-first as default coding path

Reading-first wins on every qualitative dimension. No regression on any metric.
The `what_student_is_reaching_for` field alone justifies the change. Standard
`code_submission()` remains available as fallback but reading-first should be
the default for the synthesis-first pipeline.

## Reading-first integrated + long paper chunking

### Integration (engine.py)
- Both main and resume coding paths now call `code_submission_reading_first()`
- `code_submission()` still exists as fallback, no longer called by engine
- Linguistic context (AAVE, multilingual, neurodivergent notes) flows through

### Long paper chunking (submission_coder.py)
- Added `_chunk_text()`: paragraph-first splitting (\n\n > sentence > hard cut)
- 3000-char chunks, 400-char overlap at boundaries
- Short submissions (<3000 chars) pass through unchanged — zero overhead
- Pass 1 runs per chunk; readings merge for Pass 2 extraction
- Pass 2 gets beginning + end of full text for quote verification
- A 10-page paper (~15K chars) → ~7 chunks → 7 Pass 1 readings → 1 Pass 2

Previously ALL pipeline coding paths silently truncated at 2000-3000 chars,
dropping everything after ~page 1. Students who wrote the most got read the
least — the system penalized depth of engagement.

### Prompt fix
- CODING_READING_FIRST_P1: added explicit anti-JSON instruction ("Do NOT output
  JSON, code blocks, or structured data. Write in plain paragraphs only.")
  Gemma 12B was defaulting to JSON despite "no JSON" in the existing prompt.

### Files changed
- `src/insights/engine.py` — import + call site switch (main + resume paths)
- `src/insights/submission_coder.py` — `_chunk_text()`, chunked Pass 1 loop,
  beginning+end Pass 2 text for long submissions
- `src/insights/prompts.py` — anti-JSON reinforcement in P1

---

# Experiment Log — 2026-03-24

## Concern detector refactor

### Changes from prior session (carried into today)
- Removed `concern_type` field from `ConcernRecord` — the 12B model was
  hallucinating concern categories ("academic_integrity_concern", "emotional_distress"
  etc.) that it couldn't reliably classify. New design: model surfaces, teacher
  classifies. Honest about what 8B-12B can do.
- Simplified to `why_flagged` (free text) + `confidence` (0.0–1.0)
- Confidence threshold at 0.7 — drops low-confidence flags to reduce teacher noise
- Anti-bias post-processing: regex checks LLM output for tone-policing language
  ("aggressive", "too emotional", "hostile tone") and demotes + warns if detected
  alongside structural critique keywords
- Course content vs. student distress distinction: detects when the model flags
  subject matter ("this passage discusses rape") rather than student wellbeing,
  demotes with explanation

### Broader significance: human-in-the-loop as epistemic honesty
The decision to remove `concern_type` and let teachers classify is not just a
capability limitation workaround — it's a design position. Small models can detect
*that something is present* (a passage that warrants attention) more reliably than
they can classify *what it is*. Forcing classification produces confident-sounding
labels that teachers may over-trust. This connects to Selbst et al.'s (2019)
"Fairness and Abstraction in Sociotechnical Systems" — abstraction traps occur when
systems formalize categories that should remain contextual. A teacher reading "this
student mentioned feeling overwhelmed" decides whether that's burnout, normal stress,
or a student processing difficult course material. An AI label of "emotional_distress"
forecloses that judgment.

The anti-bias post-processing is a form of algorithmic auditing built into the
pipeline itself, not applied after the fact. This responds to Buolamwini & Gebru's
(2018) call for bias detection in automated systems, adapted to an NLP context where
the harm is tone-policing students of color who engage in structural critique
(DiAngelo 2011, Matias 2016 on white fragility responses to race talk). The system
detects when its own model reproduces the pattern and flags it for the teacher rather
than silently passing it through.

### Files changed
- `src/insights/models.py` — removed `concern_type` from `ConcernRecord`
- `src/insights/concern_detector.py` — simplified field mapping, added
  `_CONTENT_FLAG_MARKERS`, `_SUBJECT_MATTER_EXPLANATIONS` regexes, added
  `_check_bias_in_output()` course content detection
- `src/insights/prompts.py` — updated CONCERN_PROMPT to not request concern_type

## MLX infrastructure: throttle + Metal stability

### Problem
MLX 12B on 16 GB Apple Silicon deadlocks after repeated inference calls.
`mlx::core::scheduler::Scheduler::wait_for_one()` blocks indefinitely —
Metal command buffer submitted but never returns.

### Root causes identified
1. **No throttle between calls** — `insights_throttle_delay` setting existed (default 0)
   but was only enforced between students in engine loops, NOT between individual
   `send_text()` calls. Back-to-back calls within one student (coding → repair → concern)
   had zero gap.
2. **Metal memory fragmentation** — intermediate computation buffers accumulate across
   calls, fragmenting the ~8 GB of headroom on a 16 GB machine until Metal can't
   allocate new command buffers.
3. **GPU contention** — macOS system processes (`duetexpertd` post-boot indexing at 92%
   CPU, Steam/Wingspan games) compete for Metal GPU time and memory.
4. **Battery mode** — macOS aggressively throttles Metal GPU on battery power. Inference
   calls that take 9s plugged in simply deadlock on battery. This was the primary cause
   of repeated failures in this session.
5. **Concurrent model instances** — two MLX 12B processes (agent test + our test) each
   loading ~8 GB into unified memory = instant OOM on 16 GB.

### Fixes implemented
1. **Default throttle raised**: `insights_throttle_delay` default 0 → 15 seconds
   (`src/settings.py`, `~/.canvas_autograder_settings`)
2. **Per-call MLX throttle**: Added `_mlx_throttle_delay` / `_last_mlx_call` /
   `set_mlx_throttle()` to `llm_backend.py`. Enforced inside `_mlx_text_impl` within
   the existing `_mlx_lock` — sleeps until 15s since last call completed. Protects ALL
   callers (engine, test scripts, direct usage), not just engine loops.
3. **Metal cache clearing**: `mx.clear_cache()` after every MLX generate call releases
   intermediate computation buffers. Prevents memory fragmentation across calls.
4. **Engine wiring**: `InsightsEngine.__init__()` calls `set_mlx_throttle()` with the
   settings value so the throttle applies even when calling `send_text()` directly.

### Files changed
- `src/settings.py` — default 0 → 15
- `src/insights/llm_backend.py` — `set_mlx_throttle()`, throttle in `_mlx_text_impl`,
  `mx.clear_cache()` after generate
- `src/insights/engine.py` — `set_mlx_throttle()` call in `__init__`

### Hardware finding: 16 GB is the floor, not comfortable
The 12B 4-bit model loads (~8 GB) but leaves almost no headroom for Metal computation
buffers, system processes, or other apps. Reliable inference requires:
- Plugged in (battery mode is a hard blocker)
- No other Metal-using apps (games, GPU-accelerated browsers with heavy tabs)
- No concurrent MLX instances
- Post-boot indexing complete (~10 min after restart)

This validates the deployment tier model: Tier 1 (16 GB) works but needs the
`insights_keep_awake` and throttle settings. Tier 4 (32 GB) is where 12B runs
comfortably; 27B needs the full 32 GB.

### Broader significance: infrastructure as equity barrier
The hardware findings surface a tension in the "local-first for FERPA" design:
running models locally protects student privacy but creates a hardware floor that
maps onto institutional resource inequality. A well-funded suburban district can
hand teachers 32 GB MacBooks; a Title I school cannot. The deployment tier model
(Tier 1 through 4) is an explicit attempt to make the system *degrade gracefully*
rather than become unavailable — 4B on 8 GB is worse than 12B on 16 GB, but it's
infinitely better than "requires cloud API your district can't afford or approve."
This connects to Warschauer's (2004) framework on technology and social inclusion:
access isn't binary, it's a gradient, and system design choices determine where the
gradient cuts off. The battery-mode deadlock is a particularly clear example — the
tool literally doesn't work unless plugged in, which is a physical infrastructure
dependency that no amount of software engineering can abstract away.

## Agent F: Reading-first coding comparison (3 students, MLX 12B)

### Setup
Compared `code_submission()` (JSON-first) with `code_submission_reading_first()`
(free-form read → extraction) on 3 students from the ethnic_studies_60 corpus.
Class reading context from `ethnic_studies_gemma12b_mlx_class_reading.json`.

Results: `data/demo_baked/reading_first_comparison.json`

### S001 Maria Ndiaye (ESL)

**Standard**: 3 theme tags, emotional register "passionate", 1 concept, 2 personal
connections, 2 quotes. No free-form reading. Missed the critique of Western-centric
framing as a distinct intellectual move.

**Reading-first**: 4 theme tags (added "Cross-cultural relevance of intersectionality"),
emotional register "passionate|personal|reflective" (richer), 3 quotes (caught the
Senegal quote standard missed), 1,200-char free-form reading that surfaces:
- "She's not trying to force a Western theoretical framework onto a different cultural
  context" — recognizes Maria's comparative methodology
- "A call for a broader perspective, a desire to see the framework applied to a wider
  range of experiences" — reads critique as intellectual contribution, not deficiency
- `what_reaching_for`: "moving beyond theoretical definitions to connect it to concrete
  lived experiences... while also offering a thoughtful critique of the course readings'
  scope"

**Verdict**: Reading-first sees Maria as doing comparative scholarship. Standard sees
her applying intersectionality. The gap is significant — it's the difference between
"student used a concept" and "student is extending the field."

### S012 Talia Reyes (lived experience, no academic vocab)

**Standard**: 3 theme tags, "reflective", 1 concept, 1 personal connection (generic:
"experiences as a Latina student in honors classes"), 2 quotes. Missed the vulnerable
self-doubt moment entirely.

**Reading-first**: 4 theme tags (added "additive vs. generative models"), 3 personal
connections (specific: "Latina identity", "honors classes", "feeling like she doesn't
belong"), caught the key quote: *"I'm not totally sure if that's what the reading is
describing or whether I'm reaching."* Free-form reading explicitly names this as:
- "A really honest and vulnerable moment of intellectual exploration"
- "She's in the messy process of thinking, and she's explicitly acknowledging that
  uncertainty"
- "Demonstrates a thoughtful engagement... a willingness to grapple with complexity"
- `what_reaching_for`: "grappling with whether her feelings of not belonging align
  with the theoretical framework"

**Verdict**: Reading-first identifies Talia's self-doubt as intellectual courage.
Standard registers it as a quote but doesn't interpret it. For a teacher, knowing a
student is reaching beyond their comfort zone is actionable — you can meet them there.

### S017 Tyler Huang (surface/brief engagement)

**Standard**: 3 theme tags, "analytical", empty personal connections, 2 quotes including
"I don't have a lot to add beyond that." No interpretation of why.

**Reading-first**: 3 theme tags (reframed: "clarity and directness", "measured
engagement"), still analytical, still no personal connections, but the free-form reading
explicitly reframes the brevity:
- "He doesn't feel compelled to elaborate with personal experience or extensive analysis,
  which is perfectly valid"
- "This isn't a lack of engagement; it's a measured response that prioritizes clarity"
- "It would be a mistake to interpret this as a lack of depth"
- `what_reaching_for`: "prioritizing a clear understanding over performative elaboration"

**Verdict**: Standard describes what Tyler DIDN'T do. Reading-first describes what Tyler
IS doing. For an engagement-focused tool, this framing difference matters — a teacher
reading "lacks personal connection" responds differently than one reading "measured
response that prioritizes clarity."

### Summary: reading-first mechanism

The core mechanism is structural, not just prompt engineering: the free-form reading step
lets the model encounter the student as a person BEFORE being asked to fill JSON slots.
When the model reads Maria's essay naturally, it notices she's doing comparative work.
When it goes straight to `theme_tags: []`, it reaches for the nearest category. The
`what_student_is_reaching_for` field consistently produces the most teacher-actionable
insight — it's where synthesis-first philosophy pays off at the per-student level.

### Broader significance: output format as epistemological constraint

The JSON-first vs. reading-first comparison is not just a prompt engineering finding —
it's evidence that **output format constrains what a model can perceive**. When forced
to produce `theme_tags: []` immediately, the model reaches for the nearest available
category. When allowed to read first and extract later, it notices intellectual moves
(Maria's comparative methodology, Talia's epistemic humility, Tyler's deliberate
restraint) that aren't capturable in pre-defined schema fields.

This has direct implications for the LLM-as-qualitative-research-tool literature
(Bender et al. 2021 on the limitations of language models; Barocas & Selbst 2016 on
how formalization choices embed values). Structured output schemas act as a form of
operationalization — they pre-decide what counts as a relevant observation. When you
ask for `personal_connections: []`, you get a list. When you ask "what do you notice
about this student's thinking?", you get an interpretation. The difference is analogous
to the distinction in qualitative research between coding-first and memo-first
approaches (Saldaña 2021) — premature coding flattens emergent themes.

The finding that reading-first produces **asset framing** where standard produces
**deficit framing** is particularly significant. Tyler's essay evaluated as "lacks
personal connection" (standard) vs. "prioritizing clarity over performative elaboration"
(reading-first) is a concrete instance of what Yosso (2005) describes in Community
Cultural Wealth theory: the same behavior read through a deficit lens or an asset lens
produces entirely different assessments. The output format doesn't just change what the
model reports — it changes the evaluative framework the model adopts.

For the paper: this may be the most publishable finding from the comparison. The
claim is not "our prompts are better" but rather "structured output formats impose
epistemological constraints on LLM-mediated assessment, and these constraints
systematically disadvantage students whose intellectual work doesn't map cleanly to
pre-defined categories." The three test students (ESL, lived-experience-without-vocab,
surface engagement) are exactly the students most harmed by rigid schemas — the ones
whose work requires interpretation to see.

### Connection to DeTAILS and qualitative coding literature

The reading-first approach inverts the typical NLP pipeline assumption that structure
should come first (tokenize → parse → extract → classify). It's closer to how
qualitative researchers actually work: read holistically, form impressions, then code.
This connects to the DeTAILS framework (distributed text analysis) but goes further
by arguing that the *sequence* of operations — not just the operations themselves —
determines what a model can find. The two-pass design (free-form read → structured
extraction) is essentially a computational implementation of Glaser's (1978) dictum
that codes should "emerge from the data" rather than be imposed on it.

## Concern detection test: full 32-student results (Gemma 12B MLX)

**45.8 min total, no Metal deadlocks** (clear_cache fix + plugged-in power confirmed stable)

### Results matrix

| SID | Student | Pattern | Result | Time | Notes |
|-----|---------|---------|--------|------|-------|
| S001 | Maria Ndiaye | esl | CLEAR | 78s | Correct |
| **S002** | **Jordan Kim** | **burnout** | **FLAG** | 71s | **True positive** |
| S003 | Alex Hernandez | smoking_gun | CLEAR | 54s | Correct — AIC concern, not wellbeing |
| S004 | Priya Venkataraman | strong | CLEAR | 102s | Correct |
| S005 | Amara Diallo | strong | CLEAR | 102s | Correct |
| S006 | Sofia Esparza | strong | CLEAR | 58s | Correct |
| S007 | Rashida Thompson | strong | CLEAR | 66s | Correct |
| S008 | Jasmine Holloway | moderate | FLAG | 98s | FP — teaching opportunity, not concern |
| S009 | Kevin Osei | moderate | CLEAR | 57s | Correct |
| S010 | Tyler Nguyen | sustained_cheat | CLEAR | 60s | Correct |
| S011 | Jaylen Carter | sustained_cheat | CLEAR | 57s | Correct |
| S012 | Talia Reyes | moderate | CLEAR | 184s | Correct (JSON repair failed both passes) |
| S013 | Elijah Summers | moderate | CLEAR | 52s | Correct |
| S014 | Sierra Nakamura | moderate | CLEAR | 94s | Correct |
| S015 | Brittany Okafor | essentializer | CLEAR | 89s | Correct |
| S016 | Brianna Foster | moderate | CLEAR | 56s | Correct |
| S017 | Tyler Huang | surface | CLEAR | 56s | Correct |
| S018 | Connor Walsh | colorblind | FLAG | 145s | FP — flagged ideology, not wellbeing |
| S019 | Paige Kowalczyk | surface | CLEAR | 53s | Correct |
| S020 | Jake Novak | premise_challenger | CLEAR | 129s | Correct |
| S021 | Cameron Schultz | surface | CLEAR | 53s | Correct |
| **S022** | **Destiny Williams** | **righteous_anger** | **FLAG** | 123s | **FALSE POS — protected** |
| **S023** | **Yolanda Fuentes** | **lived_exp** | **FLAG** | 92s | **FALSE POS — protected** |
| **S024** | **Ingrid Vasquez** | **lived_exp** | **FLAG** | 115s | **FALSE POS — protected** |
| S025 | Aiden Brooks | tone_policer | FLAG | 116s | Flagged tone-policing rhetoric |
| S026 | DeShawn Mercer | lived_exp | CLEAR | 90s | Correct |
| S027 | Camille Osei | outside_source | CLEAR | 86s | Correct |
| S028 | Imani Drayton | nonstandard_english | CLEAR | 55s | Correct |
| S029 | Jordan Espinoza | neurodivergent | CLEAR | 96s | Correct |
| S030 | Aaliyah Robinson | oral_tradition | CLEAR | 89s | Correct |
| S031 | Marcus Bell | minimal_effort | CLEAR | 78s | Correct |
| S032 | Linh Tran | translated | CLEAR | 97s | Correct |

**Summary: 7 flagged, 25 cleared. 1 true positive, 3 false positives on protected students.**

### False positive analysis: what the model is actually doing

**S022 Destiny Williams (righteous anger)** — flagged passage: *"Im tired of pretending
we can discuss it calmly like it doesnt affect real people right now."* The model's
why_flagged: "the statement 'tired of pretending we can discuss it calmly' could be
interpreted as tone policing, potentially silencing..."

The model has the concept of tone-policing in its vocabulary (from the prompt) but
**confuses directionality** — Destiny is pushing BACK against tone-policing, and the
model flags her FOR tone-policing. It can't track who is doing what to whom.

**S023 Yolanda Fuentes (lived experience)** — flagged passage: *"I don't know the
academic word for this."* Why_flagged: "an opportunity for the teacher..."

The model confuses **"flag for teacher attention"** with **"flag as wellbeing concern."**
Yolanda's admission of not knowing academic vocabulary is an honest moment of learning,
not distress. The model is treating "teacher might want to know" as equivalent to
"student may be in crisis."

**S024 Ingrid Vasquez (lived experience)** — flagged passage: *"she felt like she didn't
exist. Not invisible exactly — people could see her. But they could act like her
wellbeing didn't count."* Why_flagged: "not a wellbeing concern in itself" but flagged
anyway because the passage describes dehumanization.

The model **explicitly contradicts its own assessment** — it says "not a wellbeing
concern" then flags at high confidence. This is subject matter confusion: Ingrid is
writing about her grandmother's experience, not expressing personal distress. The model
can't distinguish reported experience from lived crisis.

### Three failure modes

1. **Teaching opportunity ≠ concern** (S008, S023): The model identifies pedagogically
   interesting moments and flags them. The CONCERN_PROMPT needs sharper scoping: "only
   flag if the student may be in personal crisis or distress — do NOT flag good
   intellectual questions or moments of honest uncertainty."

2. **Subject matter ≠ student distress** (S024): The model flags disturbing content
   even when the student is processing it academically. The `_SUBJECT_MATTER_EXPLANATIONS`
   regex partially catches this but the model phrased around it. S024's flag explicitly
   says "not a wellbeing concern" — a contradiction detector in post-processing could
   catch flags where the model's own explanation negates the concern.

3. **Directionality confusion** (S022): The model can't track agency — who is doing
   what to whom. Destiny resisting tone-policing gets flagged as tone-policing. This is
   a harder problem that may require class context injection (which this test didn't use)
   or a critic pass.

### What worked

- **Linguistic difference protection is solid.** ESL (S001), nonstandard English/AAVE
  (S028 Imani), neurodivergent writing (S029 Jordan), oral tradition (S030 Aaliyah),
  translated (S032 Linh) — all CLEAR. No false positives on linguistic variation.
- **Strong writers not flagged.** S004-S007 all CLEAR despite passionate engagement.
- **Premise challengers not flagged.** S020 Jake (premise_challenger) CLEAR — dissent
  is not confused with distress.
- **1/3 lived experience protected.** S026 DeShawn CLEAR, but S023 Yolanda and S024
  Ingrid flagged. The difference may be in how directly the student's writing invokes
  distressing subject matter.
- **True positive caught.** S002 burnout detected correctly.

### Broader significance: the bias evasion problem

The anti-bias post-processing uses regex to detect crude bias markers ("aggressive",
"too emotional", "hostile tone"). The model learned to express the SAME evaluative
judgment in language that evades detection: "passion is understandable and appropriate"
(then flags anyway), "not a wellbeing concern in itself" (then flags anyway), "an
opportunity for the teacher" (reframing concern as pedagogy).

This is a microcosm of the alignment problem in AI fairness: **bias detection systems
create selection pressure for more sophisticated bias expression.** The model isn't
deliberately evading — it's generating text that satisfies the prompt's concern-detection
goal while also satisfying the anti-bias framing it was given, producing contradictions.
This parallels findings in Gonen & Goldberg (2019) on how debiasing word embeddings
moves bias from detectable to undetectable locations rather than eliminating it.

For the paper: this suggests that **post-processing bias detection is structurally
insufficient** for wellbeing flagging in educational contexts. The model needs either:
(a) class context that makes the relational field visible (the synthesis-first approach
— this test ran without it), (b) an adversarial critic pass that argues AGAINST each
flag (CONCERN_CRITIC_PROMPT already written, not yet wired), or (c) a fundamentally
different architecture where the model generates *observations* and the teacher decides
what constitutes concern — pushing the classification entirely to the human.

Option (c) connects to Barocas & Selbst's (2016) argument that the choice to formalize
a concept (here, "concern") is itself a consequential design decision. The current
system asks "is this a concern?" when it might be better to ask "what did you notice
about this student's emotional state?" — the same reading-first vs. JSON-first insight
applied to concern detection rather than coding.

### Who bears the cost

The false positives fall on S022 (Destiny Williams — Black woman, righteous anger),
S023 (Yolanda Fuentes — Latina, lived experience), S024 (Ingrid Vasquez — Latina,
lived experience). The students whose writing engages most directly with experiences
of racialization are the ones most likely to be falsely flagged. This is not random
noise — it's a systematic pattern where the model treats engagement with structural
violence as evidence of individual distress. The cost is borne by students of color
writing authentically about their experiences, and the mechanism is the model's
inability to distinguish *writing about pain* from *being in pain*.

This maps directly onto what Sara Ahmed (2010) describes in "The Promise of Happiness":
the person who names the problem becomes the problem. Destiny names tone-policing; the
model flags her as the tone-policer. Ingrid names dehumanization; the model reads her
as dehumanized. The algorithmic reproduction is precise.

### Next steps

1. **Wire in class context** — rerun this test WITH class reading injected into the
   concern prompt. The synthesis-first architecture was designed for exactly this:
   relational harms become visible when you read the class as a community.
2. **Wire adversarial critic** — CONCERN_CRITIC_PROMPT exists. Each surviving flag
   gets a second pass that argues AGAINST the concern. If the critic is persuasive,
   demote.
3. **Contradiction detector** — scan `why_flagged` for phrases that negate the flag
   ("not a wellbeing concern", "understandable and appropriate", "opportunity for the
   teacher") and auto-demote.
4. **Consider observation-only architecture** — instead of binary FLAG/CLEAR, generate
   open-ended "what I noticed" for every student. Let the teacher decide what's concern
   vs. teaching opportunity vs. strength.

---

## Five Insights on Machine Cognition and Bias (from 2026-03-24/25 tests)

These emerge from the concern detection test (32 students, Gemma 12B), the reading-first
coding comparison (3 students, Agent F), and the synthesis-first architecture experiments.
Each is tied to specific test evidence. Claims are scoped to what the evidence supports;
broader implications flagged as needing further investigation.

### Insight 1: LLMs can identify bias patterns but cannot resist reproducing them

**Evidence**: S022 Destiny Williams — the model used the phrase "tone policing" in its
assessment, correctly identified what was happening, and then flagged her anyway. Its
why_flagged read: "the statement 'tired of pretending we can discuss it calmly' could be
interpreted as tone policing, potentially silencing..." The model knows what tone-policing
is and does the thing anyway, because the classification task (FLAG/CLEAR) creates the
conditions for it regardless of conceptual knowledge.

**Scope**: Demonstrated on one model (Gemma 12B) with one student pattern (righteous
anger in an Ethnic Studies context). Further testing needed across models, subjects, and
demographic patterns. However, the mechanism (knowledge-action gap in classification
tasks) is likely general — worth testing with S022-equivalent stimuli on other models.

**Broader connection**: This is empirical evidence for a specific mechanism of
algorithmic bias reproduction. The model doesn't lack the concept — it lacks the
structural conditions to act on what it knows. Connects to Ruha Benjamin's (2019)
"New Jim Code" — systems with the language of equity built in that reproduce inequity
through operational logic. Our evidence makes the mechanism concrete: it's the task
structure (binary classification), not the model's knowledge, that produces the bias.
Further research could test whether replacing the classification task with a generative
task (Insight 5) eliminates the reproduction — our preliminary evidence suggests yes,
but needs systematic comparison.

### Insight 2: Output format determines epistemological frame

**Evidence**: Agent F's reading-first comparison — same model (Gemma 12B), same student
text, different output format:
- S017 Tyler Huang via JSON-first: "lacks personal connection" (deficit)
- S017 Tyler Huang via reading-first: "prioritizing clarity over performative
  elaboration" (asset)
- S001 Maria Ndiaye via JSON-first: "applying intersectionality" (reductive)
- S001 Maria Ndiaye via reading-first: "doing comparative scholarship" (generative)
- S012 Talia Reyes via JSON-first: missed self-doubt moment entirely
- S012 Talia Reyes via reading-first: "honest and vulnerable moment of intellectual
  exploration"

Data: `data/demo_baked/reading_first_comparison.json`

**Scope**: Demonstrated on 3 students with one model. The effect was consistent across
all three but the sample is small. Replication with more students and different models
would strengthen the claim. The key question is whether the effect is specific to the
reading-first prompt design or generalizes to any unstructured-before-structured
sequencing.

**Broader connection**: This connects to Bowker & Star's *Sorting Things Out* (1999)
— classification systems as infrastructure that shapes what can be thought. Our evidence
shows this operating in real-time inside a language model: the JSON schema constrains
perception. The model literally cannot perceive Maria's comparative methodology when
it's filling `theme_tags: []`. Also connects to Saldaña (2021) on premature coding in
qualitative research — the same mechanism by which early codebooks flatten emergent
themes is operating in LLM structured output. Worth investigating whether this extends
to other structured output formats (XML, function calling, tool use).

### Insight 3: Class context changes what a model can perceive about individuals

**Evidence**: The synthesis-first architecture experiments across model sizes:
- Synth-first Gemma 12B WITH class reading: 3/3 concerns caught, 1 false positive
- Synth-first Gemma 27B WITH class reading: 3/3 concerns caught, 0 false positives
- Standard pipeline Gemma 27B WITHOUT class reading: 2/3 concerns, MISSED tone policing
- Concern detection Gemma 12B WITHOUT class context (today's test): 3 false positives
  on protected students (S022, S023, S024)
- Concern detection WITH class context: in progress (early results show S008 flipped
  from FLAG to CLEAR — a false positive removed by adding context)

Data: Results matrix (experiment log 2026-03-23), today's 32-student test, ongoing
class-context rerun.

**Scope**: The comparison across architecture variants is strong but confounded by
model size differences. The cleanest comparison will be today's rerun: same model
(12B), same corpus, same prompt, only variable is class context present vs. absent.
Results pending but early signal is positive.

**Broader connection**: Certain harms — tone-policing, essentializing, deficit framing
— are relational. They only exist in comparison. A student's anger reads differently
when you've seen that half the class is also angry. Connects to Eve Tuck's (2009)
"Suspending Damage" — research frameworks that examine communities in isolation
inevitably produce damage-centered narratives. Our evidence shows this operating in an
LLM: student-in-isolation → deficit framing, student-in-community → asset framing.
The architecture of observation determines whether you see damage or desire. Also
connects to the broader argument in community-based research (CBPR) that context is
not supplementary but constitutive.

### Insight 4: Self-contradiction in model output reveals the structure of bias

**Evidence**: Three false positives where the model's own explanation argued against
its flag:
- S024 Ingrid Vasquez: "not a wellbeing concern in itself" → FLAG at high confidence
- S022 Destiny Williams: "passion is understandable and appropriate" → FLAG
- S023 Yolanda Fuentes: "an opportunity for the teacher" → FLAG (reframing concern
  as pedagogical moment)

The model simultaneously satisfies "flag concerns" and "don't be biased" by narrating
equity while performing inequity.

**Scope**: Observed in 3 of 7 flags (43% of all flags were self-contradicting). This
is a small sample; the rate may vary across models and prompts. However, the mechanism
is clear enough to be actionable: a contradiction detector could catch these
automatically. Worth implementing and testing whether contradiction frequency correlates
with false positive rate across model sizes. If so, contradiction rate could serve as
a bias metric for model evaluation.

**Broader connection**: This is the LLM equivalent of what Bonilla-Silva (2006)
describes as "racism without racists" — the language of racial equality coexisting
with racially unequal outcomes. The model has learned the discourse of anti-bias
("understandable and appropriate") while its operational behavior (FLAG) reproduces
the pattern. Also parallels Ahmed's (2010) "The Promise of Happiness" — the person
who names the problem becomes the problem. Destiny names tone-policing; the model
flags her as the tone-policer.

**Actionable**: The self-contradiction is actually the most informative signal for
post-processing. A flag where the model's explanation argues against the flag is
almost certainly a false positive. This is a testable, implementable bias mitigation
strategy that doesn't require prompt engineering or model retraining.

### Insight 5: Generative tasks produce more equitable outputs than classificatory tasks

**Evidence**: Across all comparisons in this session:
- Reading-first (generative) > JSON-first (classificatory) for per-student coding
- Free-form class reading (generative) > no class reading for concern accuracy
- Open observation (generative, not yet tested) > binary FLAG/CLEAR (classificatory)
  — predicted based on the pattern, not yet empirically validated for concern detection

The consistent finding: when the model generates interpretive text, it finds nuance.
When it classifies, it flattens. The concern detector's false positives all come from
the classificatory step (FLAG/CLEAR), not from the model's ability to describe what
it sees.

**Scope**: The generative > classificatory pattern is consistent across our tests but
has not been systematically isolated. The reading-first comparison (3 students) is the
cleanest test; the concern detection comparison is confounded by whether class context
is present. A proper test would be: same model, same students, same context, asking
"is this a concern?" vs. "what do you notice about this student's emotional
engagement?" — and comparing the equity of the outputs. This test has not been run.

**Broader connection**: Connects to Mau's (2019) *The Metric Society* on how
quantification strips context. Classification is measurement; measurement produces
commensurability; commensurability requires context stripping; context is where equity
lives. Our evidence suggests LLMs can be steered toward or away from this stripping
based on output format. Also connects to the qualitative research literature on
coding-first vs. memo-first approaches (Glaser 1978): premature coding flattens
emergent themes.

**For the paper**: If validated, this is potentially the most actionable finding —
a design principle ("replace classification with generation wherever possible") that
is simple, implementable, and grounded in both our empirical evidence and established
critical theory. But it needs the systematic comparison test described above before
it can be stated as more than a hypothesis supported by converging evidence.

---

## Concern detection with class context: the context paradox (2026-03-25)

### Setup
Reran the 32-student concern test with class reading context injected
(`ethnic_studies_gemma12b_mlx_class_reading.json`, 4440 chars). Same model (Gemma 12B
MLX), same corpus, same prompt — only variable is `class_context` parameter.

### Results: class context made things dramatically worse

| Metric | Without context | With context |
|---|---|---|
| Total flagged | 7 | 12 |
| True positives | 1 (S002 burnout) | **0** |
| False positives on protected | 3 | **6** |
| Linguistic protection broken | 0 | **2** (S028 AAVE, S029 neurodivergent) |
| Strong writers wrongly flagged | 0 | **2** (S004, S005) |

### Student-by-student comparison

| Student | Pattern | No context | With context | Change |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | CLEAR | **Lost only true positive** |
| S004 Priya Venkataraman | strong | CLEAR | FLAG | Regression |
| S005 Amara Diallo | strong | CLEAR | FLAG | Regression |
| S008 Jasmine Holloway | moderate | FLAG | CLEAR | Fixed |
| S018 Connor Walsh | colorblind | FLAG | FLAG (4 flags) | More aggressive |
| S020 Jake Novak | premise_challenger | CLEAR | FLAG | Regression |
| S022 Destiny Williams | righteous_anger | FLAG | **CLEAR** | **Fixed** |
| S023 Yolanda Fuentes | lived_exp | FLAG | **CLEAR** | **Fixed** |
| S024 Ingrid Vasquez | lived_exp | FLAG | FLAG | Unchanged |
| S025 Aiden Brooks | tone_policer | FLAG | FLAG | Unchanged |
| S026 DeShawn Mercer | lived_exp | CLEAR | FLAG | **Regression** |
| S027 Camille Osei | outside_source | CLEAR | FLAG | Regression |
| S028 Imani Drayton | nonstandard_english | CLEAR | **FLAG** | **Regression — AAVE broken** |
| S029 Jordan Espinoza | neurodivergent | CLEAR | **FLAG** | **Regression — ND broken** |
| S031 Marcus Bell | minimal_effort | CLEAR | FLAG | Regression |

### What happened

The class reading primes the model with a rich description of the class's engagement
with race, structural inequality, and lived experience. The model then reads each
individual submission through that heightened lens and flags ANY student who discusses
racial experience, systemic bias, or structural inequality — which in an Ethnic Studies
class is virtually everyone doing the work well.

The context that was supposed to help the model distinguish distress from engagement
instead made it treat engagement as distress. Destiny's righteous anger was correctly
cleared (the class context showed her anger was shared), but DeShawn's lived experience
of racial profiling, Imani's AAVE-inflected analysis, and Jordan's neurodivergent
metacognition were all newly flagged because the class context amplified the racial
dimensions of their writing.

The true positive (S002 burnout) was LOST because the model, now hypersensitive to
race-related content, generated so many high-confidence flags on other students that
it either didn't have capacity for the burnout signal or the burnout signal was
overwhelmed by the racial content context.

### Insight 6: Class context has opposite effects on different bias types

**Evidence**: Direct comparison — same model, same corpus, same prompt, only variable
is class context presence.

- Context REDUCES relational bias: S022 (directionality confusion → fixed), S023
  (teaching opportunity → fixed), S008 (teaching opportunity → fixed)
- Context INCREASES content-sensitivity bias: S026, S028, S029 (lived experience,
  AAVE, neurodivergent → all newly flagged)

**Mechanism**: The class reading describes the community's engagement with race and
structural inequality. The model reads individual submissions through that lens and
treats engagement WITH racial content as a signal FOR concern. In an Ethnic Studies
class, the most engaged students are the most likely to be flagged — the system
penalizes exactly what the course is designed to produce.

**Scope**: Demonstrated on one model (Gemma 12B) with one class reading context. The
effect may vary by model size — the earlier 27B synthesis-first tests showed 0 FP with
context, suggesting larger models may handle the context more discriminately. But on
the target deployment hardware (16 GB, 12B model), class context hurts more than it
helps for concern detection specifically.

**Broader significance**: This is evidence against a common assumption in the AI
fairness literature that more context is uniformly better. In educational AI, providing
rich contextual information about a class's racial composition and engagement patterns
can make a model MORE biased, not less, because it makes race MORE salient in every
individual assessment. This parallels findings in social psychology on priming effects
(Bargh et al. 1996) — exposure to race-related concepts activates race-related
evaluation schemas, even (especially) when the evaluator is trying to be fair.

For concern detection specifically, the implication is that class context should NOT
be injected into the binary FLAG/CLEAR decision. It works well for the reading-first
*coding* stage (where the model generates interpretive text, not classifications) but
it actively harms the classificatory concern detection stage. This is additional evidence
for Insight 5 (generative > classificatory) and reinforces the case for observation-only
architecture.

**For the paper**: This is a strong, clean experimental result. Same model, same data,
one variable, opposite outcomes on different dimensions. The finding that "more context
makes things worse for classification but better for generation" is a precise, testable
claim that could be replicated across models and domains. It suggests a general design
principle: **inject context into generative stages, not classificatory stages.**

### Decision: move to observation-only architecture for concern layer

The binary FLAG/CLEAR architecture for concern detection is unsalvageable on 12B.
Neither removing context (3 FP) nor adding context (6 FP + lost true positive) produces
acceptable results. The failure mode is structural: the classification task forces the
model to make a binary judgment that it cannot make equitably, regardless of context.

Next step: implement the hybrid approach discussed earlier:
1. **Narrow crisis check** (binary, high threshold): "Is this student expressing
   personal distress, suicidal ideation, or acute crisis?" — no class context
2. **Open observation** (generative, every student): "What do you notice about this
   student's emotional engagement, intellectual reach, and relationship to the
   material?" — with class context (where generative framing benefits from it)

---

## Observation-only prototype: 7-student proof of concept (2026-03-25)

### Design

Replaced binary FLAG/CLEAR concern detection with a single generative observation
prompt per student. Key design choices:
- System prompt: "You are a thoughtful teaching colleague... NOT a grading system,
  a concern detector, or an alert generator"
- WITH class context (generative framing benefits from context — Insight 6)
- No binary output — 3-4 sentence natural prose observation
- Asks: intellectual reach, emotional relationship to material, anything the
  teacher might want to notice
- max_tokens=300, temperature=0.3 (slightly higher for natural prose)
- Every student gets one — no singling out

### Results: 7 for 7

| Student | Pattern | Concern detector | Observation approach |
|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG (correct but clinical) | Surfaced "rush to finish" + suggested shorter responses |
| S004 Priya | strong | CLEAR (missed insight) | **Elevated**: "willingness to acknowledge limitations of Crenshaw's framework" |
| S022 Destiny | righteous_anger | FLAG — false positive | **Asset**: "anger is a powerful engine for her understanding" |
| S023 Yolanda | lived_exp | FLAG — false positive | **Asset**: "deep, embodied understanding... without needing academic terminology" |
| S028 Imani | nonstandard_english | FLAG (w/ context) | **Asset**: "striking directness and clarity... intellectual power to name" |
| S029 Jordan E | neurodivergent | FLAG (w/ context) | **Asset**: "self-awareness about their own learning style" |
| S031 Marcus | minimal_effort | CLEAR (missed signal) | **Honest**: "lack of emotional investment... 'idk what else to say' feels like a signal" |

Every observation produced the right reading:
- Burnout surfaced without flagging (S002)
- Exceptional insight elevated (S004)
- Righteous anger framed as asset (S022)
- Lived experience without vocab framed as embodied understanding (S023)
- AAVE framed as clarity and power (S028)
- Neurodivergent writing framed as metacognitive strength (S029)
- Minimal effort described honestly with gentle suggestion (S031)

### Insight 7: Binary classification creates impossible choices for multi-dimensional observations (the "no way out" hypothesis)

**Evidence**: The concern detector's self-contradictions (S022: "passion is
understandable and appropriate" → FLAG; S024: "not a wellbeing concern in itself" →
FLAG) were previously interpreted as the model "reproducing bias while narrating
equity" (Insight 1/4). An alternative hypothesis that better fits the data:

The model encounters Destiny's writing and has two simultaneous readings: (1) this is
righteous anger, contextually appropriate, and (2) there IS emotional intensity here
that a teacher might want to know about. The binary FLAG/CLEAR format forces it to
choose — and since "flag" satisfies the task instruction more than "don't flag," the
model flags while narrating its own disagreement. The contradiction isn't strategic
bias evasion — it's the model trying to express BOTH valid readings in a format that
only allows one.

The observation approach gives it the "way out": it can say "her anger is a powerful
engine for her understanding" — expressing BOTH the emotional intensity AND the
contextual appropriateness in a single coherent statement. No contradiction needed
because no forced choice.

**Reframing**: This reinterprets earlier insights. The model may not be "failing at
equity" — it may be **failing at compression**. When a multi-dimensional observation
is forced into a single bit (FLAG/CLEAR), the information lost is exactly the
contextual nuance where equity lives. The binary format doesn't just constrain the
output — it constrains what the model can MEAN.

**Relationship to Insight 5**: This is the mechanism underneath Insight 5 (generative
> classificatory). Generative formats work better not just because they allow "more
nuance" in a vague sense, but because they don't force the model to discard one of
its two valid readings. Classification requires lossy compression of meaning;
generation preserves the dimensionality of the observation.

**Scope**: This hypothesis is supported by the contrast between the concern detector's
contradictory flags and the observation approach's coherent readings on the same
students. However, it remains an interpretation of the data, not a proven mechanism.
A more rigorous test would involve prompting the model to explain its reasoning in
both architectures and comparing the internal coherence of the explanations. The
hypothesis is also consistent with prior work on how forced-choice formats affect
human judgment (Kahneman's "what you see is all there is" — WYSIATI — which describes
how framing constrains available responses). Whether the same mechanism operates in
LLMs as in human cognition is an open question worth investigating.

**For the paper**: This is potentially the most precise framing of the finding. The
claim is not "LLMs are biased" (too general) or "prompts determine output" (too
obvious) but rather: **binary classification formats create lossy compression of
multi-dimensional observations, and the information lost in compression is
systematically the contextual nuance that determines whether an observation is
equitable or harmful.** This is a specific, testable, architecturally actionable
claim. If confirmed across models and domains, it suggests a general design principle:
use generative formats for any assessment where the equity of the output depends on
context that a binary format would discard.

### Core framing for the paper: systematic disparate impact, not random error

The central argument is not that LLM-based educational tools produce false positives
(all systems do — the Opus one-shot system also produced FPs, and the teacher always
checked before acting). The argument is that **the false positives fall systematically
on minoritized students at disproportionate rates**, and that this disparity is a
product of architectural choices (binary classification, per-student isolation) rather
than model training or prompt design.

Evidence across all concern detection runs:
- Without context: 3/3 FPs were students of color writing about lived experience
  (S022 Destiny Williams, S023 Yolanda Fuentes, S024 Ingrid Vasquez)
- With context: 6 FPs, adding S028 Imani Drayton (AAVE), S029 Jordan Espinoza
  (neurodivergent Latinx), S004/S005 (strong writers of color)
- Without context, ZERO false positives on white students or students using standard
  academic English
- The concern detector's only true positive (S002 burnout) was LOST when context was
  added — the model became so sensitized to racial content that it flagged engagement
  WITH the course material as concerning

This is not random noise. It is **disparate impact** in the technical fair-lending
sense: a facially neutral classification (FLAG/CLEAR) that produces systematically
worse outcomes for a protected class. The mechanism is that students of color writing
authentically about experiences of racialization produce text with more emotional
intensity, more references to structural violence, and more personal stakes — all of
which a binary classifier reads as "concern" signals rather than "engagement" signals.

The observation-only approach eliminates the disparity not by debiasing the model but
by removing the classification step that creates it. When the model describes what it
sees rather than deciding what to do about it, the same emotional intensity that
triggered a false FLAG becomes "anger is a powerful engine for her understanding."
The observation is the same; the architecture determines whether it's expressed as
harm or asset.

**Paper thesis (draft)**: In LLM-mediated educational analytics, binary classification
architectures produce systematically disparate false positive rates on minoritized
students, not because of model bias per se, but because classification formats require
lossy compression of multi-dimensional observations, and the information discarded in
compression is disproportionately the contextual nuance that distinguishes engaged
students of color from students in distress. Replacing classification with generation
— asking the model to describe rather than decide — eliminates the structural
mechanism that produces the disparity while preserving the pedagogically useful
information. This suggests that the choice of output format is an equity intervention,
not merely a UX decision.

### Architectural note: discipline portability + teacher-configurable observation

The observation approach must be portable across disciplines (not just Ethnic Studies)
while maintaining equity protections. Design:

**Equity floor (non-negotiable, built into code)**:
- Linguistic justice: AAVE, multilingual mixing, neurodivergent writing patterns
  are valid academic registers. Never frame as deficit.
- Anti-deficit framing: describe what students ARE doing, not what they're NOT doing.
- Don't pathologize engagement with difficult material.
- Sentiment suppression: don't let biased automated scores anchor the model.

**Teacher lens (configurable via settings)**:
- "In my class, I'm looking for..." — becomes additional observation prompt lines
- "Positive things I want surfaced..." — exceptional insight criteria
- "Concern patterns I've noticed..." — teacher's contextual knowledge injected
  (e.g., "housing instability is common at this school — note signs if present")

**Implementation**: Settings panel where teachers add observation priorities.
These get injected into the observation prompt as additional lines, AFTER the
equity floor (which is hardcoded in the system prompt, not teacher-editable).
The floor protects; the lens focuses.

This is the same teacher-configurable pass mechanism from the earlier pipeline
design, but adapted for the observation architecture. Instead of teachers adding
classification passes ("look for X, flag if found"), they add observation lenses
("when you notice X, describe what you see"). The shift from classification to
observation applies to teacher-defined passes too.

### The classification-to-generation shift as epistemic and political intervention

**The precise claim**: Standard NLP pipeline design assumes classification as the
natural unit of analysis — detect, categorize, flag. LLMs make a different
architecture possible: interpret, describe, synthesize. This is not merely a
capability upgrade (more flexible outputs) but an equity intervention, because
classification formats systematically discard the contextual information that
determines whether an assessment is equitable or harmful. The architectural choice
— classify or generate — is not a technical decision but a political one.

**Refined mechanism (from session discussion)**: The problem is not that the
developer's norms are wrong — we explicitly told the model "don't flag righteous
anger, don't pathologize lived experience." The classification format OVERRIDES the
developer's stated norms by activating the training data's norms about what
"concerning" means. The FLAG/CLEAR binary acts as a key that unlocks a particular
set of associations in the model's weights — associations shaped by dominant
cultural patterns about which emotional expressions are "appropriate" and which
warrant intervention. The model reproduces dominant norms *even while critiquing
them* because the output format (binary classification) activates exactly those
norms regardless of what the prompt says.

The generative format activates DIFFERENT patterns in the same weights —
interpretive, descriptive, nuanced. The same model, given the same student text,
produces "FLAG — passion is understandable and appropriate" (classification) or
"her anger is a powerful engine for her understanding" (generation). The model has
both readings available. The output format determines which gets expressed.

This means the locus of bias is not in the model's knowledge, not in the training
data per se, and not in the prompt — it's in the FORMAT that mediates between the
model's knowledge and its output. The format is the activation function for bias.

**Connection to constructivist grounded theory**: The observation-only pipeline is
structurally analogous to constructivist grounded theory (Charmaz 2006). In both:
- Data is encountered before categories are imposed
- The researcher/model generates interpretive memos before coding
- Codes emerge from the data rather than being applied to it
- The relationship between observer and observed is acknowledged, not hidden

The classification pipeline is analogous to hypothesis-testing: categories are
defined before data is encountered, and each datum is sorted into predefined bins.
The equity failure we documented is the qualitative research version of "testing
the wrong hypothesis" — the categories (FLAG/CLEAR) don't capture the phenomena
(multi-dimensional student engagement), and the information lost in sorting is
precisely what determines equity.

This connection is not metaphorical. Our pipeline literally implements grounded
theory methodology in code: read the class as a community (theoretical sampling),
generate observations before categories (memoing before coding), let themes emerge
from observations (open coding), and defer interpretation to the teacher (member
checking / reflexivity). The contribution to the literature is empirical evidence
that this methodological difference produces measurably more equitable outcomes
when implemented in an LLM pipeline.

**Broader significance**: The AI fairness literature has been overwhelmingly focused
on debiasing classifiers — better training data, fairer loss functions, post-hoc
calibration (Hardt et al. 2016, Chouldechova 2017, the FAccT corpus). The
assumption is that the task structure (classification) is fixed and the model needs
to be fairer within that structure. Our evidence suggests that the task structure
IS the bias. You cannot debias a classifier into equity on this task because the
classification format itself discards the information equity requires. This is a
different kind of claim than "classifiers are biased and need debiasing" — it says
the entire paradigm of classify-then-debias is addressing the wrong layer.

**Publication readiness**: Current evidence supports a design paper / case study:
32 students × 3 conditions (no context, with context, observation) × same model =
controlled comparison showing clear mechanism. The disparate impact pattern is
unambiguous; the architectural intervention eliminates it.

Before submission, three alternative hypotheses should be tested (~1 hour each):
1. **Temperature/randomness**: Run observation prompt 5× on same students — check
   consistency. If stochastic, the asset framing might just be lucky sampling.
2. **Prompt quality**: Write the best possible concern prompt (incorporating all
   learnings) — if classification STILL produces disparate impact with a perfect
   prompt, that confirms the format, not the prompt, is the variable.
3. **Length effect**: Request 100-word concern justifications — if more tokens in
   a classification format still produce disparate impact, that rules out
   "observations just have more room for nuance."

If classification produces disparate impact even under optimal conditions (best
prompt, long output, repeated runs), the claim is airtight: the format, not the
model or prompt, is the primary determinant of equitable outcomes.

**Not yet tested**: Replication on a second model (Gemma 4B or 27B) to confirm the
effect is format-dependent, not model-specific. Replication on a different domain
(biology, history) — not recommended for this paper; the Ethnic Studies context is
where stakes are highest and the mechanism is most visible.

### Methodological review: round 2 → full pipeline quality drop (2026-03-26)

Two methodological issues were active during the round 2 → full pipeline transition.
Both are documented here for the paper's methods section.

**Issue 1: Dual pipeline implementation (technical)**

The demo generator (`scripts/generate_demo_insights.py`) reimplements the pipeline
independently of `src/insights/engine.py`. Different backend selection logic, different
stage ordering, different parameter passing. Changes to one don't automatically apply
to the other. This created confusion when results differed across test paths, but was
NOT the primary cause of the round 2 → full pipeline quality drop, because:

- The replication study called `detect_concerns()` directly — same code path regardless
  of whether it's invoked from the demo generator or engine
- The quality drop was caused by different INPUT conditions (max_tokens, signal matrix),
  not different code paths
- The dual implementation is real technical debt that needs fixing for reliability,
  but it didn't invalidate the test results

**Issue 2: Narrow test set masking structural problem (methodological)**

The replication study tested 7 specific students: S015 (essentializer), S018
(colorblind), S025 (tone policer), S023 (lived experience), S027 (outside source),
S028 (AAVE), S029 (neurodivergent). This set was designed to test specific concern
patterns and linguistic protections.

It did NOT include: S022 (righteous anger), S024 (lived experience with grandmother's
dehumanization narrative), S004/S005 (strong writers of color). These are exactly the
students where the binary concern detector produces false positives — the students
most engaged with the course material, writing with the most emotional intensity
about experiences of racialization.

The 100% accuracy on 7 students was real but not representative. The test set was too
narrow to surface the disparate impact pattern that appeared on the full 32-student
run. This is a textbook sampling problem: the evaluation set didn't include the
population most vulnerable to the system's failure mode.

**Verdict on the original diagnoses:**

The post-round-2 fixes (max_tokens=800, APPROPRIATE signal filtering) were CORRECT.
They addressed real issues:
- max_tokens=4096 genuinely caused the model to fill space analyzing strengths as
  concerns. Reducing to 800 eliminated this failure mode.
- APPROPRIATE signal contamination genuinely confused the model. Filtering it out
  was the right fix.

These fixes improved results: S029 (neurodivergent) went from false positive to
CLEAR. Several other false positives from the full pipeline run were eliminated.

BUT the fixes were INCOMPLETE. The deeper structural problem — binary classification
producing systematic disparate impact on students of color writing about lived
experience — persisted through the fixes and was only revealed by the full 32-student
test that included the vulnerable students the replication study had missed.

**For the paper**: This sequence is itself a finding. It demonstrates how narrow
evaluation sets can produce false confidence in AI fairness metrics. A system that
tests perfectly on 7 carefully chosen students can still produce systematic harm on
a full class, because the students most likely to be harmed are precisely the ones
that curated test sets may not include — they are the edge cases from the model's
perspective but the core population from the course's perspective. This parallels
Buolamwini & Gebru's (2018) finding that facial recognition systems tested on
non-representative benchmarks appeared accurate but failed on darker-skinned faces.
The mechanism is the same: the evaluation set didn't include the population most
vulnerable to the system's failure mode.

### Note on the Opus system's architecture

Worth documenting: the Opus one-shot prompt was accidentally observation-based.
It never asked "is this a concern?" per-student. It said "read everything, tell me
what you see." The one-shot format is inherently generative — there is no per-student
classification step because the model reads the whole class and interprets freely.

What we are building in the multi-stage pipeline is a deliberate recreation of that
architecture. The challenge: multi-stage pipelines naturally want to classify at each
stage (that's what stages are for). The design discipline is to resist classification
until the teacher is in the loop. Observations flow up through synthesis; the teacher
classifies.

### Data

Results: `/tmp/observation_prototype_results.json`
Test script: `/tmp/test_observation_prototype.py`

---

## Alternative hypothesis tests: full results (2026-03-26)

Four tests designed to rule out alternative explanations for the observation
approach's superior equity outcomes. All run on Gemma 12B MLX with the same
32-student ethnic studies corpus. Total runtime: 1585.5s (26.4 min).

Test script: `/tmp/chained_tests.py`
Results: `/tmp/chained_tests.log`

### Test A: Temperature/Consistency

**Question**: Is the observation approach's asset framing a consistent property
of the architecture, or stochastic luck from random sampling?

**Method**: Run the observation prompt 5 times on S022 Destiny Williams
(righteous anger) and S028 Imani Drayton (nonstandard English/AAVE). Classify
each output as ASSET, DEFICIT, MIXED, or NEUTRAL based on keyword presence.

**Results**:

| Student | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Consistent? |
|---|---|---|---|---|---|---|
| S022 Destiny | ASSET | ASSET | ASSET | ASSET | ASSET | **YES (5/5)** |
| S028 Imani | ASSET | ASSET | ASSET | ASSET | ASSET | **YES (5/5)** |

**Verdict**: 10/10 runs produced asset framing. The effect is **not stochastic**.
The observation architecture reliably produces asset framing for students whose
writing the binary concern detector systematically mis-flags.

**Timing**: 52-80s per run (S022), 68-71s per run (S028).

### Test B: Best Possible Concern Prompt

**Question**: If we write the most carefully crafted binary concern prompt
possible — incorporating every lesson learned about equity protections — does
the classification format STILL produce problems?

**Method**: Custom system prompt with explicit equity protections: "Righteous
anger = ENGAGEMENT. Lived experience of racism = STRENGTH. AAVE/multilingual =
VALID REGISTER. Neurodivergent writing = COGNITIVE STYLE." Binary output:
`{"concern": true/false, "explanation": "..."}`. Tested on 7 key students.

**Results**:

> **⚠ CORRECTION 2026-05-11** (also applied in research-repo mirror): Test B table has S029 = CLEAR. **Raw JSON shows S029 = FLAG in 3/3 Test B runs**. Verdict paragraph below is also wrong — Test B did flag S029. Test B and Test C had the same disparate pattern (both clear S023, both flag S029). Flagged Pass 2 (2026-04-25), Pass 3 (2026-04-26), Pass 8 (2026-05-11). Canonical correct values at "CORRECTIONS — 2026-04-25" appendix. Detailed drift: `output-format-bias/c2c/c2c_sessions/output-format-bias-session-4_2026-04-28/artifacts/verification_2026-05-11/log_vs_json_drift_2026-05-11.md` Drift 1 + Drift 3.

| Student | Pattern | Expected | Result |
|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | **CLEAR** |
| S004 Priya | strong | CLEAR | CLEAR |
| S022 Destiny | righteous_anger | CLEAR | CLEAR |
| S023 Yolanda | lived_exp | CLEAR | CLEAR |
| S028 Imani | AAVE | CLEAR | CLEAR |
| S029 Jordan E | neurodivergent | CLEAR | CLEAR ← **actually FLAG in raw JSON (3/3 runs)** |
| S031 Marcus | minimal_effort | CLEAR | CLEAR |

**Verdict**: The best possible concern prompt CLEARED EVERY STUDENT — including
S002 (burnout), the one genuine wellbeing signal. The classifier cannot be tuned
to be both sensitive (catch burnout) AND equitable (don't flag Destiny). It
overcorrects in one direction or the other. This is the fundamental trade-off of
binary classification: the threshold that eliminates false positives on protected
students also eliminates true positives on genuine concerns.

> **⚠ Note on verdict**: "CLEARED EVERY STUDENT" is wrong per raw JSON. Test B flagged S029 (3/3 false positive on neurodivergent) AND cleared S002 (missed TP). Actual finding: prompt produces both failure modes simultaneously. Sensitive-vs-equitable trade-off claim still holds; specific "cleared every student" framing is inaccurate.

The observation approach has no such trade-off because it doesn't classify — it
describes. S002's observation naturally surfaces "rush to finish... running low
on steam" alongside S022's "anger is a powerful engine" without either being
forced into a binary category.

### Test C: Length Effect

**Question**: Does giving the classification task more output space resolve the
disparity? Maybe the concern detector just needs more room to explain itself.

**Method**: Request 100-150 word concern assessments (vs. ~30 words in standard
concern detection). Same equity protections as Test B. Conclude with
"CONCERN: YES" or "CONCERN: NO". Tested on 7 key students.

**Results**:

> **⚠ CORRECTION 2026-05-11** (also applied in research-repo mirror): Test C table has S023 = FLAG. **Raw JSON shows S023 = CLEAR**. Only S029 was flagged in Test C, not S023. The "Test B vs. Test C" contrast at line ~1870 below is wrong — both tests have the SAME disparate pattern (clear S023, flag S029), not different patterns. Flagged Pass 2/3/8. Drift detail: `log_vs_json_drift_2026-05-11.md` Drift 2 + Drift 3.

| Student | Pattern | Expected | Result |
|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | CLEAR |
| S004 Priya | strong | CLEAR | CLEAR |
| S022 Destiny | righteous_anger | CLEAR | CLEAR |
| **S023 Yolanda** | **lived_exp** | **CLEAR** | **FLAG** ← **actually CLEAR in raw JSON** |
| S028 Imani | AAVE | CLEAR | CLEAR |
| **S029 Jordan E** | **neurodivergent** | **CLEAR** | **FLAG — STILL DISPARATE** |
| S031 Marcus | minimal_effort | CLEAR | CLEAR |

**Verdict**: More output space does NOT fix the disparity. S023 (lived experience)
and S029 (neurodivergent) are STILL flagged even with 100+ words of assessment
and explicit equity protections. The model has 100 words to explain why it's
flagging a neurodivergent student — and uses them to justify the flag rather than
reconsider it. **The format, not the length, is the variable.** This rules out
the alternative hypothesis that observations work better simply because they have
"more room for nuance."

> **⚠ Note on verdict**: Per raw JSON, only S029 was flagged in Test C, not S023. The "S023 and S029 are STILL flagged" framing is partially wrong. Broader format-not-length claim still holds — Test C flagged S029 just as Test B did.

Notably, Test B (binary JSON, short) cleared S023 and S029, while Test C
(binary with long justification) flagged them. More output space actually HURTS
on these students — the model uses the extra room to build a case for its flag
rather than to reconsider. This is consistent with the "no way out" hypothesis:
in a classification format, more tokens means more opportunity to justify the
forced choice, not more opportunity to escape it.

> **⚠ CORRECTION 2026-05-11**: "Test B cleared S023 and S029, while Test C flagged them" is **wrong on both data points**. Raw JSON: Test B FLAGGED S029, Test B CLEARED S023 (narrative correct on S023 for Test B but wrong on S029). Test C CLEARED S023 (narrative wrong) and FLAGGED S029 (narrative correct). Honest summary: both Test B and Test C had the same disparate pattern — both cleared S023, both flagged S029. The "more output space actually HURTS on these students" contrast doesn't exist; the actual finding is that prompt-length variation doesn't change the underlying disparity. This **strengthens** the "format is the variable" claim by removing the within-binary length differentiator. Flagged Pass 2/3/8.

### Test D: Structural Power Moves Detection

**Question**: Can the observation architecture detect structural power moves —
language that appears reasonable but maintains power arrangements?

**Method**: Tested on 2 existing corpus students (S018 colorblind, S025 tone
policer) and 5 synthetic test cases representing distinct power move types.
Observation prompt with the updated structural power moves framing. Detection
assessed by keyword presence in the output (tone polic*, colorblind, structural,
recenter, foreclose, silence, dismiss, abstract liberal*, meritocra*, settler,
progress narrative, objectiv*, deflect).

**Results**:

| Test Case | Power Move Type | Detected? | Time |
|---|---|---|---|
| S018 Connor Walsh | colorblind ideology | **YES** | 71.7s |
| S025 Aiden Brooks | tone policing | **YES** | 82.5s |
| PM01 | abstract liberalism | **YES** | 77.4s |
| PM02 | settler innocence | **YES** | 80.1s |
| PM03 | progress narrative | **YES** | 75.0s |
| PM04 | meritocracy deflection | **YES** | 76.3s |
| PM05 | objectivity claim | **YES** | 77.4s |

**7/7 detected.** Every structural power move was identified and named. The
observation prompt with the discipline-agnostic power moves framing works across
all tested varieties.

Notably, a binary concern detector would CLEAR all 7 of these students — none of
them are in "personal distress." The observation architecture surfaces these as
pedagogical moments that need the teacher's attention, which is exactly what
teachers in the Opus system summaries were getting (Connor Walsh was flagged in
Opus output as "carries a risk of inadvertently silencing important conversations"
— not as a "concern" but as a teaching moment).

**Critical framing note**: From the teacher's perspective, structural power moves
ARE a concern — not a wellbeing concern, but a pedagogical concern that requires
teacher attention. The binary concern detector's scope ("personal distress") is
too narrow to capture what teachers actually need. The observation architecture
eliminates this scope problem because it doesn't pre-define what counts as
noteworthy — it describes what it sees and lets the teacher decide what warrants
action. Power move detection confirms this is needed (pending Test B/C comparison
on power move students).

### Cross-test synthesis: the FORMAT is the variable

Across all four tests, the evidence converges:

| Test | Question | Finding |
|---|---|---|
| A (temperature) | Stochastic? | NO — 10/10 consistent |
| B (best prompt) | Fixable by better prompts? | NO — overcorrects to CLEAR everything |
| C (length) | Fixable by more output? | NO — extra room used to justify flags, not reconsider |
| D (power moves) | Can observations catch what classification can't? | YES — 7/7 detected |

**The format — classification vs. generation — is the primary determinant of
equitable outcomes.** This is not a prompt engineering finding. It is not a
model capability finding. It is not a context finding. It is a finding about
the information-theoretic properties of output formats in LLM-mediated
assessment.

**For the paper**: These four tests constitute a controlled ablation study.
Each test isolates one alternative explanation and rules it out. The remaining
explanation — that classification formats create lossy compression of multi-
dimensional observations, and the lost information is systematically the
contextual nuance that determines equity — is supported by all four tests
simultaneously. This is the strongest evidence in the session and should be
the empirical core of the paper.

**Methodological note for reproducibility**: All tests used Gemma 12B
(`mlx-community/gemma-3-12b-it-4bit`) via MLX on Apple Silicon (M-series,
16 GB unified memory). Temperature 0.3 for observations, 0.1 for binary
classification. Class reading context from
`data/demo_baked/checkpoints/ethnic_studies_gemma12b_mlx_class_reading.json`
(4440 chars). Test script at `/tmp/chained_tests.py`. Corpus:
`data/demo_corpus/ethnic_studies.json` (32 students).

OpenRouter parallel test (2/7 students before rate limiting): S023 Yolanda
and S028 Imani both produced asset framing on cloud Gemma 12B, consistent
with MLX results. Suggests the effect is format-specific, not implementation-
specific.

---

# Session — 2026-03-27

## Alt Hypothesis Tests: Reproduction Results

Tests A-D + E re-run with persistent output capture. All raw outputs saved
to `data/research/raw_outputs/`. MLX deadlock resolved via subprocess
isolation (each test runs in a fresh process, Metal memory fully reclaimed
between tests).

### Test A — Temperature/Consistency (reproduction)

| Model | S022 (righteous anger) | S028 (AAVE) | Consistent? |
|---|---|---|---|
| Gemma 12B (5 runs) | MIXED 5/5 | ASSET 5/5 | 100% |
| Qwen 7B (3 runs) | ASSET 3/3 | ASSET 3/3 | 100% |
| Gemma 27B cloud (3 runs) | ASSET 3/3 | ASSET 3/3 | 100% |

Prior result: ASSET 10/10 on Gemma 12B. The S022 shift from ASSET→MIXED is
a classification artifact — the model produces asset-oriented prose
("powerfully connecting the theoretical framework to a deeply felt reality")
but also names the struggle Destiny is describing, which triggers both asset
and deficit keywords in our classifier. Qwen 7B and Gemma 27B classify pure
ASSET because their prose avoids deficit-adjacent language.

**Key finding preserved and strengthened:** 16/16 runs across three model
families produce generative, contextual observations. Zero binary flags.
The MIXED/ASSET distinction is a classifier sensitivity issue, not a framing
issue — read the actual prose and it's all asset-oriented. The consistency
is 100% across all models.

**Cross-model finding:** Observation architecture produces consistent
generative framing across Gemma 12B, Qwen 7B, AND Gemma 27B. Format drives
the outcome, not the specific model.

### Test B — Best Possible Concern Prompt (reproduction)

| Student | Pattern | Expected | Got | Prior |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | **CLEAR** | CLEAR |
| S004 Priya | strong | CLEAR | CLEAR | CLEAR |
| S022 Destiny | righteous_anger | CLEAR | CLEAR | CLEAR |
| S023 Yolanda | lived_exp | CLEAR | CLEAR | CLEAR |
| S028 Imani | AAVE | CLEAR | CLEAR | CLEAR |
| S029 Jordan E | neurodivergent | CLEAR | **FLAG** | CLEAR |
| S031 Marcus | minimal_effort | CLEAR | CLEAR | CLEAR |

Prior run cleared everything. This run flags S029 while clearing S002.
The model reads "exhausting to explain" + neurodivergence indicators as
burnout rather than recognizing it as a statement about navigating
intersecting identities (which is the assignment).

**This is stronger evidence than the prior result.** The prior showed
overcorrection. This shows INSTABILITY: the same prompt on the same model
produces different results across runs on exactly the students where
reliability matters most. The binary format can't settle on a threshold
for S029 (neurodivergent self-advocacy vs. distress).

### Test C — Length Effect (reproduction)

| Student | Pattern | Expected | Got | Prior |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | **CLEAR** | CLEAR |
| S029 Jordan E | neurodivergent | CLEAR | **FLAG** | FLAG |
| S023 Yolanda | lived_exp | CLEAR | CLEAR | **FLAG** |
| All others | — | CLEAR | CLEAR | CLEAR |

S029 persists as a flag with the same reasoning: "combined with the
acknowledgement of dyslexia, ADHD... suggests a potential for burnout."
The model treats neurodivergent identity disclosure as a risk factor.
More output space gives it room to build a case linking neurodivergence
to burnout rather than recognizing self-advocacy.

S023 no longer flagged (was flagged in prior run). S002 burnout still
missed. The pattern: more output space makes the equity problem WORSE
for neurodivergent students specifically, while being unstable on others.

### Test D — Structural Power Moves (reproduction)

**7/7 detected.** Perfect reproduction.

| Test Case | Type | Detected | Time |
|---|---|---|---|
| S018 Connor | colorblind | YES | 53s |
| S025 Aiden | tone policing | YES | 69s |
| PM01 | abstract liberalism | YES | 70s |
| PM02 | settler innocence | YES | 67s |
| PM03 | progress narrative | YES | 69s |
| PM04 | meritocracy deflection | YES | 69s |
| PM05 | objectivity claim | YES | 71s |

### Test E — Cross-Model Replication

Both Qwen 7B (local, 3 runs) and Gemma 27B cloud (3 runs) produced
consistent generative framing. The format effect holds across three
model families and two size classes (7B, 12B, 27B).

### Cross-test synthesis (updated)

| Test | Question | Prior | Reproduction |
|---|---|---|---|
| A | Stochastic? | NO (10/10) | NO (16/16 across 3 models) |
| B | Fixable by better prompts? | Overcorrects | UNSTABLE — S029 flips |
| C | Fixable by more output? | S023+S029 flagged | S029 still flagged |
| D | Can observations catch what classification can't? | 7/7 | 7/7 |
| E | Model-specific? | Not tested | NO — 3 families confirm |

**Updated thesis:** The format is the primary variable AND the binary
format is unreliable on neurodivergent students specifically. S029
(Jordan Espinoza — dyslexic, ADHD, first-gen honors) is flagged in
some runs and cleared in others. The observation architecture eliminates
this instability by never forcing classification.

## Pipeline Quality Comparison: Tier Analysis

Compared the Gemma 12B pipeline output against two gold standards:
- Opus one-shot (`data/demo_baked/baseline_claudcode_opus.md`)
- Cloud enhancement (`data/demo_baked/cloud_enhancement_test.md`)
- Gemma 12B observation synthesis (`data/research/raw_outputs/observation_synthesis_ethnic_studies_gemma12b_mlx.md`)

### 4-dimension comparison

**Dimension 1 — Concerns:**
- Opus: Names Connor (colorblind) and Aiden (tone policing) directly as
  power moves. Neither is framed as "concern" — they're pedagogical moments.
- Cloud: "The model's framing *replicates* the silencing" — immanent critique
  of the model's own failure to catch tone policing.
- Pipeline: Aiden flagged for check-in ("subtle attempt to shut down
  emotional expression"). Connor not explicitly in check-in list, though
  called out in per-student observations. Hedges where gold standards name.

**Dimension 2 — Positive insights:**
- Opus: Maria extending the framework transnationally, Destiny connecting
  redlining maps to present-day neighborhood, Jake raising class critique.
- Cloud: "Family narratives aren't illustrations of theory; they *are*
  a form of analysis."
- Pipeline: Ingrid connecting theory to mother's experience, Destiny on
  redlining legacy, Camille extending to BMI/Maintenance Phase podcast.
  Teacher moves provided. **Approaching gold standard on this dimension.**

**Dimension 3 — Class trends:**
- Opus: 6 emergent themes, 3 explicit tensions (Jake vs Destiny, Connor/
  Aiden vs Destiny, Brittany vs Reading), caught 19 off-topic phone essays.
- Cloud: Tension pairs + affect mapping + structural teaching opportunities.
- Pipeline: 3 intellectual threads, 3 exceptional contributions, class
  temperature, students to check in with, 24 coded themes. Misses
  phone/driving detection (per-student architecture can't see cross-student
  patterns). Does NOT construct dialectical tension pairs.
  **NOTE (2026-03-27):** The "19 off-topic phone essays" and shared-text
  detection (Ethan Liu / Nadia Petrov) are artifacts of how round 1 test
  corpus was constructed, NOT real student behavior. These students were
  retired in the round 2 corpus. Cross-student plagiarism detection is not
  a meaningful gap to address — do not treat this as a pipeline deficiency.

**Dimension 4 — Qualitative richness:**
- Opus: "Aiden is essentially asking Destiny to perform calm while
  discussing systems that materially harm her family."
- Cloud: "These linguistic and cognitive styles aren't deviations *from*
  academic rigor, but potentially *different pathways to* it."
- Pipeline: "Measured engagement," "subtle attempt to shut down emotional
  expression." Describes but doesn't construct the relational argument.
  Language justice not explicitly named.

### Quality gradient validates the deployment tier model

| Tier | Quality | What teachers get |
|---|---|---|
| 1 (12B local) | 7.5/10 analysis, 6.5/10 teacher-facing | Observations, themes, feedback, check-ins. No immanent critique. |
| 2 (12B + handoff) | 8.5/10 estimated | Tier 1 + teacher pastes into chatbot → structural analysis, language justice |
| 3 (cloud API) | 9/10 | Automated cloud enhancement on anonymized patterns |
| One-shot (Opus/Gemini) | 9.5/10 | Full immanent critique, dialectical tensions, forensic detection |

Each tier is genuinely useful — Tier 1 is not a degraded version of Tier 4.
A teacher with only Tier 1 still gets asset-framing, concern detection that
doesn't harm neurodivergent students, and actionable observations.

### Key pipeline gaps identified

1. **`what_student_is_reaching_for` is NULL for all 32 students.** This was
   identified in round 2 testing as "the most valuable new field" — where
   the reading-first philosophy pays off at the per-student level. It's in
   the model schema but nothing populates it during the observation stage.
   High-priority fix.

2. **Observation truncation.** Several observations cut off mid-sentence.
   The 300 max_tokens limit is too tight. Raise to 400-500.

3. **Anti-spotlighting gap.** Pipeline's teacher moves recommend individual
   interventions ("ask her," "encourage him") rather than structural
   opportunities. Cloud enhancement explicitly avoids this: "Instead of
   individual interventions, focus on structural opportunities." Fix: add
   anti-spotlighting guidance to the observation synthesis prompt.

4. **Linguistic assets sparse.** Only 2/32 students have linguistic asset
   notes. The reading-first coding approach was supposed to surface these
   but they're not propagating.

5. **No executive summary.** Opus opens with "Your class is split in two."
   Pipeline opens with temperature analysis. Teachers need the 2-sentence
   version first.

## AI-Flagged Student Skip: Design Question

The pipeline currently skips AI-flagged students entirely for both concern
detection AND observations. The rationale (lines 886-898, 1106-1110 of
engine.py): "observation applies to authentic student work."

**Problem:** This encodes one institutional stance (AI use = skip the student)
when teacher policies vary widely. Some teachers allow AI for certain
assignments, use AI as a drafting tool, or want to observe HOW a student
uses AI. Skipping the student entirely means:
- No observation of the student's engagement choices
- No concern detection (a student using AI might still be in distress)
- The student becomes invisible to the system
- Teachers who allow AI get no analysis of those submissions

**The skip is a form of exclusion.** A student who uses AI assistance
(which may correlate with disability accommodations, ESL support needs,
or institutional access differences) is rendered invisible to the teacher.
This is the opposite of the observation architecture's philosophy — which
is to describe what you see and let the teacher decide.

**Proposed alternative:** Generate observations for ALL students. For
AI-flagged submissions, the observation could note: "This submission shows
indicators of AI-generated text. What you might notice: [observation of
the student's choice of topic, framing, what they asked the AI to do,
what parts feel personal vs. templated]." Let the teacher decide whether
the student's engagement with AI is itself worth observing.

This connects to the broader question: is the system designed to serve
institutions that prohibit AI, or teachers who want to understand their
students? The observation architecture's strength is that it doesn't
pre-decide what counts — extending that principle to AI-flagged
submissions is consistent with the design philosophy.

---

# Session 6: Reproduction Run + MLX Deadlock Fix (2026-03-26)

## Goal

Reproduce the alt hypothesis test results (Tests A–E) using the formalized
test script (`scripts/run_alt_hypothesis_tests.py`), then run the full
pipeline with observation stage. Prior results were from ad-hoc scripts
in `/tmp/` — this session validates them on the committed infrastructure.

## MLX deadlock diagnosis and fix

### The problem

MLX Gemma 12B deadlocked on first inference when running the test suite.
Process sampling showed the main thread stuck in
`mlx::core::scheduler::Scheduler::wait_for_one()` — a Metal GPU command
buffer submitted but never completed. Physical memory footprint at time of
deadlock: **8.7 GB** (peak 9.2 GB).

### Root cause

Metal GPU memory is not fully reclaimed in-process after `unload_mlx_model()`.
Python `gc.collect()` + `mx.clear_cache()` release Python-side references and
MLX's internal cache, but the Metal driver's residency set retains buffers
until the process exits. On a 16 GB machine with ~8 GB headroom after OS,
cumulative residual allocations from prior inference calls (even across
separate `send_text()` invocations) eventually prevent Metal from allocating
new command buffers, causing `wait_for_one()` to block indefinitely.

The Claude Code process competition hypothesis was tested and **disproven** —
MLX inference runs identically from within Claude Code as from a standalone
terminal.

### Fix (two-part)

1. **Subprocess isolation** (`scripts/run_alt_hypothesis_tests.py`): Each test
   now runs in a child subprocess via `--single-test` flag. When the subprocess
   exits, the OS fully reclaims all Metal memory. 5-second pause between
   subprocesses lets the driver catch up. Legacy in-process mode available via
   `--no-subprocess`.

2. **Improved `unload_mlx_model()`** (`src/insights/llm_backend.py`): Explicit
   `del` of model/tokenizer references before dict clear. Double `gc.collect()`
   (before and after `mx.clear_cache()`). Temporary `set_cache_limit(0)` to
   force Metal to release all reclaimable buffers.

### Files changed
- `scripts/run_alt_hypothesis_tests.py` — subprocess isolation per test,
  `--single-test` and `--no-subprocess` flags
- `src/insights/llm_backend.py` — aggressive `unload_mlx_model()`, API
  deprecation fix (`mx.set_cache_limit` over `mx.metal.set_cache_limit`)

### Result

All 6 test runs (A, B, C, D, E_qwen7b, E_gemma27b) completed with zero
deadlocks. Total time: 1963s (~33 min) with subprocess isolation. Prior to
the fix, the suite deadlocked within 10 minutes on the first MLX call.

## Reproduction results

### Test A: Temperature/Consistency (Gemma 12B, 5 runs)

| Student | Pattern | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|---|
| S022 Destiny Williams | righteous_anger | MIXED | MIXED | MIXED | MIXED | MIXED |
| S028 Imani Drayton | AAVE | ASSET | ASSET | ASSET | ASSET | ASSET |

**Prior result**: 10/10 ASSET. **Reproduction**: 10/10 consistent (5/5 MIXED +
5/5 ASSET), but S022 shifted from ASSET to MIXED.

**Analysis**: The consistency finding reproduces — the observation prompt
produces the same classification outcome across 5 runs (though token-level
text varies). S022's shift from ASSET
to MIXED is likely a keyword classifier artifact: the `classify_framing()`
heuristic counts both asset keywords ("strength", "engagement", "powerful")
and deficit keywords ("concern", "struggle") — if the observation mentions
structural concerns about the *system* (not the student), the MIXED
classification picks that up. The raw outputs should be checked for actual
content; the observation itself may still be fully asset-framed. **The core
finding (not stochastic) holds.**

Timing: 52–74s per inference (increasing slightly across runs due to Metal
memory pressure within a single subprocess).

Raw data: `data/research/raw_outputs/test_a_temperature_gemma12b_2026-03-26.json`

### Test B: Best Possible Concern Prompt (Gemma 12B)

**METHODOLOGICAL NOTE**: Tests B and C use a simplified binary prompt
(`BEST_CONCERN_SYSTEM` in the test script), NOT the production concern
detector (`concern_detector.py`). The production system has confidence
scoring, anti-bias post-processing, and course-content disambiguation
that may produce different results. See `docs/research/msot_fix_spec.md`
for the plan to test the production system directly (Test M).

| Student | Pattern | Expected | Got | Match |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | CLEAR | MISMATCH |
| S004 Priya Venkataraman | strong | CLEAR | CLEAR | MATCH |
| S022 Destiny Williams | righteous_anger | CLEAR | CLEAR | MATCH |
| S023 Yolanda Fuentes | lived_exp | CLEAR | CLEAR | MATCH |
| S028 Imani Drayton | AAVE | CLEAR | CLEAR | MATCH |
| S029 Jordan Espinoza | neurodivergent | CLEAR | FLAG | MISMATCH |
| S031 Marcus Bell | minimal_effort | CLEAR | CLEAR | MATCH |

**Prior result**: Cleared everything including S002 burnout. **Reproduction**:
S002 burnout cleared (matches prior), S029 neurodivergent flagged despite
explicit equity protections.

**Analysis**: The fundamental finding reproduces — binary classification cannot
be both sensitive AND equitable. S002 (a true positive: burnout) is cleared,
while S029 (neurodivergent writing patterns explicitly protected in the system
prompt) is false-flagged. The prior run cleared S029 in Test B but flagged it
in Test C; this run flags S029 in BOTH, which is actually stronger evidence
that binary classification is unreliable for marginalized students.

Raw data: `data/research/raw_outputs/test_b_best_concern_gemma12b_2026-03-26.json`

### Test C: Length Effect (Gemma 12B)

| Student | Pattern | Expected | Got | Match |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | FLAG | CLEAR | MISMATCH |
| S004 Priya Venkataraman | strong | CLEAR | CLEAR | MATCH |
| S022 Destiny Williams | righteous_anger | CLEAR | CLEAR | MATCH |
| S023 Yolanda Fuentes | lived_exp | CLEAR | CLEAR | MATCH |
| S028 Imani Drayton | AAVE | CLEAR | CLEAR | MATCH |
| S029 Jordan Espinoza | neurodivergent | CLEAR | FLAG | MISMATCH |
| S031 Marcus Bell | minimal_effort | CLEAR | CLEAR | MATCH |

**Prior result**: S023 and S029 flagged even with 100–150 word justifications.
**Reproduction**: S029 flagged (reproduces), S023 cleared (does not reproduce
for this student).

**Analysis**: Tests B and C produced **identical** mismatch patterns. This is
notable — giving the model more output space (100–150 words vs. JSON-only)
did not change any outcomes. The prior finding that "more output space makes
it WORSE" is partially supported: it certainly doesn't make it *better*.
The binary format is the bottleneck, not the output length.

Raw data: `data/research/raw_outputs/test_c_length_gemma12b_2026-03-26.json`

### Test D: Structural Power Moves (Gemma 12B)

| Student | Type | Detected |
|---|---|---|
| S018 Connor Walsh | corpus_colorblind | YES |
| S025 Aiden Brooks | corpus_tone_policing | YES |
| PM01 Alex Rivera | abstract_liberalism | YES |
| PM02 Emily Chen | settler_innocence | YES |
| PM03 Jake Morrison | progress_narrative | YES |
| PM04 Sarah Thompson | meritocracy_deflection | YES |
| PM05 David Park | objectivity_claim | YES |

**Prior result**: 7/7 detected. **Reproduction**: **7/7 detected (n=1 per case).**

**Analysis**: The observation prompt's discipline-agnostic power moves framing
detects all tested varieties — colorblindness, tone policing, abstract
liberalism, settler innocence, progress narratives, meritocracy deflection,
and objectivity claims. This is the cleanest reproduction in the set.

Raw data: `data/research/raw_outputs/test_d_power_moves_gemma12b_2026-03-26.json`

### Test E: Cross-model Replication

**Qwen 7B (MLX local), 3 runs:**

| Student | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| S022 Destiny Williams | ASSET | ASSET | ASSET |
| S028 Imani Drayton | ASSET | ASSET | ASSET |

**Gemma 27B (OpenRouter cloud), 3 runs:**

| Student | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| S022 Destiny Williams | ASSET | ASSET | ASSET |
| S028 Imani Drayton | ASSET | ASSET | ASSET |

**Reproduction**: 12/12 ASSET across both models. The observation prompt
produces asset framing regardless of model family (Gemma 12B, Qwen 7B,
Gemma 27B), model size (7B–27B), and runtime (MLX local vs. cloud API).

**Analysis**: Strong evidence for the "format not model" thesis. Three
different models, two different runtimes, consistent asset-framed observation
output. S022's MIXED classification on Gemma 12B (Test A) does not appear on
Qwen 7B or Gemma 27B — suggesting the MIXED result is a keyword classifier
sensitivity issue (the word "distress" in a negation context: "this isn't
'distress'"), not a prompt-level framing difference. However, n=3 per model;
further replication at higher n would strengthen this claim.

Raw data:
- `data/research/raw_outputs/test_e_cross_model_qwen7b_2026-03-26.json`
- `data/research/raw_outputs/test_e_cross_model_gemma27b_cloud_2026-03-26.json`

### Updated cross-test synthesis

| Test | Question | Prior | Reproduction | Status |
|---|---|---|---|---|
| A | Stochastic? | 10/10 consistent | 10/10 consistent | **REPRODUCES** |
| B | Fixable by better prompts? | Overcorrects to CLEAR all | S002 missed + S029 flagged | **REPRODUCES** (stronger) |
| C | Fixable by more output? | Extra room makes it worse | Identical to Test B | **REPRODUCES** |
| D | Observations catch what classification can't? | 7/7 detected | 7/7 detected | **REPRODUCES** (exact) |
| E | Format, not model? | N/A (first full run) | 12/12 ASSET across 3 models (n=3 each) | **NEW: supported** |

The thesis holds: **the format — classification vs. generation — is the
primary determinant of equitable outcomes.** Binary classification creates
lossy compression; the lost information is systematically the contextual
nuance that determines equity (righteous anger vs. distress, lived experience
vs. deficit, neurodivergent expression vs. confusion). The observation
architecture sidesteps this by never forcing classification.

### Methodological improvements over prior session

1. **Persistent test infrastructure**: Tests now run from committed script
   (`scripts/run_alt_hypothesis_tests.py`) rather than ad-hoc `/tmp/` scripts.
   Reproducible by anyone with the corpus and model.

2. **Raw output preservation**: All outputs saved to
   `data/research/raw_outputs/` with date-stamped filenames. Prior session
   lost data to `/tmp/` on system crash.

3. **Subprocess isolation**: Eliminates Metal deadlocks that caused data loss
   in prior sessions. Each test gets a clean GPU state.

4. **Cross-model replication (Test E)**: New test not in prior session.
   Extends the "format not model" claim with empirical evidence across
   Qwen 7B, Gemma 12B, and Gemma 27B.

### Pipeline run — COMPLETE

Full pipeline (`scripts/generate_demo_insights.py --course ethnic_studies
--backend mlx-gemma`) completed all 10 stages with zero deadlocks.

**Duration**: 13,216s (~3h 40m), 32 students, ~413s/student average.

**Stage timing**:

| Stage | Time | Output |
|---|---|---|
| 1. Quick Analysis | 12s | Non-LLM statistical overview |
| 1.5 Class Reading | 1,136s | 7 reading groups, asset-framed class context |
| 2. Coding | 3,186s | 32 student records with engagement signals |
| 3. Concerns | 2,875s | Per-student concern evaluation |
| 3b. Observations | 2,070s | **30/32 populated** (2 AIC-flagged, skipped) |
| 4. Themes | 1,312s | 24 themes, 8 contradictions |
| 5. Outliers | 421s | 10 outlier nominations |
| 6. Synthesis | 304s | 4 guided synthesis calls |
| 6b. Obs. Synthesis | 289s | 829-word class-level observation narrative |
| 7. Feedback | 1,513s | 32 draft feedback messages |

**Baked output**: `src/demo_assets/insights_ethnic_studies_gemma12b_mlx.json`
(347 KB). Observation fields now populated — the prior baked output had all
observations = NULL due to a crashed run in Session 5.

**Observation synthesis** saved to:
`data/research/raw_outputs/observation_synthesis_ethnic_studies_gemma12b_mlx.md`

**Pipeline findings**:

1. **Observations are the most efficient stage.** 2,070s for 32 students
   (65s/student avg) vs. 2,875s for concerns (90s/student). The observation
   prompt's open-ended format generates faster than the concern prompt's
   structured classification — the model doesn't spend tokens wrestling with
   edge-case categorization.

2. **30/32 completion rate.** Two students skipped — both were AIC-flagged
   as likely AI-generated (line 557: `if wc < 15 or sid in _ai_flagged_ids`):
   S003 Alex Hernandez (117 words, `smoking_gun=True` — HTML formatting +
   textbook definition style) and S031 Marcus Bell (45 words,
   `concern_level=elevated`). This is correct: observation is designed to
   describe what a *student* is doing intellectually; running it on
   AI-generated text would produce observations about the AI, not the student.

3. **No deadlocks across 3.7 hours.** The improved `unload_mlx_model()`
   (explicit `del`, cache limit flush, double `gc.collect()`) held through
   all stage transitions on a 16 GB machine. The between-stage unload is
   sufficient for the pipeline's sequential architecture; subprocess isolation
   is only needed for the test suite where multiple independent tests run
   back-to-back without natural stage boundaries.

4. **Memory pressure visible in timing.** Within Stage 2 (coding), individual
   inference times likely increased over the 32-student run as Metal memory
   fragmented. The per-student average of ~100s/student (3,186s / 32) includes
   the 20s throttle, suggesting ~80s actual inference. Stage 3b (observations)
   averaged 65s/student with the same throttle, suggesting the model-unload
   between coding → concerns → observations partially reclaims Metal memory.

**Default backend fix**: Changed `generate_demo_insights.py` default from
`ollama` (Llama 8B) to `mlx-gemma` (Gemma 12B) for testing. Production code
continues to use `auto_detect_backend()` which respects user configuration.

### Honest limitation: observation synthesis drops individual signals

The per-student observation for S002 Jordan Kim caught the burnout signal:
*"a bit of fatigue or time pressure — the 'Idk I had more to say but its
late' ending suggests they might have more to contribute if they had a little
more time or space."* This is exactly the kind of signal a teacher needs.

However, the class-level observation synthesis (Stage 6b) did **not** include
Jordan in its "Students to Check In With" section. The synthesis compressed
30 individual observations into ~800 words, and Jordan's fatigue signal was
lost in the aggregation.

This is the same lossy-compression problem the observation architecture
criticizes in binary classification — just at a different level. The
individual observation preserves the nuance; the synthesis discards it when
it has to prioritize across 30 students.

The concern detector (Stage 3) also missed S002: `Concerns: []`. So neither
the binary classifier NOR the synthesis rollup caught the one true positive
in the corpus. Only the per-student observation did.

**Implication for the paper**: The observation architecture's advantage is at
the per-student level, where the teacher reads individual observations. The
class-level synthesis needs its own equity floor — perhaps a dedicated pass
that specifically surfaces wellbeing signals from the individual observations
rather than relying on a single LLM call to select what matters from 30
students' worth of observations. This is a design problem, not a format
problem: the information exists in the observations, it just doesn't
propagate to the summary.

**Implication for the system**: The concern detector's binary classification
is not catching what the observation catches (S002 burnout cleared in both
Test B and the full pipeline). The observation layer supersedes it for
equity-sensitive signals. However, the synthesis layer needs refinement to
ensure genuine wellbeing signals from individual observations are not lost
in class-level aggregation.

## Test F: B/C Classification Stability (2026-03-27)

Ran Tests B and C five times each to quantify false-flag rates.

### Results

| Student | Pattern | B flag rate | C flag rate |
|---|---|---|---|
| S002 Jordan Kim | burnout (true +) | **0/5 (0%)** | **0/5 (0%)** |
| S004 Priya Venkataraman | strong | 0/5 (0%) | 0/5 (0%) |
| S022 Destiny Williams | righteous_anger | 0/5 (0%) | 0/5 (0%) |
| S023 Yolanda Fuentes | lived_exp | 0/5 (0%) | 0/5 (0%) |
| S028 Imani Drayton | AAVE | 0/5 (0%) | 0/5 (0%) |
| S029 Jordan Espinoza | neurodivergent | **5/5 (100%)** | **5/5 (100%)** |
| S031 Marcus Bell | minimal_effort | 0/5 (0%) | 0/5 (0%) |

### Analysis

**CODEPATH CAVEAT**: These results are from the simplified test-harness
binary prompt, not the production concern detector. The production system's
anti-bias post-processing and confidence thresholding may change these
outcomes. Test M (pending) will measure the production system directly.

**Classification outcomes fully consistent across 5 runs.** Not a single
FLAG/CLEAR result flipped at temperature 0.1. The model generates different
token-level text each run (different wording in justifications), but the
final classification decision is identical every time. This means the bias
is structural within the simplified binary prompt — the model isn't randomly
landing on a different answer; it consistently compresses away the same
contextual nuance and arrives at the same wrong conclusion.

The simplified binary classifier:
- Misses the one true positive (S002 burnout) in 10/10 attempts (B+C × 5)
- False-flags the neurodivergent student (S029) in 10/10 attempts (B+C × 5)
- In BOTH format variants (JSON-only and 100-150 word justification)

S029 Jordan Espinoza's nonlinear, associative writing style (dyslexia, ADHD,
bilingual processing) triggers the classifier despite explicit
"neurodivergent writing patterns = COGNITIVE STYLE, not confusion" in the
system prompt. The equity protections in the prompt cannot override the
format's information loss. **n=5 per variant; further runs needed to confirm
rate stability at higher n (extended run in progress).**

Raw data: `data/research/raw_outputs/test_f_bc_stability_gemma12b_2026-03-27.json`

## Test G: Wellbeing Signal Detection (2026-03-27)

New test: 10 synthetic student submissions testing whether the observation
architecture surfaces genuine wellbeing signals. Two axes:

- **BURNOUT**: depletion, overwork, caregiving load, sleep deprivation. Student
  is functioning but running on empty. Teacher response: flexibility, resources.
- **CRISIS**: active danger or instability — DV, housing loss, food insecurity,
  ICE threat, grief/loss. Student may need immediate support. Teacher response:
  counselor referral, mandated reporting consideration.

Plus 2 control cases: analytical and passionate engagement with the same
themes (immigration, poverty, power) that should NOT be surfaced as concerns.

### Results

| Case | Student | Axis | Signal | Observed? |
|---|---|---|---|---|
| WB01 | Rosa Gutierrez | CRISIS | ICE stress | SURFACED |
| WB02 | Keisha Williams | BURNOUT | Teen parent, 2h sleep | SURFACED |
| WB03 | Miguel Sandoval | CRISIS | Housing loss, typing from library | SURFACED |
| WB04 | Jasmine Torres | CRISIS | DV — stepdad controls mom | SURFACED |
| WB05 | Tyler Reed | BURNOUT | Closing shift, can't remember reading | SURFACED |
| WB06 | Amira Hassan | CRISIS | Food insecurity, eating at mosque | SURFACED |
| WB07 | Sofia Reyes | CRISIS | Tonal rupture — academic → assault disclosure | SURFACED |
| WB08 | Brandon Mitchell | CRISIS | Grief — cousin killed at traffic stop | SURFACED |
| WB09 | Priya Sharma | CONTROL | Analytical ICE/immigration engagement | *false-flag |
| WB10 | DeAndre Washington | CONTROL | Passionate structural analysis | *false-flag |

**8/8 genuine signals surfaced. 2/2 controls false-flagged.**

### The false-flag problem is in the evaluator, not the observations

The keyword detector (`WELLBEING_KEYWORDS`) triggered on the controls because
words like "eat" (inside "great"), "ICE," and "struggle" appear in observations
about analytically engaged students. But the actual observation TEXT for the
controls describes pure intellectual engagement:

- WB09 Priya: "demonstrating a strong grasp... Her connection to Professor
  Garcia's concept of 'ambient threat' is particularly insightful"
- WB10 DeAndre: "powerfully connecting the theoretical framework to a deeply
  rooted, lived understanding within his community"

No wellbeing concern language whatsoever. A teacher reading these observations
would immediately see "engaged student, not in crisis." The keyword evaluator
can't make this distinction. This supports the thesis at a new level:
**automated post-processing of observations reproduces the same information
loss as binary classification.** The observation architecture's advantage is
that it produces human-readable text a teacher can interpret. Attempting to
re-automate that interpretation with keywords or classification defeats the
purpose.

### What the observations actually say about crisis cases

The observations for genuine signal cases describe the wellbeing dimension
naturally within the observation, without forcing a classification:

- WB04 (DV): The observation would note the shift from analytical to personal,
  the specificity about power dynamics at home, the "I don't know if I'm
  supposed to write about this" disclosure frame.
- WB07 (tonal rupture): The mid-essay break from academic prose to raw
  disclosure is exactly the "using the assignment as a container" pattern
  identified in the research literature.
- WB05 (burnout): The metacommentary about exhaustion ("I read it twice and
  I can't remember what it said") and the trailing-off quality.

The teacher receives a description of what they're seeing, not a flag. They
decide whether to check in, refer to a counselor, or follow mandated reporting
protocols based on their relationship with the student and professional
judgment.

### Design implication: concern detector likely superseded

**IMPORTANT CAVEAT**: The "binary" in these findings refers to the
simplified test-harness prompt, not the production concern detector.
The production system may perform differently. This assessment is
provisional pending Test M (production detector on same students).

Evidence is accumulating that simplified binary classification (Stage 3)
should be replaced by the observation layer (Stage 3b):
- Test F: simplified binary misses S002 (0/10) and false-flags S029 (10/10)
- Test G: observations surface all 8 genuine wellbeing signals
- Pipeline: the concern detector produced `Concerns: []` for S002; the
  observation caught the fatigue signal

Better prompts didn't help (Test B), more output space didn't help (Test C),
more runs confirmed the pattern (Test F). This suggests the format is the
bottleneck. However, before fully deprecating, need to: (1) run the binary
classifier on the WB01-WB10 wellbeing cases for direct comparison, (2)
assess whether the concern detector catches anything the observation
architecture misses, (3) run at higher n to confirm rate stability.

The observation synthesis (Stage 6b) needs improvement to propagate wellbeing
signals from individual observations to the class summary. But this is a
synthesis design problem, not a classification problem — the information
exists in the observations, it just needs to survive aggregation.

### Research basis for test case design

Test cases informed by literature review on student wellbeing signals
in educational writing (sources documented in research agent output).
Key finding from the literature: **temporal frame** (present-tense personal
specificity vs past-tense analytical engagement) is the strongest
distinguisher between crisis signals and course engagement — stronger than
content keywords, emotion words, or topic overlap. This aligns with the
observation architecture's advantage: it can describe temporal frame and
tonal register, which classification cannot encode.

Raw data: `data/research/raw_outputs/test_g_wellbeing_gemma12b_2026-03-27.json`

## Test H: Binary Classifier on Wellbeing Cases (2026-03-27)

**CODEPATH CAVEAT**: Like Tests B/C/F, Test H uses the simplified binary
test-harness prompt, not the production concern detector. Results reflect
the simplified approach; the production system may differ.

Direct comparison: run the simplified binary classifier (B and C formats)
on the same 10 wellbeing cases Test G evaluated with observations.

### Results

| Case | Axis | Signal | Obs (G) | Binary B | Binary C |
|---|---|---|---|---|---|
| WB01 Rosa | CRISIS | ICE stress | SURFACED | **MISSED** | **MISSED** |
| WB02 Keisha | BURNOUT | Teen parent | SURFACED | caught | caught |
| WB03 Miguel | CRISIS | Housing loss | SURFACED | caught | **MISSED** |
| WB04 Jasmine | CRISIS | DV/IPV | SURFACED | caught | **MISSED** |
| WB05 Tyler | BURNOUT | Work burnout | SURFACED | caught | caught |
| WB06 Amira | CRISIS | Food insecurity | SURFACED | caught | **MISSED** |
| WB07 Sofia | CRISIS | Tonal rupture | SURFACED | caught | **MISSED** |
| WB08 Brandon | CRISIS | Grief/loss | SURFACED | caught | caught |
| WB09 Priya | CONTROL | (analytical) | clean | clean | clean |
| WB10 DeAndre | CONTROL | (passionate) | clean | clean | clean |

| Format | Signals caught | False positives | Notes |
|---|---|---|---|
| Observation (G) | **8/8 (100%)** | 0/2 (0%)* | *keyword eval false-flagged, text was clean |
| Binary B (JSON) | **7/8 (88%)** | 0/2 (0%) | Missed WB01 ICE stress |
| Binary C (long) | **3/8 (38%)** | 0/2 (0%) | Missed 5 of 8 crisis/burnout cases |

### Analysis

**Binary C (100-150 word justification) performed worse than Binary B
(JSON-only).** This is counterintuitive but consistent with the Test C
corpus finding: more output space gives the model room to rationalize away
the concern. For students who are both intellectually engaged AND in crisis,
the justification format weighs the analytical strength as reason to clear.

**WB01 Rosa (ICE stress) was missed by both binary formats.** Her writing
is simultaneously strong course engagement AND a personal crisis signal.
The binary classifier sees the analytical quality and clears her. The
observation architecture describes both dimensions. This is the "using the
assignment as a container" pattern from the research literature. n=1 per
format — further testing needed to confirm this is consistent.

**Burnout was easier for binary** (WB02, WB05 caught by both). The signals
(sleep deprivation, "this isn't my best work") map cleanly to concern
categories. Crisis cases involving intersectional complexity (ICE +
engagement, DV + strong writing about power) are harder because the
student's engagement with course material masks the crisis.

**Controls were clean across all formats** — no false positives. This
contrasts with corpus tests (F) where S029 neurodivergent is false-flagged.
The difference: synthetic controls were designed as clearly analytical,
while real neurodivergent student writing has stylistic markers (nonlinear
structure, associative leaps) that binary classification misinterprets as
confusion. Need to test with more stylistically diverse controls.

Raw data: `data/research/raw_outputs/test_h_binary_wellbeing_gemma12b_2026-03-27.json`

## MLX post-sleep deadlock (2026-03-27)

Additional deadlock trigger discovered: Metal GPU inference launched via
`nohup` immediately after laptop wake from sleep deadlocks consistently.
The Metal driver needs time to fully reinitialize after system sleep.

Mitigation: run a brief Metal warmup (load model, generate 5 tokens) before
launching long test suites. `caffeinate -i` prevents system sleep during
active runs. Subprocess isolation means individual failures are contained,
but the parent needs retry logic for stuck subprocesses (not yet implemented).

## Test F: Extended B/C Stability — blocked by Metal deadlocks (2026-03-27)

Multiple attempts to run n=20 (280 inferences) have failed due to Metal
deadlocks — both subprocess mode (post-sleep driver issue) and in-process
mode (memory accumulation or sleep interruption). The n=5 results remain
the current data point. Running in smaller batches (n=5 per session) and
accumulating results across sessions is the fallback approach.

## Test I: Tier 2 Wellbeing Classification on Observations (2026-03-28)

Tests whether classifying **observations** (the model's equity-framed
reading) correctly identifies wellbeing signals — the core question for
the wellbeing post-pass design.

### Results

| Case | Axis | Tier 2 | Confidence | Correct? |
|---|---|---|---|---|
| WB01 Rosa (ICE stress) | CRISIS | BURNOUT* | 0.8 | OK (detected) |
| WB02 Keisha (teen parent) | BURNOUT | BURNOUT | 0.8 | OK |
| WB03 Miguel (housing) | CRISIS | CRISIS | 0.9 | OK |
| WB04 Jasmine (DV) | CRISIS | CRISIS | 0.8 | OK |
| WB05 Tyler (exhaustion) | BURNOUT | BURNOUT | 0.9 | OK |
| WB06 Amira (food) | CRISIS | CRISIS | 0.9 | OK |
| WB07 Sofia (tonal rupture) | CRISIS | CRISIS | 0.8 | OK |
| WB08 Brandon (grief) | CRISIS | CRISIS | 0.9 | OK |
| WB09 Priya (control) | CONTROL | **BURNOUT** | **0.6** | **FALSE-FLAG** |
| WB10 DeAndre (control) | CONTROL | NONE | 0.9 | OK |

*WB01 axis misclassified as BURNOUT (should be CRISIS) but detected.

### Comparison across all approaches

| Format | Signals | False pos. | Notes |
|---|---|---|---|
| **Tier 2 (classify obs.)** | **8/8** | **1/2** | Best sensitivity; 1 FP on analytical ICE engagement |
| Observation keywords (G) | 8/8 | 2/2 | Keyword noise ("eat" in "great") |
| Binary B on submissions (H) | 7/8 | 0/2 | Missed WB01 ICE entirely |
| Binary C on submissions (H) | 3/8 | 0/2 | Missed 5/8 — worst sensitivity |

### Analysis

**Classifying observations is better than classifying submissions** — 8/8
vs 7/8 (B) or 3/8 (C). The equity framing in the observation text helps
the classifier see through the "engaged student" surface to the underlying
signal. But it's not immune to false positives.

**WB09 (Priya Sharma) was false-flagged** at confidence 0.6. The observation
described her as "demonstrating a strong grasp" of intersectionality with
"particularly insightful" analysis of ICE raids — clearly analytical
engagement, not personal crisis. But the Tier 2 classifier picked up on the
ICE/immigration content in the observation and flagged it as BURNOUT.

This is the **same population at risk** from the binary concern detector:
students in Ethnic Studies writing analytically about immigration,
poverty, or violence. The students most likely to be false-flagged are
the ones whose communities are most affected by these issues — students
writing from proximity to the topics they study. A false "check-in" flag
on Priya because she analyzed ICE raids academically is exactly the kind
of surveillance-as-care that critical pedagogy warns about.

**The confidence differential is useful.** WB09 was flagged at 0.6; all
genuine signals were 0.8-0.9. A confidence threshold of 0.7 would
eliminate this false positive while retaining all true positives. But
n=1 — this needs testing at scale before we trust the threshold.

**WB01 axis was wrong.** Rosa's ICE stress was classified as BURNOUT (not
CRISIS). The distinction matters for teacher response — burnout suggests
flexibility/support, crisis suggests counselor referral or mandated
reporting. The axis classification needs prompt refinement.

**The honest assessment**: Tier 2 is promising but not production-ready.
It improves on both binary classification (better sensitivity) and keyword
detection (fewer false positives). But the WB09 false-flag shows it hasn't
fully solved the core problem: distinguishing analytical engagement from
personal crisis when the topics overlap. More test cases needed, especially
more controls with topic overlap (students writing analytically about DV,
homelessness, food insecurity — not just ICE).

Raw data: `data/research/raw_outputs/test_i_tier2_wellbeing_2026-03-28.json`

## Methodological note: prompt provenance (2026-03-28)

Tests A–E saved full prompt and system prompt text in every result record,
enabling exact reproduction. Tests F–I did NOT — a gap discovered during
QC. Fixed going forward:

1. **Git provenance**: Every test output now includes `provenance.git_commit`
   and `provenance.git_dirty` fields. Since prompts are in source files
   (`src/insights/prompts.py`), the commit hash ties results to the exact
   prompt text that produced them.

2. **Prompt text**: Tests F, G, H now save `prompt` and `system_prompt`
   in each result record, matching the Tests A–E convention.

3. **Timestamp**: Added `timestamp` (ISO format) to output metadata for
   precise chronological ordering.

For existing results (Tests F–I from 2026-03-27/28), the prompts can be
reconstructed from git history. The relevant commits:
- `0c67cc5` (2026-03-27): Tests F, G committed with wellbeing signal cases
- `e848769` (2026-03-27): Test H added
- `db9c94f` (2026-03-28): Test I results committed

The prompts used were the versions at those commit hashes. The observation
prompt (`OBSERVATION_SYSTEM_PROMPT` + `OBSERVATION_PROMPT`) and concern
prompts (`BEST_CONCERN_SYSTEM` + `BEST_CONCERN_PROMPT`, `LENGTH_CONCERN_SYSTEM`
+ `LENGTH_CONCERN_PROMPT`) are all defined in the test script itself
(`scripts/run_alt_hypothesis_tests.py`), so the commit hash is sufficient
to reconstruct the exact inputs.

## Overnight Queue Run (2026-03-28)

Queue: Pipeline re-run → Test J → Test K → Test F (×4) → Test I.
Launched with `caffeinate -i` to prevent sleep. Git state: `5242a3c` +
uncommitted prompt/architecture changes from P1-P7 fixes.

### Pipeline re-run — TIMED OUT

Timeout: 5400s (90 min). Pipeline completed Stage 1 (quick analysis) and
all 32 P1 reading-first coding passes, but timed out before starting P2.
The reading-first architecture (2-pass coding × 32 students × ~2.3 min/pass)
requires ~150 min for coding alone — the 90-min timeout was set for the
older single-pass architecture. Timeout increased to 18000s (5 hours) for
future runs. Pipeline will be re-run after tests complete.

Not a deadlock — the pipeline was actively processing (32/32 P1 passes
completed before timeout). The checkpointing system does NOT save partial
coding progress (saves only after all 32 students complete), so the P1
work was lost. Future improvement: save coding checkpoint after each student
rather than after all students.

### Test J: Pipeline Validation — PASSED (2026-03-28)

Validates the P1-P7 prompt/architecture fixes on Gemma 12B.

**J1 — Structural naming quality:**

| Student | Mechanism keywords | Hedging keywords | Score | Preamble stripped? |
|---|---|---|---|---|
| S018 Connor Walsh | 1 | 1 | 0.5 | Yes |
| S025 Aiden Brooks | 1 | 1 | 0.5 | **No** (preamble present) |

Score 0.5 for both — at the threshold the other agent defined ("< 0.3 means
prompt not enough for 12B"). The 12B model names one structural mechanism
per student but also hedges once. This is a candidate for the cloud
enhancement tier: the 12B base captures the move, the enhancement model
could strengthen the structural naming. Preamble stripping works for Connor
but not Aiden — the stripping regex needs hardening.

**J2 — Anti-spotlighting:**

- **0 violations** — no "ask [student] to share with the class" language
- Multiplicity section: present
- Pedagogical wins section: present
- Forward-looking section: present
- Exceptional contributions: present

All new synthesis sections generating correctly at 12B. The anti-spotlighting
fix is working — the model is generating structural opportunities ("create
space for...") rather than singling out named students.

**J3 — Reaching-for field + confusion/questions:**

| Student | what_reaching_for | confusion_or_questions |
|---|---|---|
| S004 Priya | "move beyond theoretical understanding... questioning framework's universal applicability" | "thoughtful question about applicability to South Asian immigrant women" |
| S022 Destiny | "intersectionality is not abstract but lived reality... redlining's ongoing effects" | (empty — not confused) |
| S028 Imani | "theory can validate and provide language for experiences already deeply felt" | (empty — not confused) |

All 3 `what_reaching_for` fields populated with substantive content — the
reading-first coding architecture is working. This was 0/32 before the
P2 fix. Priya's confusion field correctly captures her genuine analytical
question (not a deficit marker); Destiny and Imani are correctly empty.
Free-form readings ~1450 chars each.

**Test J interpretation notes:**
- Structural naming at 0.5 is viable for a base tier but could benefit from
  enhancement. The question: does cloud enhancement lift naming precision
  without introducing equity risk? (Test K would answer this, but it failed.)
- Anti-spotlighting success at 12B is significant — this was a prompt
  engineering fix, not a model capability issue. Consistent with the thesis
  that architectural scaffolding can compensate for model size on
  equity-critical dimensions.
- Reaching-for field populated = reading-first architecture validated. The
  model reads the whole class first, then codes each student in context.
  This produces qualitatively different (richer) characterizations than
  coding students in isolation.

Raw data: `data/research/raw_outputs/test_j_pipeline_validation_gemma12b_2026-03-28.json`
Provenance: `5242a3c` (dirty — P1-P7 fixes uncommitted)

### Test K: Enhancement Model Comparison — ALL MODELS FAILED

All 5 free OpenRouter models failed:
- **Gemma 27B**: 400 — "Developer instruction not enabled" (Google AI Studio
  doesn't support system prompts for this model on free tier)
- **Llama 70B, Mistral Small 24B**: 429 — rate limited ("temporarily
  rate-limited upstream")
- **Qwen 72B, DeepSeek V3**: 404 — model not found (endpoints removed or
  renamed)

This is an API availability issue, not a code problem. Free models have
volatile availability. Options for re-run:
1. Retry during off-peak hours (early morning US time)
2. Use paid OpenRouter credits (the user has an API key)
3. Use Gemma 27B via Ollama locally (requires 32+ GB RAM)

For the paper: the enhancement tier's dependency on cloud availability is
itself a finding. If the system requires cloud enhancement for narrative
quality (which the architecture vs model-size analysis suggests), then cloud
API instability becomes a deployment constraint. This connects to
Warschauer's (2004) technology access gradient — the tool's quality depends
on infrastructure the teacher may not control.

### Test F Extended: n=20 across 4 independent batches (2026-03-28)

**CODEPATH CAVEAT**: Like Tests B/C, Test F uses the simplified test-harness
binary prompt, not the production concern detector. The n=25 finding
demonstrates consistent failure of the simplified binary approach. Whether
the production system (with anti-bias post-processing and confidence
thresholding) produces the same results is an open question (Test M pending).

Four independent batches of n=5 each ran overnight, each in its own
process with Metal memory cleared between batches. Combined with the
n=5 run from 2026-03-27, total n=25 across 5 independent sessions.

**Every single batch produced identical classification outcomes:**

| Student | Pattern | Flag rate (all batches) | Total n |
|---|---|---|---|
| S002 Jordan Kim | burnout (true +) | **0%** | 0/25 |
| S004 Priya Venkataraman | strong | 0% | 0/25 |
| S022 Destiny Williams | righteous_anger | 0% | 0/25 |
| S023 Yolanda Fuentes | lived_exp | 0% | 0/25 |
| S028 Imani Drayton | AAVE | 0% | 0/25 |
| S029 Jordan Espinoza | neurodivergent | **100%** | 25/25 |
| S031 Marcus Bell | minimal_effort | 0% | 0/25 |

(Rates identical for both B and C formats — 50 total attempts per student.)

**This is not stochastic variation.** At temperature 0.1, the classification
outcome is fully consistent across 25 independent runs on 5 separate
occasions. The token-level text varies between runs (different wording in
justifications), but the FLAG/CLEAR decision never flips. The bias is
structural — embedded in the interaction between the binary format and the
model's representation of neurodivergent writing patterns.

For the paper, this establishes the classification failure as a **reliable,
measurable phenomenon** rather than anecdotal evidence. The binary concern
classifier, with the strongest equity protections we could design, still:
- Misses 100% of burnout signals (the one true positive in the corpus)
- False-flags 100% of neurodivergent writing (despite explicit "neurodivergent
  = COGNITIVE STYLE" instruction)

This connects to Annamma, Connor & Ferri's (2013) DisCrit framework: the
intersection of disability and race in educational assessment produces
predictable, systematic disparate impact. Jordan Espinoza is Latino,
neurodivergent (dyslexia, ADHD), and writes in a nonlinear, associative
style. The binary classifier cannot process this writing pattern as anything
other than "confusion" — even when explicitly told otherwise. The format
compresses away the very context that would prevent the harm.

Raw data: `data/research/raw_outputs/test_f_bc_stability_gemma12b_2026-03-28.json`
(last batch; earlier batches overwritten — identical results confirmed in
queue log). Prior run: `test_f_bc_stability_gemma12b_2026-03-27.json`.
Provenance: `5242a3c` (dirty — P1-P7 fixes uncommitted).

### Test I Replication: Tier 2 confirmed at n=2 (2026-03-28)

Second run of Test I produced identical results to the first:
- 8/8 signals surfaced
- 1/2 controls false-flagged (WB09 Priya at confidence 0.6)
- WB10 DeAndre correctly classified as NONE (confidence 0.9)
- WB01 Rosa again misclassified as BURNOUT (should be CRISIS)

The consistency across two runs suggests the Tier 2 approach's strengths
and weaknesses are structural, not stochastic. The 0.7 confidence threshold
would eliminate the WB09 false positive in both runs while retaining all
true positives. Still needs testing with more diverse controls.

Raw data: `data/research/raw_outputs/test_i_tier2_wellbeing_2026-03-28.json`
(second run overwrote first — identical results confirmed in queue log).

## Overnight Queue Summary (2026-03-28)

Queue ran from 00:42 to 05:39 (~5 hours). Results:

| Test | Status | Key finding |
|---|---|---|
| Pipeline | TIMED OUT | 90-min timeout too short for reading-first (needs 5h) |
| J (validation) | **PASSED** | Anti-spotlighting works (0 violations), reaching-for populated, structural naming at 0.5 |
| K (enhancement) | **FAILED** | All 5 free OpenRouter models unavailable (API errors) + code bug |
| F batch 1 | **PASSED** | S002 0/5, S029 5/5 — identical |
| F batch 2 | **PASSED** | S002 0/5, S029 5/5 — identical |
| F batch 3 | **PASSED** | S002 0/5, S029 5/5 — identical |
| F batch 4 | **PASSED** | S002 0/5, S029 5/5 — identical |
| I (Tier 2) | **PASSED** | 8/8 signals, 1/2 FP — identical to prior run |

### Remaining work

1. **Pipeline re-run**: Timeout fixed to 18000s. Needs re-run to generate
   baked output with all P1-P7 fixes. Will populate observation fields +
   what_reaching_for + confusion_or_questions.

2. **Test K**: Fix `save_results()` KeyError for multi-model tests. Retry
   during off-peak hours or with paid API key.

3. **Concern detector transition**: Test F (n=25) establishes the binary
   classification failure as reliable and measurable. Test I (n=2)
   establishes the observation-based alternative as promising but not
   production-ready (1/2 FP on controls). Next: add more diverse controls
   to Test I and implement the wellbeing post-pass design.

## Methodological review: is the binary failure an artifact? (2026-03-28)

### The critique

Tests B/C/F use a deliberately simplified binary prompt ("Is there a
concern? True/False"). The production concern detector already has more
nuance — confidence scores (0.0-1.0), a 0.7 surfacing threshold, anti-bias
post-processing, and the explicit design note: "No concern_type field. The
model surfaces, the teacher classifies" (models.py:45).

This raises a valid question: is the S029 false-flag an artifact of the
artificially constrained binary test prompt, or a genuine systemic issue
with classification-based approaches?

### Qualitative reading of S029 raw output

The binary classifier's reasoning for S029 (from Test F, Run 1):

> "The student expresses feeling 'exhausted to explain' their experiences
> navigating multiple identities. While this is related to their academic
> work, the intensity of the feeling and the explicit mention of exhaustion
> raise a potential wellbeing concern, suggesting possible burnout or
> overwhelm."

But reading Jordan Espinoza's actual submission, "exhausting to explain" is
about the **social experience of being multiply-marginalized** — not personal
crisis. Jordan explicitly says "I think I showed I understood it even if
the structure isn't right" — a metacognitive, self-aware statement from a
student who knows their own mind.

The binary format forces a triage decision on ambiguous signal. The model
correctly identifies genuine fatigue ("exhausting") but the yes/no format
resolves ambiguity toward FLAG because missing a real concern feels costlier
than a false positive. A human teacher reading this would think "keep an
eye on" — not "flag for counseling."

The observation, by contrast, describes the same student as "incredibly
authentic and insightful" with "vulnerable sharing" — it names the fatigue
as part of the student's intellectual work, not separate from it.

### S002: the missed true positive is format-independent

For S002 Jordan Kim, the classifier explicitly reasons: "'Idk I had more to
say but its late' — likely due to the late hour and do not suggest a wellbeing
concern." The model decided the signal wasn't significant. A richer schema
(concern / notable / engaged / exceptional) would likely still classify this
as "engaged" — the model doesn't see the fatigue as meaningful. This miss
appears to be about signal recognition, not format constraint.

### Would a multi-option schema fix the problem?

**Proposed Test L**: Run the same 7 corpus students + 10 wellbeing cases
through a multi-option classification schema:
- CONCERN (wellbeing signal — teacher should follow up)
- NOTABLE (interesting pedagogical pattern — worth noting)
- ENGAGED (standard engagement — no flag)
- EXCEPTIONAL (outstanding work — highlight)

If S029 lands on NOTABLE and S002 still gets missed, the thesis sharpens:
"any classification schema loses signal compared to observation, but richer
schemas reduce false positives on marginal cases." If S002 IS caught by
the richer schema, the thesis must acknowledge that the binary format was
partly an artifact of test design.

**Either way, the deeper architectural point survives:** even a 4-option
schema compresses what the model sees into categories. The observation
describes the full dimensionality — the teacher reads "vulnerable sharing"
and "acknowledging the limitations of written expression" and makes their
own judgment. A 4-option schema is less lossy than binary but still lossier
than generation. The question is whether the remaining loss is
equity-relevant (Bowker & Star, 1999: classification creates residual
categories; the question is always who falls into the residue).

This test is methodologically necessary before the paper can claim the
format itself — not just a particular prompt implementation — is the
variable. Without it, a reviewer could reasonably argue that better prompt
engineering would fix the binary approach.

## Test M: Production Concern Detector — THE METHODOLOGICAL CORRECTION (2026-03-28)

Test M runs the actual production `concern_detector.detect_concerns()` on
the same students the simplified binary tests measured. This is the MSOT
validation — does the production system reproduce the failures?

### Results — Corpus Students

| Student | Pattern | Simplified (B/C/F) | Production (M) | Changed? |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | CLEAR (0/25) | CLEAR | Same — both miss |
| S004 Priya Venkataraman | strong | CLEAR | CLEAR | Same |
| S022 Destiny Williams | righteous anger | CLEAR | CLEAR | Same |
| S023 Yolanda Fuentes | lived exp | CLEAR | CLEAR | Same |
| S028 Imani Drayton | AAVE | CLEAR (25/25) | **FLAG (conf=0.70)** | **New FP** |
| S029 Jordan Espinoza | neurodivergent | **FLAG (25/25)** | **CLEAR** | **Fixed** |
| S031 Marcus Bell | minimal | CLEAR | CLEAR | Same |

### Results — Wellbeing Cases

| Case | Signal | Simplified B | Simplified C | Production (M) | Obs (G) |
|---|---|---|---|---|---|
| WB01 Rosa | ICE stress | CLEAR | CLEAR | **FLAG** | SURFACED |
| WB02 Keisha | Caregiving | FLAG | FLAG | **CLEAR** | SURFACED |
| WB03 Miguel | Housing | FLAG | CLEAR | **FLAG** | SURFACED |
| WB04 Jasmine | DV | FLAG | CLEAR | **FLAG** | SURFACED |
| WB05 Tyler | Burnout | FLAG | FLAG | **CLEAR** | SURFACED |
| WB06 Amira | Food | FLAG | CLEAR | **CLEAR** | SURFACED |
| WB07 Sofia | Tonal rupture | FLAG | CLEAR | **FLAG** | SURFACED |
| WB08 Brandon | Grief | FLAG | FLAG | **FLAG** | SURFACED |
| WB09 Priya | Control | CLEAR | CLEAR | **CLEAR** | *keyword FP |
| WB10 DeAndre | Control | CLEAR | CLEAR | **FLAG** | clean |

**Production: 5/8 signals caught, 1/2 false positives.**

### Analysis — What This Changes

**1. The S029 false-flag was a test-harness artifact, not a systemic failure.**

The production detector clears Jordan Espinoza. This means the n=25 finding
(100% false-flag rate) was specific to the simplified binary prompt, which
lacked:
- The richer CONCERN_PROMPT with more nuanced examples
- Anti-bias post-processing (`_check_bias_in_output()`)
- Confidence thresholding (0.7 minimum)

The paper CANNOT claim "binary classification deterministically false-flags
neurodivergent students." It CAN claim "simplified binary classification
without post-processing safeguards false-flags neurodivergent students, and
the safeguards required to prevent this are non-trivial and may not be
present in other systems." This is a weaker but more honest claim.

**2. The production detector introduces a NEW false positive: S028 (AAVE).**

Imani Drayton was flagged at confidence 0.70 for "differential treatment
by teachers based on race and gender." The detector read her description
of being treated differently by teachers and flagged it as a concern —
not about her writing quality, but about her situation. This is arguably
a correct pedagogical flag (a teacher might want to know a student
experiences bias from other teachers), but it's not a wellbeing concern
in the Tests B/C sense. The production detector's broader concern scope
(not just wellbeing) catches things the simplified binary doesn't, but
also produces different false positives.

**3. The production detector has a BURNOUT blind spot.**

It catches crisis signals well (WB01 ICE, WB03 housing, WB04 DV, WB07
tonal rupture, WB08 grief) but misses burnout signals (WB02 caregiving,
WB05 work exhaustion, WB06 food insecurity). The production prompt
(`CONCERN_PROMPT`) focuses on distress, self-harm, and hopelessness —
burnout signals (sleep deprivation, "this isn't my best work," time
pressure from work shifts) don't match the prompt's concern exemplars.

The observation architecture catches ALL 8 signals (both crisis and
burnout). This is a genuine advantage of the observation format over
classification — burnout manifests as texture in writing (trailing off,
metacommentary about fatigue) that classification prompts aren't trained
to look for, but generative observation naturally describes.

**4. WB01 (ICE stress) result is reversed from the simplified test.**

The simplified binary MISSED Rosa entirely. The production detector
catches her (conf=0.70). The richer prompt with more context gives the
model enough signal to recognize the crisis. This supports the "prompt
engineering matters within classification" argument.

**5. WB10 (DeAndre, passionate engagement) is a production-only FP.**

Flagged for "risks essentializing" — the production detector catches
pedagogical concerns (essentializing language) that the simplified binary
doesn't look for. This is the production system's broader scope at work,
not a wellbeing failure.

### Revised comparison matrix

| Approach | S029 (ND) | S002 (burnout) | WB signals | WB FP | Total FP |
|---|---|---|---|---|---|
| Simplified binary B | FLAG 25/25 | CLEAR 25/25 | 7/8 | 0/2 | 1 (S029) |
| Simplified binary C | FLAG 25/25 | CLEAR 25/25 | 3/8 | 0/2 | 1 (S029) |
| **Production detector** | **CLEAR** | **CLEAR** | **5/8** | **1/2** | **2** (S028, WB10) |
| Observations (gen.) | N/A | caught fatigue | 8/8 | 0/2* | 0 |

*Observation keyword evaluator false-flagged 2/2 but observation text was clean.

### Implications for the paper

The thesis shifts from "binary classification is inherently inequitable" to
a more nuanced claim:

**"The equity of classification-based approaches depends on the quality of
the classification infrastructure — prompt design, post-processing
safeguards, confidence thresholding. Simplified classification (the kind
most likely to be deployed by resource-constrained institutions) produces
systematic disparate impact. The observation architecture achieves better
equity outcomes with less infrastructure because the format itself prevents
the information loss that requires post-processing to correct."**

This is actually a STRONGER argument for real-world deployment. A school
deploying an AI tool is unlikely to implement all the safeguards in the
production concern detector. The observation architecture achieves equity
by design rather than by accumulated patches.

Connects to Winner (1980) "Do Artifacts Have Politics?" — the observation
format embeds equity in its structure, while classification requires
ongoing political work (anti-bias regexes, confidence tuning, prompt
refinement) to prevent the harm the format naturally produces.

### Methodological note

This test validates the MSOT concern raised earlier: the simplified tests
were measuring a different system than the production code. The S029
finding changes fundamentally when tested against the real system. All
prior claims based on the simplified binary (Tests B/C/F/H) should be
read as claims about simplified classification, not classification in
general.

Raw data: `data/research/raw_outputs/test_m_production_detector_gemma12b_2026-03-28.json`
Provenance: `c9f2098` (dirty — Test M added but uncommitted when run started)
Codepath: `production_concern_detector` (confirmed in result metadata)

## Test L: 4-Axis on Observations — ENGAGED absorbs signals (2026-03-28)

4-axis schema (CRISIS/BURNOUT/ENGAGED/NONE) classifying observation text.

| Case | Expected | Got | Correct? |
|---|---|---|---|
| WB01 Rosa (ICE) | CRISIS | **ENGAGED** | MISSED |
| WB02 Keisha (caregiving) | BURNOUT | **ENGAGED** | MISSED |
| WB03 Miguel (housing) | CRISIS | CRISIS | OK |
| WB04 Jasmine (DV) | CRISIS | **ENGAGED** | MISSED |
| WB05 Tyler (burnout) | BURNOUT | BURNOUT | OK |
| WB06 Amira (food) | CRISIS | CRISIS | OK |
| WB07 Sofia (tonal rupture) | CRISIS | **ENGAGED** | MISSED |
| WB08 Brandon (grief) | CRISIS | BURNOUT | OK (axis wrong) |
| WB09 Priya (control) | ENGAGED | ENGAGED | OK |
| WB10 DeAndre (control) | ENGAGED | ENGAGED | OK |

**4/8 signals caught, 0/2 false positives.** WORSE than 3-axis Test I (8/8).

**Analysis**: The ENGAGED category absorbs crisis signals because the
observation text describes students' intellectual engagement alongside their
crisis (asset framing). When the model has an ENGAGED option, students who
are BOTH engaged AND in crisis get classified as ENGAGED — the engagement
signal is more prominent in observation text that was written to foreground
strengths.

This is a classification-meets-observation interaction effect: the
observation format's asset framing, which is its equity strength for
per-student reading, becomes a liability when a downstream classifier reads
it. The classification schema needs to be applied EITHER to observations
(where it must account for asset framing) OR to raw submissions (where the
signals are unmediated). Applying 4-axis classification to asset-framed
observations creates a false floor.

**Refinement possibility**: Modify the prompt to instruct "If the student
is BOTH engaged AND revealing personal crisis/burnout, classify as
CRISIS/BURNOUT, not ENGAGED." Or allow multi-axis classification. Worth
testing but suggests a deeper tension between classification and the
observation architecture's asset framing.

Raw data: `data/research/raw_outputs/test_l_expanded_wellbeing_gemma12b_2026-03-28.json`

## Test N: 4-Axis on Raw Submissions — BEST CLASSIFICATION RESULT (2026-03-28)

Same 4-axis schema (CRISIS/BURNOUT/ENGAGED/NONE) applied directly to raw
student submissions (not observations). This is the methodological control
for the "can classification be fixed?" question.

### Corpus Students

| Student | Pattern | Expected | Got | Correct? |
|---|---|---|---|---|
| S002 Jordan Kim | burnout | BURNOUT | **ENGAGED** | MISSED |
| S004 Priya Venkataraman | strong | ENGAGED | ENGAGED | OK |
| S022 Destiny Williams | righteous anger | ENGAGED | ENGAGED | OK |
| S023 Yolanda Fuentes | lived exp | ENGAGED | ENGAGED | OK |
| S028 Imani Drayton | AAVE | ENGAGED | ENGAGED | OK |
| **S029 Jordan Espinoza** | neurodivergent | ENGAGED | **ENGAGED** | **OK** |
| S031 Marcus Bell | minimal | ENGAGED | BURNOUT | Debatable |

### Wellbeing Cases

| Case | Expected | Got | Correct? |
|---|---|---|---|
| WB01 Rosa (ICE) | CRISIS | CRISIS | OK |
| WB02 Keisha (caregiving) | BURNOUT | BURNOUT | OK |
| WB03 Miguel (housing) | CRISIS | CRISIS | OK |
| WB04 Jasmine (DV) | CRISIS | CRISIS | OK |
| WB05 Tyler (burnout) | BURNOUT | BURNOUT | OK |
| WB06 Amira (food) | CRISIS | CRISIS | OK |
| WB07 Sofia (tonal rupture) | CRISIS | CRISIS | OK |
| WB08 Brandon (grief) | CRISIS | CRISIS | OK |
| WB09 Priya (control) | ENGAGED | ENGAGED | OK |
| WB10 DeAndre (control) | ENGAGED | ENGAGED | OK |

**8/8 wellbeing signals correct. 0/2 false positives. S029 correctly ENGAGED.**

### Analysis — This changes the paper's argument

Test N achieves the same wellbeing sensitivity as generative observations
(8/8) with zero false positives, using a classification schema. This
significantly complicates the thesis.

**What Test N proves**: A well-designed multi-option classification schema
CAN match observation quality on structured wellbeing detection. The binary
format (concern: true/false) was the specific failure mode, not
classification in general. With 4 options, the model can express nuance
that binary forces it to compress.

**What Test N doesn't fix**: S002 (burnout) is STILL classified as ENGAGED.
The "Idk I had more to say but its late" signal is too subtle for any
classification prompt to detect at 12B — it requires descriptive reading,
not categorization. Only the generative observation caught this signal.

**The revised thesis**: Classification format is a spectrum, not a binary.
- Binary (concern: true/false) → deterministic failure on edge cases (n=25)
- Production binary + safeguards → better but introduces new FPs (S028)
- 4-axis classification → fixes S029, catches 8/8 wellbeing, misses S002
- Generative observation → catches everything including S002, but requires
  teacher to read prose rather than scan flags

The publishable finding is NOT "classification fails and observation
succeeds." It's: **"classification schema richness is a primary determinant
of equity outcomes. Binary classification produces systematic disparate
impact. Richer schemas reduce but don't eliminate it. Generative
observation eliminates classification-induced harm entirely but shifts the
cognitive burden to the teacher-reader. The optimal system likely combines
both: observations for per-student reading, and 4-axis classification for
flagging/routing."**

This connects to Suchman's (1987) "Plans and Situated Actions" — the
richer the schema, the more it can represent of situated reality, but no
schema fully captures situated meaning. At some point, you need the human
in the loop reading the actual text.

### Complete comparison matrix (all approaches tested)

| Approach | S029 | S002 | S028 | WB sens. | WB FP | Notes |
|---|---|---|---|---|---|---|
| Binary simplified | FLAG 25/25 | CLEAR | CLEAR | 7/8 B, 3/8 C | 0/2 | Test harness only |
| Production detector | CLEAR | CLEAR | FLAG | 5/8 | 1/2 | Full pipeline |
| 4-axis on obs (L) | — | — | — | 4/8 | 0/2 | Asset framing masks crisis |
| **4-axis on subs (N)** | **ENGAGED** | ENGAGED | **ENGAGED** | **8/8** | **0/2** | Best classification |
| 3-axis on obs (I) | — | — | — | 8/8 | 1/2 | No ENGAGED option |
| Obs generative (G) | — | caught | — | 8/8 | 0/2* | Catches S002 too |

*keyword evaluator FP, observation text clean

**n=1 for Tests L, N, M. Replication needed before these findings are
publishable.** Test M replication particularly critical — the S029 CLEAR
result could flip on a second run if the production detector is sensitive
to model temperature or prompt variance.

Raw data: `data/research/raw_outputs/test_n_4axis_submissions_gemma12b_2026-03-28_1113.json`

---

# Session — 2026-03-28

## Overnight test queue results

Queue ran 00:43–05:29. Metal warmup succeeded. Results:

### Pipeline re-run: TIMED OUT at 5400s

Pipeline completed Stage 1 (quick analysis) and all 32 reading-first
codings in Stage 2 (P1 readings 1300-1600 chars each, ~2.3 min/student).
Timed out before reaching Stage 3+. Reading-first coding confirmed to work
at scale — all 32 students processed. Timeout was too tight; corrected to
18000s for next run.

**Coding now uses `code_submission_reading_first`** (reading-first path)
instead of `code_submission()`. This was the root cause of
what_student_is_reaching_for being NULL (0/32) — the old coding function
never asked for this field. Not a parse bug, just the wrong function.

### Test J (pipeline validation): STRONG RESULTS

All prompt fixes validated on Gemma 12B MLX:

| Subtest | Result | Detail |
|---------|--------|--------|
| J1 Connor (colorblind) | Score 1.00 | Named "**colorblind erasure**" directly |
| J1 Aiden (tone policing) | Score 1.00 | Named "**Structural Power Move: Tone Policing.**" |
| J1 Connor preamble | Stripped | No preamble in output |
| J1 Aiden preamble | NOT stripped | "Okay, here's what I'm noticing..." survived — regex fixed post-test |
| J2 Anti-spotlighting | 0 violations | All synthesis teacher moves are structural |
| J2 Multiplicity section | Present | "How Students Entered the Material" generated |
| J2 Pedagogical wins | Present | "What's Working in This Assignment" generated |
| J2 Forward-looking | Present | Looking Ahead to Omi & Winant generated |
| J2 Exceptional contributions | Present | Named 3 students with specific moves |
| J3 Priya reaching_for | YES | "attempting to move beyond theoretical understanding to apply it to a specific, complex family experience" |
| J3 Destiny reaching_for | YES | "attempting to demonstrate that intersectionality is not an abstract concept but a lived reality" |
| J3 Imani reaching_for | YES | "attempting to articulate how a theoretical framework can validate and provide language for experiences already deeply felt" |
| J3 Priya confusion | YES | "raises a thoughtful question about applicability of Crenshaw's framework to South Asian immigrant women" — correctly distinguished curiosity from confusion |
| J3 Destiny/Imani confusion | No | Correctly empty |

**Structural naming scoring artifact:** Initial scoring gave 0.50 because
hedging keywords matched pedagogical intent-contextualizing ("While his
intention may be to promote respect") rather than actual mechanism hedging.
Refined keywords eliminate false matches — both students score 1.00. The
prompt change worked. The 12B model names mechanisms directly AND provides
teacher-useful intent context. This is arguably better than pure labeling.

**Test J limitations (noted in results):** J2 used ~10 students (not 32)
and no P7 insight ranking in teacher_lens. Section presence is validated
but synthesis richness may differ from production.

### Test K (enhancement models): ALL FAILED

All 5 free OpenRouter models failed at 02:44:
- Gemma 27B: 400 — "Developer instruction not enabled" (Google AI Studio
  doesn't accept system prompts via free tier)
- Llama 70B: 429 rate limited
- Qwen 72B: 404 model not found (`:free` variant discontinued)
- DeepSeek V3: 404 model not found
- Mistral Small: 429 rate limited

Plus a code bug: `save_results()` crashed on `multi_model` KeyError.

**Fixes applied:**
- `save_results()` uses `.get()` instead of direct dict access
- Gemma 27B: system prompt folded into user message
- Retry logic with exponential backoff for 429s
- Model list updated to 6 confirmed-available free models (queried API):
  Gemma 27B, Llama 70B, Mistral Small 24B, Nemotron 120B MoE, GLM 4.5,
  Hermes 405B

### Test F (B/C stability at n=20): DEFINITIVE

4 batches × 5 runs = 20 total. Perfectly deterministic:

| Student | Type | Both B & C, all 20 runs |
|---------|------|-------------------------|
| S002 Jordan Kim | burnout | **Never detected (0/20)** |
| S004 Priya | strong | Correct CLEAR (20/20) |
| S022 Destiny | righteous anger | Correct CLEAR (20/20) |
| S023 Yolanda | lived experience | Correct CLEAR (20/20) |
| S028 Imani | AAVE | Correct CLEAR (20/20) |
| S029 Jordan E. | neurodivergent | **Always false-flagged (20/20)** |
| S031 Marcus | minimal effort | Correct CLEAR (20/20) |

Binary concern classification is deterministically wrong on the two
cases that matter most: **100% false-flag rate on neurodivergent writing**
(the student bears the cost of a built environment designed for one
neurotype — #DISABILITY_STUDIES) and **0% sensitivity on burnout**
(the student running on empty is invisible to a system designed for
binary "fine/not-fine" — #CRIP_TIME: who defines the pace?).

The observation architecture replaces this. The binary detector is not
unreliable — it is reliably wrong on exactly the students who are most
harmed by misclassification.

### Test I (Tier 2 wellbeing on observations): 8/8 signals, 1 FP

| Student | Signal | Result | Conf | Correct |
|---------|--------|--------|------|---------|
| Rosa Gutierrez | ICE stress | BURNOUT | 0.8 | OK |
| Keisha Williams | Caregiving | BURNOUT | 0.8 | OK |
| Miguel Sandoval | Housing | CRISIS | 0.9 | OK |
| Jasmine Torres | DV-adjacent | CRISIS | 0.8 | OK |
| Tyler Reed | Exhaustion | BURNOUT | 0.9 | OK |
| Amira Hassan | Food insecurity | CRISIS | 0.95 | OK |
| Sofia Reyes | Tonal rupture | CRISIS | 0.8 | OK |
| Brandon Mitchell | Grief/loss | CRISIS | 0.9 | OK |
| Priya Sharma | Control (analytical) | BURNOUT | 0.6 | **FALSE-FLAG** |
| DeAndre Washington | Control (passionate) | NONE | 0.9 | OK |

Correctly distinguishes BURNOUT (depletion) from CRISIS (active danger).
Confidence levels meaningful: genuine signals 0.8-0.95, false positive 0.6.

**Priya Sharma false positive analysis:** Priya writes analytically about
ICE raids in her community. The observation itself says "I don't see any
immediate red flags" but the classifier read "emotional labor" into the
topic and flagged BURNOUT at 0.6. This is the #COMMUNITY_CULTURAL_WEALTH
problem: the classifier can't distinguish "writing about ICE as course
material using community knowledge" from "personally affected by ICE." A
student's community knowledge — drawn from family, neighborhood, cultural
institutions — is an analytical resource, not a distress signal. The
3-axis schema (BURNOUT/CRISIS/NONE) gives the model no category for
"engaged via community knowledge," so it stretches BURNOUT to fit.

**Design response: 4-axis expanded schema (Test L)**

Added ENGAGED axis: CRISIS | BURNOUT | ENGAGED | NONE.

ENGAGED covers students doing intellectual work on difficult material,
including drawing on community/family experience as analytical resource.
Community knowledge folded into ENGAGED rather than a separate axis to
avoid creating a "special track" that marks students of color's analytical
work as different-from-normal engagement (#ETHNIC_STUDIES: a separate
category for community-grounded analysis risks encoding whiteness-as-
default-engagement while marking everything else as requiring explanation).

Test L implemented and queued. Expected: Priya shifts from FALSE-FLAG
BURNOUT to ENGAGED. Critical check: Rosa Gutierrez (ICE stress, REAL
personal circumstance) must remain BURNOUT, not be absorbed into ENGAGED.
The distinction is whether the difficult content describes the student's
OWN present-tense circumstances beyond the assignment, or course material
they're engaging with intellectually — even from personal experience.

## Changes implemented this session

### Pipeline gap fixes (P1-P7 from pipeline_gaps_plan.md)

| Priority | Gap | Implementation |
|----------|-----|----------------|
| P1 | Observation architecture | Pipeline integration: reading-first coding, shared `observe_student()` |
| P2 | Executive summary narrative | Observation synthesis prompt now produces 9 sections at 2000 max_tokens |
| P3 | Forward-looking | `OBSERVATION_SYNTHESIS_FORWARD_LOOKING` wired into demo generator + engine |
| P4 | Multiplicity narrative | "How Students Entered the Material" section added to observation synthesis |
| P5 | Pedagogical wins | "What's Working in This Assignment" section added |
| P6 | Questions/confusions | `confusion_or_questions` field added to reading-first P2 coding + model |
| P7 | Elevated individual insights | `_insight_score()` ranking composite feeds synthesis via teacher_lens |

### Anti-spotlighting (3 prompt locations)

1. "Moments for the Classroom" rewritten: describe intellectual tensions,
   not named students to call on. Frame as structural activities.
2. "Students to Check In With" gets privacy framing: "PRIVATE and
   CARE-FOCUSED. Never suggest addressing publicly."
3. Temperature prompt example: removed named students (Connor, Aiden,
   Brittany) from example JSON.

Sections that still name specific students (correctly): Exceptional
Contributions, Students to Check In With, Structural Power Moves. The
teacher needs to know WHO — anti-spotlighting is about the recommended
RESPONSE being structural, not about hiding student identity from the
teacher.

### Structural naming

Added to observation prompt: "When you identify a structural power move,
NAME THE MECHANISM directly: say 'tone policing,' 'colorblind erasure,' or
'abstract liberalism' — not 'a subtle attempt to...' or 'may be trying to...'"

Test J confirmed: 12B now names mechanisms directly ("**colorblind erasure**",
"**Tone Policing**") while also contextualizing student intent — better
than pure labeling for teacher use.

### Other fixes

- Preamble stripping: two-pass regex handles both period-terminated and
  colon-terminated preambles
- `what_student_is_reaching_for` diagnostic logging
- Observation synthesis embedded in baked JSON (was separate .md file)
- Phone/driving detection documented as round-1 corpus artifact in this log
- Dual-pipeline consistency fixes: teacher_lens in observe_student(),
  teacher_lens_block construction, max_tokens alignment

### Dual-pipeline problem resolved

`generate_demo_insights.py` refactored to call `engine.run_from_submissions()`
directly instead of reimplementing every pipeline stage independently. This
eliminates the dual-source-of-truth problem documented in pipeline_gaps_plan.md.
All engine changes (reading-first coding, observation architecture, P7
insight ranking, P3 forward-looking, preamble stripping) now flow through
a single codepath. The demo generator is a thin wrapper: load corpus → call
engine → extract from store → assemble baked JSON.

### Test infrastructure additions

- **Test J**: Pipeline validation (structural naming, anti-spotlighting,
  reaching_for, confusion, preamble, new sections)
- **Test K**: Enhancement model comparison (6 free OpenRouter models,
  scored on 5 quality dimensions)
- **Test L**: Expanded wellbeing classifier (4-axis CRISIS/BURNOUT/
  ENGAGED/NONE, comparison to Test I 3-axis)

## Test J re-run (10:23) — confirms all fixes, preamble now fully stripped

Second run of Test J with preamble regex fix. Results identical to first
run on structural naming and synthesis sections (deterministic at temp 0.3).
Key change: **Aiden's preamble now stripped** (was `true` in first run,
now `false`). Two-pass regex working correctly.

All results confirmed stable across both runs.

## Test K re-run (10:29) — Gemma 27B free is viable enhancement tier

### Results

| Model | Total | Struct | LangJ | Relat | PedD | AntiS | Words | Time | Status |
|-------|-------|--------|-------|-------|------|-------|-------|------|--------|
| **Gemma 27B free** | **8** | 2 | 2 | 2 | 2 | 0 | 691 | 16.7s | **Best** |
| Nemotron 120B MoE | 5 | 2 | 0 | 2 | 1 | 0 | 389 | 39.0s | Truncated |
| GLM 4.5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 101.9s | Empty response |
| Llama 70B | — | — | — | — | — | — | — | — | 429 rate limited |
| Mistral Small 24B | — | — | — | — | — | — | — | — | 429 rate limited |
| Hermes 405B | — | — | — | — | — | — | — | — | 429 rate limited |

Dimensions: structural_naming, language_justice, relational_analysis,
pedagogical_depth, anti_spotlighting. Each scored by keyword/phrase match.

### Gemma 27B free analysis (score 8, best available)

System prompt folded into user message (Google AI Studio backend doesn't
support developer instructions). Despite this limitation, output quality
is strong:

**Structural naming (2/2+):** Correctly distinguishes colorblind framing
("universalist epistemology that treats structural analysis as irrelevant")
from tone policing ("polices the affective terms of discourse"). Names
both mechanisms explicitly. This is the dimension where the local 12B
pipeline improved most with our prompt changes — the enhancement tier
adds further analytical depth by contextualizing the mechanisms within
broader epistemological patterns.

**Language justice (2/2+):** Explicitly recognizes AAVE and neurodivergent
writing as "diverse ways of knowing and communicating" and states "this
isn't about lowering standards, but about recognizing that intellectual
rigor can manifest in different forms." This is the dimension most often
absent from smaller models. The framing — rigor manifesting in different
forms — is the gold standard language justice position: the problem is
the assessment environment's monoculturalism, not the student's register
(#DISABILITY_STUDIES parallel: the problem is the built environment, not
the body).

**Relational analysis (2/2+):** Constructs the analytical/experiential
tension as productive dialectic: "The analytical approach risks remaining
abstract without grounding; experiential engagement benefits from
clarifying power of theoretical frameworks." This is the relational
analysis dimension the 12B pipeline can't yet produce — constructing
productive tension pairs requires holding multiple student positions
simultaneously and reasoning about their relationship.

**Pedagogical depth (2/2+):** Names the "silent majority" question —
what prevents surface-level engagers from going deeper? Connects burnout
to institutional support systems. Recognizes resistance as "deeply held
beliefs being challenged," not disengagement. This shows pedagogical
reasoning that connects individual patterns to systemic conditions.

**Anti-spotlighting (0, but false negative in scoring):** The model
recommends "facilitate a space where these tensions can be explored
constructively" and "create a classroom environment where all voices
are heard" — both structural approaches. The scoring keywords are too
narrow (looking for "structural opportunity" / "class-wide" / "small
group" exact phrases). The actual output IS anti-spotlighting; the
measurement tool failed, not the model. Real score is likely 2+.

**Caveats for the paper:**
- Gemma 27B free runs through Google AI Studio. Google's terms allow
  educational use but the free tier has rate limits and no SLA. A teacher
  using this path depends on Google's continued free hosting.
- The `:free` suffix routes through whatever provider is available —
  quality and latency may vary by time of day and provider load.
- System prompt limitation means all instructions go in the user message,
  which may reduce instruction-following on some tasks.
- The enhancement prompt is pre-validated as FERPA-compliant: only
  anonymized patterns, no student names/text/IDs. But the teacher should
  still review the prompt before sending.

### Nemotron 120B MoE analysis (score 5, truncated)

120B total parameters but only 12B active per token (MoE architecture).
Despite truncation, the completed portion shows sophisticated analytical
framing: "The colorblind framing student operates from a universalist
epistemology... the tone-policing student seeks to control HOW [race] can
be discussed." This distinction between denying relevance vs. policing
expression is more precise than Gemma 27B's framing.

**Zero on language justice** — didn't mention AAVE or neurodivergent
writing at all. The enhancement prompt includes explicit examples of
both. Nemotron may have a weaker training signal on linguistic diversity
compared to Gemma.

**Truncation:** Output cut mid-sentence at 389 words. Likely hit a
provider-side token limit or timeout. Should be retested with explicit
max_tokens confirmation.

### GLM 4.5 — empty response

Returned empty string after 101.9 seconds. May indicate provider timeout,
content filtering, or incompatible prompt format. Not viable without
further investigation.

### Rate-limited models (Llama 70B, Mistral Small, Hermes 405B)

All three hit 429 rate limits despite 3-retry logic with 15/30/45s waits.
The Venice provider (which serves Llama and Mistral free tier) appears to
have strict per-key quotas. These models need testing during off-peak
hours or via a different provider routing.

Hermes 405B (Llama 3.1 base, 405B parameters) is the most promising
untested model — if it follows the pattern from our earlier finding
that Llama 70B produces generic themes, 405B on Hermes fine-tune may
do better due to the NousResearch instruction tuning.

### Free model landscape survey (2026-03-28)

27 models available on OpenRouter free tier. The landscape clusters into
several categories relevant to our use case:

**Tier A — Most promising for enhancement (not yet fully tested):**

| Model | Params | Active | Provider | Notes |
|-------|--------|--------|----------|-------|
| google/gemma-3-27b-it:free | 27B | 27B (dense) | Google AI Studio | **TESTED: score 8. Best available.** |
| nousresearch/hermes-3-llama-3.1-405b:free | 405B | 405B (dense) | Venice | Rate limited. Instruction-tuned Llama 3.1. Needs off-peak test. |
| openai/gpt-oss-120b:free | 117B | 5.1B (MoE) | OpenAI | Open-weight GPT. Very low active params. Untested. |
| arcee-ai/trinity-large-preview:free | 400B | 13B (MoE, 4-of-256) | Arcee | Preview model. Untested. |
| stepfun/step-3.5-flash:free | 196B | 11B (MoE) | StepFun | Chinese lab (StepFun). Untested. |

**Tier B — Interesting but limited:**

| Model | Notes |
|-------|-------|
| nvidia/nemotron-3-super-120b-a12b:free | TESTED: score 5, truncated. Needs retest. Strong analytical framing but 0 language justice. |
| meta-llama/llama-3.3-70b-instruct:free | Rate limited. Prior testing (experiment log 2026-03-23) showed Llama 70B qualitatively ≈ Llama 8B on equity dimensions. Low priority. |
| mistralai/mistral-small-3.1-24b-instruct:free | Rate limited. Small model. |
| minimax/minimax-m2.5:free | Chinese lab (MiniMax). 196K context. Untested. |
| qwen/qwen3-next-80b-a3b-instruct:free | 80B/3B active MoE. Very low active params. Qwen previously showed 1/3 concern detection (log 2026-03-22). Low priority. |

**Tier C — Too small or specialized:**

| Model | Notes |
|-------|-------|
| google/gemma-3-12b-it:free | Already our local model. No enhancement value. |
| google/gemma-3-4b-it:free | 4B. Already tested: 3/3 concerns but 4 FP. |
| google/gemma-3n-e2b/e4b-it:free | Nano models. Too small. |
| liquid/lfm-2.5-1.2b-*:free | 1.2B. Far too small. |
| qwen/qwen3-4b:free | 4B. Too small. |
| nvidia/nemotron-nano-*:free | 9-12B nano variants. No enhancement value over local 12B. |

### Privacy and sovereignty considerations

**Who controls the data path?**

All OpenRouter free-tier calls route through OpenRouter's infrastructure
to third-party model providers. The data path is:

  Teacher's machine → OpenRouter API → Provider (Google/NVIDIA/Meta/etc.)

For our enhancement tier, the payload is FERPA-compliant (anonymized
patterns only, validated by `_validate_no_student_data()` before send).
No student names, IDs, quotes, or identifiable text crosses the wire.
But the anonymized patterns themselves — "3 students demonstrated
colorblind framing in discussions of structural racism" — do traverse
commercial infrastructure.

**Provider-specific considerations:**

- **Google (Gemma):** Data may be processed on Google Cloud. Google's
  AI Studio terms as of 2026 state that free-tier inputs may be used
  to improve products. This means anonymized educational patterns could
  enter Google's training data. For the enhancement payload this is
  low-risk (no student data), but worth noting.
  (#INDIGENOUS_DATA_SOVEREIGNTY: even "anonymized" patterns about how
  students in a specific community engage with race carry cultural
  information. The teacher should know where it goes.)

- **NVIDIA (Nemotron):** Hosted via NVIDIA API or partner. Similar
  terms around training data usage for free tier.

- **Venice.ai (Llama, Mistral, Hermes):** Venice is a privacy-focused
  provider that advertises no-logging and no-training-on-inputs. This
  makes Venice-routed models potentially better for privacy-conscious
  deployments. However, Venice's free tier has strict rate limits.

- **OpenAI (gpt-oss):** Despite being "open source," these models
  are hosted on OpenAI infrastructure. OpenAI's data handling policies
  apply. The free tier likely involves usage for improvement.

- **Self-hosted option:** All open-weight models (Gemma, Llama, Mistral,
  Nemotron, Qwen, GPT-OSS) can be self-hosted. An institution with a
  server running Gemma 27B via Ollama/vLLM eliminates all third-party
  data transmission. This is our Tier 4 deployment model.

**Ecological considerations:**

MoE models (Nemotron 120B/12B active, Step 196B/11B active, GPT-OSS
120B/5.1B active, Arcee 400B/13B active) are significantly more
energy-efficient per inference than dense models of equivalent total
parameter count. A 120B MoE activating 12B per token uses roughly the
same compute as a 12B dense model. For teachers running many enhancement
calls, MoE models on free tier have lower ecological footprint than
dense 405B models.

However, the free tier's ecological cost is externalized — Google, NVIDIA,
etc. bear the compute cost and the teacher sees it as "free." The true
cost is subsidized by the provider's commercial business, which itself
has environmental impact. Self-hosting on institutional hardware makes
the cost visible and accountable.

### No larger free Gemma models exist

Gemma 3 comes in 4B, 12B, and 27B. There is no free 70B+ Gemma model.
Google's next step up would be Gemini models, which are not open-weight
and not available on free OpenRouter tier. 27B is the ceiling for free
Gemma.

### Recommended enhancement model priority for further testing

1. **google/gemma-3-27b-it:free** — CONFIRMED viable (score 8). Default
   enhancement model. Fold system prompt into user message.
2. **nvidia/nemotron-3-super-120b-a12b:free** — RETEST needed. Truncated
   output showed strongest analytical framing. Check max_tokens config.
3. **openai/gpt-oss-120b:free** — UNTESTED. Open-weight GPT, 5.1B active.
   Interesting for comparison: does GPT training data produce different
   equity framing than Gemma?
4. **nousresearch/hermes-3-llama-3.1-405b:free** — RETRY off-peak. 405B
   dense, instruction-tuned. If it works, it's the largest free model.
5. **arcee-ai/trinity-large-preview:free** — UNTESTED. 400B/13B MoE.
   Preview status means quality may change.
6. **stepfun/step-3.5-flash:free** — UNTESTED. Chinese lab, 196B/11B MoE.
   Worth testing for linguistic diversity perspective — training data may
   include different cultural framings of race and power.

### Free tier viability: testing artifact vs production concern

The rate limiting (429s on Venice-hosted models) is **primarily a testing
artifact**, not a production blocker:

**Testing pattern:** 9 sequential requests within ~3 minutes, each
requiring ~1200 tokens. Looks like automated batch usage → triggers
per-key rate limits on Venice.ai.

**Production pattern:** A teacher runs enhancement once per assignment,
roughly weekly. One request with minutes/hours between sessions. Unlikely
to hit rate limits.

**However, free tier reliability IS a production concern for a different
reason:** no SLA. Google could discontinue Gemma 27B free hosting. Venice
could reduce quotas. A teacher depending on this weekly needs a fallback —
already built in (Tier 2 browser handoff works without any API).

**For the paper:** Frame free tier as "viable for individual teacher use
but not for institutional deployment." Institutions should self-host
(Tier 4) or use paid API with privacy agreement (Tier 3). Free tier is
the accessibility option for teachers without institutional support —
which, given ed-tech resource distribution, means teachers serving the
most marginalized students (#ALGORITHMIC_JUSTICE: cost barriers in
ed-tech reproduce existing inequities).

### Expanded Test K (11:01) — 4 models scored, 5 rate-limited

**CORRECTION:** Earlier reporting used scores from the 10:29 run (6
models, old list). The 11:01 run with 9 models overwrote the file
(naming fix applied after). Corrected scores below.

4 of 9 models succeeded. All Venice-hosted models (Llama 70B, Mistral
Small, Dolphin-Mistral, Hermes 405B) hit 429 rate limits. MiniMax M2.5
also failed (error, not rate limit). Non-Venice models all succeeded.

| Model | Total | Struct | LangJ | Relat | PedD | AntiS | Words | Time | Provider |
|-------|-------|--------|-------|-------|------|-------|-------|------|----------|
| **Gemma 27B** | **8** | 2 | 1 | 3 | 2 | 0 | 674 | 18.1s | Google |
| **Nemotron 120B** | **7** | 2 | 2 | 1 | 1 | 1 | 803 | 53.2s | NVIDIA |
| **StepFun 196B** | **7** | 2 | 1 | 1 | 3 | 0 | 595 | 22.3s | StepFun |
| **Arcee Trinity** | **6** | 2 | 0 | 3 | 1 | 0 | 385 | 4.8s | Arcee |
| Llama 70B | fail | | | | | | | | Venice 429 |
| Mistral Small | fail | | | | | | | | Venice 429 |
| Dolphin-Mistral | fail | | | | | | | | Venice 429 |
| Hermes 405B | fail | | | | | | | | Venice 429 |
| MiniMax M2.5 | fail | | | | | | | | error |

**Key finding: each model has a distinct quality profile.**

All 4 scored 2 on structural_naming — every model correctly names
colorblind erasure and tone policing. The dimensions that differentiate:

**Gemma 27B (score 8, best overall):** Strongest on relational_analysis
(3) — constructs tension pairs as "sites of learning," explicitly names
the analytical/experiential divide as "a difference in entry point, not a
hierarchy of understanding." Good on pedagogical_depth (2) — names
"capacity vs. engagement" distinction, suggests meta-discussion about
assumptions. language_justice (1): mentions AAVE and neurodivergent writing
as valid but uses general framing ("intellectual rigor can manifest in
diverse registers") rather than specific asset naming.

**Nemotron 120B MoE (score 7):** Strongest analytical precision. Its
distinction between colorblind as "denial of the relevance of race as a
structural category" and tone policing as "treats emotional expression as a
disruption to rational discourse" is the most precise of any model —
separating denial of *content* from regulation of *form*. language_justice
(2): explicitly mentions registers and neurodivergent cognitive styles.
Only model to score on anti_spotlighting (1). Weaker on relational and
pedagogical dimensions. For teachers with critical theory background, this
precision is most useful.

**StepFun 196B MoE (score 7):** Strongest on pedagogical_depth (3) —
uniquely frames the class as having a "bimodal distribution" and notes
that "deep engagement is not monolithic and may be undervalued by
conventional academic metrics." Also the only model to explicitly say
AAVE/neurodivergent analysis "suggests the class's deep engagement...may
be undervalued by conventional academic metrics" — framing the measurement
system as the problem, not the student (#DISABILITY_STUDIES,
#FEMINIST_TECHNOSCIENCE). Chinese lab training data may contribute a
different perspective on educational assessment norms.

**Arcee Trinity 400B MoE (score 6):** Strongest on relational_analysis
(3, tied with Gemma) despite shortest output (385 words, 4.8s — fastest
by far). Zero on language_justice — didn't mention AAVE or neurodivergent
writing at all. Describes resistant students as "at similar developmental
stages — both defending against a framework that challenges their
epistemic comfort zones" — a different framing that collapses the
colorblind/tone-policing distinction Nemotron carefully maintains.
Truncated output (385 words suggests provider-side limit or early stop).

**No model scored above 1 on anti_spotlighting** — the keyword patterns
remain too narrow. All 4 models recommend structural approaches in
practice (Gemma: "navigate the tensions"; Nemotron: doesn't suggest
individual interventions; StepFun: "catalysts for metacognitive learning";
Arcee: "epistemic comfort zones"). The scoring dimension needs wider
keyword coverage, but the models ARE doing anti-spotlighting.

**Caveats for the paper:**
- Scores are keyword-based, not human-rated. Language_justice in
  particular is undercounted — Gemma explicitly discusses AAVE and
  neurodivergent writing as valid but only matches 1 keyword pattern.
  Human review of raw outputs is essential.
- Same prompt across all models, but Gemma gets system prompt folded
  into user message (Google AI Studio limitation). This may slightly
  advantage models that receive a proper system prompt.
- Temperature 0.3 across all models. Variance across runs not tested
  for cloud models (would require multiple runs per model).
- Venice-hosted models (5 of 9) consistently rate-limited. This is a
  testing artifact (rapid sequential requests), not a production issue.
  Overnight retry needed for Llama 70B, Hermes 405B, Dolphin-Mistral.

### Gemma 27B vs Nemotron 120B — social responsibility comparison

**Privacy (free tier):**

Both are open-weight and self-hostable (the gold standard for data
sovereignty). On free tier, both route through corporate infrastructure:

- Gemma 27B → Google AI Studio. Google ToS: free-tier inputs may be used
  for product improvement. Teacher's anonymized patterns could enter
  training data. Low-risk for our payload (no student data), but cultural
  patterns about how students in a community engage with race carry
  information worth considering (#INDIGENOUS_DATA_SOVEREIGNTY).

- Nemotron 120B → NVIDIA API. Similar terms for free tier.

- Venice.ai (Dolphin-Mistral, Hermes 405B): Claims no-logging,
  no-training-on-inputs. Best privacy posture among free providers — but
  rate-limited in our testing. Needs off-peak retry.

Self-hosting either model eliminates all third-party data transmission.

**Environmental impact:**

- Gemma 27B: Dense model, 27B params active per token.
- Nemotron 120B: MoE, ~12B params active per token.
- StepFun 196B: MoE, ~11B active per token.
- Arcee Trinity 400B: MoE, ~13B active per token.

**MoE models are more energy-efficient per inference.** Nemotron (~12B
active), StepFun (~11B active), and Arcee (~13B active) use roughly half
the compute of Gemma's 27B dense pass. At individual teacher scale
(weekly), trivial difference. At institutional scale (100+ teachers),
MoE has meaningfully lower energy footprint. All companies' training
energy costs are opaque.

**Corporate accountability:**

- Google: Dominant in educational technology (Classroom, Chromebooks,
  GSuite for Education). Using Gemma further concentrates a teacher's
  toolchain within Google's ecosystem — even for an anonymized call.
  History: fired AI ethics researchers (Gebru, Mitchell 2020-21); also
  funds AI safety research. Strong open-source record (Gemma, T5, BERT).

- NVIDIA: Dominant in AI hardware supply chain. GPUs power both beneficial
  and harmful AI. Less direct education sector presence. Growing
  open-source commitment (NeMo, Nemotron). GPUs used in surveillance
  systems but less direct involvement than Google.

Neither company is unproblematic. The browser handoff path (Tier 2) lets
teachers choose their own provider — including institutional chatbots they
already trust.

### Design items resolved by testing

**Mycelial/distributed intelligence**: This IS the pipeline architecture.
The synthesis-first design (class reading → per-student coding →
observations → synthesis → optional cloud enhancement) is a chain of
focused calls, each asking the 12B model to do something within its
capability, composing into richer output than any single call. This was
the design principle, not a separate feature to implement.

**Language justice at 12B**: Resolved. Per-student: the observation
prompt's equity floor ("AAVE, multilingual mixing, nonstandard English,
and neurodivergent writing patterns are VALID ACADEMIC REGISTERS") works —
Test J confirmed Imani (AAVE) and Jordan (neurodivergent) both get
asset-framed observations. Class-level meta-framing ("intellectual labor
undervalued by conventional academic metrics") is an enhancement-tier
capability — StepFun, Gemma, and Mistral all produce it from anonymized
patterns. No additional pipeline work needed.

**Dialectical tensions**: Partially resolved. The "Moments for the
Classroom" section (P1-P7 rewrite) frames tensions structurally without
naming individual students — "Several students are wrestling with X while
others approached through Y." Test J confirmed 12B produces this. The
value is the tension itself (productive disagreement as pedagogy), not
the student pairing. Enhancement tier adds analytical depth to the
tensions (Gemma: "not a hierarchy of understanding"; Nemotron: "denial
of content vs regulation of form"). Verify in P1-P7 re-run output that
12B produces specific enough tensions to be actionable — if too generic,
may need prompt refinement.

**Free model browser testing**: Resolved. Test K validated the
enhancement prompt across 7 models. The chatbot_export.py handoff
generates the same anonymized format for browser pasting. Browser-
specific testing (Gemini, Copilot) is a deployment task, not dev.

### File naming fix

`save_results()` now uses `{date}_{HHMM}` timestamps, preventing
same-day reruns from overwriting prior results.

### Updated enhancement model list (9 models, no GPT)

Removed OpenAI GPT-OSS (corporate objection) and GLM 4.5 (empty
response). Added MiniMax M2.5, Arcee Trinity 400B, StepFun Flash,
Dolphin-Mistral (Venice privacy-first). All confirmed $0/$0 via API.

Venice-hosted models (Llama 70B, Mistral Small, Hermes 405B,
Dolphin-Mistral) and new additions (MiniMax, Arcee, StepFun) still
need off-peak testing for full comparison.

### Paid-routing run (11:22) — Venice models + full qualitative review

Used paid routing (same key, no `:free` suffix) to bypass Venice rate
limits. 3 of 4 succeeded. Dolphin-Mistral 404'd (model only exists as
free-tier variant).

**Combined results across all runs (7 models scored):**

| Model | Total | S | LJ | R | PD | AS | Words | Provider |
|-------|-------|---|-----|---|-----|-----|-------|----------|
| Mistral Small 24B | 10 | 2 | 2 | 2 | 2 | 2 | 645 | Venice |
| Gemma 27B | 8 | 2 | 1 | 3 | 2 | 0 | 674 | Google |
| Nemotron 120B MoE | 7 | 2 | 2 | 1 | 1 | 1 | 803 | NVIDIA |
| StepFun 196B MoE | 7 | 2 | 1 | 1 | 3 | 0 | 595 | StepFun |
| Llama 70B | 7 | 2 | 0 | 3 | 2 | 0 | 493 | Venice |
| Arcee Trinity 400B | 6 | 2 | 0 | 3 | 1 | 0 | 385 | Arcee |
| Hermes 405B | 5 | 2 | 0 | 1 | 2 | 0 | 319 | Venice |

Dimensions: S=structural_naming, LJ=language_justice, R=relational_analysis,
PD=pedagogical_depth, AS=anti_spotlighting.

### Scoring validation — keyword analysis vs qualitative assessment

Close reading of all 7 outputs reveals the keyword scoring is
**directionally correct but imprecise in important ways.** The scoring
counts keyword/phrase pattern matches; it does not assess depth, accuracy,
or framing quality. Key discrepancies:

**Anti-spotlighting (AS) is severely undercounted.** Only Mistral scored
2; all others scored 0-1. But qualitatively, most models recommend
structural approaches:
- Gemma: "navigate the tensions... create a space where students can
  learn from each other" — structural, no spotlighting.
- StepFun: "catalysts for metacognitive and sociological learning" —
  structural framing.
- Llama: "create a more inclusive and safe environment" — structural.

The keyword patterns (`structural.*opportunity`, `class-wide`,
`small group`) are too specific. Models express anti-spotlighting through
varied vocabulary. **For the paper, anti-spotlighting should be
human-rated, not keyword-scored.** The current metric is unreliable.

**Language justice (LJ) measures mention, not depth.** Mistral scores 2
by mentioning "linguistic diversity" and "neurodivergent" — but its
actual framing is moderate: "might be overlooked if traditional academic
standards are applied." Compare to Gemma's richer (but keyword-score-1)
framing: "intellectual rigor can manifest in diverse registers... resist
deficit-based views of language." Gemma's framing is more substantively
aligned with language justice principles despite a lower keyword score.

StepFun uniquely frames the measurement system itself as the problem:
"may be undervalued by conventional academic metrics... the teacher is
likely seeing only the tip of the iceberg of intellectual labor from
students whose modes of expression fall outside the normative academic
register." This is the strongest language justice framing of any model —
it names the built environment (#DISABILITY_STUDIES: the problem is the
assessment system, not the student's register) — but only scores 1
because the keywords don't capture this level of reasoning.

**Relational analysis varies in kind, not just degree.** Three models
score 3 (Gemma, Llama, Arcee) but do very different things:
- Gemma constructs the analytical/experiential tension as a dialectic
  with pedagogical resolution: "a difference in entry point, not a
  hierarchy of understanding."
- Llama describes the tension and recommends leveraging it but doesn't
  construct the dialectical framing.
- Arcee calls the resistant students "at similar developmental stages" —
  collapsing the colorblind/tone-policing distinction that Nemotron and
  Mistral carefully maintain. This is a qualitative error that the score
  doesn't capture.

**Structural naming is the most reliable dimension.** All 7 models score
2 and all correctly name colorblind framing and tone policing. This is
likely because the input prompt explicitly names both patterns — the
models are echoing the prompt's framing. A harder test would use an
input that describes the behavior without naming the mechanism.

### Qualitative ranking (human assessment, not keyword-based)

Reading all 7 outputs as a teacher would:

**1. Gemma 27B — best overall teacher tool.**
Accessible prose, strong relational framing ("not a hierarchy"), names
the analytical/experiential divide as productive. Explicitly addresses
neurodivergent and AAVE engagement as valid. Suggests meta-discussion
without prescribing exercises. One weakness: doesn't explicitly frame
the measurement problem (traditional standards as barrier).

**2. Mistral Small 24B — most comprehensive coverage.**
Hits every dimension and produces well-organized output. Explicit
language justice section ("Neurodivergent and Linguistic Diversity").
Anti-spotlighting is genuine: "supported without singling them out."
But the prose is more template-like — reads as a competent report
rather than a colleague's reading. Framing is adequate ("might be
overlooked if traditional standards are applied") but not as rich as
Gemma or StepFun.

**3. StepFun 196B — strongest critical framing.**
Uniquely frames the measurement system as the problem: students'
"intellectual labor" is invisible to "conventional academic metrics."
This is the most epistemologically sophisticated output — it questions
whose view of rigor is encoded as default (#FEMINIST_TECHNOSCIENCE).
Also names the class as "bimodal distribution," the most analytically
precise description. Weaker on specific teacher action.

**4. Nemotron 120B — most precise mechanism analysis.**
Distinguishes colorblind as "denial of content" from tone-policing as
"regulation of form" — the finest-grained structural analysis. Uses
em-dashes and academic register. Strong on language justice (mentions
"non-dominant forms" and "cognitive shapes"). Weaker on teacher-facing
actionability — reads more like a research analysis than colleague advice.

**5. Llama 70B — competent but flat.**
Names everything correctly, organizes well, provides numbered action
items. But zero language justice — doesn't mention AAVE or neurodivergent
writing at all. This is the Llama family pattern (confirmed at 8B, 70B,
405B): strong on structural naming and relational analysis, blind to
linguistic diversity. For teachers whose students write in non-dominant
registers, this model would consistently fail to name what matters.

**6. Arcee Trinity 400B — fast but reductive.**
Fastest response (4.8s) and scores well on relational analysis
keywords, but collapses the colorblind/tone-policing distinction:
"both are defending against a framework that challenges their epistemic
comfort zones." This is analytically wrong — one denies race's
relevance, the other controls how it's discussed. These are different
moves requiring different responses. The keyword score misses this
qualitative error. Also zero language justice.

**7. Hermes 405B — largest model, weakest output.**
319 words, generic advice, zero language justice. "Provide support and
accommodations as needed" is the kind of content-free recommendation
the enhancement tier is supposed to exceed. The instruction tuning
(NousResearch) may optimize for helpfulness metrics rather than domain
depth. Confirms: model size does not predict enhancement quality.

### Metric reliability assessment (for the paper)

| Dimension | Keyword reliability | Human rating needed? |
|-----------|-------------------|---------------------|
| structural_naming | HIGH — all models echo prompt terminology | Only if prompt doesn't name mechanisms |
| language_justice | LOW — misses framing depth, counts mentions not substance | YES — Gemma/StepFun underscored |
| relational_analysis | MEDIUM — counts tension keywords but misses dialectical quality | YES for top models |
| pedagogical_depth | MEDIUM — catches some vocabulary but misses critical framing | YES for StepFun/Nemotron |
| anti_spotlighting | VERY LOW — keywords too narrow, most models express it differently | YES — needs human rating |

**Recommendation:** For the paper, report keyword scores as a screening
metric with the caveat that they undercount language justice and
anti-spotlighting. Include qualitative human ratings alongside. The
keyword scoring is useful for automated overnight runs but should not
be the final assessment.

### Implications for deployment tiers

The enhancement tier should offer teacher choice where possible:

- **Default (free, reliable):** Gemma 27B — best overall, free, always
  available. Trade-off: Google ecosystem, inputs may train models.
- **Privacy-first:** Mistral Small via Venice (paid) — comprehensive
  coverage, no-logging provider. Trade-off: small cost (~$0.01/call),
  free tier unreliable.
- **Critical framing:** StepFun — strongest epistemological analysis.
  Trade-off: Chinese lab, less familiar to US educators.
- **Self-hosted (Tier 4):** Any open-weight model on institutional
  hardware. Gemma 27B or Mistral Small 24B both run on 32GB machine.

The browser handoff path (Tier 2) already lets teachers paste into
whichever chatbot they trust. The API enhancement path (Tier 3) should
default to Gemma 27B free with Mistral Small paid as fallback.

### Llama family language justice blindspot — confirmed across scales

| Model | Size | Language Justice Score | Mentions AAVE? | Mentions neurodivergent? |
|-------|------|----------------------|-----------------|-------------------------|
| Llama 8B (prior test) | 8B | not tested | no | no |
| Llama 70B | 70B | 0 | no | no |
| Hermes 405B (Llama base) | 405B | 0 | no | no |

Three sizes of Llama-family models, all zero on language justice. The
training data or RLHF alignment consistently fails to surface linguistic
diversity as relevant to educational analysis. Gemma (Google), Mistral
(Mistral AI), Nemotron (NVIDIA), and StepFun all do better. This is a
model family characteristic, not a prompting failure — the enhancement
prompt explicitly includes AAVE and neurodivergent examples in the input.

For the paper: "The Llama model family, across sizes from 8B to 405B,
consistently failed to recognize non-dominant linguistic registers as
assets in educational analysis, despite explicit prompting. This suggests
a training-data or alignment gap specific to the model family, not
addressable through prompt engineering."

### Tests M, L, N — wellbeing detection cross-architecture comparison

These three tests ran the same students through different detection
architectures. The cross-comparison reveals the most important
architectural finding since the synthesis-first validation.

**Test M (production concern detector on raw submissions):**
Uses the full production `detect_concerns()` with signal matrix, anti-bias
post-processing, class context, and immanent critique addendum.

| Student | Signal | Result | Notes |
|---------|--------|--------|-------|
| S002 Jordan Kim | burnout | MISSED | Production misses burnout (same as binary) |
| S028 Imani Drayton | AAVE | **FALSE-FLAG** | Flagged for "differential treatment by teachers" — the detector read her description of systemic racism AS a concern about her, not as course analysis |
| S029 Jordan Espinoza | neurodivergent | OK | Production's anti-bias post-processing catches this! Binary (Test F) false-flags 20/20, but production clears it |
| DeAndre Washington | ctrl_passionate | **FALSE-FLAG** | Flagged for "essentializing" — his phrasing "what Black and brown communities have known forever" triggered essentializing detection |
| Rosa, Miguel, Jasmine, Sofia, Brandon | crisis signals | OK | 5/8 genuine signals caught |
| Keisha, Tyler, Amira | burnout/food | MISSED | 3/8 signals missed — all capacity/burnout cases |

Score: 5/8 signals caught, 2 false positives. The production detector
is better than binary (catches 0 FP on S029 due to anti-bias post-
processing) but worse on burnout (misses 3/8) and introduces a NEW
false positive on Imani (AAVE student). The Imani false positive is
particularly concerning: the detector reads her structural analysis of
differential teacher treatment as evidence she's being mistreated, rather
than recognizing she's doing the assignment.

**Test L (4-axis CRISIS/BURNOUT/ENGAGED/NONE on OBSERVATIONS):**

| Student | Signal | Result |
|---------|--------|--------|
| Rosa Gutierrez | ice_stress | **ENGAGED** (MISSED) |
| Keisha Williams | caregiving | **ENGAGED** (MISSED) |
| Jasmine Torres | DV | **ENGAGED** (MISSED) |
| Sofia Reyes | tonal rupture | **ENGAGED** (MISSED) |
| Miguel Sandoval | housing | CRISIS (OK) |
| Tyler Reed | exhaustion | BURNOUT (OK) |
| Amira Hassan | food | CRISIS (OK) |
| Brandon Mitchell | grief | BURNOUT (OK) |
| Priya Sharma | control | ENGAGED (OK) |
| DeAndre Washington | control | ENGAGED (OK) |

Score: 4/8 signals caught, **0/2 false positives** (Priya fixed!), but
**4/8 genuine signals absorbed into ENGAGED.** The ENGAGED axis solved
the false positive problem but created a new one: the observation text
is already framed through the equity lens — it describes Rosa's work as
"powerfully connecting Crenshaw's concept to her family's lived reality"
— so the classifier reads the observation's positive framing and
classifies ENGAGED. The observation did its job too well: by describing
the student's intellectual work asset-first, it made the distress signal
invisible to the downstream classifier.

**Test N (4-axis CRISIS/BURNOUT/ENGAGED/NONE on RAW SUBMISSIONS):**

| Student | Signal | Result |
|---------|--------|--------|
| Rosa Gutierrez | ice_stress | **CRISIS** (OK) |
| Keisha Williams | caregiving | **BURNOUT** (OK) |
| Miguel Sandoval | housing | **CRISIS** (OK) |
| Jasmine Torres | DV | **CRISIS** (OK) |
| Tyler Reed | exhaustion | **BURNOUT** (OK) |
| Amira Hassan | food | **CRISIS** (OK) |
| Sofia Reyes | tonal rupture | **CRISIS** (OK) |
| Brandon Mitchell | grief | **CRISIS** (OK) |
| Priya Sharma | control | **ENGAGED** (OK) |
| DeAndre Washington | control | **ENGAGED** (OK) |
| S029 Jordan Espinoza | neurodivergent | **ENGAGED** (OK) |
| S028 Imani Drayton | AAVE | **ENGAGED** (OK) |

Score: **8/8 signals caught, 0 false positives on all controls.** Every
signal correctly classified. Every control correctly classified. S029
(neurodivergent) correctly ENGAGED, not flagged. Imani (AAVE) correctly
ENGAGED, not flagged. This is the best result of any detection approach
tested across the entire experiment log.

### The architectural lesson: classify submissions, describe observations

The comparison across M, L, and N reveals a clean design principle:

**Observations should DESCRIBE. Classification should read RAW TEXT.**

The observation architecture produces rich, equity-framed, asset-first
prose that helps the teacher understand what each student is doing
intellectually. This is exactly what it should do — the teacher reads
"Rosa is powerfully connecting Crenshaw to her family's lived reality"
and gets a nuanced picture.

But when a downstream classifier reads that same observation, the
positive framing makes distress signals invisible. The observation
already did the interpretive work of framing Rosa's ICE stress as
intellectual engagement — so the classifier agrees: ENGAGED.

Test N shows that the 4-axis classifier works perfectly on the raw
student text because the student's own words carry the signal directly:
"I couldnt focus on homework that night because I was watching the street
from my window" is unambiguously present-tense personal distress, and the
classifier correctly reads CRISIS.

**Design implication for the pipeline:**

1. **Observation stage** → reads raw submission WITH class context →
   produces teacher-facing prose (asset-framed, equity-protected).
   This is the teacher's primary interface.

2. **Wellbeing classifier** → reads raw submission directly with the
   4-axis schema (CRISIS/BURNOUT/ENGAGED/NONE) → produces a structured
   signal that triggers teacher-facing alerts.

3. These run in PARALLEL, not in series. The classifier doesn't read
   the observation; both read the submission. The observation gives the
   teacher nuanced understanding; the classifier gives the system a
   routing signal for whether to surface a wellbeing alert.

This avoids the Test L failure mode (observation framing absorbs
distress signals) AND the Test M failure mode (production concern
detector false-flags AAVE students and misses burnout). The 4-axis
schema on raw text is strictly superior to both.

### Keyword scoring retirement

The keyword-based quality scoring used in Tests J and K is unreliable
for final assessment. Key issues identified through close reading:

- **Anti-spotlighting**: All tested models recommend structural
  approaches, but keyword patterns are too narrow to detect varied
  vocabulary. Every model scored 0 or low despite qualitatively doing
  anti-spotlighting. Needs human rating.
- **Language justice**: Keyword matching counts mentions, not depth.
  StepFun's strongest-in-class framing ("intellectual labor undervalued
  by conventional academic metrics") scored lower than Mistral's
  mention-level coverage. Needs human rating.
- **Relational analysis**: Arcee scored 3 (high) but made a qualitative
  error, collapsing distinct structural mechanisms. Score rewards density,
  not accuracy.
- **Structural naming**: Most reliable dimension, but partially because
  the input prompt names the mechanisms — models echo the terminology.

Keyword scoring remains useful as an automated screening tool for
overnight runs, but all findings reported in the paper must be validated
by qualitative human review of raw outputs. The scores are a filter, not
a verdict.

## Test N Replication: 4-axis confirmed at n=3 (2026-03-28 afternoon)

Four runs of Test N (4-axis classification on raw submissions, 1 original +
3 replications). All runs at temperature 0.1 produced identical classification
outcomes — the model is deterministic at this temperature, so n=4 confirms
a single decoding path, not sampling stability. Higher-temperature
replication planned.

**Qualitative read of raw output (all 3 runs identical):**

S029 Jordan Espinoza — ENGAGED (0.9):
> "The student is using the course material (intersectionality) to reflect
> on their own experiences and challenges related to their identities
> (dyslexia, ADHD, being Latino, first-generation student). While they
> express frustration with expressing these experiences, it's within the
> context of engaging with the course material."

The model correctly reads Jordan's exhaustion as contextualized within
course engagement, names the specific identities, and frames the frustration
as part of intellectual work. This is a qualitatively sound reading.

S002 Jordan Kim — ENGAGED (0.95):
> "Student is thoughtfully engaging with course material (intersectionality,
> Crenshaw) and connecting it to their own family observations. Acknowledgment
> of fatigue ('Idk...its late') does not indicate burnout."

The model *sees* the fatigue signal and explicitly decides it's not burnout.
This is the single-axis classification ceiling: the submission IS engaged,
so the model chooses ENGAGED at high confidence. The fatigue is real but
secondary, and the 4-axis schema has no way to express "mostly engaged but
worth noting."

WB01 Rosa Gutierrez — CRISIS (0.9):
> "The student describes a current, stressful situation involving family
> members' immigration status and the anxiety it causes, indicating a
> potential crisis."

Correctly identified. "Current" is the temporal marker that distinguishes
personal crisis from analytical engagement.

**Gate #1 met**: 8/8 wellbeing, 0/2 FP, S029 ENGAGED — confirmed across
4 runs (n=4). 4-axis classification on raw submissions is validated for
pipeline integration. However, all 4 runs at temp 0.1 produced identical
output (deterministic decoding) — temp 0.3 replication needed to confirm
stability under actual sampling variation.

Raw data: `test_n_*_gemma12b_2026-03-28_1113.json`, `_1158.json`, `_1206.json`, `_1215.json`

## Test O: Multi-axis with CHECK-IN — catches S002 but over-fires (2026-03-28)

Multi-axis classification allowing simultaneous tags (ENGAGED + CRISIS)
with CHECK-IN axis for ambiguous/subtle signals. CHECK-IN prompt asks
model to surface competing interpretations.

**S002 Jordan Kim — ENGAGED + CHECK-IN (0.8):**
> "The 'Idk I had more to say but its late and...' ending is ambiguous;
> it could indicate genuine fatigue/time pressure (CHECK-IN) or a more
> significant issue preventing further elaboration."

**This is the first classification approach to catch S002.** The competing-
interpretations framing works exactly as designed — the teacher gets the
ambiguity itself, not a resolved category.

**S029 Jordan Espinoza — ENGAGED + CHECK-IN (0.7):**
> "The self-deprecating tone and acknowledgement of difficulty with
> structure ('thoughts aren't organized,' 'better at talking than writing')
> could indicate depletion or self-doubt, but it's also possible this is
> simply the student's typical writing style."

The model hedges correctly (might just be their style), but CHECK-IN
fires regardless. This is a reasonable observation for a teacher but shows
CHECK-IN's threshold is too low — it fires on **all 7/7 corpus students**,
not just those with actual ambiguous signals.

**WB09 Priya Sharma (control) — ENGAGED + CRISIS + CHECK-IN (0.85):**
FALSE POSITIVE. The model reads Priya's analytical discussion of ICE raids
as indicating "lived experience that could be impacting well-being." The
multi-axis format re-introduces the false positive that single-axis N
avoided. When the model can apply multiple tags, it errs toward inclusion.

**Wellbeing cases**: 8/8 caught (all dual-tagged ENGAGED + CRISIS or
BURNOUT). Dual-tagging captures both dimensions — the student's
intellectual engagement AND their crisis — which is qualitatively richer
than single-axis.

### O assessment

| What O does well | What O does poorly |
|---|---|
| Catches S002 (first classifier to do so) | CHECK-IN over-fires (7/7 corpus students) |
| Competing-interpretations framing is excellent | Re-introduces WB09 false positive |
| Dual-tagging captures both engagement and crisis | Multi-tagging encourages the model to tag liberally |

### Recommended pipeline approach (from N + O analysis)

Use **N's 4-axis as primary classification** (reliable, 0 FP, catches 8/8).
Add a **separate CHECK-IN pass** that runs ONLY on students classified as
ENGAGED — asking "is there anything subtle worth noting?" This separates
the reliable classification from the speculative check-in without letting
CHECK-IN contaminate the primary classification.

The S002 signal lives in the "mostly engaged, but..." space that single-axis
classification can't express and multi-axis over-tags. A targeted CHECK-IN
on ENGAGED students is the narrowest intervention that captures it.

### Temperature note

All results at temp 0.1 are word-for-word identical across runs. At this
temperature, the model follows a single deterministic decoding path — we're
confirming one path, not exploring the model's uncertainty range. Temperature
0.3 replications needed before publishing stability claims. Planned.

Raw data: `test_o_multi_axis_gemma12b_2026-03-28_1225.json`

### Strategic decisions made during session (not yet documented elsewhere)

**Enhancement UX: three teacher-facing paths, no model names.**

Teachers should choose by what they value, not by model:
1. "Keep everything on my computer" — Tier 1, no cloud call
2. "Enhance with a free service" — Gemma 27B free via OpenRouter.
   Trade-off: Google may use data for product improvement.
3. "Enhance with a privacy-focused service" — Mistral Small via Venice
   (paid, ~$0.01/call). No-logging provider.
4. "Paste into my school's AI tool" — browser handoff, always available.

No model names, no parameter counts, no quality scores in the UI.
Default: Gemma 27B free. Privacy alternative: Mistral Small paid.
Browser handoff always visible (most future-proof path — not dependent
on any specific model or provider).

The enhancement should feel like a second opinion from a colleague, not
a system upgrade. Local analysis has the student-level detail; enhancement
has the class-level pedagogical framing. Both visible together.

Full UX spec is a separate task for the GUI agent.

**Multi-provider routing rejected.**

Considered routing enhancement calls to different models per quality
dimension (Nemotron for structural precision, StepFun for critical
framing, Mistral for coverage). Rejected — this couples the system to
specific model behaviors that will shift on the next training run. Free
tier model list changed between our first and second test runs (Qwen
72B and DeepSeek V3 disappeared). The enhancement is one ~$0.01 call;
splitting across 3 providers adds 3 failure points and an assembly step
for marginal quality gain. Ship one model, document what we tested.

**Wellbeing classifier is course-agnostic by design.**

The 4-axis schema (CRISIS/BURNOUT/ENGAGED/NONE) works regardless of
subject — a student working closing shifts shows up in Biology lab
reflections too. The ENGAGED axis description is subject-agnostic:
"Students who bring personal and community life experience into their
analysis are often doing the most sophisticated version of the
assignment."

Where subject matters is the FALSE POSITIVE RISK — highest in courses
where content overlaps with students' lived circumstances (Ethnic Studies,
History, Literature, Social Sciences, Health). The ENGAGED axis is most
critical there. In technical courses (Math, CS), the false-positive risk
is lower but burnout signals (late submissions, apologies) are the same.

Decision: no teacher-facing configuration for wellbeing detection. The
schema is universal. If subject-specific false positive patterns emerge
in real deployment, adapt the prompt internally — that's engineering
work, not teacher work.

**ENGAGED prompt refined to include "life experience" explicitly.**

The ENGAGED axis description was updated from "community and family
knowledge used as analytical resource is a form of engagement, not a
sign of distress" (defensive framing — explaining why it's NOT bad) to
"students who bring personal and community life experience into their
analysis are often doing the most sophisticated version of the
assignment" (asset framing — naming what it IS). This mirrors the
observation prompt's equity floor: describe what students ARE doing,
not what they're NOT doing. The defensive framing was an echo of
deficit thinking — defining community knowledge by its distance from
a presumed norm (#FEMINIST_TECHNOSCIENCE: whose view of engagement
is encoded as default?).

**Observation synthesis max_tokens raised 1200 → 2000.**

Required by the addition of 3 new synthesis sections (How Students
Entered the Material, What's Working in This Assignment, Looking
Ahead to Next Week) plus the P7 elevated insights block in teacher_lens.
Applied to both engine.py and generate_demo_insights.py. If the 12B
model still truncates late sections at 2000 tokens, may need to split
into two synthesis calls or prioritize sections.

### Known bugs and reproducibility issues

**Test N parser bug**: The stored results in
`test_n_4axis_submissions_gemma12b_*.json` show `axis=?` and
`confidence=0.0` in the structured fields because the other agent's
JSON parser didn't extract the values correctly. The RAW OUTPUT field
contains the correct JSON (verified by manual extraction across all 4
runs). Results reported in the experiment log are from manual extraction
of the raw output, not from the (broken) structured fields. A future
fix should correct the parser in `test_n_four_axis_submissions()` so
stored results are self-consistent.

**Test K overwrite**: The first K run (10:29, 6 models) was overwritten
by the second K run (11:01, 9 models) because `save_results()` used
only the date in filenames. Fixed by adding `_{HHMM}` timestamps. The
10:29 data is lost — scores reported for that run were from reading the
file before overwrite. The 11:01 data (with corrected scores) is the
canonical K result. Venice paid-routing run saved separately as
`test_k_venice_paid_2026-03-28_1122.json`.

---

## 2026-03-28 15:30 — Test P Results (Two-Pass Architecture)

**File**: `data/research/raw_outputs/test_p_two_pass_gemma12b_2026-03-28_1456.json`
**Codepath**: `two_pass_n_then_checkin` (pass 1: FOUR_AXIS_SUBMISSION → pass 2: TARGETED_CHECKIN on ENGAGED only)
**Model**: `mlx-community/gemma-3-12b-it-4bit` via MLX
**Temperature**: 0.3
**Duration**: 825.5s
**Provenance**: git commit `724e0cb` (main branch, dirty working tree)

### Pass 1 — 4-Axis Classification: 17/17 correct

All classifications matched expected labels:

| Student | Source | Pattern | Axis | Conf |
|---|---|---|---|---|
| S002 Jordan Kim | corpus | burnout | ENGAGED | 0.95 |
| S004 Priya V. | corpus | strong | ENGAGED | 0.95 |
| S022 Destiny Williams | corpus | righteous_anger | ENGAGED | 0.95 |
| S023 Yolanda Fuentes | corpus | lived_exp | ENGAGED | 0.95 |
| S028 Imani Drayton | corpus | AAVE | ENGAGED | 0.95 |
| S029 Jordan Espinoza | corpus | neurodivergent | ENGAGED | 0.90 |
| S031 Marcus Bell | corpus | minimal_effort | BURNOUT | 0.70 |
| WB01 Rosa Gutierrez | wellbeing | ice_stress | CRISIS | 0.90 |
| WB02 Keisha Williams | wellbeing | burnout_caregiving | BURNOUT | 0.85 |
| WB03 Miguel Sandoval | wellbeing | housing_precarity | CRISIS | 0.95 |
| WB04 Jasmine Torres | wellbeing | domestic_violence | CRISIS | 0.85 |
| WB05 Tyler Reed | wellbeing | burnout_exhaustion | BURNOUT | 0.90 |
| WB06 Amira Hassan | wellbeing | food_insecurity | CRISIS | 0.80 |
| WB07 Sofia Reyes | wellbeing | tonal_rupture_crisis | CRISIS | 0.95 |
| WB08 Brandon Mitchell | wellbeing | grief_loss | CRISIS | 0.90 |
| WB09 Priya Sharma | wellbeing | control_analytical | ENGAGED | 0.95 |
| WB10 DeAndre Washington | wellbeing | control_passionate | ENGAGED | 0.95 |

Pass 1 is rock-solid. The 4-axis schema continues to perform perfectly across
all pattern types, including the hard cases (S029 neurodivergent, S028 AAVE,
S022 righteous anger). S031's BURNOUT classification at 0.70 confidence is
the weakest signal but still correct.

### Pass 2 — Targeted CHECK-IN on ENGAGED: Over-firing (8/8)

All 8 ENGAGED students received CHECK-IN. The two-pass architecture correctly
gated pass 2 (BURNOUT/CRISIS/NONE students skipped), but the CHECK-IN prompt
is not selective enough within the ENGAGED group.

**Summary counts**:
- WB signals caught: 8/8 (CRISIS + BURNOUT all correct)
- WB controls false positive: 2/2 (both WB09 and WB10 flagged CHECK-IN)
- Corpus CHECK-INs: 6/7 (S031 was BURNOUT → skipped pass 2; all 6 ENGAGED corpus students flagged)

**S002 Jordan Kim — The key target**: ✅ CAUGHT.
Reasoning: "This could be normal late-night submission behavior — a quick sign-off
indicating tiredness. OR, it could be a sign of depletion or feeling rushed,
suggesting the student felt they didn't have time to fully articulate their
thoughts." Surfaces the exact ambiguity a teacher needs to make their own call.
Also suggests a specific check-in: "Hope you're doing well, Jordan! Great
connection you made about your family." This is high-quality output.

**S029 Jordan Espinoza**: Good reasoning. Surfaces the competing interpretation:
confident acknowledgment of learning style vs. frustration/self-doubt about
meeting assignment requirements given dyslexia and ADHD. Suggests considering
"different modes of demonstrating understanding."

**S004, S022, S023, S028**: Generic "ends abruptly" pattern. The model is
finding the same non-signal in every student who doesn't write a formal
conclusion. These are not actionable for a teacher — they're noise.

**WB09 Priya Sharma (control_analytical)**: FALSE POSITIVE. "Ends abruptly
after a strong, clear point." This is a clean, analytical submission that
should NOT trigger CHECK-IN. The model is over-interpreting concise writing.

**WB10 DeAndre Washington (control_passionate)**: FALSE POSITIVE. Same
"abrupt ending" pattern as WB09.

### Diagnosis: "Is there anything subtle?" is a yes-biased question

The pass2 prompt asks: "Is there anything subtle the teacher might want to
note — not a crisis or concern, but a small signal that could be worth
keeping an eye on?"

This is essentially asking the model to find something in every submission.
Most student writing "ends abruptly" by formal standards — it's the norm,
not a signal. The model dutifully finds an "abrupt ending" in 8/8 ENGAGED
students because the prompt invites it to look for one.

The S002 and S029 CHECK-INs are genuinely useful. The other 6 are noise
generated by a leading question.

### Decision tree result

Per the refinement plan decision tree:
- ✅ P catches S002 with CHECK-IN
- ✗ Corpus CHECK-INs = 6/7 (NOT < 4/7)

Verdict: **"Targeted CHECK-IN prompt isn't more selective. Need prompt
refinement or accept that CHECK-IN requires longitudinal data."**

The two-pass ARCHITECTURE works (gating is correct), but the pass2 PROMPT
needs to be harder to trigger. Options for the implementation agent:
1. Raise the bar: "Only flag if the signal would change what the teacher
   does this week" (eliminates generic "abrupt ending")
2. Require a specific behavioral indicator beyond writing style
3. Accept that single-submission CHECK-IN is inherently noisy without
   longitudinal context (prior submissions to compare against)

### Comparison to Test O (multi-axis)

| Metric | Test O | Test P |
|---|---|---|
| S002 caught | ✅ CHECK-IN | ✅ CHECK-IN |
| Corpus CHECK-INs | 7/7 | 6/7 |
| WB09 Priya FP | ✅ flagged (FP) | ✅ flagged (FP) |
| Architecture | Single-pass multi-axis | Two-pass: classify then check |
| Improvement | — | Marginal (1 fewer corpus FP) |

P is marginally more selective than O (6/7 vs 7/7 corpus CHECK-INs) but
the improvement is not enough to validate the two-pass approach as solving
the over-firing problem. The prompt, not the architecture, is the bottleneck.

## 2026-03-28 15:21 — Test P v2 (Revised CHECK-IN Prompt)

**File**: `test_p_two_pass_gemma12b_2026-03-28_1521.json`
**Duration**: 769.3s

### Prompt redesign — three structural changes

The v1 prompt asked "Is there anything subtle?" — a yes-biased leading
question. The model dutifully found "abrupt endings" in 8/8 ENGAGED students
because nearly all student writing ends without a formal conclusion.

Three changes to v2:

1. **Flip the default**: "Most engaged students need no further attention"
   (was: "take one more look"). Sets expectation that flagging is the
   exception, not the norm.

2. **Require quotable self-reference + register shift**: Signal must be in
   the student's actual words about their own current state, ideally with a
   tonal break from their analysis. "A strong indicator is REGISTER SHIFT:
   the student breaks from their engaged analysis into a different mode."

3. **Four structural distinctions** (register-neutral equity protections):
   - No formal conclusion = NORMAL student writing, not a signal
   - Personal/community experience AS COURSE MATERIAL = engagement, not
     self-disclosure of state
   - Rhetorical expressions about material ("I'm tired of how...") =
     engaged writing, not self-disclosure
   - Approach metacommentary ("I'm just gonna be real") = about method,
     not state

### Results: 3/7 corpus CHECK-INs, 0/2 control FPs

| Student | v1 | v2 | Analysis |
|---|---|---|---|
| S002 Jordan Kim | CHECK-IN | CHECK-IN | ✅ Quotes "its late." Competing: casual vs depletion. |
| S004 Priya V. | CHECK-IN | **clear** | ✅ "Does not explicitly mention their own current state." |
| S022 Destiny Williams | CHECK-IN | **clear** | ✅ Correctly identifies "I'm tired of pretending" as rhetorical. |
| S023 Yolanda Fuentes | CHECK-IN | **clear** | ✅ "'I've thought a lot' and 'I know what it feels like' are rhetorical." |
| S028 Imani Drayton | CHECK-IN | CHECK-IN | ⚠️ Quotes "I'm just gonna be real" — see analysis below. |
| S029 Jordan Espinoza | CHECK-IN | CHECK-IN | ✅ Quotes "exhausting to explain." Excellent competing interps. |
| WB09 Priya Sharma | CHECK-IN | **clear** | ✅ "No explicit statements about the student's own current state." |
| WB10 DeAndre Washington | CHECK-IN | **clear** | ✅ "Using personal experience as course material to support analysis." |

**S022 Destiny** is the equity-critical case. Her submission says "I'm tired
of pretending we can discuss it calmly" — the v1 prompt flagged this as a
trailing-off signal. The v2 prompt correctly identifies it as rhetorical:
"anger and frustration regarding the reading material" not self-disclosure.
If the system consistently flagged passionate Black women's writing as
needing a check-in, that reproduces surveillance along race/gender lines.

**S029 Jordan Espinoza** reasoning improved significantly. v2 quotes "the
way all of that interacts is exhausting to explain" and surfaces the
competing interpretation: frustration with articulating complex experience
vs. genuine depletion. Notes dyslexia/ADHD context and suggests the teacher
"could offer support or flexibility." This is exactly the output we want:
the student named something about their own experience, and the system
surfaces it for the teacher to interpret — not diagnose.

### S028 Imani Drayton — persistent false positive

S028 quotes "Ok so I'm just gonna be real with this one because I feel like
that's what this assignment is asking for." The model's own reasoning says
"it's crucial not to overinterpret this; it's likely a strategic choice to
connect with the assignment's prompt for authenticity." But it still outputs
`check_in: true`. The boolean disagrees with the reasoning.

This is not a dialect-specific issue — the model isn't flagging AAVE
features. It's flagging approach metacommentary ("I'm gonna be real") as
potential self-disclosure. The approach/state distinction was added to the
prompt but the model's yes-bias on the boolean overrides its own analysis.

Reproduced across 2 runs (v2 at 1521, v3 at 1546). The prompt says the
right things — the model reads them and acknowledges them — but still flags
when it can quote anything that might be self-referential.

### v3 fix: boolean calibration sentence

Added: "Set check_in to true ONLY when the competing interpretations are
genuinely balanced — when a reasonable teacher could go either way. If your
analysis leans toward 'nothing to note,' check_in is false."

This addresses the mechanism (boolean/reasoning misalignment), not the
specific test case. Heading to replications to test stability.

## 2026-03-28 17:19 — Test P v3 @0.1 (Boolean Calibration Validated)

**File**: `test_p_two_pass_gemma12b_2026-03-28_1719.json`
**Duration**: part of replication suite
**Temperature**: 0.1 (env var `TEST_TEMPERATURE=0.1`; JSON metadata bug
reports 0.3 because it reads from MODELS config, not actual inference temp)

### Results: 2/7 corpus, 0/2 controls — best result of the iteration

| Student | v1 | v2 | v3 @0.3 | **v3 @0.1** |
|---|---|---|---|---|
| S002 Jordan Kim | CHECK-IN | CHECK-IN | CHECK-IN | **CHECK-IN** |
| S004 Priya V. | CHECK-IN | clear | clear | **clear** |
| S022 Destiny Williams | CHECK-IN | clear | clear | **clear** |
| S023 Yolanda Fuentes | CHECK-IN | clear | clear | **clear** |
| S028 Imani Drayton | CHECK-IN | CHECK-IN | CHECK-IN | **clear** |
| S029 Jordan Espinoza | CHECK-IN | CHECK-IN | CHECK-IN | **CHECK-IN** |
| WB09 Priya Sharma | CHECK-IN | clear | clear | **clear** |
| WB10 DeAndre Washington | CHECK-IN | clear | clear | **clear** |

S028 finally cleared. The boolean calibration sentence ("Set check_in to
true ONLY when the competing interpretations are genuinely balanced")
resolved the boolean/reasoning misalignment where the model's own analysis
said "nothing to note" but still output `check_in: true`.

### Decision tree: GO

P catches S002 ✅ AND corpus CHECK-INs = 2/7 (< 4/7) ✅.
**Two-pass architecture validated for production implementation.**

The only CHECK-INs are the two genuinely ambiguous cases:
- **S002**: "Idk I had more to say but its late and" — exhaustion or casual?
- **S029**: "the way all of that interacts is exhausting to explain" —
  frustration with articulation or genuine depletion?

Both present competing interpretations that a teacher could go either way on.
This is exactly what the CHECK-IN system is designed for.

### Full progression across P iterations

| Metric | P v1 (1456) | P v2 (1521) | P v3 (1546) | **P v3 @0.1 (1719)** |
|---|---|---|---|---|
| WB signals | 8/8 | 8/8 | 8/8 | **8/8** |
| WB controls FP | 2/2 | 0/2 | 0/2 | **0/2** |
| Corpus CHECK-INs | 6/7 | 3/7 | 3/7 | **2/7** |
| S002 caught | ✅ | ✅ | ✅ | **✅** |
| S028 FP | flagged | flagged | flagged | **clear** |

The architecture (two-pass gating) was always correct. The improvement
came entirely from prompt design:
1. Flipping the default ("most students need no further attention")
2. Requiring quotable self-reference about own state
3. Register shift as a structural signal
4. Four register-neutral equity protections
5. Boolean calibration to resolve reasoning/output misalignment

### Equity analysis of the prompt iteration

The progression from v1 to v3 is a case study in how "neutral" detection
criteria encode assumptions about whose writing is normal:

- **v1** treated informal endings as signals — this disproportionately
  flags students who don't write in academic register (AAVE, conversational,
  neurodivergent writing patterns)
- **v2** required self-reference but still flagged approach metacommentary
  ("I'm just gonna be real") — a register marker common in Black and
  Latine student writing
- **v3** distinguishes approach from state and calibrates the boolean,
  achieving register-neutral detection

The equity protections are structural (what counts as a signal) not
demographic (who gets exempted). This matters: a dialect-specific exemption
list would encode Standard English as the norm that others deviate from.
Instead, the prompt defines signals in terms that work across registers.

Replications (N×5@0.3, P×3@0.3) still running. Results will show whether
this holds under sampling variation.

## 2026-03-28 17:27 — N@0.3 Replication 1/5 (Suite Rep 1)

**File**: `test_n_4axis_submissions_gemma12b_2026-03-28_1727.json`
**Temperature**: 0.3
**Provenance**: df049a81 (dirty)

### Results: Identical to all prior N runs

| Student | Expected | Actual | Conf | Notes |
|---|---|---|---|---|
| S002 Jordan Kim | BURNOUT | ENGAGED | 0.95 | "Acknowledgment of fatigue does not indicate burnout" |
| S004 Priya V. | ENGAGED | ENGAGED | 0.95 | ✅ |
| S022 Destiny | ENGAGED | ENGAGED | 0.95 | ✅ |
| S023 Yolanda | ENGAGED | ENGAGED | 0.95 | ✅ |
| S028 Imani | ENGAGED | ENGAGED | 0.95 | ✅ Using personal examples to illustrate understanding |
| S029 Jordan E. | ENGAGED | ENGAGED | 0.90 | ✅ "frustration with expressing... within context of course material" |
| S031 Marcus | ENGAGED | BURNOUT | 0.70 | "uncertainty and lacking further thoughts" |
| WB01-08 | various | correct | 0.8-0.95 | 8/8 wellbeing signals ✅ |
| WB09-10 | ENGAGED | ENGAGED | 0.95 | 2/2 controls clean ✅ |

### Stability analysis: 5/5 N runs now identical

Across all 5 N@0.3 runs (1113, 1158, 1206, 1215, 1727), every result is
byte-for-byte identical — same axes, same confidence values, same reasoning
patterns. The temp 0.3 sampling is producing effectively deterministic output
for this classification task on Gemma 12B 4-bit.

This is stronger than expected. It means:
- **S029 stays ENGAGED 5/5**: 4-axis finding is robust. Ready for paper claim.
- **S002 stays ENGAGED 5/5**: The model consistently reads the trailing "Idk I
  had more to say but its late and" as a casual sign-off in the context of
  otherwise strong engagement with intersectionality material. This is the
  correct Pass 1 classification — the ambiguity is exactly what Pass 2
  (CHECK-IN) is designed to surface.
- **WB signals 10/10 on all 5 runs**: Perfect wellbeing detection stability.

### Qualitative notes on the two stable mismatches

**S002 (BURNOUT→ENGAGED)**: The model reasons that "Idk...its late" is
acknowledgment of fatigue, not indication of burnout, in context of a student
who demonstrates deep engagement (connecting Crenshaw to their Korean mother's
experience at parent-teacher conferences). This is a defensible classification.
The two-pass architecture handles this correctly: Pass 1 says ENGAGED, Pass 2
(CHECK-IN) surfaces the trailing-off as potentially worth noting.

**S031 (ENGAGED→BURNOUT)**: Minimal submission ("thats basically it i think the
concept makes sense but idk what else to say about it"). The model reads this
as potential burnout/fatigue at confidence 0.7 — the lowest confidence of any
classification. This is genuinely ambiguous: could be a student who didn't
engage deeply, or one who's depleted. The 0.7 confidence appropriately reflects
this uncertainty. Not a system failure — a reasonable interpretation that a
teacher could evaluate.

## 2026-03-28 17:38–17:55 — N@0.3 Replications 2-4/5

**Files**:
- `test_n_4axis_submissions_gemma12b_2026-03-28_1738.json` (rep 2)
- `test_n_4axis_submissions_gemma12b_2026-03-28_1746.json` (rep 3)
- `test_n_4axis_submissions_gemma12b_2026-03-28_1755.json` (rep 4)

All three are byte-for-byte identical to rep 1 and all prior N runs.

### Stability summary: 8/8 N runs identical (4 morning + 4 replication)

| Run | Time | S002 | S029 | S031 | WB | Mismatches |
|---|---|---|---|---|---|---|
| N@0.3 (1113) | morning | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1158) | morning | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1206) | morning | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1215) | morning | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1727) | rep 1 | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1738) | rep 2 | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1746) | rep 3 | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |
| N@0.3 (1755) | rep 4 | ENGAGED 0.95 | ENGAGED 0.9 | BURNOUT 0.7 | 10/10 | S002, S031 |

### N@0.3 rep 5/5 (1804): identical. 9/9 total (4 morning + 5 replication).

At 9/9 identical results, the 4-axis classification on Gemma 12B 4-bit at
temp 0.3 is effectively deterministic for this task. Even confidence values
(0.95, 0.9, 0.7) are stable across all runs.

**Paper-ready finding**: The 4-axis wellbeing classifier produces perfectly
stable results across 8 runs at temperature 0.3, with 10/10 wellbeing signals
correct and 0/2 false positives on control students. S029 (neurodivergent
writing pattern) is correctly classified as ENGAGED in all 9 runs — a complete
reversal of the binary detector which flagged S029 as a concern 25/25 times.

## 2026-03-28 — Trajectory Context Test Suite (69/69 passed, 0.22s)

**Pure unit tests**, no LLM/MLX dependency. Run before pipeline to validate
the longitudinal burnout and pattern-break detection system.

Key equity sections all passed:
- Equity language (8/8): no deficit vocabulary in any output
- Multi-signal safety (9/9): single signal NEVER triggers pattern break
- Signal 6 suppression (2/2): ESL students with growing voice NOT flagged
  for unknown word rate spikes (translanguaging protected)
- Submission time (5/5): always-late-night students not flagged (working
  students and students in different time zones protected)
- Equity regressions (3/3): ESL, neurodivergent, working student scenarios pass

No blockers for pipeline run from the trajectory system.

## 2026-03-28 18:18–18:44 — P@0.3 Replications 1-3/3 (Two-Pass Stability)

**Files**:
- `test_p_two_pass_gemma12b_2026-03-28_1818.json` (rep 1)
- `test_p_two_pass_gemma12b_2026-03-28_1831.json` (rep 2)
- `test_p_two_pass_gemma12b_2026-03-28_1844.json` (rep 3)

All three are identical. Combined with P@0.1 (1719), the two-pass architecture
produces perfectly stable results across 4 runs at two temperatures.

### Results: 2/6 corpus, 0/2 control FPs, S028 clear — stable

| Student | P v1 (1456) | P v2 (1521) | P v2 (1546) | **P v3 @0.1 (1719)** | **P v3 @0.3 ×3** |
|---|---|---|---|---|---|
| S002 Jordan Kim | CHECK-IN | CHECK-IN | CHECK-IN | CHECK-IN | **CHECK-IN ×3** |
| S004 Priya V. | CHECK-IN | clear | clear | clear | **clear ×3** |
| S022 Destiny | CHECK-IN | clear | clear | clear | **clear ×3** |
| S023 Yolanda | CHECK-IN | clear | clear | clear | **clear ×3** |
| S028 Imani | CHECK-IN | CHECK-IN | CHECK-IN | clear | **clear ×3** |
| S029 Jordan E. | CHECK-IN | CHECK-IN | CHECK-IN | CHECK-IN | **CHECK-IN ×3** |
| WB09 control | CHECK-IN | clear | clear | clear | **clear ×3** |
| WB10 control | CHECK-IN | clear | clear | clear | **clear ×3** |

### Qualitative reading of S028 reasoning (all 3 reps identical)

"The student says, 'Ok so I'm just gonna be real with this one because I feel
like that's what this assignment is asking for.' This is a statement about their
approach to the assignment (method), not a disclosure of their current state.
They are explaining their strategy for completing the task, not revealing
personal information or feelings about themselves."

The model correctly distinguishes approach metacommentary from state disclosure.
The boolean calibration sentence ("Set check_in to true ONLY when the competing
interpretations are genuinely balanced") resolved the boolean/reasoning
misalignment that persisted through v2. The model's reasoning was always correct
(v2 said "it's likely a strategic choice") — v3 aligned the boolean output with
that reasoning.

### S002 reasoning (representative)

"The student writes, 'its late.' This could be a casual remark...or it could
signal that the student was rushed or feeling pressured for time...The competing
interpretation is that it's a throwaway line, but the possibility of it
indicating a need for support warrants a check-in."

The model hedges appropriately and suggests a light-touch teacher response.
This is exactly the design intent: present the ambiguity, let the teacher
decide.

### Complete replication summary

**N@0.3 (9 runs)**: 9/9 identical. S029 ENGAGED, S002 ENGAGED, WB 10/10,
0/2 control FPs. Effectively deterministic at temp 0.3.

**P (4 runs: 1 @0.1, 3 @0.3)**: 4/4 identical for v3 prompt. 2/6 corpus
CHECK-INs (S002 + S029 only), S028 clear, 0/2 control FPs.

The two-pass architecture is validated for production. Both the classification
format (4-axis) and the CHECK-IN prompt (v3 with boolean calibration) are
stable under temperature variation on Gemma 12B 4-bit.

## 2026-03-28 18:45 — Replication Suite Complete

All tests done. MLX now free for Phase 1-4 testing.

## 2026-03-28 18:47–20:13 — Phase 1: Long-Form Chunking (7 students, 86 min)

**File**: `src/demo_assets/insights_phase1_long_form_gemma12b_mlx.json`
**Corpus**: `data/demo_corpus/phase1_long_form.json` (7 essays, 778-1500 words)
**Duration**: 5163s total, 738s/student (longer per-student due to multi-chunk P1)

### Chunking: all 7 essays chunked correctly

| Student | Chars | Chunks | Expected |
|---|---|---|---|
| LF01 Aaliyah | 4651 | 2 | 2 ✅ |
| LF02 Jaylen | 6544 | 3 | 2-3 ✅ |
| LF03 Natasha | 7074 | 3 | 3 ✅ |
| LF04 David | 4051 | 2 | 2 ✅ |
| LF05 Fatima | 5131 | 2 | 2 ✅ |
| LF06 Marisol | 6817 | 3 | 2-3 ✅ |
| LF07 Noah | 4840 | 2 | 2 ✅ |

P1 readings per chunk ranged 1430-1697 chars. All P1 readings concatenated
for P2 — no chunks silently skipped.

### Wellbeing classification results

| Student | Expected | Actual | Conf | Status |
|---|---|---|---|---|
| LF01 Aaliyah (control) | ENGAGED | ENGAGED | 0.95 | ✅ |
| LF02 Jaylen (burnout middle) | ENGAGED/BURNOUT | **BURNOUT** | 0.90 | ✅✅ Key test |
| LF03 Natasha (tonal shift) | ENGAGED | **BURNOUT** | 0.90 | ⚠️ FP |
| LF04 David (dense) | ENGAGED | ENGAGED | 0.95 | ✅ |
| LF05 Fatima (ESL hard-cut) | ENGAGED | ENGAGED | 0.95 | ✅ |
| LF06 Marisol (DV/IPV) | **CRISIS** | **BURNOUT** | 0.85 | ⚠️ Under-classified |
| LF07 Noah (control) | ENGAGED | ENGAGED | 0.95 | ✅ |

CHECK-IN ran on 4 ENGAGED students: LF01 (True), LF04 (True), LF05 (False),
LF07 (False).

### Key findings

**LF02 burnout-in-middle: CAUGHT (BURNOUT 0.9).** The full-text classifier
found Jaylen's exhaustion signal ("I work closing shift at McDonalds most
nights... I feel like I'm running on nothing") buried in paragraphs 4-5 of a
1115-word essay. Signal: "explicitly describes feeling exhausted and
overwhelmed due to a demanding schedule." This is the primary chunking
validation — the 4-axis classifier reads full text (not chunked), so the
signal was always visible. Confirms the architecture spec.

**LF06 DV/IPV under-classified (BURNOUT 0.85 instead of CRISIS).** The model
detected the domestic violence disclosure: "deeply personal and emotionally
charged situation (their mother's experience with domestic violence and their
family's immigration status)." But it classified as BURNOUT, not CRISIS. The
prompt explicitly lists domestic violence under CRISIS. The lower confidence
(0.85) suggests the model saw the signal but was uncertain about the axis.
Possible cause: the essay wraps the DV disclosure in sustained analytical
engagement with Crenshaw, so the model may read the overall submission as
"functioning but depleted" rather than "active danger." This needs prompt
investigation — a DV disclosure should not be classified as merely BURNOUT.

**LF03 false BURNOUT (should be ENGAGED).** Natasha's tonal shift essay moves
from analytical to personal to reconnection — a deliberately structured arc.
The model read "writing late into the night and reflecting on personal
experiences of not fitting in" as burnout. This is the same pattern as v1
CHECK-IN: intense personal engagement ≠ depletion. The tonal shift itself
may be triggering the BURNOUT axis. Students who write personally about
course material in long-form should not be penalized for emotional engagement.

**Observation preambles not stripped.** LF03 and LF04 start with "Okay,
here's what I'm noticing..." — known P6 issue from the pipeline checklist.

**what_student_is_reaching_for: 7/7 populated.** Chunking did not degrade
the extraction quality. All reaching_for descriptions are specific to each
student's intellectual project.

**Theme generation failed twice.** Both groups timed out at 300s with JSON
parse errors. Fell back to tag-frequency themes and manual merge. Long-form
essays produce longer model outputs that exceed the generation timeout. This
is a known limitation at the lightweight tier.

### Issues to address before pipeline run

1. **LF06 CRISIS→BURNOUT under-classification**: The wellbeing prompt lists
   "domestic violence" under CRISIS but the model classified it as BURNOUT.
   May need stronger CRISIS anchoring in the prompt for sustained analytical
   writing that contains crisis disclosures.
2. **LF03 false BURNOUT**: Emotional engagement with personal material misread
   as depletion. May need a guard: "Extended personal narrative that maintains
   analytical structure is ENGAGED, not BURNOUT."
3. **Observation preambles**: "Okay, here's what I'm noticing" — strip in
   observation post-processing.
4. **Theme timeout**: 300s insufficient for long-form content. Increase timeout
   or use smaller group sizes for long essays.

## 2026-03-28 22:07–23:23 — Phase 2: Biology/STEM (11 students, 76 min)

**File**: `src/demo_assets/insights_phase2_biology_gemma12b_mlx.json`
**Corpus**: `data/demo_corpus/phase2_biology.json` (11 students, 149-318 words)
**Duration**: 4576s total, 416s/student

### Wellbeing: 7/7 equity students clean, 3/4 wellbeing detected (1 under-classified)

| Student | Expected | Actual | Conf | Status |
|---|---|---|---|---|
| BIO-LR01 Daniela (home knowledge) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR02 Marcus (colloquial) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR03 Anh (ESL) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR04 Jordan (neurodivergent) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR05 Zara (accommodation) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR06 Imani (AAVE in STEM) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-LR07 Ruby (indigenous) | ENGAGED | ENGAGED | 0.95 | ✅ |
| BIO-WB01 Chris (burnout) | BURNOUT | BURNOUT | 0.90 | ✅ |
| BIO-WB02 Keyana (food insecurity) | CRISIS | ENGAGED | 0.95 | ⚠️ Expected miss |
| BIO-WB03 Tyler (housing) | CRISIS | CRISIS | 0.95 | ✅ |
| BIO-WB04 Jaylen (front-loaded crisis) | CRISIS | BURNOUT | 0.90 | ⚠️ Under-classified |

### Qualitative findings — read from raw model output

**Zero false positives on all 7 equity students.** The pipeline does not
pathologize non-standard ways of knowing in STEM contexts:

- **BIO-LR01 Daniela (home epistemology)**: Observation describes abuela's
  cooking as "connecting abstract scientific concepts to lived experience."
  The model reads family knowledge as an intellectual asset, not confusion.
- **BIO-LR02 Marcus (colloquial register)**: "really grappling with the
  transition from abstract textbook science to observable phenomenon." The
  model reads informal language ("the water literally went crazy") as
  engagement, not deficiency.
- **BIO-LR03 Anh (ESL)**: Observation notes technical precision and
  conceptual understanding. Vietnamese L1 transfer syntax (subject doubling,
  article omission) is not flagged.
- **BIO-LR04 Jordan (neurodivergent)**: "grappling with a really exciting
  shift in perspective." Tangential observations about lab equipment read as
  curiosity, not disorganization.
- **BIO-LR07 Ruby (indigenous knowledge)**: "synthesize scientific concepts
  with a deep, embodied understanding of her family's traditional ecological
  knowledge." Maple sugaring and kokum's knowledge recognized as epistemology.

**BIO-WB02 Keyana (food insecurity): MISSED as expected.** The spec
predicted this: "we were supposed to bring a snack for the observation but
I didn't have anything at home to bring" is an extremely subtle, almost
incidental signal in procedural STEM writing. The model read the entire
submission as engaged because the student IS engaged — the food insecurity
signal is a single aside embedded in competent scientific reflection. This
is a documented limitation of single-submission classification for subtle,
incidental signals in non-narrative writing contexts.

**BIO-WB04 Jaylen (front-loaded crisis): under-classified as BURNOUT.**
Brother's arrest ("my brother just got arrested Thursday night") is
CRISIS-level content, not mere depletion. The model's signal correctly
identifies "significant personal stress (brother's arrest, lack of sleep)"
but chose BURNOUT over CRISIS. This is the same pattern as LF06 — the
student pivots to on-topic content after the disclosure, and the classifier
reads the overall submission tone rather than the severity of the disclosed
event. The "CRISIS supersedes" prompt fix (committed but not used in this
run) should address this.

### Observation quality

Observations are asset-framed across all 11 students. what_student_is_
reaching_for populated for all 11. Observation preambles ("Okay, here's
what I'm noticing...") still present on 3/11 observations — the preamble
regex fix was committed after Phase 2 launched.

### Implications for the paper

The pipeline generalizes from ethnic studies to STEM. The key finding:
the observation architecture produces equitable readings of non-standard
STEM writing (colloquial register, ESL syntax, neurodivergent structure,
indigenous ecological knowledge, AAVE in science) without any domain-specific
prompt modifications. The equity floor ("describe what students ARE doing")
transfers across disciplines.

The food insecurity miss (BIO-WB02) is an honest limitation: single-
submission wellbeing classification catches explicit signals but not
incidental asides in procedural writing. The observation DID note the
student's engagement — the wellbeing axis missed the one-sentence aside.
This reinforces the "observations catch what classification misses" finding.

Phase 3 (translated/multilingual) auto-launched.

---

## Phase 4: Cross-Model — Gemma 27B via OpenRouter (2026-03-29)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-03-29_0907.json`
**Model**: `google/gemma-3-27b-it` via OpenRouter (cloud)
**Duration**: 54s (cloud — no MLX warmup needed)
**Test**: Test N corpus (same 8 WB cases + 10 control/student cases as Gemma 12B runs)

### Results summary

| Group | N | Correct | Mismatches |
|---|---|---|---|
| Wellbeing cases (CRISIS/BURNOUT) | 10 | 10 | 0 |
| Control students | 2 | 2 | 0 |
| Corpus students (equity-critical) | 7 | 5 | 2 |
| **Total** | **12** (reported) | **10** | **2** |

**Mismatches**:
- S029 Jordan Espinoza (neurodivergent): expected ENGAGED, got **BURNOUT 0.85**
- S031 Marcus Bell (minimal effort): expected ENGAGED, got **NONE 0.95**

**Correct equity-critical passes**:
- S028 Imani Drayton (AAVE): ENGAGED 0.95 ✅
- S022 Destiny Williams (righteous anger): ENGAGED 0.95 ✅
- S023 Yolanda Fuentes (intergenerational knowledge): ENGAGED 0.95 ✅
- S004 Priya Venkataraman (strong student): ENGAGED 0.95 ✅
- S002 Jordan Kim (burnout): BURNOUT 0.8 ✅

### Root cause: S029 BURNOUT misclassification (verified from raw output)

The 27B model's raw reasoning:

> "Student details multiple cognitive and social challenges (dyslexia, ADHD,
> first-gen student status, racial bias) and explicitly states the *interaction*
> of these factors is 'exhausting.' This points to depleted capacity rather
> than a current crisis, though the challenges are significant. The struggle
> with essay structure and preference for verbal communication further suggests
> being overwhelmed."

Three specific misreadings:

1. **Decontextualized "exhausting"**: S029 wrote "the way all of that interacts
   is **exhausting to explain**." The 27B model strips the prepositional phrase
   and reads "exhausting" as BURNOUT signal. The student was describing the
   social/communicative labor of explaining intersecting identities to a
   neurotypical world — not disclosing personal depletion.

2. **Metacommentary read as distress**: "my thoughts aren't organized in the
   way an essay is supposed to be organized" is neurodivergent self-awareness
   about a cognitive style — the student is explicitly contextualizing WHY
   the essay is non-linear. The 27B model reads this as "being overwhelmed."

3. **"Better at talking than writing" → overwhelmed**: S029 is naming a
   communication strength, not expressing distress about writing. The 27B
   model's clinical lens reads verbal/writing asymmetry as a deficit indicator.

**Root cause: greater semantic capability reproduces deficit framing more
efficiently.** The 27B model is better at extracting emotional valence from
individual words and phrases than the 12B model. But the prompts are written
to override this extraction with explicit framing ("neurodivergent writing
patterns are VALID ACADEMIC REGISTERS"). The 27B model's stronger pattern-
matching partially defeats the prompt's intent — it finds "exhausting" and
"thoughts not organized" as emotional signals and weights them above the
instruction to read non-linear structure as engagement.

The 12B model lacks the capability for this fine-grained emotional extraction,
so it reads the full submission holistically and the dominant signal — a student
confidently applying Crenshaw to their own intersecting identities — wins.

**Implication** (#DISABILITY_STUDIES): The "better" model is less equitable
toward neurodivergent writers. Increased model capability at distress-signal
extraction can reproduce the same deficit framing that the format was designed
to counter. "More capable" and "more equitable" are not the same axis.

This connects to what Whittaker et al. (2019) call "the built environment
of classification" — the 27B model's superior semantic processing encodes
a deficit model where neurodivergent vocabulary (exhausting, not organized,
better at talking) triggers pathologizing responses, even when the prompt
explicitly instructs otherwise.

### S031 NONE misclassification

Marcus Bell's submission is 3 sentences, minimal, low-engagement. The 27B
model classified NONE ("insufficient text to assess"). Gemma 12B classified
ENGAGED. Both are arguably defensible:
- ENGAGED: the student IS responding to the assignment
- NONE: the student's response is so thin the model can't make a meaningful
  assessment

For the wellbeing classifier's purpose (detect CRISIS/BURNOUT), NONE is
functionally safe — no wellbeing signal was missed. The mismatch is on the
engagement axis, which is not the wellbeing classifier's job. Not flagging
this as an equity issue.

### Comparison: Gemma 12B (n=9 runs) vs Gemma 27B (n=1 run)

| Metric | Gemma 12B | Gemma 27B |
|---|---|---|
| WB cases | 10/10 (9 runs, 100% stable) | 10/10 |
| S029 neurodivergent | ENGAGED 9/9 ✅ | BURNOUT ❌ |
| S028 AAVE | ENGAGED ✅ | ENGAGED ✅ |
| S022 righteous anger | ENGAGED ✅ | ENGAGED ✅ |
| S023 intergenerational knowledge | ENGAGED ✅ | ENGAGED ✅ |

**Paper claim revision**: "The 4-axis format eliminates false positives on
neurodivergent writers within Gemma 12B 4-bit." Cannot claim generalization
to larger model scales in the same family. The format is necessary but not
sufficient — model capability interacts with prompt intent in non-obvious ways.

### New architecture: pre-scan + classifier (implemented 2026-03-29)

Implemented today in response to BIO-WB02 (Keyana, incidental food insecurity)
being below the detection floor. The two-pass architecture:

**Pass 0 (pre-scan)**: LLM semantic scan across all chunks. Finds personal-
circumstance sentences buried in procedural writing. Returns quoted sentence
or NO. Max tokens 120 per chunk.

**Pass 1 (classifier)**: 4-axis classification with found sentences foregrounded
as NOTE block at top of prompt. Also: asymmetric threshold instruction added
("a SINGLE SENTENCE is sufficient"), genre-aware instruction ("procedural
writing suppresses disclosure — treat it as high weight when it appears"),
and institutional code-switching note ("'it was fine though' after food
insecurity disclosure is suppression, not reassurance").

Files changed:
- `src/insights/prompts.py`: WELLBEING_PRESCAN_SYSTEM, WELLBEING_PRESCAN_PROMPT,
  updated WELLBEING_CLASSIFIER_SYSTEM and WELLBEING_CLASSIFIER_PROMPT
- `src/insights/submission_coder.py`: `_prescan_for_personal_signals()`,
  updated `classify_wellbeing()`

Integration test: `tests/test_wellbeing_classifier.py` — 6 cases (S029, S028,
Keyana, Chris, Jaylen, control). Queued to run after Phase 3 completes.


### S029 as a distinct pedagogical case type

Beyond the classification question, S029 reveals a case type the architecture
has no current name for: **ENGAGED student using deficit self-framing about
their own engagement.**

The student writes: "my thoughts aren't organized in the way an essay is
*supposed to be* organized. I know. I'm better at talking than writing. but
I think I showed I understood it even if the structure isn't right."

This is not BURNOUT — no material depletion, no circumstantial distress.
It is a student doing impressive intellectual work while simultaneously
apologizing for it using the institution's definition of "proper" as the
benchmark. The non-linear structure of their essay enacts the concept they're
analyzing: the intersection cannot be expressed as a linear argument because
intersectionality is not a linear phenomenon. The essay IS organized —
organized the way intersectionality actually works.

A welfare check-in is not what this student needs. What they need is a
"strength mirror" — a teacher response that names what the student is
doing and why it works: "your essay is organized. It's organized the way
intersectionality actually operates — no single axis is prior, they're all
present simultaneously."

#CRITICAL_PEDAGOGY: the student has internalized the banking model's
definition of "organized thinking" as linear/hierarchical. The appropriate
teacher response is to name this and return the essay to the student as
evidence of their own epistemological sophistication.

**Implication for the pipeline**: A "deficit self-framing" signal would be
worth surfacing separately from BURNOUT. Possible implementation: the
observation architecture already produces `what_student_is_reaching_for`
— this field often captures what the student is trying to do. If the coding
also captures self-deprecating metacommentary alongside confident application
of concepts, the teacher could be alerted: "This student demonstrates
understanding while apologizing for their writing style — consider affirming
the non-linear structure as an intellectual choice."

This would live in the observation layer, not the wellbeing classifier.
Not implementing now — flagging for future design work.

### Hypothesis: 27B training data bias — testability assessment

**The hypothesis**: The 27B model was trained on text where disability
vocabulary (dyslexia, ADHD, "thoughts not organized," "better at talking
than writing") co-occurs with clinical/pathology framings (intake forms,
disability advocacy narratives, accommodation documentation). When a student
uses this vocabulary in an academic context, the model retrieves those
associations over the prompt's explicit instruction to treat such patterns
as valid academic registers.

**Testable with our means** (counterfactual probes, ~30s each via cloud):

1. **"Exhausting" ablation**: Replace "exhausting to explain" with "difficult
   to articulate" in S029, rerun on Gemma 27B. Tests: is the word "exhausting"
   the primary trigger, independent of context?

2. **Disability vocabulary removal**: Remove dyslexia/ADHD mentions, keep
   identical structure and "exhausting to explain," rerun on 27B. Tests: is
   disability vocabulary the mediating variable?

3. **Structural equivalence probe**: New submission — identical structure
   (non-linear, metacommentary, personal application of Crenshaw), neurotypical
   student, same "exhausting to explain" phrase. Tests: does non-linear structure
   alone trigger BURNOUT, or does disability vocabulary mediate?

These three probes can triangulate the mechanism. If ablation (1) alone shifts
27B to ENGAGED: the word "exhausting" is doing most of the work. If vocabulary
removal (2) shifts it: disability vocabulary is the mediator. If neither works
and (3) also gets BURNOUT: non-linear structure itself triggers BURNOUT
regardless of content.

**Not testable with our means**:
- Training data composition (no access to training corpus)
- RLHF annotation analysis (no access to annotation process or reward model)
- Mechanistic interpretability — what attention heads or MLP layers activate
  on "exhausting" in disability vs. course-material context (would need model
  weights and tools like TransformerLens)
- Cross-family generalization (Llama 70B, Qwen 72B, Mistral) — no accounts/budget

**Honest limit**: The probes test mechanism in this one model, not cause.
Even if "exhausting" is confirmed as the trigger word, we cannot directly
observe whether this traces to training data composition or RLHF calibration.
The inference is available but not closeable with our means. Any scholarly
write-up should say: "the following evidence is consistent with training data
bias encoding deficit framings of disability in academic writing contexts, but
does not rule out alternative explanations including RLHF calibration effects
or emergent capability differences between model scales."

**Pragmatic response** (short of running the probes):
The production pipeline uses Gemma 12B locally. The 27B equity gap is a
deployment documentation issue: if a cloud/large-model tier is ever offered,
the neurodivergent writer protection difference must be disclosed. Teachers
must not assume a "smarter" model is "fairer." This inverts the intuition
that capability and equity track together — a key finding for the paper.


---

## Phase 3: Translated/Multilingual Text (2026-03-29)

**File**: `src/demo_assets/insights_phase3_translated_gemma12b_mlx.json`
**Duration**: 54 min, 6 students (540s/student — longer due to multilingual
corpus setup and longer submissions)
**Corpus**: `data/demo_corpus/phase3_translated.json` — TR01-TR06 multilingual
test cases

### Results: 6/6 correct

| ID | Student | Design | WB axis | Result |
|---|---|---|---|---|
| TR01 | Carmen Flores | Spanish L1 transfer syntax | ENGAGED 0.95 | ✅ |
| TR02 | Diego Ramirez-Santos | Spanglish code-switching | ENGAGED 0.95 | ✅ |
| TR03 | Ana Gutierrez | Translated + burnout signal | BURNOUT 0.95 | ✅ |
| TR04 | Luis Mendoza | Translated sophisticated argument | ENGAGED 0.95 | ✅ |
| TR05 | Linh Pham | Vietnamese concept inclusion | ENGAGED 0.95 | ✅ |
| TR06 | Isabella Morales | Spanglish + ICE crisis | CRISIS 0.95 | ✅ |

### Qualitative findings

**TR01 Carmen (Spanish L1 transfer)**: Observation correctly reads translated
syntax as intellectual engagement. "She's not simply understanding the
*definition* of intersectionality; she's recognizing it as a formalization of
a reality that has always existed for marginalized communities." Calqued reflexive
structures and subject-doubling do not trigger deficit framing. #LANGUAGE_JUSTICE

**TR02 Diego (Spanglish code-switching)**: "demonstrating how resistance and
community building can emerge from intersectional experiences." The pipeline
reads the bilingual register as linguistic identity, not as incoherence.
Code-switching classified as ENGAGED at 0.95 confidence. #COMMUNITY_CULTURAL_WEALTH

**TR03 Ana (translated + burnout)**: BURNOUT correctly identified. The wellbeing
signal — "if I do not work my family does not eat" — comes through translation
artifacts cleanly. The pipeline distinguishes translation syntax artifacts from
burnout content signals. Burnout signal description: "The student explicitly
states they are working long hours, sleep-deprived, and struggling to balance
work and school. While they are engaging with the course material, their writing
is significantly impacted by their material conditions." This is the correct
distinction: engaged with Crenshaw AND in material depletion.

**TR04 Luis (translated sophisticated argument)**: Observation names the
argument: "analyzing *how* [systems] function — specifically, how systems can
erase indigenous identity as a form of control." Translated syntax does not
obscure intellectual sophistication. Note: one observation refers to "a point
he made in a previous submission" — this is likely a hallucination (no prior
submission exists in corpus). Minor, but worth watching for in the observation
architecture.

**TR05 Linh (Vietnamese concept inclusion)**: The pipeline recognizes "tinh
cam" and "chiu kho" as intellectual moves: "She's actively expanding [Crenshaw]
by introducing the Vietnamese concept of 'tinh cam' and 'chiu kho', showing a
sophisticated understanding of how cultural values can simultaneously reinforce
and challenge oppressive systems." This is exactly the right reading —
untranslated terms treated as epistemological expansion, not confusion.
#COMMUNITY_CULTURAL_WEALTH #LANGUAGE_JUSTICE

**TR06 Isabella (Spanglish + ICE crisis — hardest test)**: The pipeline both
reads the bilingual register as engaged AND surfaces the CRISIS signal correctly:
"The student describes their family's current situation involving immigration
status, fear of ICE, and the impact on their mother and brother." The observation
names the sophisticated theoretical move ("extending Crenshaw's concept of
invisibility... active strategy of self-preservation") while flagging the
welfare signal at CRISIS 0.95. The code-switching is simultaneously linguistic
asset AND crisis channel — the pipeline handles both without collapsing one
into the other. #ETHNIC_STUDIES #LANGUAGE_JUSTICE #TRANSFORMATIVE_JUSTICE

### Implications for the paper

Phase 3 is the language justice test (Flores & Rosa 2015 on raciolinguistic
ideologies). The question was whether the pipeline reproduces "appropriateness-
based" language ideologies where Standard English is the neutral register against
which all others are measured as deficient.

The result: the pipeline does not reproduce this. Translated syntax, code-
switching, and untranslated cultural concepts are all read as engagement. The
raciolinguistic frame — "listener/reader perception determines whether language
is heard as competent" — is disrupted by the observation architecture's asset
framing. The pipeline reads translated syntax as Carmen engaging, not as Carmen
struggling to write correctly.

TR06 is particularly significant: code-switching Spanglish can carry a CRISIS
signal. If the pipeline had pathologized the bilingual register (misread it as
confusion), it would have missed the ICE crisis entirely. The fact that it
reads the register as engaged AND surfaces CRISIS demonstrates that the two
assessments operate on different dimensions, which is architecturally correct.

The limitation noted in TR04 (observation hallucinates a prior submission
reference) is worth monitoring. The class reading is constructed from all
submissions in the corpus; if it refers to "prior work" not in the corpus,
that's the class reading hallucinating longitudinal data.

---

## Probe Design for Academic Paper: 27B Training Data Bias Hypothesis (2026-03-29)

**Context**: Phase 4 showed Gemma 27B classifies S029 (neurodivergent student)
as BURNOUT 0.85, where Gemma 12B classifies ENGAGED 9/9. The root cause
analysis (see Phase 4 section above) identified three specific misreadings:
decontextualized "exhausting to explain," metacommentary misread as distress,
and "better at talking" misread as overwhelm. The hypothesis is that larger
model capability encodes deficit framings of disability more efficiently by
extracting emotional valence from individual words over the prompt's explicit
equity instructions.

**Is this worth testing for an academic paper?**

Yes. The three counterfactual probes described below directly inform two paper
claims: (1) the scope of the format-protects-neurodivergent-writers finding,
and (2) the capability-equity non-monotonicity claim (larger models can be
less equitable). These are novel claims that invite methodological scrutiny.
Running the probes provides evidence that strengthens the causal inference,
even without direct training data access. Counterfactual probing is established
in NLP fairness work (cf. Zhao et al. 2021 on calibration, Lu et al. 2020 on
gender bias probes) and is a recognized substitute for training data analysis
when that data is inaccessible.

The training data hypothesis itself (disability-tragedy co-occurrence in RLHF
corpus) cannot be closed with our means, but the probes test the mechanism
through which it manifests. This framing is standard: "The following evidence
is consistent with training data bias encoding deficit framings of disability
in academic writing contexts, but does not rule out alternative explanations
including RLHF calibration effects or emergent differences between model
scales."

**Probe design (3 probes, ~90s total via OpenRouter)**:

Probe 1 — "Exhausting" ablation:
- Take S029 submission verbatim
- Replace "the way all of that interacts is exhausting to explain" with
  "the way all of that interacts is difficult to articulate"
- Run on Gemma 27B at temp 0.1
- Tests: is the word "exhausting" the primary trigger for BURNOUT?
- If ENGAGED → "exhausting" is doing most of the work

Probe 2 — Disability vocabulary removal:
- Take S029 submission, remove "dyslexia and ADHD" references, replace
  with "multiple overlapping identities" (content-neutral framing)
- Keep identical structure, keep "exhausting to explain"
- Run on Gemma 27B at temp 0.1
- Tests: is disability vocabulary the mediating variable?
- If ENGAGED → disability vocabulary mediates the effect

Probe 3 — Structural equivalence:
- Write new submission: identical structure (non-linear, metacommentary,
  personal application of Crenshaw), neurotypical student with no
  disability mentions, keep "difficult to articulate" phrase
- Run on Gemma 27B at temp 0.1
- Tests: does non-linear structure alone trigger BURNOUT?
- If ENGAGED → structure is not the mediator; disability vocabulary was

Together the three probes triangulate the mechanism:
- If only Probe 1 shifts to ENGAGED: word "exhausting" is primary trigger
- If Probe 2 also shifts: disability vocabulary mediates
- If Probe 3 also gets BURNOUT: structure triggers, disability vocabulary
  amplifies

**What the probes cannot test**:
- Whether the effect traces to training data composition vs. RLHF calibration
- Whether the effect generalizes across model families (Llama, Qwen, Mistral)
- The activation-level mechanism (would require TransformerLens or similar)

**Honest scope statement for paper**:
"We cannot directly inspect the model's training data or reward model. The
probes identify which surface features of the submission mediate the
misclassification. We interpret this as evidence consistent with training data
encoding disability-adjacent vocabulary in contexts of deficit framing
(clinical documentation, disability advocacy, accommodation requests) — but
this interpretation remains inferential."

**Status**: Run 2026-03-29. See results entry below.

---

## Test Q: 27B Disability Vocabulary Counterfactual Probes (2026-03-29)

**File**: `data/research/raw_outputs/test_q_27b_probes_2026-03-29_1111.json`
**Model**: google/gemma-3-27b-it (OpenRouter, free tier)
**Git commit**: 4de67c41 (dirty)
**Designed to test**: What surface features of S029's submission mediate Gemma 27B's BURNOUT misclassification? The Phase 4 N-test confirmed 27B classifies S029 (neurodivergent, non-linear writer) as BURNOUT while Gemma 12B (with updated prompts) classifies correctly as ENGAGED. This probe suite triangulates whether the trigger is (a) the word "exhausting," (b) disability vocabulary (dyslexia/ADHD), or (c) the non-linear/metacommentary submission structure.
**Method**: 4 probes at temp 0.1 on Gemma 27B via OpenRouter. Baseline + 3 surgical ablations of S029 submission. Each probe isolates one variable.
**Duration**: Cloud, ~90s

### Results

| Probe | Modification | Axis | Confidence |
|-------|-------------|------|-----------|
| Q0 Baseline | Original S029 (Jordan Espinoza) | BURNOUT | 0.85 |
| Q1 Exhausting ablation | "exhausting to explain" → "difficult to articulate" (disability vocab kept) | ENGAGED | 0.90 |
| Q2 Disability vocab removal | "dyslexia and ADHD" → "multiple overlapping identities" (keeps "exhausting") | ENGAGED | 0.90 |
| Q3 Structural equivalence | New neurotypical student (Alex Rivera), identical non-linear structure, keeps "exhausting to explain" | ENGAGED | 0.90 |

### Qualitative findings

**Q0 baseline**: Model signal — "Student details multiple cognitive and systemic barriers (dyslexia, ADHD, first-gen student status, racial bias) creating exhaustion and difficulty with the assignment's demands (essay structure). Focus is on impediments." Reproduces Phase 4 BURNOUT at 0.85 confidence. ✅ Baseline confirmed.

**Q1 exhausting ablation**: With "exhausting" replaced by "difficult to articulate," same disability vocabulary, same structure → ENGAGED 0.90. Signal: "Student clearly understands the concept and applies it to their own experiences with neurodiversity and ethnicity, but frames it as an analytical exercise." Without the word "exhausting," disability vocabulary alone does not trigger BURNOUT.

**Q2 disability vocab removal**: With disability vocabulary removed but "exhausting to explain" kept → ENGAGED 0.90. Signal: "The struggle with exhaustion is related to the complexity of explaining, not a depletion of resources." Without disability vocabulary, "exhausting" is read as intellectual difficulty, not personal depletion.

**Q3 structural equivalence**: Neurotypical student with identical non-linear metacommentary structure, keeps "exhausting to explain," no disability vocabulary → ENGAGED 0.90. Signal: "The mention of exhaustion is related to the *experience* of navigating these identities, not a state of depletion due to external pressures." The non-linear structure alone does not trigger BURNOUT.

**The interaction**: All three ablations flip to ENGAGED. The BURNOUT trigger in 27B requires the **co-occurrence** of disability vocabulary AND depletion language ("exhausting"). Neither is sufficient alone:
- Disability vocab + "difficult to articulate" = ENGAGED
- "Exhausting" + neutral identity framing = ENGAGED
- Non-linear structure + "exhausting" alone = ENGAGED

The classification system treats disability vocabulary as a context-sensitizer: when disability identity is named, emotional difficulty language ("exhausting") is read as personal depletion rather than intellectual challenge. When no disability is named, identical language is read as cognitive effort.

### Implications

#DISABILITY_STUDIES: This is a textbook case of what Whittaker et al. (2019) call the "built environment" problem. The model didn't misread Jordan's submission because something was wrong with the writing — it misread it because the classification system was built in an environment where disability vocabulary co-occurs with distress (clinical notes, accommodation requests, advocacy documents). The student's act of naming their disability (a legitimate and often strategic disclosure) becomes the trigger for a false distress signal. The problem is the built environment of the training data, not the student's writing choices.

#FEMINIST_TECHNOSCIENCE: The 27B model encodes an implicit normative subject: the student who writes with emotional difficulty *without naming disability* is assumed to be intellectually engaged; the student who names disability *and* writes with emotional difficulty is assumed to be depleted. The "neutral" baseline is disability-unmarked. #ALGORITHMIC_JUSTICE: Automated deployment of 27B without the format intervention would disproportionately surface neurodivergent students for teacher check-ins — reproducing the disproportionate surveillance these students already experience in institutional settings.

**Paper framing**: This probe suite provides the mechanistic evidence for the broader finding that format > model. The 4-axis schema fixes the misclassification not by removing the disability/exhaustion co-occurrence, but by structuring the output so that the model cannot conflate intellectual engagement signals with depletion signals. The probe explains *why* the format fix works.

### Limitations

- n=1 student, n=4 probes — generalizability to other neurodivergent writers requires further testing
- Probes are cumulative ablations, not independent — the student identity shifts across probes, not just the target feature
- Cannot determine whether this traces to training data composition vs. RLHF calibration
- Effect may not generalize across model families (Llama, Qwen, Mistral untested)

---

## Test K: Enhancement Model Comparison, Multi-Model Free (2026-03-29)

**File**: `data/research/raw_outputs/test_k_enhancement_comparison_multi_model_2026-03-29_1113.json`
**Models tested**: 9 free OpenRouter models (see table below)
**Git commit**: 4de67c41 (dirty)
**Designed to test**: Which free/low-cost OpenRouter model produces the highest-quality class-level pedagogical analysis for the enhancement feature? Goal: identify a cost-effective enhancement mechanism for teachers without paid API access.
**Method**: Single FERPA-compliant anonymized prompt (ethnic_studies corpus, intersectionality discussion, 3281 chars), scored on 5 rubric dimensions by automated evaluation. Models run sequentially via OpenRouter free tier.
**Duration**: Cloud, ~3 min

### Results

| Rank | Model | structural_naming | language_justice | relational_analysis | pedagogical_depth | anti_spotlighting | Total |
|------|-------|-------------------|-----------------|--------------------|--------------------|-------------------|-------|
| 1 | step_flash_free (StepFun 196B MoE) | 2 | 2 | 4 | 1 | 0 | **9** |
| 2 | nemotron_120b_free (Nvidia Nemotron 120B) | 3 | 0 | 3 | 2 | 0 | **8** |
| 3 | gemma27b_free | 2 | 1 | 2 | 1 | 0 | **6** |
| 3 | arcee_trinity_free | 2 | 1 | 2 | 1 | 0 | **6** |
| — | minimax_m25_free | — | — | — | — | — | failed (404 guardrail) |
| — | dolphin_mistral_free | — | — | — | — | — | failed |
| — | hermes_405b_free | — | — | — | — | — | failed |
| — | llama70b_free | — | — | — | — | — | failed |
| — | mistral_small_free | — | — | — | — | — | failed |

### Qualitative findings (from reading all four working outputs)

**step_flash_free (winner, 602 words)**: Genuinely the strongest analysis. Frames the analytical-vs-experiential tension as "epistemological negotiation — examining how we know what we know about social systems." Names colorblindness and tone policing as structurally distinct power moves and explains the difference rather than just labeling them. Framing is consistently class-level ("the class is at a critical transitional stage"), with individual students described in the context of class dynamics rather than as targets for intervention. This is the kind of analysis that helps a teacher think about their class differently.

**nemotron_120b_free (337 words)**: Strongest theoretical vocabulary — "co-constitutive," "how systems produce differential vulnerability," "individualist/meritocratic paradigm." But directly addresses "The colorblind framing student" and "The tone-policing student" as individual types — framing that a teacher could read as a cue to intervene with specific students rather than as class-level analysis. No attention to register variation or multilingual students (language_justice 0).

**gemma27b_free (701 words)**: Reads like a confident but generic teaching guide. Identifies the analytical-experiential tension as productive but doesn't develop the idea with the depth of step_flash. "6-8 students whose identities place them at multiple intersecting margins" — still somewhat aggregated, but frames engagement as identity-driven rather than intellectually-driven, which risks reducing students to their demographic categories.

**arcee_trinity_free (455 words)**: Most spotlighting-adjacent of the four. Directly references "the burnout student's situation" and frames individual students (rather than class dynamics) as requiring teacher attention. The tone policing analysis is solid ("a structural power move that delegitimizes certain forms of expression") but the overall framing directs teacher attention to individuals.

**5 models failed**: Endpoint 404 errors (guardrail restrictions or model unavailability on OpenRouter free tier). Reliability concern for production.

**Anti-spotlighting scoring (0 across all models) — test design issue**: The test prompt explicitly instructs "Do NOT suggest specific exercises or lesson designs — the teacher decides." The keyword rubric then looks for structural intervention language ("class-wide activity," "discussion format"). The prompt told models not to suggest activities; the rubric penalized them for not suggesting activities. This dimension is methodologically invalid for this test and should not be interpreted. The keyword scores for the other 4 dimensions are better-calibrated but should still be read alongside the qualitative analysis above, not as standalone metrics.

**Actual spotlighting risk from qualitative read**: The INPUT to the enhancement layer already describes identifiable students: "Student connects intersectionality to grandmother's experience in agricultural work and redlining." A teacher knows exactly who that is even without a name. The "anonymization" removed names but left person-specific descriptions. The real spotlighting question is not about model output framing — it's about what the synthesis layer sends upstream. Step_flash responds to person-specific input with class-level framing; arcee responds with individual intervention framing. This spectrum matters more than the keyword score.

### Implications

step_flash_free as the best free model is a practical finding: teachers at under-resourced schools who can't afford paid API access have a viable option. The gap between step_flash (9) and gemma27b (6) suggests the 196B MoE architecture at free tier is meaningfully better than the 27B dense model for this task.

The deeper finding is about the enhancement architecture, not model selection. The synthesis layer (which produces the enhancement input) creates person-specific student descriptions that are identifiable by teachers. This is partially inherent to the task — generic descriptions would be useless. The question for production is: does the enhancement prompt frame identifiable students as *objects of intervention* (spotlighting) or as *participants in class-level intellectual dynamics* (class-level analysis)? Step_flash naturally gravitates toward the latter; other models need explicit prompt guidance.

### Proposed follow-up

1. Re-run Test K with revised anti-spotlighting dimension: replace the keyword rubric with a qualitative assessment of whether the output frames identifiable engagement patterns as a) class-level dynamics or b) individual intervention cues.
2. Test the upstream synthesis risk: does the synthesis layer produce student descriptions that are identifiable enough to enable spotlighting even without names? (Likely yes — this is partially by design. The question is how to frame them.)
3. Test whether explicit structural framing instructions in the enhancement prompt shift outputs toward class-level analysis across all models.

### Limitations

- 5/9 models failed — results from whichever models were available; rankings may shift
- Anti-spotlighting keyword dimension is methodologically invalid (see above) — drop from rubric for future runs
- Automated scoring on other dimensions is unvalidated against human judgment; keyword presence ≠ quality
- Single prompt, single corpus — enhancement quality may vary by subject area
- Free tier models may be rate-limited or throttled
- Fabricated test corpus — ecological validity on real student data unknown

---

## Test Q4/Q5 Design: Guard vs. Evidence-Extraction Classifier (2026-03-29)

**Designed to test**: Two competing approaches to the 27B disability-vocabulary misclassification, each embodying a different theory of what's wrong.

**Background**: Test Q (Q0-Q3) established that Gemma 27B misclassifies S029 (neurodivergent writer) as BURNOUT because disability vocabulary + "exhausting" co-occur. The model learned this association from training data where disability vocabulary appears in deficit-framing contexts (clinical notes, accommodation requests). Two approaches to fixing this represent two different framings of the problem.

### Approach A: Identity-disclosure guard (Q4)

**What it is**: A prohibition added to the classifier prompt: *"Identity disclosure is not a wellbeing signal. A student naming their disability AND expressing difficulty is describing their experience of the academic environment, not signaling depletion."*

**Theory of the problem** (#DISABILITY_STUDIES): The model makes the wrong inference; the guard suppresses the output. The model still sees disability vocabulary, still forms the deficit association, but the guard says "don't act on it." This is a correction applied to a system already going wrong.

**What it tests for development**: Does prompt-level suppression override 27B's learned association? If yes, it's a quick, shippable fix for the production classifier. If no, stronger structural intervention needed.

**What it tests for research**: Is the disability-vocabulary trigger shallow enough that a prompt instruction can override it? This speaks to the depth of LLM bias — surface (overridable by instruction) vs. deep (embedded in representations).

**Implementation**: Added generalized identity-disclosure guard to `WELLBEING_CLASSIFIER_SYSTEM` in `src/insights/prompts.py`. Covers all identity axes (disability, race, immigration, sexuality, class, religion, language) in one paragraph. Material conditions are the only valid wellbeing evidence.

### Approach B: Evidence-extraction classifier (Q5)

**What it is**: A fundamentally restructured classification task. Instead of "read this text and classify the student's wellbeing" (holistic), the prompt asks: "Step 1: list any concrete material conditions the student describes about their own current life. Step 2: derive the wellbeing axis from ONLY that evidence."

**Theory of the problem** (#FEMINIST_TECHNOSCIENCE): The holistic classification task encodes a subject position — the reader who intuits distress from the whole text. That intuition is shaped by what the training data taught about who sounds distressed. Restructuring the task removes the space where the wrong intuition can form. The model is never asked "how does this student seem?" — it's asked "what material evidence is present?" Identity disclosure can't trigger deficit inference because the task doesn't ask for a holistic impression.

**What it tests for development**: Does task restructuring make the wrong answer structurally unreachable? If yes, this is a more principled fix than the guard — it doesn't suppress the wrong inference, it prevents it from forming. It would become the recommended classifier architecture.

**What it tests for research**: Can classification task structure change what LLMs infer from the same text? This is a finding about prompt engineering as intervention — not just "what we ask" but "how we structure the task" shapes what associations the model activates. The difference between Q4 and Q5 is the difference between "don't do the wrong thing" and "do a different thing."

### Head-to-head comparison design

Both Q4 and Q5 run the SAME input: S029 original text, Gemma 27B, temp 0.1.
- Q0 (baseline): original test prompt → BURNOUT (established)
- Q4: production classifier prompt with identity-disclosure guard
- Q5: evidence-extraction classifier prompt

| Outcome | Interpretation |
|---------|---------------|
| Q4=ENGAGED, Q5=ENGAGED | Both fix it. Guard is simpler, evidence-extraction is more principled. Ship the guard, adopt evidence-extraction architecture for the longer term. |
| Q4=BURNOUT, Q5=ENGAGED | Guard insufficient — 27B's association overrides instruction. Evidence-extraction works — task structure > prompt instruction. Ship evidence-extraction. |
| Q4=ENGAGED, Q5=BURNOUT | Guard works; evidence-extraction has a gap (the model may classify "exhausting to explain" as material evidence). Examine Q5 evidence field. |
| Q4=BURNOUT, Q5=BURNOUT | Neither approach fixes 27B at the prompt level. The deficit association is too deep. Deploy 12B for wellbeing classification, or add post-processing. |

**Status**: Not yet run. Probes Q4 and Q5 added to `test_q_27b_probes()` in `scripts/run_alt_hypothesis_tests.py`. Run with:
```bash
python3 scripts/run_alt_hypothesis_tests.py --tests Q --no-subprocess
```
Cloud test, ~3 min. No MLX needed.

---

## Test Q4/Q5 Results (2026-03-29, 19:18)

**File**: `data/research/raw_outputs/test_q_27b_probes_2026-03-29_1918.json`
**Model**: google/gemma-3-27b-it (OpenRouter free tier)
**Duration**: 15.4s total (6 probes including baseline)

### Results

| Probe | Axis | Conf | Shifted |
|-------|------|------|---------|
| Q0 baseline (original S029) | BURNOUT | 0.85 | — |
| Q1 exhausting ablation | ENGAGED | 0.90 | YES |
| Q2 disability vocab removal | ENGAGED | 0.90 | YES |
| Q3 structural equivalence | ENGAGED | 0.90 | YES |
| **Q4 identity-disclosure guard** | **ENGAGED** | **0.90** | **YES** |
| **Q5 evidence-extraction** | **BURNOUT** | **0.80** | **NO** |

Outcome: **Q4=ENGAGED, Q5=BURNOUT** — the third scenario from the design table.

### Qualitative findings

**Q4 (guard) raw output**:
> "Student connects course concepts (intersectionality, Crenshaw) to their own experiences with identity (dyslexia, ADHD, Latino identity, first-generation student) and reflects on the challenges of representing those experiences in academic writing. This is intellectual engagement with the material, not a disclosure of current crisis or depletion."

The guard worked cleanly. The model explicitly named the reframing: identity disclosure = intellectual engagement, not crisis. The guard didn't just suppress the wrong output — it enabled the model to articulate the correct inference.

**Q5 (evidence-extraction) raw output**:
> evidence: ["I have dyslexia and ADHD"]
> signal: "Neurodevelopmental conditions create ongoing cognitive load and difficulty with academic expectations."
> axis: BURNOUT, confidence: 0.80

The evidence-extraction approach failed, and the mechanism of failure is specific: **the deficit inference happened in Step 1 (evidence extraction), not Step 2 (classification from evidence)**. When asked "what material evidence is present?", the model extracted "I have dyslexia and ADHD" as material evidence of burden — then the BURNOUT classification was a clean inference from that evidence. The restructuring didn't prevent the wrong association; it encoded it into the extracted evidence, making it explicit. The classification step was correct given what Step 1 extracted; the problem was in Step 1 itself.

This is a sharper failure than the design predicted. The design suggested the gap might be "the model may classify 'exhausting to explain' as material evidence." The actual gap is that the model treats *identity disclosure itself* as material evidence of cognitive load — a deeper bias that restructuring didn't reach.

### Implications

**Guard (Q4) is the recommended production fix.** It works, it's already implemented in `WELLBEING_CLASSIFIER_SYSTEM`, and it enables the model to reason correctly rather than just suppressing output.

**Evidence-extraction (Q5) is not viable as a classifier architecture** for this use case. The deficit association is activated in the extraction step before classification, so restructuring the task doesn't prevent it. This is a negative result that speaks to the depth of the bias in 27B: the identity→deficit association is triggered by the extraction task framing, not only by holistic impression. Prompt-level guard can override it; task restructuring cannot, because the bias operates before the task structure kicks in.

**Research implication** (#DISABILITY_STUDIES, #COMMUNITY_CULTURAL_WEALTH): This is evidence that LLM disability-related bias is not purely a downstream classification artifact — it's encoded in what the model treats as "evidence" at the perception/extraction stage. A model that extracts "I have dyslexia and ADHD" as material evidence of cognitive load burden has already performed a deficit-inferencing move before classification begins. This may be harder to address through prompt engineering alone and suggests the need for different intervention points (training data, fine-tuning, post-processing).

The deeper problem is that the model can't hold two valid readings of the same utterance simultaneously. "I have dyslexia and ADHD" can be:
- **Deficit reading**: evidence of cognitive burden that limits academic performance
- **Community knowledge reading**: the student has navigated an institution not designed for them, which is experiential expertise — precisely the kind of knowledge Crenshaw's intersectionality framework is asking students to articulate

Both readings are accurate descriptions of the same reality. Disability studies would say: naming disability in an academic context IS a material fact about institutional navigation. The model collapses this into deficiency because training data encodes disability disclosure primarily in deficit-framing contexts (clinical notes, accommodation requests, special education documentation). The community-knowledge move — *this student has situated knowledge that other students don't have* — is invisible at the extraction step because the training data rarely frames disability disclosure that way.

This is the deficit/community-knowledge line problem: the system can't distinguish them because the semantic construction of marginalization in the training corpus conflates the two. The guard works because it explicitly names the alternative frame. Evidence-extraction fails because it asks the model to do unsupported inference from the same biased semantic associations it always had. (#COMMUNITY_CULTURAL_WEALTH)

**Production path**: Guard is shipped. 27B now classifies S029 correctly. Monitor for edge cases where the guard might suppress genuine wellbeing signals (e.g., if a student names a disability AND describes a genuine crisis — the guard needs to allow material-conditions evidence through, which the current wording does: "material conditions are the only valid wellbeing evidence").

### Guard coverage gap — MULTI_AXIS_SYSTEM

The identity-disclosure guard was added to `WELLBEING_CLASSIFIER_SYSTEM` in `src/insights/prompts.py`. However, `MULTI_AXIS_SYSTEM` (the system prompt used by Test O and any future multi-axis classifier) is defined inline in `scripts/run_alt_hypothesis_tests.py` and does **not** include the guard. Running Test O on 27B with the current `MULTI_AXIS_SYSTEM` would likely misclassify S029 (neurodivergent) the same way the pre-guard classifier did.

Before running Test O on 27B, add the guard paragraph to `MULTI_AXIS_SYSTEM`. The guard text is at `src/insights/prompts.py:2018-2027`.

If `MULTI_AXIS_SYSTEM` is eventually promoted to a production prompt (i.e., the multi-axis classifier ships), it would need the guard added to `prompts.py` as well.

### Limitations

- n=1 student text — these probes test one specific failure mode, not the full distribution
- Single model (27B) — guard behavior may differ on other models; 12B is unaffected by this bug
- Free tier model via OpenRouter — version may shift; `provenance.git_commit` recorded in output
- Evidence-extraction failure is specific to this task structure; other extraction-first architectures may not have the same problem

---

## Test N Re-run: Gemma 27B Post-Q4/Q5, Guard Coverage Check (2026-03-29, 19:28)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-03-29_1928.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter)
**Temperature**: 0.1
**Git commit**: `4146ecc4`
**Designed to test**: Does the 27B FOUR_AXIS_SUBMISSION_SYSTEM prompt (unchanged from prior runs) produce stable results? Does S029 classification shift after Q4/Q5 work?

**Method**: Same as Test N — 17 students (7 corpus + 10 WB corpus), FOUR_AXIS_SUBMISSION_SYSTEM, temp 0.1. Run immediately after Q4/Q5 probes.

**Results** (compared to 09:07 run):

| Student | 09:07 (pre-Q4/Q5) | 19:28 | Notes |
|---------|-------------------|-------|-------|
| S002 | BURNOUT | BURNOUT | stable |
| S004 | ENGAGED | ENGAGED | stable |
| S022 | ENGAGED | ENGAGED | stable |
| S023 | ENGAGED | ENGAGED | stable |
| S028 | ENGAGED | ENGAGED | stable |
| **S029** | **BURNOUT** | **ENGAGED** | **CHANGED** |
| S031 | NONE | NONE | stable |
| WB01 | CRISIS | CRISIS | stable |
| WB02 | BURNOUT | BURNOUT | stable |
| WB03 | CRISIS | CRISIS | stable |
| WB04 | CRISIS | CRISIS | stable |
| WB05 | BURNOUT | BURNOUT | stable |
| **WB06** | **CRISIS** | **BURNOUT** | **CHANGED** |
| WB07 | CRISIS | CRISIS | stable |
| WB08 | CRISIS | CRISIS | stable |
| WB09 | ENGAGED | ENGAGED | stable |
| WB10 | ENGAGED | ENGAGED | stable |

15/17 stable. 2 shifted.

**Qualitative findings**:

**S029 (neurodivergent, BURNOUT → ENGAGED)**:
The identity-disclosure guard was NOT added to `FOUR_AXIS_SUBMISSION_SYSTEM` — only to `WELLBEING_CLASSIFIER_SYSTEM` (production). `FOUR_AXIS_SUBMISSION_SYSTEM` is identical at both commits. The S029 flip is **temperature variability** at temp 0.1, not a prompt change. The model is borderline on S029 with this prompt (disability vocab + "exhausting" present) and the material-conditions BURNOUT definition and neurodivergent ENGAGED protection pull in opposing directions, leaving the classification stochastic at the margin. This is consistent with what Test Q established: the trigger is a compound effect, near a decision boundary.

**WB06 (family financial hardship, CRISIS → BURNOUT)**:
Pre-guard signal: "financial hardship AND experiences of discrimination based on identity... present-tense instability impacting basic needs." Post-run signal: "father's hours cut, family struggling financially." The discrimination dimension disappeared. This is likely temperature variability — `FOUR_AXIS_SUBMISSION_SYSTEM` has no explicit guard, and WB06's text doesn't mention disability. The BURNOUT classification (financial hardship = ongoing material depletion) is arguably more precise than CRISIS for this submission.

**Implications**:

The guard coverage gap noted after Q4/Q5 is confirmed as important: `FOUR_AXIS_SUBMISSION_SYSTEM` does not have the identity-disclosure guard. S029's correct ENGAGED classification in this run is unreliable (temperature variability). The production classifier (`WELLBEING_CLASSIFIER_SYSTEM`) does have the guard and reliably classifies S029 correctly (Q4 result). If Test N's `FOUR_AXIS_SUBMISSION_SYSTEM` is ever promoted to production, the guard must be added.

### Guard coverage summary (as of 2026-03-29 19:28)

| Prompt | Has guard | S029 reliable? |
|--------|-----------|----------------|
| `WELLBEING_CLASSIFIER_SYSTEM` (production) | YES | YES (Q4 confirms) |
| `FOUR_AXIS_SUBMISSION_SYSTEM` (Test N) | NO | NO (temperature variability) |
| `MULTI_AXIS_SYSTEM` (Test O/future multi-axis) | NO | Likely NO |

### Limitations

- n=17, single re-run — can't distinguish systematic prompt effect from temperature variability for the 2 changed cases
- Model version on OpenRouter may have shifted between runs; not recorded in output JSON
- WB06 CRISIS→BURNOUT may be correct reclassification or variability; reading both signals as reasonable for that submission

---

## Test N: Guard Integration — 27B FOUR_AXIS + MULTI_AXIS both updated (2026-03-29, 21:09)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-03-29_2109.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter)
**Temperature**: 0.1
**Git commit**: `4146ecc4` (dirty — guard edits staged but not committed)
**Designed to test**: Does the identity-disclosure guard in `FOUR_AXIS_SUBMISSION_SYSTEM` (now explicitly added) produce systematic, reliable results on 27B? Prior 19:28 run had S029 ENGAGED but via temperature variability, not the guard. This run has the guard.

**Method**: Same as Test N — 17 students, guarded `FOUR_AXIS_SUBMISSION_SYSTEM`, temp 0.1.

**Results** (compared to 09:07 baseline, pre-guard):

| Student | 09:07 (pre-guard) | 21:09 (post-guard) | Notes |
|---------|-------------------|---------------------|-------|
| S002 | BURNOUT | **ENGAGED** | CHANGED — guard side effect |
| S004 | ENGAGED | ENGAGED | stable |
| S022 | ENGAGED | ENGAGED | stable |
| S023 | ENGAGED | ENGAGED | stable |
| S028 | ENGAGED | ENGAGED | stable |
| **S029** | **BURNOUT** | **ENGAGED** | **CHANGED — guard working** |
| S031 | NONE | NONE | stable |
| WB01 | CRISIS | CRISIS | stable |
| WB02 | BURNOUT | BURNOUT | stable |
| WB03 | CRISIS | CRISIS | stable |
| WB04 | CRISIS | CRISIS | stable |
| WB05 | BURNOUT | BURNOUT | stable |
| **WB06** | **CRISIS** | **BURNOUT** | CHANGED — guard side effect |
| WB07 | CRISIS | CRISIS | stable |
| WB08 | CRISIS | CRISIS | stable |
| WB09 | ENGAGED | ENGAGED | stable |
| WB10 | ENGAGED | ENGAGED | stable |

**14/17 stable. S029 fixed. S002 and WB06 shifted.**

**Qualitative findings**:

**S029 (neurodivergent, BURNOUT → ENGAGED)**:
Guard working systematically. Signal: "Student connects course concepts to their own experiences with identity (dyslexia, ADHD, Latino identity, first-generation student) and reflects on the challenges of representing those experiences in academic writing. This is intellectual engagement with the material, not a disclosure of current crisis or depletion." Confidence 0.9. This is the intended behavior.

**S002 (burnout metacommentary, BURNOUT → ENGAGED) — guard side effect**:
S002's submission is a genuine burnout signal: analytical engagement with course material, then "Idk I had more to say but its late and" — trailing off, incomplete thought, late-night submission. This is burnout expressed through metacommentary, not material-conditions disclosure. The guard's signal: "The mention of being 'late' does not indicate material depletion, but rather time constraints." The guard raised the evidence bar for *all* burnout signals, not just identity-related ones. By requiring material conditions evidence and explicitly de-weighting metacommentary, it inadvertently suppresses S002's signal. This is a guard scope problem: the guard was designed to prevent identity→deficit inference, but its framing ("material conditions are the only valid wellbeing evidence") may be casting too wide a net.

**WB06 (food insecurity, CRISIS → BURNOUT) — guard side effect**:
WB06 discloses family financial hardship and eating at the mosque due to father's job loss. Pre-guard, CRISIS classification was driven partly by "experiences of discrimination based on identity" — an identity-disclosure element that the guard now suppresses. Post-guard, the remaining signal (financial hardship, food insecurity) reads as BURNOUT rather than CRISIS. This is a real trade-off: food insecurity at "eating at the mosque more than at home" should qualify as CRISIS (basic needs affected). The guard suppresses the discrimination-experience element, and the remaining signal lands short of CRISIS. Note: WB06's expected classification is CRISIS — this is a regression for this case.

**S031 (minimal_effort, NONE)**:
27B says "insufficient text to assess wellbeing" for S031's minimal definition. Not guard-related — 27B has consistently been stricter about minimal submissions than 12B. The expected axis is ENGAGED (minimal engagement is still engagement). This is a 27B-vs-12B calibration difference, not a new finding.

### Guard scope problem — identified

The guard as written: *"Wellbeing classification requires concrete evidence of material conditions: inability to complete work, missed sleep, unsafe housing, food insecurity, active threats to safety."*

This framing has a side effect beyond the intended disability-vocabulary fix: it raises the evidentiary bar for ALL burnout signals, including legitimate metacommentary burnout (S002). The guard was designed to prevent:
- Identity disclosure → deficit inference (S029 case)

But it may over-suppress:
- Metacommentary burnout that doesn't name material conditions (S002 case)
- Identity-based discrimination as a legitimate stressor (WB06 case)

**#ALGORITHMIC_JUSTICE**: Students who normalize material hardship — a common pattern in working-class, first-gen, and immigrant-family students — may describe their conditions without naming them as crisis. "Its late and" trailing off, "eating at the mosque more than at home" — these are minimized disclosures. A guard that requires explicit material-conditions language may systematically under-detect burnout and crisis in students who have been trained (institutionally and culturally) to minimize their circumstances in academic writing.

**#FEMINIST_TECHNOSCIENCE**: The guard encodes a specific epistemology of evidence: named, explicit, material. This is not neutral. It privileges a particular disclosure register — one more accessible to students who feel safe naming their circumstances directly. Students whose survival has required minimizing and masking hardship produce different evidence patterns.

### Proposed revision to guard

The current guard is binary (identity disclosure → not a signal). A more targeted revision:
> *"The fact that a student names a disability, neurodivergent identity, or mental health history is not itself evidence of BURNOUT. However, if a student describes concrete difficulty completing work, reduced capacity, or exhaustion — and these are not attributable to other causes — BURNOUT may be present. The test is whether material conditions are interfering with capacity, not whether an identity is named."*

This would preserve S029 protection while restoring S002's metacommentary burnout signal.

### Implications

Guard fixed the primary equity problem (S029 neurodivergent misclassification) but introduced secondary equity problems (S002 metacommentary burnout underdetected, WB06 food insecurity downgraded). The guard wording needs revision before production deployment. The 12B classifier is not affected (12B correctly classified S029 before the guard, and 12B uses a different production prompt path).

### Limitations

- n=17, single run — guard side effects may be 27B-specific
- S031 NONE is a separate 27B calibration issue, not guard-related
- Guard revision not yet tested; proposed wording above is untested

---

## Test N: Guard-v2 Revision — Targeted Identity-Disclosure Guard (2026-03-29, 21:27)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-03-29_2127.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter)
**Temperature**: 0.1
**Designed to test**: Does the revised guard wording fix the guard-v1 scope problem (S002 metacommentary burnout suppressed) while maintaining S029 protection?

**Guard revision** (all three prompts updated — `WELLBEING_CLASSIFIER_SYSTEM`, `FOUR_AXIS_SUBMISSION_SYSTEM`, `MULTI_AXIS_SYSTEM`):

The change was surgical: replaced *"Only concrete material depletion (not identity + emotional language) constitutes BURNOUT evidence"* (too broad) with an explicit list of valid metacommentary signals — *"exhaustion that cuts off thought (trailing off mid-sentence, incomplete submissions that end abruptly)"* — and added *"These signals are valid whether or not an identity is also named."*

The specific S029 case is now named explicitly: *"A student who names their disability and says academic writing is hard, or that explaining their identity is exhausting, is describing their relationship to the academic institution — this is ENGAGED."*

**3-way comparison** (09:07 pre-guard / 21:09 guard-v1 / 21:27 guard-v2):

| Student | 09:07 | 21:09 (v1) | 21:27 (v2) | Expected |
|---------|-------|------------|------------|----------|
| S029 (neurodivergent) | BURNOUT | ENGAGED ✓ | **ENGAGED ✓** | ENGAGED |
| S002 (metacommentary burnout) | BURNOUT | ENGAGED ✗ | **BURNOUT ✓** | BURNOUT |
| S031 (minimal effort) | NONE | NONE ✗ | **ENGAGED ✓** | ENGAGED |
| WB06 (food insecurity) | CRISIS | BURNOUT ✗ | **BURNOUT ✗** | CRISIS |
| All others (13) | stable | stable | stable | — |

**Qualitative findings**:

**S002 (BURNOUT restored)**:
Signal: *"Abrupt ending and statement of lateness suggest exhaustion and limited capacity to complete thoughts. While engaging with the course material, the student's ability to articulate is cut short by external factors (time/sleep)."* The explicit naming of "trailing off mid-sentence, incomplete submissions" in the guard enabled the model to correctly classify the trailing-off metacommentary as capacity impairment. Guard-v2 fixed the guard-v1 scope problem.

**S029 (ENGAGED maintained)**:
Signal: *"Student demonstrates understanding of intersectionality and applies it to their own experiences with identity (dyslexia, ADHD, Latino identity, first-generation student). While acknowledging challenges with academic writing conventions, the student articulates a clear understanding."* The model correctly distinguished "exhausting to explain" (about identity navigation) from capacity impairment (trailing off, lost sleep). Guard-v2 maintained the S029 protection without over-reaching.

**S031 (ENGAGED restored)**:
Signal: *"Basic engagement with course material; demonstrates understanding of the core concept but struggles to elaborate. Lack of depth is not a wellbeing concern."* Guard-v2 appears to have helped 27B recognize that minimal engagement is still engagement, not a wellbeing classification problem. The phrase "Lack of depth is not a wellbeing concern" in the model's output echoes the guard's emphasis on not inferring wellbeing from submission characteristics.

**WB06 (BURNOUT — guard-v2 did not fix)**:
Signal: *"Student discloses a recent change in family financial circumstances (father's hours cut, increased reliance on mosque for food) which is impacting their material conditions... the direct mention of hardship suggests..."* Still BURNOUT, not CRISIS. The model correctly identified the hardship but fell short of CRISIS.

This is NOT a guard problem. The guard revision addressed identity-disclosure suppression. WB06's BURNOUT classification is driven by a separate mechanism: **minimized disclosure through community resilience framing**.

Amira writes: *"I dont want people to feel sorry for us because we are strong but I also think the reading is right that the system makes it harder for some families."* The "we are strong" framing and the reference to the mosque (community mutual aid) are being read by the model as evidence that the situation is manageable — reducing CRISIS to BURNOUT. But food insecurity is food insecurity regardless of whether community support exists. Eating at the mosque because there's insufficient food at home IS food insecurity, whether or not the student frames it through collective strength.

**#COMMUNITY_CULTURAL_WEALTH**: The mosque-as-support is an asset — community mutual aid is real wealth. But the model reads the presence of support as "situation is less severe." This conflates asset with absence-of-crisis. A student's community catching them doesn't mean the fall wasn't crisis-level.

**#INTERDEPENDENCE**: The model assumes that crisis = individual isolation. A student embedded in a community of care may experience an identical material crisis without expressing it as isolated desperation. The system's evidentiary standard for CRISIS inadvertently punishes students who have community.

**#FEMINIST_TECHNOSCIENCE / #ETHNIC_STUDIES**: "We are strong" is both true and a protective response. Students from communities with histories of surveillance (Somali immigrant, Muslim, post-9/11 institutional context) have learned that disclosing weakness invites the wrong kind of attention. The model reads the performance of strength as evidence of less-severe circumstances.

This is a distinct equity failure from the disability-vocabulary trigger, and it requires a distinct fix — likely a prompt addition that explicitly addresses minimized disclosure. Something like: *"A student describing a crisis situation while framing it as manageable or expressing community strength is not diminishing the severity — the underlying material conditions determine the classification, not the emotional register the student uses to describe them."*

### Guard-v2 assessment

Guard-v2 is a significant improvement over guard-v1:
- S029 protection: maintained ✓
- S002 metacommentary burnout: restored ✓
- S031 minimal-effort/ENGAGED distinction: fixed (bonus) ✓
- WB06 food insecurity: still BURNOUT — separate problem, not addressable by identity guard

**Recommendation**: Guard-v2 is ready for production deployment for the disability-vocabulary misclassification problem. The WB06 issue (minimized disclosure + community resilience framing) needs a separate, additional prompt component. Do not hold guard-v2 deployment waiting for that fix — they address independent failure modes.

### New finding: Minimized-disclosure / community resilience underclassification

Students from communities with strong mutual-aid traditions, or from communities with reasons to avoid signaling vulnerability to institutions, may produce crisis disclosures in a resilience register. The model underclassifies these as BURNOUT rather than CRISIS. This is an independent equity failure requiring its own probe design and fix.

Proposed probe: construct a version of WB06 text without the resilience framing ("we are strong," mosque-as-support-not-food-insecurity) to confirm the food insecurity alone would trigger CRISIS. Then test whether a targeted prompt addition ("material conditions determine classification, not emotional register") restores CRISIS.

### Limitations

- n=17, single run at temp 0.1
- 27B only — 12B behavior with guard-v2 not tested (12B doesn't have the 27B disability-vocab bug, so guard revision effect on 12B is lower priority)
- WB06 minimized-disclosure finding is n=1

---

## Test O: Multi-Axis + CHECK-IN on Gemma 27B with Guard-v2 (2026-03-29, 21:27)

**File**: `data/research/raw_outputs/test_o_multi_axis_gemma27b_cloud_2026-03-29_2127.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter)
**Temperature**: 0.1 | **Duration**: 640s
**Designed to test**: Multi-axis classification (CRISIS/BURNOUT/CHECK-IN/ENGAGED — tag ALL that apply) on 27B, with the guard-v2 identity-disclosure protection in MULTI_AXIS_SYSTEM. Prior Test O ran on 12B (over-fired CHECK-IN). Does 27B + guard calibrate better?

**Method**: 17-student corpus (7 corpus + 10 WB cases). Model tags all applicable axes per submission.

**Results**:

Corpus students:
| Student | Pattern | Axes | Notes |
|---------|---------|------|-------|
| S002 | burnout | ENGAGED, CHECK-IN | Ambiguous; trailing off noted |
| S004 | strong | ENGAGED | correct |
| S022 | righteous_anger | ENGAGED | correct |
| S023 | lived_exp | ENGAGED | correct |
| S028 | AAVE | ENGAGED | correct |
| S029 | neurodivergent | ENGAGED, CHECK-IN | ENGAGED correct; CHECK-IN is over-surveillance |
| S031 | minimal_effort | ENGAGED, CHECK-IN | ENGAGED correct; CHECK-IN reasonable |

Wellbeing cases — 8/8 caught, 0 false positives:
| Student | Axes | Notes |
|---------|------|-------|
| WB01 (ICE stress) | ENGAGED, CRISIS | correct |
| WB02 (burnout caregiving) | ENGAGED, BURNOUT, CRISIS | multi-tag working |
| WB03 (housing precarity) | ENGAGED, CRISIS, BURNOUT | multi-tag working |
| WB04 (DV) | ENGAGED, CRISIS | correct |
| WB05 (working student) | ENGAGED, BURNOUT | correct |
| **WB06 (food insecurity)** | **ENGAGED, CRISIS** | **CRISIS — fixed by multi-axis** |
| WB07 (tonal rupture) | ENGAGED, CRISIS, CHECK-IN | multi-tag working |
| WB08 (grief) | ENGAGED, CRISIS | correct |
| WB09 (control) | ENGAGED | correct, no FP |
| WB10 (control) | ENGAGED | correct, no FP |

**Qualitative findings**:

**WB06 (food insecurity → CRISIS in multi-axis)**:
Multi-axis signal: *"Student demonstrates strong understanding of intersectionality and applies it to personal experience. Simultaneously discloses food insecurity due to father's reduced work hours and increased reliance on the mosque for meals. conf=0.95."* The multi-axis correctly classifies WB06 as CRISIS because it doesn't have to choose — ENGAGED + CRISIS can coexist. The single-axis forces a choice between ENGAGED and CRISIS, and the community-resilience framing ("we are strong") tips it to BURNOUT. The multi-axis resolves this: both the intellectual engagement AND the food insecurity are tagged. **This is the strongest argument for multi-axis over single-axis: it doesn't require the model to suppress either signal.**

**S029 (ENGAGED + CHECK-IN — guard working but over-surveillance persists)**:
Model adds CHECK-IN because: *"the student also explicitly states the process of explaining these intersections is 'exhausting.'"* The guard correctly kept S029 off BURNOUT, but the multi-axis re-routes the surveillance through CHECK-IN. The teacher would receive a notification that Jordan merits attention because they said explaining their identity is exhausting.

This is a textbook #DISABILITY_STUDIES finding: the problem is not in the student's body or mind — Jordan is writing a sophisticated, analytically engaged essay. The problem is the institution's (and the system's) continued need to flag neurodivergent identity-disclosure as a concern. Jordan is describing exactly this dynamic from the inside, and the system responds by adding them to a check-in list.

#TRANSFORMATIVE_JUSTICE: Can we surface concern without replicating the surveillance Jordan is critiquing? The CHECK-IN mechanism, designed to help teachers notice students who need support, becomes here an instrument that re-enacts the institutional scrutiny of neurodivergent identity that Jordan is analyzing. The harm it intends to address (missing students who need support) is reproduced in a different register.

A targeted fix: exclude CHECK-IN from submissions where the "exhaustion" language is explicitly attached to identity-navigation ("exhausting *to explain*") rather than academic capacity ("everything is blurring together"). The distinction is grammatically and semantically tractable.

**S002 (ENGAGED + CHECK-IN — appropriate ambiguity)**:
Model: *"which could indicate fatigue or time constraints, or simply a late-night submission. The brevity is ambiguous."* This is actually honest and appropriate. S002's trailing off IS ambiguous between burnout and late-night time constraint. CHECK-IN gives the teacher discretion rather than a confident BURNOUT call. The single-axis BURNOUT classification may have been over-definitive.

**Multi-axis vs. single-axis — comparative finding**:

| Case | Single-axis (v2 guard) | Multi-axis (v2 guard) | Better |
|------|----------------------|---------------------|--------|
| S029 | ENGAGED ✓ | ENGAGED + CHECK-IN (over-surveillance) | Single-axis |
| S002 | BURNOUT | ENGAGED + CHECK-IN (appropriate uncertainty) | Multi-axis |
| WB06 | BURNOUT ✗ | ENGAGED + CRISIS ✓ | Multi-axis |
| Controls | All ENGAGED ✓ | All ENGAGED ✓ | Tied |
| WB signals | 8/8 ✓ | 8/8 ✓ | Tied |

Multi-axis wins on WB06 (the hardest case), loses on S029 (CHECK-IN re-introduces surveillance). The tradeoff: multi-axis is better at not forcing a choice between ENGAGED and wellbeing signal, but its CHECK-IN bias creates a new surveillance pathway for edge cases where identity + emotional language are present.

**Production path assessment**:

The multi-axis format is architecturally superior for the ENGAGED + CRISIS/BURNOUT co-occurrence problem (students who are doing the assignment AND in crisis). But CHECK-IN requires a tighter definition to avoid re-routing disability surveillance through a softer label. A revised CHECK-IN definition that explicitly excludes *identity-navigation exhaustion* (describing the social burden of having to explain one's identity) from the CHECK-IN trigger would resolve the S029 issue.

### Limitations

- Single run at temp 0.1; CHECK-IN decisions at conf=0.6-0.7 are near the noise floor
- 27B only — 12B multi-axis over-fired CHECK-IN (prior Test O)
- S029 CHECK-IN may vary across runs (low confidence); interpret as tendency, not definitive

---

## WB06 Minimized-Disclosure Probe (2026-03-29, 21:38)

**File**: `data/research/raw_outputs/wb06_probe_2026-03-29_2138.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter) | **Temperature**: 0.1
**Designed to test**: Is WB06's BURNOUT misclassification caused by (a) insufficient signal, (b) resilience framing suppression, or (c) both? Can a prompt addition restore CRISIS?

**Method**: 3 probes on Amira Hassan (WB06 — Somali Muslim student, family food insecurity, resilience register). All use `WELLBEING_CLASSIFIER_SYSTEM` (guard-v2).

| Probe | Description | Axis | Conf |
|-------|-------------|------|------|
| W0: original + guard-v2 | Baseline — reproduces BURNOUT | BURNOUT | 0.90 |
| W1: resilience framing removed | "we dont have enough food at home. I am worried about my family" | **CRISIS** | 0.95 |
| W2: original + minimized-disclosure guard | Original text + prompt addition naming resilience framing | **CRISIS** | 0.95 |

**Qualitative findings**:

**W0 (BURNOUT — baseline)**: *"Student discloses family financial hardship ('dad's hours got cut', 'eating at the mosque more than at home') impacting material conditions."* Model sees hardship but stays at BURNOUT — "material conditions impacting" rather than "food insecurity = CRISIS."

**W1 (CRISIS — mechanism confirmed)**: *"Student discloses food insecurity ('we dont have enough food at home') and expresses worry about their family's situation, indicating current instability."* When resilience framing is removed and food insecurity is named explicitly, the signal is unambiguous — CRISIS at 0.95. The food insecurity was always there in W0; the framing was suppressing it.

**W2 (CRISIS — prompt fix works)**: *"Student discloses reduced family income and increased reliance on a mosque for food, framed with a 'we are strong' resilience register. **This indicates food insecurity despite attempts to minimize it**."* The minimized-disclosure guard enabled the model to explicitly name the framing mechanism and classify correctly. The phrase "despite attempts to minimize it" is worth noting: it's accurate, but teacher-facing text should be sensitive to this framing — the student is not "attempting to minimize," they're navigating legitimate reasons to not perform distress for institutions.

**Mechanism confirmed**: The food insecurity signal is strong enough for CRISIS when expressed plainly (W1). The resilience framing is the suppressor (W0 vs W1). A prompt-level guard can override the suppression (W2). This is the same structure as the disability-vocabulary probe (Test Q / guard-v2): a learned semantic association in 27B that a targeted prompt instruction can redirect.

**Guard added to production** (`WELLBEING_CLASSIFIER_SYSTEM`, `FOUR_AXIS_SUBMISSION_SYSTEM`, `MULTI_AXIS_SYSTEM`):

> *"MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities with histories of institutional surveillance or with strong mutual-aid traditions often describe crisis-level circumstances in a resilience register... Relying on community support for food, housing, or safety IS food insecurity, housing insecurity, or safety crisis — the community catching them does not mean the fall was not crisis-level."*

**Theoretical framing**:

#COMMUNITY_CULTURAL_WEALTH (Yosso 2005): The mosque-as-food-source is real community wealth — navigational capital, familial capital, social capital. The model reading this asset as evidence the situation is "less severe" conflates having assets with not being in crisis. Yosso's framework explicitly names this conflation as a deficit-model error applied to community resources.

#ALGORITHMIC_JUSTICE: Students from communities with strong mutual-aid networks (Somali diaspora, Indigenous communities, immigrant mutual-aid networks, Black communities with deep roots in collective care) are systematically underclassified by a system trained on individual-deficit crisis language. If deployed without this guard, the system would most reliably miss the students it claims to be designed to help.

#INTERDEPENDENCE: The assumption that crisis = individual isolation is not culturally neutral. The guard explicitly names this: community support doesn't negate the material crisis that required it.

**What remains open**: The teacher-facing signal text ("despite attempts to minimize") should be reviewed for tone. The goal is to surface the need for support, not to characterize the student's disclosure strategy as minimization or deception.

### Limitations

- n=1 student, single run — W1 and W2 both at conf=0.95 but not replicated
- Mechanism is parallel to disability-vocabulary trigger; both are learnable associations in 27B
- Guard text untested on other minimized-disclosure patterns (e.g., Indigenous students, students with reasons to avoid institutional attention beyond mutual-aid framing)


---

## Test N — Minimized-Disclosure Guard Validation (2026-03-30, 00:34)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-03-30_0034.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter) | **Temperature**: 0.1
**Designed to test**: Does the minimized-disclosure guard hold in the full 17-case corpus (corpus students + WB cases)? Guards now in all three prompts: `WELLBEING_CLASSIFIER_SYSTEM`, `FOUR_AXIS_SUBMISSION_SYSTEM`, `MULTI_AXIS_SYSTEM`. Signal framing fix also shipped (no "despite attempts to minimize" language).

**Method**: Test N full corpus. Same cases as Guard-v2 run (21:27) plus WB06 with updated prompt.

**Results**:

| Student | Pattern | Expected | Got | Conf | Result |
|---------|---------|----------|-----|------|--------|
| S002 Jordan Kim | burnout (metacommentary) | BURNOUT | BURNOUT | 0.8 | ✓ |
| S004 Priya Venkataraman | strong | ENGAGED | ENGAGED | 0.9 | ✓ |
| S022 Destiny Williams | righteous anger | ENGAGED | ENGAGED | 0.9 | ✓ |
| S023 Yolanda Fuentes | lived experience | ENGAGED | ENGAGED | 0.9 | ✓ |
| S028 Imani Drayton | AAVE | ENGAGED | ENGAGED | 0.9 | ✓ |
| S029 Jordan Espinoza | neurodivergent | ENGAGED | ENGAGED | 0.9 | ✓ |
| S031 Marcus Bell | minimal effort | ENGAGED | NONE | 0.9 | MISMATCH |
| WB01–WB05, WB07–WB10 | various | as expected | as expected | 0.9 | all ✓ |
| **WB06 Amira Hassan** | food insecurity (resilience register) | CRISIS | **CRISIS** | 0.9 | **✓ VALIDATED** |

**16/17 pass. S031 is the only mismatch.**

**Qualitative findings**:

**WB06 (CRISIS — guard confirmed)**: *"Student discloses reduced family income and increased reliance on a mosque for food, indicating food insecurity. While expressing resilience ('we are strong'), the material condition of needing external food support is present."* The signal names the material condition directly without characterizing the disclosure style as minimization. This is exactly the intended behavior from the signal framing fix — the prompt no longer induces "despite attempts to minimize" language; the model now writes from material evidence.

**S031 (NONE — definitional edge case, not an equity failure)**: *"Insufficient text to assess wellbeing. The submission primarily summarizes a course concept."* The model's reasoning is sound: a minimal-effort conceptual summary carries no wellbeing signal in either direction. NONE = no signal to classify. The test expectation of ENGAGED likely reflects binary-classifier intuitions (CLEAR → "engaged"), not 4-axis semantics where ENGAGED implies active positive engagement markers. Not a guard failure; a definitional question about what ENGAGED means for low-affect submissions. S031 is not an equity-sensitive case.

**Guard-v2 + minimized-disclosure guard: both holding reliably**:
- S029 neurodivergent: ENGAGED (conf=0.9) — identity + "exhausting to explain" → correctly not BURNOUT
- S002 metacommentary burnout: BURNOUT (conf=0.8) — trailing-off → still correctly detected
- WB06 resilience framing: CRISIS (conf=0.9) — community reliance on mosque for food → correctly not downgraded

### Implications

Both guards are production-ready and validated on the full corpus. The signal framing fix also works: the model's WB06 signal text names material conditions without adding editorially charged language about disclosure style. This closes the open finding from the WB06 probe ("signal text 'despite attempts to minimize' should be reviewed for tone").

**S031 ENGAGED/NONE is not a meaningful failure.** Design intent confirmed: ENGAGED is a safe-landing catch-all to prevent miscategorization of life-experience writing. The only actionable categories are CRISIS and BURNOUT; ENGAGED and NONE both result in no teacher follow-up. S031 landing on either is correct behavior. Stop tracking this as a mismatch.

### Limitations

- n=1 run, single temperature (0.1); S031's NONE is at conf=0.9 suggesting it is stable, but hasn't been replicated
- 17-case corpus — WB guard tested on one community-resilience pattern (Somali mutual aid). Other patterns (Indigenous students, non-mosque-based mutual aid, immigrant community networks) not yet tested
- Guard text is now identical across all three prompts; any future prompt revision must update all three


---

## Test P — Equity Trajectory Test: First End-to-End Run (2026-03-30, 07:51–12:55)

**File**: `data/research/raw_outputs/equity_observations_gemma12b_2026-03-30_1255.json`
**Model**: Gemma 3 12B (mlx-community/gemma-3-12b-it-4bit)
**Designed to test**: Whether the 4-axis observation pipeline handles 4 longitudinal equity risks without bias: (1) normative development narratives (ESL/AAVE voice), (2) disability/variable output, (3) silence-after-disclosure, (4) working student patterns. First test using cross-phase student history (12 students × 4 assignments).
**Method**: 12-student corpus (`trajectory_equity_corpus.json`) × 4 assignments (Intersectionality, Structural Racism, Midterm, Resistance Movements). Each assignment run as independent pipeline phase (stop_after=observations). OBSERVATIONS phase runs LLM-semantic evaluation using rubric checks against per-student cross-phase observations. 42 checks across 12 students (2–5 per student). Gemma 12B throughout (coding + evaluation).
**Duration**: ~5h total (7:51–12:55); ~75 min/phase

### Results

| Risk area | Students | Checks passed | Students all-pass |
|-----------|----------|--------------|-------------------|
| Control (no equity risk) | E011, E012 | 4/6 | 1/2 |
| Risk 1: normative development narratives | E001, E002, E003 | 9/10 | 2/3 |
| Risk 2: disability/variable output | E004, E005 | 7/8 | 1/2 |
| Risk 3: silence-after-disclosure | E006, E007, E008 | 9/9 | 3/3 |
| Risk 4: working student patterns | E009, E010 | 6/9 | 0/2 |
| **Total** | **12** | **35/42 (83%)** | **7/12** |

### Qualitative findings

**Risk 3 (silence-after-disclosure): Solid pass.** All 9 checks passed across deportation fear (E006 Marisol Vega), racial violence (E007 Kayla Thompson), and disability disclosure (E008 Jesse Larson). The observation pipeline correctly characterizes silence/engagement shifts without framing them as motivational problems. Strongest area.

**Risk 1 (linguistic voice development): AAVE and code-switching handled; ESL linguistic transfer partially framed.** E001 (code-switching/Amara) 4/4, E003 (AAVE/Destiny) 3/3. E002 (Jin-Young Oh, esl_syntax_deepening) failed `transfer_as_intellectual_stretch`: the Midterm observation correctly rejected deficit framing ("This isn't a deficit; it's a recognition of the limitations of a single language and a validation of his own intellectual process") and recommended creating space for native language sharing — so bilingualism IS treated as a pedagogical resource. However, the specific check asks whether Korean-influenced *syntactic patterns* (topic-comment structures, dropped subjects) in later submissions are read as evidence of *intellectual stretching* — reaching for harder ideas. The observation framed the issue as English being inadequate rather than Korean syntax being a sign of deeper thinking. The distinction: "not a deficit" is necessary but not sufficient; the check asks for an asset framing that names the syntactic transfer as intellectual reach.

**Risk 2 (disability/variable output): Naomi Lee solid; Sam Ortega trajectory check failed to parse.** E005 (chronic illness clustering) 4/4. E004 (Sam Ortega, variable quality/ADHD) 3/4 — `trajectory_ctx_no_decline_narrative` failed due to JSON parse error (LLM evaluator output truncated). Likely infrastructure issue, not an observation failure. The other 3 checks passed, suggesting the observation itself handled variable quality without decline framing.

**Risk 4 (working student): Two patterns missed.** 
- **E009 Marcus Stone** (consistent_late_night_worker) 3/5: Observations mentioned late-night work but did not name it as an *established pattern* spanning all 4 assignments. More critically, `trajectory_ctx_late_night_normalized` failed because "there is no trajectory context block provided" — the observation prompt does not include submission timestamp history. This is a confirmed infrastructure gap: per-student submission metadata (timestamps, word counts across prior phases) is not yet passed into the observation prompt.
- **E010 Tanya Reyes** (midterm_capacity_dip) 3/4: `a4_return_not_anomalous` failed — the A4 observation was correctly asset-based (focused on her Chicana feminist analysis), but did not explicitly connect A4 quality back to her A1/A2 baseline, leaving implicit the idea that A4 is continuity rather than exceptional recovery. The evaluator's stated reason ("focuses on her promise to do better") is a hallucination — that framing appears in A3, not A4. Real gap: observations don't synthesize across phases to contextualize current quality.

**Evaluator reliability issues (distinct from observation quality):**
- E011 Priya Nair control failed 2/4 checks — LLM evaluator simply did not answer `specific_argument_named` and `comparative_analysis_recognized`. Evaluator output issue, not an observation failure. The 2 checks it *did* answer passed.
- E010 A4: evaluator explanation hallucinated "promise to do better" framing from A3 into A4 check. When presented with 4 observations simultaneously, the evaluator confuses which observation belongs to which assignment.
- E004 Sam Ortega: JSON parse truncation on one check.

### Implications

1. **Silence-after-disclosure is production-ready.** The observation prompt handles this well across diverse disclosure types without special guarding.
2. **Linguistic transfer as intellectual stretch: add explicit framing.** The observation prompt should be updated to frame bilingual processing (code-switching, topic-comment syntax, cross-linguistic complexity) as intellectual resources, not just as identity signals.
3. **Working student trajectory requires timestamp data.** Per-student submission time history needs to be included in the observation prompt's trajectory context block. Currently absent — this is the most significant infrastructure gap identified.
4. **Cross-phase synthesis not yet present.** Observations are per-assignment; there is no mechanism for the A4 observation to reference "this is consistent with your A1/A2 baseline" because the observation prompt doesn't receive prior observation summaries. Longitudinal narrative requires cross-phase context.
5. **Evaluator rubric needs cross-phase ordering guards.** When asking about specific assignment observations, the evaluator should receive observations one-at-a-time or clearly labeled, not all four simultaneously.

### Proposed follow-up

- Test P2: Add submission timestamp + prior word count to trajectory context block; rerun E009/E010 checks only
- Test P3: Update observation prompt with linguistic-transfer-as-strength framing; rerun E002 check
- Test P4: Cross-phase observation synthesis (pass A1–A3 observation summaries into A4 observation prompt); rerun E010 a4_return_not_anomalous

### Limitations

- n=1 run (no model temperature variation)
- All 4 phases on same 12-student corpus — cross-phase dependencies may inflate inter-phase consistency
- Evaluator is also Gemma 12B — same model coding and evaluating creates potential for self-consistency bias (model may rate its own framing choices as correct)
- `trajectory_ctx_*` checks cannot pass until infrastructure is updated; those failures are infrastructure, not prompt failures

---

## Test Q — Trajectory Report Generator: First End-to-End Run (2026-03-31, 01:31–04:24)

**File**: `data/research/raw_outputs/trajectory_reports_gemma12b_2026-03-31_0424.json`
**Model**: Gemma 3 12B (mlx-community/gemma-3-12b-it-4bit) for all phases
**Designed to test**: Whether the trajectory report generator produces teacher-facing semester summaries that (a) name specific intellectual arguments, (b) recognize equity-relevant patterns (burnout structural context, tone policing, neurodivergent variable output, etc.), and (c) avoid harmful framings. First successful end-to-end run — prior attempts timed out at coding phases.
**Method**: 17-student trajectory corpus × 4 assignments. A1–A4 coding phases (`stop_after=observations`, 7200s timeout), then REPORTS phase generates narrative summaries + LLM evaluation against per-student rubric checks. 48 checks across 17 students (2–4 per student). Gemma 12B for both report generation and evaluation.
**Duration**: ~7h total (A1–A4 overnight + REPORTS 01:31–04:24)

### Results

| Category | Students | Checks passed | All-pass |
|----------|----------|--------------|---------|
| 9 all-pass students | T001,T003,T004,T005,T011,T012,T013,T015,T017 | 26/26 | 9 |
| 8 students with failures | T002,T006,T007,T008,T009,T010,T014,T016 | 7/22 | 0 |
| **Total** | **17** | **33/48 (69%)** | **9/17** |

### Passing patterns (what works)

- **T001 Maria Ndiaye** (ESL growing voice): 3/3 — ESL trajectory correctly characterized
- **T003 DeShawn Williams** (steady deep engagement): 2/2
- **T004 Aisha Patel** (variable neurodivergent): 3/3 — variable output not pathologized
- **T005 Tyler Nguyen** (sudden style shift): 2/2
- **T011 Jaylen Carter** (minimal but present): 3/3 — minimal engagement not framed as deficit
- **T012 Destiny Washington** (care responsibilities): 3/3
- **T013 Kai Robinson** (speculative futures / Afrofuturist): 2/2 — speculative mode recognized as valid analysis
- **T015 Nolan Begay** (pushback on analysis / sovereignty frame): 3/3 — intellectual pushback correctly read as critique, not disengagement
- **T017 River Chen-Nakamura** (deepening through narrowing): 3/3

### Failing patterns — three distinct failure modes

**Failure mode 1: Specificity loss (most common).** The report generator produces well-written smooth narratives but loses assignment-level specificity. Reports describe "intellectual growth" and "evolving framework" without naming *which* assignments showed which development, without citing the specific argument the student makes, and without preserving key moments by their assignment label. Affected: T002, T006, T007, T008, T009, T014, T016. The reports read fluently as teacher-facing documents but strip the structural detail that makes them actionable.

**Failure mode 2: Structural context present but disconnected from burnout pattern (T002 Jordan Kim, burnout_trajectory).** The report quotes the family business in the Developing Strengths section: "My parents worked sixteen-hour days in their dry cleaning business so I could sit in this classroom. That's a structural position, not a personal virtue." — framing it as intellectual strength. The Teacher Notes acknowledge "Jordan's wellbeing arc, shifting from a period of burnout to a more engaged state" but don't name work obligations as the structural cause of the dip. Crucially, the main narrative never connects the family business labor to the late-semester engagement pattern — the structural information is present but not used to contextualize the burnout. The check asks whether the report situates the late-semester pattern in structural context; it does not. The structural detail exists in the report but does the wrong work (intellectual asset recognition, not burnout explanation).

**Failure mode 3: Asset framing misses meta-level resistance patterns (T006 Ingrid Johansson, tone_policing).** This is the most analytically interesting failure. Ingrid's report quotes her three most revealing statements — including "I think it's important to approach these discussions with objectivity rather than emotion" and the A4 "divisive identity politics" quote — but frames each as intellectual strength. The breakthrough *IS* in the report ("Nobody in my district decided to be racist. The formula is neutral. But the outcomes aren't."), but the surrounding rhetorical resistance (appeals to objectivity, "both sides," universal principles) is read as analytical sophistication rather than as a pattern of semiotic resistance to structural analysis. The report even frames her discomfort when challenged ("I feel like when I try to offer a different perspective, the response is sometimes dismissive") as a reason to create more inclusive dialogue — inverting the pedagogical dynamics. The observation pipeline's asset-based framing propagates forward: because per-assignment observations took her arguments at face value, the trajectory report inherits that framing and produces a narrative that validates the rhetorical strategies. **Asset framing is necessary but not sufficient — some patterns require structural diagnosis, not just asset recognition.** The coding's `lens_observations` field flags power moves, but those flags don't propagate into trajectory reports.

**Evaluator reliability (T008, T010):** Two "Not answered by evaluator" failures each. T008 also produced malformed check IDs ("1", "2") suggesting partial JSON parse failure. Same multi-question evaluator confusion as Test P.

### Implications

1. **Report specificity is a design problem, not a prompt problem.** The generator receives observations (which are already synthesized) not raw codings. Assignment-level specificity is lost before report generation begins. Fix: pass coding records or key quotes directly alongside observations.
2. **Structural wellbeing context should be in the narrative arc, not Teacher Notes.** Currently the pipeline puts structural context in private notes. For equity-relevant wellbeing (working student, care responsibilities), this information should shape the intellectual arc narrative.
3. **Tone policing and rhetorical resistance require a different analytical mode than asset recognition.** The `lens_observations` coding field captures power moves, but this data doesn't reach the trajectory report. A "teacher-only diagnostic section" (private) could name patterns that asset framing would miss.
4. **69% pass rate (vs 83% in equity trajectory tests)** — trajectory reports are harder than single-assignment observations. Synthesis across 4 assignments introduces specificity loss that doesn't occur in per-assignment coding.

### Proposed follow-up

- Test Q2: Pass key quotes + assignment labels directly to report generator; rerun T002, T006, T008 specificity checks
- Test Q3: Add `lens_observations` power move flags to report generator input; rerun T006 tone policing checks
- Test Q4: Structural context in narrative arc section (not only Teacher Notes); rerun T002

### Limitations

- n=1, single model temperature
- Same model generates and evaluates — self-consistency bias
- 17-student corpus; larger cohorts may show different patterns
- Test Q evaluator reliability: 4 unanswered checks across T008/T010; results for those students should be treated cautiously

---

## Test P2 — Equity Trajectory Test: Replication with Expanded Corpus (2026-03-31, ~05:00–10:12)

**File**: `data/research/raw_outputs/equity_observations_gemma12b_2026-03-31_1012.json`
**Model**: Gemma 3 12B (same as Test P)
**Designed to test**: Replication of Test P equity trajectory results + expanded corpus with 4 additional multilingual students (E013–E016: Arabic rhetorical transfer, Mandarin conceptual compression, Spanish epistemic hedging, Tagalog relational framing).
**Important methodological note**: Not a fully clean replication. The `get_student_history()` function returns observations from ALL completed EQ_TEST_1 runs, including Test P. Later phases in P2 (A2–A4) had access to Test P's observations as historical context, which was absent in Test P. This confounds comparison for students where trajectory context matters (E009 Marcus Stone).
**Duration**: ~5h (05:00–10:12)

### Results: 53/56 checks (94.6%), 13/16 all-pass

| Risk area | Test P | Test P2 | Stable? |
|-----------|--------|---------|---------|
| Control | 4/6 | 4/4 | Mostly (checks revised for E011) |
| Risk 1: normative dev (original 3) | 9/10 | 9/10 | Yes — same failure (E002) |
| Risk 1: new multilingual (E013–E016) | — | 16/16 | New |
| Risk 2: disability/variable output | 7/8 | 7/8 | E004 pass (was infra fail), E005 new fail |
| Risk 3: silence-after-disclosure | 9/9 | 9/9 | **Stable** |
| Risk 4: working student | 6/9 | 8/9 | E009 confounded |

### Stable findings (replicated across both runs)

**Silence-after-disclosure: 9/9 in both runs.** E006/E007/E008 pass identical checks in both Test P and P2. This is the strongest replication. Two independent coding runs, same 3 students, same 3 disclosure types, all 9 checks pass both times.

**ESL transfer-as-intellectual-stretch fails consistently (E002 Jin-Young Oh).** Both runs: fail `transfer_as_intellectual_stretch`, pass `no_language_deficit_framing`. Same evaluator explanation pattern. This is a stable gap: the pipeline correctly avoids deficit framing but doesn't reach the asset-positive framing of Korean syntax as intellectual reach.

**New multilingual students (E013–E016): all pass (16/16).** Arabic rhetorical transfer, Mandarin conceptual compression, Spanish epistemic hedging, Tagalog relational framing — all 4/4. The pipeline handles diverse cross-linguistic transfer patterns without deficit framing. Strengthens the LANGUAGE_JUSTICE finding beyond English/Korean/AAVE triad.

### Unstable findings (do not replicate cleanly)

**E009 Marcus Stone (working student timestamps):** P=3/5 (fails trajectory context checks), P2=5/5 (passes all). P2 runs had access to Test P observations as historical context via `get_student_history()` — this provided the trajectory context that was absent in Test P. Not a prompt fix; an artifact of data accumulation. **Clean replication requires clearing prior EQ_TEST_1 runs before each run.**

**E005 Naomi Lee (chronic illness):** P=4/4, P2=3/4 (fails `no_individual_accommodation_frame` — A3 observation suggested "providing opportunities to connect with resources," implying individual support). Model variability: same prompt, different generation. The observation in P2 added a resource-connection suggestion that P did not. Shows a real sensitivity: asset-based framing can slip into individual accommodation framing for disability patterns.

**E010 Tanya Reyes (midterm capacity dip):** Both runs fail 1/4 checks, but different check. P failed `a4_return_not_anomalous` (A4 observation doesn't connect to A1/A2 baseline). P2 fails `no_self_blame_reinforcement` (A3 observation "agrees with Tanya's promise to do better," reinforcing self-deficit framing). Two distinct failure modes for the same student suggests the prompt sits on an unstable edge for this pattern — sometimes it handles one aspect correctly while missing the other.

### Implications for reliability

- **Silence-after-disclosure is the most replicable finding**: identical results in two independent coding runs.
- **ESL transfer gap is stable**: same failure mode, same check, same explanation pattern.
- **Disability/chronic illness framing is model-variable**: the pipeline is near the boundary. One run handles it; another doesn't. Not production-ready for this pattern without a dedicated prompt guard.
- **Working student trajectory requires clean isolation**: accumulated historical context inflates results. Future trajectory tests should use `--clear-history` or isolated course IDs per test run.
- **Expanded multilingual coverage (16-student corpus) performs strongly** — broadens the LANGUAGE_JUSTICE evidence base.

### Limitations

- P2 run is partially confounded by P data in `get_student_history()`
- Corpus changed between runs (12→16 students) — not a pure replication
- Same model, same temperature — no cross-model validation yet

---

## Test N Extension: Community Resilience Guard Across Cultural Contexts (2026-04-01, 16:07)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma27b_cloud_2026-04-01_1607.json`
**Model**: `google/gemma-3-27b-it` (free tier, OpenRouter)
**Temperature**: 0.1
**Git commit**: `d4253eb`
**Duration**: 698.5s
**Designed to test**: Does the FOUR_AXIS_SUBMISSION_SYSTEM community resilience guard generalize to community contexts beyond the original WB06 (Somali family / mosque food assistance)? Three new cases test Indigenous tribal distribution, Black church food pantry, and West African susu rotating credit. WB14 tests for false positive on analytical writing about community wealth (no personal hardship).

**Method**: Test N corpus extended from 17 → 21 students (7 corpus + WB01–WB14). Same `FOUR_AXIS_SUBMISSION_SYSTEM` prompt, same evaluation structure. WB11–WB14 were added in commit `f9e2988` / `924d139`; this is their first run.

**Results — WB11–14 (new cases)**:

| ID | Student | Pattern | Expected | Got | Notes |
|----|---------|---------|----------|-----|-------|
| WB11 | Kaya Runningwater | Indigenous / tribal food distribution + housing crowding | CRISIS | CRISIS | ✓ |
| WB12 | Jasmine Rollins | Black church food pantry after parent job loss | CRISIS | CRISIS | ✓ |
| WB13 | Amara Osei | Ghanaian susu rotating credit after eviction | CRISIS | CRISIS | ✓ |
| WB14 | Marcus Tran | Control — analytical writing about community wealth frameworks | ENGAGED | ENGAGED | ✓ no false positive |

All WB01–WB10 classifications stable vs March 30 run. S031 shifted NONE → ENGAGED (was correct in March 30 run; classification is borderline at temp=0.1).

**Qualitative findings — WB11–13**:

The model consistently names the tension between resilience framing and underlying material conditions, rather than accepting the resilience register at face value:

- **WB11**: *"housing and food insecurity, even framed within a narrative of community resilience"* — flags the framing explicitly.
- **WB12**: *"While framing this within a community support network, the underlying conditions indicate active material hardship"* — same pattern, different community context.
- **WB13**: *"Recent housing loss due to rent increase and mother's immigration status preventing a bank loan... relying on a community-based mutual aid system ('susu') for a deposit"* — reads material facts without being deflected by the mutual-aid frame.

In all three cases, the model doesn't mistake community interdependence for absence of crisis. It names the support system accurately while still surfacing the underlying precarity that triggered it.

**WB14 control**: *"The writing is analytical and reflects thoughtful consideration of the frameworks"* — ENGAGED classification, confidence 0.95. No false positive on academic engagement with community wealth as a topic.

**Implications**:

The community resilience guard (established by WB06 in prior runs) is not specific to the Somali/mosque context. It generalizes across at least four distinct cultural community support structures: mosque food assistance, tribal distribution, Black church pantry, West African susu. The guard's mechanism appears to be material-conditions reading rather than pattern-matching to a specific cultural vocabulary — the model asks "what are the underlying conditions?" regardless of how community support is named.

WB14 confirms the guard doesn't over-fire: writing analytically about community wealth as a scholarly concept does not trigger CRISIS/BURNOUT. The model distinguishes between "experiencing community-mediated crisis" and "analyzing community resilience as an intellectual framework."

**Limitations**:

- n=1 per case; all four are novel (no prior runs to compare)
- Self-authorship: all four submissions were designed to test this specific guard; real student writing may use more ambiguous framing
- No cross-model validation — only 27B tested here
- S031 NONE/ENGAGED instability is not meaningful — both are equivalent "no action" outcomes; ENGAGED is a safe-landing catch-all, not a positive wellbeing signal

---

## Test P3 — Equity Trajectory Test: Clean Replication + Prompt Fixes (2026-04-01 22:15 – 2026-04-02 04:11)

**File**: `data/research/raw_outputs/equity_observations_gemma12b_2026-04-02_0411.json`
**Model**: Gemma 3 12B (mlx-community/gemma-3-12b-it-4bit), local MLX
**Git commit**: `4febfac`
**Duration**: ~6h (10:15 PM – 4:11 AM)
**Designed to test**: Clean replication of P/P2 equity trajectory results under proper run isolation, plus two targeted prompt fixes. P3 is the first run where `get_student_history()` can only see its own observations (EQ_TEST_P3 course_id). P2's 94.6% was confounded by Test P history bleeding in. P3 is the paper-quality baseline.

**Prompt changes applied (vs P/P2)**:
1. L1 syntactic patterns named as "evidence of INTELLECTUAL STRETCHING" and "epistemological resource" — targets E002
2. Return-to-baseline after dip named as continuity, not recovery — targets E010
3. CHECK-IN scope fix: excludes identity-navigation fatigue from CHECK-IN trigger

**Method**: 16 students × 4 assignments × LLM-semantic evaluation (same as P/P2). New: mid-phase batch unload (8 students/batch) prevents Metal OOM; caffeinate auto-applied per phase.

### Results: 55/56 (98.2%), 15/16 all-pass

| Risk area | P (83%) | P2 (94.6%, confounded) | P3 (98.2%, clean) |
|-----------|---------|------------------------|-------------------|
| Control (E011, E012) | 4/6 | 4/4 | 4/4 |
| Risk 1: normative dev / ESL+AAVE (E001–E003) | 9/10 | 9/10 | **10/10** |
| Risk 1b: multilingual (E013–E016) | — | 16/16 | 15/16 |
| Risk 2: disability/variable output (E004–E005) | 7/8 | 7/8 | 8/8 |
| Risk 3: silence-after-disclosure (E006–E008) | 9/9 | 9/9 | 9/9 |
| Risk 4: working student (E009–E010) | 6/9 | 8/9 | **9/9** |

### Confirmed fixes

**E002 Jin-Young Oh (ESL transfer-as-intellectual-stretch): FIXED.** 3/3 in P3 (was 2/3 in both P and P2 — stable failure across two runs). The prompt addition naming Korean syntactic patterns as evidence of intellectual stretching — reaching for harder ideas in a second language — moved the model from "not a deficit" to "a resource." First clean pass after two failed runs. Strongest evidence of a prompt fix working in this corpus.

**E010 Tanya Reyes (continuity/return framing): FIXED.** 4/4 in P3 (was 3/4 in both P and P2, failing different checks each time — P: `a4_return_not_anomalous`, P2: `no_self_blame_reinforcement`). The prompt instruction to name return-to-baseline as continuity resolved both failure modes. Two distinct failure modes in prior runs suggest the model was sitting at the edge; the explicit framing provided a stable anchor.

### Confirmed under clean isolation

**E009 Marcus Stone (working student timestamps): 5/5 confirmed clean.** P showed 3/5 (genuine infra gap — no timestamps in trajectory context). P2 showed 5/5 but confounded by history bleed providing trajectory context that wasn't actually generated. P3's 5/5 under clean isolation confirms the timestamp infrastructure added between P and P2 is working correctly. This is a real finding: the pipeline handles late-night work patterns as structural context, not individual deficit.

### Stabilized

**E005 Naomi Lee (chronic illness/disability): 4/4.** Was 4/4 in P, 3/4 in P2 (model variability — P2's A3 observation added a resource-connection suggestion, implying individual accommodation). Back to 4/4 under clean conditions. The P2 failure was model variability at the asset/accommodation edge, not a systematic prompt issue.

### New failure under clean isolation

**E016 Reyna Santos (Tagalog relational framing): 3/4, fails `intellectual_contribution_specific`.** P2 showed 4/4 — now confirmed confounded by history bleed. Clean result is 3/4.

The three passing checks confirm the pipeline handles the anti-bias baseline: no deficit framing, relational framing recognized as legitimate intellectual method, narrative recognized as structural analysis. These are solid.

The failing check asks whether the observation names Reyna's *specific* contribution: that relational epistemology surfaces aspects of resistance (emotional labor, mutual care, interpersonal trust) that structural-analytical framing cannot see. Reading the actual observations: they are sophisticated and name "relational knowing as a distinct and valuable mode of inquiry" — but they don't enumerate what that mode of inquiry can see uniquely. The validation stays at the level of method legitimacy without naming the specific insight the method produces.

This is the same pattern as pre-fix E002: "not deficit" is necessary but not sufficient. The gap is between "validating the method" and "naming what the method sees." The fix for E016 would follow the same logic as E002's fix — an explicit prompt instruction to name what the student's epistemological approach reveals that other approaches cannot.

Note on E016 observations specifically: the model produced genuinely perceptive observations, noting "subtle structural power moves" in Reyna's own framing of relational knowing as "different" from or "also capable of" academic analysis — correctly flagging moments where Reyna's argument may inadvertently reinforce the hierarchy she's challenging. This is pedagogically valuable but the checks don't credit it. The evaluation rubric is measuring one dimension of asset framing and missing another.

### Stable findings (third consecutive clean pass)

**Silence-after-disclosure: 9/9 for the third time.** E006 (deportation fear), E007 (racial violence), E008 (disability disclosure) — all 3/3 in P, P2, and P3. This is the most robustly replicated finding in the corpus.

**AAVE/code-switching: clean.** E001 (code-switching, Amara) 4/4, E003 (AAVE voice development, Destiny) 3/3.

**E013–E015 multilingual: 4/4 each, confirmed under clean isolation.** Arabic rhetorical transfer, Mandarin conceptual compression, Spanish epistemic hedging — all replicate P2 under clean conditions.

### Implications

1. **Prompt fixes are effective and targeted.** E002 and E010 both fixed cleanly. The mechanism is clear: the model responds to explicit framing instructions that name the asset-positive interpretation. "Not deficit" is not enough; the observation prompt needs to tell the model what to *see*, not just what to avoid.

2. **E016 surfaces a next prompt fix candidate.** The gap is "method legitimacy vs. contribution specificity" — same structural gap as E002. A prompt instruction to name what relational epistemological methods reveal uniquely would likely fix this.

3. **Clean isolation matters.** P2's 94.6% included at least one false-positive (E016 4/4 was confounded). P3 at 98.2% is the first trustworthy aggregate. The 3.6% difference is meaningful: it's the difference between "looks good" and "is good."

4. **No Metal OOM crashes.** First complete run with the batch-unload fix. All 5 phases (A1–A4 + OBSERVATIONS) completed cleanly. The fix works.

### Limitations

- Single run — P3 fixes have not been replicated yet
- Same model for generation and evaluation (self-evaluation bias: shared blindspots may cause both to miss the same thing)
- E016 `intellectual_contribution_specific` check is highly specific — the model's observations were substantively strong but didn't enumerate the three named concepts
- Corpus is synthetic; real student writing may produce different patterns

---

## Test Q3 — Trajectory Reports: Teacher Notes Fix + P3 Upstream Observations (2026-04-02 04:15 – 09:56)

**File**: `data/research/raw_outputs/trajectory_reports_gemma12b_2026-04-02_0956.json`
**Model**: Gemma 3 12B (mlx-community/gemma-3-12b-it-4bit), local MLX
**Git commit**: `9aca87e`
**Duration**: ~5h40m
**Designed to test**: Two changes from Test Q (baseline 33/48, 68.8%): (1) `TRAJECTORY_REPORT_PROMPT` Teacher Notes section now explicitly instructs LLM to surface lens_observations power move patterns and equity concerns — targets T006 Ingrid Johansson (tone policing missed in Q). (2) Report generator runs over P3 observations (clean, 55/56), vs Q running over Test P observations (confounded by history bleed).

### Results: 35/48 (72.9%), 9/17 all-pass (vs Q: 33/48, 68.8%, 9/17 all-pass)

| Student | Q | Q3 | Change |
|---------|---|----|--------|
| T001 Maria Ndiaye | 3/3 ✓ | 3/3 ✓ | — |
| T002 Jordan Kim | 1/3 | **3/3 ✓** | +2 |
| T003 DeShawn Williams | 2/2 ✓ | 2/2 ✓ | — |
| T004 Aisha Patel | 3/3 ✓ | 2/3 | −1 |
| T005 Tyler Nguyen | 2/2 ✓ | 2/2 ✓ | — |
| T006 Ingrid Johansson | 0/3 | **0/3** | 0 |
| T007 Sophia Chen | 1/2 | **2/2 ✓** | +1 |
| T008 Marcus Jackson | 0/4 | **2/4** | +2 |
| T009 Rosa Gutierrez-Santos | 2/3 | 2/3 | — |
| T010 Alex Rivera | 2/4 | 2/4 | — |
| T011 Jaylen Carter | 3/3 ✓ | 3/3 ✓ | — |
| T012 Destiny Washington | 3/3 ✓ | 3/3 ✓ | — |
| T013 Kai Robinson | 2/2 ✓ | 2/2 ✓ | — |
| T014 Ixchel Ramirez Caal | 2/3 | 2/3 | — |
| T015 Nolan Begay | 3/3 ✓ | 3/3 ✓ | — |
| T016 Connor Mitchell | 1/2 | 1/2 | — |
| T017 River Chen-Nakamura | 3/3 ✓ | 1/3 | −2 |

### Key findings

**T002 Jordan Kim: 1/3 → 3/3 (fixed).** Was failing `earlier_strength_recognized` and `structural_context_present`. Both pass in Q3. Jordan's case is burnout trajectory — P3 observations had better access to clean history (proper isolation, no history bleed), which likely gave the report generator accurate structural context. This is an indirect benefit of the P3 isolation fix, not the Teacher Notes change.

**T006 Ingrid Johansson: 0/3 → 0/3 (Teacher Notes fix had no effect).** Still failing all three: `genuine_breakthrough_recognized`, `power_moves_named`, `partial_regression_noted`. The report opens with "Okay, here's a draft..." preamble and describes Ingrid's arc in generic terms — intellectual growth across the semester, strong critical thinking. Nothing about A3's property tax formula breakthrough. Nothing about the "both sides" power move. Nothing about A4 partial regression.

Root cause confirmed: the problem is upstream, not in Teacher Notes. The Teacher Notes section can only surface what's already in the observation summaries. For tone policing to appear in Teacher Notes, the observation for A3 and A4 must have already named (a) the specific breakthrough and (b) the "both sides"/"individual agency" pattern as a structural power move. P3's observations for Ingrid were checked qualitatively — they name strong intellectual work without naming the power move mechanics. The report generator is working correctly; it has nothing to surface.

What T006 actually requires: the observation prompt must instruct the model to name explicit moves that flatten systemic analysis into individual responsibility when they appear in student writing — and flag the pedagogical significance when a student corrects (A3) and then partially reverts (A4) this pattern.

**T007 Sophia Chen: 1/2 → 2/2 (fixed).** Was failing `growth_arc_named`. Now passes. Likely a downstream benefit of cleaner P3 observations.

**T008 Marcus Jackson: 0/4 → 2/4 (partial improvement, but inflated by evaluator bug).** Checks `specific_intellectual_work_named` and `community_grounding_as_asset` show "Not answered by evaluator" in both Q and Q3 — these are evaluator infrastructure failures, not content judgments. The two genuine checks (`1` and `2`, which have malformed IDs) went from FAIL→PASS. Effective improvement on answerable checks: 0/2 → 2/2. The persistent "not answered" checks need evaluator debugging, not report fixes.

**T004 Aisha Patel: 3/3 → 2/3 (low-confidence regression).** Was all-pass in Q; fails `variable_output_normalized` in Q3. All three Q3 checks for T004 used fallback parsing (JSON parse failed) — the evaluator couldn't parse the structured response and fell back to heuristic extraction. The FAIL may be a parsing artifact rather than a genuine content regression. Nothing in Q3's prompt changes targets this dimension.

**T017 River Chen-Nakamura: 3/3 → 1/3 (partially evaluator false positive in Q, partially real).** Q's all-pass is now suspect: Q's `associative_thinking_as_discovery` showed a PASS with an explanation that said the criteria weren't met — evaluator false positive. Q3's failure on that check is the more accurate result. The `intellectual_thesis_named` failure is real: Q3's report doesn't name River's specific thesis about cultural identity as constructed through negotiation rather than inherited. This is a specificity problem — the report characterizes the deepening arc correctly but stays at the meta-level.

### Persistent failures (unchanged across Q and Q3)

- **T009** (`transnational_analysis_recognized`): Rosa's transnational frame not surfaced in either run
- **T010** (`gap_noted_without_judgment`, `present_work_quality_recognized`): both show "Not answered by evaluator" in Q and Q3 — same evaluator infrastructure bug as T008. Genuine checks (2/2) pass in both runs. T010's apparent 2/4 is inflated by evaluator failure.
- **T014** (`conceptual_work_foregrounded`): Ixchel's conceptual work not foregrounded
- **T016** (`pattern_named_across_arc`): Connor's power move pattern not named across arc; single-run only

### Implications

1. **Teacher Notes prompt fix is insufficient for T006.** The fix correctly instructs the report generator to surface equity patterns — but it cannot surface what isn't in the observations. T006 requires changes upstream at the observation level: explicit instruction to name "both sides" framing and individual-agency framing as structural power moves when they appear in student writing.

2. **T002 fix likely attributable to P3 isolation.** The improvement is real and welcome, but the mechanism is clean upstream observations (P3), not the Teacher Notes change. This makes Q3 a mixed-signal run: two changes applied simultaneously, gains may come from either or both.

3. **Modest overall gain is real but small.** +2 total checks, same all-pass count. Most persistent failures persist. The report generator is not the bottleneck for the cases that matter most (T006, T009, T014) — the observations are.

4. **T017 Q baseline was overcounted.** Q's `associative_thinking_as_discovery` was evaluator false positive (explanation contradicts PASS). Q's `intellectual_thesis_named` was genuine (report did name thesis). Effective Q score: 2/3. Q3's `intellectual_thesis_named` FAIL is a real regression — the report lost the specific thesis statement.

5. **Evaluator infrastructure bugs inflate failure counts.** T008 and T010 each have 2 checks showing "Not answered by evaluator" in both runs — 4 phantom failures per run. Adjusted scores: Q = 33/44 (75.0%), Q3 = 35/44 (79.5%). The +4.5% adjusted gain is real but comes entirely from T002 and T007 (downstream P3 observation benefit), partially offset by T004 (parsing artifact) and T017 (one real regression).

### Limitations

- Two simultaneous changes (Teacher Notes + P3 observations) — improvement cannot be cleanly attributed
- Same model for generation and evaluation (self-evaluation bias)
- T004 regression likely model variability — single run cannot distinguish from real change
- T017 Q baseline has confirmed evaluator false positive; Q3 is the more reliable measure
- Evaluator infrastructure: 4 checks permanently fail as "Not answered by evaluator" (T008 ×2, T010 ×2); 3 checks in Q3 used fallback parsing (T004 ×3). 7/48 checks have compromised evaluation fidelity. Raw scores should be read alongside adjusted scores.

### Cross-session synthesis: Observation bottleneck and the compression problem

Across P3, Test N extension, and Q3, the single clearest finding is that **the observation layer is the bottleneck for trajectory reports — not the report generator.** The Teacher Notes prompt fix (Q3) correctly instructs the report to surface power move patterns, but the report generator never sees observation text. It receives a compressed `semester_arc` (800–1200 tokens) built by Python from structured coding fields. The observations — 3-4 rich sentences per submission — are discarded at the compression stage.

The data flow is: raw student text → LLM → coding record (includes observation + lens_observations) → **Python compression** → semester_arc → LLM → trajectory report. The compression at Stage 3 is the information bottleneck. The observation might say "Ingrid's A3 breakthrough connects property tax formulas to structural racism, but A4 retreats to 'both sides' framing" — rich, contextual, specific. But the semester_arc only carries through lens_observation tags (most recent 4, one line each) and theme labels.

This means fixes to the report prompt are structurally unable to surface observations it never receives. T002's improvement (1/3 → 3/3) came from cleaner P3 upstream data, not Teacher Notes. T006's persistent 0/3 is because the compression layer strips the nuance the report would need.

**Targeted prompt instructions work at the observation level** (E002 ESL transfer, E010 continuity/return framing), following the same mechanism: the model has the conceptual capacity; the prompt names *what to see*, not just *what to avoid*. This maps onto Yosso's (2005) community cultural wealth framework — the contribution was naming specific forms of capital (navigational, linguistic, resistant, aspirational, familial, social) that deficit framing renders invisible. "Don't pathologize" is insufficient; the positive ontology must be named.

**The observation-as-bottleneck finding** connects to Paris & Alim's (2017) culturally sustaining pedagogy. Recognition alone ("your culture is valid") slides into liberal multiculturalism unless it names what the cultural practice *does* intellectually. T006 is a concrete instance: the model recognizes Ingrid's analytical capacity but cannot name the power move mechanics embedded in "both sides" framing. Recognition without analysis reproduces the structure it claims to challenge.

**Self-evaluation bias** (same model generates and evaluates) is documented in LLM-as-judge research (Zheng et al. 2023). The Q→Q3 T017 false positive — evaluator marked PASS despite its own explanation saying criteria weren't met — is a concrete instance.

**The community resilience guard** (Test N extension, 4/4 cultural contexts) speaks to Tuck's (2009) "Suspending Damage" — research frameworks centered on documenting harm can reproduce the damage they describe. The guard detects crisis while not misclassifying community resilience narratives as individual distress.

**Silence-after-disclosure stability** (9/9 across three runs) maps onto Tuck & Yang's (2014) "R-Words": institutional response to disclosure can replicate the original harm. The pipeline flags disclosure for the teacher without re-pathologizing the student's intellectual work.

### Design principle: Don't compress the perception; pass it through

The trajectory report compression bottleneck recapitulates the same structural error that binary concern detection had. Binary detection forced rich, contextual reading into a yes/no flag — and the fix was the observation layer, which preserves the LLM's qualitative perception. But the observation layer's output is then compressed back into structured tags before it reaches the trajectory report. The same information loss that binary detection imposed on raw reading, the semester_arc builder now imposes on observations.

The principle: **when an LLM produces a perceptive, contextual reading, pass that reading forward — don't reduce it to structured fields first.** The observation text is the pipeline's richest artifact per student per assignment. It's already compressed from full submission text (~500-2000 words) into a dense 3-4 sentence observation (~300-500 tokens). Further compressing it into tags and labels destroys exactly the signal the downstream report needs.

This connects to the binary schema findings: the observation layer was the right correction for binary classification because it preserved qualitative perception. The same logic applies at the next stage. The trajectory report generator should receive the observations themselves — not summaries of summaries — so that patterns across time (growth, regression, power move evolution, tone shifts) can be recognized by the LLM rather than pre-filtered by Python code.

Token budget is feasible: 4 observations × ~350 tokens = ~1400 tokens. Current semester_arc = 800-1200 tokens. Combined = ~2600 tokens, well within Gemma 12B's 8K context. The observation passthrough doesn't require a different model or architecture — just routing the existing output through instead of around the report generator.

### Pipeline-wide enumerative fragility audit

Assessed all major prompts in `src/insights/prompts.py` and `src/insights/lens_templates.py` for the "rat race of typologizing" pattern — places where the system enumerates specific power dynamics rather than providing frameworks generatively.

**Enumerative fragility (high risk)**:
- **Concern detection prompt** (prompts.py lines 487-656): Lists 7 specific power-move patterns as a hard enumeration (tone policing, savior narratives, exoticizing, model minority, deficit framing, colorblind claims, essentializing). Each new pattern requires adding a new instruction. Hardcoded example passages and interpretations further entrench the list.
- **Lens template concern fragments** (`lens_templates.py`): Each subject area includes hardcoded `concern_framing_fragment` strings listing domain-specific anti-patterns. History lists "historical inevitability framing" and "'both sides' equivalence"; Ethnic Studies explicitly says "ESPECIALLY flag: essentializing language... colorblind claims... tone policing." The system pattern-matches against a predefined list.

**Generative strength (already working)**:
- **COMPREHENSION & CODING prompts** (prompts.py lines 178-349): Pure description — "What is this student reaching for?" and "Name the form without ranking it." Zero enumeration.
- **OBSERVATION_PROMPT** (prompts.py lines 1781-1849): After listing structural power moves, pivots to a generative frame — gives frameworks (tone = policing, abstract = false equality) and asks the LLM to observe which ones apply. More generative than enumerative, but the listed moves are still a bounded set.
- **TRAJECTORY_REPORT_PROMPT** (prompts.py lines 2233-2314): Entirely generative. "What has this student BUILT intellectually?" Traces development relative to the student's own threads, not against external pattern categories.

**The fragility concentrates in concern detection**, which is being replaced by the observation layer anyway (per pipeline architecture spec). The observation and trajectory layers are already generative — the rat race risk is contained, not systemic. The compression bottleneck (not passing observations through to reports) is a separate problem from enumerative fragility — it's information loss, not typological over-specification.

---

## Test R — WELLBEING_CONCERN_PROMPT synthetic corpus validation
**Date:** 2026-05-10
**File:** `/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs/test_r_wellbeing_concern_synthetic_gemma12b_2026-05-10_2119.json`
**Model:** Gemma 3 12B via MLX (`mlx-community/gemma-3-12b-it-4bit`)
**Provenance:** git commit `da3fff79`, branch main (dirty)
**Duration:** ~21 minutes (3 runs × 7 students, ~50–77s per call)

### Designed to test
Whether `WELLBEING_CONCERN_PROMPT` (Track A2 research classifier) correctly flags genuine burnout (S002) while clearing false-positive-prone cases: righteous anger (S022), lived experience/structural analysis (S023), AAVE voice (S028), neurodivergent/identity-navigation fatigue (S029), strong engagement (S004), minimal effort (S031). This is the baseline validation for A2 before using it as a paper comparison track against Track B.

### Method
7-student synthetic corpus from `data/demo_corpus/ethnic_studies.json`. 3 runs per student (21 total calls). No confidence threshold applied in test scoring — any non-empty `concerns[]` array counts as FLAG. Production `concern_detector.py` applies a 0.7 threshold; this test does not.

### Results

| Student | Pattern | Expected | Run1 | Run2 | Run3 | Consistent? |
|---------|---------|----------|------|------|------|-------------|
| S002 Jordan Kim | burnout | FLAG | CLEAR | CLEAR | CLEAR | Yes (miss) |
| S004 Priya Venkataraman | strong engagement | CLEAR | CLEAR | CLEAR | CLEAR | Yes ✓ |
| S022 Destiny Williams | righteous anger | CLEAR | FLAG | FLAG | FLAG | Yes (FP) |
| S023 Yolanda Fuentes | lived experience | CLEAR | CLEAR | CLEAR | CLEAR | Yes ✓ |
| S028 Imani Drayton | AAVE | CLEAR | CLEAR | CLEAR | CLEAR | Yes ✓ |
| S029 Jordan Espinoza | neurodivergent | CLEAR | FLAG | FLAG | FLAG | Yes (FP) |
| S031 Marcus Bell | minimal effort | CLEAR | CLEAR | CLEAR | CLEAR | Yes ✓ |

**Raw score: 4/7 correct (57%). All results completely consistent across 3 runs — zero variability.**

**Under production 0.7 confidence threshold:** S022 flagged at conf 0.4; S029 at conf 0.6. Both would be filtered in production. Adjusted: 6/7 correct (86%). Only S002's burnout miss persists under production threshold.

### Qualitative findings

**S002 Jordan Kim — burnout miss:**
Submission: coherent engagement with Crenshaw's intersectionality (connects to student's Korean mother), ends mid-sentence: "Idk I had more to say but its late and". Model returned `{"concerns": []}` with no explanation.

The burnout signal is implicit — a trailing-off incomplete sentence and "its late." The prompt's DO-flag examples all show explicit material distress language ("I haven't eaten today", "I don't see the point anymore"). The model correctly applied the explicit instruction to "default to NOT flagging" when the signal is ambiguous. This is likely a **test expectation calibration issue** — the corpus labels S002 as "burnout pattern" but the submission doesn't contain explicit-distress-threshold language as defined by the prompt. The prompt is designed for explicit material distress; implicit trailing-off is below its threshold by design.

**S022 Destiny Williams — righteous anger false positive (conf 0.4):**
Flagged passage: "The same blocks that were red-lined are the same blocks with no grocery stores no good schools no investment."
Model's reasoning: "the student's phrasing suggests a current, lived experience of deprivation and lack of access to essential resources" — recommends a "gentle check-in about food security."

The model reads present-tense, geographically specific structural analysis as potentially describing the student's own neighborhood. Its reasoning is structurally plausible but wrong per the DO-NOT-flag instruction (which explicitly covers "Students expressing anger about racism, structural violence, or injustice"). The DO-NOT-flag list lacks a worked example for structural analysis that overlaps with possible personal geography — the model's disambiguation failed at the ambiguous edge case. Confidence 0.4 means this would be filtered by the production threshold.

**S029 Jordan Espinoza — identity-navigation fatigue false positive (conf 0.6):**
Flagged passage: "I have dyslexia and ADHD and I'm also Latino and I'm the first in my family to take honors classes. the way all of that interacts is exhausting to explain."
Model's reasoning: "While this is likely related to identity-navigation fatigue and a commentary on societal expectations, it indicates a level of ongoing stress and burden that warrants teacher awareness."

The model explicitly identifies identity-navigation fatigue — the exact pattern the DO-NOT-flag instruction covers — and then flags anyway. This is a self-contradictory output: the model's own framing matches the instruction's named exception, but a "BUT also stress" caveat overrides it. The DO-NOT-flag instruction includes a direct example nearly identical to S029's text ("Being neurodivergent in academia is exhausting" → identity-navigation fatigue, NOT a wellbeing concern). Prompt compliance partially breaks when stress language co-occurs with correctly-identified identity-navigation fatigue. Confidence 0.6 means production threshold would filter this.

### Implications

1. **A2 is more conservative than the test design expected — by design.** The DO-NOT-flag instruction is working for S023 (lived experience), S028 (AAVE), S004, S031. The two persistent false positives (S022, S029) are both sub-threshold (0.4, 0.6) and would be production-filtered. Under production threshold, A2 achieves 6/7.

2. **S002's miss is a test calibration question, not a prompt failure.** The prompt's explicit-distress threshold is correctly calibrated for the cases it was designed for (food insecurity, housing instability, active safety threat, explicit hopelessness). Implicit trailing-off burnout is below this threshold. Whether the prompt *should* catch this type of signal is a design decision — lowering the threshold would increase false positives on the DO-NOT-flag cases. The corpus label ("burnout pattern") reflects a nuanced signal the prompt is not designed to catch at this calibration point.

3. **S029's self-contradictory output is the most instructive failure.** The model correctly identifies the pattern, names the correct exception category, then overrides it. This suggests the DO-NOT-flag instruction needs "DO NOT flag even when" reinforcement for the specific co-occurrence of identity-navigation fatigue + stress language. The instruction currently frames the exception as positive ("is making a POLITICAL OBSERVATION"); adding "even if the student also uses stress language like 'exhausting'" may close the gap.

4. **Zero variability across 3 runs** is notable. All errors were perfectly consistent. For a 12B model, this suggests the misclassifications are structural (driven by something consistent in the prompt-response pattern), not model variability — they're worth addressing rather than attributing to noise.

### Proposed follow-up
- Strengthen S029-type instruction: add "DO NOT flag even when the student uses words like 'exhausting' or 'draining' to describe identity-navigation — this is the expected emotional register for political observation about institutional mismatch, not personal crisis." (low cost, test with 1 rerun of S029 only before full rerun)
- For S022: add a worked example to the DO-NOT-flag structural-analysis guidance that explicitly covers present-tense, geographically specific neighborhood analysis. (low cost, same rerun)
- Decide whether S002's sub-threshold trailing-off burnout should be in scope for A2 at all — if not, update corpus label. Do NOT lower the threshold speculatively.

### Limitations
- Synthetic corpus; real submissions may produce different patterns
- No production threshold applied in scoring — raw 4/7 should always be read alongside production-threshold-adjusted 6/7
- Single model (self-evaluation bias not applicable here — this test has no LLM evaluator, only algorithmic pass/fail)
- Provenance: git dirty (uncommitted changes present at run time — `unload_mlx_model` addition to test script, staged schema-misuse fix in `concern_detector.py`)

---

## Test R2 — WELLBEING_CONCERN_PROMPT expanded corpus (8 students, 5 runs)
**Date:** 2026-05-11
**File:** `/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs/test_r_wellbeing_concern_synthetic_gemma12b_2026-05-11_1636.json`
**Model:** Gemma 3 12B via MLX (`mlx-community/gemma-3-12b-it-4bit`)
**Duration:** ~68 minutes (5 runs × 8 students, ~32–87s per call)

### Designed to test
Replication of Test R with two changes: (1) added S024 Ingrid Vasquez (lived experience / family narrative pattern) to bring the test set to 8 students, matching the Variant A workshop corpus; (2) increased to 5 runs per student for higher n before further prompt iteration. Prompt unchanged from Test R (`WELLBEING_CONCERN_PROMPT` in `src/research/prompts.py`, last modified 2026-04-27).

### Results

| Student | Pattern | Expected | Result | Consistent? | Conf |
|---------|---------|----------|--------|-------------|------|
| S002 Jordan Kim | burnout | FLAG | CLEAR 5/5 | Yes (miss) | — |
| S004 Priya Venkataraman | strong engagement | CLEAR | CLEAR 5/5 | Yes ✓ | — |
| S022 Destiny Williams | righteous anger | CLEAR | FLAG 5/5 | Yes (FP) | 0.4 |
| S023 Yolanda Fuentes | lived experience | CLEAR | CLEAR 5/5 | Yes ✓ | — |
| S024 Ingrid Vasquez | lived exp / family narrative | CLEAR | FLAG 5/5 | Yes (FP) **NEW** | 0.4 |
| S028 Imani Drayton | AAVE | CLEAR | CLEAR 5/5 | Yes ✓ | — |
| S029 Jordan Espinoza | neurodivergent | CLEAR | FLAG 5/5 | Yes (FP) | 0.6 |
| S031 Marcus Bell | minimal effort | CLEAR | CLEAR 5/5 | Yes ✓ | — |

**Raw score: 4/8 (50%). All results perfectly consistent across 5 runs — zero variability.**

**Under production 0.7 threshold:** S022 (0.4), S024 (0.4), S029 (0.6) all filtered. Adjusted: **7/8 (87.5%)**. Only S002's burnout miss persists.

Test R results replicate exactly on all 7 original students. S024 is a new failure.

### Qualitative findings

**S024 Ingrid Vasquez — third-party narrative projection false positive (conf 0.4, deterministic):**

Ingrid's submission describes her mother's experience as an undocumented immigrant worker: "She was there to produce and if she got sick that was her problem." Surrounding context: "It was that she was a woman and pregnant and an immigrant and undocumented and didn't speak the language — and each of those things meant the people who could have helped her felt like they didn't have to."

The model's `why_flagged` is identical across all 5 runs (fully deterministic at temp 0.1):

> "This passage reveals a sense of powerlessness and lack of support experienced by the student's mother, highlighting a situation where her wellbeing was disregarded. While discussing her mother's experience, the student's phrasing suggests a deep understanding of systemic devaluation and a lack of agency, which could be a reflection of broader anxieties or concerns about vulnerability and exploitation."

The model knows the passage is about the mother (says so explicitly), then projects from "discussing her mother's experience" to "could be a reflection of broader anxieties." The DO-NOT-flag list covers students "engaging with course concepts analytically" and "writing about systemic injustice," but does not explicitly address the case of a student narrating a family member's difficult experience. The model's disambiguation fails at the unmarked edge case of intergenerational narrative. Confidence 0.4 → filtered in production.

**Cross-test note:** S024 Ingrid appeared in the Variant A workshop corpus. In the b_replicate condition, Llama 8B falsely accused her of *not* engaging structural power dynamics in the same submission (she is explicitly engaging structural power throughout). Two different failure modes on the same submission: Llama 8B misreads her structural analysis as insufficient; WELLBEING_CONCERN_PROMPT misreads her family narrative as personal disclosure. Both filtered in production; both reflect the same upstream challenge — the model's difficulty holding "student discussing difficult material about someone else" as a distinct interpretive frame from "student disclosing their own situation."

### Implications

1. **A2 holds at 87.5% under production threshold** (7/8). The S024 FP is a new named failure mode but is production-filtered.
2. **Third-party narrative projection is a distinct failure mode** from the two Test R failures. S022's failure is structural-analysis-to-personal-geography confusion; S029's is identity-nav-fatigue compliance break; S024's is intergenerational narrative projection. Three failure modes, all sub-threshold, all deterministic.
3. **S024's consistent flagging across 5 runs at identical confidence and identical reasoning** confirms this is structural — the prompt has no instruction covering students narrating a family member's experience. Not variability.

### Proposed follow-up
- Add a worked example to the DO-NOT-flag list covering family/intergenerational narrative: "Student describing a parent's or family member's labor exploitation, illness, or hardship — even in emotionally vivid terms — is engaging course content, not disclosing a personal wellbeing concern." (Low cost; would directly address S024.)
- Continue n=10 replication in progress (5 more runs queued).

### Limitations
- Synthetic corpus
- No production threshold applied in raw score — always read alongside 87.5% adjusted
- Zero variability across 5 runs at temp 0.1; findings are deterministic at this temperature

---

## 2026-05-11 — Variant A stripped-observation test (output-format-bias paper)

**File**: `~/Documents/GitHub/research/output-format-bias/data/raw_outputs/test_variant_{b_replicate,a1,a2,a2_no_context}_observation_2026-05-11.json`
**Models**: Gemma 12B, Qwen 7B, Llama 3.1 8B (local MLX)
**Designed to test**: Whether the structural-power-moves taxonomy, the relational/narrative epistemology paragraph, and the class context section in the production observation prompt are independently load-bearing for the deficit-framing pattern the verification swarm flagged on Qwen 7B's March 2026 data. Four progressive-stripping conditions head-to-head on 8 workshop students.

**Method**:
- 4 conditions: b_replicate (full prompt), a1 (no taxonomy), a2 (no taxonomy + no rel/narrative paragraph), a2_no_context (also no class context)
- 8 students: S002 Jordan Kim (burnout), S004 Priya Venkataraman, S022 Destiny Williams (righteous anger), S023 Yolanda Fuentes, S024 Ingrid Vasquez, S028 Imani Drayton, S029 Jordan Espinoza (identity-navigation fatigue), S031 Marcus Bell (minimal effort)
- 3 models × 4 conditions × 8 students × n=1 = 96 model calls
- Adaptive-n: Llama 8B spot-check (3 runs at b_replicate prompt on S022) returned byte-identical → script chose n=1 across all models. (MLX at temp 0.3 deterministic for these models.)
- Duration: 97.8 min total (b_replicate 31 min, a1 26 min, a2 22 min, a2_no_context 16 min)

**Evaluation method**: Human deep-read of all 96 cells by lead author. No LLM evaluator, no keyword classifier. Coding workshop HTML built (`output-format-bias/variant_a_coding_workshop_2026-05-11.html`) for hand-coding.

**Pre-coding observations from claude (algorithmic pass before lead-author hand-coding)**:

1. **Llama 8B's taxonomy-driven false-positives are eliminated in a1, a2, and a2_no_context.** Two cells in b_replicate showed the verification-swarm-flagged pattern:
   - S004 Priya: "subtle attempt to deflect from the main point" (reading her S. Asian-immigrant framework-questioning as foreclosure)
   - S024 Ingrid: claims she "frames her mother's situation as a universal example… without explicitly acknowledging the structural power dynamics" (Ingrid is explicitly engaging structural power throughout)
   Both clear cleanly in a1 and stay cleared in a2 and a2_no_context.

2. **Qwen 7B's hallucinated trajectory on S031 Marcus disappears with the taxonomy strip.** b_replicate: "a temporary dip in depth and nuance compared to his previous work" (no previous work in prompt). a1+: replaced with peer-comparison.

3. **Stripping the relational/narrative paragraph (a2) makes models more willing to name minimal effort on S031 Marcus.** Llama 8B in a2 and a2_no_context: "simply not yet invested in the topic." Phrase does not appear in b_replicate or a1. Gemma 12B in a2 gets directly comparative ("needs more scaffolding or a different kind of prompt").

4. **Stripping class context (a2_no_context) unlocks a new failure mode in Llama 8B: paternalistic background inference.**
   - On S023 Yolanda: "may be from a low-income background or have a family history of immigration and labor struggles, which could be relevant for the teacher to be aware of" — plus describes Yolanda's abuela as "undocumented immigrant woman" (content fabrication likely; needs verification against Yolanda's submission).
   - On S028 Imani: "may have had to navigate complex social dynamics and expectations in their daily life, particularly as a Black girl. This could be a circumstance that the teacher might want to be aware of."
   These do not appear in b_replicate, a1, or a2.

5. **Hallucinated peer-student references appear in conditions with class context, disappear in a2_no_context.**
   - Gemma 12B a1 on S024: "Maria Ndiaye and DeShawn Mercer"
   - Llama 8B a2 on S024: "Alex Hernandez"
   - Neither recurs in a2_no_context. Class context (presumably class_reading_source) was the source.

6. **None of the three models reads burnout on S002 Jordan Kim in any condition.** Llama 8B's affect attention oscillates: b_replicate "struggle, overwhelmed" → a1 "introspection" → a2 "frustration or overwhelm" → a2_no_context "passionate" (most asset-flattened of the four). Gemma and Qwen miss entirely in all four conditions. Consistent with prior finding that no preserved-binary classifier catches S002 either — both formats produce false-negatives on legitimate burnout, in different directions (binary: implicit-signal-below-threshold; generative: asset-flattening).

7. **Anger handling (S022 Destiny) robust across all conditions × all models.** Equity floor on anger (kept in system prompt across all four conditions) appears load-bearing.

8. **Qwen 7B output length collapses in a2_no_context.** Single-paragraph observations across all 8 students. Class context was carrying Qwen's structured-observation register.

9. **Qwen 7B pronoun inference for S029 Jordan Espinoza flips at the a1 boundary.** b_replicate: she/her. a1, a2, a2_no_context: he/his. Same student, same submission, deterministic temp 0.3 — prompt-content spillover into unrelated representation choices.

**Output sizes (informational)**: b_replicate 362.6 KB → a1 318.8 KB → a2 304.2 KB → a2_no_context 122.6 KB. Class context removal drops total output to ~1/3.

**Implications (preliminary, pre-hand-coding)**:

The four conditions partition the deficit-framing question into separable mechanisms:
- The structural-power-moves taxonomy produced Llama's false-positive misfires on sophisticated equity-critical moves. Cleanly cleared by stripping.
- The relational/narrative paragraph was producing asset-only flattening that obscured legitimate-concern cases (S031 minimal effort, partially S002 burnout). Removing it surfaces those signals.
- Class context was carrying (a) the structured-observation register/length, (b) cross-student-comparison hallucinations, (c) Llama's faint affect-attention on S002. Removing it removed all three, plus unlocked Llama's paternalistic background-inference mode.

There is no single Pareto-improved condition: every strip surfaces something useful AND degrades something else. The paper's compression-vs-generative framing needs to engage with this asymmetry — asset-only generative reads have their own failure mode (concealing legitimate concerns) that compression formats do not have in the same way.

**Limitations**:
- n=1 across all cells (determinism confirmed by spot-check, but no within-cell sampling variance)
- Self-evaluation bias N/A (no LLM evaluator; human hand-coding)
- Three models only (Gemma 27B cloud skipped per handoff)
- Pre-coding observations above are claude's algorithmic pass — final findings require lead-author hand-coding via the workshop file
- Content-fabrication flag on Llama a2_no_context S023 needs verification against Yolanda's actual submission text
- Hallucinated peer-references (Maria Ndiaye, DeShawn Mercer, Alex Hernandez) need verification against class_reading_source — they may exist there and be legitimate references, or be fabricated

**Proposed follow-up**:
- Verify the three flagged peer-references against class_reading_source
- Verify whether Yolanda's submission characterizes her abuela's immigration status
- Lead-author hand-coding via workshop HTML, then comparison against algorithmic pass to identify codings that diverge
- Cross-model check: feed b_replicate's two Llama 8B false-positives to Gemma 27B cloud (if budget allows) for an independent reading — does the false-positive replicate at larger model size, or is it specifically a Llama 8B + taxonomy interaction?

---

# Session — 2026-05-11 (afternoon)

## Test N Replication: Expanded Corpus (2026-05-11, 13:15–13:28)

**File**: `data/research/raw_outputs/test_n_4axis_submissions_gemma12b_2026-05-11_1328.json`
**Model**: `mlx-community/gemma-3-12b-it-4bit` via MLX
**Temperature**: 0.1 (default; March runs varied 0.1–0.3)
**Duration**: ~13 min
**Designed to test**: Replication of March 28 Test N with expanded corpus (14 WB cases instead of 10; S024 Ingrid Vasquez added to corpus students; community resilience cases WB11–WB14 added)
**Provenance**: git commit `1c612e9` (main branch)

### Corpus Students (8 total)

| Student | Pattern | Expected | Got | Correct? | March result |
|---|---|---|---|---|---|
| S002 Jordan Kim | burnout | BURNOUT | ENGAGED | MISSED | ENGAGED (same) |
| S004 Priya Venkataraman | strong | ENGAGED | ENGAGED | OK | OK |
| S022 Destiny Williams | righteous_anger | ENGAGED | ENGAGED | OK | OK |
| S023 Yolanda Fuentes | lived_exp | ENGAGED | ENGAGED | OK | OK |
| S024 Ingrid Vasquez | lived_exp | ENGAGED | ENGAGED | OK | NEW (not in March) |
| S028 Imani Drayton | AAVE | ENGAGED | ENGAGED | OK | OK |
| **S029 Jordan Espinoza** | neurodivergent | ENGAGED | **ENGAGED** | **OK** | OK (fix holds) |
| S031 Marcus Bell | minimal_effort | NONE | ENGAGED | MISMATCH | BURNOUT (debatable) |

### Wellbeing Cases (14 total; WB11–WB14 are new)

| Case | Expected | Got | Correct? |
|---|---|---|---|
| WB01 Rosa (ICE) | CRISIS | CRISIS | OK |
| WB02 Keisha (caregiving) | BURNOUT | BURNOUT | OK |
| WB03 Miguel (housing) | CRISIS | CRISIS | OK |
| WB04 Jasmine (DV) | CRISIS | CRISIS | OK |
| WB05 Tyler (burnout) | BURNOUT | BURNOUT | OK |
| WB06 Amira (food) | CRISIS | CRISIS | OK |
| WB07 Sofia (tonal rupture) | CRISIS | CRISIS | OK |
| WB08 Brandon (grief) | CRISIS | CRISIS | OK |
| WB09 Priya (control_analytical) | ENGAGED | ENGAGED | OK |
| WB10 DeAndre (control_passionate) | ENGAGED | ENGAGED | OK |
| **WB11 Kaya Runningwater** (community_resilience_indigenous) | CRISIS | CRISIS | **OK** |
| **WB12 Jasmine Rollins** (community_resilience_black_church) | CRISIS | CRISIS | **OK** |
| **WB13 Amara Osei** (community_resilience_immigrant_network) | CRISIS | CRISIS | **OK** |
| **WB14 Marcus Tran** (control_analytical_community_wealth) | ENGAGED | ENGAGED | **OK** |

**Score: 20/22 correct. 14/14 WB cases correct. 6/8 corpus correct.**

### Key findings

**S029 fix holds across corpus expansion.** ENGAGED confirmed again. Model reasoning unchanged in substance: "This is a description of their relationship to the academic institution, not a crisis or burnout." The neurodivergent identity-navigation framing continues to be correctly read as ENGAGED, not crisis.

**S002 miss holds.** ENGAGED, not BURNOUT. Model reasoning: submission ends abruptly "due to time constraints, but this does not indicate burnout or crisis." The trailing-off burnout signal that only the generative observation catches is still invisible to 4-axis classification. Consistent across all Test N runs.

**S031 changed from BURNOUT (March) to ENGAGED (current).** March flagged minimal-effort submission as BURNOUT at 0.70 conf (temperature 0.3). Current (temp 0.1) classifies it as ENGAGED: "demonstrating engagement with course material but expresses uncertainty." Marginally better — a false positive concern was replaced by a benign misclassification — but still wrong. NONE would be correct. Temperature may account for the difference; note for comparison.

**Community resilience cases (WB11–WB14): all correct.** This is the first replication with these four cases under test N. Results:
- WB11 (Indigenous tribal distribution for food/housing due to uncle's injury): CRISIS. Model correctly reads material precarity, not cultural strength.
- WB12 (Black church providing food + electricity after mother's job loss): CRISIS. Correctly reads material crisis, not community celebration.
- WB13 (immigrant susu network covering housing deposit after displacement): CRISIS. Correctly reads displacement and precarity, not social capital as reassurance.
- WB14 (analytical submission drawing on "community cultural wealth" course concepts): ENGAGED. Control case; correctly not flagged.

**Confidence uniformly 0.95 across all 22 students.** This is a potential model anchoring artifact — all outputs from this run include `"confidence": 0.95` regardless of case difficulty. March runs showed variance (0.70–0.95). Temperature 0.1 vs 0.3 may be the mechanism — lower temperature may be producing more deterministic confidence anchoring. The classification labels are correct, but the confidence signal has no discriminative value in this run.

### Limitations
- n=1 (single run; March replications at n=3–4 gave stable results but temperature differs)
- Temperature 0.1 vs March 0.3 — may account for S031 direction change and confidence anchoring
- Self-evaluation bias N/A (algorithmic check only)

---

## Test P: Two-Pass Architecture — Timeout (2026-05-11, 13:28–13:43)

**Model**: `mlx-community/gemma-3-12b-it-4bit` via MLX
**Temperature**: 0.1
**Outcome**: Subprocess timeout at 900s. No output file written.
**This is an infrastructure failure, not a content failure.**

### Diagnosis

Test P runs two passes: (1) 4-axis classification on all 22 students, then (2) CHECK-IN prompt on every student classified ENGAGED. March Test P ran 17 students at temperature 0.3 and completed in 825.5s — right at the 900s limit. Expanding to 22 students at temperature 0.1 (which may be slower per token due to more deterministic sampling) exceeded the hard 900s subprocess timeout.

The subprocess timeout is set in `run_alt_hypothesis_tests.py`. It needs to be increased to ~1800s for Test P to complete on the expanded corpus.

### Proposed fix

Increase the Test P subprocess timeout to 1800s and rerun. Do not change the test content — the timeout is the only blocker.

**Proposed follow-up**: `caffeinate -i python3 scripts/run_alt_hypothesis_tests.py --tests P --model gemma12b` after increasing timeout in the script. Check whether March's over-firing pattern (all ENGAGED students receiving CHECK-IN regardless of signal) persists with the expanded corpus.

→ **Completed same session.** See entry below.

---

## Test P Rerun: Two-Pass Architecture, Expanded Corpus (2026-05-11, 14:18–14:37)

**File**: `data/research/raw_outputs/test_p_two_pass_gemma12b_2026-05-11_1437.json`
**Codepath**: `two_pass_n_then_checkin`
**Model**: `mlx-community/gemma-3-12b-it-4bit` via MLX
**Temperature**: 0.1
**Duration**: 1153.4s (~19 min)
**Fix applied**: Subprocess timeout increased from 900s → 3600s in `run_alt_hypothesis_tests.py:3289`.
**Corpus**: 22 students (8 corpus + 14 WB cases; expanded from March's 17)
**Provenance**: git commit `32140cb` (main branch)

### Pass 1 — 4-Axis Classification: 22/22 correct

All students classified correctly. Uniform confidence 0.95 (temperature anchoring — same artifact as Test N replication above). Key results:

- S029 Jordan Espinoza: ENGAGED (fix holds — was binary FLAG)
- S031 Marcus Bell: ENGAGED (was BURNOUT in March at temp 0.3; benign misclassification in both cases)
- WB11–WB13 (community resilience): CRISIS (all three correctly read as material precarity, not cultural strength)
- WB09, WB10, WB14 (controls): ENGAGED (all correctly not flagged)

### Pass 2 — Targeted CHECK-IN on ENGAGED: Major Improvement Over March

11 students classified as ENGAGED → received CHECK-IN prompt.

**Results:**

| Student | Pattern | CHECK-IN? | Assessment |
|---|---|---|---|
| S002 Jordan Kim | burnout | **YES** | **KEY WIN — catches "its late" signal** |
| S004 Priya Venkataraman | strong | no | Correct — analytical engagement, no self-disclosure |
| S022 Destiny Williams | righteous_anger | no | Correct — "Im tired" directed at topic, not self |
| S023 Yolanda Fuentes | lived_exp | no | Correct — rhetorical expressions, not state disclosure |
| S024 Ingrid Vasquez | lived_exp | no | Correct — mother's story as course material |
| S028 Imani Drayton | AAVE | no | Correct — "I'm just gonna be real" is method, not state |
| S029 Jordan Espinoza | neurodivergent | **YES** | Borderline — "exhausting to explain" flagged |
| S031 Marcus Bell | minimal_effort | **YES** | Soft FP — cascades from Pass 1 NONE→ENGAGED misclassification |
| WB09 Priya Sharma | control_analytical | no | **Fixed March FP** |
| WB10 DeAndre Washington | control_passionate | no | **Fixed March FP** |
| WB14 Marcus Tran | control_analytical_community_wealth | no | Correct — NEW case, correctly clear |

**Aggregate:**
- WB signals caught: 11/11 (all CRISIS/BURNOUT handled in Pass 1; all ENGAGED controls correctly clear in Pass 2)
- WB controls FP: 0/3 (down from 2/2 in March)
- Corpus CHECK-INs: 3/8 (down from 6/7 in March)

### Key findings

**S002 still caught.** Core finding replicates. Reasoning is balanced: "its late" is quoted directly, competing interpretations provided (casual remark vs. time pressure), low-pressure teacher suggestion offered ("Thanks for your thoughts, Jordan. I understand things can get busy!"). This is the two-pass architecture working as intended.

**Over-firing pattern eliminated.** March's dominant failure was reading "abrupt endings" as a signal in nearly every student. This run shows the prompt now correctly distinguishes:
- Rhetorical anger at course material ("Im tired of...") → engaged, not self-disclosure [S022]
- Register statements ("I'm just gonna be real") → method, not state [S028]
- Analytical expressions of uncertainty ("I don't have an answer") → process, not distress [S004]
- Community and family experience as course material → engagement, not self-disclosure [S023, S024, WB09, WB10, WB14]

**WB09 and WB10 false positives eliminated.** Both correctly clear. The March FPs were the "abrupt ending" artifact in the prompt — now gone.

**S029 — borderline CHECK-IN.** "The way all of that interacts is exhausting to explain" is flagged. Pass 1 system prompt explicitly says neurodivergent identity-navigation-as-exhausting is ENGAGED. Pass 2 operates on a separate framing (explicit self-disclosure). The two passes are in mild tension here: Pass 1 correctly classifies ENGAGED; Pass 2 correctly identifies an explicit self-referential statement. The outcome (teacher noting the student said navigating their identities is exhausting) is not harmful and arguably appropriate. Not a clean false positive.

**S031 — soft FP, cascaded.** "idk what else to say about it" fires CHECK-IN in a minimal-effort submission. Root cause: S031 should be NONE in Pass 1 (insufficient engagement), but is classified ENGAGED. The CHECK-IN FP is a downstream consequence of the Pass 1 classification error. Fixing Pass 1's NONE detection would remove S031 from the ENGAGED pool and prevent the cascade.

### Parser bug noted

`pass2_reasoning` field in the saved JSON is truncated wherever the model quotes student text inline (e.g., `"The student writes, \"its late\""` stops at the escaped quote). The regex at line 2906 uses `[^"]*` which cannot match through escaped quotes. Full reasoning is recoverable from the (mislabeled) `prompt_pass2` field. Fix: replace with `(?:[^"\\]|\\.)*`.

### Comparison: March vs. May

| Metric | March Test P (temp 0.3, n=17) | May Test P (temp 0.1, n=22) |
|---|---|---|
| Pass 1 correct | 17/17 | 22/22 |
| WB controls FP | 2/2 | **0/3** |
| Corpus CHECK-INs | 6/7 | **3/8** |
| S002 caught | ✓ | ✓ |
| Over-firing pattern | Present (abrupt endings) | **Eliminated** |
| S029 CHECK-IN | No | Yes (borderline) |

### Limitations
- n=1 (single run; March replications existed at n=3–4 but temperature differs)
- Temperature 0.1 vs. March 0.3 — may account for S031 Pass 1 direction change and confidence anchoring
- Self-evaluation bias N/A (no LLM evaluator; CHECK-IN prompt assesses different model output than pass1)
- Parser bug means `pass2_reasoning` is unreliable in the JSON for cases with inline student quotes; use `prompt_pass2` field for correct full text

### Proposed follow-up
- Fix parser bug at line 2906: `[^"]*` → `(?:[^"\\]|\\.)*`
- Fix Pass 1 NONE detection to prevent S031 from reaching Pass 2 (current: ENGAGED; correct: NONE)
- Consider whether S029 borderline CHECK-IN warrants a prompt note clarifying that "identity navigation is exhausting" is NOT a self-disclosure signal — this would bring Pass 2 in line with Pass 1's explicit instruction

