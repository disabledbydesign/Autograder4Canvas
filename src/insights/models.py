"""
Pydantic data models for the Insights Engine.

These models define the structured data that flows between pipeline stages.
Structured data between stages (never free text) is the primary mitigation
against map-reduce information loss.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Preprocessing metadata (carried from PreprocessedSubmission)
# ---------------------------------------------------------------------------

class PreprocessingMetadata(BaseModel):
    """Metadata about what preprocessing was applied to a submission."""
    was_translated: bool = False
    was_transcribed: bool = False
    was_image_transcribed: bool = False
    original_language_name: Optional[str] = None
    original_text: Optional[str] = None
    teacher_comment: Optional[str] = None
    needs_teacher_comment: bool = False


# ---------------------------------------------------------------------------
# Sub-records used in SubmissionCodingRecord
# ---------------------------------------------------------------------------

class QuoteRecord(BaseModel):
    """A verbatim quote from a student submission with significance note."""
    text: str
    significance: str  # why this quote matters (1 sentence)


class ConcernRecord(BaseModel):
    """A flagged passage for teacher review.

    NOTE: No concern_type field. The model surfaces, the teacher classifies.
    This is honest about what 8B can do.
    """
    flagged_passage: str
    surrounding_context: str  # 2-3 sentences around the flagged passage
    why_flagged: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


# ---------------------------------------------------------------------------
# Per-submission coding record (Phase 2+ LLM output)
# ---------------------------------------------------------------------------

class SubmissionCodingRecord(BaseModel):
    """Structured record for one student submission.

    This is the atomic data unit — synthesis never sees raw submissions,
    only these records. Richness here = nuance preserved downstream.

    NOTE: No engagement_depth categorical field (8B can't judge this reliably).
    Instead we surface evidence: quotes, concepts_applied, personal_connections,
    readings_referenced. Teacher judges depth.

    NOTE: No uniqueness_flag (model hasn't seen other submissions at coding time).
    Uniqueness detected in outlier pass.
    """
    student_id: str
    student_name: str

    # Theme coding (1-5 tags, from open vocabulary)
    theme_tags: List[str] = []
    theme_confidence: Dict[str, float] = {}  # tag → 0.0-1.0

    # Notable quotes (verbatim — teacher hears the student's actual voice)
    notable_quotes: List[QuoteRecord] = []  # max 3

    # Emotional register
    emotional_register: str = ""  # analytical|passionate|personal|urgent|reflective|disengaged
    emotional_notes: str = ""

    # Content engagement evidence
    readings_referenced: List[str] = []
    concepts_applied: List[str] = []
    personal_connections: List[str] = []
    current_events_referenced: List[str] = []

    # Concern flags (populated by DEDICATED concerns call — always separate)
    concerns: List[ConcernRecord] = []

    # Analysis lens alignment — observations, NOT scores or levels
    lens_observations: Optional[Dict[str, str]] = None

    # Free-form reading (reader-not-judge coding path)
    free_form_reading: Optional[str] = None
    what_student_is_reaching_for: Optional[str] = None
    confusion_or_questions: Optional[str] = None

    # Per-student observation (observation-only architecture)
    # Replaces binary concern FLAGS with generative prose — the teacher reads
    # observations and decides what warrants action. 3-4 sentences covering
    # intellectual reach, emotional engagement, capacity signals, and any
    # structural power moves.
    observation: Optional[str] = None

    # Wellbeing classifier (4-axis, reads raw submission)
    wellbeing_axis: Optional[str] = None       # "CRISIS"|"BURNOUT"|"ENGAGED"|"NONE"
    wellbeing_signal: Optional[str] = None     # brief LLM description
    wellbeing_confidence: float = 0.0          # 0.0-1.0

    # Pass 2: Targeted CHECK-IN (runs only on ENGAGED students)
    # Surfaces subtle self-disclosure signals for teacher awareness.
    # The reasoning presents competing interpretations — the teacher decides.
    checkin_flag: Optional[bool] = None        # True if check-in warranted
    checkin_reasoning: Optional[str] = None    # quote + competing interpretations

    # Metadata from non-LLM pass (carried forward for synthesis)
    word_count: int = 0
    submitted_at: Optional[str] = None       # ISO 8601 from Canvas
    unknown_word_rate: float = 0.0           # unknown words per 100 words (spellchecker)
    cluster_id: Optional[int] = None
    emotional_register_score: float = 0.0
    sentiment_reliability: str = "high"  # "high" | "low" | "suppressed"
    keyword_hits: Dict[str, int] = {}
    # Linguistic assets (from detect_features) — teacher-facing, positive framing
    linguistic_assets: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def _migrate_vader_sentiment(cls, data: Any) -> Any:
        """Backward compat: old DB records use 'vader_sentiment' key."""
        if isinstance(data, dict) and "vader_sentiment" in data:
            data.setdefault("emotional_register_score", data.pop("vader_sentiment"))
        return data

    # Preprocessing metadata
    preprocessing: Optional[PreprocessingMetadata] = None

    # Draft student feedback (Phase 2+)
    draft_feedback: Optional[str] = None

    # AIC engagement dimensions — snapshot, not character assessment. Some engagement happens outside of text.
    engagement_signals: Optional[Dict[str, Any]] = None

    # Direct link to Canvas submission (populated by engine — enables one-click review)
    submission_url: Optional[str] = None

    # Count of non-null engagement signal dimensions — used to surface zero-signal students.
    # Computed after engagement_signals is populated (in engine.py).
    engagement_signal_count: int = 0

    # Truncation detection (copied from PerSubmissionSummary for UI access)
    is_possibly_truncated: bool = False
    truncation_note: str = ""

    # Tier 1 integrity flags (copied from AIC + QuickAnalysis for UI access)
    # These are binary, non-negotiable observations — no cultural bias risk.
    # Displayed as warning banners, never verdicts.
    integrity_flags: Optional[Dict[str, Any]] = None

    # Mechanism 1: Class-relative writing pattern context (from CohortCalibrator).
    # cohort_percentiles: per-signal rank labels (for detailed tooltip breakdown)
    # cohort_z_score: average z-score across all signals — positive = above class
    #   mean, negative = below. This is the primary UI display value.
    # These measure structural writing patterns (sentence variety, vocabulary,
    # punctuation density, voice authenticity) — NOT content or integrity.
    cohort_percentiles: Optional[Dict[str, str]] = None
    cohort_z_score: Optional[float] = None

    # Theme tags that may be in tension with flagged concerns — teacher review recommended, never auto-correct.
    theme_concern_notes: List[str] = []


# ---------------------------------------------------------------------------
# Quick Analysis Result (non-LLM pass output)
# ---------------------------------------------------------------------------

class TermFrequency(BaseModel):
    term: str
    count: int


class TermScore(BaseModel):
    term: str
    score: float


class SubmissionStats(BaseModel):
    total_submissions: int = 0
    total_enrollment: int = 0  # 0 = unknown
    word_count_mean: float = 0.0
    word_count_median: float = 0.0
    word_count_min: int = 0
    word_count_max: int = 0
    word_counts: List[int] = []
    format_breakdown: Dict[str, int] = {}  # format → count
    timing: Dict[str, int] = {}  # on_time, late, very_late, missing


class KeywordHit(BaseModel):
    pattern_name: str
    count: int
    student_ids: List[str] = []
    examples: List[str] = []  # brief excerpts of matching text


class EmbeddingCluster(BaseModel):
    cluster_id: int
    size: int
    student_ids: List[str] = []
    student_names: List[str] = []
    top_terms: List[str] = []
    centroid_text: str = ""  # representative snippet


class ConcernSignal(BaseModel):
    """Non-LLM concern pre-screening from VADER+keyword signal matrix."""
    student_id: str
    student_name: str
    signal_type: str  # matrix cell label (e.g. "POSSIBLE CONCERN")
    keyword_category: str  # which keyword category matched
    vader_polarity: str  # positive, negative, neutral
    matched_text: str  # the text that matched
    interpretation: str  # from the signal matrix


class SharedReference(BaseModel):
    reference: str
    student_ids: List[str] = []
    count: int = 0


class ContradictionSignal(BaseModel):
    """Detected when students have opposing sentiment about the same reference."""
    reference: str
    positive_students: List[str] = []
    negative_students: List[str] = []
    description: str = ""


class PerSubmissionSummary(BaseModel):
    """Summary data for one submission in the quick analysis."""
    student_id: str
    student_name: str
    word_count: int = 0
    submission_type: str = ""
    vader_compound: float = 0.0
    # GoEmotions enrichment — empty dict when VADER fallback was used
    emotions: Dict[str, float] = {}
    # Which backend produced the score: "go_emotions" | "vader" | "none"
    sentiment_backend: str = ""
    keyword_hits: Dict[str, int] = {}
    cluster_id: Optional[int] = None
    was_translated: bool = False
    was_transcribed: bool = False
    # Gibberish gate result
    is_gibberish: bool = False
    gibberish_reason: str = ""
    gibberish_detail: str = ""
    # Assignment connection (vocabulary overlap with assignment description)
    assignment_connection: Optional["AssignmentConnectionScore"] = None
    # Named reference match (authors, titles, concepts from assignment description)
    reference_match: Optional["ReferenceMatchScore"] = None
    # Truncation detection (non-LLM heuristic)
    is_possibly_truncated: bool = False
    truncation_note: str = ""
    # Unknown word rate from spellchecker (unknown words per 100 words)
    unknown_word_rate: float = 0.0
    # Linguistic repertoire (feature-based, not population-based)
    # Stores full detection result for sentiment tier, asset labels, LLM context, AIC adjustments.
    # None for old data — submission_coder falls back to assess_sentiment_reliability.
    linguistic_repertoire: Optional[Any] = None  # LinguisticFeatureResult from modules.linguistic_features


class AssignmentConnectionScore(BaseModel):
    """Non-LLM assessment of vocabulary overlap between a submission
    and the assignment description.

    This measures VOCABULARY OVERLAP only — it cannot assess whether
    a student is engaging with the material through lived experience,
    personal narrative, or non-standard approaches.

    Personal narratives about structural conditions ARE engagement with
    the material, even without academic vocabulary match.  A student
    discussing their grandmother's experience with intersecting oppressions
    is deeply on-topic regardless of whether they use the word
    "intersectionality."

    When submissions are translated, vocabulary overlap is measured against
    translated text and may not reflect engagement in the original language.
    """
    vocabulary_overlap: float = 0.0      # 0.0-1.0 cosine similarity
    keyword_overlap_count: int = 0       # how many assignment keywords found
    keyword_overlap_ratio: float = 0.0   # found / expected
    observation: str = ""                # human-readable note for the teacher


class AssignmentFingerprint(BaseModel):
    """Named references extracted from an assignment description.

    Pure NLP — no LLM required.  Uses spaCy NER + TF-IDF + keyword
    matching to identify what the assignment asks students to engage with.

    This fingerprint is then matched against each submission to measure
    whether the student referenced the assigned readings / concepts.
    Like AssignmentConnectionScore, this measures NAMED REFERENCE OVERLAP
    only — a student engaging through lived experience, personal narrative,
    or non-standard vocabulary is engaging with the material even if they
    don't name the author or use the term "intersectionality."
    """
    author_names: List[str] = []        # e.g., ["Crenshaw", "hooks"]
    work_titles: List[str] = []         # e.g., ["Mapping the Margins"]
    key_concepts: List[str] = []        # e.g., ["intersectionality", "traffic intersection metaphor"]
    engagement_type: str = "mixed"      # personal_reflection | analysis | summary | discussion | mixed
    raw_named_entities: List[str] = []  # All NER results for reference


class ReferenceMatchScore(BaseModel):
    """Per-submission match against the AssignmentFingerprint.

    Counts how many named authors, work titles, and key concepts from the
    assignment description appear in the student's submission.

    Same equity caveat as AssignmentFingerprint: absence of named references
    does not mean absence of engagement.  Students may engage through
    personal narrative, paraphrase, or non-academic vocabulary.
    """
    authors_found: List[str] = []       # which author names appeared
    authors_total: int = 0              # how many were in the fingerprint
    titles_found: List[str] = []        # which work titles appeared
    titles_total: int = 0
    concepts_found: List[str] = []      # which key concepts appeared
    concepts_total: int = 0
    match_ratio: float = 0.0           # (authors + titles + concepts found) / total
    observation: str = ""              # human-readable note for the teacher


class HighSimilarityPair(BaseModel):
    """Individual pair with very high cosine similarity (>=0.90).

    Surfaced ONLY at extreme thresholds.  Below this, similarity can
    reflect community cultural wealth, collaborative learning, or
    shared cultural knowledge.

    Even at this threshold, the observation is factual — the system
    does not determine cause.  Collaborative learning, shared source
    material, or copy/paste are all possible interpretations.
    """
    student_id_a: str
    student_name_a: str
    student_id_b: str
    student_name_b: str
    cosine_similarity: float
    observation: str = ""


class PairwiseSimilarityStats(BaseModel):
    """Class-level pairwise cosine similarity statistics.

    Surfaces aggregate patterns.  Individual pairs are surfaced ONLY at
    extreme thresholds (>=0.90) — see ``HighSimilarityPair``.  High
    similarity can indicate community, collaboration, or shared cultural
    knowledge, not only copying.  The first interpretive question is always:
    "Is the assignment designed to produce diverse responses?"
    """
    mean_similarity: float = 0.0
    max_similarity: float = 0.0
    pairs_above_085: int = 0   # high-similarity pairs (threshold 0.85)
    pairs_above_070: int = 0   # moderate-similarity pairs (threshold 0.70)
    total_pairs: int = 0
    observation: str = ""      # human-readable class-level note for the teacher
    high_similarity_pairs: List[HighSimilarityPair] = []  # pairs >= 0.90 only


class QuickAnalysisResult(BaseModel):
    """Complete output of the non-LLM analysis pass.

    Available in seconds, no LLM required. This alone is a useful tool.
    """
    assignment_id: str
    assignment_name: str = ""
    course_id: str = ""
    course_name: str = ""
    analyzed_at: str = ""

    # Submission statistics
    stats: SubmissionStats = Field(default_factory=SubmissionStats)

    # Word frequency (stopword-filtered, top N)
    top_terms: List[TermFrequency] = []

    # TF-IDF distinctive terms
    tfidf_terms: List[TermScore] = []

    # Named entities (spaCy)
    named_entities: Dict[str, List[str]] = {}  # entity_type → [entities]

    # Keyword pattern hits
    keyword_hits: Dict[str, KeywordHit] = {}

    # Emotional register scores per submission (GoEmotions or VADER fallback)
    # Inner dict keys: compound/pos/neg/neu (float), emotions (dict), reliability (str)
    sentiments: Dict[str, Dict[str, Union[float, str, Dict[str, float]]]] = {}
    sentiment_distribution: Dict[str, int] = {}  # register → count

    # Embedding clusters
    clusters: List[EmbeddingCluster] = []
    embedding_outlier_ids: List[str] = []

    # Pairwise cosine similarity (class-level + individual pairs at >= 0.90)
    pairwise_similarity: Optional[PairwiseSimilarityStats] = None

    # Assignment connection (vocabulary overlap between submissions and assignment)
    assignment_description: str = ""
    assignment_connection_observation: str = ""
    # Assignment fingerprint (named references extracted from assignment description)
    assignment_fingerprint: Optional[AssignmentFingerprint] = None

    # Cross-submission patterns
    shared_references: List[SharedReference] = []
    contradictions: List[ContradictionSignal] = []

    # Concern signals from VADER+keyword matrix
    concern_signals: List[ConcernSignal] = []

    # Per-submission summaries
    per_submission: Dict[str, PerSubmissionSummary] = {}

    # Citation analysis (only populated when citations are found)
    citation_report: Optional[Dict] = None  # CitationReport serialized

    # Gibberish gate results (student_ids flagged as non-analyzable)
    gibberish_ids: List[str] = []

    # Analysis notes (what components ran, what was skipped)
    analysis_notes: List[str] = []


# ---------------------------------------------------------------------------
# Theme generation (Phase 2+)
# ---------------------------------------------------------------------------

class Theme(BaseModel):
    name: str
    description: str = ""
    frequency: int = 0
    student_ids: List[str] = []
    supporting_quotes: List[QuoteRecord] = []
    confidence: float = 0.0
    sub_themes: Optional[List[str]] = None

    @field_validator("sub_themes", mode="before")
    @classmethod
    def coerce_sub_themes(cls, v):
        """Larger models return sub_themes as [{name:..., description:...}] — coerce to strings."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, dict):
                # Extract name, fall back to str(item)
                result.append(item.get("name") or item.get("theme") or str(item))
            else:
                result.append(str(item))
        return result or None


class Contradiction(BaseModel):
    """Opposing views explicitly preserved — tensions are productive, not problems."""
    description: str
    side_a: str
    side_a_students: List[str] = []
    side_b: str
    side_b_students: List[str] = []
    pedagogical_significance: str = ""


class ThemeSet(BaseModel):
    themes: List[Theme] = []
    contradictions: List[Contradiction] = []


# ---------------------------------------------------------------------------
# Outlier surfacing (Phase 2+)
# ---------------------------------------------------------------------------

class OutlierRecord(BaseModel):
    student_id: str
    student_name: str
    why_notable: str
    relationship_to_themes: str = ""
    notable_quote: Optional[QuoteRecord] = None
    teacher_recommendation: str = ""


class OutlierReport(BaseModel):
    outliers: List[OutlierRecord] = []


# ---------------------------------------------------------------------------
# Synthesis (Phase 2+)
# ---------------------------------------------------------------------------

class SynthesisReport(BaseModel):
    """Final analytical report with named sections."""
    sections: Dict[str, str] = {}  # section_name → markdown text
    confidence: float = 0.0

    @field_validator("sections", mode="before")
    @classmethod
    def _coerce_section_values(cls, v: object) -> object:
        """8B models occasionally place numeric values (e.g. confidence scores)
        inside the sections dict.  Filter them out rather than crashing."""
        if not isinstance(v, dict):
            return v
        clean = {}
        for k, val in v.items():
            if isinstance(val, str):
                clean[k] = val
            elif isinstance(val, (int, float)):
                # Model wrote e.g. "confidence": 0.8 inside sections — skip it
                _log.warning(
                    "SynthesisReport.sections[%r] has numeric value %r — skipping", k, val
                )
            else:
                clean[k] = str(val)
        return clean


# ---------------------------------------------------------------------------
# Guided Synthesis (A6 — replaces broken open-ended 3-pass synthesis)
# ---------------------------------------------------------------------------

class GuidedSynthesisResult(BaseModel):
    """Structured synthesis from guided 8B calls.

    Each field is populated by a separate, scoped LLM call.
    The teacher is the synthesis layer — this provides diagnosis.

    Partial results are valid: if Call 3 fails, Calls 1, 2, and 4 still
    produce useful output. (#CRIP_TIME: partial results > crash)
    """
    concern_patterns: List[Dict[str, Any]] = []      # Call 1
    concern_differences: List[str] = []               # Call 1
    engagement_highlights: List[Dict[str, Any]] = []  # Call 2
    tensions: List[Dict[str, Any]] = []               # Call 3
    class_temperature: str = ""                       # Call 4
    attention_areas: List[str] = []                   # Call 4
    calls_completed: int = 0                          # reliability tracking
    calls_attempted: int = 0
    cloud_narrative: str = ""                         # optional cloud enhancement


# ---------------------------------------------------------------------------
# Draft feedback (Phase 2+)
# ---------------------------------------------------------------------------

class DraftFeedback(BaseModel):
    student_id: str
    student_name: str
    feedback_text: str = ""
    strengths_noted: List[str] = []
    areas_for_growth: List[str] = []
    question_for_student: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Teacher analysis profile
# ---------------------------------------------------------------------------

class TeacherAnalysisProfile(BaseModel):
    """Persisted preferences that shape future pipeline runs.
    Starts empty. Grows with each teacher interaction."""

    theme_renames: Dict[str, str] = {}
    theme_splits: List[Dict] = []
    concern_sensitivity: Dict[str, float] = {}
    interest_areas: List[str] = []
    subject_area: str = "general"
    feedback_style: str = "warm"
    feedback_length: str = "moderate"
    custom_patterns: Dict[str, str] = {}
    # Teacher-defined concern patterns: plain-English descriptions injected
    # into the concern detection prompt alongside the default patterns.
    # Examples: "student makes a claim without citing evidence",
    #           "student attributes a group behavior to biology/genetics"
    custom_concern_patterns: List[str] = []
    # Default patterns the teacher has muted for this course.
    # Wellbeing/crisis signals cannot be fully disabled — they survive
    # regardless of this list. Only pedagogical patterns (essentializing,
    # colorblind framing, tone policing) can be suppressed here.
    disabled_default_patterns: List[str] = []
    # Teacher-defined positive signals to surface: community knowledge,
    # code-switching, unexpected connections, multilingual thinking, etc.
    # Flow into coding/synthesis prompts as strengths to name explicitly.
    custom_strength_patterns: List[str] = []
    edit_history: List[Dict] = []


# ---------------------------------------------------------------------------
# Pipeline confidence
# ---------------------------------------------------------------------------

class PipelineConfidence(BaseModel):
    overall: float = 0.0
    data_quality: float = 0.0
    coding_reliability: float = 0.0
    theme_coherence: float = 0.0
    synthesis_coverage: float = 0.0
    concerns: List[str] = []


# ---------------------------------------------------------------------------
# Cross-validation (Phase 5)
# ---------------------------------------------------------------------------

class ValidationFlag(BaseModel):
    """One disagreement (or agreement) between LLM and non-LLM analysis."""
    domain: str  # "concerns" | "themes" | "outliers"
    student_id: str = ""
    student_name: str = ""
    llm_says: str = ""
    matrix_says: str = ""
    agreement: str = "agree"  # "agree" | "llm_only" | "matrix_only"
    confidence_note: str = ""


# ---------------------------------------------------------------------------
# Cross-run trajectory (Phase 5)
# ---------------------------------------------------------------------------

class ThemeEvolution(BaseModel):
    theme_name: str
    weeks_present: List[int] = []
    first_appeared: int = 0
    status: str = "one-time"  # "recurring" | "new" | "fading" | "one-time"


class WeekMetric(BaseModel):
    week: int = 0
    label: str = ""  # human-readable week label (e.g. assignment name)
    avg_words: float = 0.0
    submission_rate: float = 0.0
    concern_count: int = 0
    concern_types: List[str] = []
    late_count: int = 0
    short_count: int = 0
    silence_count: int = 0


class ReadingEngagement(BaseModel):
    reading: str
    times_referenced: int = 0
    avg_word_count: float = 0.0  # avg words of submissions that reference this


class StudentArc(BaseModel):
    student_id: str
    student_name: str
    weekly_word_counts: List[Optional[int]] = []
    weekly_submission_status: List[str] = []  # "on_time" | "late" | "missing"
    weekly_concern_flags: List[int] = []  # count per week
    trend: str = "steady"  # "steady" | "improving" | "declining" | "irregular"


class CourseTrajectory(BaseModel):
    course_id: str
    course_name: str = ""
    run_count: int = 0
    date_range: str = ""  # e.g. "Jan 15 – Mar 10, 2026"
    theme_evolution: List[ThemeEvolution] = []
    engagement_trend: List[WeekMetric] = []
    concern_trend: List[WeekMetric] = []
    exhaustion_trend: List[WeekMetric] = []
    top_readings: List[ReadingEngagement] = []
    student_trajectories: List[StudentArc] = []
