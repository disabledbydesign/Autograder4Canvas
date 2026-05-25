"""
QThread-based workers for all async Canvas API operations.
"""
import json
import logging
import tempfile

log = logging.getLogger(__name__)
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class CancellableWorker(QThread):
    """Base for all background workers. Provides cancel flag and error signal."""

    error = Signal(str)

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self._api = api
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


# ---------------------------------------------------------------------------
# Load courses / terms
# ---------------------------------------------------------------------------

class LoadCoursesWorker(CancellableWorker):
    """Fetches all terms then courses for every term (empty terms are filtered in the UI)."""

    terms_loaded = Signal(list)         # [(term_id, term_name, is_current), ...]
    courses_loaded = Signal(int, list)  # (term_id, [course_dicts])

    def run(self) -> None:
        try:
            all_terms = self._api.get_all_terms()
            if self.is_cancelled():
                return

            # Fetch ALL courses before emitting anything.
            # This means terms_loaded and every courses_loaded fire in the same
            # Qt event-queue batch — no visible intermediate state.
            courses_by_term = self._api.get_all_teacher_courses()
            if self.is_cancelled():
                return

            term_list = [(t["id"], t["name"], t["is_current"]) for t in all_terms]
            self.terms_loaded.emit(term_list)
            for term in all_terms:
                self.courses_loaded.emit(term["id"], courses_by_term.get(term["id"], []))

        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Load assignments for one course
# ---------------------------------------------------------------------------

class LoadAssignmentsWorker(CancellableWorker):
    """Fetches assignment groups with nested assignments for one course."""

    assignments_loaded = Signal(list)  # [group_dicts with 'assignments' key]

    def __init__(self, api, course_id: int, parent=None):
        super().__init__(api, parent)
        self.course_id = course_id

    def run(self) -> None:
        try:
            groups = self._api.get_assignment_groups(self.course_id)
            if not self.is_cancelled():
                self.assignments_loaded.emit(groups)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Bulk assignment prefetch (all courses upfront)
# ---------------------------------------------------------------------------

class LoadAllAssignmentsWorker(CancellableWorker):
    """
    Background prefetch: fetches assignment groups for every course in the
    given list, emitting one signal per course as each finishes.
    """

    course_assignments_loaded = Signal(int, list)  # (course_id, groups)

    def __init__(self, api, course_ids: List[int], parent=None):
        super().__init__(api, parent)
        self.course_ids = list(course_ids)

    def run(self) -> None:
        for cid in self.course_ids:
            if self.is_cancelled():
                return
            try:
                groups = self._api.get_assignment_groups(cid)
                self.course_assignments_loaded.emit(cid, groups)
            except Exception:
                self.course_assignments_loaded.emit(cid, [])


# ---------------------------------------------------------------------------
# Lazy submission count loader
# ---------------------------------------------------------------------------

class LoadSubmissionCountsWorker(CancellableWorker):
    """Fetches submission counts one assignment at a time."""

    count_ready = Signal(int, int)   # (assignment_id, count)
    progress = Signal(int, int)      # (done, total)

    def __init__(self, api, course_id: int, assignment_ids: List[int], parent=None):
        super().__init__(api, parent)
        self.course_id = course_id
        self.assignment_ids = assignment_ids

    def run(self) -> None:
        total = len(self.assignment_ids)
        for done, aid in enumerate(self.assignment_ids, 1):
            if self.is_cancelled():
                return
            try:
                count = self._api.get_submission_count(self.course_id, aid)
                self.count_ready.emit(aid, count)
            except Exception:
                self.count_ready.emit(aid, -1)
            self.progress.emit(done, total)


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

class TestConnectionWorker(CancellableWorker):
    """Tests Canvas API connection and returns user display name."""

    result_ready = Signal(bool, str)  # (ok, message)

    def run(self) -> None:
        try:
            ok = self._api.test_connection()
            if not ok:
                self.result_ready.emit(False, "Invalid token or unreachable Canvas URL")
                return
            # Fetch display name
            import requests
            url = self._api.base_url.rstrip("/") + "/api/v1/users/self"
            headers = {"Authorization": f"Bearer {self._api.api_token}"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.ok:
                name = r.json().get("name", "")
                self.result_ready.emit(True, name)
            else:
                self.result_ready.emit(True, "")
        except Exception as exc:
            self.result_ready.emit(False, str(exc))


# ---------------------------------------------------------------------------
# RunStore workers  (no API needed — all local SQLite reads)
# ---------------------------------------------------------------------------

class _StoreWorker(QThread):
    """Lightweight base for RunStore workers (no CanvasAPI dependency)."""
    error = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store


class LoadRunsWorker(_StoreWorker):
    """Load the run-browser sidebar list from RunStore."""
    runs_loaded = Signal(list)  # List[Dict]

    def run(self) -> None:
        try:
            self.runs_loaded.emit(self._store.get_runs())
        except Exception as exc:
            self.error.emit(str(exc))


class LoadCohortWorker(_StoreWorker):
    """Load scatter-plot data for one run (or latest-per-student for a course)."""
    cohort_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, course_id: str, assignment_id: Optional[str] = None, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            self.cohort_loaded.emit(
                self._store.get_cohort(self._course_id, self._assignment_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class LoadCourseMatrixWorker(_StoreWorker):
    """Load the full student × assignment matrix for the class-over-time heatmap."""
    matrix_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, course_id: str, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id

    def run(self) -> None:
        try:
            self.matrix_loaded.emit(
                self._store.get_course_matrix(self._course_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class LoadTrajectoryWorker(_StoreWorker):
    """Load sparkline data for one student across a course."""
    trajectory_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, student_id: str, course_id: str, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._course_id = course_id

    def run(self) -> None:
        try:
            self.trajectory_loaded.emit(
                self._store.get_trajectory(self._student_id, self._course_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class LoadDetailWorker(_StoreWorker):
    """Load full detail row for one student + assignment."""
    detail_loaded = Signal(dict)  # Dict or {} on not-found

    def __init__(self, store, student_id: str, assignment_id: str, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            row = self._store.get_student_detail(self._student_id, self._assignment_id)
            self.detail_loaded.emit(row or {})
        except Exception as exc:
            self.error.emit(str(exc))


class SaveNoteWorker(_StoreWorker):
    """Persist a teacher note asynchronously."""
    note_saved = Signal(int)  # new note id

    def __init__(self, store, student_id: str, course_id: str, note_text: str,
                 assignment_id: Optional[str] = None, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._course_id = course_id
        self._note_text = note_text
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            nid = self._store.save_note(
                self._student_id, self._course_id,
                self._note_text, self._assignment_id,
            )
            self.note_saved.emit(nid)
        except Exception as exc:
            self.error.emit(str(exc))


class LoadGradingAssignmentsWorker(_StoreWorker):
    """Load course -> assignment tree for grading review sidebar."""
    assignments_loaded = Signal(list)  # List[Dict]

    def run(self) -> None:
        try:
            self.assignments_loaded.emit(self._store.get_grading_assignments())
        except Exception as exc:
            self.error.emit(str(exc))


class LoadGradingCohortWorker(_StoreWorker):
    """Load all students for one assignment with AIC JOIN."""
    cohort_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, course_id, assignment_id, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            self.cohort_loaded.emit(
                self._store.get_grading_with_aic(self._course_id, self._assignment_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class SaveTeacherOverrideWorker(_StoreWorker):
    """Persist override to SQLite + post grade to Canvas."""
    override_saved = Signal(bool, str)  # (success, message)

    def __init__(self, store, api, course_id, assignment_id, student_id, grade, reason, parent=None):
        super().__init__(store, parent)
        self._api = api
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._student_id = student_id
        self._grade = grade
        self._reason = reason

    def run(self) -> None:
        try:
            self._store.set_teacher_override(
                self._student_id, self._assignment_id, self._grade, self._reason
            )
            # Post to Canvas
            import requests
            base = self._api.base_url.rstrip("/")
            url = (
                f"{base}/api/v1/courses/{self._course_id}"
                f"/assignments/{self._assignment_id}"
                f"/submissions/{self._student_id}"
            )
            r = requests.put(
                url, headers=self._api.headers,
                json={"submission": {"posted_grade": self._grade}}, timeout=30,
            )
            r.raise_for_status()
            self.override_saved.emit(True, "Grade posted to Canvas")
        except Exception as exc:
            self.override_saved.emit(False, str(exc))


class ExportXLSXWorker(_StoreWorker):
    """Generate XLSX in background thread."""
    export_done = Signal(bool, str)  # (success, path_or_error)

    def __init__(self, store, course_id, assignment_id, output_path, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._output_path = output_path

    def run(self) -> None:
        try:
            path = self._store.export_grading_xlsx(
                self._course_id, self._assignment_id, self._output_path
            )
            self.export_done.emit(True, path)
        except Exception as exc:
            self.export_done.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Logging handler that emits log records as Qt signals
# ---------------------------------------------------------------------------

class QTextEditHandler(logging.Handler):
    """Thread-safe logging handler that emits records via a Qt Signal."""

    def __init__(self, signal: Signal):
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._signal.emit(msg)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Run grading engine
# ---------------------------------------------------------------------------

class RunWorker(CancellableWorker):
    """
    Runs the appropriate grading script directly on the user-selected assignments.

    Calls Programs/Autograder_Complete-Incomplete_v1-3.py,
    Programs/Autograder_Discussion_Forum_v1-3.py, or
    Academic_Dishonesty_Check_v2.py directly — bypassing AutomationEngine
    so that per-assignment manual runs are not subject to automation scheduling
    rules (skip_future_assignments, existing config filters, etc.).
    """

    log_line = Signal(str)
    progress = Signal(int, int)   # (completed, total)
    finished = Signal(bool, str)  # (success, summary_message)
    surface  = Signal(str, dict)  # (card_type, data) for right-panel live cards
    short_sub_reviews_ready = Signal(dict)  # pending SSR reviews for teacher

    def __init__(
        self,
        api,
        course_id: int,
        course_name: str,
        selected_assignments: list,    # full assignment dicts from Canvas API
        assignment_type: str,          # "complete_incomplete" | "discussion_forum" | "aic"
        min_word_count: int = 200,
        post_min_words: int = 200,
        reply_min_words: int = 50,
        discussion_mode: str = "separate",
        grading_type: str = "complete_incomplete",
        post_points: float = 1.0,
        reply_points: float = 0.5,
        min_posts: int = 1,
        min_replies: int = 2,
        run_adc: bool = False,
        run_insights: bool = False,
        run_short_sub_review: bool = False,
        short_sub_auto_post: bool = False,
        preserve_grades: bool = True,
        mark_incomplete: bool = True,
        dry_run: bool = False,
        mode_settings: dict = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self.mode_settings = mode_settings or {}
        self.group_overrides = (mode_settings or {}).get("group_overrides", {})
        self.course_id = course_id
        self.course_name = course_name
        self.selected_assignments = selected_assignments
        self.assignment_type = assignment_type
        self.min_word_count = min_word_count
        self.post_min_words = post_min_words
        self.reply_min_words = reply_min_words
        self.discussion_mode = discussion_mode
        self.grading_type = grading_type
        self.post_points = post_points
        self.reply_points = reply_points
        self.min_posts = min_posts
        self.min_replies = min_replies
        self.run_adc = run_adc
        self.run_insights = run_insights
        self.run_short_sub_review = run_short_sub_review
        self.short_sub_auto_post = short_sub_auto_post
        self.preserve_grades = preserve_grades
        # Accumulate pending SSR reviews across all assignments/courses for this run
        self._ssr_accumulated_reviews: dict = {}
        # Cache preprocessed submissions by assignment ID so they can be
        # fetched + preprocessed once and shared across C/I grading and AIC.
        self._submissions_cache: dict = {}  # {aid: {user_id: sub_dict}}
        self.mark_incomplete = mark_incomplete
        self.dry_run = dry_run

    def _init_preprocessing(self) -> None:
        """Initialize the preprocessing pipeline if translation/transcription is enabled."""
        if hasattr(self, "_preproc_pipeline"):
            return
        self._preproc_pipeline = None
        try:
            from settings import load_settings
            s = load_settings()
            translate = s.get("insights_translate_enabled", True)
            transcribe = s.get("insights_transcribe_enabled", True)
            image_transcribe = s.get("insights_image_transcribe_enabled", True)
            if not (translate or transcribe or image_transcribe):
                return
            from preprocessing import PreprocessingPipeline
            headers = {}
            if self._api and self._api.api_token:
                headers["Authorization"] = f"Bearer {self._api.api_token}"
            self._preproc_pipeline = PreprocessingPipeline(
                canvas_headers=headers,
                translation_enabled=translate,
                transcription_enabled=transcribe,
                image_transcription_enabled=image_transcribe,
                translation_backend=s.get("insights_llm_backend") or (
                    "mlx" if __import__("platform").machine() == "arm64" else "ollama"
                ),
                translation_model=s.get("insights_translation_model", "llama3.1:8b"),
                ollama_base_url=s.get("insights_ollama_url", "http://localhost:11434"),
                cloud_api_key=s.get("insights_cloud_key", ""),
                cloud_base_url=s.get("insights_cloud_url", ""),
                cloud_model=s.get("insights_cloud_model", ""),
                whisper_model=s.get("insights_whisper_model", "medium"),
                generate_teacher_comments=False,
            )
        except ImportError:
            pass

    def _preprocess_for_assignment(self, aid: int, submissions: dict) -> None:
        """Run preprocessing on submissions, enriching body text in-place."""
        self._init_preprocessing()
        if not self._preproc_pipeline:
            return
        try:
            sub_list = [sub for sub in submissions.values()
                        if sub.get("workflow_state") not in ("unsubmitted", "not_submitted")]
            if not sub_list:
                return
            # Ensure each sub has the assignment_id the pipeline expects
            for sub in sub_list:
                sub.setdefault("assignment_id", aid)
            results = self._preproc_pipeline.process_submissions(sub_list)
            # Inject preprocessed text back into submission dicts
            for result in results:
                uid = result.user_id
                if uid in submissions and result.text:
                    original = submissions[uid].get("body", "") or ""
                    if len(result.text) > len(original):
                        submissions[uid]["body"] = result.text
                        if result.was_translated:
                            print(f"   Translated submission for student {uid}")
                        if result.was_transcribed:
                            print(f"   Transcribed submission for student {uid}")
                        if result.was_image_transcribed:
                            print(f"   Transcribed handwriting for student {uid}")
        except Exception as exc:
            print(f"   Preprocessing: {exc}")

    def _get_override(self, assignment: dict, key: str, fallback):
        """Look up a per-group template override for an assignment, or return fallback."""
        if not self.group_overrides:
            return fallback
        gid = assignment.get("assignment_group_id") or assignment.get("group_id")
        if gid and gid in self.group_overrides:
            return self.group_overrides[gid].get(key, fallback)
        return fallback

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        import sys
        import os

        src_dir = str(Path(__file__).parent.parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        if self._api and self._api.base_url:
            os.environ["CANVAS_BASE_URL"] = self._api.base_url
        if self._api and self._api.api_token:
            os.environ["CANVAS_API_TOKEN"] = self._api.api_token

        # Redirect stdout so print() output from the scripts appears in the log pane
        _emit = self.log_line.emit

        class _Capture:
            def __init__(self):
                self._buf = ""
            def write(self, text):
                self._buf += text
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    _emit(line)
                return len(text)
            def flush(self):
                if self._buf:
                    _emit(self._buf)
                    self._buf = ""

        old_stdout = sys.stdout
        sys.stdout = _Capture()

        # ── Unified progress across all phases ────────────────────────
        n_assign = len(self.selected_assignments)
        phases = 1  # grading always runs
        if self.run_adc:
            phases += 1
        if self.run_insights and not self.dry_run:
            phases += 1
        # short_sub_review runs inline during grading — not a separate phase
        self._phase_total = n_assign * phases
        self._phase_done  = 0
        # Per-student progress within the current grading phase is mapped
        # into the fraction of one assignment unit via _emit_student_progress.
        self._progress_total = max(1, self._phase_total)
        self._progress_done  = 0
        self.progress.emit(0, self._phase_total)

        try:
            if self.dry_run:
                self.log_line.emit("DRY RUN MODE — No grades will be submitted")

            if self.assignment_type == "aic":
                self._run_aic()
            elif self.assignment_type == "mixed":
                _orig = self.selected_assignments
                _ci   = [a for a in _orig
                         if "discussion_topic" not in (a.get("submission_types") or [])]
                _df   = [a for a in _orig
                         if "discussion_topic" in (a.get("submission_types") or [])]
                if _ci:
                    self.selected_assignments = _ci
                    self._run_ci()
                if _df:
                    self.selected_assignments = _df
                    self._run_df()
                self.selected_assignments = _orig
                if self.run_adc:
                    self._run_aic()
            elif self.assignment_type == "discussion_forum":
                self._run_df()
                if self.run_adc:
                    self._run_aic()
            else:
                self._run_ci()
                if self.run_adc:
                    self._run_aic()

            if self.run_insights and not self.dry_run:
                self._run_insights()

            if self._ssr_accumulated_reviews:
                self.short_sub_reviews_ready.emit(self._ssr_accumulated_reviews)
            self.finished.emit(True, "Grading complete")
        except Exception as exc:
            self.finished.emit(False, str(exc))
        finally:
            sys.stdout.flush()
            sys.stdout = old_stdout

    # ------------------------------------------------------------------
    # Script runners
    # ------------------------------------------------------------------

    def _emit_progress(self) -> None:
        """Advance by one phase unit (one assignment through one phase)."""
        self._phase_done += 1
        self.progress.emit(self._phase_done, self._phase_total)

    def _load_module(self, filename: str):
        """Dynamically load a Programs script as a module."""
        import importlib.util
        module_path = Path(__file__).parent.parent / "Programs" / filename
        spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"), module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _load_aic_module(self):
        """Load the AIC script (lives in src/, not Programs/)."""
        import importlib.util
        module_path = Path(__file__).parent.parent / "Academic_Dishonesty_Check_v2.py"
        spec = importlib.util.spec_from_file_location("aic", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _submit_individual(self, assignment_id: int, grade_data: dict) -> None:
        """
        Submit grades via individual PUT requests.

        The Canvas bulk update_grades endpoint returns 200/queued but grades
        do not reliably apply on this instance. Individual PUTs are consistent.
        grade_data: {user_id (int): posted_grade (str)}
        """
        import requests as _req
        base = self._api.base_url.rstrip("/")
        url = f"{base}/api/v1/courses/{self.course_id}/assignments/{assignment_id}/submissions"
        headers = self._api.headers

        failed = []
        for user_id, grade in grade_data.items():
            try:
                r = _req.put(
                    f"{url}/{user_id}",
                    headers=headers,
                    json={"submission": {"posted_grade": grade}},
                    timeout=30,
                )
                r.raise_for_status()
            except Exception as exc:
                print(f"   ❌ Failed for student {user_id}: {exc}")
                failed.append(user_id)

        if failed:
            raise RuntimeError(f"Grade submission failed for {len(failed)} student(s)")
        print(f"✅ {len(grade_data)} grade(s) submitted")

    def _run_ci(self) -> None:
        """Grade selected assignments using the Complete/Incomplete script."""
        ci = self._load_module("Autograder_Complete-Incomplete_v1-3.py")

        self.surface.emit("stage", {"text": f"Grading — {self.course_name}"})
        print(f"{self.course_name}")
        students = ci.get_active_students(self.course_id)
        if not students:
            print("No active students found.")
            return
        print(f"{len(students)} active students")

        # Detect LLM backend once before the assignment loop
        _short_sub_backend = None
        if self.run_short_sub_review:
            try:
                from insights.short_sub_reviewer import review_short_submission
                from insights.llm_backend import auto_detect_backend as _adb
                _short_sub_backend = _adb(tier="lightweight")
                if not _short_sub_backend:
                    print("   Short Sub Review: no LLM backend available — skipping")
            except ImportError:
                pass

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")
            if not aid:
                continue

            print(f"\n{'=' * 60}")
            print(f"{aname}")
            print(f"{'=' * 60}")

            # Per-group template override for word count
            effective_min_words = self._get_override(
                assignment, "min_word_count", self.min_word_count)

            submissions = ci.get_submissions(self.course_id, aid)
            self._preprocess_for_assignment(aid, submissions)
            # Cache for AIC reuse (avoids re-fetching + re-preprocessing)
            self._submissions_cache[aid] = submissions
            all_subs = list(submissions.values())

            grade_data = {}
            # Cache evaluation results: {user_id: (grade, flags)}
            eval_cache = {}
            # Track skipped students for RunStore persistence
            skipped_users = []
            # Track short sub review results: {user_id: ShortSubReview}
            short_sub_results = {}
            # user_ids credited by SSR but not auto-posting (queued for teacher review)
            _ssr_pending = set()
            complete = incomplete = skipped = 0
            assignment_desc = assignment.get("description", "")
            review_guidance = self.mode_settings.get("short_sub_guidance", "")
            for enrollment in students:
                user_id = enrollment.get("user_id")
                if not user_id:
                    continue
                sub = submissions.get(user_id)
                if sub and sub.get("workflow_state") not in ("unsubmitted", "not_submitted"):
                    if self.preserve_grades and sub.get("grade") == "complete":
                        skipped += 1
                        skipped_users.append(user_id)
                        eval_cache[user_id] = ("complete", [])
                        continue
                    is_ok, flags = ci.evaluate_submission(sub, all_subs, effective_min_words)
                    # ── Short Submission Review (inline) ──────────────────
                    if (self.run_short_sub_review
                            and _short_sub_backend
                            and not is_ok
                            and self._has_short_flag(flags)):
                        body = sub.get("body", "")
                        wc = len(body.split()) if body else 0
                        if wc > 0:  # skip zero-word (truly no submission)
                            student_name = sub.get("user", {}).get("name", "")
                            ssr = review_short_submission(
                                student_name=student_name,
                                submission_text=body,
                                word_count=wc,
                                min_word_count=effective_min_words,
                                assignment_prompt=assignment_desc,
                                review_guidance=review_guidance,
                                backend=_short_sub_backend,
                            )
                            if ssr:
                                short_sub_results[user_id] = ssr
                                if ssr.verdict == "CREDIT":
                                    is_ok = True
                                    flags = list(flags) + [
                                        f"Short Sub Review: CREDIT — {ssr.rationale}"
                                    ]
                                    # Grade exclusion: only add to grade_data if auto-posting
                                    if self.short_sub_auto_post and ssr.confidence >= 0.7:
                                        pass  # will be added to grade_data below
                                    else:
                                        _ssr_pending.add(user_id)
                                        self._ssr_accumulated_reviews[f"{aid}:{user_id}"] = {
                                            "student_name": student_name,
                                            "submission_text": body,
                                            "assignment_id": aid,
                                            "assignment_name": aname,
                                            "course_id": self.course_id,
                                            "course_name": self.course_name,
                                            "user_id": user_id,
                                            "review": ssr.model_dump(),
                                        }
                                else:
                                    flags = list(flags) + [
                                        f"Short Sub Review: TEACHER_REVIEW — {ssr.rationale}"
                                    ]
                    # ─────────────────────────────────────────────────────
                    grade = "complete" if is_ok else "incomplete"
                    # Mode: criteria_strict — flagged submissions → incomplete
                    if self.mode_settings.get("criteria_strict") and flags and is_ok:
                        grade = "incomplete"
                    # Mode: manual_review — flag borderline students without changing grade
                    if self.mode_settings.get("manual_review") and flags:
                        flags = flags  # keep flags for review
                    eval_cache[user_id] = (grade, flags)
                    if grade == "complete":
                        complete += 1
                    else:
                        incomplete += 1
                else:
                    if not self.mark_incomplete:
                        continue
                    grade = "incomplete"
                    eval_cache[user_id] = (grade, ["No submission"])
                    incomplete += 1
                # Only add to grade_data if not queued for teacher review
                if user_id not in _ssr_pending:
                    grade_data[user_id] = grade

            if not grade_data:
                msg = f"No students to grade"
                if skipped:
                    msg += f" ({skipped} already complete)"
                print(msg)
                self._persist_ci_results(
                    ci, aid, aname, submissions, all_subs, students,
                    grade_data, eval_cache, skipped_users,
                    complete, incomplete, skipped,
                    short_sub_results,
                )
                self.surface.emit("grading", {
                    "assignment": aname, "complete": complete,
                    "incomplete": incomplete, "skipped": skipped,
                    "flagged_students": [],
                })
                self._emit_progress()
                continue

            print(
                f"   {complete} complete, {incomplete} incomplete"
                + (f", {skipped} skipped (already complete)" if skipped else "")
            )
            if self.dry_run:
                print("DRY RUN — no grades submitted")
            else:
                self._submit_individual(aid, grade_data)

            # Build detailed student info for surface card
            incomplete_info = []
            for uid, (g, f) in eval_cache.items():
                if g == "incomplete" and uid not in skipped_users:
                    sub = submissions.get(uid, {})
                    sname = sub.get("user", {}).get("name", f"Student {uid}")
                    incomplete_info.append({"name": sname, "flags": f})

            self.surface.emit("grading", {
                "assignment": aname,
                "complete": complete,
                "incomplete": incomplete,
                "skipped": skipped,
                "incomplete_students": incomplete_info[:8],
                "flagged_students": [],
            })

            # Persist grading results to RunStore
            self._persist_ci_results(
                ci, aid, aname, submissions, all_subs, students,
                grade_data, eval_cache, skipped_users,
                complete, incomplete, skipped,
                short_sub_results,
            )
            self._emit_progress()

    @staticmethod
    def _has_short_flag(flags: list) -> bool:
        """Return True if CI evaluation flags indicate a short-text submission."""
        return any("short" in f.lower() or "below" in f.lower() for f in flags)

    def _persist_ci_results(
        self, ci, aid, aname, submissions, all_subs, students,
        grade_data, eval_cache, skipped_users,
        complete, incomplete, skipped,
        short_sub_results: dict = None,
    ) -> None:
        """Best-effort save of CI grading results to RunStore."""
        try:
            from automation.run_store import RunStore
            store = RunStore()

            # Save per-student results (graded + skipped + SSR pending)
            # eval_cache contains ALL processed students; grade_data may
            # exclude SSR-pending students, so use eval_cache as the source
            all_user_ids = list(eval_cache.keys())
            for user_id in all_user_ids:
                sub = submissions.get(user_id, {})
                user_info = sub.get("user", {})
                student_name = user_info.get("name", f"User {user_id}")
                body = sub.get("body", "")
                word_count = len(body.split()) if body else 0
                submission_type = sub.get("submission_type", "")
                submitted_at = sub.get("submitted_at")

                # Build attachment metadata
                attachments = sub.get("attachments", [])
                attach_meta = [
                    {"filename": a.get("filename", ""),
                     "size": a.get("size", 0),
                     "content_type": a.get("content-type", ""),
                     "url": a.get("url", "")}
                    for a in attachments
                ]

                grade, flags = eval_cache.get(user_id, ("incomplete", []))
                was_skipped = 1 if user_id in skipped_users else 0

                if flags:
                    reason = "; ".join(flags)
                elif grade == "complete":
                    if word_count > 0:
                        reason = f"Meets requirements ({word_count} words)"
                    elif submission_type == "media_recording":
                        reason = "Media recording submitted (content not text-verified)"
                    elif attach_meta:
                        reason = "File submitted (content not text-verified)"
                    else:
                        reason = "Meets requirements"
                else:
                    reason = "Incomplete submission"

                ssr = (short_sub_results or {}).get(user_id)
                store.save_grading_result({
                    "student_id": str(user_id),
                    "assignment_id": str(aid),
                    "student_name": student_name,
                    "course_id": str(self.course_id),
                    "course_name": self.course_name,
                    "assignment_name": aname,
                    "submitted_at": submitted_at,
                    "grade": grade,
                    "reason": reason,
                    "word_count": word_count,
                    "submission_type": submission_type,
                    "submission_body": body,
                    "attachment_meta": attach_meta,
                    "flags": flags,
                    "is_flagged": 1 if [f for f in flags if f != "No submission"] else 0,
                    "grading_tool": "ci",
                    "min_word_count": self.min_word_count,
                    "was_skipped": was_skipped,
                    "short_sub_review": json.dumps(ssr.model_dump()) if ssr else None,
                })

            # Save run-level metadata
            flagged_count = sum(
                1 for uid in all_user_ids
                if eval_cache.get(uid, (None, []))[1]
            )
            store.save_grading_run({
                "course_id": str(self.course_id),
                "assignment_id": str(aid),
                "course_name": self.course_name,
                "assignment_name": aname,
                "grading_tool": "ci",
                "total_students": complete + incomplete + skipped,
                "complete_count": complete,
                "incomplete_count": incomplete,
                "skipped_count": skipped,
                "flagged_count": flagged_count,
                "min_word_count": self.min_word_count,
                "was_dry_run": 1 if self.dry_run else 0,
                "mode_settings": json.dumps(self.mode_settings),
            })
            store.close()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"RunStore save failed (CI): {exc}")

    def _run_df(self) -> None:
        """Grade selected discussion assignments using the Discussion Forum script."""
        df = self._load_module("Autograder_Discussion_Forum_v1-3.py")

        self.surface.emit("stage", {"text": f"Discussion Grading — {self.course_name}"})
        print(f"{self.course_name}")
        students = df.get_active_students(self.course_id)
        if not students:
            print("No active students found.")
            return

        grading_type_str = "pass_fail" if self.grading_type == "complete_incomplete" else "points"
        grading_criteria = {"complete": {"total_words": self.post_min_words, "min_replies": 0}}

        # Detect LLM backend once before the assignment loop
        _short_sub_backend = None
        if self.run_short_sub_review:
            try:
                from insights.short_sub_reviewer import review_short_submission
                from insights.llm_backend import auto_detect_backend as _adb
                _short_sub_backend = _adb(tier="lightweight")
                if not _short_sub_backend:
                    print("   Short Sub Review: no LLM backend available — skipping")
            except ImportError:
                pass

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            topic = assignment.get("discussion_topic") or {}
            topic_id = topic.get("id")
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")

            if not topic_id or not aid:
                print(f"⚠️  '{aname}': no linked discussion topic — skipping")
                self._emit_progress()
                continue

            print(f"\n{'=' * 60}")
            print(f"💬 {aname}")
            print(f"{'=' * 60}")

            entries = df.fetch_discussion_entries(self.course_id, topic_id)
            if not entries:
                print("   ⚠️  No discussion entries found.")
                continue

            all_entries = df.flatten_entries(entries)
            student_posts: dict = {}
            for entry in all_entries:
                uid = entry.get("user_id")
                msg = entry.get("message", "")
                if uid:
                    student_posts.setdefault(uid, []).append(msg)

            # Fetch current grades if preserving existing work
            current_grades: dict = {}
            if self.preserve_grades:
                import requests as _req
                base = self._api.base_url.rstrip("/")
                r = _req.get(
                    f"{base}/api/v1/courses/{self.course_id}/assignments/{aid}/submissions",
                    headers=self._api.headers,
                    params={"per_page": 100},
                    timeout=30,
                )
                if r.ok:
                    for s in r.json():
                        uid = s.get("user_id")
                        if uid:
                            current_grades[uid] = s.get("grade")

            grade_data = {}
            # Cache evaluation results: {user_id: (grade, flags, word_count, post_count, avg_words)}
            eval_cache = {}
            # Track skipped students for RunStore persistence
            skipped_users = []
            # Track short sub review results: {user_id: ShortSubReview}
            short_sub_results = {}
            # user_ids credited by SSR but not auto-posting (queued for teacher review)
            _ssr_pending = set()
            complete = incomplete = skipped = 0
            student_ids = {s.get("user_id") for s in students}
            review_guidance = self.mode_settings.get("short_sub_guidance", "")
            assignment_desc = assignment.get("description", "")
            for s in students:
                user_id = s.get("user_id")
                if not user_id or user_id not in student_ids:
                    continue
                posts = student_posts.get(user_id)
                if not posts:
                    continue  # no posts — leave ungraded
                if self.preserve_grades and current_grades.get(user_id) in ("complete",) or (
                    grading_type_str != "pass_fail"
                    and current_grades.get(user_id) not in (None, "", "0", "incomplete")
                ):
                    skipped += 1
                    skipped_users.append(user_id)
                    existing_grade = current_grades.get(user_id, "complete")
                    eval_cache[user_id] = (existing_grade, [], 0, len(posts), 0.0)
                    continue
                status, flags, _wc, _pc, _avg = df.evaluate_discussion_post(
                    posts, grading_criteria, grading_type_str
                )
                if grading_type_str == "pass_fail":
                    grade = "complete" if status == "complete" else "incomplete"
                else:
                    max_pts = assignment.get("points_possible") or 10
                    grade = str(max_pts) if status not in ("incomplete", "F") else "0"
                # ── Short Submission Review (inline) ──────────────────
                is_incomplete = grade == "incomplete" or (grading_type_str != "pass_fail" and grade == "0")
                if (self.run_short_sub_review
                        and _short_sub_backend
                        and is_incomplete
                        and self._has_short_flag(flags)):
                    combined = " ".join(posts)
                    wc = len(combined.split()) if combined else 0
                    if wc > 0:
                        student_name = s.get("user", {}).get("name", "")
                        thread_ctx = (
                            {"parent_post": assignment_desc[:500],
                             "sibling_replies": [],
                             "reviewed_reply_index": -1}
                            if assignment_desc else None
                        )
                        ssr = review_short_submission(
                            student_name=student_name,
                            submission_text=combined,
                            word_count=wc,
                            min_word_count=self.post_min_words,
                            assignment_prompt=assignment_desc,
                            review_guidance=review_guidance,
                            thread_context=thread_ctx,
                            backend=_short_sub_backend,
                        )
                        if ssr:
                            short_sub_results[user_id] = ssr
                            if ssr.verdict == "CREDIT":
                                grade = "complete" if grading_type_str == "pass_fail" else str(max_pts)
                                flags = list(flags) + [
                                    f"Short Sub Review: CREDIT — {ssr.rationale}"
                                ]
                                if self.short_sub_auto_post and ssr.confidence >= 0.7:
                                    pass  # will be added to grade_data below
                                else:
                                    _ssr_pending.add(user_id)
                                    self._ssr_accumulated_reviews[f"{aid}:{user_id}"] = {
                                        "student_name": student_name,
                                        "submission_text": combined,
                                        "assignment_id": aid,
                                        "assignment_name": aname,
                                        "course_id": self.course_id,
                                        "course_name": self.course_name,
                                        "user_id": user_id,
                                        "review": ssr.model_dump(),
                                    }
                            else:
                                flags = list(flags) + [
                                    f"Short Sub Review: TEACHER_REVIEW — {ssr.rationale}"
                                ]
                # ─────────────────────────────────────────────────────
                eval_cache[user_id] = (grade, flags, _wc, _pc, _avg)
                if grade in ("complete",) or (grading_type_str != "pass_fail" and grade != "0"):
                    complete += 1
                else:
                    incomplete += 1
                # Only add to grade_data if not queued for teacher review
                if user_id not in _ssr_pending:
                    grade_data[user_id] = grade

            if not grade_data:
                msg = f"No students to grade"
                if skipped:
                    msg += f" ({skipped} already graded)"
                print(msg)
                self._persist_df_results(
                    aid, aname, student_posts, students,
                    grade_data, eval_cache, skipped_users,
                    complete, incomplete, skipped,
                    short_sub_results,
                )
                self.surface.emit("grading", {
                    "assignment": aname, "complete": complete,
                    "incomplete": incomplete, "skipped": skipped,
                    "is_discussion": True, "incomplete_students": [],
                    "flagged_students": [],
                })
                self._emit_progress()
                continue

            print(
                f"   {complete} complete, {incomplete} incomplete"
                + (f", {skipped} skipped (already graded)" if skipped else "")
            )
            if self.dry_run:
                print("DRY RUN — no grades submitted")
            else:
                self._submit_individual(aid, grade_data)

            # Build detailed student info for surface card
            student_lookup = {s.get("user_id"): s for s in students}
            incomplete_info = []
            for uid, (g, f, *rest) in eval_cache.items():
                if g in ("incomplete", "0") and uid not in skipped_users:
                    sname = student_lookup.get(uid, {}).get(
                        "user", {}).get("name", f"Student {uid}")
                    incomplete_info.append({"name": sname, "flags": f})

            self.surface.emit("grading", {
                "assignment": aname,
                "complete": complete,
                "incomplete": incomplete,
                "skipped": skipped,
                "is_discussion": True,
                "incomplete_students": incomplete_info[:8],
                "flagged_students": [],
            })

            self._persist_df_results(
                aid, aname, student_posts, students,
                grade_data, eval_cache, skipped_users,
                complete, incomplete, skipped,
                short_sub_results,
            )
            self._emit_progress()

    def _persist_df_results(
        self, aid, aname, student_posts, students,
        grade_data, eval_cache, skipped_users,
        complete, incomplete, skipped,
        short_sub_results: dict = None,
    ) -> None:
        """Best-effort save of DF grading results to RunStore."""
        try:
            from automation.run_store import RunStore
            store = RunStore()

            # Save per-student results (graded + skipped + SSR pending)
            # eval_cache contains ALL processed students; grade_data may
            # exclude SSR-pending students, so use eval_cache as the source
            all_user_ids = list(eval_cache.keys())
            for user_id in all_user_ids:
                # Find student name from enrollment list
                student_name = f"User {user_id}"
                for s in students:
                    if s.get("user_id") == user_id:
                        user_info = s.get("user", {})
                        student_name = user_info.get("name", student_name)
                        break

                posts = student_posts.get(user_id, [])
                combined_text = " ".join(posts)
                word_count = len(combined_text.split()) if combined_text.strip() else 0
                post_count = len(posts)

                grade, flags, _wc, _pc, avg_words = eval_cache.get(
                    user_id, ("incomplete", [], 0, 0, 0.0)
                )
                # Use cached word count if available (more accurate from evaluator)
                if _wc:
                    word_count = _wc
                was_skipped = 1 if user_id in skipped_users else 0

                if flags:
                    reason = "; ".join(flags)
                elif grade in ("complete",) or (grade not in ("0", "incomplete")):
                    reason = "Meets requirements"
                else:
                    reason = "Incomplete submission"

                ssr = (short_sub_results or {}).get(user_id)
                store.save_grading_result({
                    "student_id": str(user_id),
                    "assignment_id": str(aid),
                    "student_name": student_name,
                    "course_id": str(self.course_id),
                    "course_name": self.course_name,
                    "assignment_name": aname,
                    "submitted_at": None,  # discussions don't have submitted_at
                    "grade": grade,
                    "reason": reason,
                    "word_count": word_count,
                    "submission_type": "discussion_topic",
                    "submission_body": combined_text,
                    "attachment_meta": [],
                    "flags": flags,
                    "is_flagged": 1 if [f for f in flags if f not in ("No submission", "No posts")] else 0,
                    "grading_tool": "df",
                    "min_word_count": self.post_min_words,
                    "was_skipped": was_skipped,
                    "post_count": post_count,
                    "reply_count": max(0, post_count - 1) if post_count > 0 else 0,
                    "avg_words_per_post": avg_words,
                    "short_sub_review": json.dumps(ssr.model_dump()) if ssr else None,
                })

            # Save run-level metadata
            flagged_count = sum(
                1 for uid in all_user_ids
                if eval_cache.get(uid, (None, [], 0, 0, 0.0))[1]
            )
            store.save_grading_run({
                "course_id": str(self.course_id),
                "assignment_id": str(aid),
                "course_name": self.course_name,
                "assignment_name": aname,
                "grading_tool": "df",
                "total_students": complete + incomplete + skipped,
                "complete_count": complete,
                "incomplete_count": incomplete,
                "skipped_count": skipped,
                "flagged_count": flagged_count,
                "min_word_count": self.post_min_words,
                "was_dry_run": 1 if self.dry_run else 0,
                "mode_settings": json.dumps(self.mode_settings),
            })
            store.close()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"RunStore save failed (DF): {exc}")

    def _run_aic(self) -> None:
        """Run the Academic Integrity Checker on selected assignments."""
        aic = self._load_aic_module()

        settings    = self.mode_settings or {}
        global_aic  = settings.get("aic_config")
        global_mode = (global_aic or {}).get("aic_mode") or settings.get("aic_mode", "auto")

        self.surface.emit("stage", {"text": "Engagement Analysis"})
        print(f"\n{'=' * 60}")
        print("Engagement Analysis")
        print(f"{'=' * 60}")
        if global_mode and global_mode != "auto":
            print(f"   Assignment mode: {global_mode}")

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")
            if not aid:
                continue

            print(f"\n{aname}")

            # Per-group template override for AIC config
            aic_config = self._get_override(assignment, "aic_config", global_aic)
            aic_mode = (aic_config or {}).get("aic_mode") or global_mode

            # AIC works on text-entry, file uploads (.txt/.docx/.pdf), and discussions.
            # Skip only non-text types (URL-only, on_paper, etc.).
            sub_types = assignment.get("submission_types") or []
            _analyzable = {"online_text_entry", "online_upload", "discussion_topic"}
            if not any(t in _analyzable for t in sub_types):
                type_str = ", ".join(sub_types) if sub_types else "none"
                print(f"AIC skipped — no analyzable text (type: {type_str})")
                self._emit_progress()
                continue

            if self.dry_run:
                print(f"DRY RUN: Would run AIC on assignment {aid}")
                self._emit_progress()
            else:
                # Use cached preprocessed submissions if available (from C/I phase)
                cached = self._submissions_cache.get(aid)
                if cached is not None:
                    pre_subs = list(cached.values())
                else:
                    # Not in cache (AIC-only run, or discussion).
                    # Fetch and preprocess now so AIC sees translated text.
                    try:
                        _aic_mod = aic
                        raw_subs = _aic_mod.get_submissions(self.course_id, aid)
                        if raw_subs:
                            subs_by_uid = {s.get("user_id"): s for s in raw_subs}
                            self._preprocess_for_assignment(aid, subs_by_uid)
                            self._submissions_cache[aid] = subs_by_uid
                            pre_subs = list(subs_by_uid.values())
                        else:
                            pre_subs = None
                    except Exception:
                        pre_subs = None

                # Phase 9: pass full aic_config when available; fall back to bare mode name
                aic_kwargs = {"generate_report": False}
                if aic_config:
                    aic_kwargs["aic_config"] = aic_config
                elif aic_mode and aic_mode != "auto":
                    aic_kwargs["assignment_type"] = aic_mode
                if pre_subs is not None:
                    aic_kwargs["submissions"] = pre_subs

                results, _ = aic.analyze_assignment(
                    self.course_id, aid, **aic_kwargs,
                )

                # Surface card: AIC summary with highlights
                if results:
                    elevated = [r for r in results
                                if getattr(r, "concern_level", "") in ("high", "elevated")]
                    low = [r for r in results
                           if getattr(r, "concern_level", "") == "low"]
                    # Build highlights: top markers triggered across cohort
                    from collections import Counter
                    all_markers = Counter()
                    for r in results:
                        for marker, cnt in getattr(r, "marker_counts", {}).items():
                            if cnt > 0:
                                all_markers[marker] += 1  # count students, not instances
                    top_markers = [f"{name} ({cnt})"
                                   for name, cnt in all_markers.most_common(4)]
                    self.surface.emit("aic", {
                        "assignment": aname,
                        "analyzed": len(results),
                        "elevated": len(elevated),
                        "low": len(low),
                        "highlights": top_markers,
                        "students": [
                            {"name": getattr(r, "student_name", ""),
                             "concern": getattr(r, "concern_level", ""),
                             "smoking_gun": getattr(r, "smoking_gun", False)}
                            for r in elevated[:5]
                        ],
                    })
                self._emit_progress()

    def _run_insights(self) -> None:
        """Run Insights Engine on each selected assignment after grading."""
        try:
            from insights.engine import InsightsEngine
        except ImportError as e:
            print(f"\nInsights skipped — import failed: {e}")
            return

        print(f"\n{'=' * 60}")
        print("Generating Class Insights")
        print(f"{'=' * 60}")

        self.surface.emit("stage", {"text": "Generating Class Insights"})

        try:
            from settings import load_settings as _ls
            _engine_settings = _ls()
        except Exception:
            _engine_settings = {}
        engine = InsightsEngine(api=self._api, settings=_engine_settings)

        _surface = self.surface  # capture for closures

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")
            if not aid:
                continue

            is_disc = "discussion_topic" in (assignment.get("submission_types") or [])

            print(f"\n{aname}")

            def _result(result_type, data):
                _surface.emit(result_type, data)

            try:
                run_id = engine.run_analysis(
                    course_id=self.course_id,
                    course_name=self.course_name,
                    assignment_id=aid,
                    assignment_name=aname,
                    is_discussion=is_disc,
                    progress_callback=lambda msg: print(f"   {msg}"),
                    result_callback=_result,
                )
                if run_id:
                    print(f"   Insights complete (run {run_id})")
                else:
                    print(f"   No insights generated")
            except Exception as e:
                print(f"   Insights failed: {e}")
            self._emit_progress()


# ---------------------------------------------------------------------------
# Canvas edit workers (mutations via CanvasEditor)
# ---------------------------------------------------------------------------

class EditAssignmentWorker(CancellableWorker):
    """
    Runs any single CanvasEditor mutation in a background thread.

    Pass a zero-argument callable that returns an EditResult.

    Example:
        worker = EditAssignmentWorker(
            api=self._api,
            editor=self._editor,
            fn=lambda: self._editor.rename_assignment(course_id, aid, "New Name"),
        )
        worker.result_ready.connect(self._on_edit_done)
        worker.start()
    """

    result_ready = Signal(object)   # EditResult (as object so Qt doesn't need to know the type)

    def __init__(self, api, editor, fn, parent=None):
        super().__init__(api, parent)
        self._editor = editor
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            from canvas_editor import EditResult
            result = EditResult(ok=False, error_code="unknown", message=str(exc))
        if not self.is_cancelled():
            self.result_ready.emit(result)


class BulkShiftDeadlinesWorker(CancellableWorker):
    """
    Shifts due dates for a list of assignments by delta_days with per-item progress.

    Signals:
        progress(done, total)         — emitted after each assignment attempt
        item_done(assignment_id, result) — the EditResult for each assignment
        all_done(results)             — List[Tuple[int, EditResult]] when finished
    """

    progress   = Signal(int, int)    # (done, total)
    item_done  = Signal(int, object) # (assignment_id, EditResult)
    all_done   = Signal(list)        # List[Tuple[int, EditResult]]

    def __init__(self, api, editor, course_id: int,
                 assignment_ids: List[int], delta_days: int, parent=None):
        super().__init__(api, parent)
        self._editor = editor
        self._course_id = course_id
        self._assignment_ids = assignment_ids
        self._delta_days = delta_days

    def run(self) -> None:
        def _on_progress(done: int, total: int) -> None:
            if self.is_cancelled():
                return
            self.progress.emit(done, total)

        try:
            results = self._editor.bulk_shift_deadlines(
                self._course_id,
                self._assignment_ids,
                self._delta_days,
                progress_callback=_on_progress,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return

        if not self.is_cancelled():
            for aid, result in results:
                self.item_done.emit(aid, result)
            self.all_done.emit(results)


# ---------------------------------------------------------------------------
# Load assignment groups for a list of courses (for mapping panel)
# ---------------------------------------------------------------------------

class LoadGroupsForCoursesWorker(CancellableWorker):
    """
    Fetches assignment groups for multiple courses, emitting per-course as they arrive.

    Signals:
        groups_loaded(course_id, course_name, groups)  — one course done
        all_done()                                     — all courses processed
    """

    groups_loaded = Signal(int, str, list)   # (course_id, course_name, groups)
    all_done      = Signal()

    def __init__(self, api, course_entries: list, parent=None):
        """course_entries: [(course_id, course_name), ...]"""
        super().__init__(api, parent)
        self._entries = course_entries

    def run(self) -> None:
        for course_id, course_name in self._entries:
            if self.is_cancelled():
                break
            try:
                groups = self._api.get_assignment_groups(course_id)
            except Exception:
                groups = []
            if not self.is_cancelled():
                self.groups_loaded.emit(course_id, course_name, groups)
        if not self.is_cancelled():
            self.all_done.emit()


# ---------------------------------------------------------------------------
# Bulk run across multiple courses
# ---------------------------------------------------------------------------

class BulkRunWorker(CancellableWorker):
    """
    Runs the autograder across multiple courses sequentially.

    For each course: loads assignment groups, filters by scope, builds an
    AutomationConfig, and runs the engine.

    Scope dict keys (all bool):
        past_due       — include assignments whose deadline has passed
        submitted      — include assignments with ungraded submissions
        last_week_only — restrict past_due to assignments due in the last 7 days

    Options dict keys:
        run_aic          (bool)  — run academic integrity check alongside
        preserve_grades  (bool)  — preserve existing grades
        min_word_count   (int)   — CI min word count (global fallback)
        post_min_words   (int)   — discussion post min words (global fallback)
        reply_min_words  (int)   — discussion reply min words (global fallback)

    group_overrides: optional {group_id: {min_word_count, post_min_words,
        reply_min_words, run_aic, assignment_type}} — per-group template settings
        that override the global options when present.
    """

    log_line       = Signal(str)
    course_started = Signal(str)          # course_name
    progress       = Signal(int, int)     # (done, total)
    finished       = Signal(bool, str)    # (success, summary)

    def __init__(self, api, course_entries: list, scope: dict,
                 options: dict, dry_run: bool = False,
                 group_overrides: dict = None, parent=None):
        """
        course_entries: [(course_id, course_name, term_id), ...]
        group_overrides: {group_id: template_settings_dict}
        """
        super().__init__(api, parent)
        self._course_entries = course_entries
        self._scope = scope
        self._options = options
        self._dry_run = dry_run
        self._group_overrides = group_overrides or {}

    def run(self) -> None:
        import sys
        import os
        import tempfile
        from datetime import datetime, timedelta, timezone
        from pathlib import Path

        src_dir = str(Path(__file__).parent.parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        if self._api and self._api.base_url:
            os.environ["CANVAS_BASE_URL"] = self._api.base_url
        if self._api and self._api.api_token:
            os.environ["CANVAS_API_TOKEN"] = self._api.api_token

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        scope_past_due   = self._scope.get("past_due", True)
        scope_submitted  = self._scope.get("submitted", False)
        scope_last_week  = self._scope.get("last_week_only", False)

        run_aic             = self._options.get("run_aic", False)
        preserve            = self._options.get("preserve_grades", True)
        mark_incomplete     = self._options.get("mark_incomplete", False)
        min_words           = self._options.get("min_word_count", 200)
        post_words          = self._options.get("post_min_words", 200)
        reply_words         = self._options.get("reply_min_words", 50)

        total = len(self._course_entries)
        total_graded = 0
        total_errors = 0

        try:
            from automation.course_config import (
                AssignmentRule, CourseConfig, GlobalSettings, AutomationConfig,
            )
            from automation.automation_engine import AutomationEngine
            from autograder_utils import get_output_base_dir
        except Exception as exc:
            self.finished.emit(False, f"Import error: {exc}")
            return

        base_dir = get_output_base_dir()
        base_dir.mkdir(parents=True, exist_ok=True)

        handler = None
        try:
            import logging
            handler = QTextEditHandler(self.log_line)
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger = logging.getLogger("autograder_automation")

            for done, (course_id, course_name, term_id) in enumerate(self._course_entries):
                if self.is_cancelled():
                    break

                self.course_started.emit(course_name)
                self.log_line.emit(f"\n{'='*55}")
                self.log_line.emit(f"COURSE {done+1}/{total}: {course_name}")
                self.log_line.emit(f"{'='*55}")

                try:
                    groups = self._api.get_assignment_groups(course_id)
                except Exception as exc:
                    self.log_line.emit(f"  ERROR loading assignments: {exc}")
                    total_errors += 1
                    self.progress.emit(done + 1, total)
                    continue

                # Filter groups to those containing qualifying assignments
                qualifying_groups = []
                for group in groups:
                    assignments = group.get("assignments", [])
                    gid_chk = group.get("id", 0)
                    ov_chk = self._group_overrides.get(gid_chk, {})
                    desired_chk = _template_atype_to_canvas_grading_type(
                        ov_chk.get("assignment_type", "")
                    )
                    qualifies = False
                    for a in assignments:
                        if not _bulk_is_autogradeable(a, desired_chk):
                            continue
                        due_raw = a.get("due_at")
                        due_dt = _bulk_parse_due(due_raw)
                        needs_grading = (a.get("needs_grading_count") or 0) > 0

                        if scope_submitted and needs_grading:
                            qualifies = True
                            break
                        if scope_past_due and due_dt and due_dt < now:
                            if scope_last_week and due_dt < seven_days_ago:
                                continue  # too old when last_week_only is set
                            qualifies = True
                            break

                    if qualifies:
                        qualifying_groups.append(group)

                if not qualifying_groups:
                    self.log_line.emit("  No qualifying assignments found — skipping.")
                    self.progress.emit(done + 1, total)
                    continue

                self.log_line.emit(
                    f"  {len(qualifying_groups)} group(s) with qualifying assignments"
                )

                # ── Auto-convert grading types to match template settings ───
                if self._group_overrides and not self.is_cancelled():
                    from canvas_editor import CanvasEditor
                    _editor = CanvasEditor(self._api.base_url, self._api.api_token)
                    for _grp in qualifying_groups:
                        _gid = _grp.get("id", 0)
                        _ov  = self._group_overrides.get(_gid, {})
                        _target = _template_atype_to_canvas_grading_type(
                            _ov.get("assignment_type", "")
                        )
                        if not _target:
                            continue
                        for _a in _grp.get("assignments", []):
                            _cur = _a.get("grading_type", "")
                            if _cur == _target:
                                continue
                            _aid   = _a.get("id")
                            _aname = _a.get("name", f"id={_aid}")
                            if self._dry_run:
                                self.log_line.emit(
                                    f"  [preview] grading type: {_aname!r}"
                                    f"  {_cur} → {_target}"
                                )
                                _a["grading_type"] = _target
                            else:
                                _res = _editor.set_grading_type(course_id, _aid, _target)
                                if _res.ok:
                                    self.log_line.emit(
                                        f"  ✓ grading type: {_aname!r}"
                                        f"  {_cur} → {_target}"
                                    )
                                    _a["grading_type"] = _target
                                else:
                                    self.log_line.emit(
                                        f"  ✗ grading type: {_aname!r}: {_res.message}"
                                    )

                # Build config
                config = AutomationConfig()
                config.global_settings = GlobalSettings(
                    current_semester_term_ids=[term_id],
                    log_file_path=str(base_dir / "bulk_run.log"),
                    flag_excel_path=str(base_dir / "bulk_flags.xlsx"),
                    skip_future_assignments=True,
                    skip_no_submissions=not scope_submitted and scope_past_due,
                )
                course_cfg = CourseConfig(
                    course_id=course_id,
                    course_name=course_name,
                    semester_term_id=term_id,
                )
                seen_group_ids: set = set()
                for group in qualifying_groups:
                    gid = group.get("id", 0)
                    if gid in seen_group_ids:
                        continue
                    seen_group_ids.add(gid)
                    gname = group.get("name", f"Group {gid}")

                    # Per-group template overrides take precedence over globals
                    ov = self._group_overrides.get(gid, {})
                    rule_min   = ov.get("min_word_count",  min_words)
                    rule_post  = ov.get("post_min_words",  post_words)
                    rule_reply = ov.get("reply_min_words", reply_words)
                    rule_aic   = ov.get("run_aic",         run_aic)
                    rule_atype = ov.get("assignment_type", "mixed")

                    try:
                        course_cfg.add_rule(AssignmentRule(
                            rule_id=f"bulk_{gid}",
                            assignment_group_name=gname,
                            assignment_group_id=gid,
                            assignment_type=rule_atype,
                            min_word_count=rule_min,
                            post_min_words=rule_post,
                            reply_min_words=rule_reply,
                            run_adc=rule_aic,
                            preserve_existing_grades=preserve,
                            mark_missing_as_incomplete=mark_incomplete,
                        ))
                    except ValueError:
                        pass  # duplicate group — skip

                config.courses[course_id] = course_cfg

                fd, tmp_path = tempfile.mkstemp(suffix=".json")
                os.close(fd)
                tmp = Path(tmp_path)
                try:
                    config.save(tmp)
                    engine = AutomationEngine(
                        config_path=str(tmp),
                        dry_run=self._dry_run,
                        course_filter=course_id,
                    )
                    # AutomationEngine._setup_logging() clears handlers — re-add ours
                    logger.addHandler(handler)
                    engine.run()
                    total_graded += 1
                except Exception as exc:
                    self.log_line.emit(f"  ERROR running engine: {exc}")
                    total_errors += 1
                finally:
                    tmp.unlink(missing_ok=True)

                self.progress.emit(done + 1, total)

        finally:
            if handler:
                import logging
                logging.getLogger("autograder_automation").removeHandler(handler)

        if self.is_cancelled():
            self.finished.emit(False, "Cancelled.")
        elif total_errors > 0:
            self.finished.emit(
                total_graded > 0,
                f"Done. {total_graded} course(s) completed, {total_errors} error(s).",
            )
        else:
            mode = "preview" if self._dry_run else "graded"
            self.finished.emit(True, f"Done. {total_graded} course(s) {mode}.")


def _bulk_parse_due(raw):
    """Parse a due_at string; return aware datetime or None."""
    if not raw:
        return None
    try:
        from dateutil import parser as _dp
        from datetime import timezone
        dt = _dp.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


_WRITABLE_SUBMISSION_TYPES = frozenset({
    "online_text_entry", "online_upload", "online_url",
    "media_recording", "student_annotation",
})


def _template_atype_to_canvas_grading_type(assignment_type: str) -> str:
    """
    Map a template assignment_type to the Canvas grading_type string it requires.
    Returns "" if no conversion is needed (e.g. "mixed").
    """
    return {
        "complete_incomplete": "pass_fail",
        "discussion_ci":       "pass_fail",
        "discussion_points":   "points",
        "discussion_letter":   "letter_grade",
    }.get(assignment_type, "")


def _bulk_is_autogradeable(assignment: dict, desired_grading_type: str = "") -> bool:
    """Return True if the autograder can handle this assignment type.

    desired_grading_type: the Canvas grading_type the template will convert
    this assignment to (from _template_atype_to_canvas_grading_type).  When
    provided, written-submission assignments that are NOT yet pass_fail are
    also considered autogradeable so the conversion step can fix them.
    """
    grading_type = assignment.get("grading_type", "")
    submission_types = assignment.get("submission_types", [])
    if grading_type == "pass_fail" or "discussion_topic" in submission_types:
        return True
    # Template will convert this assignment — allow it if it has writable submissions
    if desired_grading_type and grading_type != "not_graded":
        return bool(set(submission_types) & _WRITABLE_SUBMISSION_TYPES)
    return False


# ---------------------------------------------------------------------------
# Demo run worker
# ---------------------------------------------------------------------------

class DemoRunWorker(QThread):
    """
    Simulates a grading run using demo_data.simulate_grading_run.
    Signals match RunWorker so RunDialog's handlers work unchanged.
    """

    log_line = Signal(str)
    progress = Signal(int, int)   # (completed, total)
    finished = Signal(bool, str)  # (success, summary_message)
    surface  = Signal(str, dict)  # (card_type, data) — matches RunWorker

    def __init__(self, selected_items: list, parent=None):
        super().__init__(parent)
        self._selected  = selected_items
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            from demo_data import simulate_grading_run

            results = simulate_grading_run(
                selected     = self._selected,
                callback     = lambda line, done, total: (
                    self.log_line.emit(line),
                    self.progress.emit(done, total),
                ),
                cancel_check = lambda: self._cancelled,
            )

            n = results["graded"]
            c = results["complete"]
            i = results["incomplete"]
            f = results["flagged"]
            msg = (
                f"Graded {n} submissions — "
                f"{c} Complete, {i} Incomplete"
                + (f", {f} flagged for review" if f else "")
            )
            self.finished.emit(True, msg)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Insights Engine worker
# ---------------------------------------------------------------------------

class InsightsWorker(CancellableWorker):
    """Runs the Insights Engine analysis pipeline in a background thread.

    Signals:
        progress_update(str): status messages from the pipeline
        analysis_complete(str): run_id on success
        error(str): error message on failure (inherited)
    """

    progress_update = Signal(str)
    result_ready = Signal(str, dict)  # (result_type, data) for live preview
    analysis_complete = Signal(str)

    def __init__(
        self,
        api,
        *,
        store=None,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[dict] = None,
        teacher_interests: Optional[list] = None,
        settings: Optional[dict] = None,
        course_profile_id: str = "default",
        next_week_topic: str = "",
        teacher_lens: str = "",
        ai_policy: str = "not_expected",
        parent=None,
    ):
        super().__init__(api, parent)
        self._store = store
        self._course_id = course_id
        self._course_name = course_name
        self._assignment_id = assignment_id
        self._assignment_name = assignment_name
        self._is_discussion = is_discussion
        self._translate_enabled = translate_enabled
        self._transcribe_enabled = transcribe_enabled
        self._model_tier = model_tier
        self._teacher_context = teacher_context
        self._analysis_lens = analysis_lens
        self._teacher_interests = teacher_interests
        self._settings = settings or {}
        self._course_profile_id = course_profile_id
        self._next_week_topic = next_week_topic
        self._teacher_lens = teacher_lens
        self._ai_policy = ai_policy

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            def _result(result_type: str, data: dict) -> None:
                self.result_ready.emit(result_type, data)

            run_id = engine.run_analysis(
                course_id=self._course_id,
                course_name=self._course_name,
                assignment_id=self._assignment_id,
                assignment_name=self._assignment_name,
                is_discussion=self._is_discussion,
                translate_enabled=self._translate_enabled,
                transcribe_enabled=self._transcribe_enabled,
                model_tier=self._model_tier,
                teacher_context=self._teacher_context,
                analysis_lens=self._analysis_lens,
                teacher_interests=self._teacher_interests,
                progress_callback=_progress,
                result_callback=_result,
                course_profile_id=self._course_profile_id,
                next_week_topic=self._next_week_topic,
                teacher_lens=self._teacher_lens,
                ai_policy=self._ai_policy,
            )

            if run_id:
                self.analysis_complete.emit(run_id)
            elif not self.is_cancelled():
                self.error.emit("Analysis returned no results.")
        except Exception as exc:
            log.exception("InsightsWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Partial re-run worker (Phase 3)
# ---------------------------------------------------------------------------

class PartialRerunWorker(CancellableWorker):
    """Re-runs downstream pipeline stages after teacher edits.

    Trigger mapping:
      Change student tags   -> start_stage="themes"   -> themes + outliers + synthesis
      Split/merge/rename    -> start_stage="outliers"  -> outliers + synthesis
      Dismiss/add outlier   -> start_stage="synthesis"  -> synthesis only
    """

    progress_update = Signal(str)
    rerun_complete = Signal(str, list)  # (run_id, stages_re_run)

    def __init__(
        self,
        api,
        *,
        run_id: str,
        start_stage: str,
        store=None,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._run_id = run_id
        self._start_stage = start_stage
        self._store = store
        self._settings = settings or {}

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            result = engine.run_partial(
                run_id=self._run_id,
                start_stage=self._start_stage,
                progress_callback=_progress,
            )

            if result:
                stages = {
                    "themes": ["themes", "outliers", "synthesis"],
                    "outliers": ["outliers", "synthesis"],
                    "synthesis": ["synthesis"],
                }
                self.rerun_complete.emit(
                    self._run_id, stages.get(self._start_stage, [])
                )
            elif not self.is_cancelled():
                self.error.emit("Partial re-run returned no results.")
        except Exception as exc:
            log.exception("PartialRerunWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Feedback post worker (Phase 4)
# ---------------------------------------------------------------------------

class FeedbackPostWorker(QThread):
    """Post approved feedback to Canvas as assignment comments.

    Signals:
        post_progress(str): "Posting feedback for Maria Garcia..."
        post_complete(int, int): (success_count, fail_count)
        error(str): error message
    """

    post_progress = Signal(str)
    post_complete = Signal(int, int)
    error = Signal(str)

    def __init__(
        self,
        api,
        *,
        store,
        run_id: str,
        course_id: str,
        assignment_id: str,
        parent=None,
    ):
        super().__init__(parent)
        self._api = api
        self._store = store
        self._run_id = run_id
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            import requests

            approved = self._store.get_approved_feedback(self._run_id)
            if not approved:
                self.post_complete.emit(0, 0)
                return

            success = 0
            fail = 0
            headers = dict(self._api.headers) if self._api else {}
            base_url = self._api.base_url.rstrip("/") if self._api else ""

            for fb in approved:
                if self._cancelled:
                    break

                student_name = fb.get("student_name", fb.get("student_id", ""))
                self.post_progress.emit(
                    f"Posting feedback for {student_name}..."
                )

                text = fb.get("approved_text") or fb.get("draft_text", "")
                if not text:
                    fail += 1
                    continue

                try:
                    url = (
                        f"{base_url}/api/v1/courses/{self._course_id}"
                        f"/assignments/{self._assignment_id}"
                        f"/submissions/{fb['student_id']}"
                    )
                    r = requests.put(
                        url,
                        headers=headers,
                        json={"comment": {"text_comment": text}},
                        timeout=30,
                    )
                    r.raise_for_status()
                    self._store.update_feedback_status(
                        self._run_id, fb["student_id"], "posted",
                        approved_text=text,
                    )
                    success += 1
                except Exception as e:
                    log.warning(
                        "Failed to post feedback for %s: %s", student_name, e
                    )
                    fail += 1

            self.post_complete.emit(success, fail)

        except Exception as exc:
            log.exception("FeedbackPostWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Batch insights worker (Phase 3)
# ---------------------------------------------------------------------------

class BatchInsightsWorker(CancellableWorker):
    """Runs insights analysis across multiple assignments sequentially.

    Signals:
        progress_update(str): per-run progress messages
        run_complete(str, int, int): (run_id, run_index, total_runs)
        batch_complete(list): list of completed run_ids
    """

    progress_update = Signal(str)
    result_ready = Signal(str, dict)  # (result_type, data) for live preview
    run_complete = Signal(str, int, int)
    batch_complete = Signal(list)

    def __init__(
        self,
        api,
        *,
        assignments: list,  # [(course_dict, assignment_dict), ...]
        store=None,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[dict] = None,
        teacher_interests: Optional[list] = None,
        settings: Optional[dict] = None,
        course_profile_id: str = "default",
        next_week_topic: str = "",
        teacher_lens: str = "",
        ai_policy: str = "not_expected",
        parent=None,
    ):
        super().__init__(api, parent)
        self._assignments = assignments
        self._store = store
        self._translate_enabled = translate_enabled
        self._transcribe_enabled = transcribe_enabled
        self._model_tier = model_tier
        self._teacher_context = teacher_context
        self._analysis_lens = analysis_lens
        self._teacher_interests = teacher_interests
        self._settings = settings or {}
        self._course_profile_id = course_profile_id
        self._next_week_topic = next_week_topic
        self._teacher_lens = teacher_lens
        self._ai_policy = ai_policy

    def run(self) -> None:
        completed_ids = []
        total = len(self._assignments)

        try:
            from insights.engine import InsightsEngine

            for idx, (course, assignment) in enumerate(self._assignments):
                if self.is_cancelled():
                    break

                assign_name = assignment.get("name", "Unknown")
                course_name = course.get("name", "")
                code = course.get("course_code", "")
                display = f"{code} — {assign_name}" if code else assign_name
                self.progress_update.emit(
                    f"Run {idx + 1}/{total}: {assign_name}..."
                )
                # Stage divider in live results
                self.result_ready.emit("stage", {
                    "stage": f"RUN {idx + 1}/{total}: {display}",
                })

                is_discussion = (
                    assignment.get("submission_types", []) == ["discussion_topic"]
                )

                engine = InsightsEngine(
                    api=self._api,
                    store=self._store,
                    settings=self._settings,
                )

                def _progress(msg: str, _idx=idx, _total=total,
                              _cname=course_name, _aname=assign_name) -> None:
                    # For batch runs, show which assignment we're on
                    # without doubling up the counter brackets
                    prefix = (
                        f"Run {_idx + 1}/{_total} · {_aname}"
                        if _total > 1 else ""
                    )
                    if prefix:
                        self.progress_update.emit(f"{prefix} — {msg}")
                    else:
                        self.progress_update.emit(msg)
                    if self.is_cancelled():
                        engine.cancel()

                def _result(result_type: str, data: dict) -> None:
                    self.result_ready.emit(result_type, data)

                run_id = engine.run_analysis(
                    course_id=course["id"],
                    course_name=course_name,
                    assignment_id=assignment["id"],
                    assignment_name=assign_name,
                    is_discussion=is_discussion,
                    translate_enabled=self._translate_enabled,
                    transcribe_enabled=self._transcribe_enabled,
                    model_tier=self._model_tier,
                    teacher_context=self._teacher_context,
                    analysis_lens=self._analysis_lens,
                    teacher_interests=self._teacher_interests,
                    progress_callback=_progress,
                    result_callback=_result,
                    course_profile_id=self._course_profile_id,
                    next_week_topic=self._next_week_topic,
                    teacher_lens=self._teacher_lens,
                    ai_policy=self._ai_policy,
                )

                if run_id:
                    completed_ids.append(run_id)
                    self.run_complete.emit(run_id, idx + 1, total)

            self.batch_complete.emit(completed_ids)
        except Exception as exc:
            log.exception("BatchInsightsWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Resume workers for interrupted runs
# ---------------------------------------------------------------------------

class RerunWorker(CancellableWorker):
    """Resume a partial run from themes/outliers/synthesis stage.

    Uses engine.run_partial() to pick up where the pipeline stopped.
    """

    progress_update = Signal(str)
    analysis_complete = Signal(str)

    def __init__(
        self,
        store,
        *,
        run_id: str,
        start_stage: str,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api=None, parent=parent)
        self._store = store
        self._run_id = run_id
        self._start_stage = start_stage
        self._settings = settings or {}

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            result = engine.run_partial(
                run_id=self._run_id,
                start_stage=self._start_stage,
                progress_callback=_progress,
            )

            if result:
                self.analysis_complete.emit(self._run_id)
            elif not self.is_cancelled():
                self.error.emit("Resume returned no results.")
        except Exception as exc:
            log.exception("RerunWorker failed: %s", exc)
            self.error.emit(str(exc))


class ResumeInsightsWorker(CancellableWorker):
    """Resume an interrupted run from coding or concerns stage.

    Re-runs the full pipeline but skips already-coded students
    and already-completed stages.
    """

    progress_update = Signal(str)
    result_ready = Signal(str, dict)
    analysis_complete = Signal(str)

    def __init__(
        self,
        api,
        *,
        store=None,
        run_id: str,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._store = store
        self._run_id = run_id
        self._settings = settings or {}

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            def _result(result_type: str, data: dict) -> None:
                self.result_ready.emit(result_type, data)

            result = engine.resume_run(
                run_id=self._run_id,
                progress_callback=_progress,
                result_callback=_result,
            )

            if result:
                self.analysis_complete.emit(self._run_id)
            elif not self.is_cancelled():
                self.error.emit("Resume returned no results.")
        except Exception as exc:
            log.exception("ResumeInsightsWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# PostCanvasCommentWorker
# ---------------------------------------------------------------------------

class PostCanvasCommentWorker(QThread):
    """Post a text comment on a student's Canvas submission."""

    comment_result = Signal(bool, str)  # (ok, message)

    def __init__(self, api, course_id: str, assignment_id: str,
                 student_id: str, text: str, parent=None):
        super().__init__(parent)
        self._api = api
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._student_id = student_id
        self._text = text

    def run(self):
        try:
            import requests as _requests
            if not self._api or not self._api.base_url:
                self.comment_result.emit(False, "Canvas API not configured")
                return
            url = (
                f"{self._api.base_url.rstrip('/')}/api/v1"
                f"/courses/{self._course_id}"
                f"/assignments/{self._assignment_id}"
                f"/submissions/{self._student_id}"
            )
            resp = _requests.put(
                url,
                headers=self._api.headers,
                json={"comment": {"text_comment": self._text}},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                self.comment_result.emit(True, "")
            else:
                self.comment_result.emit(False, f"HTTP {resp.status_code}")
        except Exception as exc:
            log.exception("PostCanvasCommentWorker failed: %s", exc)
            self.comment_result.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Research comparison worker
# ---------------------------------------------------------------------------

class ResearchComparisonWorker(CancellableWorker):
    """Background thread for the 3-way classification comparison.

    Two run modes:
      "full"          — fetch from Canvas, run all shared stages + all 3 tracks
      "track_a_only"  — use stored submission texts, run only binary Track A
    """

    progress_update = Signal(str)
    track_result = Signal(str, str, dict)   # (track_name, student_id, data)
    comparison_complete = Signal(dict)
    # error(str) inherited from CancellableWorker

    def __init__(
        self,
        api,
        *,
        store=None,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        model_tier: str = "auto",
        settings: Optional[dict] = None,
        run_mode: str = "full",         # "full" | "track_a_only"
        prior_run_id: Optional[str] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._store = store
        self._course_id = course_id
        self._course_name = course_name
        self._assignment_id = assignment_id
        self._assignment_name = assignment_name
        self._is_discussion = is_discussion
        self._model_tier = model_tier
        self._settings = settings or {}
        self._run_mode = run_mode
        self._prior_run_id = prior_run_id

    def run(self) -> None:
        try:
            from dataclasses import asdict
            from research.research_engine import ResearchEngine

            engine = ResearchEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            def _track(track: str, sid: str, data: dict) -> None:
                self.track_result.emit(track, sid, data)

            if self._run_mode == "track_a_only":
                if not self._prior_run_id:
                    self.error.emit("track_a_only mode requires prior_run_id")
                    return

                # Load stored submission texts from the prior run
                texts = engine.get_stored_texts(self._prior_run_id)
                if not texts:
                    self.error.emit(
                        "No stored submission texts found in prior run. "
                        "Run Full Comparison instead."
                    )
                    return

                # Build student_names from prior run codings
                names: dict = {}
                if engine._store:
                    try:
                        codings = engine._store.get_codings(self._prior_run_id)
                        names = {
                            str(row["student_id"]): row.get("student_name", "")
                            for row in codings
                            if row.get("student_id")
                        }
                    except Exception:
                        pass

                track_a_results = engine.run_track_a_only(
                    texts=texts,
                    student_names=names,
                    assignment_prompt=self._assignment_name,
                    model_tier=self._model_tier,
                    progress=_progress,
                    track_cb=_track,
                )

                if self.is_cancelled():
                    return

                # Merge Track A into the prior comparison result
                prior = engine.load_prior_run(
                    self._prior_run_id,
                    course_id=str(self._course_id),
                    course_name=self._course_name,
                    assignment_id=str(self._assignment_id),
                    assignment_name=self._assignment_name,
                )
                if prior is None:
                    self.error.emit("Could not load prior run data.")
                    return

                for sid, ta in track_a_results.items():
                    if sid in prior.comparisons:
                        prior.comparisons[sid].track_a = ta

                prior.metadata.tracks_freshly_run = ["track_a"]
                prior.metadata.tracks_from_prior = ["track_b", "track_c"]
                self.comparison_complete.emit(asdict(prior))

            else:
                # Full comparison
                result = engine.run_comparison(
                    course_id=self._course_id,
                    course_name=self._course_name,
                    assignment_id=self._assignment_id,
                    assignment_name=self._assignment_name,
                    is_discussion=self._is_discussion,
                    model_tier=self._model_tier,
                    progress=_progress,
                    track_cb=_track,
                )
                if result and not self.is_cancelled():
                    self.comparison_complete.emit(asdict(result))
                elif not self.is_cancelled():
                    self.error.emit("Comparison returned no results.")

        except Exception as exc:
            log.exception("ResearchComparisonWorker failed: %s", exc)
            self.error.emit(str(exc))
