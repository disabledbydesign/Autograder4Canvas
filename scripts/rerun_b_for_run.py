#!/usr/bin/env python3
"""
Rerun Track B (4-axis wellbeing + targeted CHECK-IN) for a stored
Insights run using the *upgraded* prompts/classifiers in
`src/insights/submission_coder.py` — the ones that accept an
`assignment_prompt` and include the 5 equity-hardening guards from A2.

This is a paper-side rerun, NOT a production engine run. It does not
write back to insights.db; it writes a CSV in the paper repo's data
directory for downstream A2 vs B-new comparison.

Same 25 students, same model (Gemma 3 12B via MLX), same input passed
to A2 originally (the assignment NAME as a short string). Only B's
prompt and B receiving an `assignment_prompt` slot are changing.

Default behavior: locates the most recent ETHN-1-03 Week 7 self-care
run (run_id with track_a_research_wb persisted) and runs against it.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


# Path to the original anonymized CSV; we use this to recover the
# anon_id ↔ student_id mapping (the export was not in DB row order).
ORIGINAL_ANON_CSV = Path(
    "/Users/june/Documents/GitHub/research/output-format-bias/"
    "data/dual_binary_run_2026-04-27_ETHN1_self_care/self_care_ethn1_anon.csv"
)

# Output CSV (paper repo)
OUTPUT_CSV = Path(
    "/Users/june/Documents/GitHub/research/output-format-bias/"
    "data/dual_binary_run_2026-04-27_ETHN1_self_care/"
    "rerun_2026-04-27_B_hardened_title_only.csv"
)

# Default run target — most-recent ETHN-1-03 Week 7 self-care run with
# track_a_research_wb persisted (verified at script-write time).
DEFAULT_RUN_ID = "a6ca8e5a-662e-436e-8461-3912a13e1534"


def build_anon_mapping(
    db_codings: List[dict],
) -> Dict[str, str]:
    """Map insights student_id → anon_id by matching (word_count, text-prefix)
    against the original anonymized CSV. Returns {student_id: anon_id}.
    """
    if not ORIGINAL_ANON_CSV.exists():
        raise FileNotFoundError(f"Cannot find original anon CSV: {ORIGINAL_ANON_CSV}")

    # Build lookup keyed by (word_count, first 80 chars of text-without-newlines)
    csv_lookup: Dict[Tuple[int, str], str] = {}
    with ORIGINAL_ANON_CSV.open() as f:
        for row in csv.DictReader(f):
            wc = int(row["word_count"])
            prefix = row["submission_text"].replace("\n", " ").replace("\r", " ")[:80]
            csv_lookup[(wc, prefix)] = row["student"]

    mapping: Dict[str, str] = {}
    for c in db_codings:
        sid = c.get("student_id")
        text = c.get("submission_text") or ""
        if not (sid and text):
            continue
        wc = len(text.split())
        prefix = text.replace("\n", " ").replace("\r", " ")[:80]
        anon = csv_lookup.get((wc, prefix))
        if anon is None:
            # Try a looser match — same wc, prefix-of-prefix
            for (cwc, cpref), canon in csv_lookup.items():
                if cwc == wc and cpref[:40] == prefix[:40]:
                    anon = canon
                    break
        if anon is None:
            print(f"  WARNING: no anon match for student_id={sid} wc={wc}", file=sys.stderr)
        else:
            mapping[sid] = anon
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun Track B with hardened prompts.")
    parser.add_argument(
        "--run-id", default=DEFAULT_RUN_ID,
        help=f"Run ID from insights.db (default: {DEFAULT_RUN_ID} — "
             f"the ETHN-1-03 Week 7 self-care run)",
    )
    parser.add_argument(
        "--course-id", default=None,
        help="(unused if --run-id resolves) — informational only",
    )
    parser.add_argument(
        "--assignment-id", default=None,
        help="(unused if --run-id resolves) — informational only",
    )
    parser.add_argument(
        "--output", default=str(OUTPUT_CSV),
        help=f"Output CSV path (default: {OUTPUT_CSV})",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Step 1: load run + stored texts
    # ------------------------------------------------------------------
    from insights.insights_store import InsightsStore

    store = InsightsStore()
    run = store.get_run(args.run_id)
    if not run:
        print(f"Run not found: {args.run_id}", file=sys.stderr)
        return 1

    course_name = run.get("course_name", "?")
    assignment_name = run.get("assignment_name", "?")
    print(f"Course: {course_name}")
    print(f"Assignment: {assignment_name}")
    print(f"Run id: {args.run_id}")

    codings = store.get_codings(args.run_id) or []
    if not codings:
        print("No codings found for this run.", file=sys.stderr)
        return 1

    # Recover anon mapping
    anon_map = build_anon_mapping(codings)
    print(f"Loaded {len(codings)} codings; "
          f"resolved {len(anon_map)}/{len(codings)} anon ids.")

    # Build {student_id: (name, anon_id, submission_text)} for the run
    targets: List[Tuple[str, str, str, str]] = []
    for c in codings:
        sid = c.get("student_id", "")
        text = c.get("submission_text") or ""
        name = c.get("student_name", sid)
        anon = anon_map.get(sid)
        if not (sid and text and anon):
            continue
        targets.append((sid, name, anon, text))

    # Sort by anon id (numeric) so progress prints in 1..25 order
    targets.sort(key=lambda t: int(t[2]))
    print(f"Students to process: {len(targets)}")

    # ------------------------------------------------------------------
    # Step 2: initialize MLX backend (Gemma 3 12B), require it
    # ------------------------------------------------------------------
    from insights.llm_backend import auto_detect_backend, unload_mlx_model
    from insights.submission_coder import classify_wellbeing, classify_checkin
    from dataclasses import replace as _dc_replace

    settings = {
        "insights_llm_backend": "mlx",
        "insights_mlx_model": "mlx-community/gemma-3-12b-it-4bit",
    }
    backend = auto_detect_backend(tier="lightweight", settings=settings)
    if backend is None:
        print("ERROR: no LLM backend available.", file=sys.stderr)
        return 2
    if backend.name != "mlx":
        print(f"ERROR: expected MLX backend, got '{backend.name}'. "
              f"Aborting to control for model.", file=sys.stderr)
        return 2
    print(f"Backend: {backend.name} model={backend.model}")

    # Mirror research_engine.py — CHECK-IN runs at temperature 0.3
    checkin_backend = _dc_replace(backend, temperature=0.3)

    # ------------------------------------------------------------------
    # Step 3: run B (wellbeing + conditional CHECK-IN) on each student
    # ------------------------------------------------------------------
    results: List[dict] = []
    t0 = time.time()
    n = len(targets)

    for i, (sid, name, anon, text) in enumerate(targets, 1):
        elapsed = time.time() - t0
        print(f"\n[{i}/{n}] anon={anon} ({name}) — wellbeing... "
              f"({elapsed:.0f}s elapsed)")
        try:
            wb = classify_wellbeing(
                backend,
                student_name=name,
                submission_text=text,
                assignment_prompt=assignment_name,
            )
        except Exception as exc:
            print(f"  ERROR wellbeing: {exc}", file=sys.stderr)
            wb = {"axis": "NONE", "signal": f"Error: {exc}",
                  "confidence": 0.0, "prescan_signals": []}

        axis = wb.get("axis", "NONE")
        ci_flag: Optional[bool] = None
        ci_reasoning = ""
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
                ci_reasoning = ci.get("reasoning", "")
            except Exception as exc:
                print(f"  ERROR check-in: {exc}", file=sys.stderr)

        print(f"  axis={axis} conf={wb.get('confidence', 0.0):.2f} "
              f"check_in={ci_flag}")

        results.append({
            "student": anon,
            "track_b_axis_new": axis,
            "track_b_signal_new": wb.get("signal", ""),
            "track_b_confidence_new": wb.get("confidence", 0.0),
            "track_b_checkin_flag_new": (
                "" if ci_flag is None else ("TRUE" if ci_flag else "FALSE")
            ),
            "track_b_checkin_reasoning_new": ci_reasoning,
        })

        # Mild throttle to avoid pinning the GPU
        time.sleep(0.5)

    # Unload the MLX model when done
    try:
        unload_mlx_model()
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Step 4: write output CSV (sorted by numeric anon)
    # ------------------------------------------------------------------
    results.sort(key=lambda r: int(r["student"]))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "student", "track_b_axis_new", "track_b_signal_new",
        "track_b_confidence_new", "track_b_checkin_flag_new",
        "track_b_checkin_reasoning_new",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow(r)

    elapsed = time.time() - t0
    print(f"\nWrote {len(results)} rows to {out_path}")
    print(f"Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
