"""
Pydantic v2 data models for the inbox module.
All return types from conversations.py are typed here.
The GUI can import these directly for type-safe data binding.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A single message within a Canvas conversation."""
    id: int
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    body: str
    created_at: Optional[datetime] = None


class Conversation(BaseModel):
    """
    A Canvas conversation (inbox thread) with one or more messages.
    Stored in the DB after fetch; enriched with topic_tags and status.
    """
    canvas_conversation_id: int
    course_id: Optional[int] = None
    course_code: Optional[str] = None        # e.g., "ETHN-1 03"
    course_family: Optional[str] = None      # "ethn1" or "ethn27"
    modality: Optional[str] = None           # "online" or "in_person"
    student_name: Optional[str] = None
    student_canvas_id: Optional[int] = None
    subject: str = "(no subject)"
    last_message_body: Optional[str] = None
    last_message_at: Optional[datetime] = None
    messages: List[ConversationMessage] = Field(default_factory=list)
    topic_tags: List[str] = Field(default_factory=list)
    primary_category: str = "other"
    status: str = "pending"                  # pending | drafted | sent | skipped | flagged
    semester: str = "spring_2026"
    fetched_at: Optional[datetime] = None

    @property
    def is_crisis(self) -> bool:
        return "personal_crisis" in self.topic_tags

    @property
    def latest_student_message(self) -> str:
        """Return the most recent message body from the student (not instructor)."""
        for msg in reversed(self.messages):
            if msg.author_id != self.student_canvas_id:
                continue
            return msg.body
        # Fallback: just the last message
        return self.last_message_body or ""

    @property
    def time_ago_str(self) -> str:
        """Human-readable time since last message."""
        if not self.last_message_at:
            return "unknown"
        delta = datetime.utcnow() - self.last_message_at.replace(tzinfo=None)
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"


class Response(BaseModel):
    """
    A drafted+sent response to a conversation.
    Stored in the DB for learning and context retrieval.
    """
    id: Optional[int] = None
    conversation_id: int                      # FK to DB conversations.id
    canvas_conversation_id: int
    course_id: Optional[int] = None
    course_family: Optional[str] = None
    incoming_message: str
    draft: Optional[str] = None              # Claude's initial draft
    final_sent: Optional[str] = None         # What was actually sent
    edit_distance: Optional[int] = None      # Levenshtein distance
    edit_ratio: Optional[float] = None       # 0.0 = identical, 1.0 = completely different
    topic_tags: List[str] = Field(default_factory=list)
    primary_category: str = "other"
    semester: str = "spring_2026"
    drafted_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class SyllabusPage(BaseModel):
    """A cached Module 0 page from Canvas."""
    course_id: int
    page_title: str
    page_url: Optional[str] = None
    content: str                              # Plain text (HTML stripped)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class Announcement(BaseModel):
    """A Canvas course announcement."""
    canvas_id: int
    course_id: int
    title: str
    content: str                              # Plain text
    posted_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    semester: str = "spring_2026"


class ContextBundle(BaseModel):
    """
    Assembled context for drafting a response to a conversation.
    Passed to the CLI (as JSON) for Claude Code to consume.
    """
    conversation: Conversation
    voicing_guide_excerpt: str = ""
    pedagogy: str = ""
    syllabus_pages: List[SyllabusPage] = Field(default_factory=list)
    grading_summary: str = ""
    similar_responses: List[Dict[str, Any]] = Field(default_factory=list)
    recent_announcements: List[Announcement] = Field(default_factory=list)

    def to_prompt_text(self) -> str:
        """
        Render the context bundle as a structured text block for Claude Code.
        Context is organized by tier. Context blob is intentionally not shown
        to the user by default — the CLI outputs it to a temp file.
        """
        conv = self.conversation
        lines = []

        lines.append("═" * 60)
        lines.append("INBOX CONTEXT — DO NOT SHOW THIS TO USER")
        lines.append("═" * 60)

        # Tier 1: Always-on context
        lines.append("\n── TIER 1: VOICE & PEDAGOGY ──────────────────────────────")
        if self.voicing_guide_excerpt:
            lines.append("\n[VOICING GUIDE]")
            lines.append(self.voicing_guide_excerpt)

        if self.pedagogy:
            lines.append(f"\n[PEDAGOGICAL FRAMEWORKS — {conv.course_family or 'course'}]")
            lines.append(self.pedagogy)

        if self.grading_summary:
            lines.append("\n[GRADING STRUCTURE]")
            lines.append(self.grading_summary)

        if self.syllabus_pages:
            lines.append("\n[MODULE 0 / COURSE POLICIES]")
            for page in self.syllabus_pages:
                lines.append(f"\n--- {page.page_title} ---")
                # Cap each page at ~600 words to stay concise
                words = page.content.split()
                if len(words) > 600:
                    lines.append(" ".join(words[:600]) + "\n[...truncated]")
                else:
                    lines.append(page.content)

        # Tier 2: Similar past responses
        if self.similar_responses:
            lines.append("\n── TIER 2: SIMILAR PAST EXCHANGES ────────────────────────")
            lines.append("These are approved responses (after user editing). Learn from them.")
            for i, r in enumerate(self.similar_responses, 1):
                lines.append(f"\n[Example {i} | {r.get('course_code','?')} | {r.get('days_ago','?')}d ago | similarity: {r.get('similarity',0):.2f}]")
                lines.append(f"STUDENT ASKED: {r.get('incoming_message','')[:300]}")
                lines.append(f"SENT RESPONSE:\n{r.get('final_sent','')}")

        # Tier 3: Ephemeral announcements
        if self.recent_announcements:
            lines.append("\n── TIER 3: RECENT ANNOUNCEMENTS (< 28 days) ──────────────")
            for ann in self.recent_announcements:
                ago = ""
                if ann.posted_at:
                    delta = datetime.utcnow() - ann.posted_at.replace(tzinfo=None)
                    ago = f" | {delta.days}d ago"
                lines.append(f"\n[{ann.title}{ago}]")
                lines.append(ann.content[:400])

        # Student message
        lines.append("\n── STUDENT MESSAGE ────────────────────────────────────────")
        lines.append(f"From: {conv.student_name or 'Unknown'}")
        lines.append(f"Course: {conv.course_code or 'Unknown'} ({conv.modality or 'unknown'})")
        lines.append(f"Subject: {conv.subject}")
        lines.append(f"Category: {conv.primary_category} {' | ⚠️ CRISIS' if conv.is_crisis else ''}")
        lines.append(f"\n{conv.latest_student_message}")
        lines.append("\n" + "═" * 60)

        return "\n".join(lines)
