"""
CLI entry point for the inbox module.
Run as: python -m inbox.cli <subcommand> [args]

Subcommands:
  fetch    -- Pull unread conversations from Canvas; refresh caches
  context  -- Output assembled context blob for a conversation (JSON + text)
  send     -- Send a reply via Canvas API
  log      -- Store a draft + final response for learning
  status   -- Session summary
  learning-stats -- Edit distance stats by category
"""
import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path


def cmd_fetch(args, config):
    """Pull unread conversations; refresh syllabus and announcement caches."""
    from .conversations import CanvasConversationsAPI
    from .db import InboxDB

    def progress(msg):
        if not args.quiet:
            print(f"  {msg}", file=sys.stderr)

    course_ids = None
    if args.course:
        course_ids = [int(c) for c in args.course.split(",")]
    elif args.all:
        course_ids = list(config.courses.keys())

    api = CanvasConversationsAPI(config)

    progress("Connecting to Canvas...")
    conversations = api.get_unread_conversations(course_ids=course_ids, on_progress=progress)

    with InboxDB(config.db_path) as db:
        # Check which conversations were already handled (skipped/sent/flagged)
        already_handled = set()
        for conv in conversations:
            existing_id = db.get_conversation_db_id(conv.canvas_conversation_id)
            if existing_id:
                row = db._conn.execute(
                    "SELECT status FROM conversations WHERE id=?", (existing_id,)
                ).fetchone()
                if row and row["status"] in ("sent", "flagged"):
                    already_handled.add(conv.canvas_conversation_id)

        # Store conversations in DB (preserves existing status via upsert)
        for conv in conversations:
            db.upsert_conversation(conv)

        # Refresh announcement cache for each course with unread messages
        seen_courses = set()
        for conv in conversations:
            if conv.course_id and conv.course_id not in seen_courses:
                seen_courses.add(conv.course_id)
                progress(f"Refreshing announcements for {conv.course_code}...")
                anns = api.fetch_recent_announcements(conv.course_id, on_progress=progress)
                for ann in anns:
                    db.upsert_announcement(ann)

        if args.all:
            for cid in config.courses:
                if cid not in seen_courses:
                    progress(f"Refreshing announcements for course {cid}...")
                    anns = api.fetch_recent_announcements(cid, on_progress=progress)
                    for ann in anns:
                        db.upsert_announcement(ann)

    # Output JSON — only conversations that haven't been fully handled
    output = []
    for conv in conversations:
        if conv.canvas_conversation_id in already_handled:
            continue
        icon = config.topic_icons.get(conv.primary_category, "✉️")
        crisis_flag = " ⚠️ CRISIS — FLAG FOR MANUAL REVIEW" if conv.is_crisis else ""
        output.append({
            "canvas_conversation_id": conv.canvas_conversation_id,
            "course_code": conv.course_code,
            "student_name": conv.student_name,
            "subject": conv.subject,
            "primary_category": conv.primary_category,
            "topic_tags": conv.topic_tags,
            "icon": icon,
            "time_ago": conv.time_ago_str,
            "is_crisis": conv.is_crisis,
            "crisis_flag": crisis_flag,
            "last_message_preview": (conv.last_message_body or "")[:120],
            "status": conv.status,
        })

    print(json.dumps(output, indent=2))


def cmd_context(args, config):
    """Build and output context for a conversation."""
    from .conversations import CanvasConversationsAPI
    from .db import InboxDB
    from .context_engine import build_context

    canvas_id = int(args.conversation_id)

    def progress(msg):
        if not args.quiet:
            print(f"  {msg}", file=sys.stderr)

    api = CanvasConversationsAPI(config)

    # Get full conversation detail from Canvas
    progress(f"Fetching conversation {canvas_id} from Canvas...")
    conv = api.get_conversation_detail(canvas_id)
    if not conv:
        print(json.dumps({"error": f"Conversation {canvas_id} not found"}))
        sys.exit(1)

    with InboxDB(config.db_path) as db:
        # Ensure conversation is in DB
        db.upsert_conversation(conv)

        # Build context
        bundle = build_context(conv, db, api, config, on_progress=progress)

    # Output JSON metadata + text context
    result = {
        "conversation_id": canvas_id,
        "student_name": conv.student_name,
        "course_code": conv.course_code,
        "course_family": conv.course_family,
        "modality": conv.modality,
        "subject": conv.subject,
        "primary_category": conv.primary_category,
        "topic_tags": conv.topic_tags,
        "is_crisis": conv.is_crisis,
        "latest_student_message": conv.latest_student_message,
        "similar_responses_count": len(bundle.similar_responses),
        "syllabus_pages_count": len(bundle.syllabus_pages),
        "announcements_count": len(bundle.recent_announcements),
        "context_text": bundle.to_prompt_text(),
    }

    if args.context_file:
        Path(args.context_file).write_text(bundle.to_prompt_text(), encoding="utf-8")
        result["context_file"] = args.context_file
        del result["context_text"]  # Don't double-output

    print(json.dumps(result, indent=2))


def cmd_send(args, config):
    """Send a reply via Canvas API."""
    from .conversations import CanvasConversationsAPI
    from .db import InboxDB

    canvas_id = int(args.conversation_id)
    message_path = Path(args.message_file)

    if not message_path.exists():
        print(json.dumps({"error": f"Message file not found: {args.message_file}"}))
        sys.exit(1)

    message_body = message_path.read_text(encoding="utf-8").strip()
    if not message_body:
        print(json.dumps({"error": "Message file is empty"}))
        sys.exit(1)

    def progress(msg):
        if not args.quiet:
            print(f"  {msg}", file=sys.stderr)

    api = CanvasConversationsAPI(config)
    success = api.reply_to_conversation(canvas_id, message_body, on_progress=progress)

    if success:
        api.mark_as_read(canvas_id)
        with InboxDB(config.db_path) as db:
            db.update_conversation_status(canvas_id, "sent")
        print(json.dumps({"success": True, "canvas_conversation_id": canvas_id}))
    else:
        print(json.dumps({"success": False, "error": "Send failed"}))
        sys.exit(1)


def cmd_log(args, config):
    """Store a draft + final response for learning."""
    from .db import InboxDB
    from .learning import compute_edit_ratio, extract_topic_tags
    from .models import Response

    canvas_id = int(args.conversation_id)

    draft = ""
    if args.draft_file:
        draft_path = Path(args.draft_file)
        if draft_path.exists():
            draft = draft_path.read_text(encoding="utf-8").strip()

    final_path = Path(args.final_file)
    if not final_path.exists():
        print(json.dumps({"error": f"Final file not found: {args.final_file}"}))
        sys.exit(1)
    final_sent = final_path.read_text(encoding="utf-8").strip()

    # Parse tags
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    primary_category = tags[0] if tags else "other"

    # Parse steering instructions
    steering = []
    if args.steering:
        steering = [s.strip() for s in args.steering.split("|") if s.strip()]

    edit_ratio = compute_edit_ratio(draft, final_sent) if draft else None
    edit_distance_words = None
    if draft:
        from .learning import levenshtein_distance
        edit_distance_words = levenshtein_distance(draft, final_sent)

    with InboxDB(config.db_path) as db:
        db_id = db.get_conversation_db_id(canvas_id)
        if not db_id:
            print(json.dumps({"error": f"Conversation {canvas_id} not in DB. Run fetch first."}))
            sys.exit(1)

        # Get course info from DB
        row = db._conn.execute(
            "SELECT course_id, course_family, last_message_body FROM conversations WHERE canvas_conversation_id=?",
            (canvas_id,)
        ).fetchone()
        course_id = row["course_id"] if row else None
        course_family = row["course_family"] if row else None
        incoming = row["last_message_body"] if row else ""

        resp = Response(
            conversation_id=db_id,
            canvas_conversation_id=canvas_id,
            course_id=course_id,
            course_family=course_family,
            incoming_message=incoming or "",
            draft=draft or None,
            final_sent=final_sent,
            edit_distance=edit_distance_words,
            edit_ratio=edit_ratio,
            topic_tags=tags,
            primary_category=primary_category,
            semester=config.current_semester,
            drafted_at=datetime.utcnow(),
            sent_at=datetime.utcnow(),
        )
        resp_id = db.upsert_response(resp)

        # Store steering instructions if provided
        if steering:
            db.update_response_steering(db_id, json.dumps(steering))

    print(json.dumps({
        "logged": True,
        "response_id": resp_id,
        "edit_ratio": round(edit_ratio, 3) if edit_ratio is not None else None,
        "edit_distance_words": edit_distance_words,
        "tags": tags,
        "steering_count": len(steering),
    }))


def cmd_skip(args, config):
    """Mark a conversation as skipped."""
    from .db import InboxDB
    canvas_id = int(args.conversation_id)
    with InboxDB(config.db_path) as db:
        db.update_conversation_status(canvas_id, "skipped")
    print(json.dumps({"skipped": True, "canvas_conversation_id": canvas_id}))


def cmd_flag(args, config):
    """Mark a conversation as flagged for manual review."""
    from .db import InboxDB
    canvas_id = int(args.conversation_id)
    with InboxDB(config.db_path) as db:
        db.update_conversation_status(canvas_id, "flagged")
    canvas_url = f"{config.canvas_base_url}/conversations#{canvas_id}"
    print(json.dumps({"flagged": True, "canvas_conversation_id": canvas_id, "canvas_url": canvas_url}))


def cmd_log_action(args, config):
    """Log a session action for design learning."""
    from .db import InboxDB
    with InboxDB(config.db_path) as db:
        db.log_action(
            session_id=args.session_id,
            action_type=args.action_type,
            target=args.target,
            detail=args.detail,
            result=args.result,
            course_id=int(args.course_id) if args.course_id else None,
        )
    print(json.dumps({"logged": True, "action_type": args.action_type}))


def cmd_debrief(args, config):
    """Output session data for design debrief."""
    from .db import InboxDB

    with InboxDB(config.db_path) as db:
        actions = db.get_session_actions(args.session_id)
        today = datetime.utcnow().date().isoformat()
        stats = db.get_session_stats(since_iso=today)
        learning = db.get_learning_stats(semester=config.current_semester)

    # Compute action type summary
    action_counts = {}
    for a in actions:
        t = a["action_type"]
        action_counts[t] = action_counts.get(t, 0) + 1

    # Extract steering instructions from actions
    steerings = [a["detail"] for a in actions if a["action_type"] == "steer" and a.get("detail")]

    print(json.dumps({
        "session_id": args.session_id,
        "action_summary": action_counts,
        "total_actions": len(actions),
        "actions": actions,
        "session_stats": stats,
        "learning_stats": learning,
        "steering_instructions": steerings,
    }, indent=2))


def cmd_status(args, config):
    """Show session summary."""
    from .db import InboxDB

    with InboxDB(config.db_path) as db:
        # Session = today
        today = datetime.utcnow().date().isoformat()
        stats = db.get_session_stats(since_iso=today)

    total_handled = stats.get("sent", 0) + stats.get("skipped", 0) + stats.get("flagged", 0)
    print(json.dumps({
        "since": today,
        "sent": stats.get("sent", 0),
        "skipped": stats.get("skipped", 0),
        "flagged": stats.get("flagged", 0),
        "pending": stats.get("pending", 0),
        "total_handled": total_handled,
    }))


def cmd_learning_stats(args, config):
    """Show edit distance stats by category."""
    from .db import InboxDB

    with InboxDB(config.db_path) as db:
        stats = db.get_learning_stats(semester=args.semester)

    print(json.dumps(stats, indent=2))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Canvas Inbox Responder CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m inbox.cli fetch --all
  python -m inbox.cli context 12345
  python -m inbox.cli send 12345 --message-file /tmp/reply.txt
  python -m inbox.cli log 12345 --draft-file /tmp/draft.txt --final-file /tmp/reply.txt --tags extension
  python -m inbox.cli status
  python -m inbox.cli learning-stats
        """
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress messages")
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Pull unread conversations from Canvas")
    p_fetch.add_argument("--course", help="Comma-separated course IDs to filter")
    p_fetch.add_argument("--all", action="store_true", help="Fetch from all known courses")

    # context
    p_ctx = sub.add_parser("context", help="Build context for a conversation")
    p_ctx.add_argument("conversation_id", help="Canvas conversation ID")
    p_ctx.add_argument("--context-file", help="Write context text to this file path")

    # send
    p_send = sub.add_parser("send", help="Send a reply via Canvas API")
    p_send.add_argument("conversation_id", help="Canvas conversation ID")
    p_send.add_argument("--message-file", required=True, help="Path to file containing the message body")

    # log
    p_log = sub.add_parser("log", help="Log a response for learning")
    p_log.add_argument("conversation_id", help="Canvas conversation ID")
    p_log.add_argument("--draft-file", help="Path to the initial draft file")
    p_log.add_argument("--final-file", required=True, help="Path to the final sent message file")
    p_log.add_argument("--tags", help="Comma-separated topic tags (e.g. extension,grade_question)")
    p_log.add_argument("--steering", help="Pipe-separated steering instructions (e.g. 'shorter|add office hours')")

    # log-action
    p_la = sub.add_parser("log-action", help="Log a session action for design learning")
    p_la.add_argument("--session-id", required=True, help="Session UUID")
    p_la.add_argument("--action-type", required=True, help="Action type (fetch, investigate, publish, push_deadline, announce, draft, steer, send, skip, flag, grade_fix, search_sent, mcp_lookup)")
    p_la.add_argument("--target", help="What was acted on (conversation_id, module_id, etc.)")
    p_la.add_argument("--detail", help="Details (steering instruction, search query, etc.)")
    p_la.add_argument("--result", help="What happened")
    p_la.add_argument("--course-id", help="Course ID if applicable")

    # debrief
    p_db = sub.add_parser("debrief", help="Output session data for design debrief")
    p_db.add_argument("session_id", help="Session UUID")

    # skip
    p_skip = sub.add_parser("skip", help="Mark a conversation as skipped")
    p_skip.add_argument("conversation_id", help="Canvas conversation ID")

    # flag
    p_flag = sub.add_parser("flag", help="Flag a conversation for manual review")
    p_flag.add_argument("conversation_id", help="Canvas conversation ID")

    # status
    sub.add_parser("status", help="Show session summary")

    # learning-stats
    p_ls = sub.add_parser("learning-stats", help="Show learning stats by category")
    p_ls.add_argument("--semester", help="Filter by semester (e.g. spring_2026)")

    args = parser.parse_args()

    # Load config (credentials from Autograder's credentials.json)
    from .config import get_config
    config = get_config()

    if not config.canvas_api_token:
        print(json.dumps({"error": "Canvas API token not found. Check ~/Library/Application Support/CanvasAutograder/credentials.json"}))
        sys.exit(1)

    dispatch = {
        "fetch": cmd_fetch,
        "context": cmd_context,
        "send": cmd_send,
        "log": cmd_log,
        "log-action": cmd_log_action,
        "debrief": cmd_debrief,
        "skip": cmd_skip,
        "flag": cmd_flag,
        "status": cmd_status,
        "learning-stats": cmd_learning_stats,
    }
    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()
