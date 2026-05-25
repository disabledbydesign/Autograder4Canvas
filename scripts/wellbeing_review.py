#!/usr/bin/env python3
"""
wellbeing_review.py — Generate a standalone HTML report of wellbeing flags
across all graded assignments.

Usage:
    python3 scripts/wellbeing_review.py
    python3 scripts/wellbeing_review.py --db "~/Documents/Canvas Grading/insights.db"
    python3 scripts/wellbeing_review.py --out ~/Desktop/review.html
    python3 scripts/wellbeing_review.py --axis CRISIS
    python3 scripts/wellbeing_review.py --axis CRISIS,BURNOUT
"""

import argparse
import html
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ── SQL ──────────────────────────────────────────────────────────────────────

FLAGGED_SQL = """
SELECT
    r.assignment_name, r.course_name, r.started_at, r.run_id,
    c.student_name, c.student_id,
    json_extract(c.coding_record, '$.wellbeing_axis')       AS axis,
    json_extract(c.coding_record, '$.wellbeing_signal')     AS signal,
    json_extract(c.coding_record, '$.wellbeing_confidence') AS confidence,
    json_extract(c.coding_record, '$.observation')          AS observation,
    json_extract(c.coding_record, '$.emotional_register')   AS emotional_register,
    json_extract(c.coding_record, '$.theme_tags')           AS theme_tags_json,
    c.submission_text,
    (SELECT COUNT(*) FROM insights_codings c2 WHERE c2.run_id = r.run_id) AS run_total
FROM insights_codings c
JOIN insights_runs r ON c.run_id = r.run_id
WHERE json_extract(c.coding_record, '$.wellbeing_axis') IN ({placeholders})
ORDER BY r.started_at DESC, r.run_id,
    CASE json_extract(c.coding_record, '$.wellbeing_axis')
        WHEN 'CRISIS' THEN 0 ELSE 1 END,
    c.student_name
"""

RUN_TOTALS_SQL = """
SELECT r.run_id, r.assignment_name, r.course_name, r.started_at,
       COUNT(*) AS total,
       SUM(CASE WHEN json_extract(c.coding_record, '$.wellbeing_axis') IN ('CRISIS','BURNOUT')
                THEN 1 ELSE 0 END) AS flagged
FROM insights_codings c
JOIN insights_runs r ON c.run_id = r.run_id
WHERE json_extract(c.coding_record, '$.wellbeing_axis') IS NOT NULL
GROUP BY r.run_id
ORDER BY r.started_at DESC
"""


# ── Data loading ─────────────────────────────────────────────────────────────

def load_data(db_path: Path, axes: list[str]) -> tuple[list[dict], dict[str, dict]]:
    """Return (flagged_rows, run_totals_by_id)."""
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    placeholders = ",".join("?" * len(axes))
    sql = FLAGGED_SQL.format(placeholders=placeholders)

    rows = [dict(r) for r in conn.execute(sql, axes).fetchall()]

    # Parse theme_tags from JSON string
    for row in rows:
        raw = row.get("theme_tags_json")
        if raw:
            try:
                row["theme_tags"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                row["theme_tags"] = []
        else:
            row["theme_tags"] = []
        del row["theme_tags_json"]

        # Normalise confidence to float
        try:
            row["confidence"] = float(row["confidence"]) if row["confidence"] is not None else None
        except (ValueError, TypeError):
            row["confidence"] = None

    run_totals = {}
    for r in conn.execute(RUN_TOTALS_SQL).fetchall():
        run_totals[r["run_id"]] = dict(r)

    conn.close()
    return rows, run_totals


# ── HTML generation ───────────────────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #f8f6f1;
    color: #1a1a1a;
    font-size: 15px;
    line-height: 1.6;
}

a { color: #2c5f8a; text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Layout ── */
#layout { display: flex; min-height: 100vh; }

#sidebar {
    width: 270px;
    flex-shrink: 0;
    background: #ede9e0;
    border-right: 1px solid #d4cfc4;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    padding: 20px 0;
}

#main {
    flex: 1;
    padding: 32px 36px;
    max-width: 900px;
}

/* ── Sidebar ── */
.sidebar-header {
    padding: 0 18px 16px;
    border-bottom: 1px solid #d4cfc4;
    margin-bottom: 12px;
}
.sidebar-header h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b6455;
    font-weight: 600;
}
.sidebar-header .total-badge {
    display: inline-block;
    margin-top: 6px;
    background: #c0392b;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 12px;
}

.sidebar-nav { list-style: none; }
.sidebar-nav li a {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 6px 18px;
    font-size: 13px;
    color: #3a342a;
    border-left: 3px solid transparent;
    transition: background 0.1s;
}
.sidebar-nav li a:hover {
    background: #e0dbd0;
    text-decoration: none;
}
.sidebar-nav li a .run-count {
    margin-left: auto;
    font-size: 12px;
    color: #888;
    white-space: nowrap;
}
.sidebar-nav li a .crisis-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #c0392b;
    flex-shrink: 0;
    margin-right: 2px;
}
.sidebar-nav li a .burnout-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #e67e22;
    flex-shrink: 0;
    margin-right: 2px;
}

/* ── Page header ── */
.page-header {
    margin-bottom: 32px;
    padding-bottom: 20px;
    border-bottom: 2px solid #d4cfc4;
}
.page-header h1 {
    font-size: 24px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 6px;
}
.page-header .meta {
    font-size: 13px;
    color: #6b6455;
}
.page-header .meta span { margin-right: 18px; }

/* ── Assignment section ── */
.assignment-section {
    margin-bottom: 44px;
}
.assignment-section:last-child { margin-bottom: 0; }

.assignment-header {
    margin-bottom: 16px;
    padding: 14px 16px;
    background: #eeece5;
    border-radius: 6px;
    border-left: 4px solid #a09070;
}
.assignment-header h2 {
    font-size: 17px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 4px;
}
.assignment-header .assign-meta {
    font-size: 12.5px;
    color: #6b6455;
}
.assignment-header .assign-meta span { margin-right: 16px; }
.flag-fraction {
    font-weight: 600;
    color: #c0392b;
}

/* ── Student card ── */
.student-card {
    background: #fff;
    border: 1px solid #ddd8cc;
    border-radius: 8px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    overflow: hidden;
}

.card-top {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px 12px;
}

.student-name {
    font-weight: 700;
    font-size: 15px;
    flex: 1;
}

.axis-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    white-space: nowrap;
    flex-shrink: 0;
}
.axis-CRISIS  { background: #c0392b; color: #fff; }
.axis-BURNOUT { background: #e67e22; color: #fff; }

.confidence-text {
    font-size: 12px;
    color: #888;
    white-space: nowrap;
    flex-shrink: 0;
    padding-top: 4px;
}

/* ── Card body ── */
.card-body { padding: 0 16px 14px; }

.signal-text {
    font-size: 13.5px;
    color: #444;
    margin-bottom: 8px;
    font-style: italic;
}

.observation-text {
    font-size: 13.5px;
    color: #333;
    margin-bottom: 10px;
    padding: 10px 12px;
    background: #fafaf6;
    border-left: 3px solid #c8c0b0;
    border-radius: 0 4px 4px 0;
}

.theme-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-bottom: 10px;
}
.theme-pill {
    font-size: 11.5px;
    padding: 2px 8px;
    background: #ede9e0;
    border: 1px solid #cdc7bb;
    border-radius: 10px;
    color: #5a5040;
}

/* ── Submission details ── */
details.submission-details {
    border-top: 1px solid #eeece5;
    margin-top: 2px;
}
details.submission-details summary {
    cursor: pointer;
    padding: 8px 16px;
    font-size: 13px;
    color: #6b6455;
    user-select: none;
    list-style: none;
}
details.submission-details summary::-webkit-details-marker { display: none; }
details.submission-details summary::before {
    content: '▶ ';
    font-size: 10px;
}
details.submission-details[open] summary::before {
    content: '▼ ';
}
details.submission-details summary:hover { color: #3a342a; }

.submission-body {
    padding: 0 16px 16px;
}
.submission-body pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 13px;
    color: #333;
    background: #fafaf6;
    border: 1px solid #e0dbd0;
    border-radius: 4px;
    padding: 12px 14px;
    max-height: 400px;
    overflow-y: auto;
    line-height: 1.55;
}

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #888;
}
.empty-state h2 { font-size: 18px; margin-bottom: 8px; color: #555; }

/* ── Print ── */
@media print {
    #sidebar { display: none; }
    #main { max-width: 100%; padding: 20px; }
    .student-card { break-inside: avoid; }
    details.submission-details { display: block; }
    details.submission-details summary { display: none; }
    .submission-body { display: block; }
}
"""


def h(text: str) -> str:
    """HTML-escape a string, treating None as empty."""
    if text is None:
        return ""
    return html.escape(str(text))


def format_date(iso_str: str | None) -> str:
    if not iso_str:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return iso_str[:10] if iso_str else "Unknown date"


def confidence_label(conf) -> str:
    if conf is None:
        return ""
    pct = int(round(float(conf) * 100))
    return f"{pct}% confidence"


def render_student_card(row: dict) -> str:
    axis = row.get("axis", "")
    badge_class = f"axis-{axis}" if axis in ("CRISIS", "BURNOUT") else "axis-BURNOUT"

    conf_label = confidence_label(row.get("confidence"))
    signal = row.get("signal") or ""
    observation = row.get("observation") or ""
    emotional_register = row.get("emotional_register") or ""
    theme_tags = row.get("theme_tags") or []
    submission_text = row.get("submission_text") or ""
    student_name = row.get("student_name") or "Unknown Student"

    # Pills
    pills_html = ""
    if theme_tags:
        pills = "".join(f'<span class="theme-pill">{h(tag)}</span>' for tag in theme_tags)
        pills_html = f'<div class="theme-pills">{pills}</div>'

    # Signal line
    signal_html = ""
    if signal:
        signal_html = f'<div class="signal-text">{h(signal)}</div>'

    # Observation block
    obs_html = ""
    if observation:
        obs_html = f'<div class="observation-text">{h(observation)}</div>'

    # Emotional register
    reg_html = ""
    if emotional_register:
        reg_html = f'<div style="font-size:12px;color:#888;margin-bottom:8px;">Register: {h(emotional_register)}</div>'

    # Submission
    sub_html = ""
    if submission_text:
        sub_html = (
            '<details class="submission-details">'
            '<summary>View full submission</summary>'
            '<div class="submission-body">'
            f'<pre>{h(submission_text)}</pre>'
            '</div>'
            '</details>'
        )

    return (
        '<div class="student-card">'
        '<div class="card-top">'
        f'<div class="student-name">{h(student_name)}</div>'
        f'<span class="axis-badge {badge_class}">{h(axis)}</span>'
        + (f'<span class="confidence-text">{h(conf_label)}</span>' if conf_label else "")
        + '</div>'
        '<div class="card-body">'
        + signal_html
        + obs_html
        + reg_html
        + pills_html
        + '</div>'
        + sub_html
        + '</div>'
    )


def render_assignment_section(run_id: str, rows: list[dict], run_totals: dict) -> str:
    if not rows:
        return ""

    first = rows[0]
    assignment_name = first.get("assignment_name") or "Unnamed Assignment"
    course_name = first.get("course_name") or ""
    started_at = first.get("started_at") or ""
    run_total = first.get("run_total") or 0

    flagged_count = len(rows)
    crisis_count = sum(1 for r in rows if r.get("axis") == "CRISIS")
    burnout_count = sum(1 for r in rows if r.get("axis") == "BURNOUT")

    if run_total > 0:
        pct = int(round(flagged_count / run_total * 100))
        fraction_str = f"{flagged_count}/{run_total} flagged ({pct}%)"
    else:
        fraction_str = f"{flagged_count} flagged"

    axis_breakdown = []
    if crisis_count:
        axis_breakdown.append(f"{crisis_count} CRISIS")
    if burnout_count:
        axis_breakdown.append(f"{burnout_count} BURNOUT")
    breakdown_str = " · ".join(axis_breakdown)

    # Anchor id: sanitise
    anchor = f"run-{h(run_id)}"

    cards = "\n".join(render_student_card(r) for r in rows)

    return (
        f'<section class="assignment-section" id="{anchor}">'
        '<div class="assignment-header">'
        f'<h2>{h(assignment_name)}</h2>'
        '<div class="assign-meta">'
        + (f'<span>{h(course_name)}</span>' if course_name else "")
        + f'<span>{format_date(started_at)}</span>'
        f'<span class="flag-fraction">{h(fraction_str)}</span>'
        + (f'<span style="color:#888;">{h(breakdown_str)}</span>' if breakdown_str else "")
        + '</div>'
        '</div>'
        + cards
        + '</section>'
    )


def render_sidebar(grouped: dict, run_order: list[str], rows_by_run: dict) -> str:
    total_flagged = sum(len(v) for v in rows_by_run.values())

    items = []
    for run_id in run_order:
        rows = rows_by_run.get(run_id, [])
        if not rows:
            continue
        first = rows[0]
        assignment_name = first.get("assignment_name") or "Unnamed"
        crisis_count = sum(1 for r in rows if r.get("axis") == "CRISIS")
        burnout_count = sum(1 for r in rows if r.get("axis") == "BURNOUT")

        dots = ""
        if crisis_count:
            dots += '<span class="crisis-dot"></span>'
        if burnout_count:
            dots += '<span class="burnout-dot"></span>'

        count_parts = []
        if crisis_count:
            count_parts.append(f"{crisis_count} C")
        if burnout_count:
            count_parts.append(f"{burnout_count} B")
        count_str = " · ".join(count_parts) if count_parts else str(len(rows))

        items.append(
            f'<li><a href="#run-{h(run_id)}">'
            + dots
            + f'<span style="flex:1;">{h(assignment_name)}</span>'
            + f'<span class="run-count">{count_str}</span>'
            + '</a></li>'
        )

    nav_items = "\n".join(items)

    return (
        '<aside id="sidebar">'
        '<div class="sidebar-header">'
        '<h2>Assignments</h2>'
        f'<div class="total-badge">{total_flagged} flagged total</div>'
        '</div>'
        f'<ul class="sidebar-nav">{nav_items}</ul>'
        '</aside>'
    )


def render_page_header(total_flagged: int, run_count: int, axes: list[str], generated_at: str) -> str:
    axes_str = " + ".join(axes)
    return (
        '<header class="page-header">'
        '<h1>Wellbeing Review</h1>'
        '<div class="meta">'
        f'<span><strong>{total_flagged}</strong> flagged students</span>'
        f'<span>across <strong>{run_count}</strong> assignment run{"s" if run_count != 1 else ""}</span>'
        f'<span>axes: {h(axes_str)}</span>'
        f'<span style="color:#aaa;">Generated {generated_at}</span>'
        '</div>'
        '</header>'
    )


def generate_html(rows: list[dict], run_totals: dict, axes: list[str]) -> str:
    # Group by run_id, preserving order
    run_order: list[str] = []
    rows_by_run: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rid = row["run_id"]
        if rid not in rows_by_run:
            run_order.append(rid)
        rows_by_run[rid].append(row)

    total_flagged = len(rows)
    generated_at = datetime.now().strftime("%B %-d, %Y at %-I:%M %p")

    sidebar_html = render_sidebar({}, run_order, rows_by_run)
    header_html = render_page_header(total_flagged, len(run_order), axes, generated_at)

    if rows:
        sections = "\n".join(
            render_assignment_section(rid, rows_by_run[rid], run_totals)
            for rid in run_order
        )
        main_content = header_html + sections
    else:
        main_content = (
            header_html
            + '<div class="empty-state">'
            + '<h2>No flagged students found</h2>'
            + f'<p>No students with axes {", ".join(axes)} were found in this database.</p>'
            + '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wellbeing Review</title>
<style>
{CSS}
</style>
</head>
<body>
<div id="layout">
{sidebar_html}
<main id="main">
{main_content}
</main>
</div>
</body>
</html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    default_db = Path.home() / "Documents" / "Canvas Grading" / "insights.db"
    default_out = Path.home() / "Desktop" / "wellbeing_review.html"

    parser = argparse.ArgumentParser(
        description="Generate a standalone HTML wellbeing review report from insights.db"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db,
        metavar="PATH",
        help=f"Path to insights.db (default: {default_db})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out,
        metavar="PATH",
        help=f"Output HTML path (default: {default_out})",
    )
    parser.add_argument(
        "--axis",
        type=str,
        default="CRISIS,BURNOUT",
        metavar="AXIS[,AXIS]",
        help="Comma-separated axes to include: CRISIS, BURNOUT (default: CRISIS,BURNOUT)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    axes = [a.strip().upper() for a in args.axis.split(",") if a.strip()]
    valid = {"CRISIS", "BURNOUT", "ENGAGED", "NONE"}
    for ax in axes:
        if ax not in valid:
            print(f"ERROR: Unknown axis '{ax}'. Valid values: {', '.join(sorted(valid))}", file=sys.stderr)
            sys.exit(1)

    db_path = args.db.expanduser().resolve()
    out_path = args.out.expanduser().resolve()

    print(f"Database : {db_path}")
    print(f"Axes     : {', '.join(axes)}")

    rows, run_totals = load_data(db_path, axes)

    print(f"Flagged  : {len(rows)} student records across "
          f"{len(set(r['run_id'] for r in rows))} run(s)")

    html_content = generate_html(rows, run_totals, axes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")

    print(f"Output   : {out_path}")


if __name__ == "__main__":
    main()
