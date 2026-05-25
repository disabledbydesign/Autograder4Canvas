"""
SQLite persistence layer for the inbox module.
All schema creation is idempotent (CREATE TABLE IF NOT EXISTS).
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from .models import Conversation, Response, SyllabusPage, Announcement


class InboxDB:
    """Thin wrapper around SQLite for inbox data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> "InboxDB":
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_schema()
        return self

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "InboxDB":
        return self.connect()

    def __exit__(self, *_) -> None:
        self.close()

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                canvas_conversation_id  INTEGER UNIQUE NOT NULL,
                course_id               INTEGER,
                course_code             TEXT,
                course_family           TEXT,
                modality                TEXT,
                student_name            TEXT,
                student_canvas_id       INTEGER,
                subject                 TEXT,
                last_message_body       TEXT,
                last_message_at         TEXT,
                topic_tags              TEXT DEFAULT '[]',
                primary_category        TEXT DEFAULT 'other',
                status                  TEXT DEFAULT 'pending',
                semester                TEXT NOT NULL,
                fetched_at              TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS responses (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id         INTEGER NOT NULL REFERENCES conversations(id),
                canvas_conversation_id  INTEGER NOT NULL,
                course_id               INTEGER,
                course_family           TEXT,
                incoming_message        TEXT NOT NULL,
                draft                   TEXT,
                final_sent              TEXT,
                edit_distance           INTEGER,
                edit_ratio              REAL,
                topic_tags              TEXT DEFAULT '[]',
                primary_category        TEXT DEFAULT 'other',
                semester                TEXT NOT NULL,
                drafted_at              TEXT,
                sent_at                 TEXT,
                UNIQUE(conversation_id)
            );

            CREATE TABLE IF NOT EXISTS syllabus_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id   INTEGER NOT NULL,
                page_title  TEXT NOT NULL,
                page_url    TEXT,
                content     TEXT NOT NULL,
                fetched_at  TEXT NOT NULL,
                UNIQUE(course_id, page_url)
            );

            CREATE TABLE IF NOT EXISTS announcements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                canvas_id   INTEGER NOT NULL,
                course_id   INTEGER NOT NULL,
                title       TEXT,
                content     TEXT,
                posted_at   TEXT,
                fetched_at  TEXT NOT NULL,
                semester    TEXT NOT NULL,
                UNIQUE(canvas_id)
            );

            CREATE TABLE IF NOT EXISTS session_actions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                action_type     TEXT NOT NULL,
                target          TEXT,
                detail          TEXT,
                result          TEXT,
                course_id       INTEGER
            );

            CREATE TABLE IF NOT EXISTS session_context (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date    TEXT NOT NULL,
                context         TEXT NOT NULL,
                semester        TEXT NOT NULL,
                created_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_status   ON conversations(status);
            CREATE INDEX IF NOT EXISTS idx_conversations_course    ON conversations(course_id);
            CREATE INDEX IF NOT EXISTS idx_responses_semester      ON responses(semester);
            CREATE INDEX IF NOT EXISTS idx_responses_category      ON responses(primary_category);
            CREATE INDEX IF NOT EXISTS idx_responses_family        ON responses(course_family);
            CREATE INDEX IF NOT EXISTS idx_announcements_course    ON announcements(course_id);
            CREATE INDEX IF NOT EXISTS idx_session_actions_session ON session_actions(session_id);
            CREATE INDEX IF NOT EXISTS idx_session_actions_type    ON session_actions(action_type);
        """)
        self._conn.commit()

    # ─── Conversations ────────────────────────────────────────────────────────

    def upsert_conversation(self, conv: Conversation) -> int:
        """Insert or update a conversation. Returns the DB row id."""
        now = datetime.utcnow().isoformat()
        cur = self._conn.execute("""
            INSERT INTO conversations
                (canvas_conversation_id, course_id, course_code, course_family, modality,
                 student_name, student_canvas_id, subject, last_message_body,
                 last_message_at, topic_tags, primary_category, status, semester, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(canvas_conversation_id) DO UPDATE SET
                course_id        = excluded.course_id,
                course_code      = excluded.course_code,
                course_family    = excluded.course_family,
                modality         = excluded.modality,
                student_name     = excluded.student_name,
                student_canvas_id= excluded.student_canvas_id,
                subject          = excluded.subject,
                last_message_body= excluded.last_message_body,
                last_message_at  = excluded.last_message_at,
                topic_tags       = excluded.topic_tags,
                primary_category = excluded.primary_category,
                fetched_at       = excluded.fetched_at
        """, (
            conv.canvas_conversation_id,
            conv.course_id, conv.course_code, conv.course_family, conv.modality,
            conv.student_name, conv.student_canvas_id, conv.subject,
            conv.last_message_body,
            conv.last_message_at.isoformat() if conv.last_message_at else None,
            json.dumps(conv.topic_tags), conv.primary_category,
            conv.status, conv.semester, now,
        ))
        self._conn.commit()
        # Return the row id
        if cur.lastrowid:
            return cur.lastrowid
        row = self._conn.execute(
            "SELECT id FROM conversations WHERE canvas_conversation_id=?",
            (conv.canvas_conversation_id,)
        ).fetchone()
        return row["id"]

    def get_pending_conversations(self, semester: str = None) -> List[Dict]:
        """Return conversations with status='pending', ordered by priority."""
        q = "SELECT * FROM conversations WHERE status='pending'"
        params = []
        if semester:
            q += " AND semester=?"
            params.append(semester)
        q += " ORDER BY fetched_at DESC"
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def update_conversation_status(self, canvas_conversation_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE conversations SET status=? WHERE canvas_conversation_id=?",
            (status, canvas_conversation_id)
        )
        self._conn.commit()

    def get_conversation_db_id(self, canvas_conversation_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT id FROM conversations WHERE canvas_conversation_id=?",
            (canvas_conversation_id,)
        ).fetchone()
        return row["id"] if row else None

    # ─── Responses ────────────────────────────────────────────────────────────

    def upsert_response(self, resp: Response) -> int:
        now = datetime.utcnow().isoformat()
        cur = self._conn.execute("""
            INSERT INTO responses
                (conversation_id, canvas_conversation_id, course_id, course_family,
                 incoming_message, draft, final_sent, edit_distance, edit_ratio,
                 topic_tags, primary_category, semester, drafted_at, sent_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                draft            = excluded.draft,
                final_sent       = excluded.final_sent,
                edit_distance    = excluded.edit_distance,
                edit_ratio       = excluded.edit_ratio,
                topic_tags       = excluded.topic_tags,
                primary_category = excluded.primary_category,
                sent_at          = excluded.sent_at
        """, (
            resp.conversation_id, resp.canvas_conversation_id,
            resp.course_id, resp.course_family,
            resp.incoming_message, resp.draft, resp.final_sent,
            resp.edit_distance, resp.edit_ratio,
            json.dumps(resp.topic_tags), resp.primary_category,
            resp.semester,
            resp.drafted_at.isoformat() if resp.drafted_at else now,
            resp.sent_at.isoformat() if resp.sent_at else None,
        ))
        self._conn.commit()
        return cur.lastrowid or 0

    def get_sent_responses(
        self,
        course_family: Optional[str] = None,
        semester: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """Retrieve sent responses for learning/similarity search."""
        q = "SELECT r.*, c.course_code FROM responses r LEFT JOIN conversations c ON r.conversation_id = c.id WHERE r.final_sent IS NOT NULL"
        params = []
        if course_family:
            q += " AND r.course_family=?"
            params.append(course_family)
        if semester:
            q += " AND r.semester=?"
            params.append(semester)
        if category:
            q += " AND r.primary_category=?"
            params.append(category)
        q += " ORDER BY r.sent_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_session_stats(self, since_iso: str) -> Dict:
        """Count sent/skipped/flagged since a timestamp."""
        stats = {}
        for status in ("sent", "skipped", "flagged", "pending"):
            row = self._conn.execute(
                "SELECT COUNT(*) as n FROM conversations WHERE status=? AND fetched_at>=?",
                (status, since_iso)
            ).fetchone()
            stats[status] = row["n"]
        return stats

    def get_learning_stats(self, semester: Optional[str] = None) -> Dict:
        """Edit distance stats by category for learning-stats display."""
        q = """
            SELECT primary_category,
                   COUNT(*) as count,
                   AVG(edit_ratio) as avg_edit_ratio,
                   MIN(edit_ratio) as min_edit_ratio
            FROM responses
            WHERE final_sent IS NOT NULL AND edit_ratio IS NOT NULL
        """
        params = []
        if semester:
            q += " AND semester=?"
            params.append(semester)
        q += " GROUP BY primary_category ORDER BY count DESC"
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ─── Syllabus Cache ───────────────────────────────────────────────────────

    def upsert_syllabus_page(self, page: SyllabusPage) -> None:
        self._conn.execute("""
            INSERT INTO syllabus_cache (course_id, page_title, page_url, content, fetched_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(course_id, page_url) DO UPDATE SET
                page_title = excluded.page_title,
                content    = excluded.content,
                fetched_at = excluded.fetched_at
        """, (
            page.course_id, page.page_title, page.page_url,
            page.content, page.fetched_at.isoformat()
        ))
        self._conn.commit()

    def get_syllabus_pages(self, course_id: int) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM syllabus_cache WHERE course_id=? ORDER BY page_title",
            (course_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_syllabus_cache_age_days(self, course_id: int) -> Optional[float]:
        """Return age in days of the oldest cache entry for a course, or None if empty."""
        row = self._conn.execute(
            "SELECT MIN(fetched_at) as oldest FROM syllabus_cache WHERE course_id=?",
            (course_id,)
        ).fetchone()
        if not row or not row["oldest"]:
            return None
        oldest = datetime.fromisoformat(row["oldest"])
        return (datetime.utcnow() - oldest).total_seconds() / 86400

    def delete_syllabus_cache(self, course_id: int) -> None:
        self._conn.execute("DELETE FROM syllabus_cache WHERE course_id=?", (course_id,))
        self._conn.commit()

    # ─── Announcements ────────────────────────────────────────────────────────

    def upsert_announcement(self, ann: Announcement) -> None:
        self._conn.execute("""
            INSERT INTO announcements (canvas_id, course_id, title, content, posted_at, fetched_at, semester)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(canvas_id) DO UPDATE SET
                title     = excluded.title,
                content   = excluded.content,
                fetched_at= excluded.fetched_at
        """, (
            ann.canvas_id, ann.course_id, ann.title, ann.content,
            ann.posted_at.isoformat() if ann.posted_at else None,
            ann.fetched_at.isoformat(), ann.semester,
        ))
        self._conn.commit()

    def get_recent_announcements(self, course_id: int, max_age_days: int = 28) -> List[Dict]:
        cutoff = datetime.utcnow()
        from datetime import timedelta
        cutoff_str = (cutoff - timedelta(days=max_age_days)).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM announcements WHERE course_id=? AND posted_at>=? ORDER BY posted_at DESC",
            (course_id, cutoff_str)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Session Actions (action log) ─────────────────────────────────────────

    def log_action(
        self, session_id: str, action_type: str,
        target: str = None, detail: str = None,
        result: str = None, course_id: int = None,
    ) -> None:
        """Log a session action for design learning."""
        self._conn.execute("""
            INSERT INTO session_actions (session_id, timestamp, action_type, target, detail, result, course_id)
            VALUES (?,?,?,?,?,?,?)
        """, (
            session_id, datetime.utcnow().isoformat(), action_type,
            target, detail, result, course_id,
        ))
        self._conn.commit()

    def get_session_actions(self, session_id: str) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM session_actions WHERE session_id=? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_action_stats(self, semester: Optional[str] = None) -> List[Dict]:
        """Aggregate action type frequencies across all sessions."""
        q = "SELECT action_type, COUNT(*) as count FROM session_actions"
        params = []
        if semester:
            q += " WHERE session_id IN (SELECT DISTINCT session_id FROM session_actions WHERE timestamp >= ?)"
            params.append(f"{semester.split('_')[1]}-01-01" if '_' in semester else "2026-01-01")
        q += " GROUP BY action_type ORDER BY count DESC"
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ─── Session Context ──────────────────────────────────────────────────────

    def save_session_context(self, context: str, semester: str) -> None:
        self._conn.execute("""
            INSERT INTO session_context (session_date, context, semester, created_at)
            VALUES (?,?,?,?)
        """, (
            datetime.utcnow().date().isoformat(), context,
            semester, datetime.utcnow().isoformat(),
        ))
        self._conn.commit()

    def get_recent_session_context(self, limit: int = 3) -> List[Dict]:
        """Get most recent session contexts for draft enrichment."""
        rows = self._conn.execute(
            "SELECT * FROM session_context ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Steering Instructions (on responses) ─────────────────────────────────

    def update_response_steering(self, conversation_id: int, steering_json: str) -> None:
        """Add steering instructions to an existing response record."""
        # Add column if it doesn't exist yet (migration-safe)
        try:
            self._conn.execute("ALTER TABLE responses ADD COLUMN steering_instructions TEXT")
            self._conn.commit()
        except Exception:
            pass  # Column already exists
        self._conn.execute(
            "UPDATE responses SET steering_instructions=? WHERE conversation_id=?",
            (steering_json, conversation_id)
        )
        self._conn.commit()
