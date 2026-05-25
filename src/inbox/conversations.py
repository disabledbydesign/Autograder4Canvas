"""
Canvas Conversations API wrapper.
Handles fetch, reply, and read-marking of inbox messages.
Also fetches Module 0 syllabus pages and recent announcements.

Design: methods return typed Pydantic models and accept an optional
progress callback so the future GUI can update a status bar.
"""
import re
import html
import time
import requests
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from .config import InboxConfig
from .models import Conversation, ConversationMessage, SyllabusPage, Announcement
from .learning import extract_topic_tags


class CanvasConversationsAPI:
    """
    Canvas Conversations API client.
    Reuses the pagination and retry patterns from CanvasAutomationAPI.
    """

    def __init__(self, config: InboxConfig):
        self.config = config
        if not config.canvas_api_token:
            raise ValueError("Canvas API token not set. Check credentials.json or CANVAS_API_TOKEN env var.")
        self.base_url = config.canvas_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {config.canvas_api_token}",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ─── Core HTTP ────────────────────────────────────────────────────────────

    def _get(self, endpoint: str, params: Dict = None) -> Any:
        """Single GET with retry."""
        url = f"{self.base_url}/api/v1{endpoint}"
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise
            except requests.exceptions.RequestException:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise

    def _get_paginated(self, endpoint: str, params: Dict = None) -> List[Dict]:
        """Fetch all pages from a paginated endpoint."""
        items = []
        url = f"{self.base_url}/api/v1{endpoint}"
        params = dict(params or {})
        params.setdefault("per_page", 100)

        while url:
            for attempt in range(3):
                try:
                    resp = self.session.get(url, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, list):
                        items.extend(data)
                    elif isinstance(data, dict):
                        # Some endpoints wrap in a key
                        for v in data.values():
                            if isinstance(v, list):
                                items.extend(v)
                                break
                    url = resp.links.get("next", {}).get("url")
                    params = {}  # Subsequent pages use full URL from Link header
                    break
                except requests.exceptions.Timeout:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        url = None
                        break
                except requests.exceptions.RequestException:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        url = None
                        break
        return items

    def _post(self, endpoint: str, data: Dict) -> Any:
        url = f"{self.base_url}/api/v1{endpoint}"
        resp = self.session.post(url, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _put(self, endpoint: str, data: Dict) -> Any:
        url = f"{self.base_url}/api/v1{endpoint}"
        resp = self.session.put(url, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ─── Conversations ────────────────────────────────────────────────────────

    def get_unread_conversations(
        self,
        course_ids: Optional[List[int]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[Conversation]:
        """
        Fetch unread conversations from Canvas inbox.
        Optionally filter by course_ids.
        Returns list of Conversation objects sorted by priority.
        """
        if on_progress:
            on_progress("Fetching unread conversations...")

        params = {"scope": "unread", "per_page": 100}
        if course_ids:
            # Canvas filter[] param: filter[]=course_44106
            params["filter[]"] = [f"course_{cid}" for cid in course_ids]

        raw = self._get_paginated("/conversations", params)

        conversations = []
        for item in raw:
            conv = self._parse_conversation_summary(item)
            if conv:
                conversations.append(conv)

        # Sort by priority (crisis first, then by topic priority)
        conversations.sort(key=lambda c: self.config.topic_priority.get(c.primary_category, 9))

        if on_progress:
            on_progress(f"Found {len(conversations)} unread messages.")

        return conversations

    def get_conversation_detail(
        self, canvas_conversation_id: int
    ) -> Optional[Conversation]:
        """Fetch a single conversation with all messages."""
        try:
            data = self._get(f"/conversations/{canvas_conversation_id}")
        except Exception:
            return None
        return self._parse_conversation_detail(data)

    def reply_to_conversation(
        self,
        canvas_conversation_id: int,
        body: str,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Send a reply to a conversation. Returns True on success."""
        if on_progress:
            on_progress("Sending reply...")
        try:
            self._post(
                f"/conversations/{canvas_conversation_id}/add_message",
                {"body": body}
            )
            if on_progress:
                on_progress("Sent.")
            return True
        except Exception as e:
            if on_progress:
                on_progress(f"Send failed: {e}")
            return False

    def mark_as_read(self, canvas_conversation_id: int) -> None:
        """Mark a conversation as read."""
        try:
            self._put(
                f"/conversations/{canvas_conversation_id}",
                {"conversation[workflow_state]": "read"}
            )
        except Exception:
            pass  # Non-fatal

    # ─── Syllabus (Module 0) ──────────────────────────────────────────────────

    def fetch_module_zero_pages(
        self,
        course_id: int,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[SyllabusPage]:
        """
        Fetch all pages from Module 0 (or the first module) of a course.
        Returns list of SyllabusPage with plain-text content.
        """
        if on_progress:
            on_progress(f"Fetching syllabus for course {course_id}...")

        # Find Module 0 (by name pattern)
        modules = self._get_paginated(f"/courses/{course_id}/modules", {"per_page": 50})
        target_module = None
        for mod in modules:
            name = (mod.get("name") or "").lower()
            if "module 0" in name or "week 0" in name or "start here" in name or "orientation" in name:
                target_module = mod
                break
        if not target_module and modules:
            target_module = modules[0]  # Fall back to first module
        if not target_module:
            return []

        module_id = target_module["id"]
        items = self._get_paginated(
            f"/courses/{course_id}/modules/{module_id}/items",
            {"include[]": "content_details", "per_page": 50}
        )

        pages = []
        for item in items:
            if item.get("type") != "Page":
                continue
            page_url = item.get("url") or item.get("page_url")
            if not page_url:
                continue
            try:
                page_data = self._get(f"/courses/{course_id}/pages/{page_url}")
                body_html = page_data.get("body") or ""
                content = _html_to_text(body_html)
                pages.append(SyllabusPage(
                    course_id=course_id,
                    page_title=page_data.get("title", item.get("title", "Untitled")),
                    page_url=page_url,
                    content=content,
                    fetched_at=datetime.utcnow(),
                ))
            except Exception:
                continue

        if on_progress:
            on_progress(f"Fetched {len(pages)} syllabus pages.")

        return pages

    # ─── Announcements ────────────────────────────────────────────────────────

    def fetch_recent_announcements(
        self,
        course_id: int,
        max_count: int = 10,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[Announcement]:
        """Fetch recent announcements for a course."""
        try:
            items = self._get_paginated(
                f"/courses/{course_id}/discussion_topics",
                {"only_announcements": True, "order_by": "recent_activity", "per_page": max_count}
            )
        except Exception:
            return []

        semester = self.config.current_semester
        announcements = []
        for item in items[:max_count]:
            posted_at = _parse_dt(item.get("posted_at") or item.get("created_at"))
            content = _html_to_text(item.get("message") or "")
            announcements.append(Announcement(
                canvas_id=item["id"],
                course_id=course_id,
                title=item.get("title", ""),
                content=content,
                posted_at=posted_at,
                fetched_at=datetime.utcnow(),
                semester=semester,
            ))
        return announcements

    # ─── Parsing Helpers ──────────────────────────────────────────────────────

    def _parse_conversation_summary(self, data: Dict) -> Optional[Conversation]:
        """Parse a conversation list item into a Conversation model."""
        canvas_id = data.get("id")
        if not canvas_id:
            return None

        # Detect course from context_code (e.g., "course_44106")
        context_code = data.get("context_code") or data.get("context_id") or ""
        course_id = None
        if isinstance(context_code, str) and context_code.startswith("course_"):
            try:
                course_id = int(context_code.split("_")[1])
            except (IndexError, ValueError):
                pass

        course_info = self.config.get_course(course_id) if course_id else None

        # Find the student using Canvas "audience" field (non-self participant IDs)
        participants = data.get("participants") or []
        audience_ids = set(data.get("audience") or [])
        student_name = None
        student_id = None
        if audience_ids:
            # audience contains IDs of non-self participants
            for p in participants:
                if p.get("id") in audience_ids:
                    student_name = p.get("name")
                    student_id = p.get("id")
                    break
        if not student_name and len(participants) > 1:
            # Fallback: second participant (first is usually self)
            student_name = participants[1].get("name")
            student_id = participants[1].get("id")
        elif not student_name and participants:
            student_name = participants[0].get("name")
            student_id = participants[0].get("id")

        last_message = data.get("last_message") or data.get("last_authored_message") or ""
        last_message_at = _parse_dt(data.get("last_message_at") or data.get("last_authored_at"))

        subject = data.get("subject") or "(no subject)"

        # Auto-tag from subject + last_message
        tags = extract_topic_tags(
            f"{subject} {last_message}",
            self.config.topic_keywords
        )
        primary = tags[0] if tags else "other"

        return Conversation(
            canvas_conversation_id=canvas_id,
            course_id=course_id,
            course_code=course_info["code"] if course_info else None,
            course_family=course_info["family"] if course_info else None,
            modality=course_info["modality"] if course_info else None,
            student_name=student_name,
            student_canvas_id=student_id,
            subject=subject,
            last_message_body=last_message[:500] if last_message else None,
            last_message_at=last_message_at,
            topic_tags=tags,
            primary_category=primary,
            status="pending",
            semester=self.config.current_semester,
        )

    def _parse_conversation_detail(self, data: Dict) -> Optional[Conversation]:
        """Parse a full conversation detail response with messages."""
        conv = self._parse_conversation_summary(data)
        if not conv:
            return None

        raw_messages = data.get("messages") or []
        messages = []
        for m in raw_messages:
            author_id = m.get("author_id")
            author_name = None
            for p in (data.get("participants") or []):
                if p.get("id") == author_id:
                    author_name = p.get("name")
                    break
            messages.append(ConversationMessage(
                id=m.get("id", 0),
                author_id=author_id,
                author_name=author_name,
                body=m.get("body") or "",
                created_at=_parse_dt(m.get("created_at")),
            ))

        conv.messages = messages
        return conv


# ─── Utility ─────────────────────────────────────────────────────────────────

def _html_to_text(html_str: str) -> str:
    """Strip HTML tags and decode entities to plain text."""
    if not html_str:
        return ""
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html_str, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newlines
    text = re.sub(r"<(br|p|div|li|h[1-6]|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 datetime string from Canvas."""
    if not s:
        return None
    try:
        # Canvas uses Z suffix
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None
