"""
Binary concern detector — research apparatus only.

Runs a single LLM call per submission and returns a list of ConcernRecord
objects (or empty list). Two scopes are supported via the `scope` parameter:

  - "combined" (default): wellbeing concerns + power-moves language
    (essentializing, colorblind ideology, savior narrative, etc.)
  - "wellbeing": wellbeing only — scope-matched to Track B's 4-axis
    classifier so the binary-vs-4-axis comparison isolates format from scope

Both scopes share the same equity-hardening machinery: course-content vs.
student-wellbeing distinction, the long Do-NOT-flag list, anti-tone-policing
post-processing regex, course-content-flag detection regex, and a 0.7
confidence threshold.

Anti-bias post-processing checks LLM output for bias markers
("aggressive", "emotional", "too angry") — if found alongside structural
critique, the rationale is rewritten with a "⚠ POSSIBLE MODEL BIAS" prefix
and confidence is lowered. Course-content flagging language ("triggering",
"discusses violence") triggers a similar "⚠ LIKELY COURSE CONTENT" rewrite.

This module is research-only and does not affect the production pipeline,
which uses the 4-axis wellbeing classifier (Track B) instead.
"""

import logging
import re
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import ConcernRecord, ConcernSignal
from insights.patterns import CRITICAL_KEYWORDS, has_critical_keywords
from insights.prompts import JSON_REPAIR_PROMPT, SYSTEM_PROMPT
from research.prompts import (
    CONCERN_CRITIC_PROMPT,
    CONCERN_IMMANENT_CRITIQUE_ADDENDUM,
    CONCERN_PROMPT,
    WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER,
    WELLBEING_CONCERN_PROMPT,
)

log = logging.getLogger(__name__)

# Bias markers in LLM output that suggest tone policing
_BIAS_MARKERS = re.compile(
    r"\b(aggressive|too emotional|overly emotional|hostile tone|"
    r"angry rhetoric|threatening|confrontational|too angry|"
    r"irrational|hysterical)\b",
    re.IGNORECASE,
)


def _format_signal_matrix_for_prompt(signals: List[ConcernSignal]) -> str:
    """Format signal matrix results for the concern prompt."""
    if not signals:
        return "No non-LLM concern signals for this submission."
    lines = []
    for sig in signals:
        lines.append(
            f"- {sig.signal_type}: {sig.interpretation} "
            f"(category: {sig.keyword_category}, VADER: {sig.vader_polarity})"
        )
        if sig.matched_text:
            lines.append(f'  Matched text: "{sig.matched_text}"')
    return "\n".join(lines)


def _format_signal_matrix_tuples(signals: list) -> str:
    """Format raw signal matrix tuples for the concern prompt.

    Filters out APPROPRIATE signals to avoid confusing smaller models
    into analyzing strengths as concerns.
    """
    if not signals:
        return "No non-LLM concern signals for this submission."
    lines = []
    for sig in signals:
        if isinstance(sig, tuple) and len(sig) >= 4:
            if sig[0] == "APPROPRIATE":
                continue
            lines.append(f"- {sig[0]}: {sig[3]} (category: {sig[1]}, VADER: {sig[2]})")
        elif hasattr(sig, "signal_type"):
            if sig.signal_type == "APPROPRIATE":
                continue
            lines.append(f"- {sig.signal_type}: {sig.interpretation}")
    return "\n".join(lines) if lines else "No non-LLM concern signals for this submission."


# Phrases that indicate the LLM is flagging course content, not student wellbeing
_CONTENT_FLAG_MARKERS = re.compile(
    r"\b(triggering|disturbing content|graphic|violent content|"
    r"may be triggering|this passage may|difficult material|"
    r"sensitive (content|material|topic)|mature content|"
    r"content warning|distressing (content|material)|"
    r"indication of distress)\b",
    re.IGNORECASE,
)

# Phrases that indicate the model returned an entry in concerns[] that is
# actually a non-concern annotation. Some smaller models (observed: Gemma 3
# 12B) misuse the JSON schema by putting positive reflections into
# concerns[] with why_flagged="No concerns" and confidence 1.0. Drop these
# at parse time; they are model-schema-misuse, not concerns the
# equity machinery should be analyzing.
_NON_CONCERN_DENIALS = re.compile(
    r"\b(no concerns?|not a concern|no concern (is |was )?(found|present|raised)|"
    r"not (a )?wellbeing concern|no wellbeing concern)\b",
    re.IGNORECASE,
)

# Phrases in why_flagged that suggest the model is concerned about subject
# matter rather than the student's personal state
_SUBJECT_MATTER_EXPLANATIONS = re.compile(
    r"\b(discusses? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"mentions? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"references? (to )?(rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"describes? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"course (content|material) .{0,30}(difficult|heavy|disturbing|graphic))\b",
    re.IGNORECASE,
)


def _check_bias_in_output(concerns: List[ConcernRecord], submission_text: str) -> List[ConcernRecord]:
    """Anti-bias post-processing: check LLM concern output for bias markers.

    If the LLM's 'why_flagged' uses tone-policing language AND the flagged
    passage contains structural critique keywords, add a warning.

    Also checks for the model confusing course content with student distress:
    if the model flags a passage because the SUBJECT MATTER is disturbing
    (not because the STUDENT is in distress), demote the flag.
    """
    checked = []
    for concern in concerns:
        # Check if the LLM used biased language in its explanation
        if _BIAS_MARKERS.search(concern.why_flagged):
            # Check if the flagged passage contains structural critique
            if has_critical_keywords(concern.flagged_passage) or has_critical_keywords(submission_text):
                concern.why_flagged = (
                    f"\u26a0 POSSIBLE MODEL BIAS: The model characterized this "
                    f"student's tone negatively. The passage appears to contain "
                    f"structural critique, which is appropriate academic "
                    f"engagement, not a concern. Original model assessment: "
                    f"{concern.why_flagged}"
                )
                concern.confidence = max(0.1, concern.confidence - 0.3)

        # Check if the model is flagging course CONTENT rather than student
        # WELLBEING — e.g., "this passage discusses rape" or "may be triggering"
        why = concern.why_flagged
        if (_CONTENT_FLAG_MARKERS.search(why)
                or _SUBJECT_MATTER_EXPLANATIONS.search(why)):
            # The model appears to be concerned about the subject matter,
            # not the student's personal state. Demote significantly.
            concern.why_flagged = (
                f"\u26a0 LIKELY COURSE CONTENT (not student distress): The model "
                f"flagged this because the subject matter is disturbing, not "
                f"because the student appears to be in personal crisis. "
                f"Original model assessment: {why}"
            )
            concern.confidence = max(0.1, concern.confidence - 0.4)

        checked.append(concern)
    return checked


def detect_concerns(
    *,
    submission_text: str,
    student_name: str,
    student_id: str,
    assignment_prompt: str,
    signal_matrix_results: list,
    concern_signals: Optional[List[ConcernSignal]] = None,
    tier: str,
    backend: Optional[BackendConfig],
    profile_fragment: str = "",
    class_context: str = "",
    scope: str = "combined",
) -> List[ConcernRecord]:
    """Run dedicated concern detection on one submission.

    Parameters
    ----------
    scope : "combined" | "wellbeing"
        Which prompt to use. "combined" (default) flags both wellbeing
        concerns and power-moves language (essentializing, colorblind, etc.) —
        the historical scope. "wellbeing" flags wellbeing only, scope-matched
        to Track B's 4-axis classifier.

    If no LLM backend is available, returns signal matrix results as
    low-confidence concern flags (non-LLM fallback).
    """
    if scope not in ("combined", "wellbeing", "wellbeing_no_tiebreaker"):
        raise ValueError(
            f"Unknown scope: {scope!r}; expected 'combined', 'wellbeing', "
            f"or 'wellbeing_no_tiebreaker'"
        )
    # Format signal matrix context — only pass actual concern signals,
    # not APPROPRIATE signals which confuse smaller models into flagging strengths
    if concern_signals:
        actual_concerns = [s for s in concern_signals
                           if s.signal_type not in ("APPROPRIATE",)]
        signal_text = (_format_signal_matrix_for_prompt(actual_concerns)
                       if actual_concerns
                       else "No non-LLM concern signals for this submission.")
    else:
        signal_text = _format_signal_matrix_tuples(signal_matrix_results)

    # Non-LLM fallback: return signal matrix results as low-confidence flags
    if backend is None:
        return _signal_matrix_fallback(
            concern_signals or [],
            signal_matrix_results,
            student_id,
            student_name,
            submission_text,
        )

    # LLM concern detection
    # Class context makes relational harms visible (tone policing, etc.)
    class_context_block = (
        f"\nCLASS CONTEXT (from reading all submissions as a community):\n"
        f"---\n{class_context}\n---\n"
        if class_context
        else ""
    )
    if scope == "combined":
        prompt_template = CONCERN_PROMPT
    elif scope == "wellbeing":
        prompt_template = WELLBEING_CONCERN_PROMPT
    else:
        prompt_template = WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER
    prompt = prompt_template.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        class_context=class_context_block,
        signal_matrix_result=signal_text,
        submission_text=submission_text,
        profile_fragment=profile_fragment,
    ) + CONCERN_IMMANENT_CRITIQUE_ADDENDUM

    # Cap response length — 4096 default lets small models ramble and
    # generate false positives by analyzing strengths as concerns
    raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
    parsed = parse_json_response(raw)

    if "_parse_error" in parsed:
        # Retry once
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:1500],
            expected_format='{"concerns": [{"flagged_passage": "...", ...}]}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT, max_tokens=800)
        parsed = parse_json_response(raw)

    # Build ConcernRecords from LLM response
    concerns = []
    for item in parsed.get("concerns", []):
        if not isinstance(item, dict):
            continue
        passage = item.get("flagged_passage", "")
        if not passage:
            continue
        why = item.get("why_flagged", "")
        # Schema-misuse guard: some models put positive reflections into
        # concerns[] with why_flagged="No concerns" at confidence 1.0.
        # These are not concerns; drop before building the record.
        if _NON_CONCERN_DENIALS.search(why):
            log.debug("Dropping non-concern denial entry: %r", why[:100])
            continue
        concerns.append(ConcernRecord(
            flagged_passage=passage,
            surrounding_context=item.get("surrounding_context", ""),
            why_flagged=why,
            confidence=float(item.get("confidence", 0.5)),
        ))

    # Anti-bias post-processing
    concerns = _check_bias_in_output(concerns, submission_text)

    # Drop low-confidence flags to reduce noise in teacher's view
    concerns = [c for c in concerns if c.confidence >= 0.7]

    # TODO: Adversarial critic pass — argue AGAINST each surviving flag.
    # Prompt is written (CONCERN_CRITIC_PROMPT in prompts.py).
    # Waiting on replication study frequency data before wiring in.
    # See docs/research/hidden_ideas_tracker.md

    return concerns


def _signal_matrix_fallback(
    concern_signals: List[ConcernSignal],
    signal_matrix_results: list,
    student_id: str,
    student_name: str,
    submission_text: str,
) -> List[ConcernRecord]:
    """Convert non-LLM signal matrix results to low-confidence ConcernRecords.

    Used when no LLM backend is available.
    """
    concerns = []

    # From ConcernSignal objects
    for sig in concern_signals:
        if sig.student_id != student_id:
            continue
        if sig.signal_type in ("APPROPRIATE",):
            continue  # Not a concern
        concerns.append(ConcernRecord(
            flagged_passage=sig.matched_text or "",
            surrounding_context="",
            why_flagged=f"Non-LLM signal: {sig.interpretation}",
            confidence=0.3,  # Low confidence — no LLM verification
        ))

    # From raw signal matrix tuples
    for sig in signal_matrix_results:
        if isinstance(sig, tuple) and len(sig) >= 4:
            signal_type, category, polarity, interpretation = sig
            if signal_type in ("APPROPRIATE",):
                continue
            concerns.append(ConcernRecord(
                flagged_passage="",
                surrounding_context="",
                why_flagged=f"Non-LLM signal ({category}): {interpretation}",
                confidence=0.3,
            ))

    return concerns
