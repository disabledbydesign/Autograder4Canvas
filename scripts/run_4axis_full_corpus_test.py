#!/usr/bin/env python3
"""Run the 4-axis wellbeing classifier on the full combined corpus.

Written 2026-05-11 for the output-format-bias paper (May 20 hard deadline).
Amended 2026-05-11 to support BOTH single-pass (Test N inline) and two-pass
(production classify_wellbeing) variants in a single invocation.

Context. The paper compares four architectures on the same corpus:
  - Minimal binary (Tests B/C/F)
  - Calibrated binary (Test M / Test R)
  - 4-axis classification (Test N family)
  - Generative observation (Test G / Variant A)

All existing Test N runs only cover 7-8 ES students + the 14 WB synthetic
cases. For the paper's comparison to be rigorous on the same scope, the
4-axis classifier needs evaluation on the FULL 32-student ethnic-studies
corpus + the 14 wellbeing-signal cases = 46 students.

SINGLE-PASS vs. TWO-PASS — both are findings
--------------------------------------------
Two paths in the codebase produce CRISIS/BURNOUT/ENGAGED/NONE labels:

  (1) Single-pass — test_n_four_axis_submissions in run_alt_hypothesis_tests.py.
      One LLM call. Uses inline FOUR_AXIS_SUBMISSION_SYSTEM (line 2315) and
      FOUR_AXIS_SUBMISSION_PROMPT (line 2377). Direct invocation via the
      module's `send` wrapper, which calls insights.llm_backend.send_text.
      This extends the paper's existing Row 3 evidence (Test N) to the full
      46-student corpus.

  (2) Two-pass — insights.submission_coder.classify_wellbeing (line 1009).
      Pass 0 LLM pre-scan finds personal-circumstance sentences across the
      full submission; Pass 1 classifier sees those sentences foregrounded
      via a signal_prefix. Uses WELLBEING_CLASSIFIER_SYSTEM /
      WELLBEING_CLASSIFIER_PROMPT from insights.prompts. This is what
      engine.py calls in the live pipeline.

The DIFFERENCE between (1) and (2) on the same corpus is itself a paper
finding: it isolates the contribution of the prescan-signal-prefix
mechanism, holding the corpus and 4-axis schema constant.

This script does NOT modify run_alt_hypothesis_tests.py — it imports the
single-pass prompts verbatim so the comparison is grounded in identical
prompt text.

Usage
-----
    cd /Users/june/Documents/GitHub/Autograder4Canvas

    # Both variants (default), full 46-student corpus, 5 runs each:
    python scripts/run_4axis_full_corpus_test.py

    # Single-pass only:
    python scripts/run_4axis_full_corpus_test.py --variant single-pass

    # Two-pass only:
    python scripts/run_4axis_full_corpus_test.py --variant two-pass

    # Smoke test (2 students total per variant, 1 run):
    python scripts/run_4axis_full_corpus_test.py --smoke

Estimated runtime: ~5 hours per variant on Gemma 12B MLX for the full run.
No time cutoffs are imposed.

Outputs (under --variant both, both files are written)
------------------------------------------------------
    /Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs/
      test_n_4axis_SINGLE_PASS_FULL_CORPUS_gemma12b_<YYYY-MM-DD_HHMM>.json
      test_n_4axis_TWO_PASS_FULL_CORPUS_gemma12b_<YYYY-MM-DD_HHMM>.json
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import sys
import time
import subprocess
from dataclasses import replace
from datetime import datetime
from pathlib import Path

# Path setup — match run_alt_hypothesis_tests.py conventions.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# Backend + production two-pass entry point.
from insights.llm_backend import BackendConfig, send_text, unload_mlx_model  # noqa: E402
from insights.submission_coder import classify_wellbeing  # noqa: E402
from insights.prompts import (  # noqa: E402
    WELLBEING_CLASSIFIER_SYSTEM,
    WELLBEING_CLASSIFIER_PROMPT,
)

# Single-pass entry point — import the Test N inline prompts verbatim from
# run_alt_hypothesis_tests.py so the comparison is grounded in identical text.
# Source: run_alt_hypothesis_tests.py
#   FOUR_AXIS_SUBMISSION_SYSTEM defined at line 2315
#   FOUR_AXIS_SUBMISSION_PROMPT defined at line 2377
# Also reuse WELLBEING_SIGNAL_CASES rather than duplicating 300+ lines.
from run_alt_hypothesis_tests import (  # noqa: E402
    FOUR_AXIS_SUBMISSION_SYSTEM,
    FOUR_AXIS_SUBMISSION_PROMPT,
    WELLBEING_SIGNAL_CASES,
)

# Paths
CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
OUTPUT_DIR = Path(
    "/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs"
)

# Model config — Gemma 12B MLX, temperature 0.1 (matches Tests B/C/F/M/N/R).
MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 300,
        "temperature": 0.1,
    },
}

# Assignment prompt placeholder. The synthetic corpus is built around a single
# Week-6 intersectionality discussion, consistent with Test R conventions.
ASSIGNMENT_PROMPT_TEXT = "Week 6 Discussion: Intersectionality in Practice"

# Single-pass token limit — mirrors Test N's invocation at
# run_alt_hypothesis_tests.py line 2436 / 2478 (max_tokens=150).
SINGLE_PASS_MAX_TOKENS = 150

# Reasoning-pass token limit — gives the model space to reason before committing
# to a confidence value, addressing the flat-0.95 calibration artifact observed
# in Test N / full-corpus single-pass runs.
REASONING_PASS_MAX_TOKENS = 400

# Same 4-axis categories and equity guardrails as FOUR_AXIS_SUBMISSION_SYSTEM,
# but output includes a reasoning field so the model works through the case
# before outputting confidence. Designed to test whether constrained output
# (signal only, 150 tokens) is the cause of flat 0.95 confidence.
FOUR_AXIS_REASONING_SYSTEM = (
    "You are assessing a student's submission for their teacher.\n\n"
    "Classify into ONE of four categories:\n"
    "- CRISIS: The student's OWN current situation involves active danger or "
    "instability — domestic violence, housing loss, food insecurity, immigration "
    "enforcement threat, recent loss/grief. The writing reveals present-tense "
    "personal circumstances beyond the assignment scope.\n"
    "- BURNOUT: The student's OWN capacity is depleted — exhaustion, overwork, "
    "caregiving burden, sleep deprivation. They're functioning but running on "
    "empty. The key signal is that the student's OWN MATERIAL CONDITIONS "
    "(their work schedule, their sleep loss, their caregiving duties) are "
    "breaking through and limiting their capacity. A student describing a "
    "family member's exhaustion or a parent's overwork is NOT evidence of "
    "BURNOUT — the depletion must be the student's own. "
    "Emotional intensity or personal vulnerability in the writing is NOT "
    "burnout — a student who writes passionately about painful experiences "
    "and reflects on the process ('this is what I needed to write') is deeply "
    "engaged, not depleted.\n"
    "- ENGAGED: The student is doing the assignment. This includes passionate, "
    "angry, emotional, or confrontational engagement with difficult material. "
    "Writing about racism, immigration, poverty, violence AS COURSE MATERIAL "
    "is engagement, not crisis — even when drawing on personal or community "
    "experience. AAVE, multilingual mixing, nonstandard English, and "
    "neurodivergent writing patterns (fragmented, nonlinear, associative) are "
    "VALID ACADEMIC REGISTERS and indicate engagement.\n"
    "- NONE: Insufficient text or off-topic.\n\n"
    "IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability "
    "(ADHD, dyslexia, autism), neurodivergent identity, race, religion, "
    "immigration status, sexuality, or language background is intellectual or "
    "personal disclosure — not a wellbeing signal by itself. Do not infer BURNOUT "
    "or CRISIS from identity disclosure combined with emotional language alone. "
    "Wellbeing signals require evidence beyond the identity disclosure itself: "
    "exhaustion that cuts off thought, lost sleep named directly, food or housing "
    "instability, fear for safety, caregiving burden limiting capacity.\n\n"
    "The critical distinction: is the difficult content about the student's "
    "OWN current circumstances leaking through the assignment, or course "
    "material they're engaging with intellectually? The former is CRISIS/BURNOUT; "
    "the latter is ENGAGED.\n\n"
    "CRISIS supersedes ENGAGED: If a student discloses domestic violence, "
    "housing loss, food insecurity, or immigration enforcement threat — even "
    "while maintaining strong analytical engagement — classify as CRISIS.\n\n"
    "MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Resilience framing does not "
    "reduce the severity of underlying material conditions. Classify based on "
    "material circumstances, not emotional register.\n\n"
    "PERSONAL EXPERIENCE AS COURSE MATERIAL: Students drawing on family or "
    "community experience analytically — a grandmother's migration, a father's "
    "labor — are doing the assignment. Classify as ENGAGED unless the student's "
    "OWN present-tense material conditions are also breaking through.\n\n"
    "Respond with JSON only: {\"reasoning\": \"2-3 sentences working through "
    "the evidence — explicitly note if the signal is implicit, third-party, "
    "or could be course material vs. personal disclosure\", "
    "\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description of key signal or lack thereof\", "
    "\"confidence\": 0.0-1.0 — use 0.9+ only when the evidence is direct "
    "and unambiguous; 0.65-0.85 when signal is implicit or could be read "
    "either way; 0.5-0.65 when two categories are plausibly correct}"
)

# Binary reasoning system: WELLBEING_CLASSIFIER_SYSTEM verbatim, only the output
# schema changed to put reasoning before axis and bump max_tokens to 400.
# Minimal change for paper comparability — isolates the effect of reasoning
# from guardrail language differences between the binary and 4-axis prompts.
#
# NAMING CLARITY (added 2026-05-12): `_BINARY_OLD_SCHEMA` is the schema-tail
# string used by the PRODUCTION binary classifier — but its content is the
# 4-axis schema (CRISIS|BURNOUT|ENGAGED|NONE). The production "binary"
# emits 4-axis labels at the model layer and DOWNSTREAM CODE collapses
# CRISIS+BURNOUT → CONCERN and ENGAGED+NONE → CLEAR. So at the model layer
# the production binary is a 4-axis-with-collapse, not a true binary.
#
# This constant is used as a SEARCH NEEDLE in .replace() calls — it locates
# the schema tail inside WELLBEING_CLASSIFIER_SYSTEM so the new tail can be
# substituted. The unified-* variants below use this needle to install their
# own format-specific tails. Crucially, `unified-binary-*` installs a TRUE
# binary tail (`"verdict": "CONCERN"|"CLEAR"`) — emitted at the model
# layer, NOT collapsed downstream. Do not conflate the legacy production
# "binary" (4-axis-with-collapse) with the unified-binary variants here.
_BINARY_OLD_SCHEMA = (
    'Respond with JSON only: {"axis": "CRISIS"|"BURNOUT"|"ENGAGED"|"NONE", '
    '"signal": "brief description", "confidence": 0.0-1.0}'
)
assert _BINARY_OLD_SCHEMA in WELLBEING_CLASSIFIER_SYSTEM, (
    "WELLBEING_CLASSIFIER_SYSTEM schema changed — update BINARY_REASONING_SYSTEM"
)
BINARY_REASONING_SYSTEM = WELLBEING_CLASSIFIER_SYSTEM.replace(
    _BINARY_OLD_SCHEMA,
    'Respond with JSON only: {"reasoning": "2-3 sentences working through '
    'the evidence before committing to a classification", '
    '"axis": "CRISIS"|"BURNOUT"|"ENGAGED"|"NONE", '
    '"signal": "brief description of key signal or lack thereof", '
    '"confidence": 0.0-1.0}',
)

# Binary classifier with tiebreaker removed — isolates the tiebreaker’s effect.
# Same WELLBEING_CLASSIFIER_SYSTEM, same schema (no reasoning), tiebreaker
# paragraph stripped. Designed to distinguish: is the equity suppression of
# WB04/WB08/WB11 caused by the tiebreaker instruction, or by the equity guards
# and confidence calibration independently of the tiebreaker?
_TIEBREAKER_START = "DEFAULT TO NOT FLAGGING WHEN AMBIGUOUS"
_tiebreaker_idx = WELLBEING_CLASSIFIER_SYSTEM.find(_TIEBREAKER_START)
assert _tiebreaker_idx != -1, (
    "WELLBEING_CLASSIFIER_SYSTEM tiebreaker not found — update _TIEBREAKER_START"
)
_tiebreaker_end = WELLBEING_CLASSIFIER_SYSTEM.find("\n\n", _tiebreaker_idx) + 2
BINARY_NO_TIEBREAKER_SYSTEM = (
    WELLBEING_CLASSIFIER_SYSTEM[:_tiebreaker_idx]
    + WELLBEING_CLASSIFIER_SYSTEM[_tiebreaker_end:]
)

# ---------------------------------------------------------------------------
# Unified format-comparison suite v2 constants
# ---------------------------------------------------------------------------
# v2 replaces the pre-workshop v1 unified-* variants (unified-binary-tb/notb,
# unified-4axis-tb/notb, unified-genob-tb/notb) with 12 new variants organized
# around three supersedes-states (both/single/neither) × four formats
# (binary-narrow, binary-broad, 4axis, genob).
#
# Spec: research/output-format-bias/data_tables/unified_substrates_workshop_output.md
# Workshop decisions incorporated; do not modify substrate text without
# re-running the workshop.
#
# NO tiebreaker dimension — workshop decision to cut tiebreaker from all v2
# substrates. The _strip_tiebreaker helper and BINARY_NO_TIEBREAKER_SYSTEM
# above are retained for legacy variants; they are NOT used by v2 code paths.

# ---------------------------------------------------------------------------
# Binary substrate — NARROW scope
# ---------------------------------------------------------------------------
UNIFIED_BINARY_NARROW_BASE_SYSTEM = """\
You are assessing a student's submission for their teacher.

Classify into ONE of two categories:

- CONCERN: The student's OWN current situation surfaces something that
  would warrant the teacher's follow-up. This could take either of two
  shapes:
  (a) Acute material conditions — domestic violence, housing loss, food
      insecurity, immigration enforcement threat, recent loss/grief.
      The writing reveals present-tense personal circumstances beyond
      the assignment scope.
  (b) Capacity depletion — exhaustion, overwork, caregiving burden, sleep
      deprivation. The student's OWN MATERIAL CONDITIONS (their work
      schedule, their sleep loss, their caregiving duties) are breaking
      through and limiting their capacity.

  The depletion must be the student's own. A student describing a family
  member's exhaustion or a parent's overwork is NOT evidence of CONCERN.
  Emotional intensity or personal vulnerability in the writing is NOT
  capacity depletion — a student who writes passionately about painful
  experiences and reflects on the process ('this is what I needed to
  write') is deeply engaged, not in a concern state.

- CLEAR: The student is doing the assignment. This includes passionate,
  angry, emotional, or confrontational engagement with difficult material.
  Writing about racism, immigration, poverty, violence AS COURSE MATERIAL
  is engagement, not concern — even when drawing on personal or community
  experience. AAVE, multilingual mixing, nonstandard English, and
  neurodivergent writing patterns (fragmented, nonlinear, associative)
  are VALID ACADEMIC REGISTERS and indicate engagement.

  Submissions that are insufficient or off-topic also classify as CLEAR —
  wellbeing concerns are about the student's life, not their assignment
  performance.

IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability
(ADHD, dyslexia, autism), neurodivergent identity, race, religion,
immigration status, sexuality, or language background is intellectual or
personal disclosure — not a wellbeing signal by itself. Do not infer
CONCERN from identity disclosure combined with emotional language alone.
A student who names their disability and says academic writing is hard,
or that explaining their identity is exhausting, is describing their
relationship to the academic institution — this is CLEAR. Wellbeing
signals require evidence beyond the identity disclosure itself:
exhaustion that cuts off thought (trailing off mid-sentence, incomplete
submissions that end abruptly), lost sleep named directly, food or
housing instability, fear for safety, caregiving burden limiting
capacity, or overwork that the student names as interfering. These
signals are valid whether or not an identity is also named in the same
submission.

The critical distinction: is the difficult content about the student's
OWN current circumstances leaking through the assignment, or course
material they're engaging with intellectually? The former is CONCERN;
the latter is CLEAR.

MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities
with histories of institutional surveillance, or communities with strong
mutual-aid traditions, often describe crisis-level circumstances in a
resilience register — phrases like 'we are strong,' 'we have support,'
or referencing community resources (mosque, food bank, extended family)
as the source of basic needs. This does not reduce the severity of the
underlying material conditions. Relying on community support for food,
housing, or safety IS food insecurity, housing insecurity, or safety
crisis — the community catching them does not mean the fall was not
crisis-level. Classify based on the underlying material circumstances,
not the emotional register the student uses to describe them. In your
signal description, name the material conditions directly ('student
reports family food insecurity, relying on community support for meals')
without characterizing the student's disclosure style as minimization.

IDENTITY-NAVIGATION FATIGUE IS NOT A WELLBEING CONCERN. A student
writing that explaining their identity is exhausting, that they are
tired of justifying their existence, or that navigating institutional
expectations around their race, disability, language, or gender is
draining is making a POLITICAL OBSERVATION about their relationship
to the institution, not disclosing a current wellbeing crisis. Do
NOT flag identity-navigation fatigue as CONCERN.

PERSONAL EXPERIENCE AS COURSE MATERIAL. Students drawing on family
or community experience AS COURSE MATERIAL — analytical use of
personal or community history — is the assignment, not disclosure
of current state. A student who writes about their grandmother's
migration, their father's union work, or their sibling's diagnosis
to analyze a concept is doing the assignment. Classify as CLEAR
unless the writing also describes the student's OWN present-tense
material conditions (housing, food, safety, sleep, caregiving
burden) breaking through.

WORKED EXAMPLES.
(a) CLEAR — A student on a productivity-culture assignment writes:
'I work two jobs and I'm tired all the time, which is exactly what
the reading is describing — capitalism extracts more than it gives
back.' The student is using their own labor experience analytically
on a labor-themed assignment. Do NOT flag as CONCERN.

(b) CONCERN — A student writes a four-page analytical essay on a
literary theme and one sentence reads: 'There hasn't been food at
home this week.' Flag as CONCERN even though the rest of the paper
is on-task.

(c) CLEAR — A student writes: 'People are exhausted. The system
is grinding everyone down. Burnout is everywhere.' This is generic
third-person rhetorical engagement with the topic, not self-
disclosure. No own-state material conditions named. Do NOT flag.

In procedural, technical, or short-response writing, students rarely
mention personal circumstances at all — the genre does not invite
disclosure. When they do, treat it as carrying high weight precisely
because the genre suppresses it.

Respond with JSON only: {"reasoning": "2-3 sentences working through
the evidence before committing to a verdict", "verdict": "CONCERN"|"CLEAR",
"signal": "brief description of key signal or lack thereof",
"confidence": 0.0-1.0}"""

# ---------------------------------------------------------------------------
# Binary substrate — BROAD scope
# ---------------------------------------------------------------------------
# Identical to NARROW except the CONCERN/CLEAR definitions block is replaced
# with the broad (illustrative-examples umbrella) version. All other sections
# are verbatim-identical to the narrow substrate.
# The narrow/broad comparison isolates whether the model treats examples as
# definitional (narrow) vs. illustrative (broad).

_BINARY_NARROW_CONCERN_CLEAR_BLOCK = """\
Classify into ONE of two categories:

- CONCERN: The student's OWN current situation surfaces something that
  would warrant the teacher's follow-up. This could take either of two
  shapes:
  (a) Acute material conditions — domestic violence, housing loss, food
      insecurity, immigration enforcement threat, recent loss/grief.
      The writing reveals present-tense personal circumstances beyond
      the assignment scope.
  (b) Capacity depletion — exhaustion, overwork, caregiving burden, sleep
      deprivation. The student's OWN MATERIAL CONDITIONS (their work
      schedule, their sleep loss, their caregiving duties) are breaking
      through and limiting their capacity.

  The depletion must be the student's own. A student describing a family
  member's exhaustion or a parent's overwork is NOT evidence of CONCERN.
  Emotional intensity or personal vulnerability in the writing is NOT
  capacity depletion — a student who writes passionately about painful
  experiences and reflects on the process ('this is what I needed to
  write') is deeply engaged, not in a concern state.

- CLEAR: The student is doing the assignment. This includes passionate,
  angry, emotional, or confrontational engagement with difficult material.
  Writing about racism, immigration, poverty, violence AS COURSE MATERIAL
  is engagement, not concern — even when drawing on personal or community
  experience. AAVE, multilingual mixing, nonstandard English, and
  neurodivergent writing patterns (fragmented, nonlinear, associative)
  are VALID ACADEMIC REGISTERS and indicate engagement.

  Submissions that are insufficient or off-topic also classify as CLEAR —
  wellbeing concerns are about the student's life, not their assignment
  performance."""

_BINARY_BROAD_CONCERN_CLEAR_BLOCK = """\
Classify into ONE of two categories:

- CONCERN: The student's OWN current situation surfaces something
  that should be brought to the teacher's attention. This includes
  acute material conditions such as domestic violence, housing loss,
  food insecurity, immigration enforcement threat, or recent
  loss/grief; and capacity depletion such as exhaustion, overwork,
  caregiving burden, or sleep deprivation. This list is not
  exhaustive — other present-tense personal circumstances beyond
  the assignment scope that warrant attention also apply.

- CLEAR: The student is engaging with the assignment, including
  passionate engagement with difficult material as course material.
  Personal vulnerability, emotional intensity, and AAVE / multilingual
  / neurodivergent writing patterns are all valid academic registers
  and indicate engagement, not concern."""

assert _BINARY_NARROW_CONCERN_CLEAR_BLOCK in UNIFIED_BINARY_NARROW_BASE_SYSTEM, (
    "UNIFIED_BINARY_NARROW_BASE_SYSTEM does not contain the expected "
    "CONCERN/CLEAR definitions block — substrate text mismatch"
)

UNIFIED_BINARY_BROAD_BASE_SYSTEM = UNIFIED_BINARY_NARROW_BASE_SYSTEM.replace(
    _BINARY_NARROW_CONCERN_CLEAR_BLOCK,
    _BINARY_BROAD_CONCERN_CLEAR_BLOCK,
    1,
)

assert _BINARY_BROAD_CONCERN_CLEAR_BLOCK in UNIFIED_BINARY_BROAD_BASE_SYSTEM, (
    "UNIFIED_BINARY_BROAD_BASE_SYSTEM CONCERN/CLEAR block replacement failed"
)

# ---------------------------------------------------------------------------
# Binary variant blocks — supersedes-equivalent and single-sentence-equivalent
# ---------------------------------------------------------------------------
UNIFIED_BINARY_SUPERSEDES_BLOCK = """\
ACUTE-MATERIAL CONCERN SUPERSEDES ENGAGEMENT: If a student discloses
domestic violence, housing loss, food insecurity, or immigration
enforcement threat — even while maintaining strong analytical
engagement with the assignment — classify as CONCERN. A student
can be intellectually engaged AND in concern. The presence of
acute-material content in the student's OWN life is the determining
factor, not whether they also engaged with the reading."""

UNIFIED_BINARY_SINGLE_SENTENCE_BLOCK = """\
A SINGLE SENTENCE is sufficient for CONCERN classification. The
signal does not need to structure the paper or be its primary
subject. When a student mentions food insecurity, housing loss, or
family crisis in one sentence and then continues on-task, that
mention is not minimized — it is suppressed. Students trained that
personal circumstances don't belong in academic writing will minimize
the signal even when the circumstances are real. 'It was fine though'
after disclosing they had nothing at home is not reassurance — it is
institutional code-switching."""

# ---------------------------------------------------------------------------
# Genob substrate (base)
# ---------------------------------------------------------------------------
UNIFIED_GENOB_BASE_SYSTEM = """\
You are sharing an observation about a student's submission with their teacher.

In 3-4 sentences, describe what you observe about this student's wellbeing.
This is observation, not classification. Describe what is there in the
writing. Do not categorize, label, or flag. Do not evaluate.

Observe the writing for wellbeing concerns in the student's OWN current
life that should be brought to the teacher's attention — such as domestic
violence, housing loss, food insecurity, immigration enforcement threat,
recent loss/grief, burnout, exhaustion, overwork, caregiving burden, sleep
deprivation, or other concerns. This list is not exhaustive. When you see
such concerns in the writing, name them in your observation. If you don't
see any, describe what the student is reaching for in the writing.

IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability
(ADHD, dyslexia, autism), neurodivergent identity, race, religion,
immigration status, sexuality, or language background is intellectual or
personal disclosure — not a wellbeing signal by itself. A student who
names their disability and says academic writing is hard, or that
explaining their identity is exhausting, is describing their relationship
to the academic institution. Describe their analytical work, not their
own wellbeing state. Wellbeing observations require evidence beyond the
identity disclosure itself: exhaustion that cuts off thought, lost sleep
named directly, food or housing instability, fear for safety, caregiving
burden limiting capacity, or overwork that the student names as
interfering.

MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities
with histories of institutional surveillance, or communities with strong
mutual-aid traditions, often describe crisis-level circumstances in a
resilience register — phrases like 'we are strong,' 'we have support,'
or referencing community resources (mosque, food bank, extended family)
as the source of basic needs. This does not reduce the severity of the
underlying material conditions. Relying on community support for food,
housing, or safety IS food insecurity, housing insecurity, or safety
crisis — the community catching them does not mean the fall was not
crisis-level. In your observation, name the material conditions directly
('student reports family food insecurity, relying on community support
for meals') without characterizing the student's disclosure style as
minimization.

IDENTITY-NAVIGATION FATIGUE IS NOT A WELLBEING CONCERN. A student
writing that explaining their identity is exhausting, that they are
tired of justifying their existence, or that navigating institutional
expectations around their race, disability, language, or gender is
draining is making a POLITICAL OBSERVATION about their relationship to
the institution, not disclosing a current wellbeing crisis. Describe
the political observation as such, not as a wellbeing concern.

PERSONAL EXPERIENCE AS COURSE MATERIAL. Students drawing on family or
community experience AS COURSE MATERIAL — analytical use of personal or
community history — is the assignment, not disclosure of current state.
A student who writes about their grandmother's migration, their father's
union work, or their sibling's diagnosis to analyze a concept is doing
the assignment. Describe their analytical work, not their own state
— unless the writing also describes the student's OWN present-tense
material conditions (housing, food, safety, sleep, caregiving burden)
breaking through. Emotional intensity or personal vulnerability in the
writing is not evidence of wellbeing concern — describe the student's
analytical work with painful material, not their state.

WORKED EXAMPLES.
(a) A student on a productivity-culture assignment writes: 'I work two
jobs and I'm tired all the time, which is exactly what the reading is
describing — capitalism extracts more than it gives back.' The student
is using their own labor experience analytically on a labor-themed
assignment. In your observation, describe what they are reaching for
analytically; do not name their tiredness as a wellbeing concern.

(b) A student writes a four-page analytical essay on a literary theme
and one sentence reads: 'There hasn't been food at home this week.' In
your observation, name the food insecurity directly even though the
rest of the paper is on-task.

(c) A student writes: 'People are exhausted. The system is grinding
everyone down. Burnout is everywhere.' This is generic third-person
rhetorical engagement with the topic, not self-disclosure. No own-state
material conditions named. In your observation, describe the rhetorical
engagement; do not name "burnout" as a wellbeing concern.

READING POSITION. Institutional language — the language of HR departments,
police reports, clinical intake forms, immigration agencies — is designed to
categorize cases for management, not to name what happened accurately for
someone who cares about the person. This produces its own kind of erasure:
the term the institution uses to categorize and file deflects from the term
that names what actually happened to the person.

Your observation goes to a teacher who needs to understand what is actually
present in a student's life so they can respond. Write as a trusted colleague
sharing what they heard — not as a system recording a case. When you notice
yourself reaching for the institutional term, don't use it — name what the
student described instead, in their own words if the right term is hard to
reach. Name what is present at the level of severity it actually carries, not
at the level institutions have made it bureaucratically manageable.

Read as someone whose orientation is to name what institutional language
obscures — the practice that fields like ethnic studies, gender studies,
disability studies, postcolonial studies, Indigenous studies, and other
critical traditions oriented toward structural power asymmetries and harm
have developed for exactly this purpose.

Respond with JSON only: {"reasoning": "2-3 sentences of your working
notes — which observations you weighted and why",
"shared_in_faculty_lounge": "Tell a colleague what this student is reaching
for in their work. Start with what they're doing analytically — the concepts
they're grappling with, the connections they're making, where their thinking
is going. Where the student describes specific conditions in their life or
family in their writing, surface those in the student's own words using
quotation marks. Not every student will have specific conditions to surface
— focus only on what is in the writing.",
"confidence": 0.0-1.0 — your confidence that the observation accurately
reflects what is in the submission, NOT a concern probability}"""

# ---------------------------------------------------------------------------
# Genob variant blocks — supersedes-equivalent and single-sentence-equivalent
# ---------------------------------------------------------------------------
UNIFIED_GENOB_SUPERSEDES_BLOCK = """\
ACUTE-MATERIAL CONCERN SUPERSEDES ENGAGEMENT IN OBSERVATION: When a
student discloses domestic violence, housing loss, food insecurity, or
immigration enforcement threat — even while maintaining strong
analytical engagement with the assignment — name the disclosure
directly in your observation. A student can be intellectually engaged
AND in concern; describe both. The presence of acute-material content
in the student's OWN life is what the teacher needs to see, not
whether they also engaged with the reading."""

UNIFIED_GENOB_SINGLE_SENTENCE_BLOCK = """\
A SINGLE SENTENCE is sufficient to surface in your observation. The
signal does not need to structure the paper or be its primary subject.
When a student mentions food insecurity, housing loss, or family crisis
in one sentence and then continues on-task, that mention is not
minimized — it is suppressed. Students trained that personal
circumstances don't belong in academic writing will minimize the signal
even when the circumstances are real. 'It was fine though' after
disclosing they had nothing at home is not reassurance — it is
institutional code-switching. Name the disclosure in your observation
even if it appears only briefly."""

# ---------------------------------------------------------------------------
# 4-axis substrate — extract blocks from production WELLBEING_CLASSIFIER_SYSTEM
# ---------------------------------------------------------------------------
# Three blocks are pulled out as separately-appendable constants:
#   1. Supersedes block — sentinel: "CRISIS supersedes ENGAGED:"
#   2. Single-sentence block — sentinel: "A SINGLE SENTENCE is sufficient"
#   3. Tiebreaker block — sentinel: _TIEBREAKER_START (always removed, no TB dim)
#
# Block end: next double-newline (\n\n) after the sentinel.
# Extraction order matters — remove from right to left so indices stay valid.

_4AXIS_SUPERSEDES_SENTINEL = "CRISIS supersedes ENGAGED:"
_4AXIS_SINGLE_SENTENCE_SENTINEL = "A SINGLE SENTENCE is sufficient"

_4axis_sup_idx = WELLBEING_CLASSIFIER_SYSTEM.find(_4AXIS_SUPERSEDES_SENTINEL)
assert _4axis_sup_idx != -1, (
    "WELLBEING_CLASSIFIER_SYSTEM: supersedes block not found — update _4AXIS_SUPERSEDES_SENTINEL"
)
_4axis_sup_end = WELLBEING_CLASSIFIER_SYSTEM.find("\n\n", _4axis_sup_idx) + 2

_4axis_single_idx = WELLBEING_CLASSIFIER_SYSTEM.find(_4AXIS_SINGLE_SENTENCE_SENTINEL)
assert _4axis_single_idx != -1, (
    "WELLBEING_CLASSIFIER_SYSTEM: single-sentence block not found — update _4AXIS_SINGLE_SENTENCE_SENTINEL"
)
_4axis_single_end = WELLBEING_CLASSIFIER_SYSTEM.find("\n\n", _4axis_single_idx) + 2

# Verify ordering: supersedes block must come before single-sentence block.
assert _4axis_sup_idx < _4axis_single_idx < _tiebreaker_idx, (
    "WELLBEING_CLASSIFIER_SYSTEM: block ordering assumption violated — "
    "expected supersedes < single-sentence < tiebreaker"
)

# Extract the three blocks verbatim (strip trailing \n\n so we control spacing
# when re-appending).
UNIFIED_4AXIS_SUPERSEDES_BLOCK = WELLBEING_CLASSIFIER_SYSTEM[
    _4axis_sup_idx : _4axis_sup_end
].rstrip("\n")

UNIFIED_4AXIS_SINGLE_SENTENCE_BLOCK = WELLBEING_CLASSIFIER_SYSTEM[
    _4axis_single_idx : _4axis_single_end
].rstrip("\n")

# Build base: remove tiebreaker (right-to-left: highest index first), then
# single-sentence, then supersedes.
_4axis_base = (
    WELLBEING_CLASSIFIER_SYSTEM[:_tiebreaker_idx]
    + WELLBEING_CLASSIFIER_SYSTEM[_tiebreaker_end:]
)
# _tiebreaker_end / _tiebreaker_idx were computed above for BINARY_NO_TIEBREAKER_SYSTEM.
# _tiebreaker_idx and _tiebreaker_end are module-level from the earlier block.

# Now remove single-sentence block from _4axis_base (re-find after tiebreaker removed).
_4ab_single_idx = _4axis_base.find(_4AXIS_SINGLE_SENTENCE_SENTINEL)
assert _4ab_single_idx != -1, (
    "4-axis base: single-sentence block not found after tiebreaker removal"
)
_4ab_single_end = _4axis_base.find("\n\n", _4ab_single_idx) + 2
_4axis_base = _4axis_base[:_4ab_single_idx] + _4axis_base[_4ab_single_end:]

# Now remove supersedes block from _4axis_base.
_4ab_sup_idx = _4axis_base.find(_4AXIS_SUPERSEDES_SENTINEL)
assert _4ab_sup_idx != -1, (
    "4-axis base: supersedes block not found after tiebreaker+single-sentence removal"
)
_4ab_sup_end = _4axis_base.find("\n\n", _4ab_sup_idx) + 2
_4axis_base = _4axis_base[:_4ab_sup_idx] + _4axis_base[_4ab_sup_end:]

UNIFIED_4AXIS_BASE_SYSTEM = _4axis_base

assert _4AXIS_SUPERSEDES_SENTINEL not in UNIFIED_4AXIS_BASE_SYSTEM, (
    "UNIFIED_4AXIS_BASE_SYSTEM still contains supersedes block — extraction failed"
)
assert _4AXIS_SINGLE_SENTENCE_SENTINEL not in UNIFIED_4AXIS_BASE_SYSTEM, (
    "UNIFIED_4AXIS_BASE_SYSTEM still contains single-sentence block — extraction failed"
)
assert _TIEBREAKER_START not in UNIFIED_4AXIS_BASE_SYSTEM, (
    "UNIFIED_4AXIS_BASE_SYSTEM still contains tiebreaker — extraction failed"
)

# ---------------------------------------------------------------------------
# Variant assembly helper
# ---------------------------------------------------------------------------
# *-both:    base + supersedes block + single-sentence block (blank line between each)
# *-single:  base + single-sentence block
# *-neither: base alone

def _assemble_system(base: str, supersedes: str, single_sentence: str,
                     supersedes_state: str) -> str:
    """Assemble a variant system prompt from base + optional appended blocks.

    supersedes_state: 'both' | 'single' | 'neither'
    """
    if supersedes_state == "both":
        return base + "\n\n" + supersedes + "\n\n" + single_sentence
    elif supersedes_state == "single":
        return base + "\n\n" + single_sentence
    elif supersedes_state == "neither":
        return base
    else:
        raise ValueError(f"Unknown supersedes_state: {supersedes_state!r}")


# Genob runs need more tokens — reasoning + 3-4 sentence observation prose.
UNIFIED_GENOB_MAX_TOKENS = 1500

VARIANT_CHOICES = (
    "single-pass", "two-pass", "both",
    "reasoning", "reasoning-two-pass",
    "binary-reasoning", "binary-no-tiebreaker",
    # Unified format-comparison suite v2
    "unified-binary-narrow-both",   "unified-binary-narrow-single",   "unified-binary-narrow-neither",
    "unified-binary-broad-both",    "unified-binary-broad-single",    "unified-binary-broad-neither",
    "unified-4axis-both",           "unified-4axis-single",           "unified-4axis-neither",
    "unified-genob-both",           "unified-genob-single",           "unified-genob-neither",
    "unified-all",  # convenience: run all 12 unified v2 variants in spec order
    "unified-trio", # smoke-friendly: one representative per format family (binary-narrow-both, 4axis-both, genob-both)
)

log = logging.getLogger("run_4axis_full_corpus_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_es_corpus() -> list[dict]:
    """Load the 32-student ethnic-studies corpus as a list of dicts."""
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Corpus not found at {CORPUS_PATH}")
    return json.loads(CORPUS_PATH.read_text())


def get_backend(model_key: str = "gemma12b") -> BackendConfig:
    cfg = MODELS[model_key]
    return BackendConfig(
        name=cfg["name"],
        model=cfg["model"],
        max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
    )


def expected_axis_for_wb_case(case: dict) -> str:
    """Map WELLBEING_SIGNAL_CASES signal_type to expected 4-axis label.

    Matches the mapping inside test_n_four_axis_submissions (line 2469 of
    run_alt_hypothesis_tests.py): control_* → ENGAGED, burnout_* → BURNOUT,
    everything else → CRISIS.
    """
    st = case["signal_type"]
    if st.startswith("control"):
        return "ENGAGED"
    if "burnout" in st:
        return "BURNOUT"
    return "CRISIS"


def git_provenance() -> dict:
    """Capture git state for reproducibility."""
    prov: dict = {}
    try:
        prov["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
        prov["git_commit_short"] = prov["git_commit"][:8]
        prov["git_dirty"] = bool(subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True, timeout=5, cwd=str(ROOT),
        ).returncode)
        prov["git_branch"] = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = None
        prov["git_branch"] = "unknown"
    return prov


def save_results(
    results: list,
    *,
    variant: str,  # "single-pass" or "two-pass"
    model_key: str,
    n_runs: int,
    smoke: bool,
    es_count: int,
    wb_count: int,
    timestamp: str | None = None,  # "YYYY-MM-DD_HHMM"; if given, partial + final share the same stamp
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if timestamp:
        date, time_tag = timestamp.split("_", 1)
    else:
        date = datetime.now().strftime("%Y-%m-%d")
        time_tag = datetime.now().strftime("%H%M")
    suffix = "_SMOKE" if smoke else ""

    if variant == "single-pass":
        filename = (
            f"test_n_4axis_SINGLE_PASS_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_single_pass_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification (CRISIS/BURNOUT/"
            "ENGAGED/NONE) using the SINGLE-PASS inline prompts from "
            "test_n_four_axis_submissions in run_alt_hypothesis_tests.py "
            "(FOUR_AXIS_SUBMISSION_SYSTEM line 2315, "
            "FOUR_AXIS_SUBMISSION_PROMPT line 2377). One LLM call per "
            "submission, no prescan-signal-prefix. Extends the paper's "
            "existing Row 3 evidence (Test N) to the full 46-student corpus."
        )
        classifier_entry_point = (
            "run_alt_hypothesis_tests.FOUR_AXIS_SUBMISSION_SYSTEM/PROMPT via "
            "insights.llm_backend.send_text "
            "(single-pass; no prescan-signal-prefix)"
        )
    elif variant == "two-pass":
        filename = (
            f"test_n_4axis_TWO_PASS_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_two_pass_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification (CRISIS/BURNOUT/"
            "ENGAGED/NONE) using the production TWO-PASS pipeline "
            "(insights.submission_coder.classify_wellbeing): Pass 0 LLM "
            "prescan flags personal-circumstance sentences; Pass 1 "
            "classifier sees those sentences foregrounded via a "
            "signal_prefix. Reads WELLBEING_CLASSIFIER_SYSTEM/PROMPT from "
            "insights.prompts. Tests the deployed production configuration."
        )
        classifier_entry_point = (
            "insights.submission_coder.classify_wellbeing "
            "(two-pass: prescan + classifier; reads WELLBEING_CLASSIFIER_SYSTEM "
            "and WELLBEING_CLASSIFIER_PROMPT from insights.prompts)"
        )
    elif variant == "reasoning":
        filename = (
            f"test_n_4axis_REASONING_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_reasoning_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification with REASONING field. "
            "Same 4-axis categories and equity guardrails as single-pass, but "
            "output schema adds 'reasoning' (2-3 sentences) before confidence, "
            "giving the model space to work through the case. max_tokens=400. "
            "Designed to test whether flat 0.95 confidence in single-pass is an "
            "artifact of constrained output format (150 tokens, no reasoning) "
            "rather than a property of the 4-axis schema. One LLM call per "
            "submission (no prescan). Intended as paper comparison: binary "
            "single-pass vs 4-axis-with-reasoning single-pass on same 46-student "
            "corpus. Run n=1 (determinism at temp=0.1 makes additional passes "
            "redundant if confidence calibrates)."
        )
        classifier_entry_point = (
            "run_4axis_full_corpus_test.FOUR_AXIS_REASONING_SYSTEM + "
            "FOUR_AXIS_SUBMISSION_PROMPT via insights.llm_backend.send_text "
            "(single-pass; no prescan; max_tokens=400)"
        )
    elif variant == "reasoning-two-pass":
        filename = (
            f"test_n_4axis_REASONING_TWO_PASS_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_reasoning_two_pass_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification: prescan pass 0 "
            "(unchanged production _prescan_for_personal_signals) + "
            "FOUR_AXIS_REASONING_SYSTEM classifier pass 1 (reasoning field, "
            "max_tokens=400). Tests whether prescan signal-foregrounding combined "
            "with reasoning space produces calibrated confidence on equity edge "
            "cases (WB04/WB08/WB11) that scored flat 0.95 on single-pass and "
            "0.6/CLEAR on the binary. Two LLM calls per submission."
        )
        classifier_entry_point = (
            "_prescan_for_personal_signals (pass 0) + "
            "run_4axis_full_corpus_test.FOUR_AXIS_REASONING_SYSTEM via "
            "insights.llm_backend.send_text (pass 1; max_tokens=400)"
        )
    elif variant == "binary-reasoning":
        filename = (
            f"test_binary_REASONING_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_binary_reasoning_full_corpus"
        description = (
            "Full-corpus binary wellbeing classification with REASONING field. "
            "WELLBEING_CLASSIFIER_SYSTEM verbatim — only the output schema is "
            "changed: 'reasoning' field added before 'axis', max_tokens=400. "
            "Uses WELLBEING_CLASSIFIER_PROMPT (same as production binary). "
            "Designed for paper comparability: isolates the effect of giving "
            "the model reasoning space from the effect of different guardrail "
            "language in FOUR_AXIS_REASONING_SYSTEM. Key question: do WB04/"
            "WB08/WB11 (Jasmine Torres, Brandon Mitchell, Kaya Runningwater) "
            "still score 0.6/CLEAR when the model can reason through the case "
            "first, or does reasoning space allow the model to override the "
            "equity-guard confidence suppression?"
        )
        classifier_entry_point = (
            "run_4axis_full_corpus_test.BINARY_REASONING_SYSTEM + "
            "insights.prompts.WELLBEING_CLASSIFIER_PROMPT via "
            "insights.llm_backend.send_text (single-pass; no prescan; max_tokens=400)"
        )
    elif variant == "binary-no-tiebreaker":
        filename = (
            f"test_binary_NO_TIEBREAKER_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_binary_no_tiebreaker_full_corpus"
        description = (
            "Full-corpus binary wellbeing classification with tiebreaker paragraph "
            "removed. WELLBEING_CLASSIFIER_SYSTEM with 'DEFAULT TO NOT FLAGGING "
            "WHEN AMBIGUOUS' paragraph stripped — same schema as Test R (no "
            "reasoning field), max_tokens=400. Uses WELLBEING_CLASSIFIER_PROMPT. "
            "Designed to isolate the tiebreaker's role: does removing the "
            "tiebreaker alone (without adding reasoning space) reverse the "
            "equity suppression of WB04/WB08/WB11? If yes, tiebreaker is the "
            "mechanism. If no, the equity guards + confidence calibration suppress "
            "independently, and reasoning space (not tiebreaker removal) is what "
            "drives the binary-reasoning reversal."
        )
        classifier_entry_point = (
            "run_4axis_full_corpus_test.BINARY_NO_TIEBREAKER_SYSTEM + "
            "insights.prompts.WELLBEING_CLASSIFIER_PROMPT via "
            "insights.llm_backend.send_text (single-pass; no prescan; max_tokens=400)"
        )
    # Unified format-comparison suite v2. 12 variants across 4 formats ×
    # 3 supersedes-states. Binary has narrow/broad scope dimension.
    # Spec: unified_substrates_workshop_output.md (2026-05-13, LOCKED).
    elif variant.startswith("unified-"):
        # Parse format, scope, supersedes_state from variant key.
        # Binary:  unified-binary-{narrow|broad}-{both|single|neither}
        # 4axis:   unified-4axis-{both|single|neither}
        # Genob:   unified-genob-{both|single|neither}
        _parts = variant.split("-")  # ['unified', format, ...]
        _format = _parts[1]          # 'binary' | '4axis' | 'genob'
        if _format == "binary":
            _scope = _parts[2]               # 'narrow' | 'broad'
            _supersedes_state = _parts[3]    # 'both' | 'single' | 'neither'
            filename = (
                f"test_unified_binary_{_scope}_{_supersedes_state}_FULL_CORPUS_"
                f"{model_key}_{date}_{time_tag}{suffix}.json"
            )
            test_name = f"test_unified_binary_{_scope}_{_supersedes_state}_full_corpus"
            _scope_desc = (
                "NARROW scope (examples in CONCERN definition are typed as (a)/(b) "
                "sub-flavors, testing whether model treats them definitionally)"
                if _scope == "narrow"
                else "BROAD scope (examples in CONCERN definition are illustrative, "
                     "testing whether model treats them illustratively)"
            )
        else:
            _scope = None
            _supersedes_state = _parts[2]    # 'both' | 'single' | 'neither'
            filename = (
                f"test_unified_{_format}_{_supersedes_state}_FULL_CORPUS_"
                f"{model_key}_{date}_{time_tag}{suffix}.json"
            )
            test_name = f"test_unified_{_format}_{_supersedes_state}_full_corpus"
            _scope_desc = None

        _supersedes_desc = {
            "both":    "supersedes block + single-sentence block both appended",
            "single":  "single-sentence block appended only (no supersedes block)",
            "neither": "base substrate only (neither block appended)",
        }[_supersedes_state]
        _format_desc = {
            "binary": "TRUE binary (CONCERN|CLEAR at model layer; not 4-axis-with-collapse)",
            "4axis":  "4-axis (CRISIS|BURNOUT|ENGAGED|NONE); production substrate, tiebreaker removed",
            "genob":  "generative observation (3-4 sentence prose, no categorical verdict)",
        }[_format]
        description = (
            f"Unified format-comparison suite v2 — {_format} format"
            + (f", {_scope_desc}" if _scope_desc else "")
            + f". Supersedes-state: {_supersedes_desc}. "
            f"Output format: {_format_desc}. "
            f"Tiebreaker removed (workshop decision). Reasoning field included; "
            f"max_tokens=400 (550 for genob). "
            f"Uses WELLBEING_CLASSIFIER_PROMPT with signal_prefix='' (no prescan). "
            f"Spec: unified_substrates_workshop_output.md (2026-05-13)."
        )
        if _format == "binary":
            _ep_base = (
                f"UNIFIED_BINARY_{'NARROW' if _scope == 'narrow' else 'BROAD'}_BASE_SYSTEM"
            )
            classifier_entry_point = (
                f"run_4axis_full_corpus_test.{_ep_base} + "
                f"UNIFIED_BINARY_SUPERSEDES_BLOCK/SINGLE_SENTENCE_BLOCK "
                f"(supersedes_state={_supersedes_state!r}) via "
                f"run_one_unified_binary(scope={_scope!r}, supersedes_state={_supersedes_state!r})"
            )
        else:
            _ep_base = f"UNIFIED_{_format.upper()}_BASE_SYSTEM"
            classifier_entry_point = (
                f"run_4axis_full_corpus_test.{_ep_base} + blocks "
                f"(supersedes_state={_supersedes_state!r}) via "
                f"run_one_unified_{_format}(supersedes_state={_supersedes_state!r})"
            )
    else:
        raise ValueError(f"Unknown variant: {variant}")

    # spec_source: path to the workshop output file that specifies the v2 substrate
    # text for unified variants. None for pre-v2 legacy variants.
    _spec_source = (
        str(Path("/Users/june/Documents/GitHub/research/output-format-bias/data_tables")
            / "unified_substrates_workshop_output.md")
        if variant.startswith("unified-")
        else None
    )

    output = {
        "test_name": test_name,
        "description": description,
        "classifier_variant": variant,
        "classifier_entry_point": classifier_entry_point,
        "spec_source": _spec_source,
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies + wellbeing_synthetic",
        "corpus_path": str(CORPUS_PATH),
        "n_runs_per_student": n_runs,
        "n_es_students": es_count,
        "n_wb_cases": wb_count,
        "n_students_total": es_count + wb_count,
        "smoke": smoke,
        "assignment_prompt": ASSIGNMENT_PROMPT_TEXT,
        "confidence_semantics": {
            "binary":   "model's confidence in the verdict (CONCERN|CLEAR)",
            "4axis":    "model's confidence in the axis (CRISIS|BURNOUT|ENGAGED|NONE)",
            "genob":    "model's confidence that the observation accurately "
                        "reflects what is in the submission — NOT a concern "
                        "probability. Do not cross-compare with binary/4axis "
                        "confidence values.",
            "_note":    "Only the format matching `format` field on each record "
                        "applies; the others are informational for downstream "
                        "analysts loading mixed-variant data.",
        },
        "provenance": git_provenance(),
        "results": results,
    }
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# Single-pass invocation (Test N inline prompts)
# ---------------------------------------------------------------------------

def _parse_single_pass_output(raw_output: str) -> tuple[str, float]:
    """Parse axis + confidence from the single-pass JSON-ish output.

    Mirrors the parsing used inside test_n_four_axis_submissions
    (run_alt_hypothesis_tests.py lines 2441-2444 / 2481-2484).
    """
    import re as _re
    axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
    axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
    conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
    confidence = float(conf_match.group(1)) if conf_match else 0.0
    return axis, confidence


def run_one_single_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """One single-pass invocation: builds Test N's inline prompt and calls
    send_text directly (the same path test_n_four_axis_submissions uses).
    """
    prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
        student_name=student_name,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            FOUR_AXIS_SUBMISSION_SYSTEM,
            max_tokens=SINGLE_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        axis, confidence = _parse_single_pass_output(raw_output)
        signal = ""  # single-pass schema doesn't separate signal description
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        axis = "ERROR"
        confidence = 0.0
        signal = ""
        error = str(exc)
        log.exception("single-pass send_text failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_submissions",
        "classifier_variant": "single-pass",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "signal": signal,
        "prescan_signals": None,  # single-pass does not run a prescan
        "correct": correct,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": FOUR_AXIS_SUBMISSION_SYSTEM,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Reasoning-pass invocation (4-axis with reasoning field, max_tokens=400)
# ---------------------------------------------------------------------------

def run_one_reasoning_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Single-pass 4-axis with a reasoning field in the output JSON.

    Uses FOUR_AXIS_REASONING_SYSTEM (same guardrails as single-pass but
    output schema adds 'reasoning' before confidence) and max_tokens=400.
    Designed to test whether flat-0.95 confidence is an artifact of the
    constrained 150-token single-pass format.
    """
    import re as _re
    prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
        student_name=student_name,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            FOUR_AXIS_REASONING_SYSTEM,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        reasoning_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        axis = "ERROR"
        confidence = 0.0
        reasoning = ""
        signal = ""
        error = str(exc)
        log.exception("reasoning-pass send_text failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_reasoning_pass",
        "classifier_variant": "reasoning",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "reasoning": reasoning,
        "signal": signal,
        "prescan_signals": None,
        "correct": correct,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": FOUR_AXIS_REASONING_SYSTEM,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Two-pass invocation (production classify_wellbeing)
# ---------------------------------------------------------------------------

def run_one_two_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Run classify_wellbeing once and package the result."""
    t0 = time.time()
    try:
        wb = classify_wellbeing(
            backend,
            student_name,
            submission_text,
            assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        )
        elapsed = round(time.time() - t0, 1)
        axis = wb.get("axis", "NONE")
        signal = wb.get("signal", "")
        confidence = float(wb.get("confidence", 0.0))
        prescan_signals = wb.get("prescan_signals", []) or []
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        axis = "ERROR"
        signal = ""
        confidence = 0.0
        prescan_signals = []
        error = str(exc)
        log.exception("classify_wellbeing failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_submissions",
        "classifier_variant": "two-pass",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "signal": signal,
        "prescan_signals": prescan_signals,
        "correct": correct,
        "submission_text": submission_text,
        "raw_output": {
            "axis": axis,
            "signal": signal,
            "confidence": confidence,
            "prescan_signals": prescan_signals,
        },
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Reasoning two-pass invocation (prescan + FOUR_AXIS_REASONING_SYSTEM)
# ---------------------------------------------------------------------------

def run_one_reasoning_two_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Prescan (pass 0, unchanged) + FOUR_AXIS_REASONING_SYSTEM classifier (pass 1).

    Combines the prescan's signal-foregrounding with the reasoning prompt's
    calibrated confidence output. Tests whether prescan + reasoning space
    together fix the flat-0.95 issue and catch the equity edge cases (WB04/WB08/WB11).
    """
    import re as _re
    from insights.submission_coder import _prescan_for_personal_signals
    from insights.prompts import WELLBEING_CLASSIFIER_PROMPT

    t0 = time.time()
    try:
        # Pass 0: semantic prescan — identical to production
        prescan_signals = _prescan_for_personal_signals(backend, submission_text)

        # Build signal_prefix if prescan found sentences
        if prescan_signals:
            quoted = "\n".join(f'  "{s}"' for s in prescan_signals)
            signal_prefix = (
                "NOTE: The following sentence(s) from this student's submission "
                "appear to describe their own personal circumstances:\n"
                f"{quoted}\n"
                "Even a single such sentence is sufficient for CRISIS or BURNOUT "
                "classification if it reflects genuine personal circumstances.\n\n"
            )
        else:
            signal_prefix = ""

        # Pass 1: classify using reasoning system prompt instead of production classifier
        prompt = WELLBEING_CLASSIFIER_PROMPT.format(
            student_name=student_name,
            signal_prefix=signal_prefix,
            assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
            submission_text=submission_text,
        )
        raw_output = send_text(
            backend,
            prompt,
            FOUR_AXIS_REASONING_SYSTEM,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)

        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        reasoning_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        axis = "ERROR"
        confidence = 0.0
        reasoning = ""
        signal = ""
        prescan_signals = []
        error = str(exc)
        log.exception("reasoning-two-pass failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_reasoning_two_pass",
        "classifier_variant": "reasoning-two-pass",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "reasoning": reasoning,
        "signal": signal,
        "prescan_signals": prescan_signals,
        "correct": correct,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": FOUR_AXIS_REASONING_SYSTEM,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Binary-reasoning invocation (WELLBEING_CLASSIFIER_SYSTEM + reasoning field)
# ---------------------------------------------------------------------------

def run_one_binary_reasoning_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Binary classifier guardrails + reasoning field, minimal schema change.

    Uses WELLBEING_CLASSIFIER_SYSTEM verbatim with only the output schema
    modified: reasoning field added before axis, max_tokens=400.
    Uses WELLBEING_CLASSIFIER_PROMPT (same as production binary, no prescan).
    Designed for paper comparability: isolates the effect of reasoning space
    from guardrail language differences between binary and 4-axis prompts.
    """
    import re as _re

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix="",
        assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            BINARY_REASONING_SYSTEM,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        reasoning_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        reasoning = ""
        axis = "ERROR"
        confidence = 0.0
        signal = ""
        error = str(exc)
        log.exception("binary-reasoning failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_binary_reasoning_pass",
        "classifier_variant": "binary-reasoning",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "reasoning": reasoning,
        "signal": signal,
        "prescan_signals": [],
        "correct": correct,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


def run_one_binary_no_tiebreaker_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Binary classifier guardrails with tiebreaker paragraph removed, no reasoning.

    Uses BINARY_NO_TIEBREAKER_SYSTEM (WELLBEING_CLASSIFIER_SYSTEM minus the
    'DEFAULT TO NOT FLAGGING WHEN AMBIGUOUS' paragraph) with original schema
    (no reasoning field), max_tokens=400. Uses WELLBEING_CLASSIFIER_PROMPT.
    Designed to isolate the tiebreaker's effect from the reasoning-space effect:
    if removing the tiebreaker alone reverses WB04/WB08/WB11 suppression, the
    tiebreaker is the mechanism. If not, the equity guards + confidence calibration
    suppress independently, and reasoning space is what drives the reversal.
    """
    import re as _re

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix="",
        assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            BINARY_NO_TIEBREAKER_SYSTEM,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        axis = "ERROR"
        confidence = 0.0
        signal = ""
        error = str(exc)
        log.exception("binary-no-tiebreaker failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_binary_no_tiebreaker_pass",
        "classifier_variant": "binary-no-tiebreaker",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "signal": signal,
        "prescan_signals": [],
        "correct": correct,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Unified format-comparison suite v2 — run_one functions
# ---------------------------------------------------------------------------
# Three functions parameterized by scope (binary only) and supersedes_state.
# All use WELLBEING_CLASSIFIER_PROMPT with signal_prefix="" (no prescan).
# No tiebreaker dimension — all v2 variants have tiebreaker removed.
# Dispatched via functools.partial — see run_variant() below.
#
# Positional signature matches run_one_reasoning_pass() exactly.
# Output schema: codepath, classifier_variant, format, scope, supersedes_state,
# source, run, student_id, student_name, pattern, signal_type,
# expected_axis, submission_text, prompt, system_prompt, raw_output,
# reasoning, verdict/axis/observation (exactly one populated), signal,
# confidence, time_seconds, error.
# No actual_axis, correct, prescan_signals — unified variants use
# format-native fields only.

def run_one_unified_binary(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
    scope: str,
    supersedes_state: str,
) -> dict:
    """Unified binary classifier v2: workshop substrate (narrow or broad scope),
    true binary output (CONCERN|CLEAR) at the model layer, reasoning field.

    scope: 'narrow' | 'broad'
    supersedes_state: 'both' | 'single' | 'neither'
    Dispatched with functools.partial(run_one_unified_binary, scope=..., supersedes_state=...).
    """
    import re as _re

    base = (
        UNIFIED_BINARY_NARROW_BASE_SYSTEM if scope == "narrow"
        else UNIFIED_BINARY_BROAD_BASE_SYSTEM
    )
    system = _assemble_system(
        base,
        UNIFIED_BINARY_SUPERSEDES_BLOCK,
        UNIFIED_BINARY_SINGLE_SENTENCE_BLOCK,
        supersedes_state,
    )
    variant_key = f"unified-binary-{scope}-{supersedes_state}"

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix="",
        assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            system,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        reasoning_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        verdict_match = _re.search(r'"verdict"\s*:\s*"([^"]*)"', raw_output or "")
        verdict = verdict_match.group(1) if verdict_match else "PARSE_ERROR"
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        reasoning = ""
        verdict = "ERROR"
        signal = ""
        confidence = 0.0
        error = str(exc)
        log.exception("unified-binary failed for %s: %s", student_id, exc)

    return {
        "codepath": "test_harness_unified_suite_v2",
        "classifier_variant": variant_key,
        "format": "binary",
        "scope": scope,
        "supersedes_state": supersedes_state,
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": system,
        "raw_output": raw_output,
        "reasoning": reasoning,
        "verdict": verdict,
        "axis": None,
        "observation": None,
        "signal": signal,
        "confidence": confidence,
        "time_seconds": elapsed,
        "error": error,
    }


def run_one_unified_4axis(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
    supersedes_state: str,
) -> dict:
    """Unified 4-axis classifier v2: production WELLBEING_CLASSIFIER_SYSTEM
    substrate (tiebreaker removed), 4-axis output (CRISIS|BURNOUT|ENGAGED|NONE),
    reasoning field. Supersedes and single-sentence blocks appended per supersedes_state.

    supersedes_state: 'both' | 'single' | 'neither'
    Dispatched with functools.partial(run_one_unified_4axis, supersedes_state=...).
    """
    import re as _re

    system = _assemble_system(
        UNIFIED_4AXIS_BASE_SYSTEM,
        UNIFIED_4AXIS_SUPERSEDES_BLOCK,
        UNIFIED_4AXIS_SINGLE_SENTENCE_BLOCK,
        supersedes_state,
    )
    variant_key = f"unified-4axis-{supersedes_state}"

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix="",
        assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            system,
            max_tokens=REASONING_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        reasoning_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', raw_output or "")
        signal = signal_match.group(1) if signal_match else ""
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        reasoning = ""
        axis = "ERROR"
        signal = ""
        confidence = 0.0
        error = str(exc)
        log.exception("unified-4axis failed for %s: %s", student_id, exc)

    return {
        "codepath": "test_harness_unified_suite_v2",
        "classifier_variant": variant_key,
        "format": "4axis",
        "scope": None,
        "supersedes_state": supersedes_state,
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": system,
        "raw_output": raw_output,
        "reasoning": reasoning,
        "verdict": None,
        "axis": axis,
        "observation": None,
        "signal": signal,
        "confidence": confidence,
        "time_seconds": elapsed,
        "error": error,
    }


def run_one_unified_genob(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
    supersedes_state: str,
) -> dict:
    """Unified generative-observation variant v2: workshop genob substrate,
    prose observation output (no classification verdict).
    confidence semantics: accuracy of characterization, NOT concern probability.
    max_tokens=UNIFIED_GENOB_MAX_TOKENS (550) to fit reasoning + 3-4 sentence prose.

    supersedes_state: 'both' | 'single' | 'neither'
    Dispatched with functools.partial(run_one_unified_genob, supersedes_state=...).
    """
    import re as _re

    system = _assemble_system(
        UNIFIED_GENOB_BASE_SYSTEM,
        UNIFIED_GENOB_SUPERSEDES_BLOCK,
        UNIFIED_GENOB_SINGLE_SENTENCE_BLOCK,
        supersedes_state,
    )
    variant_key = f"unified-genob-{supersedes_state}"

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix="",
        assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            system,
            max_tokens=UNIFIED_GENOB_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        reasoning_match = (
            _re.search(r'"scratchpad"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
            or _re.search(r'"reasoning"\s*:\s*"([^"]*)"', raw_output or "")
        )
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        # Output field name varies across format tests. Try each in order so
        # old outputs remain parseable.
        obs_match = (
            _re.search(r'"thoughtful_observation"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
            or _re.search(r'"shared_in_faculty_lounge"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
            or _re.search(r'"whispered_to_colleague_in_hall"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
            or _re.search(r'"thinking_aloud"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
            or _re.search(r'"observation"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output or "")
        )
        observation = obs_match.group(1) if obs_match else ""
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
        confidence = float(conf_match.group(1)) if conf_match else 0.0
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        reasoning = ""
        observation = ""
        confidence = 0.0
        error = str(exc)
        log.exception("unified-genob failed for %s: %s", student_id, exc)

    return {
        "codepath": "test_harness_unified_suite_v2",
        "classifier_variant": variant_key,
        "format": "genob",
        "scope": None,
        "supersedes_state": supersedes_state,
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": system,
        "raw_output": raw_output,
        "reasoning": reasoning,
        "verdict": None,
        "axis": None,
        "observation": observation,
        "signal": None,
        "confidence": confidence,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Per-variant driver
# ---------------------------------------------------------------------------

def run_variant(
    variant: str,
    *,
    backend: BackendConfig,
    es_corpus: list[dict],
    wb_cases: list[dict],
    model_key: str,
    n_runs: int,
    smoke: bool,
) -> Path:
    """Run ONE classifier variant across the full corpus, save its JSON."""
    if variant == "single-pass":
        run_one = run_one_single_pass
    elif variant == "two-pass":
        run_one = run_one_two_pass
    elif variant == "reasoning":
        run_one = run_one_reasoning_pass
    elif variant == "reasoning-two-pass":
        run_one = run_one_reasoning_two_pass
    elif variant == "binary-reasoning":
        run_one = run_one_binary_reasoning_pass
    elif variant == "binary-no-tiebreaker":
        run_one = run_one_binary_no_tiebreaker_pass
    # Unified format-comparison suite v2
    elif variant == "unified-binary-narrow-both":
        run_one = functools.partial(run_one_unified_binary, scope="narrow", supersedes_state="both")
    elif variant == "unified-binary-narrow-single":
        run_one = functools.partial(run_one_unified_binary, scope="narrow", supersedes_state="single")
    elif variant == "unified-binary-narrow-neither":
        run_one = functools.partial(run_one_unified_binary, scope="narrow", supersedes_state="neither")
    elif variant == "unified-binary-broad-both":
        run_one = functools.partial(run_one_unified_binary, scope="broad", supersedes_state="both")
    elif variant == "unified-binary-broad-single":
        run_one = functools.partial(run_one_unified_binary, scope="broad", supersedes_state="single")
    elif variant == "unified-binary-broad-neither":
        run_one = functools.partial(run_one_unified_binary, scope="broad", supersedes_state="neither")
    elif variant == "unified-4axis-both":
        run_one = functools.partial(run_one_unified_4axis, supersedes_state="both")
    elif variant == "unified-4axis-single":
        run_one = functools.partial(run_one_unified_4axis, supersedes_state="single")
    elif variant == "unified-4axis-neither":
        run_one = functools.partial(run_one_unified_4axis, supersedes_state="neither")
    elif variant == "unified-genob-both":
        run_one = functools.partial(run_one_unified_genob, supersedes_state="both")
    elif variant == "unified-genob-single":
        run_one = functools.partial(run_one_unified_genob, supersedes_state="single")
    elif variant == "unified-genob-neither":
        run_one = functools.partial(run_one_unified_genob, supersedes_state="neither")
    else:
        raise ValueError(f"Unknown variant: {variant}")

    # Unified variants use format-native output fields (verdict/axis/observation)
    # rather than actual_axis. Flag this so the progress print loop below can
    # display something sensible without crashing.
    _is_unified = variant.startswith("unified-")

    print(f"\n{'=' * 70}")
    print(f"  4-AXIS FULL-CORPUS TEST — VARIANT: {variant.upper()}  "
          f"({'SMOKE' if smoke else 'FULL'})")
    print(f"  Model: {model_key}  |  Runs per student: {n_runs}")
    if variant == "single-pass":
        print(f"  Classifier: Test N inline prompts via "
              f"insights.llm_backend.send_text")
    elif variant in ("reasoning", "reasoning-two-pass"):
        print(f"  Classifier: FOUR_AXIS_REASONING_SYSTEM (reasoning field, "
              f"max_tokens={REASONING_PASS_MAX_TOKENS})"
              + (" + prescan pass 0" if variant == "reasoning-two-pass" else ""))
    elif variant == "binary-reasoning":
        print(f"  Classifier: BINARY_REASONING_SYSTEM (WELLBEING_CLASSIFIER_SYSTEM "
              f"+ reasoning field, max_tokens={REASONING_PASS_MAX_TOKENS}, no prescan)")
    elif variant == "binary-no-tiebreaker":
        print(f"  Classifier: BINARY_NO_TIEBREAKER_SYSTEM (WELLBEING_CLASSIFIER_SYSTEM "
              f"minus tiebreaker paragraph, original schema, max_tokens={REASONING_PASS_MAX_TOKENS})")
    else:
        print(f"  Classifier: insights.submission_coder.classify_wellbeing")
    print(f"{'=' * 70}\n")

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    variant_slug = variant.replace("-", "_")
    suffix = "_SMOKE" if smoke else ""
    partial_path = OUTPUT_DIR / f"test_4axis_{variant_slug}_FULL_CORPUS_{model_key}_{ts}{suffix}.partial.json"

    results: list = []
    total_students = len(es_corpus) + len(wb_cases)
    total_runs = total_students * n_runs
    print(f"  ES students: {len(es_corpus)}  |  WB cases: {len(wb_cases)}  "
          f"|  Total LLM sessions ({variant}): {total_runs}\n")

    call_idx = 0

    # Pass-first loop order: complete each pass over both corpuses before
    # moving to the next. This lets us checkpoint after each complete pass
    # rather than waiting until all ES passes then all WB passes finish.
    for run_idx in range(1, n_runs + 1):
        print(f"  --- Run {run_idx}/{n_runs} (ethnic_studies, {variant}) ---")
        for student in es_corpus:
            call_idx += 1
            sid = student["student_id"]
            name = student["student_name"]
            text = student["text"]
            pattern = student.get("pattern")
            rec = run_one(
                backend,
                student_id=sid,
                student_name=name,
                submission_text=text,
                source="ethnic_studies",
                expected_axis=None,
                pattern=pattern,
                signal_type=None,
                run_idx=run_idx,
            )
            results.append(rec)
            if _is_unified:
                # Unified variants use verdict/axis/observation, not actual_axis.
                _displayed = (
                    rec.get("verdict") or rec.get("axis") or
                    (rec.get("observation") or "")[:30] or "N/A"
                )
            else:
                _displayed = rec['actual_axis']
            print(
                f"    [{call_idx:4d}/{total_runs}] {sid} {name:24s} "
                f"axis={_displayed:8s} conf={rec['confidence']:.2f} "
                f"({rec['time_seconds']}s)"
                + (f"  ERROR: {rec['error']}" if rec['error'] else "")
            )
            if rec.get("reasoning"):
                print(f"      reasoning: {rec['reasoning'][:120]}")

        print(f"\n  --- Run {run_idx}/{n_runs} (wellbeing_synthetic, {variant}) ---")
        for case in wb_cases:
            call_idx += 1
            expected = expected_axis_for_wb_case(case)
            rec = run_one(
                backend,
                student_id=case["id"],
                student_name=case["name"],
                submission_text=case["text"],
                source="wellbeing_synthetic",
                expected_axis=expected,
                pattern=None,
                signal_type=case["signal_type"],
                run_idx=run_idx,
            )
            results.append(rec)
            if _is_unified:
                _displayed = (
                    rec.get("verdict") or rec.get("axis") or
                    (rec.get("observation") or "")[:30] or "N/A"
                )
                _correct_str = "N/A"
            else:
                _displayed = rec['actual_axis']
                _correct_str = rec['correct']
            print(
                f"    [{call_idx:4d}/{total_runs}] {case['id']:5s} "
                f"{case['name']:22s} {case['signal_type']:30s} "
                f"expect={expected:8s} got={_displayed:8s} "
                f"conf={rec['confidence']:.2f} [{_correct_str}] "
                f"({rec['time_seconds']}s)"
                + (f"  ERROR: {rec['error']}" if rec['error'] else "")
            )

        # Checkpoint after each complete pass (skip for smoke — 1-2 students, trivial to rerun).
        if not smoke:
            partial_path.write_text(json.dumps({
                "variant": variant,
                "model": model_key,
                "passes_complete": run_idx,
                "n_runs": n_runs,
                "results_so_far": results,
            }, indent=2))
            print(f"\n  >> Checkpoint written after pass {run_idx}/{n_runs}: {partial_path.name}")

    path = save_results(
        results,
        variant=variant,
        model_key=model_key,
        n_runs=n_runs,
        smoke=smoke,
        es_count=len(es_corpus),
        wb_count=len(wb_cases),
        timestamp=ts,
    )
    if partial_path.exists():
        partial_path.unlink()
        print(f"  Partial checkpoint removed (run complete): {partial_path.name}")
    print(f"\n  Results saved ({variant}): {path}")

    # Quick summary: WB hit rate per case across runs.
    print(f"\n  WB summary ({variant}, axis match across runs):")
    wb_results = [r for r in results if r["source"] == "wellbeing_synthetic"]
    by_case: dict[str, list[dict]] = {}
    for r in wb_results:
        by_case.setdefault(r["student_id"], []).append(r)
    for cid in sorted(by_case):
        recs = by_case[cid]
        expected = recs[0]["expected_axis"]
        if _is_unified:
            # Unified variants don't have actual_axis; show format-native field.
            matches_str = "N/A (genob prose)" if recs[0].get("format") == "genob" else (
                f"{sum(1 for r in recs if (r.get('verdict') or r.get('axis')) == expected)}"
                f"/{len(recs)}"
            )
        else:
            matches = sum(1 for r in recs if r["actual_axis"] == expected)
            matches_str = f"{matches}/{len(recs)}"
        name = recs[0]["student_name"]
        st = recs[0]["signal_type"]
        print(
            f"    {cid} {name:22s} {st:30s} "
            f"expect={expected:8s}  match={matches_str}"
        )

    # ES corpus axis / output distribution.
    print(f"\n  ES distribution ({variant}, "
          f"n={len(es_corpus)} students x {n_runs} runs):")
    es_results = [r for r in results if r["source"] == "ethnic_studies"]
    from collections import Counter
    if _is_unified:
        _fmt = es_results[0].get("format") if es_results else "unknown"
        if _fmt == "binary":
            dist = Counter(r.get("verdict", "N/A") for r in es_results)
        elif _fmt == "4axis":
            dist = Counter(r.get("axis", "N/A") for r in es_results)
        else:
            dist = Counter("PROSE" for _ in es_results)
    else:
        dist = Counter(r["actual_axis"] for r in es_results)
    for label, count in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"    {label:12s} {count}")

    return path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_WHITE_CODED_NAME_MAP = {
    "WB04": "Emily Anderson",
    "WB07": "Sarah O'Brien",
    "WB08": "Brad Whitmore",
}


def run_full(model_key: str, n_runs: int, smoke: bool, variant: str,
             student_ids: set | None = None,
             anonymize: bool = False,
             invert_names: bool = False,
             text_swaps: list[tuple[str, str]] | None = None) -> list[Path]:
    backend = get_backend(model_key)
    backend = replace(backend, temperature=MODELS[model_key]["temperature"])

    es_corpus = load_es_corpus()
    wb_cases = list(WELLBEING_SIGNAL_CASES)

    if smoke:
        es_corpus = es_corpus[:1]
        wb_cases = wb_cases[:1]
        n_runs = 1

    if student_ids:
        es_corpus = [s for s in es_corpus if s["student_id"] in student_ids]
        wb_cases = [c for c in wb_cases if c["id"] in student_ids]

    if anonymize:
        es_corpus = [
            {**s, "student_name": f"Student {chr(65+i)}"}
            for i, s in enumerate(es_corpus)
        ]
        wb_cases = [
            {**c, "name": f"Student {chr(65+i+len(es_corpus))}"}
            for i, c in enumerate(wb_cases)
        ]
        print(f"  [ANONYMIZED] {len(wb_cases)+len(es_corpus)} students renamed to Student A/B/C/...")

    if invert_names:
        wb_cases = [
            {**c, "name": _WHITE_CODED_NAME_MAP.get(c["id"], c["name"])}
            for c in wb_cases
        ]
        renamed = [(c["id"], c["name"]) for c in wb_cases if c["id"] in _WHITE_CODED_NAME_MAP]
        print(f"  [NAME INVERSION] Renamed {len(renamed)} students to white-coded names: {renamed}")

    if text_swaps:
        def _apply_swaps(t):
            for old, new in text_swaps:
                t = t.replace(old, new)
            return t
        wb_cases = [{**c, "text": _apply_swaps(c["text"])} for c in wb_cases]
        es_corpus = [{**s, "text": _apply_swaps(s["text"])} for s in es_corpus]
        print(f"  [TEXT SWAPS] Applied {len(text_swaps)} substitution(s): {text_swaps}")

    if variant == "both":
        variants_to_run = ["single-pass", "two-pass"]
    elif variant == "unified-all":
        # Run all 12 unified v2 variants in the spec-specified order
        # (unified_substrates_workshop_output.md, variant matrix):
        # binary-narrow-both → binary-narrow-single → binary-narrow-neither →
        # binary-broad-both  → binary-broad-single  → binary-broad-neither  →
        # 4axis-both → 4axis-single → 4axis-neither →
        # genob-both → genob-single → genob-neither
        variants_to_run = [
            "unified-binary-narrow-both",   "unified-binary-narrow-single",   "unified-binary-narrow-neither",
            "unified-binary-broad-both",    "unified-binary-broad-single",    "unified-binary-broad-neither",
            "unified-4axis-both",           "unified-4axis-single",           "unified-4axis-neither",
            "unified-genob-both",           "unified-genob-single",           "unified-genob-neither",
        ]
    elif variant == "unified-trio":
        # One representative per format family. Use this for smoke testing and
        # initial full-corpus passes before committing to all 12 variants.
        # Loads the model once — safer than running three separate processes.
        variants_to_run = [
            "unified-binary-narrow-both",
            "unified-4axis-both",
            "unified-genob-both",
        ]
    else:
        variants_to_run = [variant]

    paths: list[Path] = []
    for v in variants_to_run:
        path = run_variant(
            v,
            backend=backend,
            es_corpus=es_corpus,
            wb_cases=wb_cases,
            model_key=model_key,
            n_runs=n_runs,
            smoke=smoke,
        )
        paths.append(path)

    print(f"\n{'=' * 70}")
    print(f"  ALL VARIANTS COMPLETE")
    for p in paths:
        print(f"    {p}")
    print(f"{'=' * 70}\n")
    return paths


def _metal_warmup(model_key: str = "gemma12b") -> None:
    """Fire a short inference to initialize Metal before the main run.

    Prevents Metal kernel-compilation stalls on cold starts (especially after
    display sleep). Skipped in smoke mode — smoke runs are short enough that
    warmup adds proportionally too much overhead.
    """
    print("\n  [Metal warmup] Initializing GPU...")
    t0 = time.time()
    try:
        backend = get_backend(model_key)
        backend = replace(backend, temperature=0.1, max_tokens=8)
        send_text(backend, "Hi", "You are a test.")
        # Do NOT unload here — leave model cached so first real inference
        # reuses it directly.
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)\n")
    except Exception as e:  # noqa: BLE001
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run 4-axis wellbeing classifier on the full 32 ES + "
                    "14 WB combined corpus. Supports single-pass (Test N "
                    "inline prompts), two-pass (production "
                    "classify_wellbeing), or both."
    )
    parser.add_argument(
        "--variant",
        choices=list(VARIANT_CHOICES),
        default="both",
        help="Classifier variant to run. 'single-pass' = Test N inline "
             "prompts; 'two-pass' = production classify_wellbeing; "
             "'both' = run single-pass then two-pass sequentially "
             "and write two separate JSON files. Default: both.",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Smoke-test: 1 ES student + 1 WB case, 1 run each, per variant.",
    )
    parser.add_argument(
        "--model", default="gemma12b",
        choices=list(MODELS.keys()),
        help="Model key. Default: gemma12b.",
    )
    parser.add_argument(
        "--n-runs", type=int, default=5,
        help="Runs per student for the full run (ignored under --smoke). "
             "Default: 5.",
    )
    parser.add_argument(
        "--student-ids", type=str, default=None,
        help="Comma-separated student IDs to run (e.g. WB04,WB07,WB08,WB14). "
             "Default: all students.",
    )
    parser.add_argument(
        "--anonymize", action="store_true",
        help="Replace all student names with 'Student A/B/C/...' to test "
             "whether racialized name signals drive model behavior.",
    )
    parser.add_argument(
        "--invert-names", action="store_true",
        help="Replace WB04/WB07/WB08 with white-coded names (Emily Anderson, "
             "Sarah O'Brien, Brad Whitmore). For inversion test of racialized "
             "differential naming.",
    )
    parser.add_argument(
        "--text-swap", action="append", default=[],
        help="Apply a text substitution to all student submissions before passing "
             "to the model. Format: 'old phrase=>new phrase'. Can be repeated.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        # Always warm up — smoke runs still hit cold Metal on first inference.
        # Skipping warmup for smoke was a premature optimization that caused
        # Metal kernel-compilation stalls (and on 16 GB machines, system freezes).
        student_ids = (
            set(s.strip() for s in args.student_ids.split(",") if s.strip())
            if args.student_ids else None
        )
        text_swaps = []
        for swap in args.text_swap:
            if "=>" in swap:
                old, new = swap.split("=>", 1)
                text_swaps.append((old, new))
        _metal_warmup(args.model)
        run_full(
            model_key=args.model,
            n_runs=args.n_runs,
            smoke=args.smoke,
            variant=args.variant,
            student_ids=student_ids,
            anonymize=args.anonymize,
            invert_names=args.invert_names,
            text_swaps=text_swaps,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    except Exception as exc:  # noqa: BLE001
        log.exception("Run failed: %s", exc)
        return 2
    finally:
        try:
            unload_mlx_model()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
