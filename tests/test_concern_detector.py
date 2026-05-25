"""
concern_detector.py — unit tests for pure (non-LLM) functions.

Tests the anti-bias post-processing layer, signal matrix formatters,
and the no-backend fallback path.

Equity-critical cases:
  - Anti-bias post-processing: LLM output using tone-policing language
    ("aggressive", "too emotional") + structural critique → bias warning added.
  - Content flag demotion: model flagging COURSE CONTENT rather than
    STUDENT WELLBEING must be caught and demoted.
  - APPROPRIATE signals must be filtered from concern prompts — we never
    want the LLM to analyze strengths as concerns.

No LLM calls in these tests.

Run with: python3 -m pytest tests/test_concern_detector.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from research.concern_detector import (
    _check_bias_in_output,
    _format_signal_matrix_for_prompt,
    _format_signal_matrix_tuples,
    _signal_matrix_fallback,
)
from insights.models import ConcernRecord, ConcernSignal


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

def make_concern(
    flagged_passage="The system is broken.",
    why_flagged="Student seems angry about the topic.",
    surrounding_context="",
    confidence=0.8,
) -> ConcernRecord:
    return ConcernRecord(
        flagged_passage=flagged_passage,
        surrounding_context=surrounding_context,
        why_flagged=why_flagged,
        confidence=confidence,
    )


def make_signal(
    student_id="s001",
    student_name="Alex Rivera",
    signal_type="CHECK IN",
    keyword_category="distress",
    vader_polarity="negative",
    matched_text="I can't cope anymore",
    interpretation="Possible distress signal",
) -> ConcernSignal:
    return ConcernSignal(
        student_id=student_id,
        student_name=student_name,
        signal_type=signal_type,
        keyword_category=keyword_category,
        vader_polarity=vader_polarity,
        matched_text=matched_text,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# _format_signal_matrix_for_prompt
# ---------------------------------------------------------------------------

class TestFormatSignalMatrixForPrompt:
    def test_empty_list_returns_no_signals_message(self):
        result = _format_signal_matrix_for_prompt([])
        assert "No non-LLM concern signals" in result

    def test_single_signal_formatted(self):
        sig = make_signal()
        result = _format_signal_matrix_for_prompt([sig])
        assert "CHECK IN" in result
        assert "distress" in result
        assert "negative" in result

    def test_matched_text_included(self):
        sig = make_signal(matched_text="I can't cope anymore")
        result = _format_signal_matrix_for_prompt([sig])
        assert "I can't cope" in result

    def test_empty_matched_text_not_added(self):
        sig = make_signal(matched_text="")
        result = _format_signal_matrix_for_prompt([sig])
        # No "Matched text:" line when empty
        assert "Matched text" not in result

    def test_multiple_signals_all_included(self):
        sigs = [
            make_signal(signal_type="CHECK IN", keyword_category="distress"),
            make_signal(signal_type="CONCERN", keyword_category="essentializing",
                        matched_text="all those people"),
        ]
        result = _format_signal_matrix_for_prompt(sigs)
        assert "CHECK IN" in result
        assert "CONCERN" in result

    def test_interpretation_included(self):
        sig = make_signal(interpretation="Possible student distress — teacher should check in")
        result = _format_signal_matrix_for_prompt([sig])
        assert "Possible student distress" in result


# ---------------------------------------------------------------------------
# _format_signal_matrix_tuples
# ---------------------------------------------------------------------------

class TestFormatSignalMatrixTuples:
    def test_empty_list_returns_no_signals_message(self):
        result = _format_signal_matrix_tuples([])
        assert "No non-LLM concern signals" in result

    def test_appropriate_signal_filtered_out(self):
        """APPROPRIATE signals must NOT appear in the concern prompt — we never
        want the LLM to analyze strengths as concerns."""
        signals = [("APPROPRIATE", "critical", "negative", "Passionate critique — not a concern")]
        result = _format_signal_matrix_tuples(signals)
        assert "APPROPRIATE" not in result
        assert "No non-LLM concern signals" in result

    def test_non_appropriate_tuple_formatted(self):
        signals = [("CHECK IN", "distress", "negative", "Possible student distress")]
        result = _format_signal_matrix_tuples(signals)
        assert "CHECK IN" in result
        assert "distress" in result

    def test_mixed_appropriate_and_concern(self):
        signals = [
            ("APPROPRIATE", "critical", "negative", "Structural critique"),
            ("CHECK IN", "distress", "negative", "Possible distress"),
        ]
        result = _format_signal_matrix_tuples(signals)
        assert "APPROPRIATE" not in result
        assert "CHECK IN" in result

    def test_object_with_signal_type_attribute(self):
        sig = make_signal(signal_type="CONCERN")
        result = _format_signal_matrix_tuples([sig])
        assert "CONCERN" in result

    def test_appropriate_object_also_filtered(self):
        sig = make_signal(signal_type="APPROPRIATE")
        result = _format_signal_matrix_tuples([sig])
        assert "APPROPRIATE" not in result
        assert "No non-LLM concern signals" in result

    def test_all_appropriate_returns_no_signals_message(self):
        signals = [
            ("APPROPRIATE", "critical", "negative", "Fine"),
            ("APPROPRIATE", "critical", "positive", "Also fine"),
        ]
        result = _format_signal_matrix_tuples(signals)
        assert "No non-LLM concern signals" in result


# ---------------------------------------------------------------------------
# _check_bias_in_output — anti-bias post-processing
# ---------------------------------------------------------------------------

class TestCheckBiasInOutput:
    """
    #TRANSFORMATIVE_JUSTICE: This function exists to catch cases where the
    LLM itself perpetuates tone policing — labeling students' passionate
    critique as 'aggressive' or 'too emotional'. The system must be able
    to catch when it's about to replicate the harm it's designed to surface.
    """

    def test_tone_policing_plus_structural_critique_adds_warning(self):
        concern = make_concern(
            flagged_passage="This system operates through structural racism and oppression.",
            why_flagged="The student seems aggressive in their tone.",
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert len(result) == 1
        assert "POSSIBLE MODEL BIAS" in result[0].why_flagged

    def test_bias_warning_lowers_confidence_by_03(self):
        concern = make_concern(
            flagged_passage="Liberation requires confronting colonialism directly.",
            why_flagged="This student is too emotional and irrational.",
            confidence=0.8,
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert result[0].confidence == pytest.approx(0.5)  # 0.8 - 0.3

    def test_confidence_floor_at_01(self):
        concern = make_concern(
            flagged_passage="We need to decolonize these institutions.",
            why_flagged="Aggressive and irrational response.",
            confidence=0.3,  # 0.3 - 0.3 = 0.0, but floor is 0.1
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert result[0].confidence >= 0.1

    def test_no_bias_markers_passes_through_unchanged(self):
        concern = make_concern(
            flagged_passage="I can't cope anymore. Everything is too much.",
            why_flagged="Student appears to be expressing distress about their circumstances.",
            confidence=0.85,
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert result[0].confidence == 0.85
        assert "BIAS" not in result[0].why_flagged

    def test_content_flag_marker_demoted(self):
        """Model flagging disturbing COURSE CONTENT (not student distress) → demoted."""
        concern = make_concern(
            flagged_passage="The text discusses rape and violence in graphic detail.",
            why_flagged="This passage may be triggering and discusses graphic violence.",
            confidence=0.9,
        )
        result = _check_bias_in_output([concern], "The reading covered historical violence.")
        assert result[0].confidence == pytest.approx(0.5)  # 0.9 - 0.4
        assert "COURSE CONTENT" in result[0].why_flagged

    def test_subject_matter_explanation_demoted(self):
        """Model explaining it's concerned about the topic, not the student → demoted."""
        concern = make_concern(
            flagged_passage="In this passage the author discusses genocide.",
            why_flagged="Student discusses genocide and abuse — this content is disturbing.",
            confidence=0.85,
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert result[0].confidence == pytest.approx(0.45)  # 0.85 - 0.4

    def test_content_demotion_lowers_confidence_by_04(self):
        concern = make_concern(
            why_flagged="This is sensitive material and may be triggering.",
            confidence=0.9,
        )
        result = _check_bias_in_output([concern], "plain submission text")
        # confidence reduced by 0.4, floor at 0.1
        assert result[0].confidence == pytest.approx(max(0.1, 0.9 - 0.4))

    def test_multiple_concerns_processed_independently(self):
        concerns = [
            make_concern(
                flagged_passage="oppression and liberation",
                why_flagged="Student is too aggressive.",
                confidence=0.8,
            ),
            make_concern(
                flagged_passage="I can't cope.",
                why_flagged="Student appears to be in distress.",
                confidence=0.9,
            ),
        ]
        result = _check_bias_in_output(concerns, "structural racism liberation")
        # First: bias warning, lowered confidence
        assert result[0].confidence < 0.8
        # Second: no bias markers, unchanged
        assert result[1].confidence == 0.9

    def test_empty_concerns_returns_empty(self):
        result = _check_bias_in_output([], "any submission text")
        assert result == []

    def test_original_assessment_preserved_in_warning(self):
        """When bias warning is added, original model text should still be visible."""
        original_why = "The student seems aggressive in their tone."
        concern = make_concern(
            flagged_passage="structural racism and oppression",
            why_flagged=original_why,
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        # Original text should appear in the modified why_flagged
        assert original_why in result[0].why_flagged

    def test_hysterical_triggers_bias_check(self):
        concern = make_concern(
            flagged_passage="colonialism and liberation",
            why_flagged="Student comes across as hysterical about these issues.",
        )
        result = _check_bias_in_output([concern], concern.flagged_passage)
        assert "POSSIBLE MODEL BIAS" in result[0].why_flagged

    def test_bias_markers_without_critique_no_warning(self):
        """
        #TRANSFORMATIVE_JUSTICE: Bias markers WITHOUT structural critique must
        NOT trigger the bias warning. If they did, genuine wellbeing concerns
        from frustrated students would get a bias-dismissal label.
        """
        concern = make_concern(
            flagged_passage="I hate everything and I want to give up.",
            why_flagged="Student is too emotional and seems aggressive in their frustration.",
            confidence=0.8,
        )
        result = _check_bias_in_output([concern], "I hate this class and everything about it.")
        # No structural critique → no bias rewrite → confidence unchanged
        assert result[0].confidence == pytest.approx(0.8)
        assert "POSSIBLE MODEL BIAS" not in result[0].why_flagged


# ---------------------------------------------------------------------------
# _signal_matrix_fallback
# ---------------------------------------------------------------------------

class TestSignalMatrixFallback:
    """Tests the no-LLM fallback that converts signal matrix results to
    low-confidence ConcernRecords."""

    def test_appropriate_concern_signal_skipped(self):
        sig = make_signal(student_id="s001", signal_type="APPROPRIATE")
        result = _signal_matrix_fallback([sig], [], "s001", "Alex Rivera", "text")
        assert len(result) == 0

    def test_non_appropriate_concern_signal_included(self):
        sig = make_signal(student_id="s001", signal_type="CHECK IN")
        result = _signal_matrix_fallback([sig], [], "s001", "Alex Rivera", "text")
        assert len(result) == 1

    def test_fallback_confidence_is_low(self):
        sig = make_signal(student_id="s001", signal_type="CHECK IN")
        result = _signal_matrix_fallback([sig], [], "s001", "Alex Rivera", "text")
        assert result[0].confidence == pytest.approx(0.3)

    def test_student_id_mismatch_excluded(self):
        """Signals from other students must not appear in this student's fallback."""
        sig = make_signal(student_id="s999", signal_type="CHECK IN")
        result = _signal_matrix_fallback([sig], [], "s001", "Alex Rivera", "text")
        assert len(result) == 0

    def test_tuple_signal_included(self):
        raw = [("CHECK IN", "distress", "negative", "Possible distress")]
        result = _signal_matrix_fallback([], raw, "s001", "Alex Rivera", "text")
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.3)

    def test_appropriate_tuple_excluded(self):
        raw = [("APPROPRIATE", "critical", "negative", "Structural critique — not a concern")]
        result = _signal_matrix_fallback([], raw, "s001", "Alex Rivera", "text")
        assert len(result) == 0

    def test_why_flagged_contains_interpretation(self):
        raw = [("CHECK IN", "distress", "negative", "Possible distress signal")]
        result = _signal_matrix_fallback([], raw, "s001", "Alex Rivera", "text")
        assert "Possible distress signal" in result[0].why_flagged

    def test_concern_signal_why_flagged_contains_interpretation(self):
        sig = make_signal(interpretation="Student may be experiencing distress")
        result = _signal_matrix_fallback([sig], [], "s001", "Alex Rivera", "text")
        assert "Student may be experiencing distress" in result[0].why_flagged

    def test_empty_inputs_returns_empty(self):
        result = _signal_matrix_fallback([], [], "s001", "Alex Rivera", "text")
        assert result == []
