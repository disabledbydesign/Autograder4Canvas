"""
Research engine: 3-way classification comparison orchestrator.

Runs three independent classification tracks on the same student data
for a paper comparing binary concern detection, 4-axis wellbeing
classification, and generative observation approaches.

Uses production pipeline functions — never duplicates them.
Does NOT write to InsightsStore (except to read prior run data).

## Two operating modes:

Mode 1 — run_comparison(): Full isolated test suite. Fetches submissions
  from Canvas, runs all shared stages, then all 3 tracks.

Mode 2 — run_track_a_only(): Fill in gaps. Accepts stored submission
  texts from a prior Insights run. Runs QuickAnalyzer (non-LLM) +
  detect_concerns() only. No Canvas fetch, no class reading.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)

_SOFTWARE_VERSION = "autograder4canvas research v1"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BackendMetadata:
    """LLM backend configuration captured at run start for reproducibility."""
    backend_name: str     # "mlx" | "ollama" | "openrouter" | "cloud" | "none"
    model_name: str       # e.g. "gemma-3-12b-it-4bit"
    temperature: float    # classifier default (Track A/B); Track C uses 0.3
    quantization: str     # "4bit" | "8bit" | "fp16" | ""


@dataclass
class TrackTiming:
    """Per-track wall-clock timing."""
    started_at: str           # ISO 8601
    completed_at: str         # ISO 8601
    duration_seconds: float
    students_processed: int


@dataclass
class TrackAResult:
    """Binary concern detection result for one student."""
    student_id: str
    student_name: str
    flagged: bool             # True if any concerns survive post-processing
    concerns: list            # List[dict] from ConcernRecord.model_dump()
    bias_warnings: list       # Concern dicts whose why_flagged has ⚠ prefix
    signal_matrix_summary: str  # Non-LLM pre-screening summary for this student


@dataclass
class TrackBResult:
    """4-axis wellbeing + CHECK-IN result for one student."""
    student_id: str
    student_name: str
    axis: str                    # CRISIS | BURNOUT | ENGAGED | NONE
    signal: str                  # Brief LLM description
    confidence: float            # 0.0–1.0
    prescan_signals: list        # Sentences found by semantic prescan
    checkin_flag: Optional[bool]  # None if student not ENGAGED (pass 2 skipped)
    checkin_reasoning: str       # Quote + competing interpretations; "" if skipped


@dataclass
class TrackCResult:
    """Generative observation for one student."""
    student_id: str
    student_name: str
    observation: str             # 3-4 sentence generative prose


@dataclass
class StudentComparison:
    """All three track results for one student."""
    student_id: str
    student_name: str
    word_count: int
    track_a: Optional[TrackAResult] = None
    track_b: Optional[TrackBResult] = None
    track_c: Optional[TrackCResult] = None


@dataclass
class ComparisonMetadata:
    """Full provenance metadata for reproducibility and paper citation."""
    run_id: str
    started_at: str                             # ISO 8601
    completed_at: str                           # ISO 8601
    total_duration_seconds: float
    backend: BackendMetadata
    track_timings: Dict[str, TrackTiming]       # "track_a" | "track_b" | "track_c"
    tracks_freshly_run: List[str]               # Tracks run in this session
    tracks_from_prior: List[str]                # Tracks loaded from prior run
    prior_run_id: Optional[str]                 # Source run_id if any tracks loaded
    pipeline_config: dict                       # throttle_delay, model_tier, etc.
    git_hash: str                               # HEAD commit hash
    software_version: str


@dataclass
class ComparisonResult:
    """Complete 3-way comparison for one assignment."""
    course_id: str
    course_name: str
    assignment_id: str
    assignment_name: str
    total_students: int
    comparisons: Dict[str, StudentComparison]  # student_id → comparison
    metadata: ComparisonMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _strip_html(text: str) -> str:
    """Minimal HTML stripping — mirrors engine._strip_html."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_output_dir() -> Path:
    try:
        from autograder_utils import get_output_base_dir
        return Path(get_output_base_dir())
    except Exception:
        return Path.home() / "Canvas Grading"


def _capture_backend_metadata(backend) -> BackendMetadata:
    if backend is None:
        return BackendMetadata(
            backend_name="none", model_name="", temperature=0.1, quantization=""
        )
    quant = ""
    model = backend.model or ""
    if "4bit" in model:
        quant = "4bit"
    elif "8bit" in model:
        quant = "8bit"
    elif "fp16" in model:
        quant = "fp16"
    return BackendMetadata(
        backend_name=backend.name,
        model_name=model,
        temperature=backend.temperature,
        quantization=quant,
    )


# ---------------------------------------------------------------------------
# ResearchEngine
# ---------------------------------------------------------------------------

class ResearchEngine:
    """Orchestrates 3-way classification comparison.

    Calls existing production functions directly — never duplicates logic.
    Does NOT write to InsightsStore (read-only access for prior run loading).
    """

    def __init__(self, api=None, store=None, settings: Optional[dict] = None):
        self._api = api
        self._store = store        # InsightsStore (read-only)
        self._settings = settings or {}
        self._cancelled = False
        # Research-panel runs are long (3-track comparison spans hundreds of
        # LLM calls). Reuse the same sleep-prevention helper the production
        # pipeline uses so the Mac doesn't suspend mid-run and deadlock MLX.
        # The helper is idempotent: if production is also running and already
        # holds caffeinate, our start() is a no-op.
        from insights.process_keepalive import SleepPreventer
        self._sleep_preventer = SleepPreventer(
            enabled=bool(self._settings.get("insights_keep_awake", True))
        )

    def cancel(self) -> None:
        self._cancelled = True
        # Make sure caffeinate is released even if the worker thread is
        # mid-call and we never reach the function-level finally block.
        try:
            self._sleep_preventer.stop()
        except Exception:
            pass

    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    # Prior run access
    # ------------------------------------------------------------------

    def find_prior_run(self, course_id: str, assignment_id: str) -> Optional[str]:
        """Find the most recent completed Insights run for this course+assignment.

        Returns run_id or None.
        """
        if not self._store:
            return None
        try:
            runs = self._store.get_runs(course_id=str(course_id))
            for run in runs:
                if (str(run.get("assignment_id", "")) == str(assignment_id)
                        and run.get("completed_at")):
                    return run["run_id"]
        except Exception as exc:
            log.warning("find_prior_run failed: %s", exc)
        return None

    def load_prior_run(
        self,
        run_id: str,
        *,
        course_id: str = "",
        course_name: str = "",
        assignment_id: str = "",
        assignment_name: str = "",
    ) -> Optional[ComparisonResult]:
        """Extract Tracks B+C from a prior Insights pipeline run.

        Track A is always empty (detect_concerns never called in production).
        Metadata reflects that these tracks were loaded, not freshly run.
        """
        if not self._store:
            return None
        try:
            run_meta = self._store.get_run(run_id)
            if not run_meta:
                log.warning("load_prior_run: run_id %s not found", run_id)
                return None

            codings = self._store.get_codings(run_id)
            comparisons: Dict[str, StudentComparison] = {}

            for row in codings:
                cr = row.get("coding_record") or {}
                sid = str(row.get("student_id", ""))
                name = row.get("student_name", sid)
                wc = cr.get("word_count", 0)

                # Track B
                axis = cr.get("wellbeing_axis") or ""
                track_b: Optional[TrackBResult] = None
                if axis:
                    track_b = TrackBResult(
                        student_id=sid,
                        student_name=name,
                        axis=axis,
                        signal=cr.get("wellbeing_signal") or "",
                        confidence=float(cr.get("wellbeing_confidence", 0.0)),
                        prescan_signals=[],   # not stored in production
                        checkin_flag=cr.get("checkin_flag"),
                        checkin_reasoning=cr.get("checkin_reasoning") or "",
                    )

                # Track C
                obs = cr.get("observation") or ""
                track_c: Optional[TrackCResult] = None
                if obs:
                    track_c = TrackCResult(
                        student_id=sid,
                        student_name=name,
                        observation=obs,
                    )

                comparisons[sid] = StudentComparison(
                    student_id=sid,
                    student_name=name,
                    word_count=wc,
                    track_a=None,   # never populated by production pipeline
                    track_b=track_b,
                    track_c=track_c,
                )

            meta = ComparisonMetadata(
                run_id=run_id,
                started_at=run_meta.get("started_at", ""),
                completed_at=run_meta.get("completed_at", ""),
                total_duration_seconds=0.0,
                backend=BackendMetadata(
                    backend_name="prior_run",
                    model_name=run_meta.get("model_tier", ""),
                    temperature=0.1,
                    quantization="",
                ),
                track_timings={},
                tracks_freshly_run=[],
                tracks_from_prior=["track_b", "track_c"],
                prior_run_id=run_id,
                pipeline_config={},
                git_hash=_git_hash(),
                software_version=_SOFTWARE_VERSION,
            )

            return ComparisonResult(
                course_id=course_id or str(run_meta.get("course_id", "")),
                course_name=course_name or run_meta.get("course_name", ""),
                assignment_id=assignment_id or str(run_meta.get("assignment_id", "")),
                assignment_name=assignment_name or run_meta.get("assignment_name", ""),
                total_students=len(comparisons),
                comparisons=comparisons,
                metadata=meta,
            )

        except Exception as exc:
            log.error("load_prior_run failed: %s", exc, exc_info=True)
            return None

    def get_stored_texts(self, run_id: str) -> Dict[str, str]:
        """Return {student_id: submission_text} from a prior run's stored codings."""
        if not self._store:
            return {}
        try:
            codings = self._store.get_codings(run_id)
            return {
                str(row["student_id"]): (row.get("submission_text") or "")
                for row in codings
                if row.get("student_id")
            }
        except Exception as exc:
            log.warning("get_stored_texts failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Mode 1: Full 3-track comparison
    # ------------------------------------------------------------------

    def run_comparison(
        self,
        *,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        model_tier: str = "auto",
        progress: Callable[[str], None] = lambda m: None,
        track_cb: Callable[[str, str, dict], None] = lambda *a: None,
    ) -> Optional[ComparisonResult]:
        """Mode 1: Full isolated test suite — public entry point.

        Wraps `_run_comparison_inner` in a sleep-prevention guard so the
        Mac can't suspend mid-run (which would deadlock MLX). Inner method
        contains all the actual orchestration logic.
        """
        # Re-read setting in case it changed since construction.
        self._sleep_preventer._enabled = bool(
            self._settings.get("insights_keep_awake", True)
        )
        self._sleep_preventer.start()
        try:
            return self._run_comparison_inner(
                course_id=course_id,
                course_name=course_name,
                assignment_id=assignment_id,
                assignment_name=assignment_name,
                is_discussion=is_discussion,
                model_tier=model_tier,
                progress=progress,
                track_cb=track_cb,
            )
        finally:
            self._sleep_preventer.stop()

    def _run_comparison_inner(
        self,
        *,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        model_tier: str = "auto",
        progress: Callable[[str], None] = lambda m: None,
        track_cb: Callable[[str, str, dict], None] = lambda *a: None,
    ) -> Optional[ComparisonResult]:
        """Mode 1 implementation: Full isolated test suite.

        Executes all shared stages plus all 3 classification tracks from
        scratch, regardless of whether a prior Insights run exists.

        Track execution order (sequential for MLX 16 GB):
          Shared:  Stage 1-2 (fetch + preprocess)
                   Stage 3   (QuickAnalyzer — signal matrix for Track A)
                   Stage 3.5 (class reading — context for Track C)
                   Stage 4   (per-submission coding — teacher_lens for Track C)
          Track A: detect_concerns() per student — NO class context
          Track B: classify_wellbeing() + classify_checkin() — NO class context
          Track C: observe_student() — WITH class reading

        MLX memory: unload_mlx_model() is called between each stage group
        to prevent Metal memory fragmentation on 16 GB machines.
        """
        self._cancelled = False
        run_id = str(uuid.uuid4())
        started_at = _iso_now()
        t_total_start = time.time()

        progress(f"Starting 3-way comparison — run {run_id[:8]}...")

        # ------------------------------------------------------------------
        # Backend
        # ------------------------------------------------------------------
        from insights.llm_backend import auto_detect_backend, unload_mlx_model
        backend = auto_detect_backend(model_tier, self._settings)
        if backend is None:
            progress("No LLM backend available — aborting.")
            return None
        progress(f"Backend: {backend.name} ({backend.model})")
        backend_meta = _capture_backend_metadata(backend)

        throttle = float(self._settings.get("insights_throttle_delay", 2.0))
        pipeline_config = {
            "throttle_delay": throttle,
            "model_tier": model_tier,
            "is_discussion": is_discussion,
        }

        # ------------------------------------------------------------------
        # Stage 1-2: Fetch + preprocess
        # ------------------------------------------------------------------
        if self._cancelled:
            return None

        progress("Stage 1-2: Fetching and preprocessing submissions...")
        from insights.engine import InsightsEngine, DataFetcher
        _engine = InsightsEngine(api=self._api, store=self._store,
                                 settings=self._settings)

        fetcher = DataFetcher(self._api)
        if is_discussion:
            assign_info = fetcher.fetch_assignment_info(course_id, assignment_id)
            topic_id = (assign_info or {}).get("discussion_topic", {}).get("id")
            if not topic_id:
                topic_id = assignment_id
            raw_submissions = fetcher.fetch_discussion_entries(course_id, topic_id)
        else:
            raw_submissions = fetcher.fetch_submissions(course_id, assignment_id)

        if not raw_submissions:
            progress("No submissions found.")
            return None
        progress(f"Found {len(raw_submissions)} submissions.")

        submissions = _engine._preprocess(
            raw_submissions,
            translate_enabled=self._settings.get("insights_translate_enabled", False),
            transcribe_enabled=self._settings.get("insights_transcribe_enabled", False),
            progress=progress,
        )

        # Fetch assignment description
        assignment_description = ""
        try:
            info = fetcher.fetch_assignment_info(course_id, assignment_id)
            if info:
                assignment_description = _strip_html(info.get("description", "") or "")
        except Exception:
            pass

        assignment_prompt = (
            f"Assignment: {assignment_name}\nDescription: {assignment_description[:500]}"
            if assignment_description
            else f"Assignment: {assignment_name}"
        )

        # Build texts + meta dicts
        texts: Dict[str, str] = {}
        meta: Dict[str, dict] = {}
        for sub in submissions:
            sid = str(sub.get("student_id", sub.get("user_id", "")))
            body = _strip_html(sub.get("body") or sub.get("text") or "")
            texts[sid] = body
            meta[sid] = sub

        if self._cancelled:
            return None

        # ------------------------------------------------------------------
        # Stage 3: Quick analysis (signal matrix for Track A)
        # ------------------------------------------------------------------
        progress("Stage 3: Running non-LLM quick analysis...")
        from insights.quick_analyzer import QuickAnalyzer
        qa = QuickAnalyzer(progress_callback=progress)
        qa_result = qa.analyze(
            submissions,
            assignment_id=str(assignment_id),
            assignment_name=assignment_name,
            assignment_description=assignment_description,
            course_id=str(course_id),
            course_name=course_name,
        )

        # Build per-student signal data structures
        # qa_result.per_submission is a dict: student_id → PerSubmissionSummary
        per_sub = getattr(qa_result, "per_submission", {}) or {}
        # concern_signals is a list of ConcernSignal objects
        concern_signals_all = getattr(qa_result, "concern_signals", []) or []
        # Group concern_signals by student_id
        concern_signals_by_sid: Dict[str, list] = {}
        for cs in concern_signals_all:
            sid = str(getattr(cs, "student_id", ""))
            concern_signals_by_sid.setdefault(sid, []).append(cs)

        if self._cancelled:
            return None

        # ------------------------------------------------------------------
        # Stage 3.5: Class reading (for Track C)
        # ------------------------------------------------------------------
        progress("Stage 3.5: Reading class as a community (for Track C)...")
        from insights.class_reader import generate_class_reading, is_reflective_assignment
        class_reading = ""
        if is_reflective_assignment(assignment_name, assignment_description):
            try:
                names = {
                    sid: meta[sid].get("student_name", f"Student {sid}")
                    for sid in texts
                }
                class_reading = generate_class_reading(
                    submissions=texts,
                    submission_names=names,
                    assignment_prompt=assignment_prompt,
                    course_name=course_name,
                    backend=backend,
                )
                progress(f"Class reading complete ({len(class_reading)} chars).")
            except Exception as exc:
                log.warning("Class reading failed (non-fatal): %s", exc)
                progress(f"Class reading failed: {exc}")
        else:
            progress("Non-reflective assignment — skipping class reading.")

        if backend.name == "mlx":
            unload_mlx_model()

        if self._cancelled:
            return None

        # ------------------------------------------------------------------
        # Stage 4: Per-submission coding (teacher_lens for Track C)
        # ------------------------------------------------------------------
        progress("Stage 4: Coding submissions for teacher lens context...")
        from insights.submission_coder import code_submission_reading_first
        coding_records = []
        names_map: Dict[str, str] = {
            sid: meta[sid].get("student_name", f"Student {sid}") for sid in texts
        }
        for sid, body in texts.items():
            if self._cancelled:
                return None
            name = names_map[sid]
            try:
                rec = code_submission_reading_first(
                    backend=backend,
                    student_name=name,
                    submission_text=body,
                    class_context=class_reading,
                    assignment=assignment_prompt,
                )
                coding_records.append((sid, name, rec))
            except Exception as exc:
                log.warning("Coding failed for %s: %s", name, exc)
                coding_records.append((sid, name, None))
            if throttle > 0:
                time.sleep(throttle)

        if backend.name == "mlx":
            unload_mlx_model()

        if self._cancelled:
            return None

        # Build teacher_lens from codings
        teacher_lens_map: Dict[str, str] = {}
        for sid, name, rec in coding_records:
            if rec and hasattr(rec, "what_student_is_reaching_for"):
                tl = rec.what_student_is_reaching_for or ""
                if tl:
                    teacher_lens_map[sid] = tl

        # ------------------------------------------------------------------
        # Track A: Binary concern detection
        # ------------------------------------------------------------------
        progress("Track A: Binary concern detection (no class context)...")
        t_a_start = time.time()
        t_a_iso = _iso_now()

        track_a_results: Dict[str, TrackAResult] = {}
        from research.concern_detector import detect_concerns

        for sid, body in texts.items():
            if self._cancelled:
                return None
            name = names_map[sid]
            progress(f"Track A: {name}...")

            sub_summary = per_sub.get(sid)
            sig_matrix = []
            if sub_summary:
                # raw signal_matrix_results as tuples for the prompt formatter
                sig_matrix = getattr(sub_summary, "signal_matrix_results", []) or []

            concern_sigs = concern_signals_by_sid.get(sid, [])

            try:
                concerns = detect_concerns(
                    submission_text=body,
                    student_name=name,
                    student_id=sid,
                    assignment_prompt=assignment_prompt,
                    signal_matrix_results=sig_matrix,
                    concern_signals=concern_sigs or None,
                    tier=model_tier if model_tier != "auto" else "lightweight",
                    backend=backend,
                    profile_fragment="",
                    class_context="",   # NO class context for binary track
                )
                concern_dicts = [c.model_dump() for c in concerns]
                bias_warns = [c for c in concern_dicts
                              if c.get("why_flagged", "").startswith("⚠")]
                sig_summary = _format_signal_summary(sig_matrix, concern_sigs)

                result = TrackAResult(
                    student_id=sid,
                    student_name=name,
                    flagged=any(c["confidence"] >= 0.5 for c in concern_dicts),
                    concerns=concern_dicts,
                    bias_warnings=bias_warns,
                    signal_matrix_summary=sig_summary,
                )
            except Exception as exc:
                log.warning("Track A failed for %s: %s", name, exc)
                result = TrackAResult(
                    student_id=sid, student_name=name,
                    flagged=False, concerns=[], bias_warnings=[],
                    signal_matrix_summary=f"Error: {exc}",
                )

            track_a_results[sid] = result
            track_cb("track_a", sid, asdict(result))

            if throttle > 0:
                time.sleep(throttle)

        t_a_end = time.time()
        t_a_iso_end = _iso_now()

        if backend.name == "mlx":
            unload_mlx_model()

        if self._cancelled:
            return None

        # ------------------------------------------------------------------
        # Track B: 4-axis wellbeing + targeted CHECK-IN
        # ------------------------------------------------------------------
        progress("Track B: 4-axis wellbeing classification (no class context)...")
        t_b_start = time.time()
        t_b_iso = _iso_now()

        track_b_results: Dict[str, TrackBResult] = {}
        from insights.submission_coder import classify_wellbeing, classify_checkin
        from dataclasses import replace as _dc_replace
        checkin_backend = _dc_replace(backend, temperature=0.3)

        for sid, body in texts.items():
            if self._cancelled:
                return None
            name = names_map[sid]
            progress(f"Track B (wellbeing): {name}...")

            try:
                wb = classify_wellbeing(
                    backend,
                    student_name=name,
                    submission_text=body,
                    assignment_prompt=assignment_prompt,
                )
                axis = wb.get("axis", "NONE")
                ci_flag: Optional[bool] = None
                ci_reasoning = ""

                if axis == "ENGAGED":
                    progress(f"Track B (CHECK-IN): {name}...")
                    try:
                        ci = classify_checkin(
                            checkin_backend,
                            student_name=name,
                            submission_text=body,
                            assignment_prompt=assignment_prompt,
                        )
                        ci_flag = ci.get("check_in", False)
                        ci_reasoning = ci.get("reasoning", "")
                    except Exception as exc:
                        log.warning("CHECK-IN failed for %s: %s", name, exc)

                result = TrackBResult(
                    student_id=sid,
                    student_name=name,
                    axis=axis,
                    signal=wb.get("signal", ""),
                    confidence=float(wb.get("confidence", 0.0)),
                    prescan_signals=wb.get("prescan_signals", []),
                    checkin_flag=ci_flag,
                    checkin_reasoning=ci_reasoning,
                )
            except Exception as exc:
                log.warning("Track B failed for %s: %s", name, exc)
                result = TrackBResult(
                    student_id=sid, student_name=name,
                    axis="NONE", signal=f"Error: {exc}", confidence=0.0,
                    prescan_signals=[], checkin_flag=None, checkin_reasoning="",
                )

            track_b_results[sid] = result
            track_cb("track_b", sid, asdict(result))

            if throttle > 0:
                time.sleep(throttle)

        t_b_end = time.time()
        t_b_iso_end = _iso_now()

        if backend.name == "mlx":
            unload_mlx_model()

        if self._cancelled:
            return None

        # ------------------------------------------------------------------
        # Track C: Generative observation (WITH class reading)
        # ------------------------------------------------------------------
        progress("Track C: Generating observations (with class context)...")
        t_c_start = time.time()
        t_c_iso = _iso_now()

        track_c_results: Dict[str, TrackCResult] = {}
        from insights.submission_coder import observe_student

        for sid, body in texts.items():
            if self._cancelled:
                return None
            name = names_map[sid]
            progress(f"Track C: {name}...")

            teacher_lens = teacher_lens_map.get(sid, "")
            try:
                obs = observe_student(
                    backend,
                    student_name=name,
                    submission_text=body,
                    class_context=class_reading,
                    assignment=assignment_prompt,
                    teacher_lens=teacher_lens,
                )
                result = TrackCResult(
                    student_id=sid, student_name=name, observation=obs
                )
            except Exception as exc:
                log.warning("Track C failed for %s: %s", name, exc)
                result = TrackCResult(
                    student_id=sid, student_name=name,
                    observation=f"[Error: {exc}]",
                )

            track_c_results[sid] = result
            track_cb("track_c", sid, asdict(result))

            if throttle > 0:
                time.sleep(throttle)

        t_c_end = time.time()
        t_c_iso_end = _iso_now()

        # ------------------------------------------------------------------
        # Build result
        # ------------------------------------------------------------------
        completed_at = _iso_now()
        total_duration = time.time() - t_total_start

        comparisons: Dict[str, StudentComparison] = {}
        for sid in texts:
            sub_summary = per_sub.get(sid)
            wc = 0
            if sub_summary:
                wc = getattr(sub_summary, "word_count", 0) or 0
            comparisons[sid] = StudentComparison(
                student_id=sid,
                student_name=names_map[sid],
                word_count=wc,
                track_a=track_a_results.get(sid),
                track_b=track_b_results.get(sid),
                track_c=track_c_results.get(sid),
            )

        metadata = ComparisonMetadata(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            total_duration_seconds=round(total_duration, 1),
            backend=backend_meta,
            track_timings={
                "track_a": TrackTiming(
                    started_at=t_a_iso,
                    completed_at=t_a_iso_end,
                    duration_seconds=round(t_a_end - t_a_start, 1),
                    students_processed=len(track_a_results),
                ),
                "track_b": TrackTiming(
                    started_at=t_b_iso,
                    completed_at=t_b_iso_end,
                    duration_seconds=round(t_b_end - t_b_start, 1),
                    students_processed=len(track_b_results),
                ),
                "track_c": TrackTiming(
                    started_at=t_c_iso,
                    completed_at=t_c_iso_end,
                    duration_seconds=round(t_c_end - t_c_start, 1),
                    students_processed=len(track_c_results),
                ),
            },
            tracks_freshly_run=["track_a", "track_b", "track_c"],
            tracks_from_prior=[],
            prior_run_id=None,
            pipeline_config=pipeline_config,
            git_hash=_git_hash(),
            software_version=_SOFTWARE_VERSION,
        )

        result = ComparisonResult(
            course_id=str(course_id),
            course_name=course_name,
            assignment_id=str(assignment_id),
            assignment_name=assignment_name,
            total_students=len(comparisons),
            comparisons=comparisons,
            metadata=metadata,
        )

        self._save_checkpoint(result)
        return result

    # ------------------------------------------------------------------
    # Mode 2: Track A only (fill in gaps)
    # ------------------------------------------------------------------

    def run_track_a_only(
        self,
        *,
        texts: Dict[str, str],
        student_names: Dict[str, str],
        assignment_prompt: str = "",
        model_tier: str = "auto",
        progress: Callable[[str], None] = lambda m: None,
        track_cb: Callable[[str, str, dict], None] = lambda *a: None,
    ) -> Dict[str, TrackAResult]:
        """Mode 2: Fill in gaps — run binary concern detection only.

        Accepts stored submission texts from a prior Insights run.
        No Canvas fetch needed. Runs QuickAnalyzer (non-LLM, fast)
        for signal matrix, then detect_concerns() per student.

        Does NOT inject class context (proven to hurt binary classification).
        """
        self._cancelled = False
        throttle = float(self._settings.get("insights_throttle_delay", 2.0))

        # Keep the Mac awake for the duration. Idempotent: if the production
        # pipeline is also running and already holds caffeinate, this is a
        # no-op. Re-read setting in case it changed since construction.
        self._sleep_preventer._enabled = bool(
            self._settings.get("insights_keep_awake", True)
        )
        self._sleep_preventer.start()
        try:
            progress("Initializing backend...")
            from insights.llm_backend import auto_detect_backend
            backend = auto_detect_backend(model_tier, self._settings)
            if backend is None:
                progress("No LLM backend available.")
                return {}
            progress(f"Backend: {backend.name} ({backend.model})")

            return self._run_track_a_only_inner(
                texts=texts,
                student_names=student_names,
                assignment_prompt=assignment_prompt,
                model_tier=model_tier,
                backend=backend,
                throttle=throttle,
                progress=progress,
                track_cb=track_cb,
            )
        finally:
            self._sleep_preventer.stop()

    def _run_track_a_only_inner(
        self,
        *,
        texts: Dict[str, str],
        student_names: Dict[str, str],
        assignment_prompt: str,
        model_tier: str,
        backend,
        throttle: float,
        progress: Callable[[str], None],
        track_cb: Callable[[str, str, dict], None],
    ) -> Dict[str, TrackAResult]:
        """Inner body of run_track_a_only — see that method's docstring."""
        # Build minimal submission dicts for QuickAnalyzer
        fake_submissions = [
            {
                "student_id": sid,
                "student_name": student_names.get(sid, sid),
                "body": body,
            }
            for sid, body in texts.items()
        ]

        progress("Running non-LLM quick analysis (for signal matrix)...")
        from insights.quick_analyzer import QuickAnalyzer
        qa = QuickAnalyzer(progress_callback=progress)
        qa_result = qa.analyze(
            fake_submissions,
            assignment_id="research_track_a",
            assignment_name="Research Track A",
        )

        per_sub = getattr(qa_result, "per_submission", {}) or {}
        concern_signals_all = getattr(qa_result, "concern_signals", []) or []
        concern_signals_by_sid: Dict[str, list] = {}
        for cs in concern_signals_all:
            sid = str(getattr(cs, "student_id", ""))
            concern_signals_by_sid.setdefault(sid, []).append(cs)

        progress("Track A: Binary concern detection...")
        from research.concern_detector import detect_concerns

        results: Dict[str, TrackAResult] = {}
        tier = model_tier if model_tier != "auto" else "lightweight"

        for sid, body in texts.items():
            if self._cancelled:
                return results
            name = student_names.get(sid, sid)
            progress(f"Track A: {name}...")

            sub_summary = per_sub.get(sid)
            sig_matrix = getattr(sub_summary, "signal_matrix_results", []) if sub_summary else []
            concern_sigs = concern_signals_by_sid.get(sid, [])

            sig_summary = _format_signal_summary(sig_matrix, concern_sigs)

            # Run combined-scope binary (wellbeing + power moves) — Track A
            try:
                combined = detect_concerns(
                    submission_text=body,
                    student_name=name,
                    student_id=sid,
                    assignment_prompt=assignment_prompt,
                    signal_matrix_results=sig_matrix,
                    concern_signals=concern_sigs or None,
                    tier=tier,
                    backend=backend,
                    profile_fragment="",
                    class_context="",   # NO class context
                    scope="combined",
                )
                combined_dicts = [c.model_dump() for c in combined]
                combined_bias = [c for c in combined_dicts
                                 if c.get("why_flagged", "").startswith("⚠")]
                combined_result = TrackAResult(
                    student_id=sid,
                    student_name=name,
                    flagged=any(c["confidence"] >= 0.5 for c in combined_dicts),
                    concerns=combined_dicts,
                    bias_warnings=combined_bias,
                    signal_matrix_summary=sig_summary,
                )
            except Exception as exc:
                log.warning("Track A combined failed for %s: %s", name, exc)
                combined_result = TrackAResult(
                    student_id=sid, student_name=name,
                    flagged=False, concerns=[], bias_warnings=[],
                    signal_matrix_summary=f"Error: {exc}",
                )

            results[sid] = combined_result
            track_cb("track_a", sid, asdict(combined_result))

            if self._cancelled:
                return results

            # Inter-call throttle to keep MLX stable
            if throttle > 0:
                time.sleep(throttle)

            # Run wellbeing-only-scope binary — Track A_wb
            try:
                wb = detect_concerns(
                    submission_text=body,
                    student_name=name,
                    student_id=sid,
                    assignment_prompt=assignment_prompt,
                    signal_matrix_results=sig_matrix,
                    concern_signals=concern_sigs or None,
                    tier=tier,
                    backend=backend,
                    profile_fragment="",
                    class_context="",
                    scope="wellbeing",
                )
                wb_dicts = [c.model_dump() for c in wb]
                wb_bias = [c for c in wb_dicts
                           if c.get("why_flagged", "").startswith("⚠")]
                wb_result = TrackAResult(
                    student_id=sid,
                    student_name=name,
                    flagged=any(c["confidence"] >= 0.5 for c in wb_dicts),
                    concerns=wb_dicts,
                    bias_warnings=wb_bias,
                    signal_matrix_summary=sig_summary,
                )
            except Exception as exc:
                log.warning("Track A wellbeing-only failed for %s: %s", name, exc)
                wb_result = TrackAResult(
                    student_id=sid, student_name=name,
                    flagged=False, concerns=[], bias_warnings=[],
                    signal_matrix_summary=f"Error: {exc}",
                )

            track_cb("track_a_wb", sid, asdict(wb_result))

            if throttle > 0 and len(results) < len(texts):
                time.sleep(throttle)

        return results

    # ------------------------------------------------------------------
    # Checkpoint (resume support)
    # ------------------------------------------------------------------

    def _save_checkpoint(self, result: ComparisonResult) -> None:
        try:
            out_dir = _get_output_dir() / "research_checkpoints"
            out_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{result.course_id}_{result.assignment_id}.json"
            (out_dir / fname).write_text(json.dumps(asdict(result), indent=2))
            log.info("Research checkpoint saved to %s", out_dir / fname)
        except Exception as exc:
            log.warning("Could not save checkpoint: %s", exc)

    def load_checkpoint(
        self, course_id: str, assignment_id: str
    ) -> Optional[ComparisonResult]:
        """Load a partial result from a previous interrupted run."""
        try:
            out_dir = _get_output_dir() / "research_checkpoints"
            fname = f"{course_id}_{assignment_id}.json"
            path = out_dir / fname
            if not path.exists():
                return None
            data = json.loads(path.read_text())
            # Reconstruct from dict — minimal reconstruction for display
            return _reconstruct_comparison_result(data)
        except Exception as exc:
            log.warning("Could not load checkpoint: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_signal_summary(sig_matrix: list, concern_sigs: list) -> str:
    """Format a brief signal summary for display and export."""
    parts = []
    for sig in (concern_sigs or []):
        st = getattr(sig, "signal_type", "")
        interp = getattr(sig, "interpretation", "")
        if st and st != "APPROPRIATE":
            parts.append(f"{st}: {interp}")
    if not parts and sig_matrix:
        for item in sig_matrix[:3]:
            if isinstance(item, tuple) and len(item) >= 4 and item[0] != "APPROPRIATE":
                parts.append(f"{item[0]}: {item[3]}")
    return "; ".join(parts) if parts else "No non-LLM signals"


def _reconstruct_comparison_result(data: dict) -> ComparisonResult:
    """Shallow reconstruction of ComparisonResult from asdict() output."""
    comparisons = {}
    for sid, sc_data in data.get("comparisons", {}).items():
        ta = sc_data.get("track_a")
        tb = sc_data.get("track_b")
        tc = sc_data.get("track_c")
        comparisons[sid] = StudentComparison(
            student_id=sc_data["student_id"],
            student_name=sc_data["student_name"],
            word_count=sc_data.get("word_count", 0),
            track_a=TrackAResult(**ta) if ta else None,
            track_b=TrackBResult(**tb) if tb else None,
            track_c=TrackCResult(**tc) if tc else None,
        )

    meta_data = data.get("metadata", {})
    bm = meta_data.get("backend", {})
    backend = BackendMetadata(
        backend_name=bm.get("backend_name", ""),
        model_name=bm.get("model_name", ""),
        temperature=bm.get("temperature", 0.1),
        quantization=bm.get("quantization", ""),
    )
    timings = {}
    for k, v in meta_data.get("track_timings", {}).items():
        timings[k] = TrackTiming(**v)

    metadata = ComparisonMetadata(
        run_id=meta_data.get("run_id", ""),
        started_at=meta_data.get("started_at", ""),
        completed_at=meta_data.get("completed_at", ""),
        total_duration_seconds=meta_data.get("total_duration_seconds", 0.0),
        backend=backend,
        track_timings=timings,
        tracks_freshly_run=meta_data.get("tracks_freshly_run", []),
        tracks_from_prior=meta_data.get("tracks_from_prior", []),
        prior_run_id=meta_data.get("prior_run_id"),
        pipeline_config=meta_data.get("pipeline_config", {}),
        git_hash=meta_data.get("git_hash", ""),
        software_version=meta_data.get("software_version", ""),
    )

    return ComparisonResult(
        course_id=data.get("course_id", ""),
        course_name=data.get("course_name", ""),
        assignment_id=data.get("assignment_id", ""),
        assignment_name=data.get("assignment_name", ""),
        total_students=data.get("total_students", 0),
        comparisons=comparisons,
        metadata=metadata,
    )
