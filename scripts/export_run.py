#!/usr/bin/env python3
"""
Export an Insights run to a clean Markdown report.

Usage:
    python3 scripts/export_run.py                       # interactive: lists runs, pick one
    python3 scripts/export_run.py <run_id>              # export a specific run by id
    python3 scripts/export_run.py <run_id> -o file.md   # specify output path

Output goes to ~/Desktop by default with filename derived from course/assignment.
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from insights.insights_store import InsightsStore


def _decode_json_field(value):
    """Best-effort decode of a JSON field that may already be a dict."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _safe_filename(s: str, maxlen: int = 60) -> str:
    keep = "".join(c if c.isalnum() or c in "-_ " else "_" for c in s)
    return keep.replace(" ", "_")[:maxlen].strip("_")


def _pick_run_interactive(store: InsightsStore) -> str:
    runs = store.get_completed_runs()
    if not runs:
        print("No completed runs found in the database.", file=sys.stderr)
        sys.exit(1)

    print("Recent completed runs:\n")
    for i, r in enumerate(runs[:30], 1):
        date = (r.get("completed_at") or r.get("started_at") or "")[:10]
        course = r.get("course_name", "?")[:40]
        assign = r.get("assignment_name", "?")[:50]
        print(f"  [{i:>2}] {date}  {course}  ·  {assign}")

    raw = input("\nPick a run number: ").strip()
    try:
        idx = int(raw) - 1
        return runs[idx]["run_id"]
    except (ValueError, IndexError):
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)


def _format_themes(theme_set) -> str:
    """theme_set is stored as JSON; structure varies but typically has 'themes' key."""
    data = _decode_json_field(theme_set)
    if not data:
        return "_(no themes saved)_"
    themes = data.get("themes", []) if isinstance(data, dict) else data
    if not isinstance(themes, list) or not themes:
        return "_(no themes saved)_"

    lines = []
    for t in themes:
        if not isinstance(t, dict):
            continue
        label = (t.get("name") or t.get("label") or t.get("theme_label")
                 or "(untitled)")
        desc  = t.get("description") or t.get("theme_description") or ""
        # frequency may be a count; student_ids is the canonical list
        count = (t.get("frequency")
                 or t.get("student_count")
                 or len(t.get("student_ids") or t.get("students") or []))
        students = t.get("student_ids") or t.get("students") or []
        quotes = (t.get("supporting_quotes")
                  or t.get("representative_quotes")
                  or t.get("quotes") or [])

        lines.append(f"### {label}")
        if count:
            lines.append(f"_{count} students_")
        if desc:
            lines.append(f"\n{desc}")
        if students and isinstance(students, list):
            names = ", ".join(str(s) for s in students[:10])
            more  = "" if len(students) <= 10 else f" (+{len(students)-10} more)"
            lines.append(f"\n**Students:** {names}{more}")
        if quotes:
            lines.append("\nSupporting quotes:")
            for q in quotes[:3]:
                if isinstance(q, dict):
                    text = (q.get("text") or q.get("quote") or "").strip()
                    sig  = (q.get("significance") or "").strip()
                    name = (q.get("student_name") or q.get("student_id") or "").strip()
                    prefix = f"_{name}_: " if name else ""
                    lines.append(f"- {prefix}\"{text}\"")
                    if sig:
                        lines.append(f"  - _{sig}_")
                else:
                    lines.append(f"- \"{q}\"")
        lines.append("")
    return "\n".join(lines)


def _format_student_record(record: dict) -> str:
    """Format a single coding record as a Markdown student section."""
    name    = record.get("student_name", "Unknown")
    raw     = _decode_json_field(record.get("coding_record")) or {}
    sub_txt = (record.get("submission_text") or "").strip()

    axis      = raw.get("wellbeing_axis", "")
    signal    = (raw.get("wellbeing_signal") or "").strip()
    conf      = raw.get("wellbeing_confidence")
    prescan   = raw.get("prescan_signals") or []
    checkin   = raw.get("checkin_flag")
    checkin_r = (raw.get("checkin_reasoning") or "").strip()
    obs       = (raw.get("observation") or "").strip()
    wc        = raw.get("word_count")

    lines = [f"### {name}"]
    meta = []
    if wc:
        meta.append(f"{wc} words")
    if axis:
        conf_str = f" (conf {float(conf):.2f})" if conf is not None else ""
        meta.append(f"4-axis: **{axis}**{conf_str}")
    if checkin:
        meta.append("**CHECK-IN flagged**")
    if meta:
        lines.append(" · ".join(meta))

    if signal:
        lines.append(f"\n**Signal:** {signal}")
    if prescan:
        lines.append("\n**Prescan signals:**")
        for s in prescan[:5]:
            lines.append(f"- \"{s}\"")
    if checkin and checkin_r:
        lines.append(f"\n**Check-in reasoning:** {checkin_r}")
    if obs:
        lines.append(f"\n**Observation:**\n\n{obs}")
    if sub_txt:
        # quote each line to render as a Markdown blockquote
        quoted = "\n".join(f"> {ln}" if ln else ">" for ln in sub_txt.splitlines())
        lines.append(f"\n**Submission:**\n\n{quoted}")
    lines.append("")
    return "\n".join(lines)


def export_run_csv(run_id: str, out_path: Path) -> None:
    """Write per-student CSV: name, 4-axis, check-in, observation.

    Track A (binary concern) is not persisted to the DB — to get it,
    run Track A in the offline research panel and use its 'Export CSV'
    button instead.
    """
    store = InsightsStore()
    run = store.get_run(run_id)
    if not run:
        print(f"Run not found: {run_id}", file=sys.stderr)
        sys.exit(1)

    codings = store.get_codings(run_id) or []
    sorted_codings = sorted(codings, key=lambda r: (r.get("student_name") or "").lower())

    fields = [
        "student_name",
        "word_count",
        "submission_text",
        "axis",
        "axis_confidence",
        "signal",
        "prescan_signals",
        "checkin_flag",
        "checkin_reasoning",
        "observation",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for record in sorted_codings:
            raw = _decode_json_field(record.get("coding_record")) or {}
            prescan = raw.get("prescan_signals") or []
            w.writerow({
                "student_name":       record.get("student_name", ""),
                "word_count":         raw.get("word_count", ""),
                "submission_text":    record.get("submission_text", "") or "",
                "axis":               raw.get("wellbeing_axis", ""),
                "axis_confidence":    raw.get("wellbeing_confidence", ""),
                "signal":             raw.get("wellbeing_signal", ""),
                "prescan_signals":    " | ".join(str(s) for s in prescan),
                "checkin_flag":       raw.get("checkin_flag", ""),
                "checkin_reasoning":  raw.get("checkin_reasoning", ""),
                "observation":        raw.get("observation", ""),
            })

    print(f"Wrote {len(sorted_codings)} students to {out_path}")


def export_run(run_id: str, out_path: Path) -> None:
    store = InsightsStore()
    run = store.get_run(run_id)
    if not run:
        print(f"Run not found: {run_id}", file=sys.stderr)
        sys.exit(1)

    course   = run.get("course_name", "?")
    assign   = run.get("assignment_name", "?")
    started  = (run.get("started_at") or "")[:19].replace("T", " ")
    finished = (run.get("completed_at") or "")[:19].replace("T", " ")
    model    = run.get("model_name", "?")
    tier     = run.get("model_tier", "?")
    n_subs   = run.get("total_submissions", 0)
    pipeline_conf = _decode_json_field(run.get("pipeline_confidence")) or {}

    # Class-level data is stored in insights_themes (one row per run)
    theme_row = None
    rows = store._conn.execute(
        "SELECT theme_set, outlier_report, synthesis_report, observation_synthesis "
        "FROM insights_themes WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    if rows:
        theme_row = dict(rows[0])

    synthesis = (theme_row or {}).get("synthesis_report", "") or ""
    outlier   = (theme_row or {}).get("outlier_report", "") or ""
    obs_synth = (theme_row or {}).get("observation_synthesis", "") or ""
    theme_set = (theme_row or {}).get("theme_set")

    # Codings (per-student)
    codings = store.get_codings(run_id) or []

    # Build the Markdown
    md = []
    md.append(f"# {assign}")
    md.append(f"\n**Course:** {course}  ")
    md.append(f"**Run date:** {finished or started}  ")
    md.append(f"**Students analyzed:** {n_subs}  ")
    md.append(f"**Model:** {model} ({tier})  ")
    if pipeline_conf:
        overall = pipeline_conf.get("overall")
        if overall is not None:
            md.append(f"**Pipeline confidence:** {float(overall):.2f}  ")
    md.append(f"**Run ID:** `{run_id}`\n")
    md.append("---\n")

    # Class synthesis — prefer observation_synthesis (newer, richer) over the
    # older synthesis_report; show both if both populated and they differ.
    md.append("## Class synthesis\n")
    primary = obs_synth.strip() or synthesis.strip()
    md.append(primary if primary else "_(no synthesis saved)_")
    md.append("\n")
    if obs_synth.strip() and synthesis.strip() and synthesis.strip() != obs_synth.strip():
        md.append("### (legacy synthesis report)\n")
        md.append(synthesis)
        md.append("\n")

    # Themes
    md.append("## Themes\n")
    md.append(_format_themes(theme_set))
    md.append("")

    # Outliers
    if outlier.strip():
        md.append("## Outliers\n")
        md.append(outlier)
        md.append("")

    # Check-in flagged students summary (high-priority for teacher attention)
    flagged = []
    for record in codings:
        raw = _decode_json_field(record.get("coding_record")) or {}
        if raw.get("checkin_flag"):
            flagged.append(record)
    if flagged:
        md.append("## Check-in flags\n")
        md.append("Students the system flagged for a possible check-in. "
                  "These are *signals to consider*, not verdicts.\n")
        for record in flagged:
            name = record.get("student_name", "?")
            raw  = _decode_json_field(record.get("coding_record")) or {}
            reasoning = (raw.get("checkin_reasoning") or "").strip()
            md.append(f"- **{name}** — {reasoning}")
        md.append("")

    # Per-student detail
    md.append("## Per-student records\n")
    md.append(f"_{len(codings)} students; sorted alphabetically._\n")
    sorted_codings = sorted(codings, key=lambda r: (r.get("student_name") or "").lower())
    for record in sorted_codings:
        md.append(_format_student_record(record))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {len(codings)} students to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an Insights run to Markdown.")
    parser.add_argument("run_id", nargs="?",
                        help="Run ID to export (omit for interactive picker)")
    parser.add_argument("-o", "--output", type=Path,
                        help="Output path (default: ~/Desktop/<course>_<assignment>.md)")
    parser.add_argument("--csv", action="store_true",
                        help="Write CSV instead of Markdown "
                             "(columns: name, 4-axis, check-in, observation)")
    args = parser.parse_args()

    store = InsightsStore()
    run_id = args.run_id or _pick_run_interactive(store)

    if args.output:
        out_path = args.output
    else:
        run = store.get_run(run_id)
        course = _safe_filename(run.get("course_name", "course"), 30)
        assign = _safe_filename(run.get("assignment_name", "assignment"), 50)
        date   = (run.get("completed_at") or run.get("started_at") or "")[:10]
        suffix = "csv" if args.csv else "md"
        out_path = Path.home() / "Desktop" / f"{course}_{assign}_{date}.{suffix}"

    if args.csv:
        export_run_csv(run_id, out_path)
    else:
        export_run(run_id, out_path)


if __name__ == "__main__":
    main()
