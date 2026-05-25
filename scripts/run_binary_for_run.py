#!/usr/bin/env python3
"""
Run both binary concern classifiers (combined + wellbeing-only) on every
student in a stored Insights run and persist the results to the DB.

Usage:
    python3 scripts/run_binary_for_run.py <run_id> [--tier auto|lightweight|medium]

Reads stored submission texts from insights.db, runs ResearchEngine.run_track_a_only
which now calls detect_concerns(scope="combined") AND detect_concerns(scope="wellbeing")
on each submission, persists each result to coding_record under
'track_a_research' (combined) and 'track_a_research_wb' (wellbeing-only).

Resumes naturally — if a student already has a persisted result, it will be
overwritten by the new run. If you want to skip already-classified students,
filter manually before launching.
"""

import argparse
import sys
import time
from pathlib import Path

_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run binary concern classifiers on a stored run.")
    parser.add_argument("run_id", help="Run ID from insights.db")
    parser.add_argument("--tier", default="auto",
                        help="Model tier: auto, lightweight, medium (default: auto)")
    parser.add_argument("--force", action="store_true",
                        help="Re-run on students who already have persisted results "
                             "(default: skip)")
    args = parser.parse_args()

    from insights.insights_store import InsightsStore
    from research.research_engine import ResearchEngine

    store = InsightsStore()
    run = store.get_run(args.run_id)
    if not run:
        print(f"Run not found: {args.run_id}", file=sys.stderr)
        return 1

    print(f"Course: {run.get('course_name', '?')}")
    print(f"Assignment: {run.get('assignment_name', '?')}")
    print(f"Total submissions: {run.get('total_submissions', '?')}")

    # Pull stored submission texts and student names
    codings = store.get_codings(args.run_id) or []
    if not codings:
        print("No codings found for this run.", file=sys.stderr)
        return 1

    texts = {}
    student_names = {}
    skipped_combined = 0
    skipped_wb = 0
    for c in codings:
        sid = c.get("student_id", "")
        text = c.get("submission_text") or ""
        if not (sid and text):
            continue
        student_names[sid] = c.get("student_name", sid)
        # Skip students who already have BOTH classifiers persisted
        # (force flag overrides this)
        if not args.force:
            raw = c.get("coding_record") or {}
            if isinstance(raw, str):
                import json as _json
                try:
                    raw = _json.loads(raw)
                except Exception:
                    raw = {}
            has_combined = bool(raw.get("track_a_research"))
            has_wb       = bool(raw.get("track_a_research_wb"))
            if has_combined:
                skipped_combined += 1
            if has_wb:
                skipped_wb += 1
            if has_combined and has_wb:
                # Both already done, skip this student entirely
                continue
        texts[sid] = text

    print(f"Students with stored submissions: {len(codings)}")
    if not args.force:
        print(f"Already done — combined: {skipped_combined}, "
              f"wellbeing-only: {skipped_wb}")
    print(f"Students to process: {len(texts)}")
    if not texts:
        print("Nothing to do — all students already classified.")
        return 0

    engine = ResearchEngine(api=None, store=store, settings={
        "insights_keep_awake": True,
        # Use whatever the production pipeline normally uses
    })

    persist_keys = {
        "track_a":    "track_a_research",
        "track_a_wb": "track_a_research_wb",
    }

    counters = {"track_a": 0, "track_a_wb": 0}
    t0 = time.time()

    def on_progress(msg: str) -> None:
        print(f"  · {msg}")

    def on_track_result(track: str, sid: str, data: dict) -> None:
        key = persist_keys.get(track)
        if not key:
            return
        try:
            store.save_track_a_result(args.run_id, sid, data, key=key)
            counters[track] += 1
            elapsed = time.time() - t0
            name = student_names.get(sid, sid)
            flagged = data.get("flagged", "?")
            n_concerns = len(data.get("concerns") or [])
            print(f"  [{counters[track]}/{len(texts)}] {track}: {name} "
                  f"→ flagged={flagged} concerns={n_concerns}  ({elapsed:.0f}s)")
        except Exception as exc:
            print(f"  ERROR persisting {track} for {sid}: {exc}", file=sys.stderr)

    print(f"\nStarting dual binary classifier run "
          f"(combined + wellbeing-only)...\n")

    try:
        engine.run_track_a_only(
            texts=texts,
            student_names=student_names,
            assignment_prompt=run.get("assignment_name", ""),
            model_tier=args.tier,
            progress=on_progress,
            track_cb=on_track_result,
        )
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s "
          f"({elapsed/60:.1f} min). "
          f"Combined: {counters['track_a']}/{len(texts)}, "
          f"Wellbeing-only: {counters['track_a_wb']}/{len(texts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
