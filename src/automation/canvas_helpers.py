"""
Canvas Autograder - Canvas API Helpers
Specialized API wrappers for automation system.
"""

import os
import time
import requests
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from dateutil import parser
import pytz


class CanvasAutomationAPI:
    """Canvas API helpers for automation system."""

    def __init__(self, base_url: str = None, api_token: str = None):
        """
        Initialize Canvas API helper.

        Args:
            base_url: Canvas base URL (defaults to env CANVAS_BASE_URL or Cabrillo)
            api_token: Canvas API token (defaults to env CANVAS_API_TOKEN)
        """
        self.base_url = base_url or os.getenv("CANVAS_BASE_URL")
        self.api_token = api_token or os.getenv("CANVAS_API_TOKEN")

        if not self.api_token:
            raise ValueError("CANVAS_API_TOKEN not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _get_paginated(self, url: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Fetch all pages from a paginated Canvas API endpoint.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            List of all items from all pages
        """
        items = []
        params = params or {}

        while url:
            # Retry with exponential backoff
            for attempt in range(3):
                try:
                    response = requests.get(url, headers=self.headers, params=params, timeout=30)
                    response.raise_for_status()
                    items.extend(response.json())

                    # Get next page URL from Link header
                    url = response.links.get('next', {}).get('url')
                    params = {}  # Params are in the next URL
                    break  # Success, exit retry loop

                except requests.exceptions.Timeout as e:
                    if attempt < 2:  # Don't wait after last attempt
                        wait_time = 2 ** attempt  # 1s, 2s
                        print(f"⏱️  Timeout on attempt {attempt + 1}/3, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"⚠️  API request failed after 3 attempts: {e}")
                        url = None  # Give up on remaining pages
                        break
                except requests.exceptions.RequestException as e:
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        print(f"⚠️  Request failed on attempt {attempt + 1}/3, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"⚠️  API request failed after 3 attempts: {e}")
                        url = None
                        break

        return items

    def get_all_terms(self) -> List[Dict[str, Any]]:
        """
        Get all enrollment terms that have a start date, sorted newest first.
        Each dict includes an 'is_current' bool.
        """
        # Collect all pages — Canvas default page size can be as low as 10
        all_raw: list = []
        url = f"{self.base_url}/api/v1/accounts/1/terms"
        params = {'per_page': 100}
        while url:
            try:
                response = requests.get(url, headers=self.headers,
                                        params=params, timeout=30)
                response.raise_for_status()
                all_raw.extend(response.json().get('enrollment_terms', []))
                # Follow Canvas Link: <url>; rel="next" pagination
                link = response.headers.get('Link', '')
                url = None
                for part in link.split(','):
                    part = part.strip()
                    if 'rel="next"' in part:
                        url = part.split(';')[0].strip().strip('<>')
                        break
                params = {}  # page token is already in the next URL
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch terms: {e}")
                break

        now = datetime.now(pytz.UTC)
        result = []
        for term in all_raw:
            start_str = term.get('start_at')
            if not start_str:
                continue
            try:
                start = parser.isoparse(start_str)
                end_str = term.get('end_at')
                end = parser.isoparse(end_str) if end_str else None
                is_current = end is not None and start <= now <= end
                result.append({
                    'id': term['id'],
                    'name': term['name'],
                    'start_at': start_str,
                    'end_at': end_str,
                    'is_current': is_current,
                    '_sort_key': start,   # parsed datetime for reliable sort
                })
            except (ValueError, TypeError):
                continue

        result.sort(key=lambda t: t['_sort_key'], reverse=True)
        for t in result:
            del t['_sort_key']
        return result

    def get_current_term_ids(self) -> List[Dict[str, Any]]:
        """
        Get enrollment terms for current semester.

        Returns:
            List of current term dictionaries with id, name, start_at, end_at
        """
        url = f"{self.base_url}/api/v1/accounts/1/terms"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            terms = response.json()['enrollment_terms']
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch terms: {e}")
            return []

        now = datetime.now(pytz.UTC)
        current_terms = []

        for term in terms:
            start_str = term.get('start_at')
            end_str = term.get('end_at')

            if not start_str or not end_str:
                continue

            try:
                start = parser.isoparse(start_str)
                end = parser.isoparse(end_str)

                # Include if currently active (within date range)
                if start <= now <= end:
                    current_terms.append({
                        'id': term['id'],
                        'name': term['name'],
                        'start_at': start_str,
                        'end_at': end_str
                    })
            except (ValueError, TypeError):
                continue

        return current_terms

    def get_all_teacher_courses(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Fetch every course where the user is a teacher in one request,
        then group them by enrollment_term_id client-side.

        Returns:
            {term_id: [course_dict, ...]}
        """
        url = f"{self.base_url}/api/v1/courses"
        params = {
            'enrollment_type': 'teacher',
            'state[]': ['available', 'unpublished'],
            'include[]': 'total_students',
            'per_page': 100,
        }
        courses = self._get_paginated(url, params)
        grouped: Dict[int, list] = {}
        for course in courses:
            tid = course.get('enrollment_term_id')
            if tid is not None:
                grouped.setdefault(tid, []).append(course)
        return grouped

    def get_courses_in_term(self, term_id: int) -> List[Dict[str, Any]]:
        """
        Get courses in term where user is teacher.

        Args:
            term_id: Canvas enrollment term ID

        Returns:
            List of course dictionaries
        """
        url = f"{self.base_url}/api/v1/courses"
        params = {
            'enrollment_term_id': term_id,
            'enrollment_type': 'teacher',
            'state': ['available'],
            'per_page': 100
        }

        courses = self._get_paginated(url, params)
        return courses

    def get_assignment_groups(self, course_id: int) -> List[Dict[str, Any]]:
        """
        Get assignment groups with assignments.

        Args:
            course_id: Canvas course ID

        Returns:
            List of assignment group dictionaries
        """
        import logging
        logger = logging.getLogger('autograder_automation')

        url = f"{self.base_url}/api/v1/courses/{course_id}/assignment_groups"
        params = {'include[]': ['assignments', 'discussion_topic', 'needs_grading_count']}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️  Timeout fetching assignment groups for course {course_id}: {e}")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Connection error fetching assignment groups for course {course_id}: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️  Failed to fetch assignment groups for course {course_id}: {e}")
            return []

    def get_assignments_in_group(self, course_id: int, group_id: int) -> List[Dict[str, Any]]:
        """
        Get assignments in a specific assignment group.

        Args:
            course_id: Canvas course ID
            group_id: Assignment group ID

        Returns:
            List of assignment dictionaries
        """
        # Get all assignment groups with assignments
        groups = self.get_assignment_groups(course_id)

        for group in groups:
            if group['id'] == group_id:
                return group.get('assignments', [])

        return []

    def check_for_new_assignments(self, course_id: int,
                                  known_group_ids: Set[int]) -> List[Dict[str, Any]]:
        """
        Check if new assignment groups created since last config.

        Args:
            course_id: Canvas course ID
            known_group_ids: Set of known assignment group IDs

        Returns:
            List of new assignment group dictionaries
        """
        current_groups = self.get_assignment_groups(course_id)

        new_groups = [
            g for g in current_groups
            if g['id'] not in known_group_ids
        ]

        return new_groups

    def get_submission_count(self, course_id: int, assignment_id: int) -> int:
        """
        Get count of submissions for an assignment.

        Only needs to determine whether any submitted work exists (> 0), so
        fetches a single page of 1 and filters for actually-submitted workflow
        states. Avoids a full paginated fetch on every assignment, which was
        causing multi-minute hangs when Canvas was slow.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Number of submissions (may be capped at 1 — callers only check > 0)
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        # Don't filter by workflow_state at the API level — discussion_topic and
        # online_upload submissions don't always use workflow_state='submitted',
        # causing them to be skipped. Use submitted_at instead, which is reliably
        # set for all submission types when a student has turned in work.
        params = {'per_page': 10}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            submissions = response.json()
            return len([
                s for s in submissions
                if s.get('submitted_at') is not None
            ])

        except requests.exceptions.RequestException as e:
            import logging
            logging.getLogger('autograder_automation').warning(
                f"⚠️  Failed to get submission count for assignment {assignment_id}: {e}"
            )
            return 0

    def get_assignment_details(self, course_id: int, assignment_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an assignment.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Assignment dictionary or None if not found
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Failed to get assignment details: {e}")
            return None

    def is_future_assignment(self, assignment: Dict[str, Any]) -> bool:
        """
        Check if assignment has a future deadline.

        Args:
            assignment: Assignment dictionary

        Returns:
            True if due date is in the future
        """
        due_at = assignment.get('due_at')
        if not due_at:
            return False

        try:
            due_date = parser.isoparse(due_at)
            now = datetime.now(pytz.UTC)
            return due_date > now
        except (ValueError, TypeError):
            return False

    def get_course_name(self, course_id: int) -> str:
        """
        Get course name.

        Args:
            course_id: Canvas course ID

        Returns:
            Course name or empty string if not found
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json().get('name', '')
        except requests.exceptions.RequestException:
            return ''

    def test_connection(self) -> bool:
        """
        Test Canvas API connection.

        Returns:
            True if connection successful
        """
        url = f"{self.base_url}/api/v1/users/self"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def create_assignment(
        self,
        course_id: int,
        *,
        name: str,
        description: str = "",
        submission_types: Optional[List[str]] = None,
        points_possible: float = 0,
        published: bool = True,
    ) -> Dict[str, Any]:
        """Create a Canvas assignment.

        Returns the assignment dict from Canvas API.
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments"
        payload = {
            "assignment": {
                "name": name,
                "description": description,
                "submission_types": submission_types or ["none"],
                "points_possible": points_possible,
                "published": published,
            }
        }
        response = requests.post(
            url, headers=self.headers, json=payload, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def post_submission_comment(
        self,
        course_id: int,
        assignment_id: int,
        student_id: str,
        comment_text: str,
    ) -> Dict[str, Any]:
        """Post a comment on a student's submission.

        Uses PUT to update the submission with a text comment.
        """
        url = (
            f"{self.base_url}/api/v1/courses/{course_id}"
            f"/assignments/{assignment_id}/submissions/{student_id}"
        )
        payload = {
            "comment": {
                "text_comment": comment_text,
            }
        }
        response = requests.put(
            url, headers=self.headers, json=payload, timeout=30
        )
        response.raise_for_status()
        return response.json()
