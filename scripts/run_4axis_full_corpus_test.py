#!/usr/bin/env python3
"""Run the 4-axis wellbeing classifier on the full combined corpus.

Written 2026-05-11 for the output-format-bias paper (May 20 hard deadline).
Amended 2026-05-11 to support BOTH single-pass (Test N inline) and two-pass
(production classify_wellbeing) variants in a single invocation.

Context. The paper compares four architectures on the same corpus:
  - Minimal binary (Tests B/C/F)
  - Calibrated binary (Test M / Test R)
  - 4-axis classification (Test N family)
  - Generative observation (Test G / Variant A)

All existing Test N runs only cover 7-8 ES students + the 14 WB synthetic
cases. For the paper's comparison to be rigorous on the same scope, the
4-axis classifier needs evaluation on the FULL 32-student ethnic-studies
corpus + the 14 wellbeing-signal cases = 46 students.

SINGLE-PASS vs. TWO-PASS — both are findings
--------------------------------------------
Two paths in the codebase produce CRISIS/BURNOUT/ENGAGED/NONE labels:

  (1) Single-pass — test_n_four_axis_submissions in run_alt_hypothesis_tests.py.
      One LLM call. Uses inline FOUR_AXIS_SUBMISSION_SYSTEM (line 2315) and
      FOUR_AXIS_SUBMISSION_PROMPT (line 2377). Direct invocation via the
      module's `send` wrapper, which calls insights.llm_backend.send_text.
      This extends the paper's existing Row 3 evidence (Test N) to the full
      46-student corpus.

  (2) Two-pass — insights.submission_coder.classify_wellbeing (line 1009).
      Pass 0 LLM pre-scan finds personal-circumstance sentences across the
      full submission; Pass 1 classifier sees those sentences foregrounded
      via a signal_prefix. Uses WELLBEING_CLASSIFIER_SYSTEM /
      WELLBEING_CLASSIFIER_PROMPT from insights.prompts. This is what
      engine.py calls in the live pipeline.

The DIFFERENCE between (1) and (2) on the same corpus is itself a paper
finding: it isolates the contribution of the prescan-signal-prefix
mechanism, holding the corpus and 4-axis schema constant.

This script does NOT modify run_alt_hypothesis_tests.py — it imports the
single-pass prompts verbatim so the comparison is grounded in identical
prompt text.

Usage
-----
    cd /Users/june/Documents/GitHub/Autograder4Canvas

    # Both variants (default), full 46-student corpus, 5 runs each:
    python scripts/run_4axis_full_corpus_test.py

    # Single-pass only:
    python scripts/run_4axis_full_corpus_test.py --variant single-pass

    # Two-pass only:
    python scripts/run_4axis_full_corpus_test.py --variant two-pass

    # Smoke test (2 students total per variant, 1 run):
    python scripts/run_4axis_full_corpus_test.py --smoke

Estimated runtime: ~5 hours per variant on Gemma 12B MLX for the full run.
No time cutoffs are imposed.

Outputs (under --variant both, both files are written)
------------------------------------------------------
    /Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs/
      test_n_4axis_SINGLE_PASS_FULL_CORPUS_gemma12b_<YYYY-MM-DD_HHMM>.json
      test_n_4axis_TWO_PASS_FULL_CORPUS_gemma12b_<YYYY-MM-DD_HHMM>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import subprocess
from dataclasses import replace
from datetime import datetime
from pathlib import Path

# Path setup — match run_alt_hypothesis_tests.py conventions.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# Backend + production two-pass entry point.
from insights.llm_backend import BackendConfig, send_text, unload_mlx_model  # noqa: E402
from insights.submission_coder import classify_wellbeing  # noqa: E402

# Single-pass entry point — import the Test N inline prompts verbatim from
# run_alt_hypothesis_tests.py so the comparison is grounded in identical text.
# Source: run_alt_hypothesis_tests.py
#   FOUR_AXIS_SUBMISSION_SYSTEM defined at line 2315
#   FOUR_AXIS_SUBMISSION_PROMPT defined at line 2377
# Also reuse WELLBEING_SIGNAL_CASES rather than duplicating 300+ lines.
from run_alt_hypothesis_tests import (  # noqa: E402
    FOUR_AXIS_SUBMISSION_SYSTEM,
    FOUR_AXIS_SUBMISSION_PROMPT,
    WELLBEING_SIGNAL_CASES,
)

# Paths
CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
OUTPUT_DIR = Path(
    "/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs"
)

# Model config — Gemma 12B MLX, temperature 0.1 (matches Tests B/C/F/M/N/R).
MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 300,
        "temperature": 0.1,
    },
}

# Assignment prompt placeholder. The synthetic corpus is built around a single
# Week-6 intersectionality discussion, consistent with Test R conventions.
ASSIGNMENT_PROMPT_TEXT = "Week 6 Discussion: Intersectionality in Practice"

# Single-pass token limit — mirrors Test N's invocation at
# run_alt_hypothesis_tests.py line 2436 / 2478 (max_tokens=150).
SINGLE_PASS_MAX_TOKENS = 150

VARIANT_CHOICES = ("single-pass", "two-pass", "both")

log = logging.getLogger("run_4axis_full_corpus_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_es_corpus() -> list[dict]:
    """Load the 32-student ethnic-studies corpus as a list of dicts."""
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Corpus not found at {CORPUS_PATH}")
    return json.loads(CORPUS_PATH.read_text())


def get_backend(model_key: str = "gemma12b") -> BackendConfig:
    cfg = MODELS[model_key]
    return BackendConfig(
        name=cfg["name"],
        model=cfg["model"],
        max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
    )


def expected_axis_for_wb_case(case: dict) -> str:
    """Map WELLBEING_SIGNAL_CASES signal_type to expected 4-axis label.

    Matches the mapping inside test_n_four_axis_submissions (line 2469 of
    run_alt_hypothesis_tests.py): control_* → ENGAGED, burnout_* → BURNOUT,
    everything else → CRISIS.
    """
    st = case["signal_type"]
    if st.startswith("control"):
        return "ENGAGED"
    if "burnout" in st:
        return "BURNOUT"
    return "CRISIS"


def git_provenance() -> dict:
    """Capture git state for reproducibility."""
    prov: dict = {}
    try:
        prov["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
        prov["git_commit_short"] = prov["git_commit"][:8]
        prov["git_dirty"] = bool(subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True, timeout=5, cwd=str(ROOT),
        ).returncode)
        prov["git_branch"] = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = None
        prov["git_branch"] = "unknown"
    return prov


def save_results(
    results: list,
    *,
    variant: str,  # "single-pass" or "two-pass"
    model_key: str,
    n_runs: int,
    smoke: bool,
    es_count: int,
    wb_count: int,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    time_tag = datetime.now().strftime("%H%M")
    suffix = "_SMOKE" if smoke else ""

    if variant == "single-pass":
        filename = (
            f"test_n_4axis_SINGLE_PASS_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_single_pass_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification (CRISIS/BURNOUT/"
            "ENGAGED/NONE) using the SINGLE-PASS inline prompts from "
            "test_n_four_axis_submissions in run_alt_hypothesis_tests.py "
            "(FOUR_AXIS_SUBMISSION_SYSTEM line 2315, "
            "FOUR_AXIS_SUBMISSION_PROMPT line 2377). One LLM call per "
            "submission, no prescan-signal-prefix. Extends the paper's "
            "existing Row 3 evidence (Test N) to the full 46-student corpus."
        )
        classifier_entry_point = (
            "run_alt_hypothesis_tests.FOUR_AXIS_SUBMISSION_SYSTEM/PROMPT via "
            "insights.llm_backend.send_text "
            "(single-pass; no prescan-signal-prefix)"
        )
    elif variant == "two-pass":
        filename = (
            f"test_n_4axis_TWO_PASS_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{suffix}.json"
        )
        test_name = "test_n_4axis_two_pass_full_corpus"
        description = (
            "Full-corpus 4-axis wellbeing classification (CRISIS/BURNOUT/"
            "ENGAGED/NONE) using the production TWO-PASS pipeline "
            "(insights.submission_coder.classify_wellbeing): Pass 0 LLM "
            "prescan flags personal-circumstance sentences; Pass 1 "
            "classifier sees those sentences foregrounded via a "
            "signal_prefix. Reads WELLBEING_CLASSIFIER_SYSTEM/PROMPT from "
            "insights.prompts. Tests the deployed production configuration."
        )
        classifier_entry_point = (
            "insights.submission_coder.classify_wellbeing "
            "(two-pass: prescan + classifier; reads WELLBEING_CLASSIFIER_SYSTEM "
            "and WELLBEING_CLASSIFIER_PROMPT from insights.prompts)"
        )
    else:
        raise ValueError(f"Unknown variant: {variant}")

    output = {
        "test_name": test_name,
        "description": description,
        "classifier_variant": variant,
        "classifier_entry_point": classifier_entry_point,
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies + wellbeing_synthetic",
        "corpus_path": str(CORPUS_PATH),
        "n_runs_per_student": n_runs,
        "n_es_students": es_count,
        "n_wb_cases": wb_count,
        "n_students_total": es_count + wb_count,
        "smoke": smoke,
        "assignment_prompt": ASSIGNMENT_PROMPT_TEXT,
        "provenance": git_provenance(),
        "results": results,
    }
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# Single-pass invocation (Test N inline prompts)
# ---------------------------------------------------------------------------

def _parse_single_pass_output(raw_output: str) -> tuple[str, float]:
    """Parse axis + confidence from the single-pass JSON-ish output.

    Mirrors the parsing used inside test_n_four_axis_submissions
    (run_alt_hypothesis_tests.py lines 2441-2444 / 2481-2484).
    """
    import re as _re
    axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', raw_output or "")
    axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
    conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', raw_output or "")
    confidence = float(conf_match.group(1)) if conf_match else 0.0
    return axis, confidence


def run_one_single_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """One single-pass invocation: builds Test N's inline prompt and calls
    send_text directly (the same path test_n_four_axis_submissions uses).
    """
    prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
        student_name=student_name,
        submission_text=submission_text,
    )
    t0 = time.time()
    try:
        raw_output = send_text(
            backend,
            prompt,
            FOUR_AXIS_SUBMISSION_SYSTEM,
            max_tokens=SINGLE_PASS_MAX_TOKENS,
        )
        elapsed = round(time.time() - t0, 1)
        axis, confidence = _parse_single_pass_output(raw_output)
        signal = ""  # single-pass schema doesn't separate signal description
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        raw_output = ""
        axis = "ERROR"
        confidence = 0.0
        signal = ""
        error = str(exc)
        log.exception("single-pass send_text failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_submissions",
        "classifier_variant": "single-pass",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "signal": signal,
        "prescan_signals": None,  # single-pass does not run a prescan
        "correct": correct,
        "submission_text": submission_text,
        "prompt": prompt,
        "system_prompt": FOUR_AXIS_SUBMISSION_SYSTEM,
        "raw_output": raw_output,
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Two-pass invocation (production classify_wellbeing)
# ---------------------------------------------------------------------------

def run_one_two_pass(
    backend: BackendConfig,
    student_id: str,
    student_name: str,
    submission_text: str,
    *,
    source: str,
    expected_axis: str | None,
    pattern: str | None,
    signal_type: str | None,
    run_idx: int,
) -> dict:
    """Run classify_wellbeing once and package the result."""
    t0 = time.time()
    try:
        wb = classify_wellbeing(
            backend,
            student_name,
            submission_text,
            assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
        )
        elapsed = round(time.time() - t0, 1)
        axis = wb.get("axis", "NONE")
        signal = wb.get("signal", "")
        confidence = float(wb.get("confidence", 0.0))
        prescan_signals = wb.get("prescan_signals", []) or []
        error = None
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.time() - t0, 1)
        axis = "ERROR"
        signal = ""
        confidence = 0.0
        prescan_signals = []
        error = str(exc)
        log.exception("classify_wellbeing failed for %s: %s", student_id, exc)

    correct = "N/A"
    if expected_axis is not None and axis not in ("ERROR", "PARSE_ERROR"):
        correct = "OK" if axis == expected_axis else "MISMATCH"

    return {
        "codepath": "test_harness_4axis_submissions",
        "classifier_variant": "two-pass",
        "source": source,
        "run": run_idx,
        "student_id": student_id,
        "student_name": student_name,
        "pattern": pattern,
        "signal_type": signal_type,
        "expected_axis": expected_axis,
        "actual_axis": axis,
        "confidence": confidence,
        "signal": signal,
        "prescan_signals": prescan_signals,
        "correct": correct,
        "submission_text": submission_text,
        "raw_output": {
            "axis": axis,
            "signal": signal,
            "confidence": confidence,
            "prescan_signals": prescan_signals,
        },
        "time_seconds": elapsed,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Per-variant driver
# ---------------------------------------------------------------------------

def run_variant(
    variant: str,
    *,
    backend: BackendConfig,
    es_corpus: list[dict],
    wb_cases: list[dict],
    model_key: str,
    n_runs: int,
    smoke: bool,
) -> Path:
    """Run ONE classifier variant across the full corpus, save its JSON."""
    if variant == "single-pass":
        run_one = run_one_single_pass
    elif variant == "two-pass":
        run_one = run_one_two_pass
    else:
        raise ValueError(f"Unknown variant: {variant}")

    print(f"\n{'=' * 70}")
    print(f"  4-AXIS FULL-CORPUS TEST — VARIANT: {variant.upper()}  "
          f"({'SMOKE' if smoke else 'FULL'})")
    print(f"  Model: {model_key}  |  Runs per student: {n_runs}")
    if variant == "single-pass":
        print(f"  Classifier: Test N inline prompts via "
              f"insights.llm_backend.send_text")
    else:
        print(f"  Classifier: insights.submission_coder.classify_wellbeing")
    print(f"{'=' * 70}\n")

    results: list = []
    total_students = len(es_corpus) + len(wb_cases)
    total_runs = total_students * n_runs
    print(f"  ES students: {len(es_corpus)}  |  WB cases: {len(wb_cases)}  "
          f"|  Total LLM sessions ({variant}): {total_runs}\n")

    call_idx = 0

    # --- Ethnic-studies corpus ---
    for run_idx in range(1, n_runs + 1):
        print(f"  --- Run {run_idx}/{n_runs} (ethnic_studies, {variant}) ---")
        for student in es_corpus:
            call_idx += 1
            sid = student["student_id"]
            name = student["student_name"]
            text = student["text"]
            pattern = student.get("pattern")
            rec = run_one(
                backend,
                student_id=sid,
                student_name=name,
                submission_text=text,
                source="ethnic_studies",
                expected_axis=None,
                pattern=pattern,
                signal_type=None,
                run_idx=run_idx,
            )
            results.append(rec)
            print(
                f"    [{call_idx:4d}/{total_runs}] {sid} {name:24s} "
                f"axis={rec['actual_axis']:8s} conf={rec['confidence']:.2f} "
                f"({rec['time_seconds']}s)"
                + (f"  ERROR: {rec['error']}" if rec['error'] else "")
            )

    # --- Wellbeing synthetic cases ---
    for run_idx in range(1, n_runs + 1):
        print(f"\n  --- Run {run_idx}/{n_runs} (wellbeing_synthetic, {variant}) ---")
        for case in wb_cases:
            call_idx += 1
            expected = expected_axis_for_wb_case(case)
            rec = run_one(
                backend,
                student_id=case["id"],
                student_name=case["name"],
                submission_text=case["text"],
                source="wellbeing_synthetic",
                expected_axis=expected,
                pattern=None,
                signal_type=case["signal_type"],
                run_idx=run_idx,
            )
            results.append(rec)
            print(
                f"    [{call_idx:4d}/{total_runs}] {case['id']:5s} "
                f"{case['name']:22s} {case['signal_type']:30s} "
                f"expect={expected:8s} got={rec['actual_axis']:8s} "
                f"conf={rec['confidence']:.2f} [{rec['correct']}] "
                f"({rec['time_seconds']}s)"
                + (f"  ERROR: {rec['error']}" if rec['error'] else "")
            )

    path = save_results(
        results,
        variant=variant,
        model_key=model_key,
        n_runs=n_runs,
        smoke=smoke,
        es_count=len(es_corpus),
        wb_count=len(wb_cases),
    )
    print(f"\n  Results saved ({variant}): {path}")

    # Quick summary: WB hit rate per case across runs.
    print(f"\n  WB summary ({variant}, axis match across runs):")
    wb_results = [r for r in results if r["source"] == "wellbeing_synthetic"]
    by_case: dict[str, list[dict]] = {}
    for r in wb_results:
        by_case.setdefault(r["student_id"], []).append(r)
    for cid in sorted(by_case):
        recs = by_case[cid]
        expected = recs[0]["expected_axis"]
        matches = sum(1 for r in recs if r["actual_axis"] == expected)
        name = recs[0]["student_name"]
        st = recs[0]["signal_type"]
        print(
            f"    {cid} {name:22s} {st:30s} "
            f"expect={expected:8s}  match={matches}/{len(recs)}"
        )

    # ES corpus axis distribution.
    print(f"\n  ES axis distribution ({variant}, "
          f"n={len(es_corpus)} students x {n_runs} runs):")
    es_results = [r for r in results if r["source"] == "ethnic_studies"]
    from collections import Counter
    dist = Counter(r["actual_axis"] for r in es_results)
    for axis, count in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"    {axis:12s} {count}")

    return path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_full(model_key: str, n_runs: int, smoke: bool, variant: str) -> list[Path]:
    backend = get_backend(model_key)
    backend = replace(backend, temperature=MODELS[model_key]["temperature"])

    es_corpus = load_es_corpus()
    wb_cases = list(WELLBEING_SIGNAL_CASES)

    if smoke:
        es_corpus = es_corpus[:1]
        wb_cases = wb_cases[:1]
        n_runs = 1

    if variant == "both":
        variants_to_run = ["single-pass", "two-pass"]
    else:
        variants_to_run = [variant]

    paths: list[Path] = []
    for v in variants_to_run:
        path = run_variant(
            v,
            backend=backend,
            es_corpus=es_corpus,
            wb_cases=wb_cases,
            model_key=model_key,
            n_runs=n_runs,
            smoke=smoke,
        )
        paths.append(path)

    print(f"\n{'=' * 70}")
    print(f"  ALL VARIANTS COMPLETE")
    for p in paths:
        print(f"    {p}")
    print(f"{'=' * 70}\n")
    return paths


def _metal_warmup(model_key: str = "gemma12b") -> None:
    """Fire a short inference to initialize Metal before the main run.

    Prevents Metal kernel-compilation stalls on cold starts (especially after
    display sleep). Skipped in smoke mode — smoke runs are short enough that
    warmup adds proportionally too much overhead.
    """
    print("\n  [Metal warmup] Initializing GPU...")
    t0 = time.time()
    try:
        backend = get_backend(model_key)
        backend = replace(backend, temperature=0.1, max_tokens=8)
        send_text(backend, "Hi", "You are a test.")
        # Do NOT unload here — leave model cached so first real inference
        # reuses it directly.
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)\n")
    except Exception as e:  # noqa: BLE001
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run 4-axis wellbeing classifier on the full 32 ES + "
                    "14 WB combined corpus. Supports single-pass (Test N "
                    "inline prompts), two-pass (production "
                    "classify_wellbeing), or both."
    )
    parser.add_argument(
        "--variant",
        choices=list(VARIANT_CHOICES),
        default="both",
        help="Classifier variant to run. 'single-pass' = Test N inline "
             "prompts; 'two-pass' = production classify_wellbeing; "
             "'both' = run single-pass then two-pass sequentially "
             "and write two separate JSON files. Default: both.",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Smoke-test: 1 ES student + 1 WB case, 1 run each, per variant.",
    )
    parser.add_argument(
        "--model", default="gemma12b",
        choices=list(MODELS.keys()),
        help="Model key. Default: gemma12b.",
    )
    parser.add_argument(
        "--n-runs", type=int, default=5,
        help="Runs per student for the full run (ignored under --smoke). "
             "Default: 5.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        if not args.smoke:
            _metal_warmup(args.model)
        run_full(
            model_key=args.model,
            n_runs=args.n_runs,
            smoke=args.smoke,
            variant=args.variant,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    except Exception as exc:  # noqa: BLE001
        log.exception("Run failed: %s", exc)
        return 2
    finally:
        try:
            unload_mlx_model()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
