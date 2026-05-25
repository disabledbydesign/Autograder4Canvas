#!/usr/bin/env python3
"""
Multi-assignment rerun of Track B with the *upgraded* hardened prompts
and the new `assignment_prompt` input. Sequences through a list of
run_ids, processes each with the same model (Gemma 3 12B / MLX), and
writes one CSV per run to ~/Documents/Canvas Grading/research_output_2026-04-27/.

Output is a per-run CSV with columns:
  student_id, student_name, word_count, assignment_name, run_id,
  track_b_axis_new, track_b_signal_new, track_b_confidence_new,
  track_b_checkin_flag_new, track_b_checkin_reasoning_new,
  submission_text_first_200

Sequenced because MLX is single-tenant. Total runtime ≈ 15 sec/student
after first model load (first call adds ~30 sec).
"""

import csv
import sys
import time
from dataclasses import replace as _dc_replace
from pathlib import Path
from typing import Optional

_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


# Output directory inside autograder's standard data location
OUTPUT_DIR = Path.home() / "Documents" / "Canvas Grading" / "research_output_2026-04-27"

# Hardcoded run list with rationale (set at script-write time):
#   1. Week 5 T&Q Journal (course 44853, n=19) — apples-to-apples with
#      the already-exported old-B Week 5 CSV in the paper repo.
#   2. Week 2 Discussion: Racial Formation in Action (course 44106, n=31)
#      — same course as Week 7 self-care, different topic, discussion
#      forum format. Tests new-B on a non-burnout discussion forum.
#   3. Native Space - Discussion Forum (course 44673, n=41) — different
#      course (Native American Studies), different topic, larger n.
RUN_IDS = [
    "ab9136d6-...",  # Week 5 T&Q Journal — placeholder, real id substituted at runtime
    "a4958bc6-...",  # Week 2 Discussion: Racial Formation in Action
    "50e953f7-...",  # Native Space - Discussion Forum
]

# Real run IDs (resolved from get_runs lookup)
RUN_TARGETS = [
    {"run_id_prefix": "ab9136d6", "label": "Week 5 T&Q Journal (44853)"},
    {"run_id_prefix": "a4958bc6", "label": "Week 2 Discussion Racial Formation (44106)"},
    {"run_id_prefix": "50e953f7", "label": "Native Space Discussion Forum (44673)"},
    {"run_id_prefix": "371c322a", "label": "Week 7 T&Q Journal (ETHN-1-02, 44853)"},
]


def safe_assignment_filename(name: str) -> str:
    """Make assignment_name filesystem-safe."""
    return (
        name.replace("/", "-")
            .replace(":", "")
            .replace("?", "")
            .replace("*", "")
            .replace("&", "and")
            .replace(" ", "_")
            [:80]
    )


def find_full_run_id(store, prefix: str) -> Optional[str]:
    """Resolve a short run_id prefix to the full uuid."""
    for r in store.get_runs():
        rid = r.get("run_id", "")
        if rid.startswith(prefix) and r.get("completed_at"):
            return rid
    return None


def process_run(store, backend, checkin_backend, run_id: str, output_dir: Path) -> dict:
    """Run hardened B on every student in this run; write a CSV."""
    from insights.submission_coder import classify_wellbeing, classify_checkin

    run = store.get_run(run_id)
    course_name = run.get("course_name", "?")
    assignment_name = run.get("assignment_name", "?")
    print(f"\n{'=' * 70}")
    print(f"RUN {run_id[:8]} — {course_name} / {assignment_name}")
    print(f"{'=' * 70}")

    codings = store.get_codings(run_id) or []
    targets = []
    for c in codings:
        sid = c.get("student_id", "")
        text = c.get("submission_text") or ""
        name = c.get("student_name", sid)
        if sid and text:
            targets.append((sid, name, text))
    print(f"Students: {len(targets)}")

    results = []
    t0 = time.time()
    for i, (sid, name, text) in enumerate(targets, 1):
        elapsed = time.time() - t0
        print(f"\n[{i}/{len(targets)}] {sid} ({name}) ({elapsed:.0f}s)")
        try:
            wb = classify_wellbeing(
                backend,
                student_name=name,
                submission_text=text,
                assignment_prompt=assignment_name,
            )
        except Exception as exc:
            print(f"  ERROR wellbeing: {exc}", file=sys.stderr)
            wb = {"axis": "NONE", "signal": f"Error: {exc}", "confidence": 0.0}

        axis = wb.get("axis", "NONE")
        ci_flag = None
        ci_reason = ""
        if axis == "ENGAGED":
            print(f"  → ENGAGED, running CHECK-IN...")
            try:
                ci = classify_checkin(
                    checkin_backend,
                    student_name=name,
                    submission_text=text,
                    assignment_prompt=assignment_name,
                )
                ci_flag = bool(ci.get("check_in", False))
                ci_reason = ci.get("reasoning", "")
            except Exception as exc:
                print(f"  ERROR check-in: {exc}", file=sys.stderr)

        print(f"  axis={axis} conf={wb.get('confidence', 0.0):.2f} check_in={ci_flag}")

        results.append({
            "student_id": sid,
            "student_name": name,
            "word_count": len(text.split()),
            "assignment_name": assignment_name,
            "run_id": run_id,
            "track_b_axis_new": axis,
            "track_b_signal_new": wb.get("signal", ""),
            "track_b_confidence_new": wb.get("confidence", 0.0),
            "track_b_checkin_flag_new": (
                "" if ci_flag is None else ("TRUE" if ci_flag else "FALSE")
            ),
            "track_b_checkin_reasoning_new": ci_reason,
            "submission_text_first_200": text[:200].replace("\n", " "),
        })
        time.sleep(0.3)

    # Write CSV
    safe = safe_assignment_filename(assignment_name)
    out_path = output_dir / f"new_B_{run_id[:8]}_{safe}.csv"
    fieldnames = list(results[0].keys()) if results else [
        "student_id", "student_name", "word_count", "assignment_name", "run_id",
        "track_b_axis_new", "track_b_signal_new", "track_b_confidence_new",
        "track_b_checkin_flag_new", "track_b_checkin_reasoning_new",
        "submission_text_first_200",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow(r)

    elapsed = time.time() - t0
    print(f"\nWrote {len(results)} rows to {out_path}")
    print(f"Run elapsed: {elapsed:.0f}s ({elapsed / 60:.1f} min)")

    # Headline counts
    from collections import Counter
    axes = Counter(r["track_b_axis_new"] for r in results)
    checkins = sum(1 for r in results if r["track_b_checkin_flag_new"] == "TRUE")
    print(f"B axis: {dict(axes)}  CHECK-IN: {checkins}")

    return {
        "run_id": run_id,
        "assignment_name": assignment_name,
        "course_name": course_name,
        "n": len(results),
        "axes": dict(axes),
        "checkins": checkins,
        "elapsed_sec": elapsed,
        "output_csv": str(out_path),
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from insights.insights_store import InsightsStore
    from insights.llm_backend import auto_detect_backend, unload_mlx_model

    store = InsightsStore()

    # Resolve run targets
    resolved = []
    for tgt in RUN_TARGETS:
        rid = find_full_run_id(store, tgt["run_id_prefix"])
        if rid is None:
            print(f"WARNING: could not resolve {tgt['run_id_prefix']} ({tgt['label']})",
                  file=sys.stderr)
            continue
        resolved.append((rid, tgt["label"]))
        print(f"Resolved: {tgt['run_id_prefix']} → {rid[:8]} ({tgt['label']})")

    if not resolved:
        print("No runs resolved.", file=sys.stderr)
        return 1

    # Initialize MLX backend (once for all runs)
    settings = {
        "insights_llm_backend": "mlx",
        "insights_mlx_model": "mlx-community/gemma-3-12b-it-4bit",
    }
    backend = auto_detect_backend(tier="lightweight", settings=settings)
    if backend is None or backend.name != "mlx":
        print(f"ERROR: backend={backend}", file=sys.stderr)
        return 2
    print(f"Backend: {backend.name} model={backend.model}")
    checkin_backend = _dc_replace(backend, temperature=0.3)

    # Sequence through runs
    summaries = []
    t_total = time.time()
    for rid, label in resolved:
        try:
            summary = process_run(store, backend, checkin_backend, rid, OUTPUT_DIR)
            summaries.append(summary)
        except Exception as exc:
            print(f"ERROR processing {label}: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    try:
        unload_mlx_model()
    except Exception:
        pass

    total_elapsed = time.time() - t_total
    print(f"\n{'=' * 70}")
    print(f"ALL RUNS COMPLETE — total {total_elapsed / 60:.1f} min")
    print(f"{'=' * 70}")
    for s in summaries:
        print(f"  {s['assignment_name']} (n={s['n']}, {s['elapsed_sec']:.0f}s): "
              f"axes={s['axes']} checkins={s['checkins']}")
        print(f"    → {s['output_csv']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
