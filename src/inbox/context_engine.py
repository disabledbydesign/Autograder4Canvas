"""
Context assembly engine.
Builds a ContextBundle for a given conversation, pulling from all three tiers:
  Tier 1: Voicing guide, pedagogy, Module 0 syllabus, grading config (always)
  Tier 2: Similar past responses (semester-scoped, time-decayed)
  Tier 3: Recent announcements (< 28 days, hard cutoff)
"""
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List

from .config import InboxConfig
from .db import InboxDB
from .models import Conversation, ContextBundle, SyllabusPage, Announcement
from .conversations import CanvasConversationsAPI
from .learning import find_similar_responses


def build_context(
    conversation: Conversation,
    db: InboxDB,
    api: CanvasConversationsAPI,
    config: InboxConfig,
    on_progress: Optional[Callable[[str], None]] = None,
) -> ContextBundle:
    """
    Assemble a full ContextBundle for drafting a response.
    Refreshes syllabus cache if stale (>7 days).
    """

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    course_id = conversation.course_id
    course_family = conversation.course_family or "ethn1"
    modality = conversation.modality or "online"

    # ─── Tier 1: Voicing guide ────────────────────────────────────────────────
    _progress("Loading voicing guide...")
    voicing_excerpt = _load_voicing_guide(config)

    # ─── Tier 1: Pedagogical frameworks ──────────────────────────────────────
    _progress("Loading pedagogical frameworks...")
    pedagogy = _load_pedagogy(config, course_family)

    # ─── Tier 1: Grading config ───────────────────────────────────────────────
    _progress("Loading grading config...")
    grading_summary = _load_grading_summary(config, modality)

    # ─── Tier 1: Syllabus (Module 0) ─────────────────────────────────────────
    syllabus_pages: List[SyllabusPage] = []
    if course_id:
        _progress("Checking syllabus cache...")
        age_days = db.get_syllabus_cache_age_days(course_id)
        if age_days is None or age_days > config.syllabus_cache_max_age_days:
            _progress(f"Syllabus cache stale ({int(age_days or 0)}d old). Refreshing from Canvas...")
            fresh_pages = api.fetch_module_zero_pages(course_id, on_progress=on_progress)
            if fresh_pages:
                db.delete_syllabus_cache(course_id)
                for page in fresh_pages:
                    db.upsert_syllabus_page(page)
                syllabus_pages = fresh_pages
                _progress(f"Cached {len(fresh_pages)} syllabus pages.")
            else:
                _progress("No Module 0 pages found on Canvas.")
        else:
            _progress(f"Syllabus cache fresh ({int(age_days)}d old).")
            raw = db.get_syllabus_pages(course_id)
            syllabus_pages = [
                SyllabusPage(
                    course_id=r["course_id"],
                    page_title=r["page_title"],
                    page_url=r.get("page_url"),
                    content=r["content"],
                    fetched_at=datetime.fromisoformat(r["fetched_at"]),
                )
                for r in raw
            ]

    # ─── Tier 2: Similar past responses ──────────────────────────────────────
    _progress("Looking up similar past responses...")
    query_text = f"{conversation.subject} {conversation.latest_student_message}"
    past_raw = db.get_sent_responses(
        course_family=course_family,
        semester=None,      # Include all semesters; decay handles filtering
        limit=300,
    )
    similar = find_similar_responses(
        query_text=query_text,
        past_responses=past_raw,
        course_family=course_family,
        current_semester=config.current_semester,
        max_results=config.max_similar_responses,
        threshold=config.tfidf_similarity_threshold,
    )
    _progress(f"Found {len(similar)} similar past responses.")

    # ─── Tier 3: Recent announcements ─────────────────────────────────────────
    announcements: List[Announcement] = []
    if course_id:
        _progress("Loading recent announcements...")
        raw_anns = db.get_recent_announcements(course_id, config.tier3_max_age_days)
        for r in raw_anns:
            posted_at = datetime.fromisoformat(r["posted_at"]) if r.get("posted_at") else None
            announcements.append(Announcement(
                canvas_id=r["canvas_id"],
                course_id=r["course_id"],
                title=r["title"] or "",
                content=r["content"] or "",
                posted_at=posted_at,
                fetched_at=datetime.fromisoformat(r["fetched_at"]),
                semester=r["semester"],
            ))

    return ContextBundle(
        conversation=conversation,
        voicing_guide_excerpt=voicing_excerpt,
        pedagogy=pedagogy,
        syllabus_pages=syllabus_pages,
        grading_summary=grading_summary,
        similar_responses=similar,
        recent_announcements=announcements,
    )


# ─── File Loaders ─────────────────────────────────────────────────────────────

def _load_voicing_guide(config: InboxConfig) -> str:
    """
    Load the voicing guide. For context efficiency, include:
    - The "Scaling for Routine vs. Complex Emails" section
    - The language DOs/DON'Ts
    - The sign-off convention
    - Cap at ~2500 words.
    """
    path = config.voicing_guide_path
    if not path.exists():
        return "(Voicing guide not found — use Dr. Bloch's characteristic direct, care-centered, structurally-aware voice. Sign off 'In solidarity, June'.)"

    text = path.read_text(encoding="utf-8")
    # Cap at ~2500 words
    words = text.split()
    if len(words) > 2500:
        text = " ".join(words[:2500]) + "\n\n[...voicing guide truncated for context efficiency]"
    return text


def _load_pedagogy(config: InboxConfig, course_family: str) -> str:
    """Load pedagogical frameworks for the course family."""
    paths = config.pedagogy_path
    path = paths.get(course_family) or paths.get("ethn1")
    if not path or not path.exists():
        return "(Pedagogical frameworks not found.)"
    text = path.read_text(encoding="utf-8")
    words = text.split()
    if len(words) > 1500:
        text = " ".join(words[:1500]) + "\n[...truncated]"
    return text


def _load_grading_summary(config: InboxConfig, modality: str) -> str:
    """
    Load a condensed grading summary from the YAML config.
    Preserves structure (section headings + nearby lines) rather than
    pulling random decontextualized lines.
    """
    paths = config.grading_config_path
    path = paths.get(modality) or paths.get("online")
    if not path or not path.exists():
        return "(Grading config not found.)"

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find lines mentioning student-relevant terms, then include context around them
    keywords = {"late", "extension", "flex", "incomplete", "points", "due", "submit", "emergency", "pathway"}
    keep = set()
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords) or line.startswith("#") or line.startswith("  -"):
            # Keep this line and 2 lines of context above/below
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                keep.add(j)

    if not keep:
        # Nothing matched — include first 2000 chars as fallback
        return text[:2000]

    result = []
    prev_idx = -2
    for idx in sorted(keep):
        if idx > prev_idx + 1:
            result.append("...")  # Gap marker
        result.append(lines[idx])
        prev_idx = idx

    summary = "\n".join(result[:100])  # Cap at 100 lines
    return summary
