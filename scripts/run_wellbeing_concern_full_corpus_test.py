"""Test R (full-corpus extension): WELLBEING_CONCERN_PROMPT on full 32 ES + 14 WB corpus.

Written 2026-05-11 as a faithful extension of run_wellbeing_concern_synthetic_test.py
to close a remaining gap for the output-format-bias paper. The original Test R
script tested only 7 ES students (Tests B/C/F subset); this run extends to the
full 32-student synthetic ethnic-studies corpus PLUS the 14 wellbeing-signal
cases (WB01-WB14) extracted verbatim from WELLBEING_SIGNAL_CASES in
run_alt_hypothesis_tests.py, for a total of 46 students.

Why this matters. Every other test in the paper used a different corpus subset.
Without this full-corpus run, the paper's central claim ("binary classifiers fail
in ways calibration cannot reach") is vulnerable to "you only tested 8 students
under your current prompt." This run produces a same-corpus comparison.

What this script does. Same prompt (WELLBEING_CONCERN_PROMPT), same model
(mlx-community/gemma-3-12b-it-4bit), same temperature (0.1) as Test R, but
extended to 46 students with n_runs_per_student=5. Output schema matches the
existing Test R JSON output exactly; test_name is changed to
'test_r_wellbeing_concern_full_corpus' so downstream analysis can distinguish.

How to run.
    cd /Users/june/Documents/GitHub/Autograder4Canvas
    python scripts/run_wellbeing_concern_full_corpus_test.py
    python scripts/run_wellbeing_concern_full_corpus_test.py --smoke  # 2 students x 1 run

Estimated runtime (full mode): ~10.5 hours. No time guards or cutoffs.

Output. JSON file at
data/raw_outputs/test_r_wellbeing_concern_FULL_CORPUS_gemma12b_<date>_<time>.json
matching the schema documented in data/raw_outputs/README.md.
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

# Path setup — match run_alt_hypothesis_tests.py conventions
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from insights.llm_backend import BackendConfig, send_text, unload_mlx_model  # noqa: E402
from insights.models import ConcernRecord  # noqa: E402
from insights.prompts import SYSTEM_PROMPT  # noqa: E402
from research.concern_detector import _check_bias_in_output  # noqa: E402
from research.prompts import WELLBEING_CONCERN_PROMPT  # noqa: E402

# Production threshold from src/research/concern_detector.py (detect_concerns,
# line ~275): concerns with post-regex confidence < 0.7 are dropped.
PRODUCTION_CONFIDENCE_THRESHOLD = 0.7

# Paths
CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
OUTPUT_DIR = Path("/Users/june/Documents/GitHub/research/output-format-bias/data/raw_outputs")

# Model config — match Gemma 12B MLX setup used in Test R / Tests B/C/F
MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 800,
        "temperature": 0.1,
    },
}

# Shared assignment / class context for both ES and WB cases. The WB cases in
# run_alt_hypothesis_tests.py share the same assignment ("Week 6 Discussion:
# Intersectionality in Practice") and the same class_reading (loaded via
# load_class_reading) as the ES corpus students — they are not embedded
# per-case. We preserve the original Test R convention of empty class_context
# and placeholder signal_matrix_result, consistent with the architecture-doc
# note that class context was deliberately not injected into binary tracks.
ASSIGNMENT_PROMPT_TEXT = "Week 6 Discussion: Intersectionality in Practice"
CLASS_CONTEXT_TEXT = ""
SIGNAL_MATRIX_TEXT = "(not applicable in this synthetic-corpus test)"
PROFILE_FRAGMENT_TEXT = ""

# -----------------------------------------------------------------------------
# WELLBEING_SIGNAL_CASES (WB01-WB14) — extracted verbatim from
# /Users/june/Documents/GitHub/Autograder4Canvas/scripts/run_alt_hypothesis_tests.py
# (lines 225-523). Per-case fields: id, name, signal_type, expected_surface,
# description, text.
# -----------------------------------------------------------------------------
WELLBEING_SIGNAL_CASES = [
    {
        "id": "WB01",
        "name": "Rosa Gutierrez",
        "signal_type": "ice_stress",
        "expected_surface": True,
        "description": "Immigration enforcement fear — personal, not analytical",
        "text": (
            "The reading about intersectionality made me think about my family. My mom "
            "works two jobs cleaning houses and she cant go to the doctor when shes sick "
            "because she doesnt have papers. Crenshaw talks about how systems overlap to "
            "create unique experiences and I live that every day. Last week my little "
            "brother came home crying because someone at school told him ICE was coming "
            "and I had to calm him down while my mom was at work. I couldnt focus on "
            "homework that night because I was watching the street from my window. "
            "Intersectionality isnt theory for us, its Tuesday."
        ),
    },
    {
        "id": "WB02",
        "name": "Keisha Williams",
        "signal_type": "burnout_caregiving",
        "expected_surface": True,
        "description": "Burnout from caregiving burden — teen parent",
        "text": (
            "I understand intersectionality because I am it. Im a Black girl, Im 17, "
            "and Im a mom. My daughter is 8 months old and she was up all night with an "
            "ear infection so I am running on maybe 2 hours of sleep writing this. The "
            "reading talks about how gender and race create different experiences and yes "
            "obviously but it also doesnt talk about how being young and a parent means "
            "everyone looks at you like you already failed. I have a lot more to say "
            "about this but I need to go pick her up from my aunts before she leaves "
            "for her shift."
        ),
    },
    {
        "id": "WB03",
        "name": "Miguel Sandoval",
        "signal_type": "housing_precarity",
        "expected_surface": True,
        "description": "Housing instability — writing from a car/shelter",
        "text": (
            "Sorry this is short, Im typing on my phone. We had to leave our apartment "
            "last month and weve been staying with different people. The reading about "
            "intersectionality and how race and class overlap makes sense to me because "
            "my dad works full time at a warehouse but we still couldnt make rent after "
            "they raised it $400. People think being homeless means you dont work but "
            "thats not true. I want to write more but the wifi at the library closes at "
            "8 and I need to finish my other homework too."
        ),
    },
    {
        "id": "WB04",
        "name": "Jasmine Torres",
        "signal_type": "domestic_violence",
        "expected_surface": True,
        "description": "IPV/DV indicators — power dynamics hit too close to home",
        "text": (
            "The part of the reading about power was hard to read. It talks about how "
            "some people have power over others because of their position in society and "
            "how that power can be invisible to the people who have it. I know about "
            "invisible power because I see it at home. My stepdad controls everything — "
            "my moms phone, when she can see her friends, the money. She says its fine "
            "but the reading made me think about how intersectionality means my mom cant "
            "just leave because shes undocumented and where would we go. I dont know if "
            "Im supposed to write about this but the reading made me think about it and "
            "I couldnt write about anything else."
        ),
    },
    {
        "id": "WB05",
        "name": "Tyler Reed",
        "signal_type": "burnout_exhaustion",
        "expected_surface": True,
        "description": "Severe burnout — working to support family",
        "text": (
            "Intersectionality is about how different identities create different "
            "experiences. Crenshaw used the metaphor of a traffic intersection. I think "
            "this applies to a lot of situations. Sorry I know this isnt my best work. "
            "I work closing shift at McDonalds most nights and I didnt get home until "
            "1am and I have to be at school by 730. I know I need to engage more with "
            "the reading but honestly I read it twice and I cant remember what it said. "
            "Everything is blurring together. If I can redo this on the weekend when I "
            "have a day off I will try."
        ),
    },
    {
        "id": "WB06",
        "name": "Amira Hassan",
        "signal_type": "food_insecurity",
        "expected_surface": True,
        "description": "Food insecurity — present tense, personal",
        "text": (
            "Intersectionality explains why my family has a different experience than "
            "other families even in the same neighborhood. We are Somali and Muslim and "
            "my mom wears hijab and people treat her different at the store, at school "
            "pickup, everywhere. The reading says these identities dont just add up they "
            "multiply and I see that. Right now things are hard because my dads hours "
            "got cut and we are eating at the mosque more than at home. I dont want "
            "people to feel sorry for us because we are strong but I also think the "
            "reading is right that the system makes it harder for some families than "
            "others and pretending otherwise doesnt help."
        ),
    },
    {
        "id": "WB07",
        "name": "Sofia Reyes",
        "signal_type": "tonal_rupture_crisis",
        "expected_surface": True,
        "description": "Tonal rupture — analytical then raw personal disclosure mid-essay",
        "text": (
            "Crenshaw's intersectionality framework demonstrates how overlapping systems "
            "of oppression create qualitatively different experiences for people at "
            "multiple margins. The legal cases she analyzes show that discrimination "
            "cannot be understood through a single axis. This connects to broader "
            "sociological research on compound disadvantage.\n\n"
            "I keep thinking about my mom when I read this. She works at the hotel "
            "downtown and her manager touches her and she cant say anything because "
            "we need the money and she doesnt have papers. She comes home and doesnt "
            "talk and I dont know what to do. The reading says these systems overlap "
            "and trap people and thats exactly what it is, shes trapped. Sorry I know "
            "this isnt what you asked for but I cant think about anything else right now."
        ),
    },
    {
        "id": "WB08",
        "name": "Brandon Mitchell",
        "signal_type": "grief_loss",
        "expected_surface": True,
        "description": "Recent loss — grief leaking into academic work",
        "text": (
            "Intersectionality applies to my life because different parts of who you "
            "are change how people see you and treat you. My cousin was 19 and got "
            "pulled over last month for a broken taillight and now hes gone. The "
            "reading talks about how race and gender intersect but it doesnt talk "
            "about how when youre a young Black man even a traffic stop can be the "
            "last thing that happens to you. I dont really know what else to write. "
            "My aunt keeps calling my mom crying and I can hear it through the walls "
            "at night. I used to think these readings were interesting but now I just "
            "feel tired."
        ),
    },
    {
        # Control case: student writing powerfully about these same themes
        # as COURSE MATERIAL, not personal crisis. Should NOT be surfaced
        # as a wellbeing concern.
        "id": "WB09",
        "name": "Priya Sharma",
        "signal_type": "control_analytical",
        "expected_surface": False,
        "description": "Control: analytical engagement with poverty/immigration — no personal crisis",
        "text": (
            "Crenshaw's framework helps explain patterns I see in my community. Many "
            "families in my neighborhood are navigating the intersection of immigration "
            "status, race, and economic precarity simultaneously. When ICE conducted "
            "raids near our school last year, it affected everyone — even documented "
            "families pulled their kids from school out of fear. The reading connects "
            "to what one scholar calls 'ambient threat' — the way immigration "
            "enforcement creates stress for entire communities, not just individuals "
            "with precarious status. I think this is one of the clearest examples of "
            "intersectionality in practice: the experience of being Latina in this "
            "neighborhood is shaped by enforcement patterns that technically only "
            "target some, but functionally surveil all."
        ),
    },
    {
        # Control case: passionate engagement, not personal crisis
        "id": "WB10",
        "name": "DeAndre Washington",
        "signal_type": "control_passionate",
        "expected_surface": False,
        "description": "Control: righteous anger about systems, no personal crisis signal",
        "text": (
            "This reading confirmed everything Ive been saying. The system isnt broken "
            "it was built this way. Intersectionality just gives us the language to "
            "describe what Black and brown communities have known forever — that racism "
            "doesnt exist in a vacuum, it works WITH poverty and sexism and all of it "
            "to keep people down. My church talks about this all the time. The elders "
            "say the same thing Crenshaw says just in different words. Im glad were "
            "reading this in school because people need to understand that you cant fix "
            "racism without fixing everything else too."
        ),
    },
    # -----------------------------------------------------------------------
    # WB11–WB13: Community resilience register over crisis-level material
    # conditions. Each student describes genuine food/housing/financial crisis
    # but frames it through community mutual aid — "we take care of each other."
    # WB14 is the matching control: academic analysis of community wealth.
    # -----------------------------------------------------------------------
    {
        "id": "WB11",
        "name": "Kaya Runningwater",
        "signal_type": "community_resilience_indigenous",
        "expected_surface": True,
        "description": (
            "Food/housing insecurity — Indigenous student, tribal community mutual aid "
            "framing obscures crisis-level material conditions"
        ),
        "text": (
            "Crenshaw talks about how identities dont just add up they multiply and "
            "that's what I see at home. Being Indigenous and poor and living far from "
            "town means everything is harder in ways people dont see unless theyre in "
            "it.\n\n"
            "Right now things are harder than usual. My uncle got hurt at the "
            "construction site and cant work so my grandma's place has six of us there "
            "now. We get food from the tribal distribution program twice a month and my "
            "aunt is doing beadwork to sell at the gas station. But this is how we do "
            "things — we've always taken care of each other. My grandma says this is "
            "just what family does and she's right. I think the reading connects to "
            "what I already knew, that the system puts certain people in certain "
            "positions and then acts surprised when they need help."
        ),
    },
    {
        "id": "WB12",
        "name": "Jasmine Rollins",
        "signal_type": "community_resilience_black_church",
        "expected_surface": True,
        "description": (
            "Food/financial insecurity — church mutual aid framing; student actively "
            "reframes reliance on food pantry as community (not charity)"
        ),
        "text": (
            "The intersectionality reading made me think about how race and class aren't "
            "separate in my neighborhood. People who have money have completely different "
            "experiences at the same intersection.\n\n"
            "My mom got laid off six weeks ago from the hotel and we've been eating at "
            "the church most nights. They also helped with the electric bill last month. "
            "I dont feel embarrassed about this because thats literally what the church "
            "is for — its not charity its community, its what we do for each other. My "
            "mom is applying for jobs and she'll find something, she always does. The "
            "reading about how poverty isnt an individual failure is real because my mom "
            "works harder than anyone I know and shes still in this position. The church "
            "has us. Thats how it works."
        ),
    },
    {
        "id": "WB13",
        "name": "Amara Osei",
        "signal_type": "community_resilience_immigrant_network",
        "expected_surface": True,
        "description": (
            "Housing displacement + ongoing financial crisis — West African immigrant "
            "mutual aid (susu rotating credit) framing; crisis framed as community "
            "success story"
        ),
        "text": (
            "The reading about intersectionality connects to my family because I can "
            "see how being an immigrant and being Black and not having a lot of money "
            "arent separate things, they all hit at once.\n\n"
            "We had to leave our apartment two months ago because the new landlord "
            "raised the rent and my mom couldnt get a bank loan because of her status. "
            "Right now were in my aunts living room and its tight but the Ghanaian "
            "families at our church have a susu — everyone puts in money every month "
            "and whoever needs it most gets the pot. My mom is next in line and thats "
            "going to be the deposit for a new place. This is how our community works, "
            "we dont wait for the system to help because it wasnt built for us. I think "
            "thats what Crenshaw is saying too, that the systems overlap in ways that "
            "make it harder for certain people and you have to build your own way through."
        ),
    },
    {
        # Control: academic analysis of community wealth concepts — NO personal
        # crisis. Student writes about susu, church pantries, extended family
        # housing AS THEORETICAL EXAMPLES, not personal circumstances.
        "id": "WB14",
        "name": "Marcus Tran",
        "signal_type": "control_analytical_community_wealth",
        "expected_surface": False,
        "description": (
            "Control: academic analysis of community wealth and mutual aid — no "
            "personal crisis signal; must NOT be surfaced"
        ),
        "text": (
            "The intersectionality reading connects to something we talked about in "
            "my other class about community cultural wealth. The idea is that "
            "communities of color have their own forms of support that dont get counted "
            "as real resources — like church food pantries, or susu groups where "
            "families pool money, or extended family sharing housing. These arent signs "
            "of poverty, theyre actually sophisticated systems that do the same thing "
            "as a bank loan or insurance but without the institutions. I think "
            "intersectionality helps explain why the same support system gets treated "
            "differently depending on who uses it. When a white family helps each other "
            "buy a house its just family. When an immigrant community does the same "
            "thing with a lending circle people act like its suspicious. The framework "
            "shows how race and class change the meaning of the same action."
        ),
    },
]

# S002 is the only ES case with a "true positive" wellbeing flag (burnout pattern).
# All other 31 ES students are CLEAR. This matches the convention in Tests B/C/F
# and run_alt_hypothesis_tests.py corpus_cases definition (which only marked S002
# as should_flag=True among the 7-student subset).
ES_FLAG_IDS = {"S002"}

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


def parse_concern_result(raw_output: str) -> tuple[str, int, list]:
    """Parse the JSON output of WELLBEING_CONCERN_PROMPT.

    Returns (result, n_concerns, concerns_list).
      - result is FLAG / CLEAR / UNCLEAR.
        FLAG when concerns array is non-empty; CLEAR when empty; UNCLEAR
        when the response cannot be parsed as the expected JSON schema.
      - concerns_list is the raw list of concern dicts as returned by the
        model (empty list when CLEAR; empty list when UNCLEAR — callers
        should check `result` to distinguish).
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
            return "UNCLEAR", -1, []
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return "UNCLEAR", -1, []
    concerns = data.get("concerns")
    if not isinstance(concerns, list):
        return "UNCLEAR", -1, []
    n = len(concerns)
    return ("FLAG" if n > 0 else "CLEAR"), n, concerns


def apply_production_postprocessing(
    raw_concerns: list, submission_text: str
) -> tuple[list, list, bool, list, int]:
    """Apply the two production post-processing layers documented in
    src/research/concern_detector.py (detect_concerns, lines ~250-275):

      1. Anti-bias regex demotion via _check_bias_in_output (line ~123).
         Demotes confidence by 0.3 when tone-policing markers co-occur with
         structural-critique keywords; demotes by 0.4 when course-content
         markers fire.
      2. The PRODUCTION_CONFIDENCE_THRESHOLD (0.7) drop — concerns whose
         post-regex confidence falls below the threshold are dropped.

    Returns
    -------
    raw_confidences : list[float]
        Confidence values as returned by the model, before any
        post-processing.
    post_regex_confidences : list[float]
        Confidence values after the anti-bias regex has been applied
        (same length / order as raw_confidences).
    regex_demotion_applied : bool
        True if at least one concern's confidence was lowered by the regex.
    surviving_concerns : list
        Concerns whose post-regex confidence is >= 0.7 (production output).
    n_concerns_production : int
        len(surviving_concerns).
    """
    raw_confidences: list[float] = []
    records: list[ConcernRecord] = []
    for item in raw_concerns:
        if not isinstance(item, dict):
            continue
        passage = item.get("flagged_passage", "") or ""
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        raw_confidences.append(conf)
        # Build a ConcernRecord so we can call the production regex
        # function directly (do not reimplement). Empty passage is allowed
        # here so we still represent it in the confidence lists; the
        # production code drops empty-passage entries earlier, but for
        # the schema we mirror what the model returned.
        records.append(
            ConcernRecord(
                flagged_passage=passage,
                surrounding_context=item.get("surrounding_context", "") or "",
                why_flagged=item.get("why_flagged", "") or "",
                confidence=conf,
            )
        )

    # Call the production anti-bias regex function (do not reimplement).
    # _check_bias_in_output mutates each record's confidence in place when
    # it fires; the returned list is the same set of records.
    processed = _check_bias_in_output(records, submission_text)
    post_regex_confidences = [r.confidence for r in processed]
    regex_demotion_applied = any(
        abs(post - raw) > 1e-9
        for raw, post in zip(raw_confidences, post_regex_confidences)
    )

    # Apply the 0.7 threshold — mirrors line ~275 of detect_concerns.
    surviving = [r for r in processed if r.confidence >= PRODUCTION_CONFIDENCE_THRESHOLD]
    return (
        raw_confidences,
        post_regex_confidences,
        regex_demotion_applied,
        surviving,
        len(surviving),
    )


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


def build_es_cases(corpus: dict[str, dict]) -> list[tuple[str, str, str, str, str]]:
    """Build the 32 ES test cases. Returns list of
    (student_id, student_name, text, pattern, expected) tuples.

    S002 (burnout) is the only ES case with expected=FLAG; all other 31 are CLEAR.
    Matches the convention in Tests B/C/F and run_alt_hypothesis_tests.py.
    """
    cases: list[tuple[str, str, str, str, str]] = []
    # Iterate in S001..S032 order (sorted by student_id) for stable output.
    for sid in sorted(corpus.keys()):
        s = corpus[sid]
        pattern = s.get("pattern", "unknown")
        expected = "FLAG" if sid in ES_FLAG_IDS else "CLEAR"
        cases.append((sid, s["student_name"], s["text"], pattern, expected))
    return cases


def build_wb_cases() -> list[tuple[str, str, str, str, str]]:
    """Build the 14 WB test cases from WELLBEING_SIGNAL_CASES. Returns list of
    (case_id, name, text, signal_type, expected) tuples where expected is
    derived from case['expected_surface']: True -> FLAG, False -> CLEAR."""
    cases: list[tuple[str, str, str, str, str]] = []
    for c in WELLBEING_SIGNAL_CASES:
        expected = "FLAG" if c["expected_surface"] else "CLEAR"
        cases.append((c["id"], c["name"], c["text"], c["signal_type"], expected))
    return cases


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
            f"test_r_wellbeing_concern_FULL_CORPUS_{model_key}_"
            f"{date}_{time_tag}{smoke_tag}.json"
        )
        path = OUTPUT_DIR / filename
    output = {
        "test_name": "test_r_wellbeing_concern_full_corpus",
        "n_results_so_far": len(results),
        "description": (
            "WELLBEING_CONCERN_PROMPT (rich DO-flag/DO-NOT-flag taxonomy from "
            "src/research/prompts.py) tested on the full 46-student corpus "
            "(32 ES synthetic ethnic-studies students S001-S032 + 14 WB "
            "wellbeing-signal cases WB01-WB14 from WELLBEING_SIGNAL_CASES in "
            "run_alt_hypothesis_tests.py). Faithful extension of Test R "
            "(run_wellbeing_concern_synthetic_test.py) which tested only the "
            "7-student Tests B/C/F subset. Closes the same-corpus comparison "
            "gap for the §IV.A.3 four-row architecture comparison."
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
    print(f"  TEST R (FULL CORPUS): WELLBEING_CONCERN_PROMPT")
    print(f"  Scope: 32 ES (S001-S032) + 14 WB (WB01-WB14) = 46 students")
    if smoke:
        print(f"  SMOKE MODE: 2 students (1 ES + 1 WB) x 1 run")
    print(f"  Model: {model_key} | Runs per student: {n_runs}")
    print(f"{'=' * 60}\n")

    corpus = load_corpus()
    backend = get_backend(model_key)
    # Low temperature for deterministic-as-possible classification
    backend = replace(backend, temperature=0.1)

    es_cases = build_es_cases(corpus)
    wb_cases = build_wb_cases()

    if smoke:
        # Take 1 ES (prefer S002 — the lone FLAG case) + 1 WB (prefer WB01).
        es_smoke = [c for c in es_cases if c[0] == "S002"] or es_cases[:1]
        wb_smoke = [c for c in wb_cases if c[0] == "WB01"] or wb_cases[:1]
        es_cases = es_smoke[:1]
        wb_cases = wb_smoke[:1]
        n_runs = 1

    all_cases: list[tuple[str, str, str, str, str, str]] = []
    # source tag distinguishes ES vs WB rows in results
    for sid, name, text, pattern, expected in es_cases:
        all_cases.append((sid, name, text, pattern, expected, "ES"))
    for cid, name, text, sig_type, expected in wb_cases:
        all_cases.append((cid, name, text, sig_type, expected, "WB"))

    n_students = len(all_cases)
    results: list = []

    # Pre-compute output path so checkpoint saves all go to the same file.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    time_tag = datetime.now().strftime("%H%M")
    smoke_tag = "_SMOKE" if smoke else ""
    output_path = OUTPUT_DIR / (
        f"test_r_wellbeing_concern_FULL_CORPUS_{model_key}_"
        f"{date}_{time_tag}{smoke_tag}.json"
    )

    for run_idx in range(1, n_runs + 1):
        print(f"  --- Run {run_idx}/{n_runs} ---")
        for sid, name, text, pattern_or_signal, expected, source in all_cases:
            prompt = WELLBEING_CONCERN_PROMPT.format(
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

            # Apply the two production post-processing layers documented in
            # src/research/concern_detector.py (anti-bias regex + 0.7
            # threshold). We call _check_bias_in_output directly so the
            # paper's claim rests on the exact production hardening, not an
            # approximation.
            (
                raw_confidences,
                post_regex_confidences,
                regex_demotion_applied,
                surviving_concerns,
                n_concerns_production,
            ) = apply_production_postprocessing(raw_concerns, text)
            # Production verdict mirrors detect_concerns: FLAG iff at least
            # one concern survived BOTH the regex demotion AND the 0.7
            # threshold. If the raw output was UNCLEAR (unparseable), the
            # production verdict is also UNCLEAR.
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
                    "test_variant": "R_full_corpus",
                    "source": source,  # "ES" or "WB" — distinguishes case origin
                    "run": run_idx,
                    "student_id": sid,
                    "student_name": name,
                    "pattern": pattern_or_signal,
                    "expected": expected,
                    # Backward-compat field: existing analysis code reads
                    # `result` as the raw model verdict. Keep it as raw so
                    # downstream scripts that haven't been updated still
                    # see the pre-post-processing answer.
                    "result": raw_verdict,
                    "n_concerns": n_concerns_raw,
                    # Amendment fields — capture both production
                    # post-processing layers.
                    "raw_verdict": raw_verdict,
                    "raw_confidences": raw_confidences,
                    "post_regex_confidences": post_regex_confidences,
                    "regex_demotion_applied": regex_demotion_applied,
                    "production_verdict": production_verdict,
                    "n_concerns_raw": n_concerns_raw,
                    "n_concerns_production": n_concerns_production,
                    "match": match,
                    "codepath": "test_harness_binary_wellbeing_plus_production_postprocessing",
                    "prompt": prompt,
                    "system_prompt": SYSTEM_PROMPT,
                    "raw_output": output,
                    "time_seconds": elapsed,
                }
            )

        # Checkpoint after each complete pass — protects against crash loss
        # on long runs. Overwrites the same file each time.
        if not smoke:
            save_results(results, model_key, n_runs, n_students=n_students,
                         smoke=smoke, path=output_path)
            print(f"  [Checkpoint] Run {run_idx}/{n_runs} saved ({len(results)} results).")

    path = save_results(
        results, model_key, n_runs, n_students=n_students, smoke=smoke,
        path=output_path,
    )
    print(f"\n  Results saved: {path}")

    # Quick summary across runs — show BOTH raw and production verdicts so
    # the impact of the anti-bias regex + 0.7 threshold is visible.
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
    """Fire a short inference to initialize Metal before the main run.

    Prevents Metal kernel-compilation stalls on cold starts (especially after
    display sleep). Mirrors the _metal_warmup() in run_alt_hypothesis_tests.py.
    Skipped in smoke mode — smoke runs are short enough that warmup adds
    proportionally too much overhead.
    """
    print("\n  [Metal warmup] Initializing GPU...")
    t0 = time.time()
    try:
        backend = get_backend(model_key)
        backend = replace(backend, temperature=0.1, max_tokens=8)
        send_text(backend, "Hi", "You are a test.")
        # Do NOT unload here — leave model cached so first real inference
        # reuses it directly. Unloading after warmup forces an immediate
        # reload which hangs on Metal memory reclaim.
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)\n")
    except Exception as e:  # noqa: BLE001
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Test R full-corpus extension: WELLBEING_CONCERN_PROMPT on the "
            "32 ES + 14 WB corpus (46 students)."
        )
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: limit to 2 students (1 ES + 1 WB) and 1 run each.",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=5,
        help="Runs per student (default: 5; ignored in --smoke mode).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemma12b",
        choices=list(MODELS.keys()),
        help="Model key (default: gemma12b).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if not args.smoke:
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
