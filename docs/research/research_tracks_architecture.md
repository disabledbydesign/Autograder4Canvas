# Research Tracks Architecture — Autograder4Canvas

This document describes the classification tracks in the research apparatus, the logic each follows, and the anti-bias mechanisms built into each. It is meant for collaborators reading anonymized data alongside the system's outputs.

The research apparatus runs **four** independent classifiers on each student submission, side-by-side, so their outputs can be compared:

- **Track A1 — Binary concern classifier (combined scope)** — flags wellbeing concerns AND power-moves language (essentializing, colorblind ideology, savior narrative, etc.) in a single FLAG/CLEAR call. The historical retired-from-production classifier.
- **Track A2 — Binary concern classifier (wellbeing-only scope)** — flags wellbeing concerns only, scope-matched to Track B's 4-axis classifier. Built specifically so the binary-vs-4-axis comparison isolates *format* (binary vs 4-axis) from *scope* (combined vs wellbeing-only).
- **Track B — 4-axis wellbeing classifier + targeted check-in** — the production successor to the binary classifiers.
- **Track C — Generative observation** — the qualitative reading; production primary.

Both binary classifiers (A1 and A2) share the same equity-hardening machinery — anti-tone-policing post-processing, course-content vs student-wellbeing distinction, confidence threshold, structured output. They differ only in scope. This is intentional: it lets the paper attribute differences in classifier behavior to the *scope difference*, not to differences in equity protections.

The point of running them all together is to make design tradeoffs visible: where the binary classifiers miss something the qualitative reading catches; where the structured 4-axis classifier converges with each binary; where each produces false flags; what the *scope mismatch* between combined and wellbeing-only binaries actually costs.

## Source code layout

Research code lives in `src/research/` — separated from production code in `src/insights/` and `src/gui/`:

```
src/research/
  __init__.py
  prompts.py            # CONCERN_PROMPT (combined),
                        # WELLBEING_CONCERN_PROMPT (wellbeing-only),
                        # CONCERN_CRITIC_PROMPT, CONCERN_IMMANENT_CRITIQUE_ADDENDUM
  concern_detector.py   # detect_concerns(scope="combined" | "wellbeing")
  research_engine.py    # ResearchEngine — orchestrates the comparison
  research_window.py    # QMainWindow shell for the research GUI
  research_panel.py     # 4-track per-student comparison panel
```

Production code (`src/insights/`) keeps the 4-axis wellbeing classifier, observation, synthesizer, etc. — anything used in the production pipeline. The research apparatus imports production functions directly (it never duplicates them) but production never imports from research.

The historical research test harness lives in `scripts/run_alt_hypothesis_tests.py` — Tests A through O, including the simplified binary classifiers (`BEST_CONCERN_PROMPT`, `LENGTH_CONCERN_PROMPT`) used for early ablation studies. **Note for paper authors:** `BEST_CONCERN_PROMPT` was a retrospective recreation written in commit `765ba64` (March 26) after raw test output was lost in `tmp/`. It is *not* the same as the production-grade equity-hardened wellbeing-only binary (`WELLBEING_CONCERN_PROMPT` in `src/research/prompts.py`); the latter was written deliberately to match v2's full hardening, scope-swapped.

## Cross-cutting design principles

These principles hold across all four tracks and shape what each is allowed to do:

1. **Don't compress the perception; pass it through.** When the model produces a qualitative reading, that reading should propagate forward into downstream stages — not be reduced to structured fields. Binary classification (Tracks A1 and A2) failed on this principle in production. The observation layer (Track C) corrects it.

2. **Anti-enumeration.** Don't typologize every possible pattern. Give the model frameworks and let it observe. Enumerative prompt instructions ("flag X, Y, Z patterns") are fragile; generative framing scales.

3. **Course content ≠ student wellbeing.** Many courses (Ethnic Studies, sociology, history, literature) require students to discuss violence, trauma, oppression, genocide. A student writing *about* these topics is doing the assignment. The classifier must distinguish the subject matter from the student's personal state.

4. **Self-disclosure of identity is not deficit.** A student naming their own disability, neurodivergence, language status, or marginalized identity is doing self-advocacy through a course framework — intellectual work, not a wellbeing concern. The question is not whether the student has a hard time; it is whether the systems around them were built for someone else.

5. **Identity-navigation fatigue is not a wellbeing signal.** A student writing that explaining their identity is exhausting, or that navigating institutional expectations around their race, disability, language, or gender is draining, is making a *political observation*, not disclosing their current state. This exclusion appears explicitly in the wellbeing-only binary classifier (Track A2) and in the Track B check-in prompt.

---

## Tracks A1 and A2 — Binary concern classifier (`src/research/concern_detector.py`)

Both binary classifiers are implemented in a single function, `detect_concerns(scope=...)`, parameterized over scope:

- `scope="combined"` → uses `CONCERN_PROMPT` (Track A1)
- `scope="wellbeing"` → uses `WELLBEING_CONCERN_PROMPT` (Track A2)

Everything else is identical: the LLM call, the post-processing pipeline, the confidence threshold, the output structure.

### Shared architecture (both A1 and A2)

- Always a separate LLM call per submission.
- Receives: submission text, signal-matrix pre-screen results, optional class context, optional teacher-profile fragment, scope.
- Returns: a list of `ConcernRecord` objects, each with `flagged_passage`, `surrounding_context`, `why_flagged`, `confidence` (0.0–1.0).
- After LLM output, runs two post-processing filters (see anti-bias section below).
- Final filter: drops anything with confidence < 0.7.
- Has a non-LLM fallback (signal matrix only) at fixed 0.3 confidence — gets filtered out by the threshold, so without an LLM, both classifiers return essentially nothing.

### Pre-screen ("signal matrix")

A non-LLM keyword + VADER-sentiment scanner that runs first. Output categories include `CRITICAL`, `APPROPRIATE`, etc. The `APPROPRIATE` category is *filtered out* before sending to the LLM, because smaller models would otherwise try to analyze student strengths as concerns.

### Track A1 — Combined scope (`CONCERN_PROMPT`)

Prompt opens with: *"You are looking for signs of STUDENT WELLBEING issues or language that essentializes or dismisses groups."*

The DO-flag list includes both wellbeing-style and power-moves-style triggers:

- Essentializing language ("all X people", "they always")
- Colorblind claims ("I don't see race", "reverse racism")
- Tone policing
- Savior narratives, exoticizing, model-minority framing
- Deficit framing of poverty
- Personal crisis / hopelessness / self-harm
- Direct requests for help

This is the historical scope — what the original concern classifier was designed to flag.

### Track A2 — Wellbeing-only scope (`WELLBEING_CONCERN_PROMPT`)

Prompt opens with: *"Review this student submission for passages that suggest the student may be experiencing wellbeing concerns in their OWN current life that the teacher should be aware of."*

The DO-flag list contains *only* material-distress signals:

- Active food insecurity ("I haven't eaten today", "no food at home")
- Active housing instability ("we lost the apartment")
- Active danger or safety threat (DV, immigration enforcement threat, suicidal ideation)
- Recent or active loss in the student's OWN life (death of family, recent diagnosis)
- Sleep deprivation or burnout from material conditions
- Expressions of hopelessness about THEIR OWN life (not course material)
- Direct requests for help that go beyond the academic context

The DO-NOT-flag list is identical to A1's, *plus* an explicit identity-navigation-fatigue exclusion lifted from the Track B check-in prompt.

### Why both versions exist

Comparing A1 and A2 isolates the **scope effect** (combined vs wellbeing-only) while holding the **equity hardening** constant. The most informative cells in the data:

- **A1 flag + A2 clear** → almost certainly a power-moves flag (essentializing, colorblind, etc.) — A2 wasn't asked to find these.
- **A2 flag + A1 clear** → A2 caught a wellbeing signal A1 missed, despite both having the same wellbeing-protection equity machinery. Likely surfacing an effect of *prompt scope narrowing* — telling the model only to look for wellbeing concerns improves wellbeing recall.
- **Both flag** → robust signal, both prompt scopes converge.
- **Neither flag** → consensus clear.

Run on the self-care assignment in ETHN-1-03 Week 7 (n=25): A1 flagged 6, A2 flagged 4, with 3 students flagged by A1 only (likely power-moves), 1 by A2 only, 3 by both, 18 cleared by both.

### Why this was retired in production

Binary classification compresses the perception too aggressively — the act of reducing a nuanced reading to flag/clear loses the very signal that makes the reading valuable. It also has high false-positive risk when the model conflates course content with student state. The 4-axis classifier (Track B) and observation (Track C) replace it in the production pipeline. The binary classifiers are preserved in `src/research/` for research comparison only.

### Anti-bias mechanics (applies to both A1 and A2 identically)

**1. Anti-tone-policing post-processing (`_check_bias_in_output`):**

Scans the LLM's `why_flagged` text for tone-policing markers:

```
aggressive, too emotional, overly emotional, hostile tone,
angry rhetoric, threatening, confrontational, too angry,
irrational, hysterical
```

If any of these are found AND the flagged passage contains structural critique keywords (capitalism, white supremacy, colonialism, patriarchy, etc.), the rationale is rewritten to:

> ⚠ POSSIBLE MODEL BIAS: The model characterized this student's tone negatively. The passage appears to contain structural critique, which is appropriate academic engagement, not a concern. Original model assessment: [original]

Confidence is then lowered by 0.3.

**Rationale:** students writing structural critique often get tone-policed by AI. This catches the moment and makes the bias visible to the teacher rather than hiding it.

**2. Course content vs. student wellbeing distinction:**

Both prompts contain an extensive "Do NOT flag" list:

- Students discussing, analyzing, or emotionally responding to assigned course material about historical trauma, violence, colonialism, genocide, sexual violence, slavery, forced removal — *this is the assignment, not a concern*
- Students expressing anger, grief, shock, or moral outrage about injustice described in course material
- Students using words like "triggered", "overwhelming", or "hard to read" when describing emotional response to difficult course material
- Students expressing anger about racism, structural violence, or injustice (this is appropriate academic engagement)
- Students describing their own past experiences with discrimination as analytical material
- Students critiquing institutional racism, policing, immigration enforcement
- Students using urgent or passionate language about justice issues
- Students whose writing style differs from academic English conventions (AAVE, multilingual mixing, code-switching)
- Students with fragmented, nonlinear, associative writing (cognitive style, not confusion)
- Students using colloquial intensifiers like "crazy", "insane", "wild" reacting to course content
- Students naming their own disability, neurodivergence, or learning difference as part of analysis (self-advocacy)
- Students whose thoughts "aren't organized" — read as awareness of mismatch with academic norm, not inability
- (A2 only, additional) Identity-navigation fatigue — political observation, not a current wellbeing signal

Then post-processing scans `why_flagged` for content-flagging language:

```
triggering, disturbing content, graphic, violent content,
may be triggering, this passage may, difficult material,
sensitive content/material/topic, mature content,
content warning, distressing content/material,
indication of distress
```

And separately for subject-matter-explanation patterns:

```
discusses/mentions/references/describes (rape|violence|murder|
assault|genocide|trauma|abuse), course content … difficult/
heavy/disturbing/graphic
```

If either matches, the rationale is rewritten to:

> ⚠ LIKELY COURSE CONTENT (not student distress): The model flagged this because the subject matter is disturbing, not because the student appears to be in personal crisis. Original model assessment: [original]

Confidence lowered by 0.4.

**3. Class context passthrough:**

When available, the full-class reading is passed into the prompt. This makes *relational harms* visible (e.g., tone-policing patterns within the class discussion, dynamics where some voices are getting dismissed) — which a single-submission view would miss.

In current research-engine usage, class context is *deliberately not* injected into the binary tracks (proven to hurt classification stability). It remains in the prompt template for use cases where the class reading is available and stable.

**4. Adversarial critic pass (TODO, not yet wired in):**

A `CONCERN_CRITIC_PROMPT` exists in `src/research/prompts.py` but is not currently invoked. It would re-prompt the LLM to argue *against* each surviving flag, dropping ones that don't survive critique. Pending replication-study frequency data before activation.

---

## Track B — 4-axis wellbeing classifier + targeted check-in (`src/insights/submission_coder.py`)

Production code, used by both the production insights pipeline and the research apparatus.

**Purpose:** Replace binary flagging with a four-way structured classification, plus a separate "soft" signal for engaged students who may still merit a brief check-in.

### Pass 0 — Pre-scan (`_prescan_for_personal_signals`)

A semantic scan across all chunks of the raw submission text, looking for sentences that describe the student's *own* personal circumstances. This is necessary because:

- Personal-circumstance sentences are often buried in procedural or topic-focused writing
- Single-pass classifiers tend to weight the dominant register and miss isolated disclosures
- The pre-scan surfaces these sentences explicitly so they can be foregrounded for the classifier

Reads RAW submission text (not summaries or observations). Test N validation: 8/8 detection, 0 false positives on raw text.

### Pass 1 — 4-axis classifier (`classify_wellbeing`)

Sends the submission to the LLM with the pre-scan-found sentences foregrounded. Returns one of four axis values:

- **CRISIS** — evidence of active danger (DV, housing loss, food insecurity, immigration enforcement, safety threat, recent loss, suicidal ideation)
- **BURNOUT** — evidence of depletion from material conditions (work schedule, sleep deprivation, caregiving burden), but not active danger
- **ENGAGED** — student is doing the work; no material wellbeing evidence found
- **NONE** — insufficient text for classification (typically <15 words)

Plus: `signal` (a brief explanation of what the classifier saw) and `confidence` (0.0–1.0).

### Pass 2 — Targeted CHECK-IN (`classify_checkin`)

Runs *only* on students classified as ENGAGED by Pass 1. Looks for a different category of signal: not material conditions, but **register shift** — moments when the student briefly steps outside the assignment to comment on their own current state (an apology for quality, mention of exhaustion, a "things have been rough"). Returns a boolean `check_in` flag plus reasoning.

### Anti-bias mechanics in Track B

**1. Identity-navigation fatigue is explicitly excluded** (in `TARGETED_CHECKIN_SYSTEM`):

> IDENTITY-NAVIGATION FATIGUE IS NOT A CHECK-IN SIGNAL. A student who writes that explaining their identity is exhausting, that they are tired of justifying their existence, or that navigating institutional expectations around their race, disability, language, or gender is draining — is describing their relationship to the institution, not their current capacity. This is political observation, not self-disclosure about state. Do not flag it.

**2. Family/community experience as course material is excluded:**

> Students drawing on personal or community experience AS COURSE MATERIAL are engaged, not disclosing their state. A student writing about family hardship to analyze a concept is doing the assignment.

**3. Approach metacommentary is excluded:**

> Statements about the student's APPROACH to the assignment ("I'm just gonna be real", "let me try to explain", "here's my take") are about method, not state.

**4. Calibration to false-flag-low:**

> Set check_in to true ONLY when the competing interpretations are genuinely balanced — when a reasonable teacher could go either way. If your analysis leans toward 'nothing to note,' check_in is false.

**5. Evidence-extraction variant (experimental, available but not currently active):**

`WELLBEING_EVIDENCE_EXTRACTION_SYSTEM` is a two-step alternative classifier: STEP 1 extracts only concrete material evidence (present-tense, about the student's own circumstances, material rather than identity-based); STEP 2 derives the axis from the extracted evidence only. The goal is to make the inference "identity → deficit" structurally unreachable by separating evidence extraction from classification.

---

## Track C — Generative observation (`src/insights/submission_coder.py:observe_student`)

**Purpose:** Produce a 3–4 sentence qualitative reading of the submission — what the student is reaching for, how they're entering the material, what's working in their thinking. Not a classification; a description.

**Architecture:**
- Single LLM call per submission
- Receives: submission text, full class context (the synthesizer's reading of the whole class), assignment prompt, optional teacher lens, optional trajectory context
- Returns: free-form text

**Why this is the production primary, not the binary classifiers:**

Track C does not compress the perception. The model reads the submission and produces a description. Downstream stages (themes, synthesis, trajectory reports, feedback drafter) consume the observations directly, preserving the qualitative reading. This propagation principle is the architectural lesson learned from the binary-classifier design.

### Anti-bias mechanics in Track C

Track C's anti-bias work is mostly upstream — in what gets passed in, and what gets asked.

**1. Class context, not isolated submission:**

The observer sees the synthesizer's reading of the whole class first. This makes relational moves visible (who's building on whom, who's getting dismissed, where care is or isn't being extended) — moves invisible from a single submission.

**2. Teacher lens fragments (`src/insights/lens_templates.py`):**

Subject-area-specific generative prompt fragments that orient the observation. They are *generative* by design — not enumerative ("look for X, Y, Z patterns"), but framework-grounded ("here is the analytical lens this discipline uses; observe through it"). Anti-enumeration is the load-bearing principle.

**3. No flag/no verdict:**

The observation is description, not classification. There is no flag-or-clear decision Track C can make incorrectly. It can be wrong about what it observes, but it cannot make the binary mistake.

**4. Asset/threshold/connection oriented readings:**

Three universal orientations are run alongside the observation:
- Asset reading — what is the student bringing
- Threshold reading — where is their thinking edge
- Connection reading — what are they linking to

These are anti-deficit by construction.

---

## How the four tracks are compared in the research panel

The `ResearchEngine` runs all classifiers on the same submissions and emits results into a side-by-side display. The data layout per student is:

```
{
  student_id: {
    track_a:    {flagged: bool, concerns: [...], bias_warnings: [...]},  # combined
    track_a_wb: {flagged: bool, concerns: [...], bias_warnings: [...]},  # wellbeing-only
    track_b:    {axis, signal, confidence, prescan_signals,
                 checkin_flag, checkin_reasoning},
    track_c:    {observation: str},
    word_count: int,
  },
  ...
}
```

Per-concern records (in `track_a.concerns` and `track_a_wb.concerns`) have:
```
{flagged_passage, surrounding_context, why_flagged, confidence}
```

The `why_flagged` may be prefixed with `⚠ POSSIBLE MODEL BIAS` or `⚠ LIKELY COURSE CONTENT` if the post-processing layer rewrote it.

### Persistence

Track B and C are persisted by the production pipeline in `coding_record` (under `wellbeing_axis`, `wellbeing_signal`, `prescan_signals`, `checkin_flag`, `checkin_reasoning`, `observation`). The research panel reads these directly from the DB.

The binary tracks (A1 and A2) are persisted by the research panel as it runs them, into the same `coding_record` JSON:

- `coding_record.track_a_research` — Track A1 (combined scope)
- `coding_record.track_a_research_wb` — Track A2 (wellbeing-only scope)

This means classifier results survive panel restarts and can be retrieved by anyone reading the SQLite store directly. No schema migration is needed; the research keys live alongside production fields.

### Operating modes

The research panel has two modes:

- **Full-comparison** (`ResearchEngine.run_comparison`) — fetches submissions from Canvas, runs all production stages (class reading, observations, etc.) in addition to all four research classifiers. Used when Canvas access is available.
- **Track A only** (`ResearchEngine.run_track_a_only`) — uses stored submission texts from a prior insights-pipeline run. Runs the QuickAnalyzer (non-LLM signal matrix) plus both binary classifiers. No Canvas fetch needed; works fully offline. Track B and C are loaded from the prior run's stored coding records.

The "Track A only" mode is the path used for offline research review and for filling in the binary classifiers on assignments where the production pipeline already ran. It does not call class context for the binary classifiers (proven to hurt classification stability).

## Disagreement categories — the most informative data cells

The research apparatus exposes disagreements as the primary research signal. Disagreement-counting is a richer framework now that there are four classifiers:

### Within-format disagreements (binary vs binary)

- **A1 flag + A2 clear** — almost certainly a power-moves flag (essentializing, colorblind, etc.). A2 wasn't asked to find these, so missing them is expected. Useful for separating the wellbeing-flag and power-moves-flag populations within A1.
- **A1 clear + A2 flag** — A2 caught a wellbeing signal A1 missed despite identical equity machinery. Likely an effect of prompt scope narrowing improving wellbeing recall — telling the model "look for wellbeing only" makes it more sensitive to the wellbeing signal it might otherwise diffuse across the broader scope.
- **Both flag** — robust signal, both binary scopes converge on the wellbeing concern.

### Cross-format disagreements (binary vs 4-axis)

- **A2 flag + B ENGAGED** — wellbeing-only binary flagged, 4-axis says engaged. Tests the hypothesis that binary classifiers over-flag when the signal is ambiguous and the 4-axis classifier's option to say ENGAGED-with-no-flag absorbs the ambiguity.
- **A2 clear + B CRISIS/BURNOUT** — 4-axis caught a wellbeing signal the wellbeing-only binary missed. Likely the 2-pass architecture (pre-scan + foregrounded classification) surfacing buried sentences single-pass binary classifiers drown in topic content.
- **B CHECK-IN + A2 clear** — 4-axis check-in flagged a softer signal the binary wasn't designed to detect. Demonstrates the value of the structured pass over the binary collapse.

### Cross-everything disagreements (vs Track C)

- **All structured classifiers clear + Track C surfaces a concern in prose** — the qualitative reading is catching something all classification formats miss. Often relational dynamics that don't reduce to per-student flags.
- **Some classifier flags + Track C clear** — the structured classifier may be over-flagging; the qualitative reading provides a different lens.

These disagreements are the most informative cells for a paper analyzing classifier behavior — they are precisely where the design differences manifest as different judgments. The within-format A1 vs A2 comparison is *new* in this version of the apparatus and is the cleanest way to isolate scope from format.

## Data exports

The research panel produces two CSV formats:

- **CSV (anon)** — student IDs replaced with `anon_001`, `anon_002`, etc. For research sharing / external publication.
- **CSV (named)** — real student names + submission text. For internal teaching review only; do not share externally.

Both formats include separate columns per binary classifier:

- `track_a_flagged`, `track_a_concern_count`, `track_a_max_confidence`, `track_a_flagged_passages`, `track_a_why_flagged`, `track_a_confidences`, `track_a_bias_warning` (combined scope)
- `track_a_wb_flagged`, `track_a_wb_concern_count`, `track_a_wb_max_confidence`, `track_a_wb_flagged_passages`, `track_a_wb_why_flagged`, `track_a_wb_confidences`, `track_a_wb_bias_warning` (wellbeing-only scope)
- `track_b_axis`, `track_b_signal`, `track_b_confidence`, `track_b_prescan_signals`, `track_b_checkin_flag`, `track_b_checkin_reasoning`
- `track_c_observation`

Multi-concern fields (passages, why_flagged, confidences) are joined with ` || ` to keep one row per student while preserving per-concern detail.

A separate Markdown export (`scripts/export_run.py`) produces a human-readable per-student report with the same data.

## Code references

- `src/research/concern_detector.py` — the binary classifier function `detect_concerns(scope=...)` for both A1 and A2
- `src/research/prompts.py` — `CONCERN_PROMPT` (combined), `WELLBEING_CONCERN_PROMPT` (wellbeing-only), `CONCERN_CRITIC_PROMPT`, `CONCERN_IMMANENT_CRITIQUE_ADDENDUM`
- `src/research/research_engine.py` — `ResearchEngine.run_comparison()` and `run_track_a_only()` orchestrators; runs both binary scopes per student
- `src/research/research_panel.py`, `src/research/research_window.py` — research GUI
- `src/insights/submission_coder.py` — `classify_wellbeing` (Track B Pass 1), `classify_checkin` (Track B Pass 2), `observe_student` (Track C)
- `src/insights/prompts.py` — production prompts: `WELLBEING_CLASSIFIER_PROMPT`, `WELLBEING_EVIDENCE_EXTRACTION_SYSTEM`, `TARGETED_CHECKIN_SYSTEM`, `OBSERVATION_PROMPT`
- `src/insights/lens_templates.py` — subject-area lens fragments
- `src/insights/process_keepalive.py` — `SleepPreventer` class shared between production and research; cross-platform `caffeinate -s` (macOS) / `powercfg` (Windows) / `systemd-inhibit` (Linux). Idempotent, so the research panel doesn't double-spawn caffeinate when the production pipeline already holds it.
- `scripts/run_alt_hypothesis_tests.py` — historical test harness (Tests A–O), including `BEST_CONCERN_PROMPT` and `LENGTH_CONCERN_PROMPT`. **Note:** these are *retrospective recreations* of earlier classifiers whose raw output was lost in `tmp/`; they are not the same as the production-grade equity-hardened wellbeing-only classifier in `src/research/prompts.py`.
- `scripts/launch_research.py` — entry point; supports `--offline` flag to bypass Canvas credential loading.
- `scripts/run_binary_for_run.py` — batch-runs both binary classifiers on every student in a stored Insights run, persists results to the DB. Skips students who already have both classifiers persisted (use `--force` to override).
- `scripts/export_run.py` — Markdown / CSV exporter for stored runs.

## Models used

- Local: Gemma 3 12B (lightweight tier) and Gemma 3 27B (medium tier), via Ollama or Apple MLX. The tier matters: Gemma 3 12B handles the binary classifiers' anti-bias post-processing reliably but produces more false positives in pre-bias output. 27B reduces both false-positive rate and post-processing intervention frequency.
- Cloud (optional): OpenAI-compatible endpoints for the deep tier; not used in the current research runs.

The first full dual-binary run completed on 2026-04-27 against the ETHN-1-03 Week 7 self-care assignment (n=25 students), using Gemma 3 12B via MLX. Results are persisted in `insights.db` under `coding_record.track_a_research` (combined) and `coding_record.track_a_research_wb` (wellbeing-only).
