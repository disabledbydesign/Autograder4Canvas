"""
Per-submission LLM coding for the Insights Engine.

Tier logic:
  Lightweight: 2 calls (comprehension -> interpretation) per submission
  Medium: 1 combined call per submission
  Deep: 1 full call per submission

Wellbeing classification (4-axis) runs as a separate stage on raw submissions.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    PerSubmissionSummary,
    QuoteRecord,
    SubmissionCodingRecord,
)
from insights.patterns import assess_sentiment_reliability, classify_vader_polarity
from insights.prompts import (
    ANALYSIS_LENS_PROMPT_FRAGMENT,
    CODING_FULL_PROMPT,
    CODING_READING_FIRST_P1,
    CODING_READING_FIRST_P2,
    COMPREHENSION_PROMPT,
    DEEPENING_PROMPT,
    INTEREST_AREAS_FRAGMENT,
    INTERPRETATION_PROMPT,
    JSON_REPAIR_PROMPT,
    SYSTEM_PROMPT,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM output schema for constrained generation (Ollama format parameter)
# ---------------------------------------------------------------------------

class _QuoteOutput(BaseModel):
    """Quote sub-object as the LLM generates it."""
    text: str
    significance: str = ""


class _CodingOutput(BaseModel):
    """Schema for the fields the LLM produces in the coding pass.

    Intentionally narrower than SubmissionCodingRecord — excludes internal
    fields (student_id, engagement_signals, submitted_at, etc.) that are
    set programmatically, not by the model.

    Passed as response_schema to send_text() for constrained generation:
    Ollama uses GBNF grammar, MLX uses Outlines FSM (when installed).
    Enforces float values for theme_confidence and correct object shapes
    for notable_quotes — output is valid JSON by construction.
    """
    student_name: str = ""
    theme_tags: List[str] = []
    theme_confidence: Dict[str, float] = {}
    what_student_is_reaching_for: Optional[str] = None
    notable_quotes: List[_QuoteOutput] = []
    emotional_register: str = ""
    emotional_notes: str = ""
    readings_referenced: List[str] = []
    concepts_applied: List[str] = []
    personal_connections: List[str] = []
    current_events_referenced: List[str] = []
    confusion_or_questions: Optional[str] = None
    lens_observations: Optional[Dict[str, str]] = None


def _coerce_str(val, default: str = "") -> str:
    """Coerce a value to string — handles lists from LLM JSON output."""
    if val is None:
        return default
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


def _safe_list(val: Any, default: Optional[list] = None) -> list:
    """Coerce a value to List[str], tolerating a bare string from LLM output.

    The LLM occasionally returns a plain string instead of a list (e.g.
    personal_connections: "connects to chapter 3" rather than [...]).
    Pydantic raises ValidationError on the wrong type, which degrades the
    student to a fallback record.  This helper wraps the bare string in a
    list so the field stays populated rather than falling back.
    """
    if default is None:
        default = []
    if val is None:
        return default
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val] if val.strip() else default
    return default


def _safe_theme_confidence(raw: Any) -> dict:
    """Coerce theme_confidence to Dict[str, float], tolerating string values.

    The LLM (especially in repair responses) sometimes returns string values
    like "high", "0.8", or "very confident" instead of floats.  Pydantic
    raises ValidationError for non-float-coercible strings, which kills the
    whole assignment run.  This helper converts each value:
      - numeric strings ("0.8") → float
      - qualitative strings ("high") → mapped to a float (0.8, etc.)
      - anything else → 0.5 fallback
    """
    _QUAL_MAP = {
        "very high": 0.9, "high": 0.8, "medium-high": 0.7,
        "medium": 0.6, "moderate": 0.6, "low-medium": 0.5,
        "low": 0.4, "very low": 0.2,
    }
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, (int, float)):
            out[str(k)] = float(v)
        elif isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in _QUAL_MAP:
                out[str(k)] = _QUAL_MAP[v_lower]
            else:
                try:
                    out[str(k)] = float(v_lower)
                except ValueError:
                    out[str(k)] = 0.5  # unknown string → neutral confidence
        else:
            out[str(k)] = 0.5
    return out


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list:
    """Split text into overlapping chunks, preferring paragraph boundaries.

    Break priority: paragraph (\n\n) > sentence (. ! ?) > hard cut.
    Paragraphs are the natural unit of student thought — splitting
    mid-paragraph risks severing an argument the student is building.

    Returns a list of chunks. Short text (≤ chunk_size) returns a single-element list.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Search the last ~500 chars of the chunk for a break point
        search_start = max(start, end - 500)
        search_region = text[search_start:end]

        # Priority 1: paragraph break (double newline)
        para_idx = search_region.rfind("\n\n")
        if para_idx >= 0:
            end = search_start + para_idx + 2  # include the break
        else:
            # Priority 2: sentence boundary
            best_sent = -1
            for marker in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                idx = search_region.rfind(marker)
                if idx > best_sent:
                    best_sent = idx
            if best_sent >= 0:
                end = search_start + best_sent + 2
            # else: hard cut at chunk_size (no good break found)

        chunks.append(text[start:end])
        # Overlap from the break point so the next chunk has context
        start = max(start + 1, end - overlap)

    return chunks


# Wellbeing pre-scan constants
_PRESCAN_CHUNK_SIZE = 3000   # chars per chunk — covers ~600 words
_CLASSIFIER_MAX_INPUT = 4000  # max chars passed to 4-axis classifier


def _prescan_for_personal_signals(
    backend: BackendConfig,
    text: str,
    *,
    max_tokens: int = 120,
) -> list[str]:
    """Scan all chunks for sentences describing the student's personal circumstances.

    Uses LLM semantic understanding rather than keywords — avoids false positives
    on students discussing poverty/violence/crisis as course material.

    Returns a list of found sentences (often empty). Each item is a quoted
    sentence from the student's text.
    """
    from insights.prompts import WELLBEING_PRESCAN_SYSTEM, WELLBEING_PRESCAN_PROMPT

    chunks = _chunk_text(text, _PRESCAN_CHUNK_SIZE, overlap=200)
    found = []
    for chunk in chunks:
        try:
            raw = send_text(
                backend,
                WELLBEING_PRESCAN_PROMPT.format(text=chunk),
                WELLBEING_PRESCAN_SYSTEM,
                max_tokens=max_tokens,
            ).strip()
            if raw.upper() != "NO" and raw:
                found.append(raw)
        except Exception as exc:
            log.warning("Wellbeing prescan chunk failed: %s", exc)
    return found


def _format_signal_matrix(signals: list) -> str:
    """Format signal matrix results for prompt injection."""
    if not signals:
        return "No signal matrix flags for this submission."
    lines = []
    for sig in signals:
        if hasattr(sig, "signal_type"):
            lines.append(f"- {sig.signal_type}: {sig.interpretation} (category: {sig.keyword_category})")
        elif isinstance(sig, tuple) and len(sig) >= 4:
            lines.append(f"- {sig[0]}: {sig[3]} (category: {sig[1]})")
    return "\n".join(lines) if lines else "No signal matrix flags."


def _format_keyword_hits(hits: Dict[str, int]) -> str:
    if not hits:
        return "none"
    return ", ".join(f"{k}: {v}" for k, v in sorted(hits.items(), key=lambda x: -x[1])[:8])


def _build_lens_fragment(analysis_lens: Optional[Dict]) -> str:
    if not analysis_lens:
        return ""
    criteria = []
    for name, desc in analysis_lens.items():
        criteria.append(f"- {name}: {desc}")
    if not criteria:
        return ""
    return ANALYSIS_LENS_PROMPT_FRAGMENT.format(lens_criteria="\n".join(criteria))


def _build_interests_fragment(teacher_interests: list) -> str:
    if not teacher_interests:
        return ""
    summary = ", ".join(f"({i+1}) {interest}" for i, interest in enumerate(teacher_interests[:3]))
    return INTEREST_AREAS_FRAGMENT.format(interests_summary=summary)


def _parse_response(raw: str, student_name: str, student_id: str) -> dict:
    """Parse LLM JSON response with retry-on-failure logic."""
    parsed = parse_json_response(raw)
    if "_parse_error" in parsed:
        log.warning("JSON parse failed for %s: %s", student_name, parsed["_parse_error"])
        return parsed
    return parsed


def _safe_quotes(quotes_data: list) -> list:
    """Safely convert quote dicts to QuoteRecord instances."""
    result = []
    for q in (quotes_data or [])[:3]:
        if isinstance(q, dict) and q.get("text"):
            result.append(QuoteRecord(
                text=q["text"],
                significance=q.get("significance", ""),
            ))
    return result


def _validate_concepts(concepts: list, submission_text: str) -> list:
    """Post-validate concepts_applied against actual submission text.

    Removes concepts the student never mentioned.  An 8B model sometimes
    attributes course concepts to a submission based on the assignment
    prompt rather than the actual text.  Misrepresenting a student's
    engagement is a form of harm — it could lead a teacher to assume
    understanding that isn't there.

    Uses simple token overlap (not embedding similarity) to keep it
    fast and deterministic.
    """
    import re as _re

    if not concepts:
        return []

    sub_lower = submission_text.lower()
    sub_tokens = set(_re.findall(r"[a-z]{3,}", sub_lower))

    validated = []
    for concept in concepts:
        concept_lower = concept.lower()
        concept_tokens = set(_re.findall(r"[a-z]{3,}", concept_lower))

        if not concept_tokens:
            validated.append(concept)
            continue

        # Check 1: Direct substring match (handles multi-word concepts)
        if concept_lower in sub_lower:
            validated.append(concept)
            continue

        # Check 2: Token overlap — strict majority of the concept's content
        # words appear in the submission.  "> 0.5" (not ">= 0.5") means a
        # two-token concept like "cellular activity" requires BOTH tokens
        # present, preventing false validation when a single shared term
        # is a cross-domain homograph (e.g. "cellular" in "cellular device"
        # validating the biology concept "cellular activity").
        overlap = len(concept_tokens & sub_tokens)
        if overlap / len(concept_tokens) > 0.5:
            validated.append(concept)
            continue

        # Check 3: Stem overlap — catches partial references like
        # "intersectional" for the concept "intersectionality".
        # Same strict-majority rule: more than half the concept stems
        # must appear to avoid single-stem false cognates.
        stems = {t[:6] for t in concept_tokens if len(t) > 3}
        sub_stems = {t[:6] for t in sub_tokens if len(t) > 3}
        if stems and len(stems & sub_stems) / len(stems) > 0.5:
            validated.append(concept)
            continue

        log.debug(
            "Hallucination guard removed concept '%s' — "
            "no vocabulary support in submission text",
            concept,
        )

    return validated


def code_deepening(
    *,
    submission_text: str,
    student_name: str,
    student_id: str,
    coding_record: "SubmissionCodingRecord",
    primary_concern: object,
    backend: BackendConfig,
) -> dict:
    """Deepening pass for flagged submissions (experimental, Stage 4b).

    Runs ONLY when a concern flag exists for this student. Asks the 8B to:
      1. Name the rhetorical strategy precisely
      2. Reconsider emotional register given the concern context
      3. Surface theme tags in tension with the concern

    Returns a dict with keys: rhetorical_strategy, revised_register,
    register_change_reason, theme_tensions.
    Returns empty dict on any failure — pipeline must never crash here.

    Equity note: righteous anger about structural injustice is APPROPRIATE
    engagement. The concern detector already protects it — if no concern was
    flagged, this pass never runs for that student.
    """
    flagged_passage = getattr(primary_concern, "flagged_passage", "") or ""
    why_flagged = getattr(primary_concern, "why_flagged", "") or ""
    current_register = coding_record.emotional_register or "unassigned"
    theme_tags_str = (
        ", ".join(coding_record.theme_tags) if coding_record.theme_tags else "none"
    )
    coding_summary = (
        f"Theme tags: {theme_tags_str}\n"
        f"Emotional register: {current_register}\n"
        f"Emotional notes: {coding_record.emotional_notes or 'none'}\n"
        f"Personal connections: "
        f"{', '.join(coding_record.personal_connections[:2]) if coding_record.personal_connections else 'none'}"
    )

    try:
        prompt = DEEPENING_PROMPT.format(
            student_name=student_name,
            coding_summary=coding_summary,
            flagged_passage=flagged_passage[:400],
            why_flagged=why_flagged[:300],
            submission_text=submission_text[:2000],
            current_register=current_register,
            theme_tags_str=theme_tags_str,
        )
        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=600)
        parsed = parse_json_response(raw)
        if "_parse_error" in parsed:
            log.warning("Deepening pass JSON parse failed for %s", student_name)
            return {}
        return parsed
    except Exception as e:
        log.warning("Deepening pass failed for %s: %s", student_name, e)
        return {}


def code_submission(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    quick_summary: Optional[PerSubmissionSummary],
    signal_matrix_results: list,
    tier: str,
    backend: BackendConfig,
    analysis_lens: Optional[Dict] = None,
    teacher_interests: Optional[list] = None,
    profile_fragment: str = "",
    class_context: str = "",
) -> SubmissionCodingRecord:
    """Code one student submission using the LLM.

    Returns a SubmissionCodingRecord populated with LLM analysis.
    Concern detection is NOT included — that's a separate call.
    """
    # Build context from quick analysis
    vader_compound = quick_summary.vader_compound if quick_summary else 0.0
    vader_polarity = classify_vader_polarity(vader_compound)
    keyword_hits = _format_keyword_hits(quick_summary.keyword_hits if quick_summary else {})
    cluster_id = str(quick_summary.cluster_id) if quick_summary and quick_summary.cluster_id is not None else "none"
    signal_ctx = _format_signal_matrix(signal_matrix_results)
    lens_fragment = _build_lens_fragment(analysis_lens)
    interests_text = _build_interests_fragment(teacher_interests)

    # Linguistic repertoire → sentiment tier + LLM context + asset labels.
    # Uses the feature-based detector (from quick analysis) when available;
    # falls back to assess_sentiment_reliability for backward compat.
    _repertoire = quick_summary.linguistic_repertoire if quick_summary else None
    if _repertoire and hasattr(_repertoire, "sentiment_tier"):
        _reliability_tier = _repertoire.sentiment_tier
        _reliability_triggers = list(_repertoire.sentiment_triggers)
        linguistic_context = _repertoire.llm_context_note or ""
    else:
        # Fallback: bare assess_sentiment_reliability (no repertoire available)
        word_count_for_reliability = len(submission_text.split())
        _ac = quick_summary.assignment_connection if quick_summary else None
        _rel = assess_sentiment_reliability(
            submission_text,
            word_count=word_count_for_reliability,
            was_translated=quick_summary.was_translated if quick_summary else False,
            was_transcribed=quick_summary.was_transcribed if quick_summary else False,
            assignment_connection_overlap=_ac.vocabulary_overlap if _ac else None,
            compound_score=vader_compound,
        )
        _reliability_tier = _rel.tier
        _reliability_triggers = list(_rel.triggers)
        linguistic_context = ""
    # Build concise display strings for the prompt — NOT the full diagnostic caveat.
    trigger_summary = ", ".join(_reliability_triggers)
    if _reliability_tier == "suppressed":
        display_compound: object = "[SUPPRESSED]"
        display_polarity: str = f"score withheld ({trigger_summary}) — read tone directly from text"
        # Guard: the signal matrix was computed from the same biased score.
        # Prepend a reliability note so the LLM doesn't anchor on spurious
        # disengagement / compliance signals derived from the withheld score.
        signal_ctx = (
            f"[Signal matrix reliability note: same bias risk applies ({trigger_summary}) "
            f"— treat matrix signals as weak context only]\n{signal_ctx}"
        )
    elif _reliability_tier == "low":
        display_compound = f"{vader_compound:.3f}"
        display_polarity = f"{vader_polarity} [weak signal: {trigger_summary}]"
    else:
        display_compound = f"{vader_compound:.3f}"
        display_polarity = vader_polarity

    # GoEmotions top-3 enrichment — only surface when score is not suppressed
    # and the richer model was actually used.  Empty string when VADER fallback
    # or when score is withheld (would contradict the suppression instruction).
    _backend = quick_summary.sentiment_backend if quick_summary else ""
    _emotions_dict = quick_summary.emotions if quick_summary else {}
    if _backend == "go_emotions" and _reliability_tier != "suppressed" and _emotions_dict:
        _top3 = sorted(_emotions_dict.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_emotions_str = (
            "\n  Named emotions: "
            + ", ".join(f"{label} ({score:.2f})" for label, score in _top3)
        )
    else:
        top_emotions_str = ""

    if tier == "lightweight":
        record = _code_lightweight(
            submission_text=submission_text,
            student_id=student_id,
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            vader_compound=display_compound,
            vader_polarity=display_polarity,
            top_emotions=top_emotions_str,
            linguistic_context=linguistic_context,
            keyword_hits=keyword_hits,
            cluster_id=cluster_id,
            signal_ctx=signal_ctx,
            lens_fragment=lens_fragment,
            interests_text=interests_text,
            backend=backend,
            profile_fragment=profile_fragment,
            class_context=class_context,
        )
    else:
        record = _code_full(
            submission_text=submission_text,
            student_id=student_id,
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            vader_compound=display_compound,
            vader_polarity=display_polarity,
            top_emotions=top_emotions_str,
            linguistic_context=linguistic_context,
            keyword_hits=keyword_hits,
            cluster_id=cluster_id,
            signal_ctx=signal_ctx,
            lens_fragment=lens_fragment,
            interests_text=interests_text,
            backend=backend,
            analysis_lens=analysis_lens,
            profile_fragment=profile_fragment,
            class_context=class_context,
        )

    # Carry forward non-LLM metadata
    record.student_id = student_id
    record.student_name = student_name
    record.word_count = len(submission_text.split())
    record.emotional_register_score = vader_compound
    record.sentiment_reliability = _reliability_tier
    if quick_summary:
        record.cluster_id = quick_summary.cluster_id
        record.keyword_hits = quick_summary.keyword_hits
    # Linguistic assets (from feature detection — asset framing, not deficit)
    if _repertoire and hasattr(_repertoire, "asset_labels"):
        record.linguistic_assets = _repertoire.asset_labels

    return record


def _code_lightweight(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    vader_compound: Any,
    vader_polarity: str,
    top_emotions: str = "",
    linguistic_context: str = "",
    keyword_hits: str,
    cluster_id: str,
    signal_ctx: str,
    lens_fragment: str,
    interests_text: str,
    backend: BackendConfig,
    profile_fragment: str = "",
    class_context: str = "",
) -> SubmissionCodingRecord:
    """Lightweight tier: 2 decomposed calls (comprehension + interpretation)."""

    # Call 1: Comprehension
    class_context_block = f"\nCLASS CONTEXT: {class_context}\n" if class_context else ""
    # Linguistic context note goes before signals so it frames how the LLM reads
    _ling_block = f"\n{linguistic_context}\n" if linguistic_context else ""
    comp_prompt = COMPREHENSION_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        class_context=class_context_block,
        linguistic_context=_ling_block,
        vader_compound=vader_compound,
        vader_polarity=vader_polarity,
        top_emotions=top_emotions,
        keyword_hits=keyword_hits,
        cluster_id=cluster_id,
        signal_matrix_context=signal_ctx,
        submission_text=submission_text,
        profile_fragment=profile_fragment,
    )

    raw_comp = send_text(backend, comp_prompt, SYSTEM_PROMPT)
    comp = _parse_response(raw_comp, student_name, student_id)

    # Retry once on parse failure
    if "_parse_error" in comp:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw_comp[:1500],
            expected_format='{"student_name": "...", "readings_referenced": [...], ...}',
        )
        raw_comp = send_text(backend, repair, SYSTEM_PROMPT)
        comp = _parse_response(raw_comp, student_name, student_id)

    # Call 2: Interpretation
    interp_prompt = INTERPRETATION_PROMPT.format(
        student_name=student_name,
        comprehension_json=json.dumps(comp, indent=2)[:2000],
        assignment_prompt=assignment_prompt,
        teacher_interests=interests_text,
        submission_text=submission_text,
        lens_fragment=lens_fragment,
        profile_fragment=profile_fragment,
    )

    raw_interp = send_text(backend, interp_prompt, SYSTEM_PROMPT)
    interp = _parse_response(raw_interp, student_name, student_id)

    if "_parse_error" in interp:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw_interp[:1500],
            expected_format='{"theme_tags": [...], "theme_confidence": {...}, ...}',
        )
        raw_interp = send_text(backend, repair, SYSTEM_PROMPT)
        interp = _parse_response(raw_interp, student_name, student_id)

    # Validate concepts against submission text (hallucination guard)
    validated_concepts = _validate_concepts(
        comp.get("concepts_applied", []), submission_text,
    )

    # Merge comprehension + interpretation into a single record
    return SubmissionCodingRecord(
        student_id=student_id,
        student_name=student_name,
        # From comprehension
        notable_quotes=_safe_quotes(comp.get("notable_quotes", [])),
        readings_referenced=_safe_list(comp.get("readings_referenced")),
        concepts_applied=validated_concepts,
        personal_connections=_safe_list(comp.get("personal_connections")),
        current_events_referenced=_safe_list(comp.get("current_events_referenced")),
        # From interpretation
        theme_tags=_safe_list(interp.get("theme_tags")),
        theme_confidence=_safe_theme_confidence(interp.get("theme_confidence", {})),
        emotional_register=_coerce_str(interp.get("emotional_register")),
        emotional_notes=interp.get("emotional_notes", ""),
    )


def _code_full(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    vader_compound: Any,
    vader_polarity: str,
    top_emotions: str = "",
    linguistic_context: str = "",
    keyword_hits: str,
    cluster_id: str,
    signal_ctx: str,
    lens_fragment: str,
    interests_text: str,
    backend: BackendConfig,
    analysis_lens: Optional[Dict] = None,
    profile_fragment: str = "",
    class_context: str = "",
) -> SubmissionCodingRecord:
    """Medium/Deep tier: single combined coding call."""

    class_context_block = f"\nCLASS CONTEXT: {class_context}\n" if class_context else ""
    _ling_block = f"\n{linguistic_context}\n" if linguistic_context else ""
    prompt = CODING_FULL_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        teacher_interests=interests_text,
        class_context=class_context_block,
        linguistic_context=_ling_block,
        vader_compound=vader_compound,
        vader_polarity=vader_polarity,
        top_emotions=top_emotions,
        keyword_hits=keyword_hits,
        cluster_id=cluster_id,
        signal_matrix_context=signal_ctx,
        submission_text=submission_text,
        lens_fragment=lens_fragment,
        profile_fragment=profile_fragment,
    )

    raw = send_text(backend, prompt, SYSTEM_PROMPT, response_schema=_CodingOutput)
    parsed = _parse_response(raw, student_name, student_id)

    if "_parse_error" in parsed:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:1500],
            expected_format='{"student_name": "...", "theme_tags": [...], ...}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT)
        parsed = _parse_response(raw, student_name, student_id)

    # Build lens observations if analysis lens provided
    lens_obs = None
    if analysis_lens and parsed.get("lens_observations"):
        lens_obs = parsed["lens_observations"]

    # Validate concepts against submission text (hallucination guard)
    validated_concepts = _validate_concepts(
        parsed.get("concepts_applied", []), submission_text,
    )

    try:
        return SubmissionCodingRecord(
            student_id=student_id,
            student_name=student_name,
            theme_tags=_safe_list(parsed.get("theme_tags")),
            theme_confidence=_safe_theme_confidence(parsed.get("theme_confidence", {})),
            notable_quotes=_safe_quotes(parsed.get("notable_quotes", [])),
            emotional_register=_coerce_str(parsed.get("emotional_register")),
            emotional_notes=parsed.get("emotional_notes", ""),
            readings_referenced=_safe_list(parsed.get("readings_referenced")),
            concepts_applied=validated_concepts,
            personal_connections=_safe_list(parsed.get("personal_connections")),
            current_events_referenced=_safe_list(parsed.get("current_events_referenced")),
            lens_observations=lens_obs,
        )
    except Exception as exc:
        log.warning(
            "SubmissionCodingRecord construction failed for %s (%s) — "
            "returning minimal fallback record. Parsed keys: %s",
            student_name, exc, list(parsed.keys()),
        )
        return SubmissionCodingRecord(
            student_id=student_id,
            student_name=student_name,
            theme_tags=["parse error — teacher review needed"],
            emotional_notes=f"Coding failed: {exc}",
        )


def code_submission_reading_first(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    backend: BackendConfig,
    analysis_lens: Optional[Dict] = None,
    class_context: str = "",
    linguistic_context: str = "",
) -> SubmissionCodingRecord:
    """Reader-not-judge coding: free-form reading → structured extraction.

    Pass 1 — the model reads as a human reader would: no JSON, no rubric,
    just "what do you notice?" This produces the qualitative richness that
    JSON-first prompting kills (see synthesis-first architecture notes).

    Pass 2 — a lightweight extraction pass pulls structured fields from the
    reading. The reading grounds the extraction, preventing slot-filling
    behavior where the model invents content to satisfy the schema.

    This is an ALTERNATIVE to code_submission(), not a replacement.
    The existing tiers (lightweight, medium, deep) remain unchanged.
    """
    # --- Pass 1: Free-form reading ---
    # For long submissions, chunk into overlapping segments and merge readings.
    # Each chunk gets a full Pass 1 reading; readings are concatenated for Pass 2.
    # This ensures the model sees the ENTIRE submission — no silent truncation.
    CHUNK_SIZE = 3000       # chars per chunk (~600 words)
    CHUNK_OVERLAP = 400     # overlap to preserve context across boundaries

    class_context_block = f"\nCLASS CONTEXT:\n{class_context}\n" if class_context else ""
    ling_block = f"\n{linguistic_context}\n" if linguistic_context else ""

    chunks = _chunk_text(submission_text, CHUNK_SIZE, CHUNK_OVERLAP)

    readings = []
    for ci, chunk in enumerate(chunks):
        chunk_label = ""
        if len(chunks) > 1:
            chunk_label = f"\n[Section {ci + 1} of {len(chunks)}]\n"

        p1_prompt = CODING_READING_FIRST_P1.format(
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            class_context=class_context_block if ci == 0 else "",
            linguistic_context=ling_block if ci == 0 else "",
            submission_text=chunk_label + chunk,
        )

        chunk_reading = send_text(backend, p1_prompt, SYSTEM_PROMPT, max_tokens=1200)
        readings.append(chunk_reading)
        log.info(
            "Reading-first P1 for %s chunk %d/%d: %d chars",
            student_name, ci + 1, len(chunks), len(chunk_reading),
        )

    reading = "\n\n".join(readings)

    # --- Pass 2: Structured extraction ---
    # For long submissions, Pass 2 gets beginning + end so the model can
    # verify quotes against actual text. The reading from Pass 1 carries
    # the full content understanding.
    #
    # Cap the reading injected into Pass 2 at 1500 chars.  The full P2 prompt
    # also contains up to 3000 chars of submission text — combined with a long
    # reading the total can still exhaust a lightweight model's context window
    # even after the original 3000-char cap.  1500 chars (~300 tokens) carries
    # the key qualitative observations while reliably preserving response budget.
    # (Observed: char 658 truncation for one long submission with 3000-char cap.)
    _MAX_READING_FOR_P2 = 1500
    reading_for_p2 = reading
    if len(reading) > _MAX_READING_FOR_P2:
        reading_for_p2 = reading[:_MAX_READING_FOR_P2] + "\n[... reading truncated for context window ...]"
        log.debug(
            "Reading-first P2 for %s: reading truncated from %d → %d chars to preserve context window",
            student_name, len(reading), _MAX_READING_FOR_P2,
        )

    lens_fragment = _build_lens_fragment(analysis_lens)

    if len(submission_text) > CHUNK_SIZE:
        # Show beginning and end so quotes from any part can be verified
        half = CHUNK_SIZE // 2
        p2_text = submission_text[:half] + "\n[...]\n" + submission_text[-half:]
    else:
        p2_text = submission_text

    p2_prompt = CODING_READING_FIRST_P2.format(
        student_name=student_name,
        free_form_reading=reading_for_p2,
        submission_text=p2_text,
        lens_fragment=lens_fragment,
    )

    # Pass response_schema for constrained generation: Ollama uses GBNF grammar,
    # MLX uses Outlines FSM (when installed). Cloud backends silently ignore it.
    raw = send_text(backend, p2_prompt, SYSTEM_PROMPT, max_tokens=1200,
                    response_schema=_CodingOutput)
    parsed = _parse_response(raw, student_name, student_id)

    if "_parse_error" in parsed:
        # Attempt 2: JSON repair prompt
        # (Ollama users won't reach this — constrained generation prevents it)
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:1500],
            expected_format='{"student_name": "...", "theme_tags": [...], ...}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT, max_tokens=1200)
        parsed = _parse_response(raw, student_name, student_id)

    if "_parse_error" in parsed:
        # Attempt 3: re-run Pass 2 with an explicit JSON-only instruction
        # prepended. Some models (Gemma, Llama) generate preamble text even
        # when asked not to — a fresh call with a stronger constraint often
        # succeeds where the repair prompt failed.
        log.warning(
            "JSON repair failed for %s — retrying Pass 2 with JSON-only constraint",
            student_name,
        )
        json_only_prefix = (
            "Respond with ONLY a valid JSON object. "
            "No preamble, no explanation, no markdown fences. "
            "Start your response with { and end with }.\n\n"
        )
        raw = send_text(
            backend,
            json_only_prefix + p2_prompt,
            SYSTEM_PROMPT,
            max_tokens=1200,
            response_schema=_CodingOutput,
        )
        parsed = _parse_response(raw, student_name, student_id)
        if "_parse_error" not in parsed:
            log.info("JSON-only retry succeeded for %s", student_name)
        else:
            log.warning(
                "All 3 JSON attempts failed for %s — "
                "will use fallback record. Final error: %s",
                student_name, parsed.get("_parse_error", ""),
            )

    # Validate concepts against submission text (hallucination guard)
    validated_concepts = _validate_concepts(
        parsed.get("concepts_applied", []), submission_text,
    )

    reaching_for = parsed.get("what_student_is_reaching_for", "")
    if not reaching_for:
        log.warning(
            "what_student_is_reaching_for empty for %s — LLM may have "
            "omitted it from JSON. Parsed keys: %s",
            student_name, list(parsed.keys()),
        )

    try:
        return SubmissionCodingRecord(
            student_id=student_id,
            student_name=student_name,
            theme_tags=_safe_list(parsed.get("theme_tags")),
            theme_confidence=_safe_theme_confidence(parsed.get("theme_confidence", {})),
            notable_quotes=_safe_quotes(parsed.get("notable_quotes", [])),
            emotional_register=_coerce_str(parsed.get("emotional_register")),
            emotional_notes=parsed.get("emotional_notes", ""),
            readings_referenced=_safe_list(parsed.get("readings_referenced")),
            concepts_applied=validated_concepts,
            personal_connections=_safe_list(parsed.get("personal_connections")),
            # Reader-not-judge specific fields
            free_form_reading=reading,
            what_student_is_reaching_for=reaching_for,
            confusion_or_questions=parsed.get("confusion_or_questions") or None,
            # Non-LLM metadata — must be set here (unlike code_submission which
            # sets it post-return). Trajectory context depends on word_count > 0
            # to include prior records via _is_usable().
            word_count=len(submission_text.split()),
        )
    except Exception as exc:
        log.warning(
            "SubmissionCodingRecord construction failed for %s (%s) — "
            "returning minimal fallback record. Parsed keys: %s",
            student_name, exc, list(parsed.keys()),
        )
        return SubmissionCodingRecord(
            student_id=student_id,
            student_name=student_name,
            theme_tags=["parse error — teacher review needed"],
            emotional_notes=f"Coding failed: {exc}",
            free_form_reading=reading,
            word_count=len(submission_text.split()),
        )


# ---------------------------------------------------------------------------
# Per-student observation (shared between engine and demo generator)
# ---------------------------------------------------------------------------

_AI_FLAG_PREFIX = (
    "[NOTE: This submission was flagged as likely AI-generated by the "
    "engagement analysis system. The observation below describes what was "
    "submitted, regardless of authorship.]\n\n"
)


def observe_student(
    backend: BackendConfig,
    student_name: str,
    submission_text: str,
    class_context: str,
    assignment: str,
    *,
    is_ai_flagged: bool = False,
    teacher_lens: str = "",
    trajectory_context: str = "",
    max_tokens: int = 400,
) -> str:
    """Generate a 3-4 sentence observation for one student.

    This is the single source of truth for the observation stage.
    Both InsightsEngine and generate_demo_insights.py call this.

    Args:
        trajectory_context: Optional longitudinal context from prior
            submissions. Injected into the prompt so the LLM can see
            pattern breaks against the student's own baseline.

    Returns the observation text (may be prefixed with an AI-flag note).
    Returns empty string on failure.
    """
    from insights.prompts import OBSERVATION_SYSTEM_PROMPT, OBSERVATION_PROMPT

    wc = len(submission_text.split())
    if wc < 15:
        return "Submission too brief for observation."

    # Allow slightly more output when trajectory context is present
    effective_max_tokens = max_tokens + (100 if trajectory_context else 0)

    prompt = OBSERVATION_PROMPT.format(
        class_context=class_context,
        assignment=assignment,
        student_name=student_name,
        submission_text=submission_text,
        trajectory_context=trajectory_context,
        teacher_lens=teacher_lens,
    )

    try:
        raw = send_text(backend, prompt, OBSERVATION_SYSTEM_PROMPT,
                        max_tokens=effective_max_tokens)
        obs_text = raw.strip()
        # Strip model preamble ("Okay, here are my observations...",
        # "Okay, here's what I'm noticing about...", etc.)
        # Two patterns: period-terminated ("Here are my observations.") and
        # colon-terminated ("Okay, here's what I'm noticing about X:")
        import re as _re
        obs_text = _re.sub(
            r"^(?:Okay|OK|Sure|Here(?:'s| is| are))[^.]*(?:observations?|thoughts?|notes?|notic\w+)[^.]*\.\s*",
            "", obs_text, count=1, flags=_re.IGNORECASE,
        )
        obs_text = _re.sub(
            r"^(?:Okay|OK|Sure|Here)[^:\n]*(?:notic\w+|what I.m (?:seeing|noticing|"
            r"observing)|my (?:take|read|reading))[^:\n]*:\s*",
            "", obs_text, count=1, flags=_re.IGNORECASE,
        )
        if is_ai_flagged:
            obs_text = _AI_FLAG_PREFIX + obs_text
        return obs_text
    except Exception as exc:
        log.warning("Observation failed for %s: %s", student_name, exc)
        return ""


def classify_wellbeing(
    backend: BackendConfig,
    student_name: str,
    submission_text: str,
    *,
    assignment_prompt: str = "",
    max_tokens: int = 150,
) -> dict:
    """Classify a student's submission on the 4-axis wellbeing schema.

    Two-pass architecture (2026-03-29):
      Pass 0 (pre-scan): LLM semantic scan across all chunks — finds personal
        circumstance sentences buried in procedural/STEM writing. Avoids false
        positives on course material discussing the same topics.
      Pass 1 (classifier): 4-axis classification with found sentences
        foregrounded so they're not swamped by on-task content.

    Reads RAW SUBMISSION TEXT (not observations) — Test N showed 8/8,
    0 FP on raw text.

    Returns dict with keys: axis, signal, confidence, prescan_signals.
    Returns {"axis": "NONE", "signal": "", "confidence": 0.0} on failure.
    """
    from insights.prompts import (
        WELLBEING_CLASSIFIER_SYSTEM, WELLBEING_CLASSIFIER_PROMPT,
    )

    wc = len(submission_text.split())
    if wc < 15:
        return {"axis": "NONE", "signal": "Too brief", "confidence": 0.0,
                "prescan_signals": []}

    # Pass 0: semantic pre-scan across all chunks
    found_signals = _prescan_for_personal_signals(backend, submission_text)

    # Build signal prefix to foreground any found sentences for the classifier
    if found_signals:
        quoted = "\n".join(f'  "{s}"' for s in found_signals)
        signal_prefix = (
            "NOTE: The following sentence(s) from this student's submission "
            "appear to describe their own personal circumstances:\n"
            f"{quoted}\n"
            "Even a single such sentence is sufficient for CRISIS or BURNOUT "
            "classification if it reflects genuine personal circumstances.\n\n"
        )
    else:
        signal_prefix = ""

    # Truncate for classifier — pre-scan already covered the full text
    classifier_input = submission_text
    if len(submission_text) > _CLASSIFIER_MAX_INPUT:
        classifier_input = (
            submission_text[:_CLASSIFIER_MAX_INPUT] + "\n[...submission continues...]"
        )

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        signal_prefix=signal_prefix,
        assignment_prompt=assignment_prompt,
        submission_text=classifier_input,
    )

    try:
        raw = send_text(backend, prompt, WELLBEING_CLASSIFIER_SYSTEM,
                        max_tokens=max_tokens)
        parsed = _parse_response(raw, student_name, "wellbeing")

        axis = parsed.get("axis", "NONE")
        if axis not in ("CRISIS", "BURNOUT", "ENGAGED", "NONE"):
            log.warning("Unexpected wellbeing axis '%s' for %s", axis, student_name)
            axis = "NONE"

        return {
            "axis": axis,
            "signal": parsed.get("signal", ""),
            "confidence": float(parsed.get("confidence", 0.0)),
            "prescan_signals": found_signals,
        }
    except Exception as exc:
        log.warning("Wellbeing classification failed for %s: %s", student_name, exc)
        return {"axis": "NONE", "signal": "", "confidence": 0.0, "prescan_signals": []}


def classify_checkin(
    backend: BackendConfig,
    student_name: str,
    submission_text: str,
    *,
    assignment_prompt: str = "",
    max_tokens: int = 200,
) -> dict:
    """Pass 2: Targeted CHECK-IN for ENGAGED students only.

    Surfaces subtle self-disclosure signals (exhaustion, time pressure,
    personal difficulty) that a teacher might want to note. Only called
    on students already classified as ENGAGED by Pass 1 (4-axis).

    The prompt requires quotable self-reference about the student's OWN
    state, register shift as a strong indicator, and boolean calibration
    to prevent reasoning/output misalignment.

    Returns dict with keys: check_in (bool), reasoning (str).
    Returns {"check_in": False, "reasoning": ""} on failure.
    """
    from insights.prompts import (
        TARGETED_CHECKIN_SYSTEM, TARGETED_CHECKIN_PROMPT
    )

    wc = len(submission_text.split())
    if wc < 15:
        return {"check_in": False, "reasoning": "Too brief for check-in analysis."}

    prompt = TARGETED_CHECKIN_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        submission_text=submission_text,
    )

    try:
        raw = send_text(backend, prompt, TARGETED_CHECKIN_SYSTEM,
                        max_tokens=max_tokens)
        parsed = _parse_response(raw, student_name, "checkin")

        check_in = parsed.get("check_in", False)
        if not isinstance(check_in, bool):
            check_in = str(check_in).lower() in ("true", "1", "yes")

        return {
            "check_in": check_in,
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as exc:
        log.warning("CHECK-IN classification failed for %s: %s", student_name, exc)
        return {"check_in": False, "reasoning": ""}
