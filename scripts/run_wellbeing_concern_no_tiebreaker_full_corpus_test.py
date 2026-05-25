"""Binary classifier WITHOUT the tiebreaker paragraph — full 46-student corpus.

Variant of run_wellbeing_concern_full_corpus_test.py that swaps in
WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER (WELLBEING_CONCERN_PROMPT with the
"When uncertain, default to NOT flagging…" paragraph stripped). Same model,
same temperature, same 46-student corpus (32 ES + 14 WB), same production
post-processing (anti-bias regex + 0.7 threshold). Output schema matches
Test R so downstream comparison code does not need to branch.

This closes the gap exposed during the 2026-05-12 audit: the prior
"binary-no-tiebreaker" runs in run_4axis_full_corpus_test.py were 4-axis
runs mislabeled as binary (they stripped the tiebreaker from
WELLBEING_CLASSIFIER_SYSTEM, which is itself a 4-axis classifier — not
the production binary). This script is the REAL binary-no-tiebreaker
variant and the proper comparison companion to Test R.

How to run.
    cd /Users/june/Documents/GitHub/Autograder4Canvas
    python scripts/run_wellbeing_concern_no_tiebreaker_full_corpus_test.py
    python scripts/run_wellbeing_concern_no_tiebreaker_full_corpus_test.py --smoke

Output. JSON at
data/raw_outputs/test_binary_concern_no_tiebreaker_FULL_CORPUS_gemma12b_<date>_<time>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from insights.llm_backend import BackendConfig, send_text, unload_mlx_model  # noqa: E402
from insights.models import ConcernRecord  # noqa: E402
from insights.prompts import SYSTEM_PROMPT  # noqa: E402
from research.concern_detector import _check_bias_in_output  # noqa: E402
from research.prompts import WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER  # noqa: E402

# Reuse the canonical corpus and case lists from the Test R script — keeps a
# single source of truth for the 46-student corpus and the WELLBEING_SIGNAL_CASES
# fixture. If that file moves, this import will fail loud.
from run_wellbeing_concern_full_corpus_test import (  # noqa: E402
    ASSIGNMENT_PROMPT_TEXT,
    CLASS_CONTEXT_TEXT,
    CORPUS_PATH,
    ES_FLAG_IDS,
    MODELS,
    PRODUCTION_CONFIDENCE_THRESHOLD,
    PROFILE_FRAGMENT_TEXT,
    SIGNAL_MATRIX_TEXT,
    WELLBEING_SIGNAL_CASES,
    apply_production_postprocessing,
    build_es_cases,
    build_wb_cases,
    get_backend,
    git_provenance,
    load_corpus,
    parse_concern_result,
)

OUTPUT_DIR = Path("/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs")

log = logging.getLogger(__name__)


def save_results(
    results: list,
    model_key: str,
    n_runs: int,
    n_students: int,
    smoke: bool,
    path: Path | None = None,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    if path is None:
        time_tag = datetime.now().strftime("%H%M")
        smoke_tag = "_SMOKE" if smoke else ""
        filename = (
            f"test_binary_concern_no_tiebreaker_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{smoke_tag}.json"
        )
        path = OUTPUT_DIR / filename
    output = {
        "test_name": "test_binary_concern_no_tiebreaker_full_corpus",
        "n_results_so_far": len(results),
        "description": (
            "WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER — production binary "
            "wellbeing-concern prompt with the 'When uncertain, default to "
            "NOT flagging' paragraph stripped. Tested on the full 46-student "
            "corpus (32 ES + 14 WB). Closes the binary-no-tiebreaker gap "
            "exposed in the 2026-05-12 audit: the prior 'binary-no-tiebreaker' "
            "runs were 4-axis runs on WELLBEING_CLASSIFIER_SYSTEM, not the "
            "production binary concern detector. This is the REAL "
            "binary-no-tiebreaker variant. Apples-to-apples comparison "
            "companion to test_r_wellbeing_concern_full_corpus."
        ),
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies + wellbeing_signal_cases",
        "corpus_path": str(CORPUS_PATH),
        "n_runs_per_student": n_runs,
        "n_students_tested": n_students,
        "assignment_prompt": ASSIGNMENT_PROMPT_TEXT,
        "class_context": CLASS_CONTEXT_TEXT
        or "(empty — class context was not injected into binary tracks)",
        "signal_matrix_result": SIGNAL_MATRIX_TEXT,
        "provenance": git_provenance(),
        "results": results,
    }
    path.write_text(json.dumps(output, indent=2, default=str))
    return path


def run_test(
    model_key: str = "gemma12b",
    n_runs: int = 5,
    smoke: bool = False,
) -> Path:
    print(f"\n{'=' * 60}")
    print(f"  BINARY (NO TIEBREAKER) — FULL CORPUS")
    print(f"  Prompt: WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER")
    print(f"  Scope: 32 ES (S001-S032) + 14 WB (WB01-WB14) = 46 students")
    if smoke:
        print(f"  SMOKE MODE: 2 students (1 ES + 1 WB) x 1 run")
    print(f"  Model: {model_key} | Runs per student: {n_runs}")
    print(f"{'=' * 60}\n")

    corpus = load_corpus()
    backend = get_backend(model_key)
    backend = replace(backend, temperature=0.1)

    es_cases = build_es_cases(corpus)
    wb_cases = build_wb_cases()

    if smoke:
        es_smoke = [c for c in es_cases if c[0] == "S002"] or es_cases[:1]
        wb_smoke = [c for c in wb_cases if c[0] == "WB01"] or wb_cases[:1]
        es_cases = es_smoke[:1]
        wb_cases = wb_smoke[:1]
        n_runs = 1

    all_cases: list[tuple[str, str, str, str, str, str]] = []
    for sid, name, text, pattern, expected in es_cases:
        all_cases.append((sid, name, text, pattern, expected, "ES"))
    for cid, name, text, sig_type, expected in wb_cases:
        all_cases.append((cid, name, text, sig_type, expected, "WB"))

    n_students = len(all_cases)
    results: list = []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    time_tag = datetime.now().strftime("%H%M")
    smoke_tag = "_SMOKE" if smoke else ""
    output_path = OUTPUT_DIR / (
        f"test_binary_concern_no_tiebreaker_FULL_CORPUS_{model_key}_"
        f"{date}_{time_tag}{smoke_tag}.json"
    )

    for run_idx in range(1, n_runs + 1):
        print(f"  --- Run {run_idx}/{n_runs} ---")
        for sid, name, text, pattern_or_signal, expected, source in all_cases:
            prompt = WELLBEING_CONCERN_PROMPT_NO_TIEBREAKER.format(
                student_name=name,
                assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
                class_context=CLASS_CONTEXT_TEXT,
                signal_matrix_result=SIGNAL_MATRIX_TEXT,
                submission_text=text,
                profile_fragment=PROFILE_FRAGMENT_TEXT,
            )
            t0 = time.time()
            output = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
            elapsed = round(time.time() - t0, 1)
            raw_verdict, n_concerns_raw, raw_concerns = parse_concern_result(output)

            (
                raw_confidences,
                post_regex_confidences,
                regex_demotion_applied,
                surviving_concerns,
                n_concerns_production,
            ) = apply_production_postprocessing(raw_concerns, text)

            if raw_verdict == "UNCLEAR":
                production_verdict = "UNCLEAR"
            else:
                production_verdict = "FLAG" if n_concerns_production > 0 else "CLEAR"

            match = "MATCH" if production_verdict == expected else "MISMATCH"
            marker = "!" if production_verdict != expected else " "
            print(
                f"   {marker} [{source}] {sid} {name:22s} "
                f"expected={expected:5s} raw={raw_verdict:7s} prod={production_verdict:7s} "
                f"(n_raw={n_concerns_raw}, n_prod={n_concerns_production}, "
                f"regex={'Y' if regex_demotion_applied else 'N'}, {elapsed}s)"
            )
            results.append(
                {
                    "test_variant": "R_full_corpus_no_tiebreaker",
                    "source": source,
                    "run": run_idx,
                    "student_id": sid,
                    "student_name": name,
                    "pattern": pattern_or_signal,
                    "expected": expected,
                    "result": raw_verdict,
                    "n_concerns": n_concerns_raw,
                    "raw_verdict": raw_verdict,
                    "raw_confidences": raw_confidences,
                    "post_regex_confidences": post_regex_confidences,
                    "regex_demotion_applied": regex_demotion_applied,
                    "production_verdict": production_verdict,
                    "n_concerns_raw": n_concerns_raw,
                    "n_concerns_production": n_concerns_production,
                    "match": match,
                    "codepath": "test_harness_binary_wellbeing_no_tiebreaker_plus_production_postprocessing",
                    "prompt": prompt,
                    "system_prompt": SYSTEM_PROMPT,
                    "raw_output": output,
                    "time_seconds": elapsed,
                }
            )

        if not smoke:
            save_results(results, model_key, n_runs, n_students=n_students,
                         smoke=smoke, path=output_path)
            print(f"  [Checkpoint] Run {run_idx}/{n_runs} saved ({len(results)} results).")

    path = save_results(
        results, model_key, n_runs, n_students=n_students, smoke=smoke,
        path=output_path,
    )
    print(f"\n  Results saved: {path}")

    print(f"\n  Summary (across {n_runs} runs) — raw / production verdicts:")
    by_student: dict = {}
    for r in results:
        key = (r["source"], r["student_id"], r["student_name"], r["expected"])
        by_student.setdefault(key, []).append(
            (r["raw_verdict"], r["production_verdict"])
        )
    for (source, sid, name, expected), outcomes in by_student.items():
        raw_flags = sum(1 for raw, _ in outcomes if raw == "FLAG")
        raw_clears = sum(1 for raw, _ in outcomes if raw == "CLEAR")
        raw_unclears = sum(1 for raw, _ in outcomes if raw == "UNCLEAR")
        prod_flags = sum(1 for _, prod in outcomes if prod == "FLAG")
        prod_clears = sum(1 for _, prod in outcomes if prod == "CLEAR")
        prod_unclears = sum(1 for _, prod in outcomes if prod == "UNCLEAR")
        total = len(outcomes)
        print(
            f"    [{source}] {sid} {name:22s} expected={expected:5s} | "
            f"raw FLAG={raw_flags}/{total} CLEAR={raw_clears}/{total} "
            f"UNCLEAR={raw_unclears}/{total} | "
            f"prod FLAG={prod_flags}/{total} CLEAR={prod_clears}/{total} "
            f"UNCLEAR={prod_unclears}/{total}"
        )

    return path


def _metal_warmup(model_key: str = "gemma12b") -> None:
    print("\n  [Metal warmup] Initializing GPU...")
    t0 = time.time()
    try:
        backend = get_backend(model_key)
        backend = replace(backend, temperature=0.1, max_tokens=8)
        send_text(backend, "Hi", "You are a test.")
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)\n")
    except Exception as e:  # noqa: BLE001
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Binary classifier WITHOUT tiebreaker, full 32 ES + 14 WB corpus "
            "(46 students). Companion to run_wellbeing_concern_full_corpus_test.py."
        )
    )
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke: 2 students (1 ES + 1 WB) x 1 run.")
    parser.add_argument("--n-runs", type=int, default=5,
                        help="Runs per student (default 5; ignored under --smoke).")
    parser.add_argument("--model", type=str, default="gemma12b",
                        choices=list(MODELS.keys()),
                        help="Model key (default: gemma12b).")
    parser.add_argument("--skip-warmup", action="store_true",
                        help="Skip _metal_warmup. Use when warmup hangs (observed "
                             "2026-05-12: warmup send_text deadlocks before first "
                             "inference; smoke path skips warmup and runs fine).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if not args.smoke and not args.skip_warmup:
            _metal_warmup(args.model)
        run_test(model_key=args.model, n_runs=args.n_runs, smoke=args.smoke)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    except Exception as exc:  # noqa: BLE001
        log.exception("Test failed: %s", exc)
        return 2
    finally:
        unload_mlx_model()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
