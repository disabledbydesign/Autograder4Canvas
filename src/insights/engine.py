"""
InsightsEngine — Pipeline orchestrator for the Insights Engine.

Phase 1 flow:
  data_fetcher → preprocessing pipeline → quick_analyzer → save to insights_store

Phase 2 flow (after quick analysis):
  LLM backend detection → per-submission coding → wellbeing classification →
  per-student observations → theme generation → outlier surfacing →
  observation synthesis → feedback drafting → save all to store

Takes progress_callback for GUI integration.
Saves intermediaries at each stage for resumability.
"""

import logging
import os
import re
import shutil
import time
from typing import Callable, Dict, List, Optional

from insights.data_fetcher import DataFetcher
from insights.insights_store import InsightsStore
from insights.models import (
    QuickAnalysisResult,
    SubmissionCodingRecord,
)
from insights.patterns import signal_matrix_classify
from insights.quick_analyzer import QuickAnalyzer

log = logging.getLogger(__name__)

# AIC engagement signals — graceful degradation if module unavailable
try:
    import sys as _sys
    import os as _os
    _aic_src = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)))
    if _aic_src not in _sys.path:
        _sys.path.insert(0, _aic_src)
    from Academic_Dishonesty_Check_v2 import DishonestyAnalyzer as _DishonestyAnalyzer
    _HAS_AIC = True
except Exception as _aic_import_err:
    log.warning("AIC engagement signals unavailable (import failed): %s", _aic_import_err)
    _DishonestyAnalyzer = None  # type: ignore
    _HAS_AIC = False


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


# Theme-tag prefixes that mark un-analyzable submissions.
# Wellbeing classification and observation generation must skip these records —
# running them on empty/short text produces arbitrary classifications that look
# like real data in the DB and UI.
_SKIP_TAG_PREFIXES = (
    "blank submission",
    "insufficient text",
    "audio/video submission",
    "image submission",
    "unsupported format",
    "non-analyzable text",
    "parse error",
)


def _is_skip_record(record) -> bool:
    """True if this coding record was created because the submission couldn't be analyzed."""
    tags = record.theme_tags if hasattr(record, "theme_tags") else record.get("theme_tags", [])
    return any(
        tag.startswith(p)
        for tag in (tags or [])
        for p in _SKIP_TAG_PREFIXES
    )


# File extensions by type — used for skip-reason diagnosis
_AUDIO_VIDEO_EXTS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".webm", ".mp4", ".mov",
    ".flac", ".aac", ".wma", ".opus", ".oga",
}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".bmp", ".webp"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx", ".doc"}
_ODT_EXTS = {".odt"}


def _check_lib(module_name: str) -> bool:
    """Return True if module_name can be imported."""
    import importlib.util
    return importlib.util.find_spec(module_name) is not None


def _diagnose_skip(attachments: list) -> tuple[str, str]:
    """Return (tag, reason) for a student skipped due to unextractable attachments.

    Produces specific, actionable messaging for teachers based on what was submitted.
    """
    if not attachments:
        return "blank submission", "blank submission (no text entered)"

    exts = [os.path.splitext(a.get("filename", ""))[1].lower() for a in attachments]
    names = [a.get("filename", "?") for a in attachments[:3]]
    names_str = ", ".join(names)

    # All audio/video → Whisper path was expected but unavailable
    if all(e in _AUDIO_VIDEO_EXTS for e in exts if e):
        return (
            "audio/video submission — transcription unavailable",
            f"audio/video file(s) ({names_str}) — Whisper transcription not available; "
            f"check whisper-cli installation",
        )

    # All images → vision model expected but unavailable / not enabled
    if all(e in _IMAGE_EXTS for e in exts if e):
        return (
            "image submission — teacher review needed",
            f"image file(s) ({names_str}) — vision model not configured; "
            f"teacher should review submission directly",
        )

    # PDF — requires pdfminer.six
    if all(e in _PDF_EXTS for e in exts if e):
        if not _check_lib("pdfminer"):
            return (
                "PDF extraction unavailable — missing library",
                f"PDF file(s) ({names_str}) — pdfminer.six is not installed; "
                f"run: pip install pdfminer.six",
            )
        return (
            "PDF extraction failed",
            f"PDF file(s) ({names_str}) — extraction failed; file may be scanned "
            f"(image-only PDF) or corrupted",
        )

    # Word documents — requires python-docx
    if all(e in _DOCX_EXTS for e in exts if e):
        if not _check_lib("docx"):
            return (
                "Word document extraction unavailable — missing library",
                f"Word file(s) ({names_str}) — python-docx is not installed; "
                f"run: pip install python-docx",
            )
        return (
            "Word document extraction failed",
            f"Word file(s) ({names_str}) — extraction failed; file may be corrupted "
            f"or an unsupported legacy format",
        )

    # ODT — requires odfpy
    if all(e in _ODT_EXTS for e in exts if e):
        if not _check_lib("odf"):
            return (
                "ODT extraction unavailable — missing library",
                f"ODT file(s) ({names_str}) — odfpy is not installed; "
                f"run: pip install odfpy",
            )
        return (
            "ODT extraction failed",
            f"ODT file(s) ({names_str}) — extraction failed; file may be corrupted",
        )

    # Mixed or unknown formats
    ext_list = ", ".join(sorted({e for e in exts if e})) or "unknown"
    return (
        f"unsupported format — teacher review needed",
        f"file(s) ({names_str}) format not supported for text extraction "
        f"(extensions: {ext_list}); teacher should review submission directly",
    )


class InsightsEngine:
    """Pipeline orchestrator for the Insights Engine.

    Phase 1: data_fetcher → preprocessing → quick_analyzer → store.
    Phase 2: adds LLM passes (coding, concerns, themes, outliers, synthesis).
    """

    def __init__(
        self,
        api=None,
        store: Optional[InsightsStore] = None,
        settings: Optional[Dict] = None,
    ):
        self._api = api
        self._store = store or InsightsStore()
        self._settings = settings or {}
        self._cancelled = False
        # Sleep prevention is delegated to the shared SleepPreventer helper
        # (also used by the research-panel engine). Kept as an attribute so
        # cancel()/finally blocks can stop it from anywhere in the pipeline.
        from insights.process_keepalive import SleepPreventer
        self._sleep_preventer = SleepPreventer(
            enabled=bool(self._settings.get("insights_keep_awake", True))
        )
        # Back-compat: a few older code paths poked `_caffeinate_proc` directly.
        # Anything new should go through `_sleep_preventer`.
        self._caffeinate_proc = None

        # Push throttle setting into the LLM backend so it applies to all
        # MLX calls (even those outside the engine's own loops).
        from insights.llm_backend import set_mlx_throttle, unload_mlx_model
        self._unload_mlx = unload_mlx_model
        set_mlx_throttle(float(self._settings.get("insights_throttle_delay", 20)))

    def cancel(self) -> None:
        self._cancelled = True
        self._stop_sleep_prevention()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _start_sleep_prevention(self) -> None:
        """Prevent the computer from sleeping while the pipeline runs.

        Delegates to the shared `SleepPreventer` helper (see
        `insights.process_keepalive`). Idempotent.
        """
        # Honor live settings changes — the preventer only spawns if enabled
        self._sleep_preventer._enabled = bool(
            self._settings.get("insights_keep_awake", True)
        )
        self._sleep_preventer.start()

    def _stop_sleep_prevention(self) -> None:
        """Restore normal sleep behavior. Safe to call repeatedly."""
        self._sleep_preventer.stop()

    def _emit_timing(self, timing_callback, stage_name, start_time):
        """Emit timing if callback is set."""
        if timing_callback:
            timing_callback(stage_name, round(time.time() - start_time, 2))

    def run_analysis(
        self,
        *,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[Dict] = None,
        teacher_interests: Optional[list] = None,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
        course_profile_id: str = "default",
        next_week_topic: str = "",
        teacher_lens: str = "",
        ai_policy: str = "not_expected",
    ) -> Optional[str]:
        """Run the full analysis pipeline for one assignment.

        Fetches data from Canvas, preprocesses, then delegates to
        run_from_submissions() for the analysis pipeline.

        Returns the run_id on success, None on failure/cancellation.
        """
        progress = progress_callback or (lambda msg: None)

        # ----------------------------------------------------------
        # Stage 1: Data fetch
        # ----------------------------------------------------------
        progress(f"Fetching submissions for {assignment_name} ({course_name})...")

        fetcher = DataFetcher(self._api)

        if is_discussion:
            assign_info = fetcher.fetch_assignment_info(course_id, assignment_id)
            topic_id = None
            if assign_info:
                topic_id = assign_info.get("discussion_topic", {}).get("id")
            if not topic_id:
                topic_id = assignment_id
                log.info("No discussion_topic.id found, trying assignment_id as topic_id")
            raw_submissions = fetcher.fetch_discussion_entries(
                course_id, topic_id
            )
        else:
            raw_submissions = fetcher.fetch_submissions(
                course_id, assignment_id
            )

        if not raw_submissions:
            progress("No submissions found.")
            return None

        progress(f"Found {len(raw_submissions)} submissions.")

        # ----------------------------------------------------------
        # Stage 2: Preprocessing (translation + transcription)
        # ----------------------------------------------------------
        progress("Preprocessing submissions...")
        submissions = self._preprocess(
            raw_submissions,
            translate_enabled=translate_enabled,
            transcribe_enabled=transcribe_enabled,
            progress=progress,
        )

        # Fetch assignment description for vocabulary overlap check
        assignment_description = ""
        try:
            if self._api:
                _desc_fetcher = DataFetcher(self._api)
                assign_info = _desc_fetcher.fetch_assignment_info(
                    course_id, assignment_id
                )
                if assign_info:
                    raw_desc = assign_info.get("description", "")
                    if raw_desc:
                        assignment_description = _strip_html(raw_desc)
        except Exception as e:
            log.debug("Could not fetch assignment description: %s", e)

        # Delegate to the core pipeline
        return self.run_from_submissions(
            submissions=submissions,
            course_id=str(course_id),
            course_name=course_name,
            assignment_id=str(assignment_id),
            assignment_name=assignment_name,
            assignment_description=assignment_description,
            model_tier=model_tier,
            teacher_context=teacher_context,
            analysis_lens=analysis_lens,
            teacher_interests=teacher_interests,
            progress_callback=progress_callback,
            result_callback=result_callback,
            course_profile_id=course_profile_id,
            next_week_topic=next_week_topic or self._settings.get("insights_next_week_topic", ""),
            skip_feedback=not self._settings.get("insights_draft_feedback", False),
            teacher_lens=teacher_lens,
            ai_policy=ai_policy,
        )

    def run_from_submissions(
        self,
        *,
        submissions: List[Dict],
        course_id: str = "0",
        course_name: str = "",
        assignment_id: str = "0",
        assignment_name: str = "",
        assignment_description: str = "",
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[Dict] = None,
        teacher_interests: Optional[list] = None,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
        course_profile_id: str = "default",
        next_week_topic: str = "",
        skip_feedback: bool = False,
        timing_callback: Optional[Callable] = None,
        backend_override=None,
        teacher_lens: str = "",
        ai_policy: str = "not_expected",
        stop_after: str = "",
    ) -> Optional[str]:
        """Run the analysis pipeline on pre-loaded submissions.

        This is the core pipeline. run_analysis() fetches from Canvas and
        delegates here. Scripts can call this directly with corpus data.

        Returns the run_id on success, None on failure/cancellation.
        """
        progress = progress_callback or (lambda msg: None)
        emit_result = result_callback or (lambda t, d: None)
        self._cancelled = False
        self._start_sleep_prevention()

        # Load teacher profile for prompt injection
        from insights.teacher_profile import TeacherProfileManager
        profile_mgr = TeacherProfileManager(self._store, course_profile_id)
        profile_fragment = profile_mgr.get_full_profile_fragment()

        run_id = self._store.generate_run_id()
        total = len(submissions)

        # Build submission URL template — used to give teachers one-click access
        # to the raw Canvas submission for any student, especially skip records.
        _canvas_base = (
            self._api.base_url.rstrip("/") if self._api and getattr(self._api, "base_url", None) else ""
        )
        def _submission_url(sid: str) -> Optional[str]:
            if not _canvas_base:
                return None
            return f"{_canvas_base}/courses/{course_id}/assignments/{assignment_id}/submissions/{sid}"

        # Create run in store
        self._store.create_run(
            run_id=run_id,
            course_id=course_id,
            course_name=course_name,
            assignment_id=assignment_id,
            assignment_name=assignment_name,
            model_tier=model_tier,
            total_submissions=total,
            teacher_context=teacher_context,
            analysis_lens_config=analysis_lens,
            course_profile_id=course_profile_id,
        )
        self._store.complete_stage(run_id, "data_fetch")
        self._store.complete_stage(run_id, "preprocessing")

        try:
            # ----------------------------------------------------------
            # Stage 3: Quick Analysis (non-LLM)
            # ----------------------------------------------------------

            _stage_t0 = time.time()
            progress("Running Quick Analysis...")
            analyzer = QuickAnalyzer(
                progress_callback=progress,
            )
            qa_result = analyzer.analyze(
                submissions,
                assignment_id=str(assignment_id),
                assignment_name=assignment_name,
                assignment_description=assignment_description,
                course_id=str(course_id),
                course_name=course_name,
            )

            # Save quick analysis result
            self._store.save_quick_analysis(run_id, qa_result.model_dump_json())
            self._store.complete_stage(run_id, "quick_analysis")
            self._emit_timing(timing_callback, "quick_analysis", _stage_t0)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 4-8: LLM Analysis Pipeline
            # ----------------------------------------------------------
            # Detect available LLM backend
            from insights.llm_backend import auto_detect_backend

            if backend_override is not None:
                backend = backend_override
            else:
                backend = auto_detect_backend(model_tier, self._settings)

            if backend is None:
                # No LLM available — complete with Quick Analysis only
                progress("No LLM backend available — Quick Analysis complete.")
                confidence = {
                    "overall": self._compute_confidence(qa_result),
                    "data_quality": min(1.0, total / max(total, 1)),
                }
                self._store.complete_run(run_id, confidence)
                return run_id

            progress(f"LLM backend: {backend.name} ({backend.model})")

            # Build submission text map
            texts: Dict[str, str] = {}
            meta: Dict[str, Dict] = {}
            for sub in submissions:
                sid = str(sub.get("student_id", sub.get("user_id", "")))
                body = sub.get("body") or sub.get("text") or ""
                texts[sid] = _strip_html(body)
                meta[sid] = sub

            # Build assignment prompt (assignment_description already
            # fetched before Quick Analysis).
            assignment_prompt = (
                f"Assignment: {assignment_name}\n"
                f"Description: {assignment_description[:500]}"
                if assignment_description
                else f"Assignment: {assignment_name}"
            )

            # GPU throttle delay
            throttle = float(self._settings.get("insights_throttle_delay", 2.0))

            # ----------------------------------------------------------
            # Stage 3.5: Class Reading (synthesis-first)
            # Read the class as a community before coding individual students.
            # Relational harms (tone policing, essentializing in context) are
            # invisible when students are read in isolation — the class reading
            # makes them visible by surfacing the full relational field first.
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.class_reader import (
                generate_class_reading,
                is_reflective_assignment,
            )

            # Check if this assignment type benefits from a class reading.
            # Lab reports, problem sets, coding assignments etc. don't have
            # relational voice — skip class reading for those.
            _skip_class_reading = not is_reflective_assignment(
                assignment_name, assignment_description
            )
            if _skip_class_reading:
                log.info(
                    "Skipping class reading: assignment '%s' is non-reflective",
                    assignment_name,
                )
                progress("Non-reflective assignment — skipping class reading.")

            # Pre-scan AIC to identify likely AI-generated submissions BEFORE
            # the class reading, so AI voice doesn't center over authentic voices.
            # Gate on ai_policy: "allowed" skips AIC entirely (teacher says AI is fine)
            _ai_flagged_ids: set = set()
            if _HAS_AIC and not _skip_class_reading and ai_policy != "allowed":
                try:
                    _prescan_aic = _DishonestyAnalyzer(
                        profile_id="standard",
                        context_profile=self._settings.get(
                            "context_profile", "high_school"
                        ),
                    )
                    for _sid, _body in texts.items():
                        try:
                            _pre_result = _prescan_aic.analyze_text(
                                text=_body,
                                student_id=_sid,
                                student_name=meta.get(_sid, {}).get(
                                    "student_name", _sid
                                ),
                            )
                            # Flag submissions with elevated+ concern OR smoking gun
                            _cl = (
                                _pre_result.adjusted_concern_level
                                or _pre_result.concern_level
                            )
                            if _cl in ("elevated", "high") or _pre_result.smoking_gun:
                                _ai_flagged_ids.add(_sid)
                        except Exception:
                            pass  # non-fatal — student just won't be flagged
                    if _ai_flagged_ids:
                        log.info(
                            "AIC pre-scan: %d/%d submissions flagged as likely AI-generated",
                            len(_ai_flagged_ids),
                            len(texts),
                        )
                except Exception as _aic_pre_err:
                    log.warning("AIC pre-scan failed (non-fatal): %s", _aic_pre_err)

            emit_result("stage", {"stage": "READING CLASS AS A COMMUNITY"})
            progress("Reading class as a community...")

            class_reading = ""
            if _skip_class_reading:
                log.info("Class reading skipped for non-reflective assignment")
            else:
                try:
                    _cr_texts = {sid: texts[sid] for sid in texts}
                    _cr_names = {
                        sid: meta[sid].get("student_name", f"Student {sid}")
                        for sid in texts
                        if sid in meta
                    }

                    # Get cluster assignments from quick analysis if available
                    _cluster_map: Dict[str, int] = {}
                    if qa_result:
                        for _ps in qa_result.per_submission.values():
                            if (
                                hasattr(_ps, "cluster_id")
                                and _ps.cluster_id is not None
                            ):
                                _cluster_map[_ps.student_id] = _ps.cluster_id

                    # Build quick summaries for signal-guided excerpt selection
                    _quick_sums = (
                        {sid: qa_result.per_submission[sid]
                         for sid in _cr_texts if sid in qa_result.per_submission}
                        if qa_result and qa_result.per_submission else None
                    )

                    class_reading = generate_class_reading(
                        submissions=_cr_texts,
                        submission_names=_cr_names,
                        assignment_prompt=assignment_prompt,
                        course_name=course_name,
                        backend=backend,
                        teacher_context=teacher_context,
                        cluster_assignments=_cluster_map if _cluster_map else None,
                        quick_summaries=_quick_sums,
                        ai_flagged_ids=_ai_flagged_ids if _ai_flagged_ids else None,
                    )
                    if class_reading:
                        log.info("Class reading complete (%d chars)", len(class_reading))
                        self._store.save_class_reading(run_id, class_reading)
                        progress("Class reading complete.")
                    else:
                        log.info("Class reading returned empty — will use basic stats fallback")
                        progress("Class reading empty — using basic stats.")
                except Exception as _cr_err:
                    log.warning("Class reading failed (non-fatal): %s", _cr_err)
                    progress("Class reading failed — using basic stats.")

            self._emit_timing(timing_callback, "class_reading", _stage_t0)

            # ----------------------------------------------------------
            # Stage 4: Per-submission coding
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.submission_coder import code_submission, code_submission_reading_first

            progress("Coding submissions with LLM...")
            coding_records: List[SubmissionCodingRecord] = []

            # Build class context once — used as reference point for per-student coding.
            # Prefer the full class reading (synthesis-first); fall back to basic stats
            # so the 8B always has some distributional reference.
            _stats = qa_result.stats
            if class_reading:
                _class_context = class_reading
            else:
                _class_context = ""
                if _stats.total_submissions > 0:
                    _parts = [
                        f"Class has {_stats.total_submissions} submissions.",
                        f"Typical word count: {int(_stats.word_count_median)} words "
                        f"(range {_stats.word_count_min}–{_stats.word_count_max}).",
                    ]
                    if _stats.word_count_mean > 0:
                        _parts.append(
                            f"Average word count: {int(_stats.word_count_mean)} words."
                        )
                    _class_context = " ".join(_parts)

            # AIC engagement signals — fast (<0.1s per submission), no LLM
            aic_analyzer = None
            if _HAS_AIC:
                try:
                    aic_analyzer = _DishonestyAnalyzer(
                        profile_id="standard",
                        context_profile=self._settings.get("context_profile", "high_school"),
                    )
                except Exception as e:
                    log.warning("Could not instantiate AIC analyzer: %s", e)
                    aic_analyzer = None

            # Accumulate per-student AIC results for batch cohort calibration
            # (cohort calibration needs the full class distribution — can't be
            # per-student; we run it once after the coding loop completes)
            _aic_results_by_sid: Dict = {}

            for i, (sid, body) in enumerate(texts.items()):
                if self._cancelled:
                    return None

                sub_meta = meta.get(sid, {})
                name = sub_meta.get("student_name", f"Student {sid}")
                quick_sub = qa_result.per_submission.get(sid)

                # Get signal matrix results for this submission
                vader_compound = qa_result.sentiments.get(sid, {}).get("compound", 0.0)
                wc = len(body.split())
                sig_results = signal_matrix_classify(
                    body, vader_compound, wc, qa_result.stats.word_count_median
                )

                # Get concern signals for this student
                student_concern_signals = [
                    s for s in qa_result.concern_signals if s.student_id == sid
                ]

                if i == 0:
                    emit_result("stage", {"stage": "LISTENING TO STUDENT WORK"})
                progress(f"Reading student work ({i + 1}/{total}): {name}...")

                # Show the student's actual text while LLM processes
                emit_result("reading", {
                    "student_name": name,
                    "text": body[:500],
                    "word_count": wc,
                })

                # Guard: skip LLM coding for very short submissions
                if wc < 15:
                    # Diagnose WHY the text is blank/short
                    sub_type = sub_meta.get("submission_type", "")
                    attachments = sub_meta.get("attachments", [])
                    if wc == 0 and sub_type == "online_upload" and attachments:
                        tag, reason = _diagnose_skip(attachments)
                    elif wc == 0 and not body.strip():
                        reason = "blank submission (no text entered)"
                        tag = "blank submission"
                    else:
                        reason = f"only {wc} words"
                        tag = "insufficient text for analysis"

                    log.warning("Skipping %s: %s", name, reason)
                    progress(f"  Skipping {name}: {reason}")

                    record = SubmissionCodingRecord(
                        student_id=sid,
                        student_name=name,
                        theme_tags=[tag],
                        theme_confidence={tag: 1.0},
                        emotional_register="",
                        emotional_notes=reason,
                        notable_quotes=[],
                        word_count=wc,
                        submission_url=_submission_url(sid),
                    )
                    # Persist Canvas metadata for trajectory comparator
                    record.submitted_at = meta.get(sid, {}).get("submitted_at")
                    if quick_sub:
                        record.unknown_word_rate = quick_sub.unknown_word_rate
                    coding_records.append(record)
                    self._store.save_coding(
                        run_id, sid, name, record.model_dump_json(),
                        submission_text=body,
                    )
                    # Surface prior engagement context for skip cards in the GUI
                    try:
                        from insights.trajectory_context import build_trajectory_context
                        _traj = build_trajectory_context(
                            self._store, student_id=sid, course_id=str(course_id),
                            current_run_id=run_id, current_word_count=wc,
                            current_submitted_at=record.submitted_at or "",
                        )
                        if _traj:
                            record.observation = _traj
                            self._store.save_coding(
                                run_id, sid, name, record.model_dump_json(),
                                submission_text=body,
                            )
                    except Exception:
                        pass
                    preview_data = record.model_dump()
                    preview_data["_original_text"] = body[:300] if body.strip() else reason
                    emit_result("coding", preview_data)
                    continue

                # Guard: skip LLM coding for gibberish submissions
                if quick_sub and quick_sub.is_gibberish:
                    progress(f"  Skipping {name}: gibberish ({quick_sub.gibberish_reason})")
                    record = SubmissionCodingRecord(
                        student_id=sid,
                        student_name=name,
                        theme_tags=["non-analyzable text"],
                        theme_confidence={"non-analyzable text": 1.0},
                        emotional_register="",
                        emotional_notes=f"Gibberish gate: {quick_sub.gibberish_detail}",
                        notable_quotes=[],
                        word_count=wc,
                        integrity_flags={
                            "gibberish": True,
                            "gibberish_reason": quick_sub.gibberish_reason,
                            "gibberish_detail": quick_sub.gibberish_detail,
                        },
                        submission_url=_submission_url(sid),
                    )
                    # Persist Canvas metadata for trajectory comparator
                    record.submitted_at = meta.get(sid, {}).get("submitted_at")
                    if quick_sub:
                        record.unknown_word_rate = quick_sub.unknown_word_rate
                    coding_records.append(record)
                    self._store.save_coding(
                        run_id, sid, name, record.model_dump_json(),
                        submission_text=body,
                    )
                    preview_data = record.model_dump()
                    preview_data["_original_text"] = body[:300]
                    emit_result("coding", preview_data)
                    continue

                # Inject assignment connection note when vocabulary
                # overlap is low — prevents the 8B from hallucinating
                # assignment concepts onto unrelated content.
                coding_prompt = assignment_prompt
                if quick_sub and quick_sub.assignment_connection:
                    ac = quick_sub.assignment_connection
                    if ac.vocabulary_overlap < 0.3:
                        coding_prompt = (
                            f"{assignment_prompt}\n\n"
                            f"NOTE: This submission's vocabulary has "
                            f"low overlap ({ac.vocabulary_overlap:.0%}) "
                            f"with the assignment keywords. Code what "
                            f"the student ACTUALLY wrote about, not "
                            f"what the assignment asked for. If the "
                            f"student is engaging with the material "
                            f"through personal experience rather than "
                            f"academic vocabulary, that engagement is "
                            f"valid — capture it."
                        )

                # Run AIC engagement signals before coding (fast, no LLM)
                engagement = None
                aic_result = None
                if aic_analyzer is not None:
                    try:
                        aic_result = aic_analyzer.analyze_text(
                            text=body,
                            student_id=sid,
                            student_name=name,
                        )
                        engagement = aic_result.engagement_signals
                        _aic_results_by_sid[sid] = aic_result
                    except Exception as e:
                        log.warning("AIC engagement signals failed for %s: %s", sid, e)
                        engagement = None

                # Build engagement context note for 8B
                if engagement:
                    depth = engagement.get("engagement_depth", "unavailable")
                    personal = engagement.get("personal_connection", {}).get("label", "unavailable")
                    engagement_note = (
                        f"\n\n[Engagement signals from structural analysis: "
                        f"depth={depth}, personal_connection={personal}. "
                        f"These are structural indicators — the student may engage "
                        f"in ways not visible in text.]"
                    )
                else:
                    engagement_note = ""

                # Build linguistic context for reading-first coding
                _coding_ling_note = ""
                if quick_sub and hasattr(quick_sub, "linguistic_repertoire"):
                    _rep = quick_sub.linguistic_repertoire
                    if _rep and hasattr(_rep, "llm_context_note") and _rep.llm_context_note:
                        _coding_ling_note = _rep.llm_context_note

                record = code_submission_reading_first(
                    submission_text=body,
                    student_id=sid,
                    student_name=name,
                    assignment_prompt=coding_prompt,
                    backend=backend,
                    analysis_lens=analysis_lens,
                    class_context=_class_context,
                    linguistic_context=_coding_ling_note,
                )

                if record is not None:
                    record.engagement_signals = engagement
                    # Count non-null signal dimensions — surfaces zero-signal students.
                    if engagement:
                        record.engagement_signal_count = sum(
                            1 for v in engagement.values()
                            if v is not None and v != "" and v is not False
                        )
                    # Copy truncation data from QuickAnalysis for UI access
                    if quick_sub and quick_sub.is_possibly_truncated:
                        record.is_possibly_truncated = True
                        record.truncation_note = quick_sub.truncation_note

                    # Copy Tier 1 integrity flags for UI display
                    _iflags: dict = {}
                    if aic_result is not None:
                        if aic_result.smoking_gun:
                            _iflags["smoking_gun"] = True
                            _iflags["smoking_gun_details"] = list(
                                aic_result.smoking_gun_details
                            )
                        if aic_result.unicode_manipulation:
                            _iflags["unicode_manipulation"] = True
                            _iflags["unicode_manipulation_details"] = list(
                                aic_result.unicode_manipulation_details
                            )
                    if quick_sub and quick_sub.is_gibberish:
                        _iflags["gibberish"] = True
                        _iflags["gibberish_reason"] = quick_sub.gibberish_reason
                        _iflags["gibberish_detail"] = quick_sub.gibberish_detail
                    if _iflags:
                        record.integrity_flags = _iflags

                    # Persist Canvas metadata for trajectory comparator
                    record.submitted_at = meta.get(sid, {}).get("submitted_at")
                    record.submission_url = _submission_url(sid)
                    if quick_sub:
                        record.unknown_word_rate = quick_sub.unknown_word_rate

                coding_records.append(record)

                # Save intermediary (include submission text for chatbot export)
                self._store.save_coding(
                    run_id, sid, name, record.model_dump_json(),
                    submission_text=body,
                )

                # Emit for live preview — include original text for sparse results
                preview_data = record.model_dump()
                preview_data["_original_text"] = body[:300]
                emit_result("coding", preview_data)

                # Throttle between LLM calls
                if throttle > 0 and i < total - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "coding")
            self._emit_timing(timing_callback, "coding_total", _stage_t0)

            # Audit: surface any fallback records so trends are visible in logs.
            _parse_error_records = [
                r for r in coding_records
                if r is not None
                and "parse error — teacher review needed" in (r.theme_tags or [])
            ]
            if _parse_error_records:
                names = [r.student_name for r in _parse_error_records]
                log.warning(
                    "Coding degraded for %d/%d students (JSON parse failures after "
                    "3 attempts): %s. These students have a fallback record — "
                    "teacher should review their submissions directly.",
                    len(_parse_error_records), total, ", ".join(names),
                )

            # Release MLX model between stages to prevent Metal memory
            # fragmentation on 16 GB machines.  Costs ~15-20s reload but
            # prevents the cumulative deadlock that freezes the system.
            if backend and backend.name == "mlx":
                self._unload_mlx()

            # ----------------------------------------------------------
            # Linguistic feature baselines + trends
            # ----------------------------------------------------------
            _trends: List[str] = []
            try:
                from modules.linguistic_features import compute_feature_baseline, surface_linguistic_trends, FeatureBaseline
                import json as _json_feat

                # Collect feature results from quick analysis
                _feature_results = []
                for sid in texts:
                    _qs = qa_result.per_submission.get(sid) if qa_result else None
                    if _qs and hasattr(_qs, 'linguistic_repertoire') and _qs.linguistic_repertoire:
                        _feature_results.append(_qs.linguistic_repertoire)

                if _feature_results:
                    # Compute and store baseline (EMA with prior if available)
                    _prior_json = self._store.get_feature_baseline(str(course_id))
                    _prior = None
                    if _prior_json:
                        try:
                            _prior = FeatureBaseline(**_json_feat.loads(_prior_json))
                        except Exception:
                            pass
                    _new_baseline = compute_feature_baseline(_feature_results, prior=_prior)
                    self._store.save_feature_baseline(
                        str(course_id),
                        _json_feat.dumps(_new_baseline.model_dump() if hasattr(_new_baseline, 'model_dump') else vars(_new_baseline)),
                        n_students=len(_feature_results),
                    )

                    # Surface trends for synthesis
                    _trends = surface_linguistic_trends(_feature_results, len(texts))
                    if _trends:
                        log.info("Linguistic trends: %s", _trends)
            except Exception as e:
                log.debug("Feature baseline/trends: %s", e)
                _trends = []

            # ----------------------------------------------------------
            # Cohort calibration (post-coding batch pass)
            # Requires the full class of AIC results — cannot run per-student.
            # Annotates each coding_record with class-relative percentile ranks.
            # ----------------------------------------------------------
            if _aic_results_by_sid and len(_aic_results_by_sid) >= 3:
                try:
                    from modules.cohort_calibration import (
                        CohortCalibrator,
                        extract_signal_vector,
                    )
                    _calibrator = CohortCalibrator()
                    _signal_vectors = []
                    _vector_map: Dict = {}
                    for _sid, _ar in _aic_results_by_sid.items():
                        _vec = extract_signal_vector(_ar)
                        if _vec:
                            _signal_vectors.append(_vec)
                            _vector_map[_sid] = _vec

                    if _signal_vectors:
                        _distributions = _calibrator.compute_class_distributions(
                            _signal_vectors
                        )
                        # Annotate each coding record with percentiles + z-score
                        _n_annotated = 0
                        for _rec in coding_records:
                            _vec = _vector_map.get(_rec.student_id)
                            if _vec is not None and _distributions:
                                _rec.cohort_percentiles = (
                                    _calibrator.compute_student_percentiles(
                                        _vec, _distributions
                                    )
                                )
                                # Compute average z-score across signals
                                _z_scores = []
                                for _sig, _val in _vec.items():
                                    _stats = _distributions.get(_sig)
                                    if _stats and _stats.get("stdev", 0) > 0:
                                        _z = (_val - _stats["mean"]) / _stats["stdev"]
                                        _z_scores.append(_z)
                                if _z_scores:
                                    _rec.cohort_z_score = round(
                                        sum(_z_scores) / len(_z_scores), 2
                                    )
                                _n_annotated += 1
                                # Re-save with cohort data
                                self._store.save_coding(
                                    run_id,
                                    _rec.student_id,
                                    _rec.student_name,
                                    _rec.model_dump_json(),
                                )
                        log.info(
                            "Cohort calibration: %d vectors, %d records annotated",
                            len(_signal_vectors),
                            _n_annotated,
                        )
                except Exception as _ce:
                    log.warning("Cohort calibration skipped in Insights engine: %s", _ce)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 5: Wellbeing classification (4-axis, reads raw submissions)
            # Replaces binary concern detection. Classifies each student as
            # CRISIS / BURNOUT / ENGAGED / NONE. Validated Test N (n=4):
            # 8/8, 0 FP, 100% stable across runs.
            # Runs sequentially with observations (MLX single-inference on 16GB).
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.submission_coder import classify_wellbeing

            progress("Running wellbeing classification...")

            for i, record in enumerate(coding_records):
                if self._cancelled:
                    return None

                # Skip students whose submissions couldn't be analyzed — running
                # wellbeing on empty text produces arbitrary classifications that
                # look like real data and confuse the teacher.
                if _is_skip_record(record):
                    log.debug("Wellbeing: skipping %s (skip record: %s)",
                              record.student_name, record.theme_tags)
                    continue

                sid = record.student_id
                body = texts.get(sid, "")

                progress(f"Wellbeing {i + 1}/{total}: {record.student_name}...")

                wb = classify_wellbeing(
                    backend,
                    student_name=record.student_name,
                    submission_text=body,
                    assignment_prompt=assignment_prompt,
                )
                record.wellbeing_axis = wb["axis"]
                record.wellbeing_signal = wb["signal"]
                record.wellbeing_confidence = wb["confidence"]

                self._store.save_coding(
                    run_id, sid, record.student_name, record.model_dump_json()
                )

                if throttle > 0 and i < total - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "wellbeing")
            self._emit_timing(timing_callback, "wellbeing", _stage_t0)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 5a: Targeted CHECK-IN (Pass 2 of two-pass wellbeing)
            # Runs ONLY on ENGAGED students. Surfaces subtle self-disclosure
            # signals (exhaustion, time pressure, personal difficulty) for
            # teacher awareness. Uses temp 0.3 (generative reasoning).
            # Validated: Test P v3 (2/7 corpus, 0/2 control FPs).
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from dataclasses import replace as _dc_replace
            from insights.submission_coder import classify_checkin

            # CHECK-IN uses higher temperature for generative reasoning
            checkin_backend = _dc_replace(backend, temperature=0.3)

            engaged_records = [
                r for r in coding_records if r.wellbeing_axis == "ENGAGED"
            ]
            progress(
                f"Running CHECK-IN on {len(engaged_records)} ENGAGED "
                f"students (skipping {total - len(engaged_records)} "
                f"CRISIS/BURNOUT/NONE)..."
            )

            for i, record in enumerate(engaged_records):
                if self._cancelled:
                    return None

                sid = record.student_id
                body = texts.get(sid, "")

                progress(
                    f"CHECK-IN {i + 1}/{len(engaged_records)}: "
                    f"{record.student_name}..."
                )

                ci = classify_checkin(
                    checkin_backend,
                    student_name=record.student_name,
                    submission_text=body,
                    assignment_prompt=assignment_prompt,
                )
                record.checkin_flag = ci["check_in"]
                record.checkin_reasoning = ci["reasoning"]

                self._store.save_coding(
                    run_id, sid, record.student_name, record.model_dump_json()
                )

                if throttle > 0 and i < len(engaged_records) - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "checkin")
            self._emit_timing(timing_callback, "checkin", _stage_t0)

            # Release MLX model between checkin → observations
            if backend and backend.name == "mlx":
                self._unload_mlx()

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 5b: Per-student observations
            # Every student gets a 3-4 sentence observation describing their
            # intellectual reach, emotional engagement, and anything the teacher
            # should notice — including structural power moves.
            # Results stored as observation field on each coding record.
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.submission_coder import observe_student
            from insights.trajectory_context import build_trajectory_context

            progress("Generating per-student observations...")
            _teacher_lens = ""
            _tl_raw = teacher_lens or self._settings.get("insights_teacher_lens", "")
            if _tl_raw:
                _teacher_lens = (
                    f"TEACHER'S OBSERVATION PRIORITIES:\n{_tl_raw}\n"
                )

            observations_map = {}  # sid -> observation text
            for i, record in enumerate(coding_records):
                if self._cancelled:
                    return None

                # Skip students whose submissions couldn't be analyzed — an
                # observation on empty text is an empty string at best, a
                # hallucinated fabrication at worst.
                if _is_skip_record(record):
                    log.debug("Observations: skipping %s (skip record: %s)",
                              record.student_name, record.theme_tags)
                    continue

                sid = record.student_id
                body = texts.get(sid, "")

                progress(f"Observing {i + 1}/{total}: {record.student_name}...")

                # Build longitudinal context from prior runs
                _traj_ctx = ""
                try:
                    _cur_es = record.engagement_signals or {}
                    _traj_ctx = build_trajectory_context(
                        self._store,
                        student_id=sid,
                        course_id=str(course_id),
                        current_run_id=run_id,
                        current_word_count=record.word_count,
                        current_submitted_at=record.submitted_at or "",
                        current_register=record.emotional_register or "",
                        current_engagement_depth=(
                            _cur_es.get("engagement_depth")
                            if isinstance(_cur_es, dict) else None
                        ),
                        current_unknown_word_rate=record.unknown_word_rate,
                        current_linguistic_assets=record.linguistic_assets,
                        current_theme_tags=record.theme_tags,
                        current_personal_connections=record.personal_connections,
                        current_readings_referenced=record.readings_referenced,
                    )
                except Exception as _tc_err:
                    log.debug("Trajectory context skipped for %s: %s",
                              record.student_name, _tc_err)

                obs_text = observe_student(
                    backend,
                    student_name=record.student_name,
                    submission_text=body,
                    class_context=class_reading,
                    assignment=assignment_prompt,
                    is_ai_flagged=(sid in _ai_flagged_ids),
                    teacher_lens=_teacher_lens,
                    trajectory_context=_traj_ctx,
                )
                observations_map[sid] = obs_text

                # Store on the record
                record.observation = obs_text
                self._store.save_coding(
                    run_id, sid, record.student_name, record.model_dump_json()
                )

                if throttle > 0 and i < total - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "observations")
            self._emit_timing(timing_callback, "observations", _stage_t0)

            if stop_after == "observations":
                self._store.complete_run(run_id)
                self._stop_sleep_prevention()
                progress("Pipeline complete (stopped after observations).")
                return run_id

            # Release MLX model between observations → themes
            if backend and backend.name == "mlx":
                self._unload_mlx()

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 6: Theme generation
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.theme_generator import generate_themes

            progress("Generating themes...")

            theme_set = generate_themes(
                coding_records,
                tier=model_tier,
                backend=backend,
                assignment_name=assignment_name,
                analysis_lens=analysis_lens,
                teacher_interests=teacher_interests,
                profile_fragment=profile_fragment,
            )

            self._store.save_themes(
                run_id, theme_set_json=theme_set.model_dump_json()
            )
            self._store.complete_stage(run_id, "themes")
            self._emit_timing(timing_callback, "themes", _stage_t0)

            # Emit themes and contradictions for live preview
            emit_result("stage", {"stage": "THEMES IDENTIFIED"})
            for t in theme_set.themes:
                emit_result("theme", t.model_dump() if hasattr(t, "model_dump") else t)
            for c in theme_set.contradictions:
                emit_result("contradiction", c.model_dump() if hasattr(c, "model_dump") else c)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 7: Outlier surfacing
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            from insights.theme_generator import surface_outliers

            progress("Surfacing outliers...")

            outlier_report = surface_outliers(
                theme_set,
                coding_records,
                qa_result.embedding_outlier_ids,
                tier=model_tier,
                backend=backend,
                assignment_name=assignment_name,
            )

            self._store.save_themes(
                run_id, outlier_report_json=outlier_report.model_dump_json()
            )
            self._store.complete_stage(run_id, "outliers")
            self._emit_timing(timing_callback, "outliers", _stage_t0)

            # Emit outliers for live preview
            emit_result("stage", {"stage": "OUTLIERS — UNIQUE VOICES"})
            for o in outlier_report.outliers:
                emit_result("outlier", o.model_dump() if hasattr(o, "model_dump") else o)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 8: Observation-based synthesis
            # Reads all per-student observations and produces a teacher-facing
            # class summary. Replaces the former guided synthesis chain.
            # ----------------------------------------------------------
            from insights.llm_backend import send_text
            from insights.prompts import (
                OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                OBSERVATION_SYNTHESIS_PROMPT,
                OBSERVATION_SYNTHESIS_FORWARD_LOOKING,
            )

            _stage_t0 = time.time()
            if observations_map:
                progress("Generating observation-based class summary...")

                _obs_formatted = ""
                for sid, obs in observations_map.items():
                    _rec = next((r for r in coding_records if r.student_id == sid), None)
                    _name = _rec.student_name if _rec else sid
                    _obs_formatted += f"\n**{_name}** ({sid}):\n{obs}\n"

                # P7: Elevated insights — pre-rank students for synthesis
                def _insight_score(rec):
                    score = 0
                    reaching = rec.what_student_is_reaching_for or ""
                    if reaching:
                        score += min(len(reaching.split()) / 15, 2.0)
                    score += min(len(rec.notable_quotes), 3)
                    score += min(len(rec.concepts_applied), 2)
                    score += min(len(rec.personal_connections), 2)
                    if rec.emotional_register in ("passionate", "urgent", "personal"):
                        score += 0.5
                    return score

                _ranked = sorted(coding_records, key=_insight_score, reverse=True)
                _top = _ranked[:8]
                _insight_block = ""
                if any(_insight_score(r) > 1 for r in _top):
                    _il = ["ELEVATED INSIGHTS (students with richest engagement signals):"]
                    for r in _top:
                        s = _insight_score(r)
                        if s <= 1:
                            break
                        reaching = r.what_student_is_reaching_for or ""
                        _il.append(
                            f"- {r.student_name}: reaching_for={'yes' if reaching else 'no'}, "
                            f"quotes={len(r.notable_quotes)}, concepts={len(r.concepts_applied)}, "
                            f"register={r.emotional_register or 'unknown'}"
                        )
                        if reaching:
                            _il.append(f"  → {reaching}")
                    _insight_block = "\n".join(_il) + "\n"

                _combined_lens = _teacher_lens
                if _insight_block:
                    _combined_lens += (
                        "\nTEACHER LENS — Pre-ranked engagement signals from coding stage:\n"
                        + _insight_block
                        + "Use this to inform your Exceptional Contributions section, but "
                        "trust your own reading of the observations over these signals.\n"
                    )

                _fwd = ""
                _next_week = next_week_topic or self._settings.get("insights_next_week_topic", "")
                if _next_week:
                    _fwd = OBSERVATION_SYNTHESIS_FORWARD_LOOKING.format(
                        next_week_topic=_next_week
                    )

                # Class-wide trajectory for synthesis context
                _class_traj = ""
                try:
                    from insights.class_trajectory_context import (
                        build_class_trajectory_context,
                    )
                    _class_traj = build_class_trajectory_context(
                        self._store,
                        course_id=str(course_id),
                        current_run_id=run_id,
                    )
                except Exception as _ct_err:
                    log.debug("Class trajectory context skipped: %s", _ct_err)

                _synth_prompt = OBSERVATION_SYNTHESIS_PROMPT.format(
                    assignment=assignment_prompt,
                    class_context=class_reading,
                    class_trajectory=_class_traj,
                    observations=_obs_formatted,
                    teacher_lens=_combined_lens,
                    forward_looking=_fwd,
                )

                try:
                    obs_synthesis = send_text(
                        backend, _synth_prompt,
                        OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                        max_tokens=2000,
                    )

                    # Store as a special synthesis record
                    self._store.save_themes(
                        run_id,
                        observation_synthesis=obs_synthesis.strip(),
                    )
                    log.info("Observation synthesis: %d words", len(obs_synthesis.split()))
                except Exception as exc:
                    log.warning("Observation synthesis failed: %s", exc)

            # Optional cloud enhancement (FERPA-safe: anonymized patterns only)
            try:
                from insights.synthesizer import run_cloud_enhancement
                _cloud_narrative = run_cloud_enhancement(
                    coding_records, assignment_name, self._settings
                )
                if _cloud_narrative:
                    self._store.save_themes(
                        run_id, synthesis_report_json=_cloud_narrative
                    )
            except Exception as _ce:
                log.warning("Cloud enhancement failed (non-fatal): %s", _ce)

            self._store.complete_stage(run_id, "synthesis")
            self._emit_timing(timing_callback, "observation_synthesis", _stage_t0)

            # ----------------------------------------------------------
            # Stage 9: Draft student feedback (if enabled)
            # ----------------------------------------------------------
            _stage_t0 = time.time()
            if not skip_feedback and backend:
                from insights.feedback_drafter import FeedbackDrafter

                progress("Drafting feedback for students...")
                drafter = FeedbackDrafter()
                profile = self._load_teacher_profile()

                for i, record in enumerate(coding_records):
                    if self._cancelled:
                        return None

                    progress(
                        f"Drafting feedback {i + 1}/{len(coding_records)}: "
                        f"{record.student_name}..."
                    )

                    record_dict = record.model_dump()
                    preprocessing_meta = record_dict.get("preprocessing")
                    if preprocessing_meta and isinstance(preprocessing_meta, dict):
                        pass  # already a dict
                    else:
                        # Pull from submission metadata
                        sub_meta = meta.get(record.student_id, {})
                        preprocessing_meta = {
                            "was_translated": sub_meta.get("was_translated", False),
                            "was_transcribed": sub_meta.get("was_transcribed", False),
                            "original_language_name": sub_meta.get(
                                "original_language_name"
                            ),
                        }

                    draft = drafter.draft_feedback(
                        coding_record=record_dict,
                        assignment_prompt=assignment_prompt,
                        analysis_lens=analysis_lens,
                        preprocessing_meta=preprocessing_meta,
                        teacher_profile=profile,
                        tier=model_tier,
                        backend=backend,
                    )

                    self._store.save_feedback(
                        run_id=run_id,
                        student_id=record.student_id,
                        student_name=record.student_name,
                        draft_text=draft.feedback_text,
                        confidence=draft.confidence,
                    )

                    if throttle > 0 and i < len(coding_records) - 1:
                        time.sleep(throttle)

                self._store.complete_stage(run_id, "feedback")
            self._emit_timing(timing_callback, "feedback", _stage_t0)

            # ----------------------------------------------------------
            # Complete run
            # ----------------------------------------------------------
            confidence = self._compute_full_confidence(
                qa_result, coding_records, theme_set,
                outlier_report=outlier_report,
            )
            self._store.complete_run(run_id, confidence)
            progress("Analysis complete.")
            self._stop_sleep_prevention()

            return run_id

        except Exception as e:
            log.exception("Analysis pipeline failed: %s", e)
            progress(f"Error: {e}")
            self._stop_sleep_prevention()
            return None


    def run_partial(
        self,
        *,
        run_id: str,
        start_stage: str,
        progress_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Re-run pipeline from start_stage forward using existing data.

        start_stage: "themes" | "outliers" | "synthesis"
        Returns run_id on success, None on failure.
        """
        progress = progress_callback or (lambda msg: None)
        self._cancelled = False

        run = self._store.get_run(run_id)
        if not run:
            progress("Run not found.")
            return None

        from insights.teacher_profile import TeacherProfileManager
        _profile_id = run.get("course_profile_id", "default") or "default"
        profile_mgr = TeacherProfileManager(self._store, _profile_id)
        profile_fragment = profile_mgr.get_full_profile_fragment()

        try:
            from insights.llm_backend import auto_detect_backend

            model_tier = run.get("model_tier", "lightweight")
            backend = auto_detect_backend(model_tier, self._settings)
            if backend is None:
                progress("No LLM backend available for re-run.")
                return None

            assignment_name = run.get("assignment_name", "")
            course_name = run.get("course_name", "")
            teacher_context = run.get("teacher_context", "")
            analysis_lens = run.get("analysis_lens_config")
            teacher_interests = None

            # Load existing data
            codings = self._store.get_codings(run_id)
            coding_records = []
            for row in codings:
                rec = row.get("coding_record", {})
                if isinstance(rec, str):
                    import json as _json
                    rec = _json.loads(rec)
                from insights.models import SubmissionCodingRecord
                coding_records.append(SubmissionCodingRecord.model_validate(rec))

            themes_row = self._store.get_themes(run_id)
            qa_json = run.get("quick_analysis")
            qa_result = None
            if qa_json:
                qa_result = QuickAnalysisResult.model_validate_json(qa_json)

            stages_run = []

            # Theme generation
            if start_stage in ("themes",):
                from insights.theme_generator import generate_themes
                progress("Re-generating themes...")
                theme_set = generate_themes(
                    coding_records, tier=model_tier, backend=backend,
                    assignment_name=assignment_name,
                    analysis_lens=analysis_lens,
                    teacher_interests=teacher_interests,
                    profile_fragment=profile_fragment,
                )
                self._store.save_themes(
                    run_id, theme_set_json=theme_set.model_dump_json()
                )
                self._store.complete_stage(run_id, "themes")
                stages_run.append("themes")
            else:
                import json as _json
                ts_raw = themes_row.get("theme_set", "{}") if themes_row else "{}"
                from insights.models import ThemeSet
                theme_set = ThemeSet.model_validate_json(ts_raw)

            if self._cancelled:
                return None

            # Outlier surfacing
            if start_stage in ("themes", "outliers"):
                from insights.theme_generator import surface_outliers
                progress("Re-surfacing outliers...")
                embedding_ids = qa_result.embedding_outlier_ids if qa_result else []
                outlier_report = surface_outliers(
                    theme_set, coding_records, embedding_ids,
                    tier=model_tier, backend=backend,
                    assignment_name=assignment_name,
                )
                self._store.save_themes(
                    run_id, outlier_report_json=outlier_report.model_dump_json()
                )
                self._store.complete_stage(run_id, "outliers")
                stages_run.append("outliers")
            else:
                import json as _json
                or_raw = themes_row.get("outlier_report", "{}") if themes_row else "{}"
                from insights.models import OutlierReport
                outlier_report = OutlierReport.model_validate_json(or_raw)

            if self._cancelled:
                return None

            # Observation synthesis — rebuild from stored observations + class reading.
            if start_stage in ("themes", "outliers", "synthesis"):
                from insights.llm_backend import send_text as _send
                from insights.prompts import (
                    OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                    OBSERVATION_SYNTHESIS_PROMPT,
                )

                observations_map = {
                    r.student_id: r.observation
                    for r in coding_records
                    if r.observation
                }
                if observations_map:
                    progress("Generating observation-based class summary...")
                    _obs_formatted = ""
                    for sid, obs in observations_map.items():
                        _rec = next((r for r in coding_records if r.student_id == sid), None)
                        _name = _rec.student_name if _rec else sid
                        _obs_formatted += f"\n**{_name}** ({sid}):\n{obs}\n"

                    _class_reading = self._store.get_class_reading(run_id) or ""
                    _synth_prompt = OBSERVATION_SYNTHESIS_PROMPT.format(
                        assignment=assignment_name,
                        class_context=_class_reading,
                        class_trajectory="",
                        observations=_obs_formatted,
                        teacher_lens="",
                        forward_looking="",
                    )
                    try:
                        obs_synthesis = _send(
                            backend, _synth_prompt,
                            OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                            max_tokens=2000,
                        )
                        self._store.save_themes(
                            run_id, observation_synthesis=obs_synthesis.strip()
                        )
                        log.info("Observation synthesis: %d words", len(obs_synthesis.split()))
                    except Exception as _exc:
                        log.warning("Observation synthesis failed (non-fatal): %s", _exc)

            self._store.complete_stage(run_id, "synthesis")
            stages_run.append("synthesis")

            if self._cancelled:
                return None

            # Feedback drafting
            if start_stage in ("themes", "outliers", "synthesis", "feedback"):
                from insights.feedback_drafter import FeedbackDrafter
                drafter = FeedbackDrafter()
                profile = self._load_teacher_profile()
                progress("Drafting feedback for students...")
                for i, record in enumerate(coding_records):
                    if self._cancelled:
                        return None
                    progress(
                        f"Drafting feedback {i + 1}/{len(coding_records)}: "
                        f"{record.student_name}..."
                    )
                    draft = drafter.draft_feedback(
                        coding_record=record.model_dump(),
                        assignment_prompt=assignment_name,
                        analysis_lens=analysis_lens,
                        preprocessing_meta={"was_translated": False, "was_transcribed": False},
                        teacher_profile=profile,
                        tier=model_tier,
                        backend=backend,
                    )
                    self._store.save_feedback(
                        run_id=run_id,
                        student_id=record.student_id,
                        student_name=record.student_name,
                        draft_text=draft.feedback_text,
                        confidence=draft.confidence,
                    )

            self._store.complete_stage(run_id, "feedback")
            stages_run.append("feedback")

            self._store.complete_run(run_id)
            progress(f"Re-run complete ({', '.join(stages_run)}).")
            return run_id

        except Exception as e:
            log.exception("Partial re-run failed: %s", e)
            progress(f"Re-run error: {e}")
            return None

    def resume_run(
        self,
        *,
        run_id: str,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Resume an interrupted run from where it stopped.

        Skips already-coded students, then runs remaining stages.
        Returns run_id on success, None on failure.
        """
        progress = progress_callback or (lambda msg: None)
        emit_result = result_callback or (lambda t, d: None)
        self._cancelled = False
        self._start_sleep_prevention()

        run = self._store.get_run(run_id)
        if not run:
            progress("Run not found.")
            return None

        import json as _json
        stages = run.get("stages_completed", [])
        if isinstance(stages, str):
            stages = _json.loads(stages)
        completed_set = set(stages)

        progress(f"Resuming run — completed stages: {', '.join(stages)}")

        try:
            from insights.llm_backend import auto_detect_backend
            from insights.teacher_profile import TeacherProfileManager

            model_tier = run.get("model_tier", "lightweight")
            backend = auto_detect_backend(model_tier, self._settings)
            if backend is None:
                progress("No LLM backend available.")
                self._stop_sleep_prevention()
                return None

            progress(f"LLM backend: {backend.name} ({backend.model})")

            _profile_id = run.get("course_profile_id", "default") or "default"
            profile_mgr = TeacherProfileManager(self._store, _profile_id)
            profile_fragment = profile_mgr.get_full_profile_fragment()

            assignment_name = run.get("assignment_name", "")
            course_name = run.get("course_name", "")
            teacher_context = run.get("teacher_context", "")
            analysis_lens = run.get("analysis_lens_config")
            teacher_interests = None
            assignment_prompt = f"Assignment: {assignment_name}"

            qa_json = run.get("quick_analysis")
            qa_result = None
            if qa_json:
                qa_result = QuickAnalysisResult.model_validate_json(qa_json)

            throttle = float(self._settings.get("insights_throttle_delay", 2.0))

            # Load existing codings
            existing_codings = self._store.get_codings(run_id)
            coded_sids = set()
            coding_records = []
            for row in existing_codings:
                rec = row.get("coding_record", {})
                if isinstance(rec, str):
                    rec = _json.loads(rec)
                coding_records.append(
                    SubmissionCodingRecord.model_validate(rec)
                )
                coded_sids.add(row.get("student_id", ""))

            # Build texts dict from stored submission_text column
            # (available for any student already coded)
            texts: Dict[str, str] = {}
            for row in existing_codings:
                sid = row.get("student_id", "")
                sub_text = row.get("submission_text", "")
                if sub_text:
                    texts[sid] = sub_text

            total = run.get("total_submissions", 0)

            # ----------------------------------------------------------
            # If coding is not complete, re-fetch and code remaining
            # ----------------------------------------------------------
            if "coding" not in completed_set:
                if not self._api:
                    progress(
                        "Cannot resume mid-coding — Canvas API not available. "
                        "Re-open with Canvas connection to resume."
                    )
                    self._stop_sleep_prevention()
                    return None

                course_id = run.get("course_id")
                assignment_id = run.get("assignment_id")
                progress(
                    f"Re-fetching submissions to resume coding "
                    f"({len(coded_sids)} already done)..."
                )

                fetcher = DataFetcher(self._api)
                raw_submissions = fetcher.fetch_submissions(course_id, assignment_id)
                if not raw_submissions:
                    # Try as discussion topic
                    assign_info = fetcher.fetch_assignment_info(course_id, assignment_id)
                    topic_id = None
                    if assign_info:
                        topic_id = assign_info.get("discussion_topic", {}).get("id")
                    if topic_id:
                        raw_submissions = fetcher.fetch_discussion_entries(
                            course_id, topic_id
                        )
                if not raw_submissions:
                    progress(
                        "Could not re-fetch submissions from Canvas. "
                        "Check your connection and try again."
                    )
                    self._stop_sleep_prevention()
                    return None

                # Build meta map; supplement texts for any newly-fetched sids
                meta_map: Dict[str, Dict] = {}
                for sub in raw_submissions:
                    sid = str(sub.get("student_id", sub.get("user_id", "")))
                    meta_map[sid] = sub
                    if sid not in texts:
                        body = sub.get("body") or sub.get("text") or ""
                        texts[sid] = _strip_html(body)

                total = len(texts)
                uncoded_items = [
                    (sid, texts[sid]) for sid in texts if sid not in coded_sids
                ]
                progress(
                    f"Resuming coding: {len(coded_sids)} done, "
                    f"{len(uncoded_items)} remaining of {total}..."
                )
                emit_result("stage", {"stage": "RESUMING — LISTENING TO STUDENT WORK"})

                from insights.submission_coder import code_submission_reading_first

                # Build class context for resume path
                _resume_stats = qa_result.stats if qa_result else None
                _resume_class_context = ""
                if _resume_stats and _resume_stats.total_submissions > 0:
                    _resume_class_context = (
                        f"Class has {_resume_stats.total_submissions} submissions. "
                        f"Typical word count: {int(_resume_stats.word_count_median)} words "
                        f"(range {_resume_stats.word_count_min}–{_resume_stats.word_count_max})."
                    )

                initial_coded_count = len(coded_sids)
                for i, (sid, body) in enumerate(uncoded_items):
                    if self._cancelled:
                        self._stop_sleep_prevention()
                        return None

                    sub_meta = meta_map.get(sid, {})
                    name = sub_meta.get("student_name", f"Student {sid}")
                    quick_sub = qa_result.per_submission.get(sid) if qa_result else None
                    vader_compound = (
                        qa_result.sentiments.get(sid, {}).get("compound", 0.0)
                        if qa_result else 0.0
                    )
                    wc = len(body.split())
                    median_wc = qa_result.stats.word_count_median if qa_result else 0
                    sig_results = signal_matrix_classify(
                        body, vader_compound, wc, median_wc
                    )

                    overall_idx = initial_coded_count + i + 1
                    progress(f"Reading student work ({overall_idx}/{total}): {name}...")
                    emit_result("reading", {
                        "student_name": name,
                        "text": body[:500],
                        "word_count": wc,
                    })

                    if wc < 15:
                        sub_type = sub_meta.get("submission_type", "")
                        attachments = sub_meta.get("attachments", [])
                        if wc == 0 and sub_type == "online_upload" and attachments:
                            tag, reason = _diagnose_skip(attachments)
                        elif wc == 0 and not body.strip():
                            reason = "blank submission (no text entered)"
                            tag = "blank submission"
                        else:
                            reason = f"only {wc} words"
                            tag = "insufficient text for analysis"
                        log.warning("Skipping %s: %s", name, reason)
                        progress(f"  Skipping {name}: {reason}")
                        record = SubmissionCodingRecord(
                            student_id=sid, student_name=name,
                            theme_tags=[tag], theme_confidence={tag: 1.0},
                            emotional_register="", emotional_notes=reason,
                            notable_quotes=[], word_count=wc,
                        )
                    elif quick_sub and quick_sub.is_gibberish:
                        progress(
                            f"  Skipping {name}: gibberish ({quick_sub.gibberish_reason})"
                        )
                        record = SubmissionCodingRecord(
                            student_id=sid, student_name=name,
                            theme_tags=["non-analyzable text"],
                            theme_confidence={"non-analyzable text": 1.0},
                            emotional_register="",
                            emotional_notes=f"Gibberish gate: {quick_sub.gibberish_detail}",
                            notable_quotes=[], word_count=wc,
                        )
                    else:
                        # Build linguistic context for resume path
                        _resume_ling_note = ""
                        if quick_sub and hasattr(quick_sub, "linguistic_repertoire"):
                            _rep = quick_sub.linguistic_repertoire
                            if _rep and hasattr(_rep, "llm_context_note") and _rep.llm_context_note:
                                _resume_ling_note = _rep.llm_context_note

                        record = code_submission_reading_first(
                            submission_text=body,
                            student_id=sid, student_name=name,
                            assignment_prompt=assignment_prompt,
                            backend=backend,
                            analysis_lens=analysis_lens,
                            class_context=_resume_class_context,
                            linguistic_context=_resume_ling_note,
                        )

                    # Persist Canvas metadata for trajectory comparator
                    record.submitted_at = sub_meta.get("submitted_at")
                    record.submission_url = _submission_url(sid)
                    if quick_sub:
                        record.unknown_word_rate = quick_sub.unknown_word_rate

                    coding_records.append(record)
                    coded_sids.add(sid)
                    self._store.save_coding(
                        run_id, sid, name, record.model_dump_json(),
                        submission_text=body,
                    )
                    # Surface prior engagement context for skip cards in the GUI
                    if _is_skip_record(record):
                        try:
                            from insights.trajectory_context import build_trajectory_context
                            _traj = build_trajectory_context(
                                self._store, student_id=sid,
                                course_id=str(course_id) if course_id else "",
                                current_run_id=run_id, current_word_count=wc,
                                current_submitted_at=record.submitted_at or "",
                            )
                            if _traj:
                                record.observation = _traj
                                self._store.save_coding(
                                    run_id, sid, name, record.model_dump_json(),
                                    submission_text=body,
                                )
                        except Exception:
                            pass
                    preview_data = record.model_dump()
                    preview_data["_original_text"] = body[:300]
                    emit_result("coding", preview_data)

                    if throttle > 0 and i < len(uncoded_items) - 1:
                        time.sleep(throttle)

                self._store.complete_stage(run_id, "coding")
                progress("Coding complete.")

                if self._cancelled:
                    self._stop_sleep_prevention()
                    return None

            # ----------------------------------------------------------
            # If wellbeing classification not complete, run it
            # ----------------------------------------------------------
            if "wellbeing" not in completed_set:
                if not texts:
                    for row in existing_codings:
                        sid = row.get("student_id", "")
                        sub_text = row.get("submission_text", "")
                        if sub_text:
                            texts[sid] = sub_text

                if texts and coding_records:
                    from insights.submission_coder import classify_wellbeing

                    progress("Running wellbeing classification...")
                    for i, record in enumerate(coding_records):
                        if self._cancelled:
                            self._stop_sleep_prevention()
                            return None

                        sid = record.student_id
                        body = texts.get(sid, "")

                        progress(
                            f"Wellbeing {i + 1}/{len(coding_records)}: "
                            f"{record.student_name}..."
                        )

                        wb = classify_wellbeing(
                            backend,
                            student_name=record.student_name,
                            submission_text=body,
                            assignment_prompt=assignment_prompt,
                        )
                        record.wellbeing_axis = wb["axis"]
                        record.wellbeing_signal = wb["signal"]
                        record.wellbeing_confidence = wb["confidence"]

                        self._store.save_coding(
                            run_id, sid, record.student_name,
                            record.model_dump_json(),
                        )

                        if throttle > 0 and i < len(coding_records) - 1:
                            time.sleep(throttle)

                    self._store.complete_stage(run_id, "wellbeing")
                    progress("Wellbeing classification complete.")
                else:
                    self._store.complete_stage(run_id, "wellbeing")

                if self._cancelled:
                    self._stop_sleep_prevention()
                    return None

            # ----------------------------------------------------------
            # If CHECK-IN not complete, run it on ENGAGED students
            # ----------------------------------------------------------
            if "checkin" not in completed_set:
                if not texts:
                    for row in existing_codings:
                        sid = row.get("student_id", "")
                        sub_text = row.get("submission_text", "")
                        if sub_text:
                            texts[sid] = sub_text

                if texts and coding_records:
                    from dataclasses import replace as _dc_replace
                    from insights.submission_coder import classify_checkin

                    checkin_backend = _dc_replace(backend, temperature=0.3)

                    engaged_records = [
                        r for r in coding_records
                        if r.wellbeing_axis == "ENGAGED"
                    ]
                    progress(
                        f"Running CHECK-IN on {len(engaged_records)} "
                        f"ENGAGED students..."
                    )

                    for i, record in enumerate(engaged_records):
                        if self._cancelled:
                            self._stop_sleep_prevention()
                            return None

                        sid = record.student_id
                        body = texts.get(sid, "")

                        progress(
                            f"CHECK-IN {i + 1}/{len(engaged_records)}: "
                            f"{record.student_name}..."
                        )

                        ci = classify_checkin(
                            checkin_backend,
                            student_name=record.student_name,
                            submission_text=body,
                            assignment_prompt=assignment_prompt,
                        )
                        record.checkin_flag = ci["check_in"]
                        record.checkin_reasoning = ci["reasoning"]

                        self._store.save_coding(
                            run_id, sid, record.student_name,
                            record.model_dump_json(),
                        )

                        if throttle > 0 and i < len(engaged_records) - 1:
                            time.sleep(throttle)

                    self._store.complete_stage(run_id, "checkin")
                    progress("CHECK-IN complete.")
                else:
                    self._store.complete_stage(run_id, "checkin")

                if self._cancelled:
                    self._stop_sleep_prevention()
                    return None

            # ----------------------------------------------------------
            # If observations not complete, run them
            # ----------------------------------------------------------
            if "observations" not in completed_set:
                if not texts:
                    for row in existing_codings:
                        sid = row.get("student_id", "")
                        sub_text = row.get("submission_text", "")
                        if sub_text:
                            texts[sid] = sub_text

                if texts and coding_records:
                    from insights.submission_coder import observe_student
                    from insights.trajectory_context import (
                        build_trajectory_context,
                    )

                    _resume_class_reading = self._store.get_class_reading(run_id)
                    _resume_teacher_lens = ""
                    _tl_raw = self._settings.get("insights_teacher_lens", "")
                    if _tl_raw:
                        _resume_teacher_lens = (
                            f"TEACHER'S OBSERVATION PRIORITIES:\n{_tl_raw}\n"
                        )

                    _resume_course_id = str(run.get("course_id", "0"))

                    progress("Generating per-student observations...")
                    for i, record in enumerate(coding_records):
                        if self._cancelled:
                            self._stop_sleep_prevention()
                            return None

                        sid = record.student_id
                        # Skip if observation already populated (partial resume)
                        if record.observation:
                            continue

                        body = texts.get(sid, "")
                        progress(
                            f"Observing {i + 1}/{len(coding_records)}: "
                            f"{record.student_name}..."
                        )

                        # Build longitudinal context from prior runs
                        _traj_ctx = ""
                        try:
                            _cur_es = record.engagement_signals or {}
                            _traj_ctx = build_trajectory_context(
                                self._store,
                                student_id=sid,
                                course_id=_resume_course_id,
                                current_run_id=run_id,
                                current_word_count=record.word_count,
                                current_submitted_at=record.submitted_at or "",
                                current_register=record.emotional_register or "",
                                current_engagement_depth=(
                                    _cur_es.get("engagement_depth")
                                    if isinstance(_cur_es, dict) else None
                                ),
                                current_unknown_word_rate=record.unknown_word_rate,
                                current_linguistic_assets=record.linguistic_assets,
                                current_theme_tags=record.theme_tags,
                                current_personal_connections=record.personal_connections,
                                current_readings_referenced=record.readings_referenced,
                            )
                        except Exception as _tc_err:
                            log.debug(
                                "Trajectory context skipped for %s: %s",
                                record.student_name, _tc_err,
                            )

                        obs_text = observe_student(
                            backend,
                            student_name=record.student_name,
                            submission_text=body,
                            class_context=_resume_class_reading,
                            assignment=assignment_prompt,
                            teacher_lens=_resume_teacher_lens,
                            trajectory_context=_traj_ctx,
                        )
                        record.observation = obs_text
                        self._store.save_coding(
                            run_id, sid, record.student_name,
                            record.model_dump_json(),
                        )

                        if throttle > 0 and i < len(coding_records) - 1:
                            time.sleep(throttle)

                    self._store.complete_stage(run_id, "observations")
                    progress("Observations complete.")
                else:
                    self._store.complete_stage(run_id, "observations")

                if self._cancelled:
                    self._stop_sleep_prevention()
                    return None

            # ----------------------------------------------------------
            # Determine which downstream stage to resume from
            # ----------------------------------------------------------
            if "themes" not in completed_set:
                start = "themes"
            elif "outliers" not in completed_set:
                start = "outliers"
            elif "synthesis" not in completed_set:
                start = "synthesis"
            elif "feedback" not in completed_set:
                start = "feedback"
            else:
                progress("All stages already complete.")
                self._stop_sleep_prevention()
                return run_id

            progress(f"Resuming from {start}...")
            result = self.run_partial(
                run_id=run_id,
                start_stage=start,
                progress_callback=progress_callback,
            )

            self._stop_sleep_prevention()
            return result

        except Exception as e:
            log.exception("Resume run failed: %s", e)
            progress(f"Resume error: {e}")
            self._stop_sleep_prevention()
            return None

    def _preprocess(
        self,
        raw_submissions: List[Dict],
        *,
        translate_enabled: bool,
        transcribe_enabled: bool,
        progress: Callable,
    ) -> List[Dict]:
        """Run the preprocessing pipeline on raw Canvas submissions."""
        try:
            from preprocessing import PreprocessingPipeline
        except ImportError:
            log.info("Preprocessing pipeline not available — using raw text")
            progress("Preprocessing pipeline not available — using raw text.")
            return raw_submissions

        s = self._settings
        whisper_model = s.get("insights_whisper_model", "medium")
        translation_backend = s.get("insights_translation_backend", "ollama")
        translation_model = s.get("insights_translation_model", "llama3.1:8b")
        handwriting_enabled = s.get("insights_handwriting_enabled", False)

        canvas_headers = {}
        if self._api:
            canvas_headers = dict(self._api.headers)

        # Auto-enable image transcription if a vision model is available,
        # regardless of the handwriting toggle — we want to capture all
        # image submissions, not just handwritten ones.
        if not handwriting_enabled:
            try:
                from preprocessing.image_transcriber import ImageTranscriber
                _it = ImageTranscriber(
                    backend=s.get("insights_llm_backend", translation_backend),
                    model=s.get("insights_mlx_vision_model",
                                "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"),
                    ollama_base_url=s.get("insights_ollama_url",
                                          "http://localhost:11434"),
                )
                if _it.is_available():
                    handwriting_enabled = True
                    log.info("Auto-enabled image analysis (vision model available)")
            except Exception:
                pass

        try:
            pipeline = PreprocessingPipeline(
                canvas_headers=canvas_headers,
                translation_enabled=translate_enabled,
                transcription_enabled=transcribe_enabled,
                image_transcription_enabled=handwriting_enabled,
                whisper_model=whisper_model,
                translation_backend=translation_backend,
                translation_model=translation_model,
            )
            results = pipeline.process_submissions(
                raw_submissions,
                progress_callback=lambda cur, tot, msg: progress(
                    f"Preprocessing ({cur + 1}/{tot}): {msg}"
                ),
            )
        except Exception as e:
            log.warning("Preprocessing failed, falling back to raw text: %s", e)
            progress(f"Preprocessing failed ({e}) — using raw text.")
            return raw_submissions

        enriched = []
        for sub, result in zip(raw_submissions, results):
            sub = dict(sub)
            sub["body"] = result.text
            sub["was_translated"] = result.was_translated
            sub["was_transcribed"] = result.was_transcribed
            sub["was_image_transcribed"] = result.was_image_transcribed
            sub["original_language_name"] = result.original_language_name
            sub["original_text"] = result.original_text
            sub["multilingual_type"] = result.multilingual_type
            sub["detected_languages"] = result.detected_languages
            if result.teacher_comment:
                sub["preprocessing_comment"] = result.teacher_comment
            enriched.append(sub)

        return enriched

    def _load_teacher_profile(self) -> Optional[dict]:
        """Load the teacher profile for feedback generation."""
        from insights.teacher_profile import TeacherProfileManager
        try:
            mgr = TeacherProfileManager(self._store)
            return mgr.profile.model_dump()
        except Exception:
            return None

    def _compute_confidence(self, result: QuickAnalysisResult) -> float:
        """Compute confidence from Quick Analysis alone."""
        factors = []

        n = result.stats.total_submissions
        if n >= 20:
            factors.append(1.0)
        elif n >= 10:
            factors.append(0.8)
        elif n >= 5:
            factors.append(0.6)
        else:
            factors.append(0.4)

        components_run = 0
        if result.top_terms:
            components_run += 1
        if result.tfidf_terms:
            components_run += 1
        if result.sentiments:
            components_run += 1
        if result.clusters:
            components_run += 1
        if result.keyword_hits:
            components_run += 1
        if result.named_entities:
            components_run += 1
        factors.append(min(1.0, components_run / 6))

        return round(sum(factors) / len(factors), 2) if factors else 0.0

    def _compute_full_confidence(
        self,
        qa: QuickAnalysisResult,
        records: List[SubmissionCodingRecord],
        theme_set,
        outlier_report=None,
    ) -> dict:
        """Compute full pipeline confidence after all LLM stages.

        Enhanced in Phase 5 with cross-validation and synthesis coverage.
        """
        data_quality = self._compute_confidence(qa)

        # Coding reliability: how many records have non-empty theme tags
        coded = sum(1 for r in records if r.theme_tags)
        coding_reliability = coded / max(len(records), 1)

        # Theme coherence: what % of students appear in at least one theme
        themed_ids = set()
        for t in theme_set.themes:
            themed_ids.update(t.student_ids)
        all_ids = {r.student_id for r in records}
        orphan_rate = 1.0 - (len(themed_ids) / max(len(all_ids), 1))
        theme_coherence = (1.0 - orphan_rate)

        # Cross-validation concerns
        concern_notes: list = []
        try:
            from insights.cross_validator import CrossValidator
            cv = CrossValidator()
            concern_flags = cv.validate_concerns(records, qa.concern_signals)
            disagreements = [f for f in concern_flags if f.agreement != "agree"]
            if disagreements:
                concern_notes.append(
                    f"LLM and signal matrix disagreed on {len(disagreements)} concern flag(s)"
                )

            # Theme vs embedding cluster validation
            if theme_set and hasattr(theme_set, "themes") and qa.clusters:
                theme_flags = cv.validate_themes(
                    [t.model_dump() if hasattr(t, "model_dump") else t
                     for t in theme_set.themes],
                    qa.clusters,
                )
                low_overlap = [f for f in theme_flags if "low overlap" in (f.confidence_note or "").lower()]
                if low_overlap:
                    concern_notes.append(
                        f"{len(low_overlap)} theme(s) don't align well with "
                        f"embedding clusters — may reflect LLM interpretation "
                        f"rather than actual submission groupings"
                    )

            # Outlier cross-validation (with actual LLM outliers)
            llm_outliers = []
            if outlier_report and hasattr(outlier_report, "outliers"):
                llm_outliers = [
                    o.model_dump() if hasattr(o, "model_dump") else o
                    for o in outlier_report.outliers
                ]
            outlier_flags = cv.validate_outliers(
                llm_outliers,
                qa.embedding_outlier_ids,
            )
            embed_only = [f for f in outlier_flags if f.agreement == "matrix_only"]
            if embed_only:
                concern_notes.append(
                    f"{len(embed_only)} embedding outlier(s) not surfaced by LLM"
                )
        except Exception:
            log.debug("Cross-validation skipped", exc_info=True)

        # Data quality notes
        n_subs = qa.stats.total_submissions
        n_enrolled = qa.stats.total_enrollment
        if n_enrolled > 0 and n_subs < n_enrolled * 0.7:
            concern_notes.append(
                f"Only {n_subs}/{n_enrolled} students submitted — "
                f"analysis may not represent the full class"
            )

        overall = round(
            (data_quality + coding_reliability + theme_coherence) / 3, 2
        )

        return {
            "overall": overall,
            "data_quality": round(data_quality, 2),
            "coding_reliability": round(coding_reliability, 2),
            "theme_coherence": round(theme_coherence, 2),
            "concerns": concern_notes,
        }
