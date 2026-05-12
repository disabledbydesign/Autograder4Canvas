"""Test R: WELLBEING_CONCERN_PROMPT on the synthetic ethnic-studies corpus.

Written 2026-05-10 to close a gap in the binary-classifier ablation history.

Context. Tests B/C/F (March 26–28) tested the calibrated binary classifier
on the 32-student synthetic corpus using BEST_CONCERN_SYSTEM — the 5-equation
retroactive reconstruction of the original lost prompt. Test M (March 28)
added regex post-processing + a 0.7 confidence threshold using the production
combined-scope CONCERN_PROMPT. The wellbeing-scope WELLBEING_CONCERN_PROMPT
(the rich DO-flag / DO-NOT-flag taxonomy) was written later for the April 27
dual-binary live-data run and never tested on the synthetic corpus.

What this script does. Runs WELLBEING_CONCERN_PROMPT on the same 7-student
test set used in Tests B/C/F, 3 passes per student, Gemma 12B via MLX, low
temperature for deterministic-as-possible classification. Saves results to
data/raw_outputs in the same JSON schema as the other tests. Lets the paper
report a third configuration row in the §IV.A.3 ablation: bare prompt
(Tests B/C/F), prompt + post-processing (Test M), rich wellbeing taxonomy
(this test).

How to run.
    cd /Users/june/Documents/GitHub/autograder4canvas
    python scripts/run_wellbeing_concern_synthetic_test.py

The script uses the same paths and conventions as scripts/run_alt_hypothesis_tests.py
(load_corpus, get_backend, save_results, SYSTEM_PROMPT). It does not depend
on class-context loading or the non-LLM signal matrix; those fields are
passed as empty placeholders, consistent with the architecture-doc note
that class context was deliberately not injected into binary tracks.

Output. JSON file at data/raw_outputs/test_r_wellbeing_concern_synthetic_gemma12b_<date>_<time>.json
matching the schema documented in data/raw_outputs/README.md.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

# Path setup — match run_alt_hypothesis_tests.py conventions
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from insights.llm_backend import BackendConfig, send_text, unload_mlx_model  # noqa: E402
from insights.prompts import SYSTEM_PROMPT  # noqa: E402
from research.prompts import WELLBEING_CONCERN_PROMPT  # noqa: E402

# Paths
CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
OUTPUT_DIR = Path("/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs")

# Model config — match Gemma 12B MLX setup used in Tests B/C/F
MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 800,
        "temperature": 0.1,
    },
}

# Test cases — same 7-student subset used in Tests B/C/F
TEST_CASES = [
    ("S002", "burnout", "FLAG"),
    ("S004", "strong", "CLEAR"),
    ("S022", "righteous_anger", "CLEAR"),
    ("S023", "lived_exp", "CLEAR"),
    ("S024", "lived_exp", "CLEAR"),
    ("S028", "AAVE", "CLEAR"),
    ("S029", "neurodivergent", "CLEAR"),
    ("S031", "minimal_effort", "CLEAR"),
]

# Placeholder values for WELLBEING_CONCERN_PROMPT template variables that the
# synthetic-corpus run does not provide. The synthetic corpus has no per-student
# assignment prompt; using the assignment label that Test A used for the same
# corpus. class_context and signal_matrix_result are deliberately left empty —
# class context was not injected into binary tracks in any of the prior tests
# (Tests B/C/F also ran without it), and the non-LLM signal matrix is part of
# the live-data architecture, not the synthetic ablation.
ASSIGNMENT_PROMPT_TEXT = "Week 6 Discussion: Intersectionality in Practice"
CLASS_CONTEXT_TEXT = ""
SIGNAL_MATRIX_TEXT = "(not applicable in this synthetic-corpus test)"
PROFILE_FRAGMENT_TEXT = ""

log = logging.getLogger(__name__)


def load_corpus() -> dict[str, dict]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(
            f"Corpus not found at {CORPUS_PATH}. "
            "Adjust CORPUS_PATH at the top of this script if it has moved."
        )
    corpus = json.loads(CORPUS_PATH.read_text())
    return {s["student_id"]: s for s in corpus}


def get_backend(model_key: str = "gemma12b") -> BackendConfig:
    cfg = MODELS[model_key]
    return BackendConfig(
        name=cfg["name"],
        model=cfg["model"],
        max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
    )


def parse_concern_result(raw_output: str) -> tuple[str, int]:
    """Parse the JSON output of WELLBEING_CONCERN_PROMPT.

    Returns (result, n_concerns). result is FLAG / CLEAR / UNCLEAR.
    FLAG when concerns array is non-empty; CLEAR when empty; UNCLEAR
    when the response cannot be parsed as the expected JSON schema.
    """
    text = raw_output.strip()
    # Try direct JSON first
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return "UNCLEAR", -1
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return "UNCLEAR", -1
    concerns = data.get("concerns")
    if not isinstance(concerns, list):
        return "UNCLEAR", -1
    n = len(concerns)
    return ("FLAG" if n > 0 else "CLEAR"), n


def git_provenance() -> dict:
    """Capture git state for reproducibility — same shape as save_results in
    run_alt_hypothesis_tests.py."""
    import subprocess

    prov: dict = {}
    try:
        prov["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(ROOT),
        ).stdout.strip()
        prov["git_commit_short"] = prov["git_commit"][:8]
        prov["git_dirty"] = bool(
            subprocess.run(
                ["git", "diff", "--quiet"],
                capture_output=True,
                timeout=5,
                cwd=str(ROOT),
            ).returncode
        )
        prov["git_branch"] = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(ROOT),
        ).stdout.strip()
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = None
    return prov


def save_results(results: list, model_key: str, n_runs: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    time_tag = datetime.now().strftime("%H%M")
    filename = f"test_r_wellbeing_concern_synthetic_{model_key}_{date}_{time_tag}.json"
    output = {
        "test_name": "test_r_wellbeing_concern_synthetic",
        "description": (
            "WELLBEING_CONCERN_PROMPT (rich DO-flag/DO-NOT-flag taxonomy from "
            "src/research/prompts.py) tested on the 32-student synthetic "
            "ethnic-studies corpus. Closes the gap between the live-data rich "
            "taxonomy and the synthetic-corpus ablation."
        ),
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies",
        "corpus_path": str(CORPUS_PATH),
        "n_runs_per_student": n_runs,
        "n_students_tested": len(TEST_CASES),
        "assignment_prompt": ASSIGNMENT_PROMPT_TEXT,
        "class_context": CLASS_CONTEXT_TEXT or "(empty — class context was not injected into binary tracks)",
        "signal_matrix_result": SIGNAL_MATRIX_TEXT,
        "provenance": git_provenance(),
        "results": results,
    }
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    return path


def run_test(model_key: str = "gemma12b", n_runs: int = 3) -> Path:
    print(f"\n{'=' * 60}")
    print(f"  TEST R: WELLBEING_CONCERN_PROMPT on synthetic corpus")
    print(f"  Model: {model_key} | Runs per student: {n_runs}")
    print(f"{'=' * 60}\n")

    corpus = load_corpus()
    backend = get_backend(model_key)
    # Match Tests B/C/F: low temperature for deterministic classification
    backend = replace(backend, temperature=0.1)

    results: list = []

    for run_idx in range(1, n_runs + 1):
        print(f"  --- Run {run_idx}/{n_runs} ---")
        for sid, pattern, expected in TEST_CASES:
            if sid not in corpus:
                print(f"    {sid}: SKIPPED — not in corpus")
                continue
            student = corpus[sid]
            prompt = WELLBEING_CONCERN_PROMPT.format(
                student_name=student["student_name"],
                assignment_prompt=ASSIGNMENT_PROMPT_TEXT,
                class_context=CLASS_CONTEXT_TEXT,
                signal_matrix_result=SIGNAL_MATRIX_TEXT,
                submission_text=student["text"],
                profile_fragment=PROFILE_FRAGMENT_TEXT,
            )
            t0 = time.time()
            output = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
            elapsed = round(time.time() - t0, 1)
            result, n_concerns = parse_concern_result(output)
            match = "MATCH" if result == expected else "MISMATCH"
            marker = "!" if result != expected else " "
            print(
                f"   {marker} {sid} {student['student_name']:20s} "
                f"expected={expected:5s} got={result:7s} (n_concerns={n_concerns}, {elapsed}s)"
            )
            results.append(
                {
                    "test_variant": "R",
                    "run": run_idx,
                    "student_id": sid,
                    "student_name": student["student_name"],
                    "pattern": pattern,
                    "expected": expected,
                    "result": result,
                    "n_concerns": n_concerns,
                    "match": match,
                    "codepath": "test_harness_binary_wellbeing_only",
                    "prompt": prompt,
                    "system_prompt": SYSTEM_PROMPT,
                    "raw_output": output,
                    "time_seconds": elapsed,
                }
            )

    path = save_results(results, model_key, n_runs)
    print(f"\n  Results saved: {path}")

    # Quick summary across runs
    print(f"\n  Summary (across {n_runs} runs):")
    by_student: dict = {}
    for r in results:
        key = (r["student_id"], r["student_name"], r["expected"])
        by_student.setdefault(key, []).append(r["result"])
    for (sid, name, expected), outcomes in by_student.items():
        flags = sum(1 for o in outcomes if o == "FLAG")
        clears = sum(1 for o in outcomes if o == "CLEAR")
        unclears = sum(1 for o in outcomes if o == "UNCLEAR")
        print(
            f"    {sid} {name:20s} expected={expected:5s} "
            f"FLAG={flags}/{n_runs} CLEAR={clears}/{n_runs} UNCLEAR={unclears}/{n_runs}"
        )

    return path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        run_test(model_key="gemma12b", n_runs=10)
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
