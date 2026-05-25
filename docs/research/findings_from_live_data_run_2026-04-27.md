# Findings from First Live-Data Dual-Binary Run — 2026-04-27

This doc captures research-system findings surfaced during paper analysis of the first formal live-data run. It exists for the next autograder agent: things to look at, fix, or design-decide. Paper-side analysis lives in the output-format-bias paper repo, not here.

## ⚠ PRODUCTION PRIORITY — Track B fixes ship to production, not just research

The 4-axis wellbeing classifier and the targeted CHECK-IN pass referred to as "Track B" in the paper analysis are **production code**, not research apparatus. They are the live wellbeing-classification path teachers see in the production insights pipeline:

- `src/insights/submission_coder.py` — `classify_wellbeing()` (Pass 1, the 4-axis classifier) and `classify_checkin()` (Pass 2, targeted CHECK-IN)
- `src/insights/prompts.py` — `WELLBEING_CLASSIFIER_SYSTEM`, `WELLBEING_CLASSIFIER_PROMPT`, `TARGETED_CHECKIN_SYSTEM`, `TARGETED_CHECKIN_PROMPT`
- `src/insights/engine.py` — production callers

**Two production gaps surfaced in the live-data analysis (detail in §6 below):**

1. **Input gap:** B Pass 1 and Pass 2 do not receive the assignment prompt. They see only `student_name` and `submission_text`. This means the production wellbeing classifier classifies submissions without knowing what the assignment was about — preventing topic-adjacency reasoning. Track A2 (research apparatus) and Track C (production observation) both receive the assignment context (or at least the assignment name); B does not.

   **For production: pull the FULL assignment description, not just the name.** The `InsightsStore` schema currently has only `assignment_id` and `assignment_name` columns (`src/insights/insights_store.py:50-68`); add an `assignment_description` column and fetch the description from Canvas API during production runs (the engine already has Canvas access). Persist it; pass it into `classify_wellbeing` and `classify_checkin` alongside the existing inputs. The assignment name alone is a several-word label ("Week 7 Self-Care Reflection"); the full description is the instructional text students were responding to, which gives the model real topic-adjacency signal. **For testing/research:** the rerun in the paper repo will pass a controlled assignment-description string directly — no need to wait on the schema migration to validate the change.
2. **Equity-hardening gap:** B's prompt is missing five guards present in A2's `WELLBEING_CONCERN_PROMPT` (research). On a topic-adjacent assignment (Week 7 self-care, themes of burnout/rest/exhaustion), this gap produced a high false-positive rate on engaged-student work being misclassified as BURNOUT.

**Both fixes are production-impacting.** The paper's analysis is testing them via a research rerun, but if validated, they need to ship — they affect every wellbeing classification production runs against a topic-adjacent assignment (anything where students are asked to discuss rest, burnout, productivity, self-care, mental health, or related themes).

**Calibration intent to preserve:** the production design choice that "CRISIS supersedes ENGAGED" and "single sentence sufficient for CRISIS or BURNOUT classification" should be retained — those are correct production behavior for genuine crisis detection. The new guards apply to BURNOUT vs. ENGAGED disambiguation and CHECK-IN calibration, not to CRISIS detection. This is calibration-aware hardening, not blanket conservatism.

**See §6 for the discrete architecture questions** (acuity gradient, sleep-deprivation axis, hyperbole detection, direct-quote handling, temporal distance, longitudinal data wiring, reply-context register, CHECK-IN calibration drift, equity-protection symmetry). Each item is tagged as *production-impacting* or *research-apparatus-only*. Items 6.1, 6.2, 6.3, 6.4, 6.6, 6.8, 6.9, 6.10 hit production. Items 6.5 (direct-quote detection in A1) and 6.7 (longitudinal-data audit) are research-apparatus questions in scope.

**Recommended order for the next autograder session:**

1. Resolve the staged Student 17 schema-misuse fix (research-only, §1).
2. **Production: feed assignment_prompt to `classify_wellbeing` and `classify_checkin`** — this is the structural fix; it changes the function signatures + prompt templates and propagates through `engine.py` callers. Likely the highest-impact production change here.
3. **Production: port the five equity-hardening guards from A2's `WELLBEING_CONCERN_PROMPT` into `WELLBEING_CLASSIFIER_SYSTEM`**, adapted to B's voice and scoped to BURNOUT/ENGAGED disambiguation rather than CRISIS.
4. Strengthen `TARGETED_CHECKIN_SYSTEM`'s "ONLY when... genuinely balanced" instruction — calibration drift on live data (Students 4 and 22 in the run).
5. Address remaining production items from §6 in priority order.

The research rerun (paper-side, with the same n=25 ETHN-1-03 Week 7 data) will test whether the fixes from steps 2–4 above close the precision gap with Track C. If validated, ship them to production.

## Run context

- **Date:** 2026-04-27
- **Model:** Gemma 3 12B via MLX (Apple Silicon)
- **Assignment:** ETHN-1-03 Week 7 self-care (Audre Lorde framing), n=25
- **Mode:** `run_track_a_only` (binary classifiers run against stored prior-run texts; Tracks B and C loaded from prior production-pipeline run)
- **Anonymized export:** `~/Documents/GitHub/research/output-format-bias/data/dual_binary_run_2026-04-27_ETHN1_self_care/self_care_ethn1_anon.csv` (gitignored — student writing is FERPA-adjacent even when anonymized)

## 1. Schema-misuse bug — fix staged but uncommitted in working tree

**What:** A1 (combined-scope binary) flagged Student 17's positive reflections at confidence 1.0 with `why_flagged = "This is a positive reflection... No concerns."` Two such entries on a single submission. The model is misusing the JSON schema — putting non-concerns into the `concerns[]` array with denial text in the rationale.

**Why it surfaces:** The parsing layer in `detect_concerns()` trusts that anything in `parsed["concerns"]` *is* a concern. The post-processing rewrite layer's regexes don't include "no concerns / not a concern" so demotion never fires. The 0.7 threshold passes them at conf 1.0.

**Fix staged in working tree (uncommitted):** `src/research/concern_detector.py`
- Added `_NON_CONCERN_DENIALS` regex matching `\bno concerns?\b`, `not a concern`, `no concern (is|was) (found|present|raised)`, `not (a )?wellbeing concern`, etc.
- Added skip in the parsing loop in `detect_concerns()` before `ConcernRecord` creation, with `log.debug` for traceability

**To-do for the next autograder session:**
- Review the regex (false-positive risk: minimal — phrases like "no concerns" rarely embed in legitimate concern explanations, but worth a sanity check)
- Add a unit test against Student 17's exact `why_flagged` strings (preserved in the anonymized CSV)
- Consider whether this should also catch the case `confidence == 1.0 AND why_flagged contains positive language` more broadly — the regex is one specific pattern; the underlying issue is "model packaged a non-concern as a concern"
- Decide whether to reprocess the affected run or leave Student 17's two A1 flags as-is for the paper (the paper analysis is treating them as a *finding* about A1's failure mode, not just a count error)
- Commit when ready

## 2. Bias-rewrite vocabulary is narrow — misses soft tone-policing of structural critique

**Observation:** On this run, zero `_BIAS_MARKERS` regex hits across all 10 flagged concerns. But A1 still produced flags that read as soft tone-policing of structural analysis:

- **Student 14** (A1 flag, conf 0.7): the model flagged "corporations solely thrive on exploitation" as "a strong and potentially generalizing statement about corporations" — soft-tone-policing register, no overtly aggressive vocabulary, so the rewrite regex didn't trigger.
- **Student 16** (A1 flags, conf 0.8): the model flagged two passages about productivity culture as systemic oppression. Its `why_flagged` text *praises* the analysis ("sophisticated understanding," "demonstrates a strong understanding") while still flagging it as "potential for burnout" or insight to "encourage further exploration." Flagging-as-praise — even harder to catch with a vocabulary-keyed rewrite.

**Implication for the system:** `_BIAS_MARKERS` is keyed to a small list of overtly aggressive words (`aggressive, too emotional, hostile, irrational, hysterical`, etc.). These don't exhaust how a model can soft-flag structural critique. The rewrite layer's narrow definition of "bias language" is a methodological limitation worth naming — and possibly addressable via:

- Expanding the regex with softer markers ("generalizing," "potentially problematic generalization," "strong statement," "may want to consider nuance")
- Or — more architecturally — moving from regex-based detection to a small dedicated LLM critic pass (`CONCERN_CRITIC_PROMPT` in `prompts.py` exists for this; not yet wired)

Decision deferred to a dedicated autograder session.

## 3. Threshold filter eats most bias-warnings before they reach teachers — design check needed

**Observation:** Reading `concern_detector.py:255-256`, the 0.7 confidence threshold filter runs *after* `_check_bias_in_output`. Post-processing demotes confidence by 0.3 (tone-policing) or 0.4 (course-content). Math:

- Tone-policing rewrite at incoming conf 0.7 → 0.4 → filtered out
- Course-content rewrite at conf 1.0 → 0.6 → filtered out (max possible after 0.4 demotion)
- Only tone-policing rewrite at conf ≥ 1.0 → 0.7 survives the filter

**Implication:** The architecture documentation describes bias-warning prefixes (`⚠ POSSIBLE MODEL BIAS`, `⚠ LIKELY COURSE CONTENT`) as visible to teachers — but in practice almost all rewritten flags get silently dropped. The post-processing functions primarily as a *demotion-and-drop* mechanism, not a *visible-warning* mechanism.

**Open design question:** Is this the intended design (quietly drop bad flags) or a missed opportunity (show the warning so teachers learn what the equity layer is catching)? Worth a deliberate decision. Two paths:

1. Keep as-is, update the architecture doc to describe the layer accurately as drop-not-warn.
2. Change behavior: rewritten flags survive the threshold filter when they carry a `⚠` prefix (so teachers always see them) — even though confidence is demoted.

Path 2 makes the equity work visible-by-design. Path 1 is the simpler ship.

## 4. Track B calibration on live data — not yet tuned

**Observation:** B's distribution on this run was 14 ENGAGED / 9 BURNOUT / 2 CRISIS / 0 NONE — 44% wellbeing-signal rate. The 4-axis classifier was previously tuned on synthetic papers, not live student data. This run is the first live-data exposure.

The BURNOUT-heavy distribution may reflect:

- (a) Tuning-on-synthetic carrying over too sensitively to live writing
- (b) Substantive student state (week 7 of an Ethnic Studies course; prior week was high-burnout)
- (c) The format itself being more sensitive (legitimate strength)

This question can't be fully resolved from a single run. Per-case qualitative reading (paper-side analysis, in progress) will give a per-student plausibility judgment via the `prescan_signals` field. A second run on a less-ambiguous assignment (other ETHN-1 weeks; June can run this) would triangulate.

**For the next autograder agent:** B's prompts (`WELLBEING_CLASSIFIER_PROMPT`, `TARGETED_CHECKIN_SYSTEM`) may want recalibration after the paper analysis surfaces specific failure modes. Don't tune speculatively — wait for the paper's per-case analysis to land.

## 5. Reply-context attribution — classifiers conflate primary disclosure with relational-reply disclosure

**Observation surfaced during paper-side review (June, 2026-04-27):** Track B's BURNOUT flag on Student 5 keyed on a sentence written in a *reply addressed to Student 13* (a classmate disclosing the recent COVID death of their father), not in Student 5's primary post. The sentence — *"I sometimes struggle with my mental health and have found community with my coworkers who have been really supportive towards me"* — was offered as relational reciprocity to support a grieving peer.

**The architectural issue:** The pipeline pulls a student's submission as `body = _strip_html(sub.get("body") or sub.get("text") or "")` (per `src/research/research_engine.py`). For Canvas discussion threads, this concatenates `[Post] ... [Reply] ... [Reply] ...` into a single document handed to the classifiers. Classifiers have no signal indicating which segment is the main post vs. a reply context.

**Why it matters:** The illocutionary force of self-disclosure differs by context. *"I struggle with mental health"* in a primary self-disclosure post vs. in a reply offering support to a grieving peer is functionally different writing — in the reply context, self-disclosure is relational and conversationally appropriate ("I'm telling you this because you told me something") rather than a teacher-targeted declaration. The architecture doc's calibration rules (especially CHECK-IN's "Set check_in to true ONLY when... genuinely balanced") may need different thresholds for reply-context disclosures.

**Possible fixes (decision needed):**

1. **Run classifiers separately on Post vs. Reply segments** — different output rows per context, with reply-context having calibrated-higher threshold or a separate "reply-disclosure" axis.
2. **Inject context markers into the prompt** — *"Sentences in reply contexts (offering support to a peer) should be calibrated to higher threshold than main-post disclosures."*
3. **Add exclusion to existing prompts** — explicitly: "If self-disclosure is in a reply offering relational support to a peer who also disclosed, treat with higher threshold."

**Paper-side note:** This is also a paper-relevant methodological finding. *Discussion-board AI classifiers are blind to register-by-position* (main vs reply), and reply contexts are a discoverable false-positive category for live data. The architecture doc doesn't currently address this. The paper will name it as a Limitations / Methodological-extension point.

**To-do for next autograder session:** decide between fix paths 1/2/3 above. Path 1 is the most architecturally clean but requires Canvas-side data restructuring (the body-pull layer would need updating). Path 2 is the lightest change and probably worth piloting first.

## 6. Architecture questions surfaced from June's coding-review pass

These came out of the paper-side qualitative review where June judged each classifier flag against her teacher knowledge of the students + full submission texts. Each is a discrete architecture question or potential improvement worth a dedicated autograder session.

### 6.1 — A2 vs B prompt difference on "not a wellbeing concern *per se*"

Student 7: A1 phrased its flag as *"not a wellbeing concern *per se*, the teacher might consider prompting a discussion about..."* — i.e., the binary classifier produced a flag-shaped output that *also* internally hedged itself as "not a wellbeing concern." B's structured-output for the same submission classified BURNOUT with no equivalent hedge available. **Question:** does A2's prompt allow this kind of "this is a teaching moment, not a wellbeing concern" framing in a way B's commits-to-an-axis structure doesn't? If so, that's an architectural asymmetry worth naming and possibly addressing in B (an axis or annotation for "not a wellbeing concern but worth surfacing").

### 6.2 — Acuity gradient missing in B

Student 5: a general mention of "I sometimes struggle with my mental health" (in a peer reply offering relational support to a grieving classmate) was classified as BURNOUT. June's diagnosis: *"we need a new category for something like — general mention of what could flag as a concern (in this case, mental health issues), but in a generalized sense rather than something that is culminating as a problem now... could be a question of acuity for our system."*

**Question:** should B distinguish between *acute-now* vs. *general-mention* as a separate axis or gradient? Currently BURNOUT/CRISIS lump these together; the result is teachers getting flagged on every general mental-health mention.

### 6.3 — Sleep deprivation as its own axis

Student 12: B's BURNOUT classification correctly fired on sleep-deprivation language — sleep-dep is in B's named criteria. But June's read was that the disclosure was course-aligned reflection (the assignment is about productivity-guilt-around-rest), not a teacher-actionable wellbeing concern.

**Question:** should sleep-deprivation be a separate axis with its own threshold, separate from general BURNOUT? Sleep is a specific actionable category that doesn't always rise to "the teacher needs to intervene," but currently triggers full BURNOUT classification.

### 6.4 — Hyperbolic / sentiment-based disambiguation

Student 3: A2 flagged *"literally kill ourselves in the pursuit of productivity"* as wellbeing concern — the rhetoric is plainly metaphorical in context. June's question: *"Maybe some sentiment analysis would help here?"*

**Question:** can a sentiment-analysis or hyperbole-detection layer disambiguate metaphorical-rhetorical disclosures from literal disclosures? The current prompts rely on the LLM's own judgment, which doesn't reliably catch hyperbole in topic-adjacent contexts.

### 6.5 — Direct-quote detection

Student 2: A1 flagged *"Black people are dying from sleep deprivation"* as essentializing language. June confirmed: *"This is a direct quote"* (from the readings). The classifier didn't register the passage as quoted material.

**Question:** should classifiers detect quoted material (typographic markers, common-attribution patterns) and either skip it or apply different criteria? Flagging direct quotation as if student-authored is a discoverable failure mode.

### 6.6 — Temporal distance for loss

Student 13: A2 flagged "father's death during COVID" as recent loss. June: *"The death isn't described as recent — the student specifically says it was a few years ago... Stream 1 issue — the 'few years ago' is a big differentiator."* Even C's read was slightly stronger than June would code — it didn't differentiate temporal distance.

**Question:** should the wellbeing prompts include explicit guidance on temporal distance for loss? Currently the architecture lists "recent or active loss" but the LLM isn't reliably parsing "recent" against the student's own temporal markers.

### 6.7 — Longitudinal data access

C's check-in suggestions for Students 12, 15, 19, 20 all key on word-count drops, late-submission timing, prior-flag history — context A2 and B don't appear to receive in their prompts. June: *"I didn't realize we had that in the system."*

**Question (clarifying):** what data does each track actually receive? If C uniquely receives longitudinal context, that's a structural capability gap — not a prompt-design failure but a feature B doesn't have. Worth confirming the wiring and either (a) extending it to A2/B if appropriate, or (b) explicitly documenting it as C's architectural advantage. Affects how the paper describes the C-vs-structured comparison.

### 6.8 — Reply-context register

Students 5, 22: flagged passages were in *replies* (offering support to a peer) rather than the student's primary post. The classifier sees `submission_text` as concatenated `[Post]` + `[Reply]` + `[Reply]`. Reply-context disclosure has different illocutionary force than primary self-disclosure (relational reciprocity vs. teacher-targeted declaration).

**Note:** June initially read this as a thread-attribution bug, then corrected: replies are correctly attributed to the authoring student (their replies across multiple threads). Not a data bug, but a register-blind classification issue.

**Question:** should classifiers either (a) run separately on Post vs Reply segments, (b) include explicit register markers in the prompt, or (c) apply higher thresholds to reply-context disclosures?

### 6.9 — CHECK-IN calibration drift

Student 4: B's CHECK-IN flagged a closing exclamation *"I really enjoyed the topic and readings this week!"* The checkin_reasoning text *itself* named the unbalanced read ("could be interpreted as a simple expression of enjoyment") and flagged anyway, violating the architecture doc's *"ONLY when... genuinely balanced"* instruction.

**Question:** is this a calibration drift on live data (synthetic-corpus validation didn't expose it), a prompt strength issue (the instruction needs sharpening), or both? Likely both. Worth tightening the prompt's competing-interpretation language.

### 6.10 — Equity-protection legibility for exhaustion/burnout

Student 23 (June's observation): *"The underlying pattern may be similar to our finding about neurodivergent v. AAVE protections — exhaustion and burnout are going to have the same weight in terms of equity and protection — it's not as widely legible."*

**Question:** are exhaustion/burnout-related equity protections drawn as legibly in the prompts as protections for AAVE/neurodivergence/code-switching/etc.? Worth a prompt-level audit checking symmetry of equity-protection coverage across categories.

---

## 7. Production pipeline equity machinery — not investigated this round

The above all concerns the *research apparatus* (binary classifiers A1/A2 in `src/research/`). Tracks B and C are in production code (`src/insights/submission_coder.py`) with their own equity-hardening (identity-navigation-fatigue exclusions, family-experience-as-course-material exclusions, calibration-to-false-flag-low). Whether B's hardening fired or didn't on this run is a separate question — Track B doesn't surface a `bias_warning` column, so the analogous diagnostic isn't available without reading the prompts and instrumenting.

Worth a dedicated session if Track B exhibits unexpected calibration in the paper analysis.

---

**Pointer to paper-side analysis:** ongoing in `~/Documents/GitHub/research/output-format-bias/data/dual_binary_run_2026-04-27_ETHN1_self_care/analysis.md`. That doc is paper material, not system-tuning material — but if the paper's qualitative reads turn up additional system findings, they'll get cross-referenced back here.

---

## 8. Prescan-signal-prefix mechanism — root cause for the topic-adjacency FP pattern (added 2026-04-27 evening, after Week 2 cross-validation run)

This is the structural mechanism behind several of the §6 findings. It was identified during paper-side analysis of the Week 2 ETHN-1 Racial Formation discussion-forum run (cross-assignment validation of Week 7's findings) and confirmed via two architecture audits.

### 8.1 — The mechanism (what it does)

Track B's `classify_wellbeing` is a two-pass architecture:

1. **Prescan pass** (`src/insights/submission_coder.py:194-224`, `_prescan_for_personal_signals`) — an LLM pass that scans the submission text in isolated chunks for "own-personal-circumstances" mentions, with no access to assignment topic or surrounding analytical register. The prescan system prompt (`src/insights/prompts.py:1671-1685`, `WELLBEING_PRESCAN_SYSTEM`) names a specific keyword list: *food insecurity, housing instability, sleep deprivation from work or caregiving, family crisis, immigration enforcement threat, domestic violence, recent loss, health emergency*.

2. **Main classifier pass** receives prescan-found sentences foregrounded in the prompt with priming language (`src/insights/submission_coder.py:1044-1055`):
   > *"NOTE: The following sentence(s) from this student's submission appear to describe their own personal circumstances: [quoted sentences]. Even a single such sentence is sufficient for CRISIS or BURNOUT classification if it reflects genuine personal circumstances."*

The main classifier prompt (`prompts.py:1697-1827`, `WELLBEING_CLASSIFIER_SYSTEM`) includes the equity-hardening exclusions surfaced as production gap §6 (topic-adjacency threshold, identity-navigation-fatigue exclusion, personal-experience-as-course-material exclusion). **The exclusions never get to override the prescan priming**, because the priming arrives in the prompt context labeled as fact ("appear to describe their own personal circumstances") with the single-sentence-sufficient instruction attached. By the time the classifier reads the analytical context, the foregrounded sentence is already gated as material disclosure.

### 8.2 — Why this explains the Week 7 hardening rerun result

The Week 7 prompt-iteration rerun (paper analysis Phase 3) added five hardening guards to the main classifier prompt, explicitly addressing each documented FP failure mode. **Result: 22 of 25 classifications unchanged; 5 of 7 headline-cell BURNOUT FPs persisted; 1 regression to CRISIS.** The architecture audit identifies why: the hardening was added to the main classifier prompt, but the prescan happens upstream and primes the classifier with the offending sentences foregrounded. The topic-adjacency guards never get to override the priming.

This is structural, not a tuning artifact. Prompt iteration on `WELLBEING_CLASSIFIER_SYSTEM` cannot scalably close the gap as long as the prescan-signal-prefix architecture gates the main classifier's full-text read.

### 8.3 — Cross-validation from the Week 2 Racial Formation run

Week 2 (n=31, ETHN-1 racial formation discussion forum, same date / model / prompts / format as Week 7) produced **0 BURNOUT classifications, 1 CRISIS classification, 1 CHECK-IN-among-ENGAGED**. The CRISIS case (Student 17) involves family-deportation-risk language. The instructor's verdict on Student 17: *"I wouldn't call it a 'crisis'. But this is SCARED."*

Two findings from this:

- **The Week 7 BURNOUT FP rate is topic-adjacency-driven, not a uniform B miscalibration.** When the topic doesn't trigger the prescan's wellbeing keyword list, B's flag rate collapses. Paper-side analysis: `~/Documents/GitHub/research/output-format-bias/data/dual_binary_run_2026-04-27_ETHN1_Week2_RacialForm/analysis.md`.
- **A second FP failure mode: structural-slot-mismatch on the 4-axis output.** Student 17's "scared, not crisis" register doesn't fit BURNOUT (no depletion), CRISIS (no active emergency), or ENGAGED-without-flag (the fear is real). The closest fit is CHECK-IN — but B's CHECK-IN axis only runs on ENGAGED classifications, so by classifying CRISIS, B foreclosed the CHECK-IN pathway. **Architectural design question:** should CHECK-IN be made independent of the four-axis classification (run on every submission), so it can surface fear-without-emergency cases without competing with the disclosure-axis decision? See §8.6 below for the broader future-direction this suggests.

### 8.4 — Family-keyword detail (for posterity, not paper-load-bearing)

The B↔C parallel surfacing of "family" on Student 17 was investigated as a possible prompt-collision. Findings:

- **Track C is architecturally independent of the prescan.** No `signal_prefix` parameter exists in `OBSERVATION_PROMPT` (`prompts.py:1463-1540`). C reads raw submission text only; B receives the prescan-foregrounded prefix.
- **"family crisis" is explicitly listed in B's prescan keyword set** (`prompts.py:1675`).
- **C's prompt frames family as intellectual contribution** (relational epistemology, `prompts.py:1499-1506`), not as a disclosure trigger. C surfaced family-mention via register-shift recognition (emotional stakes, urgency, shorter-than-typical analytical work) — independent of B's mechanism.

**Conclusion:** the parallel is independent confluence, not prompt-driven collision. Both architectures noticed something real through different mechanisms. This actually validates the disclosure-is-real reading; what diverges is the *characterization* (B → CRISIS via keyword-priming, C → "real and immediate threat... heightened emotional stakes" via register-shift). For paper purposes: the convergent-flag claim doesn't need the family-keyword nuance to land; the architecturally-independent-confluence is too detailed for the empirical paper but is documented here for autograder context.

### 8.5 — Three fix options (Stream 1 design decisions)

From the architecture audit. Listed in increasing implementation cost.

1. **Prescan-level course-material disambiguation** (lightest). Add to `WELLBEING_PRESCAN_SYSTEM` (around `prompts.py:1680`): worked examples contrasting analytical vs. personal references for keywords with topic-adjacency risk (immigration, food, housing, family). Example contrast:
   - NOT flagged: *"The racial project operates through immigration enforcement to maintain white supremacy"* (analytical, 3rd person, structural)
   - Flagged: *"My family is afraid to go outside since ICE came"* (personal, 1st person, present-tense)
   - Architectural pattern: instruct prescan to exclude sentences where the student is analyzing a concept (vs. describing their own state).

2. **Weighted signal_prefix** (medium). Replace "Even a single such sentence is sufficient" with conditional language requiring the classifier to verify modal-qualifier register (e.g., "may", "could") and surrounding analytical context before applying the rule. Suggested replacement at `submission_coder.py:1051`:
   > *"NOTE: The prescan identified the following sentence(s) as potentially personal: [quoted]. Verify whether the student is disclosing their own circumstances or analyzing course material on this topic. Single-sentence-sufficient applies ONLY to unambiguous material disclosures (no modal qualifiers like 'may,' 'could'). Assess with full analytical context."*

3. **Two-pass keyword-context check** (strongest, highest implementation cost). A non-LLM pre-filter that downweights prescan findings when surrounded by analytical keywords from the assignment's reading list. Pass 1: keyword-context check. Pass 2: weighted signal_prefix to main classifier. Requires assignment-description input (production gap from §6 Item 1 — already on the autograder roadmap).

Validation strategy: rerun the same Week 7 + Week 2 datasets after each fix. Closing the C-vs-B precision gap on the Week 7 self-care headline cell while preserving B's strength on Week 7 T&Q Student 13 (the buried minimal disclosure C missed) is the success criterion. Recommended order: Option 1 first (cheapest, addresses the topic-adjacency FP), then Option 2 if Option 1 alone doesn't close the gap.

### 8.6 — Future direction: C↔B inconsistency-driven axis-learning loop

Stream 1 future work (NOT for the May 20 paper). June's articulation 2026-04-27:

> "I would love to design a learning loop that found inconsistencies between C and B and built additional axes. But that would be an extremely complicated design."

The premise: B's axis-iteration is reactive by design. Each new axis (acuity gradient §6.2, sleep-deprivation as separate axis §6.3, hyperbole detection §6.4, etc.) emerges from post-hoc identification of patterns the existing axes missed. C carries no axis-design burden because it doesn't compress.

A learning loop would automate the pattern-noticing step: when C's qualitative observation surfaces a register or concern that B's structured output misses or miscategorizes, the loop logs the mismatch as a candidate-new-axis. Over time, B's axis set evolves toward closer fit with C's open-ended register space — without manual axis-design.

Design challenges: (a) defining "inconsistency" without false positives (B and C will always describe differently — when does a structural classification miss vs. just describe-differently?); (b) preventing axis-explosion (need merging/abstraction logic); (c) human-in-the-loop validation before adding axes to production. Complicated but tractable. Worth a dedicated design session; not a May 20 paper deliverable.

The Discussion section of the May 20 paper will name this as a future direction emerging from the empirical findings — particularly from the structural observation that B's axis-iteration is necessarily reactive while C's open-endedness is not.

### 8.7 — What this means for production (Stream 1 scope-decision)

The prescan-signal-prefix architecture is **defensible-by-design as a tradeoff**: it was added to address the opposite failure mode (Week 7 T&Q Student 13's 5-word food-insecurity disclosure, which C's holistic read averaged over). "Single sentence sufficient" is *correct* for unambiguous cases ("I haven't eaten today" is sufficient regardless of engagement frame). The cost is keyword-priming on course-relevant topics where the same word can be analytical or disclosural.

**Production recommendation:** ship Option 1 (prescan worked-example update) once the assignment-description input gap from §6 Item 1 lands. Don't ship Option 3 (two-pass keyword-context check) speculatively; validate Option 1 first.

**Paper-side note:** the May 20 paper documents the mechanism as architectural finding and uses it to support the multi-track-architecture argument. The fix itself is Round-2-paper material (the iterative-calibration follow-on study, parked per `PUBLICATION_PIPELINE.md`). Don't conflate the empirical-mechanism finding (paper-now) with the validate-the-fix study (Round 2).

---

## 9. AI-paste artifacts — academic integrity flag (routed from paper-side analysis 2026-04-28)

**Source:** C-scrutiny session (2026-04-28) morning review, Case 3.

**What:** Three Week 7 self-care submissions (student IDs 10, 17, 21 in the anonymized dataset at `~/Documents/GitHub/research/output-format-bias/data/dual_binary_run_2026-04-27_ETHN1_self_care/`) contain HTML attribute strings visible in the submission text — copy-paste artifacts from a chat interface (e.g., ChatGPT or similar). The artifacts are legible as web-interface paste debris.

**Why it matters for the system:** The current pipeline has no AI-detection pass. These three submissions surface a need for at least a lightweight detection signal in the production pipeline — not necessarily an accusation layer, but a flag for teacher attention before June reads the submission.

**Possible approaches:**
1. Passive flag: if raw submission text contains HTML-attribute debris patterns (e.g., `data-`, `class=`, `id=` strings, or `<span`/`<div` remnants after HTML stripping), add a `possible_ai_paste_artifact` annotation to the submission record.
2. Dedicated AI-detection pass (heavier): a small LLM or regex pass checking for stylistic markers. Out of scope for the May 20 paper cycle; design-decide after submission.

**June's routing decision:** route to autograder agent for AI-detection feature design. Not paper-relevant.

**Recommended action:** log as a feature backlog item. Low urgency; does not affect the current production pipeline's correctness. Address after the May 20 paper submission.

---

## 10. C-observation truncations — data-quality bug (routed from paper-side analysis 2026-04-28)

**Source:** C-scrutiny session (2026-04-28) Pass 2 cross-tabulation, Case 5.

**What:** Two Track C observations from the Week 2 Racial Formation run (student IDs 8 and 11 in `~/Documents/GitHub/research/output-format-bias/data/dual_binary_run_2026-04-27_ETHN1_Week2_RacialForm/`) end mid-sentence. The truncation is most likely max-token output overflow — the generative observation ran up against the model's output limit before completing.

**Why it matters:** Truncated observations are qualitatively incomplete — a teacher reading a mid-sentence C output gets an unreliable register read. For the paper, these two cases were excluded from the C-accuracy claim (not counted as C errors, but flagged as data-quality issues). For production, systematic truncation would undermine C's usefulness.

**Diagnosis path:**
- Check `src/insights/submission_coder.py` and `src/insights/prompts.py` for the max_tokens / max_new_tokens parameter on the `OBSERVATION_PROMPT` path.
- Check whether IDs 8 and 11 are unusually long submissions (high word count → longer observation → hits limit).
- Check if truncation is a consistent risk for long submissions or a one-off.

**June's routing decision:** data-quality bug; route to autograder agent. Not paper-relevant.

**Recommended action:** verify max_tokens setting for the observation generation path; if below ~800 tokens, increase. Add a truncation-detection check (observation ends without sentence terminator) that logs a warning and optionally re-runs with higher limit.
