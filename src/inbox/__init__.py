"""
Canvas Inbox Responder — AI-assisted student message drafting.

Primary interface: CLI via `python -m inbox.cli`
Future: importable by Autograder GUI (inbox_panel.py)
"""
from .models import Conversation, Response, SyllabusPage, Announcement
from .db import InboxDB
from .config import InboxConfig

__all__ = ["Conversation", "Response", "SyllabusPage", "Announcement", "InboxDB", "InboxConfig"]
