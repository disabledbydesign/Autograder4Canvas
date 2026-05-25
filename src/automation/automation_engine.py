"""
Canvas Autograder - Automation Engine
Main orchestration engine for automated grading.
"""

import os
import sys
import logging
import requests
import importlib.util
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from dateutil import parser
import pytz

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .course_config import AutomationConfig, CourseConfig, AssignmentRule
from .canvas_helpers import CanvasAutomationAPI
from .grade_checker import GradeChecker
from .flag_aggregator import FlagAggregator
from .notification_manager import NotificationManager, IncompleteEvent
from .reply_quality_checker import OllamaReplyChecker


class AutomationEngine:
    """Main automation engine for Canvas autograding."""

    def __init__(self, config_path: str, dry_run: bool = False, course_filter: Optional[int] = None):
        """
        Initialize automation engine.

        Args:
            config_path: Path to configuration JSON file
            dry_run: If True, don't actually submit grades
            course_filter: If set, only process this course ID
        """
        self.config_path = Path(config_path)
        self.dry_run = dry_run
        self.course_filter = course_filter

        # Load configuration
        self.config = AutomationConfig.load(self.config_path)

        # Initialize helpers
        self.api = CanvasAutomationAPI()
        self.grade_checker = GradeChecker()
        self.flag_aggregator = FlagAggregator(
            self.config.global_settings.flag_excel_path
        )

        # Setup logging
        self.logger = self._setup_logging()

        # Notification manager (only if configured)
        gs = self.config.global_settings
        if gs.n8n_webhook_url and gs.notify_email:
            self.notifier = NotificationManager(gs.n8n_webhook_url, gs.notify_email)
        else:
            self.notifier = None

        # LLM reply quality checker (lazy — only used when rule enables it)
        self._reply_checker = None

        # Canvas API details
        self.base_url = os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com")
        self.api_token = os.getenv("CANVAS_API_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup logging to file and console."""
        logger = logging.getLogger('autograder_automation')
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers.clear()

        # File handler
        log_path = Path(self.config.global_settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def run(self):
        """Main execution - runs unattended."""
        self.logger.info("=" * 60)
        self.logger.info("AUTOMATION RUN STARTED")
        self.logger.info("=" * 60)

        if self.dry_run:
            self.logger.info("🔍 DRY RUN MODE - No grades will be submitted")

        # Check for new assignments (if enabled)
        if self.config.global_settings.auto_update_enabled:
            self._check_for_new_assignments()

        # Process each enabled course
        stats = {
            'courses': 0,
            'assignments': 0,
            'submissions_graded': 0,
            'submissions_skipped': 0,
            'flags': 0
        }

        for course_id, course_config in self.config.courses.items():
            # Apply course filter if set
            if self.course_filter and course_id != self.course_filter:
                continue

            if not course_config.enabled:
                self.logger.info(f"⏭️  Skipping disabled course: {course_config.course_name}")
                continue

            try:
                course_stats = self._process_course(course_id, course_config)
                stats['courses'] += 1
                stats['assignments'] += course_stats['assignments']
                stats['submissions_graded'] += course_stats['submissions_graded']
                stats['submissions_skipped'] += course_stats['submissions_skipped']
                stats['flags'] += course_stats['flags']

            except Exception as e:
                self.logger.error(f"❌ Course {course_id} ({course_config.course_name}) failed: {e}", exc_info=True)
                # Continue to next course

        # Save aggregated flags
        if stats['flags'] > 0:
            self.flag_aggregator.save()

        # Generate summary report
        self._generate_summary(stats)

        # Send notification digest if any incompletes were found
        if self.notifier:
            self.notifier.send_digest()

        self.logger.info("=" * 60)
        self.logger.info("AUTOMATION RUN COMPLETED")
        self.logger.info("=" * 60)

    def _process_course(self, course_id: int, config: CourseConfig) -> Dict[str, int]:
        """
        Process all assignment groups in a course.

        Args:
            course_id: Canvas course ID
            config: Course configuration

        Returns:
            Dictionary of statistics
        """
        self.logger.info("")
        self.logger.info(f"📚 Processing course: {config.course_name} ({course_id})")

        stats = {
            'assignments': 0,
            'submissions_graded': 0,
            'submissions_skipped': 0,
            'flags': 0
        }

        for rule in config.assignment_rules:
            # Get assignments matching this rule
            assignments = self._get_assignments_for_rule(course_id, rule)

            self.logger.info(f"  📁 Group: {rule.assignment_group_name} ({len(assignments)} assignments)")

            for assignment in assignments:
                # Skip checks
                if self._should_skip_assignment(assignment, rule):
                    continue

                # Process assignment (handles type auto-detection for mixed assignments)
                try:
                    graded_count, skipped_count = self._process_assignment(
                        course_id, assignment, rule, config.course_name
                    )

                    stats['assignments'] += 1
                    stats['submissions_graded'] += graded_count
                    stats['submissions_skipped'] += skipped_count

                    # Run ADC if enabled and submissions were graded
                    if rule.run_adc and graded_count > 0:
                        flags = self._run_adc(course_id, assignment, config.course_name)
                        if flags:
                            self.flag_aggregator.add_flags(flags)
                            stats['flags'] += len(flags)

                except Exception as e:
                    self.logger.error(f"    ❌ Failed to grade {assignment['name']}: {e}")
                    continue

        return stats

    def _should_skip_assignment(self, assignment: Dict[str, Any], rule: AssignmentRule) -> bool:
        """
        Intelligent skipping logic.

        Args:
            assignment: Assignment dictionary
            rule: Assignment rule

        Returns:
            True if should skip
        """
        # Skip if future deadline
        if self.config.global_settings.skip_future_assignments:
            if self.api.is_future_assignment(assignment):
                self.logger.info(f"    ⏭️  Skipping {assignment['name']}: future deadline")
                return True

        # Skip if no submissions
        if self.config.global_settings.skip_no_submissions:
            submission_count = self.api.get_submission_count(
                assignment['course_id'], assignment['id']
            )
            if submission_count == 0:
                self.logger.info(f"    ⏭️  Skipping {assignment['name']}: no submissions")
                return True

        return False

    def _get_assignments_for_rule(self, course_id: int, rule: AssignmentRule) -> List[Dict[str, Any]]:
        """
        Get assignments matching a rule.

        Args:
            course_id: Canvas course ID
            rule: Assignment rule

        Returns:
            List of assignment dictionaries
        """
        assignments = self.api.get_assignments_in_group(course_id, rule.assignment_group_id)
        return assignments

    def _process_assignment(self, course_id: int, assignment: Dict[str, Any],
                           rule: AssignmentRule, course_name: str) -> tuple:
        """
        Process a single assignment, auto-detecting type for mixed assignments.

        For 'mixed' assignment types, inspects Canvas submission_types to determine
        whether the assignment is a discussion forum or regular submission, then
        routes to the appropriate grading method.

        Returns:
            Tuple of (graded_count, skipped_count)
        """
        assignment_type = rule.assignment_type

        if assignment_type == "mixed":
            submission_types = assignment.get('submission_types', [])
            if 'discussion_topic' in submission_types:
                assignment_type = "discussion_forum"
                self.logger.debug(f"      🔍 Mixed type detected as: discussion_forum")
            else:
                assignment_type = "complete_incomplete"
                self.logger.debug(f"      🔍 Mixed type detected as: complete_incomplete")

        if assignment_type == "discussion_forum":
            return self._run_discussion_forum(course_id, assignment, rule, course_name)
        elif assignment_type == "complete_incomplete":
            return self._run_complete_incomplete(course_id, assignment, rule, course_name)
        else:
            self.logger.warning(f"    ⚠️  Unknown assignment type: {assignment_type}")
            return 0, 0

    def _run_complete_incomplete(self, course_id: int, assignment: Dict[str, Any],
                                 rule: AssignmentRule, course_name: str = "") -> tuple:
        """
        Execute complete/incomplete grading.

        Args:
            course_id: Canvas course ID
            assignment: Assignment dictionary
            rule: Assignment rule
            course_name: Course name for notification events

        Returns:
            Tuple of (graded_count, skipped_count)
        """
        # Dynamic import for hyphenated filename
        module_path = Path(__file__).parent.parent / "Programs" / "Autograder_Complete-Incomplete_v1-3.py"
        spec = importlib.util.spec_from_file_location("autograder_ci", module_path)
        autograder_ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(autograder_ci)

        assignment_id = assignment['id']
        assignment_name = assignment['name']

        self.logger.info(f"    📝 Grading: {assignment_name}")

        # Fetch data
        students = autograder_ci.get_active_students(course_id)
        submissions = autograder_ci.get_submissions(course_id, assignment_id)

        # Build student name lookup and active student id set
        student_names = {}
        active_student_ids = set()
        for enrollment in students:
            user = enrollment.get('user', {})
            uid = user.get('id')
            student_names[uid] = user.get('name', f"Student {uid!r}")
            if uid is not None:
                active_student_ids.add(uid)

        # Filter out students who never submitted (keep for absent-grading check below)
        submitted = {
            user_id: sub for user_id, sub in submissions.items()
            if sub.get('submitted_at') is not None
        }
        absent_ids = active_student_ids - set(submitted.keys())
        submissions = submitted

        # Apply grade preservation filter
        if rule.preserve_existing_grades:
            original_count = len(submissions)
            submissions = self.grade_checker.filter_gradeable(submissions)
            skipped_count = original_count - len(submissions)

            if skipped_count > 0:
                self.logger.info(f"      ℹ️  {skipped_count} already graded, skipping")
        else:
            skipped_count = 0

        if not submissions:
            self.logger.info(f"      ⏭️  All submissions already graded")
            return 0, skipped_count

        # Determine grading mode
        use_points = (rule.grading_type == "points")
        max_points = assignment.get('points_possible', 0) if use_points else None

        # Evaluate submissions
        grade_data = {}
        all_submissions_list = list(submissions.values())

        for user_id, submission in submissions.items():
            is_complete, flags = autograder_ci.evaluate_submission(
                submission, all_submissions_list, rule.min_word_count
            )

            if is_complete:
                if use_points:
                    grade_data[user_id] = {"score": max_points}
                else:
                    grade_data[user_id] = {"posted_grade": "complete"}
            else:
                # Never assign 0/incomplete — grant credit and flag for manual review
                if use_points:
                    grade_data[user_id] = {"score": max_points}
                else:
                    grade_data[user_id] = {"posted_grade": "complete"}
                # Collect notification event so instructor can review manually
                if self.notifier:
                    body = submission.get("body", "")
                    word_count = self._count_words(body) if body else 0
                    self.notifier.add_event(IncompleteEvent(
                        course_name=course_name,
                        assignment_name=assignment_name,
                        student_name=student_names.get(user_id, f"Student {user_id}"),
                        student_id=user_id,
                        course_id=course_id,
                        assignment_id=assignment_id,
                        word_count=word_count,
                        required_words=rule.min_word_count or 0,
                        category="ci"
                    ))

        # If mark_missing_as_incomplete is set, grade absent students as Incomplete
        if rule.mark_missing_as_incomplete:
            for user_id in absent_ids:
                grade_data[user_id] = {"posted_grade": "incomplete"}
            if absent_ids:
                self.logger.info(f"      ℹ️  {len(absent_ids)} absent student(s) marked Incomplete")

        # If mark_missing_as_zero is set (points mode), grade absent students as 0
        # Only for past-due assignments — never push 0 for future work
        if rule.mark_missing_as_zero and use_points:
            if not self.api.is_future_assignment(assignment):
                for user_id in absent_ids:
                    grade_data[user_id] = {"score": 0}
                if absent_ids:
                    self.logger.info(f"      ℹ️  {len(absent_ids)} absent student(s) marked 0 pts (past due)")
            else:
                self.logger.info(f"      ⏭️  Skipping mark_missing_as_zero — assignment is not yet past due")

        # Submit grades to Canvas (unless dry-run)
        if not self.dry_run and grade_data:
            self._submit_grades(course_id, assignment_id, grade_data)
            if use_points:
                full_count = sum(1 for g in grade_data.values() if g.get("score", 0) > 0)
                zero_count = sum(1 for g in grade_data.values() if g.get("score", 0) == 0)
                self.logger.info(f"      ✅ Graded {len(grade_data)}: {full_count} full credit, {zero_count} marked 0")
            else:
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                flagged_count = len(grade_data) - complete_count
                self.logger.info(f"      ✅ Graded {len(grade_data)}: {complete_count} complete, {flagged_count} flagged for review (granted credit)")
        elif self.dry_run:
            if use_points:
                full_count = sum(1 for g in grade_data.values() if g.get("score", 0) > 0)
                zero_count = sum(1 for g in grade_data.values() if g.get("score", 0) == 0)
                self.logger.info(f"      🔍 Would grade {len(grade_data)} ({full_count} full credit, {zero_count} zero)")
            else:
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                self.logger.info(f"      🔍 Would grade {len(grade_data)} ({complete_count} complete, {len(grade_data) - complete_count} flagged for review)")
        else:
            self.logger.info(f"      ℹ️  No submissions to evaluate")

        return len(grade_data), skipped_count

    def _run_discussion_forum(self, course_id: int, assignment: Dict[str, Any],
                             rule: AssignmentRule, course_name: str = "") -> tuple:
        """
        Execute discussion forum grading.

        Handles two modes:
        - "separate": Posts and replies evaluated independently against their own
          word count thresholds. Student must have >= min_posts qualifying posts
          AND >= min_replies qualifying replies.
        - "combined": All messages (posts + replies) pooled together. Total word
          count checked against post_min_words as the threshold.

        Args:
            course_id: Canvas course ID
            assignment: Assignment dictionary (must have discussion_topic link)
            rule: Assignment rule
            course_name: Course name for notification events

        Returns:
            Tuple of (graded_count, skipped_count)
        """
        assignment_id = assignment['id']
        assignment_name = assignment['name']

        # Get the linked discussion topic ID
        topic_id = self._get_discussion_topic_id(assignment)
        if not topic_id:
            self.logger.warning(f"    ⚠️  {assignment_name}: no linked discussion topic found")
            return 0, 0

        self.logger.info(f"    💬 Discussion: {assignment_name} (topic {topic_id})")

        # Fetch discussion entries from Canvas
        entries = self._fetch_discussion_entries(course_id, topic_id)
        if not entries:
            self.logger.info(f"      ℹ️  No entries in this discussion")
            return 0, 0

        # Categorize entries into posts vs replies per student
        student_data = self._categorize_discussion_entries(entries)
        self.logger.info(f"      ℹ️  {len(student_data)} student(s) participated")

        # Build student name lookup from entries (Canvas includes user info)
        student_names = {}
        for entry in entries:
            uid = entry.get("user_id")
            user = entry.get("user", {})
            if uid and user:
                student_names[uid] = user.get("name", f"Student {uid}")

        # Determine grading mode
        mode = rule.discussion_grading_mode or "separate"
        grading_type = rule.grading_type or "complete_incomplete"
        grade_data = {}
        skipped_count = 0

        if grading_type == "points":
            # ── Points mode: incremental reply tracking ──
            # Resolve the reply credit assignment ID for this discussion (if configured).
            # When set, reply points go to a separate not_graded Canvas assignment so
            # students see a clean score (no percentage display) for post vs reply credit.
            reply_credit_assignment_id: Optional[int] = None
            if rule.reply_credit_assignment_ids:
                for week_key, rcid in rule.reply_credit_assignment_ids.items():
                    if week_key.lower() in assignment_name.lower():
                        reply_credit_assignment_id = rcid
                        break
                if reply_credit_assignment_id:
                    self.logger.info(
                        f"      📋 Reply credits → assignment {reply_credit_assignment_id}"
                    )

            # Fetch existing submissions for the post assignment — abort if this fails
            # to avoid writing bad state (e.g. treating already-graded students as ungraded)
            try:
                existing_subs = self._fetch_submissions(course_id, assignment_id)
            except Exception as e:
                self.logger.error(
                    f"      ❌ Aborting {assignment_name}: could not fetch existing grades ({e}). "
                    f"State file not modified."
                )
                return 0, 0

            existing_grades = {
                uid: sub for uid, sub in existing_subs.items()
                if sub.get("workflow_state") == "graded"
            }

            # Also fetch existing reply credit grades if using a separate assignment
            existing_reply_grades: Dict[int, float] = {}
            if reply_credit_assignment_id:
                try:
                    reply_subs = self._fetch_submissions(course_id, reply_credit_assignment_id)
                    existing_reply_grades = {
                        uid: float(sub.get("score") or 0)
                        for uid, sub in reply_subs.items()
                        if sub.get("workflow_state") == "graded"
                    }
                except Exception as e:
                    self.logger.warning(
                        f"      ⚠️  Could not fetch reply credit grades for assignment "
                        f"{reply_credit_assignment_id}: {e}. Treating all reply scores as 0."
                    )

            state_key = f"{course_id}:{assignment_id}"
            full_state = self._load_discussion_state()
            assignment_state = full_state.get(state_key, {})

            # Collect state updates in memory — only flushed to disk after
            # _submit_grades succeeds, so a Canvas timeout can't leave the state
            # file ahead of what was actually graded.
            pending_state: Dict[int, Dict[str, Any]] = {}

            # Separate grade_data dicts: post scores go to the discussion assignment,
            # reply scores go to the reply credit assignment (or fall back to post assignment)
            post_grade_data: Dict[int, Dict[str, Any]] = {}
            reply_grade_data: Dict[int, Dict[str, Any]] = {}

            for user_id, data in student_data.items():
                student_name = student_names.get(user_id, f"Student {user_id}")
                student_state = assignment_state.get(str(user_id), {})

                if user_id not in existing_grades:
                    # ── Scenario A: never graded — score posts and replies from scratch ──
                    post_score, reply_score = self._score_discussion_student_split(data, rule, mode)

                    # Never assign 0 — grant full post credit and flag for manual review
                    needs_review = post_score == 0
                    if needs_review:
                        post_score = rule.post_points if rule.post_points is not None else 1.0

                    post_grade_data[user_id] = {"score": post_score}
                    if reply_score > 0:
                        reply_grade_data[user_id] = {"score": reply_score}

                    # Stage state update — written after successful grade submission
                    all_ids = [e["id"] for e in data["posts"] + data["replies"]]
                    credited_replies = [e for e in data["replies"]
                                        if self._count_words(e["message"]) >= (rule.reply_min_words or 40)]
                    pending_state[user_id] = {
                        "credited_entry_ids": all_ids,
                        "reply_audit": self._build_reply_audit(
                            data["replies"], credited_replies, rule, student_state
                        )
                    }

                    total_score = post_score + reply_score
                    self.logger.info(
                        f"      👤 {student_name}: first grade → "
                        f"post {post_score:.1f} + reply {reply_score:.1f} = {total_score:.1f}"
                        + (" [flagged for manual review]" if needs_review else "")
                    )

                    # Notify if post didn't qualify — granted credit but flag for manual review
                    if self.notifier and needs_review:
                        post_words = sum(self._count_words(e["message"]) for e in data["posts"])
                        self.notifier.add_event(IncompleteEvent(
                            course_name=course_name,
                            assignment_name=assignment_name,
                            student_name=student_name,
                            student_id=user_id,
                            course_id=course_id,
                            assignment_id=assignment_id,
                            word_count=post_words,
                            required_words=rule.post_min_words or 200,
                            category="discussion_post"
                        ))
                else:
                    # ── Scenario B: already graded ──
                    canvas_post_score = float(existing_grades[user_id].get("score") or 0)
                    canvas_reply_score = existing_reply_grades.get(user_id, 0.0)

                    # One-time migration: if no state entry yet, lock all currently-visible
                    # entry IDs so existing work isn't re-scored on first run under new system
                    if not student_state:
                        all_current_ids = [e["id"] for e in data["posts"] + data["replies"]]
                        self.logger.info(
                            f"      👤 {student_name}: migrating — locking "
                            f"{len(all_current_ids)} existing entries"
                        )
                        student_state = {"credited_entry_ids": all_current_ids, "reply_audit": []}
                        pending_state[user_id] = student_state

                    # Check for new replies not yet credited
                    delta, new_ids, new_audit = self._score_new_replies_for_student(
                        data, rule, student_state
                    )

                    if delta > 0:
                        new_reply_total = canvas_reply_score + delta
                        reply_grade_data[user_id] = {"score": new_reply_total}

                        updated_ids = student_state.get("credited_entry_ids", []) + new_ids
                        existing_audit = student_state.get("reply_audit", [])
                        pending_state[user_id] = {
                            "credited_entry_ids": updated_ids,
                            "reply_audit": existing_audit + new_audit
                        }

                        self.logger.info(
                            f"      👤 {student_name}: +{delta:.1f} reply credit "
                            f"({canvas_reply_score:.1f} → {new_reply_total:.1f})"
                        )
                    else:
                        # No new qualifying replies — stage tracking of new IDs
                        if new_ids:
                            updated_ids = student_state.get("credited_entry_ids", []) + new_ids
                            existing_audit = student_state.get("reply_audit", [])
                            pending_state[user_id] = {
                                "credited_entry_ids": updated_ids,
                                "reply_audit": existing_audit + new_audit
                            }
                        skipped_count += 1
                        self.logger.info(
                            f"      👤 {student_name}: no new qualifying replies, skipping"
                        )

            # Merge post and reply grade_data for the legacy path (no separate assignment)
            if not reply_credit_assignment_id:
                # No separate reply assignment — combine into single grade on post assignment
                grade_data = {}
                all_uids = set(post_grade_data) | set(reply_grade_data)
                for uid in all_uids:
                    post_s = post_grade_data.get(uid, {}).get("score", 0)
                    reply_s = reply_grade_data.get(uid, {}).get("score", 0)
                    grade_data[uid] = {"score": post_s + reply_s}
            else:
                grade_data = post_grade_data  # used only for the legacy submission path below

        else:
            # ── Complete/Incomplete mode: original skip-if-graded behavior ──
            if rule.preserve_existing_grades:
                try:
                    existing = self._fetch_submissions(course_id, assignment_id)
                    already_graded = self.grade_checker.get_graded_user_ids(existing)
                    if already_graded:
                        skipped_count = len(already_graded & set(student_data.keys()))
                        student_data = {
                            uid: data for uid, data in student_data.items()
                            if uid not in already_graded
                        }
                        self.logger.info(f"      ℹ️  {skipped_count} already graded, skipping")
                except Exception as e:
                    self.logger.warning(f"      ⚠️  Could not check existing grades: {e}")

            for user_id, data in student_data.items():
                is_complete = self._evaluate_discussion_student(data, rule, mode)
                if is_complete:
                    grade_data[user_id] = {"posted_grade": "complete"}
                else:
                    # Never assign 0/incomplete — grant credit and flag for manual review
                    grade_data[user_id] = {"posted_grade": "complete"}
                    # Collect notification events so instructor can review manually
                    if self.notifier and mode == "separate":
                        post_threshold = rule.post_min_words or 200
                        reply_threshold = rule.reply_min_words or 50
                        qualifying_posts = sum(
                            1 for e in data["posts"] if self._count_words(e["message"]) >= post_threshold
                        )
                        min_posts_req = rule.min_posts if rule.min_posts is not None else 1
                        if qualifying_posts < min_posts_req:
                            post_words = sum(self._count_words(e["message"]) for e in data["posts"])
                            self.notifier.add_event(IncompleteEvent(
                                course_name=course_name,
                                assignment_name=assignment_name,
                                student_name=student_names.get(user_id, f"Student {user_id}"),
                                student_id=user_id,
                                course_id=course_id,
                                assignment_id=assignment_id,
                                word_count=post_words,
                                required_words=post_threshold,
                                category="discussion_post"
                            ))
                        qualifying_replies = sum(
                            1 for e in data["replies"] if self._count_words(e["message"]) >= reply_threshold
                        )
                        min_replies_req = rule.min_replies if rule.min_replies is not None else 2
                        if qualifying_replies < min_replies_req:
                            reply_words = sum(self._count_words(e["message"]) for e in data["replies"])
                            self.notifier.add_event(IncompleteEvent(
                                course_name=course_name,
                                assignment_name=assignment_name,
                                student_name=student_names.get(user_id, f"Student {user_id}"),
                                student_id=user_id,
                                course_id=course_id,
                                assignment_id=assignment_id,
                                word_count=reply_words,
                                required_words=reply_threshold,
                                category="discussion_reply"
                            ))
                    elif self.notifier and mode == "combined":
                        all_words = sum(self._count_words(e["message"]) for e in data["posts"] + data["replies"])
                        self.notifier.add_event(IncompleteEvent(
                            course_name=course_name,
                            assignment_name=assignment_name,
                            student_name=student_names.get(user_id, f"Student {user_id}"),
                            student_id=user_id,
                            course_id=course_id,
                            assignment_id=assignment_id,
                            word_count=all_words,
                            required_words=rule.post_min_words or 200,
                            category="discussion_post"
                        ))

        # Submit grades
        if grading_type == "points":
            if not self.dry_run:
                submitted_post_count = 0
                submitted_reply_count = 0

                # Submit post grades to the discussion assignment
                if post_grade_data and reply_credit_assignment_id:
                    self._submit_grades(course_id, assignment_id, post_grade_data)
                    submitted_post_count = len(post_grade_data)
                    post_scores = [g["score"] for g in post_grade_data.values()]
                    self.logger.info(
                        f"      ✅ Post grades submitted ({submitted_post_count}): "
                        f"range {min(post_scores):.1f}–{max(post_scores):.1f}"
                    )
                elif grade_data and not reply_credit_assignment_id:
                    # Legacy path: combined score on post assignment
                    self._submit_grades(course_id, assignment_id, grade_data)
                    submitted_post_count = len(grade_data)
                    scores = [g["score"] for g in grade_data.values()]
                    self.logger.info(
                        f"      ✅ Graded {submitted_post_count}: scores range {min(scores):.1f}–{max(scores):.1f}"
                    )

                # Submit reply grades to the separate reply credit assignment
                # Uses individual PUTs (not bulk update_grades) for points/null assignments
                if reply_grade_data and reply_credit_assignment_id:
                    self._submit_reply_credits(course_id, reply_credit_assignment_id, reply_grade_data)
                    submitted_reply_count = len(reply_grade_data)
                    reply_scores = [g["score"] for g in reply_grade_data.values()]
                    self.logger.info(
                        f"      ✅ Reply credits submitted ({submitted_reply_count}): "
                        f"range {min(reply_scores):.1f}–{max(reply_scores):.1f}"
                    )
                    # Post submission comments for audit trail
                    self._post_reply_audit_comments(
                        course_id, reply_credit_assignment_id,
                        pending_state, student_names, assignment_name
                    )

                # Flush pending state only after all submissions succeed
                for uid, student_state in pending_state.items():
                    self._save_discussion_state(state_key, uid, student_state)

            elif self.dry_run:
                if post_grade_data and reply_credit_assignment_id:
                    post_scores = [g["score"] for g in post_grade_data.values()]
                    self.logger.info(
                        f"      🔍 Would submit {len(post_grade_data)} post grades: "
                        f"range {min(post_scores):.1f}–{max(post_scores):.1f}"
                    )
                if reply_grade_data and reply_credit_assignment_id:
                    reply_scores = [g["score"] for g in reply_grade_data.values()]
                    self.logger.info(
                        f"      🔍 Would submit {len(reply_grade_data)} reply credits: "
                        f"range {min(reply_scores):.1f}–{max(reply_scores):.1f}"
                    )
                if grade_data and not reply_credit_assignment_id:
                    scores = [g["score"] for g in grade_data.values()]
                    self.logger.info(
                        f"      🔍 Would grade {len(grade_data)}: scores range {min(scores):.1f}–{max(scores):.1f}"
                    )

            elif not self.dry_run and pending_state:
                # No grades to submit but tracking-only state updates (new non-qualifying reply IDs)
                for uid, student_state in pending_state.items():
                    self._save_discussion_state(state_key, uid, student_state)

            total_graded = len(post_grade_data) if reply_credit_assignment_id else len(grade_data)
            return total_graded, skipped_count

        else:
            # Complete/Incomplete submit path
            if not self.dry_run and grade_data:
                self._submit_grades(course_id, assignment_id, grade_data)
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                self.logger.info(f"      ✅ Graded {len(grade_data)}: {complete_count} complete, {len(grade_data) - complete_count} incomplete")
            elif self.dry_run and grade_data:
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                self.logger.info(f"      🔍 Would grade {len(grade_data)}: {complete_count} complete, {len(grade_data) - complete_count} incomplete")

        return len(grade_data), skipped_count

    def _get_discussion_topic_id(self, assignment: Dict[str, Any]) -> Optional[int]:
        """
        Extract discussion topic ID from an assignment.

        Canvas includes a discussion_topic object on graded discussion assignments,
        or we can fall back to fetching it separately if submission_types indicates
        this is a discussion.

        Args:
            assignment: Assignment dictionary

        Returns:
            Topic ID or None
        """
        # Direct link in assignment object (most common)
        topic = assignment.get('discussion_topic')
        if topic and isinstance(topic, dict):
            return topic.get('id')

        # Some responses put it as a flat field
        if assignment.get('discussion_topic_id'):
            return assignment['discussion_topic_id']

        # If submission_types includes online_discussion but no topic link,
        # try fetching the discussion topic separately
        submission_types = assignment.get('submission_types', [])
        if 'online_discussion' in submission_types:
            # Fetch all topics for the course and find the one matching this assignment
            try:
                url = f"{self.base_url}/api/v1/courses/{assignment['course_id']}/discussion_topics"
                response = requests.get(url, headers=self.headers, params={'per_page': 100}, timeout=30)
                response.raise_for_status()
                topics = response.json()

                for topic in topics:
                    linked_assignment = topic.get('assignment', {})
                    if linked_assignment and linked_assignment.get('id') == assignment['id']:
                        return topic['id']
            except Exception as e:
                self.logger.warning(f"      ⚠️  Failed to fetch discussion topics: {e}")

        return None

    def _fetch_discussion_entries(self, course_id: int, topic_id: int) -> List[Dict[str, Any]]:
        """
        Fetch all entries (posts and nested replies) for a discussion topic.

        Uses Canvas's /discussion_topics/{id}/view endpoint which returns
        the full nested tree of entries.

        Args:
            course_id: Canvas course ID
            topic_id: Discussion topic ID

        Returns:
            List of top-level entry dicts (each may contain nested replies)
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("view", [])
        except Exception as e:
            self.logger.error(f"      ❌ Failed to fetch discussion entries: {e}")
            return []

    def _categorize_discussion_entries(self, entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """
        Walk the nested entry tree and separate each student's posts from replies.

        Canvas returns entries as a nested structure:
            view: [
                {id, user_id, message, replies: [
                    {id, user_id, message, replies: [...]},
                    ...
                ]},
                ...
            ]

        Top-level entries in the view array are original posts. Anything nested
        inside a replies array is a reply (regardless of further nesting depth).

        Each entry is stored as {"id": int, "message": str} so that callers can
        track which specific entries have been credited across grading runs.

        Args:
            entries: Top-level entry list from the /view endpoint

        Returns:
            Dict of {user_id: {"posts": [{"id", "message"}], "replies": [{"id", "message"}]}}
        """
        student_data: Dict[int, Dict[str, Any]] = {}

        def ensure_student(uid: int):
            if uid not in student_data:
                student_data[uid] = {"posts": [], "replies": []}

        def collect_replies(reply_list: List[Dict[str, Any]], parent_message: str = ""):
            """Recursively collect all replies (and replies-to-replies)."""
            for reply in reply_list:
                uid = reply.get("user_id")
                message = reply.get("message", "")
                if uid and message:
                    ensure_student(uid)
                    student_data[uid]["replies"].append({
                        "id": reply.get("id"),
                        "message": message,
                        "parent_message": parent_message,
                    })
                if "replies" in reply:
                    collect_replies(reply["replies"], parent_message=reply.get("message", ""))

        # Top-level entries are posts
        for entry in entries:
            uid = entry.get("user_id")
            message = entry.get("message", "")
            if uid and message:
                ensure_student(uid)
                student_data[uid]["posts"].append({"id": entry.get("id"), "message": message})

            if "replies" in entry:
                collect_replies(entry["replies"], parent_message=entry.get("message", ""))

        return student_data

    def _evaluate_discussion_student(self, student_data: Dict[str, List[str]],
                                      rule: AssignmentRule, mode: str) -> bool:
        """
        Evaluate a single student's discussion participation against the rule.

        Separate mode: Student must have >= min_posts posts each meeting
        post_min_words, AND >= min_replies replies each meeting reply_min_words.
        Either threshold can be set to 0 to skip that check.

        Combined mode: Total word count across ALL messages (posts + replies)
        must meet post_min_words as the threshold.

        Args:
            student_data: {"posts": [message_texts], "replies": [message_texts]}
            rule: Assignment rule with discussion settings
            mode: "separate" or "combined"

        Returns:
            True if student meets the requirements
        """
        posts = [e["message"] for e in student_data["posts"]]
        replies = [e["message"] for e in student_data["replies"]]

        if mode == "combined":
            # Pool everything together, check total word count
            all_messages = posts + replies
            total_words = sum(self._count_words(msg) for msg in all_messages)
            threshold = rule.post_min_words or 200
            qualifies = total_words >= threshold
            self.logger.info(
                f"        [combined] {len(all_messages)} messages, {total_words} total words "
                f"(need {threshold}) → {'✅' if qualifies else '❌'}"
            )
            return qualifies

        else:  # "separate"
            # Posts check
            min_posts_required = rule.min_posts if rule.min_posts is not None else 1
            post_threshold = rule.post_min_words or 200
            qualifying_posts = sum(1 for msg in posts if self._count_words(msg) >= post_threshold)

            # Replies check
            min_replies_required = rule.min_replies if rule.min_replies is not None else 2
            reply_threshold = rule.reply_min_words or 50
            qualifying_replies = sum(1 for msg in replies if self._count_words(msg) >= reply_threshold)

            posts_ok = qualifying_posts >= min_posts_required
            replies_ok = qualifying_replies >= min_replies_required

            self.logger.info(
                f"        [separate] posts: {qualifying_posts}/{min_posts_required} "
                f"(need {post_threshold} words each) → {'✅' if posts_ok else '❌'} | "
                f"replies: {qualifying_replies}/{min_replies_required} "
                f"(need {reply_threshold} words each) → {'✅' if replies_ok else '❌'}"
            )
            return posts_ok and replies_ok

    def _score_discussion_student(self, student_data: Dict[str, List[str]],
                                    rule: AssignmentRule, mode: str) -> float:
        """
        Calculate numeric score for a student's discussion participation.

        In separate mode:
            score = post_points (if at least one qualifying post)
                  + (qualifying_reply_count × reply_points)

        In combined mode:
            score = (post_points + reply_points) if total words >= threshold, else 0
            (Combined mode with points is binary — you either meet the total or you don't)

        Args:
            student_data: {"posts": [message_texts], "replies": [message_texts]}
            rule: Assignment rule with points settings
            mode: "separate" or "combined"

        Returns:
            Calculated score as float
        """
        posts = [e["message"] for e in student_data["posts"]]
        replies = [e["message"] for e in student_data["replies"]]
        post_pts = rule.post_points if rule.post_points is not None else 1.0
        reply_pts = rule.reply_points if rule.reply_points is not None else 0.5

        if mode == "combined":
            all_messages = posts + replies
            total_words = sum(self._count_words(msg) for msg in all_messages)
            threshold = rule.post_min_words or 200
            if total_words >= threshold:
                # Award full post points + per-reply points for combined
                score = post_pts + (len(replies) * reply_pts)
            else:
                score = 0.0
            self.logger.info(
                f"        [combined/points] {total_words} total words (need {threshold}) → "
                f"score: {score:.1f} (post: {post_pts}, {len(replies)} replies × {reply_pts})"
            )
            return score

        else:  # "separate"
            score = 0.0
            post_threshold = rule.post_min_words or 200
            reply_threshold = rule.reply_min_words or 50

            # Posts: award post_points if student has at least one qualifying post
            qualifying_posts = sum(1 for msg in posts if self._count_words(msg) >= post_threshold)
            if qualifying_posts > 0:
                score += post_pts

            # Replies: award reply_points for EACH qualifying reply
            word_count_pass = [e for e in student_data["replies"]
                               if self._count_words(e["message"]) >= reply_threshold]

            if rule.use_llm_reply_check and word_count_pass:
                if self._reply_checker is None:
                    self._reply_checker = OllamaReplyChecker()
                qualifying_replies = 0
                for e in word_count_pass:
                    wc = self._count_words(e["message"])
                    is_sub = self._reply_checker.is_substantive(
                        e.get("parent_message", ""), e["message"]
                    )
                    if is_sub:
                        qualifying_replies += 1
                        self.logger.info(
                            f"        [quality] Reply {e['id']} ({wc} words): "
                            f"PASS — substantive"
                        )
                    else:
                        self.logger.info(
                            f"        [quality] Reply {e['id']} ({wc} words): "
                            f"FAIL — not substantive, no credit"
                        )
            else:
                qualifying_replies = len(word_count_pass)
            score += qualifying_replies * reply_pts

            self.logger.info(
                f"        [separate/points] posts: {qualifying_posts} qualifying "
                f"(+{post_pts if qualifying_posts > 0 else 0}) | "
                f"replies: {qualifying_replies} qualifying (+{qualifying_replies * reply_pts:.1f}) → "
                f"score: {score:.1f}"
            )
            return score

    def _count_words(self, text: str) -> int:
        """
        Count words in a message, stripping HTML tags first.

        Canvas discussion messages are HTML. This strips tags and counts
        whitespace-delimited tokens.

        Args:
            text: Raw message text (may contain HTML)

        Returns:
            Word count
        """
        import re
        # Strip HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text or "")
        # Collapse whitespace and split
        words = clean.split()
        return len(words)

    def _discussion_state_path(self) -> Path:
        """Return path to the discussion state JSON file."""
        return self.config_path.parent / "discussion_state.json"

    def _load_discussion_state(self) -> Dict[str, Any]:
        """Load the discussion state file, or return empty dict if missing."""
        path = self._discussion_state_path()
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_discussion_state(self, state_key: str, user_id: int,
                               student_state: Dict[str, Any]) -> None:
        """Merge and save a single student's state into the discussion state file."""
        state = self._load_discussion_state()
        if state_key not in state:
            state[state_key] = {}
        state[state_key][str(user_id)] = student_state
        path = self._discussion_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _score_new_replies_for_student(self, data: Dict[str, Any],
                                        rule: AssignmentRule,
                                        student_state: Dict[str, Any]
                                        ) -> Tuple[float, List[int], List[Dict[str, Any]]]:
        """
        Score only NEW replies that haven't been credited yet.

        Args:
            data: Student's categorized entries {"posts": [...], "replies": [...]}
            rule: Assignment rule with reply_points and reply_min_words
            student_state: {"credited_entry_ids": [...], "reply_audit": [...]}

        Returns:
            (delta_score, new_entry_ids, audit_entries)
            - new_entry_ids includes ALL new reply IDs (even non-qualifying, to prevent re-eval)
            - audit_entries is a list of dicts with id, words, credited, reason, timestamp
        """
        from datetime import datetime as _dt
        already_credited = set(student_state.get("credited_entry_ids", []))
        new_replies = [e for e in data["replies"] if e["id"] not in already_credited]

        if not new_replies:
            return 0.0, [], []

        reply_threshold = rule.reply_min_words or 50
        reply_pts = rule.reply_points if rule.reply_points is not None else 0.5
        audit_entries: List[Dict[str, Any]] = []

        # Step 1: filter by word count
        word_count_pass = []
        for e in new_replies:
            wc = self._count_words(e["message"])
            if wc < reply_threshold:
                audit_entries.append({
                    "entry_id": e["id"],
                    "words": wc,
                    "credited": False,
                    "reason": f"too short ({wc} words, need {reply_threshold})",
                    "graded_at": _dt.now().isoformat(timespec="seconds")
                })
            else:
                word_count_pass.append(e)

        # Step 2: LLM quality check (if enabled)
        if rule.use_llm_reply_check and word_count_pass:
            if self._reply_checker is None:
                self._reply_checker = OllamaReplyChecker()

            qualifying = []
            for e in word_count_pass:
                wc = self._count_words(e["message"])
                is_sub = self._reply_checker.is_substantive(
                    e.get("parent_message", ""), e["message"]
                )
                if is_sub:
                    qualifying.append(e)
                    audit_entries.append({
                        "entry_id": e["id"],
                        "words": wc,
                        "credited": True,
                        "reason": "substantive (LLM pass)",
                        "graded_at": _dt.now().isoformat(timespec="seconds")
                    })
                    self.logger.info(
                        f"        [quality] Reply {e['id']} ({wc} words): "
                        f"PASS — substantive"
                    )
                else:
                    audit_entries.append({
                        "entry_id": e["id"],
                        "words": wc,
                        "credited": False,
                        "reason": "not substantive (LLM fail)",
                        "graded_at": _dt.now().isoformat(timespec="seconds")
                    })
                    self.logger.info(
                        f"        [quality] Reply {e['id']} ({wc} words): "
                        f"FAIL — not substantive, no credit"
                    )
            qualifying_count = len(qualifying)
        else:
            qualifying_count = len(word_count_pass)
            for e in word_count_pass:
                wc = self._count_words(e["message"])
                audit_entries.append({
                    "entry_id": e["id"],
                    "words": wc,
                    "credited": True,
                    "reason": "meets word count",
                    "graded_at": _dt.now().isoformat(timespec="seconds")
                })

        delta = qualifying_count * reply_pts
        new_ids = [e["id"] for e in new_replies]

        self.logger.info(
            f"        [incremental] {len(new_replies)} new replies, "
            f"{qualifying_count} qualifying → +{delta:.1f} points"
        )

        return delta, new_ids, audit_entries

    def _score_discussion_student_split(self, data: Dict[str, Any],
                                         rule: AssignmentRule,
                                         mode: str) -> Tuple[float, float]:
        """
        Like _score_discussion_student but returns (post_score, reply_score) separately.
        Used in Scenario A (first grade) when reply credits go to a separate assignment.
        """
        posts = [e["message"] for e in data["posts"]]
        replies = data["replies"]
        post_pts = rule.post_points if rule.post_points is not None else 1.0
        reply_pts = rule.reply_points if rule.reply_points is not None else 0.5

        if mode == "combined":
            all_words = sum(self._count_words(m) for m in posts) + \
                        sum(self._count_words(e["message"]) for e in replies)
            threshold = rule.post_min_words or 200
            if all_words >= threshold:
                return post_pts, len(replies) * reply_pts
            return 0.0, 0.0

        # separate mode
        post_threshold = rule.post_min_words or 200
        reply_threshold = rule.reply_min_words or 50

        qualifying_posts = sum(1 for msg in posts if self._count_words(msg) >= post_threshold)
        post_score = post_pts if qualifying_posts > 0 else 0.0

        word_count_pass = [e for e in replies
                           if self._count_words(e["message"]) >= reply_threshold]
        if rule.use_llm_reply_check and word_count_pass:
            if self._reply_checker is None:
                self._reply_checker = OllamaReplyChecker()
            qualifying_replies = sum(
                1 for e in word_count_pass
                if self._reply_checker.is_substantive(e.get("parent_message", ""), e["message"])
            )
        else:
            qualifying_replies = len(word_count_pass)

        reply_score = qualifying_replies * reply_pts
        self.logger.info(
            f"        [separate/points] posts: {qualifying_posts} qualifying (+{post_score:.1f}) | "
            f"replies: {qualifying_replies} qualifying (+{reply_score:.1f})"
        )
        return post_score, reply_score

    def _build_reply_audit(self, all_replies: List[Dict[str, Any]],
                            credited_replies: List[Dict[str, Any]],
                            rule: AssignmentRule,
                            student_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build audit trail entries for Scenario A (first grade).
        Returns a list of audit dicts for all replies seen.
        """
        from datetime import datetime as _dt
        credited_ids = {e["id"] for e in credited_replies}
        reply_threshold = rule.reply_min_words or 50
        audit = []
        for e in all_replies:
            wc = self._count_words(e["message"])
            if e["id"] in credited_ids:
                reason = "substantive (LLM pass)" if rule.use_llm_reply_check else "meets word count"
                credited = True
            elif wc < reply_threshold:
                reason = f"too short ({wc} words, need {reply_threshold})"
                credited = False
            else:
                reason = "not substantive (LLM fail)"
                credited = False
            audit.append({
                "entry_id": e["id"],
                "words": wc,
                "credited": credited,
                "reason": reason,
                "graded_at": _dt.now().isoformat(timespec="seconds")
            })
        return audit

    def _post_reply_audit_comments(self, course_id: int, reply_assignment_id: int,
                                    pending_state: Dict[int, Dict[str, Any]],
                                    student_names: Dict[int, str],
                                    assignment_name: str) -> None:
        """
        Post a submission comment on each student's reply credit assignment entry
        listing which reply entry IDs were credited and which were not.
        This gives instructors (and optionally students) a traceable audit trail.
        """
        base_url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{reply_assignment_id}"

        for user_id, state in pending_state.items():
            audit = state.get("reply_audit", [])
            if not audit:
                continue

            credited = [a for a in audit if a["credited"]]
            rejected = [a for a in audit if not a["credited"]]

            lines = [f"Reply credit audit for {assignment_name}:"]
            lines.append("")
            if credited:
                lines.append(f"✅ Credited ({len(credited)}):")
                for a in credited:
                    lines.append(f"  • Entry {a['entry_id']} — {a['words']} words — {a['reason']}")
            if rejected:
                lines.append(f"❌ Not credited ({len(rejected)}):")
                for a in rejected:
                    lines.append(f"  • Entry {a['entry_id']} — {a['words']} words — {a['reason']}")
            lines.append("")
            lines.append(f"Graded by autograder on {credited[0]['graded_at'][:10] if credited else rejected[0]['graded_at'][:10] if rejected else 'unknown'}")

            comment_text = "\n".join(lines)

            try:
                url = f"{base_url}/submissions/{user_id}"
                requests.put(
                    url,
                    headers=self.headers,
                    json={"comment": {"text_comment": comment_text}},
                    timeout=30
                )
            except Exception as e:
                self.logger.warning(
                    f"      ⚠️  Could not post audit comment for student {user_id}: {e}"
                )

    def _fetch_submissions(self, course_id: int, assignment_id: int) -> Dict[int, Dict[str, Any]]:
        """
        Fetch current submissions for an assignment (for grade preservation).

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Dict of {user_id: submission_data}
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {"per_page": 100}

        submissions = {}
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        for sub in response.json():
            uid = sub.get("user_id")
            if uid:
                submissions[uid] = sub
        return submissions

    def _submit_grades(self, course_id: int, assignment_id: int, grade_data: Dict[int, Dict[str, Any]]):
        """
        Submit grades to Canvas using individual PUT requests.

        The bulk update_grades endpoint is unreliable on this Canvas instance —
        it returns 200/queued but grades don't always apply. Individual PUTs are
        consistent for both points and complete/incomplete assignments.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID
            grade_data: Dictionary of {user_id: {"score": float} or {"posted_grade": str}}
        """
        base_url = (
            f"{self.base_url}/api/v1/courses/{course_id}"
            f"/assignments/{assignment_id}/submissions"
        )
        failed = []
        for user_id, data in grade_data.items():
            # Translate grade_data dict to posted_grade string for the PUT endpoint
            if "score" in data:
                posted_grade = str(data["score"])
            else:
                posted_grade = data.get("posted_grade", "")

            try:
                response = requests.put(
                    f"{base_url}/{user_id}",
                    headers=self.headers,
                    json={"submission": {"posted_grade": posted_grade}},
                    timeout=30
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"      ❌ Failed to submit grade for student {user_id}: {e}")
                failed.append(user_id)

        if failed:
            raise RuntimeError(f"Grade submission failed for {len(failed)} student(s): {failed}")

    def _submit_reply_credits(self, course_id: int, reply_assignment_id: int,
                              grade_data: Dict[int, Dict[str, Any]]) -> None:
        """
        Submit reply credit grades using individual PUT requests.

        The bulk update_grades endpoint is unreliable for points/null assignments
        (points_possible=None), so we use individual submission PUTs instead.

        Args:
            course_id: Canvas course ID
            reply_assignment_id: The reply credit assignment ID
            grade_data: Dict of {user_id: {"score": float}}
        """
        base_url = (
            f"{self.base_url}/api/v1/courses/{course_id}"
            f"/assignments/{reply_assignment_id}/submissions"
        )
        failed = []
        for user_id, data in grade_data.items():
            score = data.get("score", 0)
            try:
                response = requests.put(
                    f"{base_url}/{user_id}",
                    headers=self.headers,
                    json={"submission": {"posted_grade": str(score)}},
                    timeout=30
                )
                response.raise_for_status()
                actual = response.json().get("score")
                if actual != score:
                    self.logger.warning(
                        f"      ⚠️  Reply credit for student {user_id}: "
                        f"submitted {score} but Canvas returned {actual}"
                    )
            except requests.exceptions.RequestException as e:
                self.logger.error(
                    f"      ❌ Failed to submit reply credit for student {user_id}: {e}"
                )
                failed.append(user_id)

        if failed:
            raise RuntimeError(
                f"Reply credit submission failed for {len(failed)} student(s): {failed}"
            )

    def _run_adc(self, course_id: int, assignment: Dict[str, Any], course_name: str) -> List[Dict[str, Any]]:
        """
        Run Academic Integrity Check on all text submissions for this assignment.

        Fetches submissions from Canvas, runs DishonestyAnalyzer on each, saves
        results to RunStore (SQLite), runs peer comparison, then returns flag dicts
        for backwards-compatibility with FlagAggregator.

        Invocation note: AIC can also be triggered directly via
        Academic_Dishonesty_Check_v2.analyze_assignment() from the GUI or CLI.
        RunStore.save_result() is called from both paths.
        """
        assignment_id = assignment["id"]
        assignment_name = assignment["name"]

        self.logger.info(f"      🔍 Running Academic Integrity Check: {assignment_name}")

        # ── Import AIC engine and RunStore ─────────────────────────────────
        try:
            from Academic_Dishonesty_Check_v2 import DishonestyAnalyzer, PeerComparisonAnalyzer
            from automation.run_store import RunStore
        except ImportError as e:
            self.logger.warning(f"      ⚠ AIC skipped — import failed: {e}")
            return []

        # ── Fetch submissions — discussion entries if applicable ───────────
        submissions = []
        is_discussion = "discussion_topic" in assignment.get("submission_types", [])

        if is_discussion:
            topic_id = self._get_discussion_topic_id(assignment)
            if topic_id:
                entries = self._fetch_discussion_entries(course_id, topic_id)
                if entries:
                    # Build pseudo-submissions from discussion entries
                    user_texts: Dict[str, List[str]] = defaultdict(list)
                    user_names: Dict[str, str] = {}

                    def _collect(entry):
                        uid = str(entry.get("user_id", ""))
                        msg = entry.get("message") or ""
                        if uid and msg.strip():
                            user_texts[uid].append(msg)
                            if uid not in user_names:
                                user_names[uid] = entry.get("user_name", f"Student {uid}")
                        for reply in entry.get("replies", []):
                            _collect(reply)

                    for e in entries:
                        _collect(e)

                    for uid, texts in user_texts.items():
                        submissions.append({
                            "user_id": int(uid) if uid.isdigit() else uid,
                            "user": {"name": user_names.get(uid, f"Student {uid}")},
                            "body": "\n\n".join(texts),
                            "workflow_state": "submitted",
                            "submitted_at": None,
                        })
                    self.logger.info(
                        f"      📝 Discussion: {len(submissions)} participants with text"
                    )

        if not submissions:
            url = (f"{self.base_url}/api/v1/courses/{course_id}"
                   f"/assignments/{assignment_id}/submissions")
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    params={"per_page": 100, "include[]": "user"},
                    timeout=30,
                )
                resp.raise_for_status()
                submissions = resp.json()
            except requests.RequestException as e:
                self.logger.warning(f"      ⚠ AIC skipped — could not fetch submissions: {e}")
                return []

        # ── Open RunStore ──────────────────────────────────────────────────
        try:
            store = RunStore()
        except Exception as e:
            self.logger.warning(f"      ⚠ AIC skipped — could not open RunStore: {e}")
            return []

        try:
            from settings import load_settings as _load_settings
            context_profile = _load_settings().get("context_profile", "community_college")
        except Exception:
            context_profile = "community_college"

        # Phase 8: Compose per-marker weights from active credential profile
        composed_weights = None
        try:
            from modules.weight_composer import compose_from_profile
            from credentials import get_active_profile
            _, active_profile = get_active_profile()
            if active_profile:
                composed_weights = compose_from_profile(active_profile)
                self.logger.info(
                    f"      📊 Weight system: {composed_weights.education_level} "
                    f"(ESL={composed_weights.population.esl_level}, "
                    f"first_gen={composed_weights.population.first_gen_level}, "
                    f"ND={composed_weights.population.neurodivergent_aware})"
                )
        except Exception as e:
            self.logger.debug(f"      Weight composer unavailable, using legacy path: {e}")

        analyzer = DishonestyAnalyzer(
            context_profile=context_profile,
            composed_weights=composed_weights,
        )

        results = []
        submitted_at_by_student: Dict[str, Optional[str]] = {}
        skipped = 0

        # ── Analyze each submission ────────────────────────────────────────
        for sub in submissions:
            student_id = str(sub.get("user_id", ""))
            body = sub.get("body") or ""
            submitted_at = sub.get("submitted_at")
            workflow_state = sub.get("workflow_state", "")
            user_info = sub.get("user") or {}
            student_name = (
                user_info.get("name")
                or user_info.get("short_name")
                or f"Student {student_id}"
            )

            # Skip unsubmitted or empty text
            if workflow_state in ("unsubmitted", "deleted") or not body.strip():
                skipped += 1
                continue

            # Skip if same submission was already analyzed (re-run on resubmission)
            if not store.should_reanalyze(student_id, str(assignment_id), submitted_at):
                skipped += 1
                continue

            submitted_at_by_student[student_id] = submitted_at

            try:
                result = analyzer.analyze_text(
                    body,
                    student_id=student_id,
                    student_name=student_name,
                )
                store.save_result(
                    result,
                    course_id=str(course_id),
                    course_name=course_name,
                    assignment_id=str(assignment_id),
                    assignment_name=assignment_name,
                    submitted_at=submitted_at,
                    context_profile=context_profile,
                    submission_body=body,
                )
                results.append(result)
            except Exception as e:
                self.logger.warning(
                    f"      ⚠ AIC failed for student {student_id}: {e}"
                )

        # ── Peer comparison — updates results in-place with percentiles ────
        if len(results) >= 3:
            try:
                outlier_pct = (
                    composed_weights.outlier_percentile
                    if composed_weights is not None else 95.0
                )
                peer_analyzer = PeerComparisonAnalyzer(outlier_percentile=outlier_pct)
                peer_analyzer.analyze_cohort(results)
                # Re-save results that were flagged as outliers
                for r in results:
                    if r.is_outlier:
                        # Find original body for this student
                        _sub = next(
                            (s for s in submissions
                             if str(s.get("user_id")) == str(r.student_id)),
                            {},
                        )
                        store.save_result(
                            r,
                            course_id=str(course_id),
                            course_name=course_name,
                            assignment_id=str(assignment_id),
                            assignment_name=assignment_name,
                            submitted_at=submitted_at_by_student.get(str(r.student_id)),
                            context_profile=context_profile,
                            submission_body=(_sub.get("body") or ""),
                        )
            except Exception as e:
                self.logger.warning(f"      ⚠ Peer comparison skipped: {e}")

        # ── Log summary ────────────────────────────────────────────────────
        concern_counts: Dict[str, int] = {}
        for r in results:
            concern_counts[r.concern_level] = concern_counts.get(r.concern_level, 0) + 1
        smoking_guns = sum(1 for r in results if r.smoking_gun)

        self.logger.info(
            f"      ✅ AIC complete: {len(results)} analyzed, {skipped} skipped"
            f" | concern breakdown: {concern_counts}"
            + (f" | !! SMOKING GUNS: {smoking_guns}" if smoking_guns else "")
        )

        # ── Return flag dicts for FlagAggregator backwards compatibility ───
        flags = []
        for r in results:
            if r.concern_level in ("high", "elevated", "moderate"):
                flags.append({
                    "student_id": r.student_id,
                    "student_name": r.student_name,
                    "course_name": course_name,
                    "assignment_name": assignment_name,
                    "concern_level": r.concern_level.capitalize(),
                    "suspicious_score": r.suspicious_score,
                    "authenticity_score": r.authenticity_score,
                    "smoking_gun": r.smoking_gun,
                })
        return flags

    def _check_for_new_assignments(self):
        """Check for new assignment groups in configured courses."""
        self.logger.info("🔍 Checking for new assignment groups...")

        updates_found = False

        for course_id, course_config in self.config.courses.items():
            known_group_ids = {rule.assignment_group_id for rule in course_config.assignment_rules}
            new_groups = self.api.check_for_new_assignments(course_id, known_group_ids)

            if new_groups:
                updates_found = True
                self.logger.info(f"  ℹ️  Found {len(new_groups)} new group(s) in {course_config.course_name}")
                for group in new_groups:
                    self.logger.info(f"      - {group['name']}")

        if not updates_found:
            self.logger.info("  ✅ No new assignment groups found")

        self.logger.info("")

    def _generate_summary(self, stats: Dict[str, int]):
        """
        Generate summary report.

        Args:
            stats: Statistics dictionary
        """
        self.logger.info("")
        self.logger.info("📊 SUMMARY")
        self.logger.info("-" * 60)
        self.logger.info(f"  Courses processed: {stats['courses']}")
        self.logger.info(f"  Assignments graded: {stats['assignments']}")
        self.logger.info(f"  Submissions graded: {stats['submissions_graded']}")
        self.logger.info(f"  Submissions skipped: {stats['submissions_skipped']}")
        self.logger.info(f"  Academic dishonesty flags: {stats['flags']}")
        self.logger.info("")

        if stats['flags'] > 0:
            self.logger.info(f"  📁 Flags saved to: {self.config.global_settings.flag_excel_path}")
