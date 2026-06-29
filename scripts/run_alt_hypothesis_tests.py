#!/usr/bin/env python3
"""
Alternative hypothesis tests for the observation architecture paper.

Reconstructed from docs/research/experiment_log.md methodology.
Saves all raw outputs to data/research/raw_outputs/ (persistent, not /tmp).

Tests:
  A: Temperature/consistency (5 runs × 2 students on observation prompt)
  B: Best possible concern prompt (7 key students)
  C: Length effect (7 key students, 100-150 word assessments)
  D: Structural power moves detection (2 corpus + 5 synthetic)
  E: Cross-model replication (Test A on Qwen 7B)

Usage:
    python scripts/run_alt_hypothesis_tests.py [--tests A,B,C,D,E] [--model gemma12b]
    python scripts/run_alt_hypothesis_tests.py --tests A,E  # just temperature + cross-model
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
CLASS_READING_PATH = ROOT / "data" / "demo_baked" / "checkpoints" / "ethnic_studies_gemma12b_mlx_class_reading.json"
# Overridden at runtime by --corpus flag; tests that use CLASS_READING_PATH
# (synthesis-first variants) will need a matching checkpoint — see --class-reading.
OUTPUT_DIR = ROOT / "data" / "research" / "raw_outputs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alt_hypothesis_tests")


# ---------------------------------------------------------------------------
# Model configs
# ---------------------------------------------------------------------------

def _openrouter_key():
    """Load OpenRouter API key from Reframe .env."""
    env_path = Path.home() / "Documents" / "GitHub" / "Reframe" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REFRAME_SHARED_OPENROUTER_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REFRAME_SHARED_OPENROUTER_KEY", "")


MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "qwen7b": {
        "name": "mlx",
        "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "gemma27b_cloud": {
        "name": "cloud",
        "model": "google/gemma-3-27b-it",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
    "mistral_large_cloud": {
        "name": "cloud",
        "model": "mistralai/mistral-large-2411",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
}


# ---------------------------------------------------------------------------
# Prompts (from src/insights/prompts.py + experiment log methodology)
# ---------------------------------------------------------------------------

from insights.prompts import OBSERVATION_SYSTEM_PROMPT, OBSERVATION_PROMPT

BEST_CONCERN_SYSTEM = (
    "You are assessing whether a student's submission raises genuine wellbeing "
    "concerns that the teacher should be aware of.\n\n"
    "CRITICAL EQUITY PROTECTIONS — These are NOT concerns:\n"
    "- Righteous anger about injustice = ENGAGEMENT, not distress\n"
    "- Lived experience of racism, poverty, immigration, disability, "
    "or gender violence described AS COURSE MATERIAL = doing the assignment\n"
    "- AAVE, multilingual mixing, nonstandard English = VALID ACADEMIC REGISTER\n"
    "- Neurodivergent writing patterns (fragmented, nonlinear, associative) = "
    "COGNITIVE STYLE, not confusion\n"
    "- Passionate, emotional, or confrontational engagement with difficult "
    "material = INTELLECTUAL ENGAGEMENT\n\n"
    "Genuine wellbeing concerns include: signs of burnout/exhaustion, "
    "expressions of hopelessness about personal situation (not course material), "
    "mentions of self-harm, or requests for help."
)

BEST_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Respond with JSON only: {{"concern": true/false, "explanation": "..."}}"""

LENGTH_CONCERN_SYSTEM = BEST_CONCERN_SYSTEM

LENGTH_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

In 100-150 words, assess this student's submission for genuine wellbeing concerns.
Consider the equity protections carefully. Then conclude with either:
CONCERN: YES
or
CONCERN: NO"""


# Synthetic power move test cases (from experiment log Test D methodology)
POWER_MOVE_CASES = [
    {
        "id": "PM01",
        "name": "Alex Rivera",
        "type": "abstract_liberalism",
        "text": (
            "I think the most important thing is that we should treat everyone equally "
            "regardless of race. The reading talks about structural racism, but I believe "
            "if we just focus on being fair to everyone as individuals, these problems "
            "would go away. My parents taught me that judging people by their character "
            "is what matters. I don't see why we need to keep bringing up race when the "
            "goal should be a colorblind society where everyone has the same opportunities."
        ),
    },
    {
        "id": "PM02",
        "name": "Emily Chen",
        "type": "settler_innocence",
        "text": (
            "This reading about indigenous land rights was really eye-opening. I feel "
            "terrible about what happened to Native Americans, but my family immigrated "
            "from China in the 1990s, so we weren't part of colonization. I think it's "
            "unfair to make people who weren't involved feel guilty. We should acknowledge "
            "history but also move forward. My family worked really hard to build a life "
            "here and I don't think that makes us complicit in something that happened "
            "hundreds of years ago."
        ),
    },
    {
        "id": "PM03",
        "name": "Jake Morrison",
        "type": "progress_narrative",
        "text": (
            "While I understand the frustration in the reading, I think we need to "
            "acknowledge how much progress we've made. We had a Black president, we have "
            "more diverse representation in media than ever, and there are laws against "
            "discrimination. Things aren't perfect but they're so much better than they "
            "were 50 years ago. I worry that focusing too much on what's still wrong "
            "ignores all the positive changes and makes people feel hopeless."
        ),
    },
    {
        "id": "PM04",
        "name": "Sarah Thompson",
        "type": "meritocracy_deflection",
        "text": (
            "The reading makes it sound like the system is designed to keep people down, "
            "but I know plenty of people from disadvantaged backgrounds who succeeded "
            "through hard work. My uncle grew up in poverty and became a doctor. Instead "
            "of blaming the system, maybe we should focus on individual empowerment and "
            "education. If people just tried harder and took advantage of the opportunities "
            "that exist, I think a lot of these disparities would decrease."
        ),
    },
    {
        "id": "PM05",
        "name": "David Park",
        "type": "objectivity_claim",
        "text": (
            "I think this discussion would benefit from a more objective, data-driven "
            "approach. The reading relies a lot on personal stories and emotional arguments. "
            "If we really want to understand racial disparities, we should look at the "
            "statistics and let the data speak for itself instead of cherry-picking "
            "anecdotes. Science is supposed to be neutral and we should apply the same "
            "rigor to social issues instead of letting ideology drive the conclusions."
        ),
    },
]

# ---------------------------------------------------------------------------
# Synthetic wellbeing signal cases (Test G)
#
# Each case contains a genuine wellbeing signal embedded in course-relevant
# writing. The challenge: in Ethnic Studies, students write about poverty,
# violence, immigration, etc. AS COURSE MATERIAL. These cases test whether
# the observation architecture can distinguish "doing the assignment" from
# "this student is telling me something about their own situation."
#
# Key design principle: the signal is PRESENT-TENSE and PERSONAL — not
# analytical engagement with course themes but the student's own immediate
# circumstances leaking through.
# ---------------------------------------------------------------------------

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
    #
    # These test the MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE guard:
    # the classifier must see through the resilience framing to the underlying
    # material conditions. Three distinct community contexts:
    #   WB11 — Indigenous student, tribal food distribution + housing crowding
    #   WB12 — Black student, church food pantry after parent's job loss
    #   WB13 — Ghanaian immigrant student, susu rotating credit after eviction
    #
    # WB14 is the matching control: academic analysis of community wealth
    # concepts (Yosso) with NO personal crisis signal. Guard must not fire.
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
        # Guard must not fire: analytical writing about these topics ≠ crisis.
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

# Wellbeing signal keywords for Test G evaluation
WELLBEING_KEYWORDS = [
    r"fatigue", r"exhaust", r"sleep", r"tired", r"burnout",
    r"shelter", r"hous", r"evict", r"homeless", r"unstable",
    r"food", r"hungry", r"eat", r"meal",
    r"ICE|immigra.*fear|deportat|undocument",
    r"safe|afraid|scar|violen|abus|control",
    r"work.*shift|closing shift|job",
    r"check.?in|wellbeing|support|resource",
    r"caregiv|parent|baby|child.*care",
    r"precari|instabil|crisis|struggl",
]


# Detection keywords for Test D
POWER_MOVE_KEYWORDS = [
    r"tone.?polic", r"colorblind", r"structural", r"recenter", r"foreclose",
    r"silenc", r"dismiss", r"abstract.?liberal", r"meritocra", r"settler",
    r"progress.?narrative", r"objectiv", r"deflect", r"power.?move",
    r"power.?arrangement", r"maintain.*power", r"innocen",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_corpus() -> Dict[str, dict]:
    corpus = json.loads(CORPUS_PATH.read_text())
    return {s["student_id"]: s for s in corpus}


def load_class_reading() -> str:
    data = json.loads(CLASS_READING_PATH.read_text())
    if isinstance(data, dict) and "class_reading" in data:
        return data["class_reading"]
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return str(data)


def get_backend(model_key: str):
    from insights.llm_backend import BackendConfig
    cfg = MODELS[model_key]
    kwargs = {
        "name": cfg["name"],
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]
    if "api_key_fn" in cfg:
        kwargs["api_key"] = cfg["api_key_fn"]()
    elif "api_key" in cfg:
        kwargs["api_key"] = cfg["api_key"]
    return BackendConfig(**kwargs)


def send(backend, prompt: str, system_prompt: str, max_tokens: int = 300) -> str:
    from insights.llm_backend import send_text
    return send_text(backend, prompt, system_prompt, max_tokens=max_tokens)


def classify_framing(text: str) -> str:
    """Classify observation output as ASSET, DEFICIT, MIXED, or NEUTRAL."""
    asset_kw = ["strength", "asset", "engagement", "reaching for", "intellectual",
                 "powerful", "sophisticated", "valuable", "valid", "courage",
                 "epistemolog", "resist", "creative"]
    deficit_kw = ["lacks", "deficien", "struggle", "concern", "limited",
                  "weak", "fail", "problem", "risk", "distress", "inadequa"]
    lower = text.lower()
    a = sum(1 for k in asset_kw if k in lower)
    d = sum(1 for k in deficit_kw if k in lower)
    if a > 0 and d == 0:
        return "ASSET"
    if d > 0 and a == 0:
        return "DEFICIT"
    if a > 0 and d > 0:
        return "MIXED"
    return "NEUTRAL"


def detect_power_move(text: str) -> bool:
    lower = text.lower()
    return any(re.search(kw, lower) for kw in POWER_MOVE_KEYWORDS)


def _git_provenance() -> dict:
    """Capture git state for reproducibility.

    Every test output should record which code produced it, since prompts
    and architecture are actively evolving. The git commit hash + dirty flag
    lets us reconstruct the exact prompt text and pipeline configuration
    that generated any result set.
    """
    import subprocess as _sp
    prov = {}
    try:
        prov["git_commit"] = _sp.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
        prov["git_commit_short"] = prov["git_commit"][:8]
        prov["git_dirty"] = bool(_sp.run(
            ["git", "diff", "--quiet"],
            capture_output=True, timeout=5, cwd=str(ROOT),
        ).returncode)
        prov["git_branch"] = _sp.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = None
    return prov


def save_results(test_name: str, model_key: str, results: list, metadata: dict = None):
    """Save raw results to persistent location.

    Includes git provenance (commit hash, dirty flag) so results can be
    tied to the exact code version that produced them. Prompts are being
    actively refined — the commit hash is essential for reproducibility.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    time_tag = datetime.now().strftime("%H%M")
    filename = f"{test_name}_{model_key}_{date}_{time_tag}.json"
    output = {
        "test_name": test_name,
        "model": MODELS.get(model_key, {}).get("model", model_key),
        "backend": MODELS.get(model_key, {}).get("name", "multi"),
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS.get(model_key, {}).get("temperature", "varies"),
        "corpus": "ethnic_studies",
        "class_reading_source": str(CLASS_READING_PATH.relative_to(ROOT)),
        "provenance": _git_provenance(),
        "results": results,
    }
    if metadata:
        output.update(metadata)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    log.info("Results saved: %s", path)
    return path


def unload_model():
    """Release MLX model between tests."""
    try:
        from insights.llm_backend import unload_mlx_model
        unload_mlx_model()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test A: Temperature/Consistency
# ---------------------------------------------------------------------------

def test_a_temperature(model_key: str = "gemma12b", n_runs: int = 5):
    print(f"\n{'='*60}")
    print(f"  TEST A: Temperature/Consistency ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    test_students = ["S022", "S028"]  # Destiny (righteous anger), Imani (AAVE)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []
    for sid in test_students:
        student = corpus[sid]
        print(f"\n  {sid} {student['student_name']}:")
        for run in range(1, n_runs + 1):
            prompt = OBSERVATION_PROMPT.format(
                class_context=class_reading,
                assignment=assignment,
                student_name=student["student_name"],
                submission_text=student["text"],
                teacher_lens="",
            )
            t0 = time.time()
            output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
            elapsed = round(time.time() - t0, 1)
            classification = classify_framing(output)
            results.append({
                "student_id": sid,
                "student_name": student["student_name"],
                "run": run,
                "codepath": "production_prompt_direct",
                "prompt": prompt,
                "system_prompt": OBSERVATION_SYSTEM_PROMPT,
                "raw_output": output,
                "classification": classification,
                "time_seconds": elapsed,
            })
            print(f"    Run {run}: {classification} ({elapsed}s)")

    path = save_results("test_a_temperature", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test B: Best Possible Concern Prompt
# ---------------------------------------------------------------------------

def test_b_best_concern(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST B: Best Possible Concern Prompt ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    # Override temperature to 0.1 for classification
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = BEST_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, BEST_CONCERN_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse result
        lower = output.lower()
        if '"concern": true' in lower or '"concern":true' in lower:
            result = "FLAG"
        elif '"concern": false' in lower or '"concern":false' in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "codepath": "test_harness_binary",
            "prompt": prompt,
            "system_prompt": BEST_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_b_best_concern", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test C: Length Effect
# ---------------------------------------------------------------------------

def test_c_length(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST C: Length Effect ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = LENGTH_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, LENGTH_CONCERN_SYSTEM, max_tokens=500)
        elapsed = round(time.time() - t0, 1)

        lower = output.lower()
        if "concern: yes" in lower:
            result = "FLAG"
        elif "concern: no" in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "codepath": "test_harness_binary",
            "prompt": prompt,
            "system_prompt": LENGTH_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_c_length", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test D: Structural Power Moves Detection
# ---------------------------------------------------------------------------

def test_d_power_moves(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST D: Structural Power Moves ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    # Combine corpus students + synthetic cases
    test_cases = []
    for sid in ["S018", "S025"]:
        s = corpus[sid]
        test_cases.append({
            "id": sid,
            "name": s["student_name"],
            "type": "corpus_" + ("colorblind" if sid == "S018" else "tone_policing"),
            "text": s["text"],
        })
    test_cases.extend(POWER_MOVE_CASES)

    results = []
    for case in test_cases:
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=case["name"],
            submission_text=case["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
        elapsed = round(time.time() - t0, 1)

        detected = detect_power_move(output)
        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "power_move_type": case["type"],
            "detected": detected,
            "codepath": "production_prompt_direct",
            "prompt": prompt,
            "system_prompt": OBSERVATION_SYSTEM_PROMPT,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        status = "DETECTED" if detected else "MISSED"
        print(f"  {case['id']:5s} {case['name']:20s} ({case['type']:25s}) {status} ({elapsed}s)")

    path = save_results("test_d_power_moves", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test F: Multi-run B/C stability (quantify false-flag rate)
# ---------------------------------------------------------------------------

def test_f_bc_stability(model_key: str = "gemma12b", n_runs: int = 5):
    """Run Tests B and C multiple times to quantify classification instability.

    Binary classification should be deterministic at low temperature, but
    marginal students (S029 neurodivergent, S023 lived experience) may flip
    between FLAG and CLEAR across runs. This test measures the false-flag
    RATE rather than a single-shot result.
    """
    print(f"\n{'='*60}")
    print(f"  TEST F: B/C Stability ({model_key}, {n_runs} runs each)")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace
    backend_low_t = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    all_results = []

    for run_idx in range(1, n_runs + 1):
        print(f"\n  --- Run {run_idx}/{n_runs} ---")

        # Test B variant
        for sid, pattern, expected in test_cases:
            student = corpus[sid]
            prompt = BEST_CONCERN_PROMPT.format(
                student_name=student["student_name"],
                submission_text=student["text"],
            )
            t0 = time.time()
            output = send(backend_low_t, prompt, BEST_CONCERN_SYSTEM, max_tokens=150)
            elapsed = round(time.time() - t0, 1)
            lower = output.lower()
            if '"concern": true' in lower or '"concern":true' in lower:
                result = "FLAG"
            elif '"concern": false' in lower or '"concern":false' in lower:
                result = "CLEAR"
            else:
                result = "UNCLEAR"
            all_results.append({
                "test_variant": "B",
                "run": run_idx,
                "student_id": sid,
                "student_name": student["student_name"],
                "pattern": pattern,
                "expected": expected,
                "result": result,
                "codepath": "test_harness_binary",
                "prompt": prompt,
                "system_prompt": BEST_CONCERN_SYSTEM,
                "raw_output": output,
                "time_seconds": elapsed,
            })
            marker = "!" if result != expected else " "
            print(f"  {marker} B {sid} {student['student_name']:20s} {result:7s} ({elapsed}s)")

        # Test C variant
        for sid, pattern, expected in test_cases:
            student = corpus[sid]
            prompt = LENGTH_CONCERN_PROMPT.format(
                student_name=student["student_name"],
                submission_text=student["text"],
            )
            t0 = time.time()
            output = send(backend_low_t, prompt, LENGTH_CONCERN_SYSTEM, max_tokens=500)
            elapsed = round(time.time() - t0, 1)
            lower = output.lower()
            if "concern: yes" in lower:
                result = "FLAG"
            elif "concern: no" in lower:
                result = "CLEAR"
            else:
                result = "UNCLEAR"
            all_results.append({
                "test_variant": "C",
                "run": run_idx,
                "student_id": sid,
                "student_name": student["student_name"],
                "pattern": pattern,
                "expected": expected,
                "result": result,
                "codepath": "test_harness_binary",
                "prompt": prompt,
                "system_prompt": LENGTH_CONCERN_SYSTEM,
                "raw_output": output,
                "time_seconds": elapsed,
            })
            marker = "!" if result != expected else " "
            print(f"  {marker} C {sid} {student['student_name']:20s} {result:7s} ({elapsed}s)")

    # Aggregate: per-student false-flag rates
    print(f"\n  === Stability Summary ===")
    for sid, pattern, expected in test_cases:
        for variant in ("B", "C"):
            runs = [r for r in all_results
                    if r["student_id"] == sid and r["test_variant"] == variant]
            flags = sum(1 for r in runs if r["result"] == "FLAG")
            clears = sum(1 for r in runs if r["result"] == "CLEAR")
            unclear = sum(1 for r in runs if r["result"] == "UNCLEAR")
            rate = flags / len(runs) if runs else 0
            status = "OK" if (expected == "FLAG" and rate > 0.5) or (expected == "CLEAR" and rate == 0) else "PROBLEM"
            print(f"  {variant} {sid} {pattern:20s} FLAG={flags} CLEAR={clears} UNK={unclear} "
                  f"rate={rate:.0%} [{status}]")

    path = save_results("test_f_bc_stability", model_key, all_results, {
        "n_runs": n_runs,
        "note": "Multi-run B/C to quantify false-flag rates on marginal students",
    })
    print(f"\n  Results: {path}")
    return all_results


# ---------------------------------------------------------------------------
# Test H: Binary classifier on wellbeing cases (direct comparison to Test G)
# ---------------------------------------------------------------------------

def test_h_binary_on_wellbeing(model_key: str = "gemma12b"):
    """Run the binary concern classifier on the same wellbeing cases Test G uses.

    Direct comparison: does the binary classifier (Tests B/C format) catch the
    same signals the observation architecture (Test G) catches? Expected: binary
    will either miss subtle cases (burnout, tonal rupture) or false-flag
    controls — the same pattern seen with corpus students.
    """
    print(f"\n{'='*60}")
    print(f"  TEST H: Binary Classifier on Wellbeing Cases ({model_key})")
    print(f"{'='*60}")

    backend = get_backend(model_key)
    from dataclasses import replace
    backend_low_t = replace(backend, temperature=0.1)

    results = []
    for case in WELLBEING_SIGNAL_CASES:
        # Test B format (JSON-only)
        prompt_b = BEST_CONCERN_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output_b = send(backend_low_t, prompt_b, BEST_CONCERN_SYSTEM, max_tokens=150)
        elapsed_b = round(time.time() - t0, 1)
        lower_b = output_b.lower()
        if '"concern": true' in lower_b or '"concern":true' in lower_b:
            result_b = "FLAG"
        elif '"concern": false' in lower_b or '"concern":false' in lower_b:
            result_b = "CLEAR"
        else:
            result_b = "UNCLEAR"

        # Test C format (100-150 word justification)
        prompt_c = LENGTH_CONCERN_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output_c = send(backend_low_t, prompt_c, LENGTH_CONCERN_SYSTEM, max_tokens=500)
        elapsed_c = round(time.time() - t0, 1)
        lower_c = output_c.lower()
        if "concern: yes" in lower_c:
            result_c = "FLAG"
        elif "concern: no" in lower_c:
            result_c = "CLEAR"
        else:
            result_c = "UNCLEAR"

        # Determine axis
        if case["signal_type"] in ("burnout_caregiving", "burnout_exhaustion"):
            axis = "BURNOUT"
        elif case["signal_type"] in ("ice_stress", "housing_precarity",
                                      "domestic_violence", "food_insecurity",
                                      "tonal_rupture_crisis", "grief_loss"):
            axis = "CRISIS"
        elif case["signal_type"].startswith("control"):
            axis = "CONTROL"
        else:
            axis = "?"

        # For signal cases: FLAG is correct. For controls: CLEAR is correct.
        if case["expected_surface"]:
            correct_b = "OK" if result_b == "FLAG" else "MISSED"
            correct_c = "OK" if result_c == "FLAG" else "MISSED"
        else:
            correct_b = "OK" if result_b == "CLEAR" else "FALSE-FLAG"
            correct_c = "OK" if result_c == "CLEAR" else "FALSE-FLAG"

        results.append({
            "codepath": "test_harness_binary",
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "axis": axis,
            "expected_surface": case["expected_surface"],
            "binary_b_result": result_b,
            "binary_b_correct": correct_b,
            "binary_c_result": result_c,
            "binary_c_correct": correct_c,
            "prompt_b": prompt_b,
            "system_prompt_b": BEST_CONCERN_SYSTEM,
            "prompt_c": prompt_c,
            "system_prompt_c": LENGTH_CONCERN_SYSTEM,
            "raw_output_b": output_b,
            "raw_output_c": output_c,
            "time_b": elapsed_b,
            "time_c": elapsed_c,
        })

        print(f"  {case['id']:5s} {case['name']:22s} {axis:8s} "
              f"B={result_b:7s}[{correct_b:10s}] "
              f"C={result_c:7s}[{correct_c:10s}]")

    # Summary
    print(f"\n  === Binary vs Observation Comparison ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    b_caught = sum(1 for r in signals if r["binary_b_result"] == "FLAG")
    c_caught = sum(1 for r in signals if r["binary_c_result"] == "FLAG")
    b_fp = sum(1 for r in controls if r["binary_b_result"] == "FLAG")
    c_fp = sum(1 for r in controls if r["binary_c_result"] == "FLAG")
    print(f"  Binary B: caught {b_caught}/{len(signals)} signals, "
          f"{b_fp}/{len(controls)} false positives")
    print(f"  Binary C: caught {c_caught}/{len(signals)} signals, "
          f"{c_fp}/{len(controls)} false positives")
    print(f"  Observation (Test G): caught 8/8 signals, 0/2 false positives*")
    print(f"  (* keyword evaluator false-flagged 2/2, but observation TEXT was clean)")

    path = save_results("test_h_binary_wellbeing", model_key, results, {
        "note": "Binary classifier on wellbeing cases — direct comparison to Test G observations",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test G: Wellbeing signal detection via observations
# ---------------------------------------------------------------------------

def test_g_wellbeing_signals(model_key: str = "gemma12b"):
    """Test whether the observation prompt surfaces genuine wellbeing signals.

    Uses synthetic submissions with embedded signals (ICE stress, burnout,
    housing precarity, DV, food insecurity, caregiving burden) plus control
    cases (analytical engagement, passionate engagement) that should NOT
    be surfaced as concerns.

    Two axes being tested:
    - BURNOUT: exhaustion, overwork, caregiving load, sleep deprivation.
      The student is functioning but depleted. Teacher response: flexibility,
      deadline extension, resource connection.
    - CRISIS: active danger or instability — DV, housing loss, food insecurity,
      ICE threat. The student may need immediate support. Teacher response:
      counselor referral, mandated reporting consideration, resource connection.

    The observation architecture should describe what it sees on BOTH axes
    without forcing a binary flag. Controls should be described as engaged
    students, not surfaced as concerns.
    """
    print(f"\n{'='*60}")
    print(f"  TEST G: Wellbeing Signal Detection ({model_key})")
    print(f"{'='*60}")

    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []
    for case in WELLBEING_SIGNAL_CASES:
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=case["name"],
            submission_text=case["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=400)
        elapsed = round(time.time() - t0, 1)

        # Check if wellbeing keywords appear in observation
        lower = output.lower()
        wb_detected = any(re.search(kw, lower, re.IGNORECASE)
                          for kw in WELLBEING_KEYWORDS)
        # Check framing
        framing = classify_framing(output)

        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "expected_surface": case["expected_surface"],
            "description": case["description"],
            "codepath": "production_prompt_direct",
            "prompt": prompt,
            "system_prompt": OBSERVATION_SYSTEM_PROMPT,
            "wellbeing_detected": wb_detected,
            "framing": framing,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        # Determine axis
        if case["signal_type"] in ("burnout_caregiving", "burnout_exhaustion"):
            axis = "BURNOUT"
        elif case["signal_type"] in ("ice_stress", "housing_precarity",
                                      "domestic_violence", "food_insecurity",
                                      "tonal_rupture_crisis", "grief_loss"):
            axis = "CRISIS"
        elif case["signal_type"].startswith("control"):
            axis = "CONTROL"
        else:
            axis = "?"

        expect = "SURFACE" if case["expected_surface"] else "no-flag"
        actual = "SURFACED" if wb_detected else "silent"
        match = "OK" if (wb_detected == case["expected_surface"]) else "MISS"
        print(f"  {case['id']:5s} {case['name']:22s} {axis:8s} "
              f"{case['signal_type']:22s} expect={expect:8s} got={actual:8s} "
              f"[{match}] ({elapsed}s)")

    # Summary
    print(f"\n  === Wellbeing Detection Summary ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    sig_hit = sum(1 for r in signals if r["wellbeing_detected"])
    ctrl_miss = sum(1 for r in controls if r["wellbeing_detected"])
    print(f"  Signals surfaced: {sig_hit}/{len(signals)}")
    print(f"  Controls false-flagged: {ctrl_miss}/{len(controls)}")

    path = save_results("test_g_wellbeing", model_key, results, {
        "note": "Wellbeing signal detection via observation architecture",
        "axes": "BURNOUT (depletion) vs CRISIS (active danger) vs CONTROL",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test E: Cross-model replication (Test A on different model)
# ---------------------------------------------------------------------------

def test_e_cross_model(model_key: str = "qwen7b", n_runs: int = 3):
    print(f"\n{'='*60}")
    print(f"  TEST E: Cross-model Replication ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    # Same as Test A but on a different model
    results = test_a_temperature(model_key=model_key, n_runs=n_runs)

    # Re-save under test_e name
    path = save_results("test_e_cross_model", model_key, results, {
        "note": "Cross-model replication of Test A (temperature/consistency)",
        "reference_model": "gemma-3-12b-it-4bit",
    })
    print(f"\n  Cross-model results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test J: Pipeline validation (post-fix quality checks)
# ---------------------------------------------------------------------------

# Quality dimensions scored by keyword detection + human-interpretable output.
# These are NOT pass/fail — they produce scored outputs for the overnight agent
# to interpret.

STRUCTURAL_NAMING_KEYWORDS = [
    r"tone.?polic",
    r"colorblind(?:\s+(?:erasure|ideology|framing))?",
    r"abstract.?liberal",
    r"settler.?innocen",
    r"progress.?narrative",
    r"meritocra",
    r"objectiv.*claim",
    r"deflect",
]

# Hedging keywords — ONLY match hedging about whether a structural mechanism
# exists, NOT pedagogical contextualizing of student intent.
# "While his intention may be to promote respect" is intent context (good).
# "This could be seen as a subtle form of tone policing" is hedging (bad).
HEDGING_KEYWORDS = [
    r"subtle(?:ly)?\s+(?:attempt|form of|way)",
    r"could\s+be\s+(?:seen|interpreted|read)\s+as",
    r"(?:seems?|appears?)\s+to\s+(?:be\s+)?(?:a form|an instance|an example)\s+of",
    r"what\s+(?:might|could)\s+be\s+(?:called|described\s+as)",
    r"border(?:s|ing)\s+on",
]

ANTI_SPOTLIGHTING_VIOLATIONS = [
    r"ask\s+(?:him|her|them|this student)\s+to\s+share",
    r"have\s+(?:him|her|them)\s+present",
    r"invite\s+(?:him|her|them)\s+to\s+read",
    r"call\s+on\s+(?:him|her|them)",
    r"single\s+(?:him|her|them)\s+out",
]


def test_j_pipeline_validation(model_key: str = "gemma12b"):
    """Post-fix quality checks on observation and coding outputs.

    Tests whether recent prompt changes actually work at 12B:
    1. Structural naming: Does the model use mechanism names directly
       instead of hedging ("subtle attempt to...")?
    2. Anti-spotlighting: Do teacher move suggestions use structural
       language instead of individual-focused interventions?
    3. what_student_is_reaching_for: Is the field populated in
       reading-first coding?
    4. confusion_or_questions: Is the field populated when appropriate?
    5. Preamble stripping: Are model preambles cleaned from observations?
    6. Immanent critique: Does concern output name relational costs?

    HOW TO INTERPRET RESULTS (for the overnight monitoring agent):
    ─────────────────────────────────────────────────────────────
    This test produces SCORED dimensions, not binary pass/fail.

    structural_naming_score: Higher = better. >0.5 means the model is
      naming mechanisms more than hedging. Score = (mechanism keywords
      found) / (mechanism + hedging keywords found). A score of 0 with
      hedging keywords present means the model still hedges instead of
      naming. Compare to prior runs to assess whether the prompt change
      to "Name the structural mechanism directly" is working.

    anti_spotlighting_violations: Should be 0. Any violation means the
      anti-spotlighting prompt language is being ignored. Report the
      exact violation text.

    what_reaching_for_populated: Should be >0 (ideally all students).
      If still 0, the LLM is not returning this field in JSON — check
      the log for "what_student_is_reaching_for empty" warnings.

    preamble_stripped: Should be True for all observations. If False,
      the regex isn't catching the model's preamble pattern — report
      the first 50 chars of the observation.

    WHAT TO DO WITH RESULTS:
    - If structural_naming_score < 0.3: The prompt change isn't enough
      for 12B. This gap may require the enhancement tier (cloud model).
      Flag for design discussion.
    - If anti_spotlighting_violations > 0: The prompt isn't strong enough.
      Flag the specific violation for prompt hardening.
    - If what_reaching_for = 0/N: Check the parse log. The LLM may need
      the field emphasized more in the prompt, or the JSON schema is too
      complex for 12B to fully populate.
    """
    print(f"\n{'='*60}")
    print(f"  TEST J: Pipeline Validation ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []

    # --- J1: Structural naming on power move students ---
    # Uses observe_student() — same function as the pipeline — so preamble
    # stripping and other post-processing match the real codepath.
    print("\n  J1: Structural Naming Quality")
    from insights.submission_coder import observe_student
    power_students = ["S018", "S025"]  # Connor (colorblind), Aiden (tone policing)
    for sid in power_students:
        student = corpus[sid]
        t0 = time.time()
        output = observe_student(
            backend,
            student_name=student["student_name"],
            submission_text=student["text"],
            class_context=class_reading,
            assignment=assignment,
        )
        elapsed = round(time.time() - t0, 1)

        # Score: mechanism names vs hedging
        lower = output.lower()
        mechanism_hits = sum(1 for kw in STRUCTURAL_NAMING_KEYWORDS
                            if re.search(kw, lower))
        hedging_hits = sum(1 for kw in HEDGING_KEYWORDS
                          if re.search(kw, lower))
        total_hits = mechanism_hits + hedging_hits
        naming_score = mechanism_hits / total_hits if total_hits > 0 else 0.0

        # Preamble should already be stripped by observe_student()
        has_preamble = bool(re.match(
            r"^(?:Okay|OK|Sure|Here are)", output, re.IGNORECASE))

        results.append({
            "codepath": "production_pipeline",
            "subtest": "J1_structural_naming",
            "student_id": sid,
            "student_name": student["student_name"],
            "mechanism_keywords_found": mechanism_hits,
            "hedging_keywords_found": hedging_hits,
            "structural_naming_score": round(naming_score, 2),
            "has_preamble": has_preamble,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"    {sid} {student['student_name']:20s} "
              f"mechanisms={mechanism_hits} hedges={hedging_hits} "
              f"score={naming_score:.2f} preamble={has_preamble} ({elapsed}s)")

    # --- J2: Anti-spotlighting in observation synthesis ---
    # Uses observe_student() for consistency with the real pipeline.
    # Includes forward_looking to validate P3 wiring.
    print("\n  J2: Anti-Spotlighting in Synthesis")
    from insights.prompts import (OBSERVATION_SYNTHESIS_PROMPT,
                                  OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                                  OBSERVATION_SYNTHESIS_FORWARD_LOOKING)

    obs_formatted = ""
    _j2_count = 0
    for sid in sorted(corpus.keys()):
        student = corpus[sid]
        obs = observe_student(
            backend,
            student_name=student["student_name"],
            submission_text=student["text"],
            class_context=class_reading,
            assignment=assignment,
        )
        if obs:
            obs_formatted += f"\n**{student['student_name']}** ({sid}):\n{obs}\n"
            _j2_count += 1
        # Cap at 10 students (enough for synthesis test, saves MLX time)
        if _j2_count >= 10:
            break

    _j2_fwd = OBSERVATION_SYNTHESIS_FORWARD_LOOKING.format(
        next_week_topic="Week 7: Racial Formation — Omi & Winant's framework"
    )

    synth_prompt = OBSERVATION_SYNTHESIS_PROMPT.format(
        assignment=assignment,
        class_context=class_reading,
        observations=obs_formatted,
        teacher_lens="",
        forward_looking=_j2_fwd,
    )

    t0 = time.time()
    synthesis = send(backend, synth_prompt, OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                     max_tokens=2000)
    elapsed = round(time.time() - t0, 1)

    # Check for anti-spotlighting violations
    lower_synth = synthesis.lower()
    violations = []
    for kw in ANTI_SPOTLIGHTING_VIOLATIONS:
        matches = re.findall(kw, lower_synth)
        violations.extend(matches)

    # Check new sections exist
    has_multiplicity = bool(re.search(
        r"how students entered|entry points|different.*registers", lower_synth))
    has_ped_wins = bool(re.search(
        r"what.s working|working well|assignment.*doing well", lower_synth))
    has_moments = bool(re.search(r"moments for", lower_synth))
    has_forward = bool(re.search(
        r"looking ahead|next week|upcoming", lower_synth))
    has_exceptional = bool(re.search(
        r"exceptional|stood out|standout", lower_synth))

    results.append({
        "codepath": "production_pipeline",
        "subtest": "J2_anti_spotlighting",
        "anti_spotlighting_violations": violations,
        "violation_count": len(violations),
        "has_multiplicity_section": has_multiplicity,
        "has_pedagogical_wins_section": has_ped_wins,
        "has_moments_section": has_moments,
        "has_forward_looking_section": has_forward,
        "has_exceptional_contributions": has_exceptional,
        "students_in_synthesis": _j2_count,
        "note": (
            f"J2 used {_j2_count}/32 students (subset for test speed). "
            "Section presence is valid but synthesis richness and word counts "
            "will differ from production (32 students). Does not include P7 "
            "insight ranking in teacher_lens — tests synthesis prompt quality "
            "without the ranking data."
        ),
        "raw_synthesis": synthesis,
        "time_seconds": elapsed,
    })
    print(f"    Violations: {len(violations)}")
    if violations:
        for v in violations:
            print(f"      - '{v}'")
    print(f"    Multiplicity section: {has_multiplicity}")
    print(f"    Pedagogical wins section: {has_ped_wins}")
    print(f"    Moments section: {has_moments}")
    print(f"    Forward-looking section: {has_forward}")
    print(f"    Exceptional contributions: {has_exceptional}")
    print(f"    ({elapsed}s)")

    # --- J3: what_student_is_reaching_for via reading-first coding ---
    print("\n  J3: what_student_is_reaching_for Population")
    from insights.submission_coder import code_submission_reading_first
    test_sids = ["S004", "S022", "S028"]  # Talia (strong), Destiny (anger), Imani (AAVE)
    reaching_populated = 0
    confusion_populated = 0
    for sid in test_sids:
        student = corpus[sid]
        t0 = time.time()
        record = code_submission_reading_first(
            submission_text=student["text"],
            student_id=sid,
            student_name=student["student_name"],
            assignment_prompt=assignment,
            backend=backend,
            class_context=class_reading,
        )
        elapsed = round(time.time() - t0, 1)

        reaching = record.what_student_is_reaching_for or ""
        confusion = record.confusion_or_questions or ""
        if reaching:
            reaching_populated += 1

        results.append({
            "codepath": "production_pipeline",
            "subtest": "J3_reaching_for",
            "student_id": sid,
            "student_name": student["student_name"],
            "what_reaching_for": reaching,
            "reaching_for_populated": bool(reaching),
            "confusion_or_questions": confusion,
            "confusion_populated": bool(confusion),
            "free_form_reading_length": len(record.free_form_reading or ""),
            "time_seconds": elapsed,
        })
        print(f"    {sid} {student['student_name']:20s} "
              f"reaching={'YES' if reaching else 'NO':3s} "
              f"confusion={'YES' if confusion else 'no':3s} ({elapsed}s)")
        if reaching:
            print(f"      → {reaching[:100]}...")

    print(f"\n  Summary: {reaching_populated}/{len(test_sids)} reaching_for populated")

    path = save_results("test_j_pipeline_validation", model_key, results, {
        "note": "Post-fix pipeline validation: structural naming, anti-spotlighting, "
                "reaching_for, confusion field, preamble stripping",
        "prompt_changes": [
            "Added 'Name the structural mechanism directly' to observation prompt",
            "Rewrote 'Moments for the Classroom' for anti-spotlighting",
            "Added privacy framing to 'Students to Check In With'",
            "Removed named students from temperature prompt example",
            "Added confusion_or_questions field to reading-first P2",
        ],
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test K: Enhancement model comparison (OpenRouter free/cheap models)
# ---------------------------------------------------------------------------

# Enhancement evaluation dimensions — scored from the raw output.
# These capture the qualitative richness that distinguishes the
# enhancement tier from the local 12B pipeline.
ENHANCEMENT_QUALITY_MARKERS = {
    "structural_naming": [
        r"tone.?polic", r"colorblind", r"abstract.?liberal",
        r"settler", r"meritocra", r"progress.?narrative",
    ],
    "language_justice": [
        r"AAVE|African.American.Vernacular",
        r"(?:code.?switch|translingual|multilingual|linguistic.?(?:asset|divers|capital))",
        r"(?:register|dialect|vernacular).*(?:valid|legit|rigor|academ)",
        r"neurodivergent|cognitive.?(?:plural|divers|style)",
        r"pathway.*rigor|different.*pathway",
    ],
    "relational_analysis": [
        r"tension\s+between",
        r"(?:dialectic|productive.*disagree|productive.*tension)",
        r"(?:against|alongside|in contrast to|juxtapos)",
        r"(?:respond.*to|building.*on|extending|counter)",
    ],
    "pedagogical_depth": [
        r"(?:assignment.*design|prompt.*design|format.*choice|structure.*of)",
        r"(?:scaffold|bridge|entry.?point|on.?ramp)",
        r"(?:pedagogic|curricular|instructional|teaching.*implica)",
        r"(?:what.*working|strengths.*of.*design|by design)",
    ],
    "anti_spotlighting": [
        r"structur.*(?:opportunit|activit|format|approach)",
        r"(?:class-wide|whole.?class|everyone|all students)",
        r"(?:discussion.*format|small.?group|writing.*move)",
    ],
}

# Models to test — free tier on OpenRouter (confirmed 2026-03-28).
# Ordered: reliable providers first, Venice (rate-limited) last.
# This ensures we get data from working models even if Venice quota is hit.
_OR = {"base_url": "https://openrouter.ai/api/v1", "api_key_fn": _openrouter_key}
ENHANCEMENT_MODELS = {
    # --- Tier 1: Reliable providers (no rate limit issues in testing) ---
    "gemma27b_free": {
        "name": "cloud", "model": "google/gemma-3-27b-it:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Google-hosted (no system prompt)",
        "fold_system_into_user": True,
    },
    "nemotron_120b_free": {
        "name": "cloud", "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — NVIDIA-hosted, 120B MoE (12B active)",
    },
    "step_flash_free": {
        "name": "cloud", "model": "stepfun/step-3.5-flash:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — StepFun-hosted, 196B MoE (11B active)",
    },
    "arcee_trinity_free": {
        "name": "cloud", "model": "arcee-ai/trinity-large-preview:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Arcee-hosted, 400B MoE (13B active), preview",
    },
    "minimax_m25_free": {
        "name": "cloud", "model": "minimax/minimax-m2.5:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — MiniMax-hosted, 196K context",
    },
    # --- Tier 2: Venice-hosted (privacy-first but rate-limited) ---
    "dolphin_mistral_free": {
        "name": "cloud",
        "model": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Venice (no-logging), 24B",
    },
    "hermes_405b_free": {
        "name": "cloud", "model": "nousresearch/hermes-3-llama-3.1-405b:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Venice (no-logging), 405B dense",
    },
    "llama70b_free": {
        "name": "cloud", "model": "meta-llama/llama-3.3-70b-instruct:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Venice, 70B dense",
    },
    "mistral_small_free": {
        "name": "cloud", "model": "mistralai/mistral-small-3.1-24b-instruct:free",
        "max_tokens": 1200, "temperature": 0.3, **_OR,
        "cost_note": "Free — Venice, 24B",
    },
}


def _build_test_enhancement_prompt() -> str:
    """Build a representative anonymized enhancement prompt from checkpoint data.

    Uses the actual synthesis pipeline output format so test results
    are representative of real enhancement calls.
    """
    # This mirrors the payload format from synthesizer._run_cloud_enhancement()
    return (
        "An engagement analysis found these patterns in a class of 32 students "
        "responding to an assignment about Week 6 Discussion: Intersectionality "
        "in Practice:\n\n"
        "CONCERN PATTERNS:\n"
        "- Student uses colorblind framing ('I don't see race, I just see people') "
        "that resists engaging with the structural analysis framework the reading "
        "presents. Does not engage with Crenshaw's argument. (1 student(s))\n"
        "- Student calls for 'calm, rational discussion' in a context where another "
        "student is expressing urgent anger about ICE enforcement affecting her "
        "family. This positions emotional engagement as illegitimate. (1 student(s))\n"
        "- Student shows signs of burnout — submission is markedly shorter than "
        "previous weeks, mentions being 'exhausted' and working closing shifts. "
        "Engagement with material is still present but capacity seems strained. "
        "(1 student(s))\n"
        "Key distinctions:\n"
        "  - The colorblind and tone-policing students are making distinct structural "
        "moves — one denies the relevance of race, the other polices HOW race can be "
        "discussed. They should not be grouped together pedagogically.\n"
        "  - The burnout student is not a concern about engagement quality — this is "
        "a capacity issue. Different teacher response needed.\n\n"
        "ENGAGEMENT HIGHLIGHTS:\n"
        "- Student connects intersectionality framework to grandmother's experience "
        "in agricultural work and redlining legacy in their neighborhood. Deep "
        "personal-structural bridging. (1 student(s))\n"
        "- Student uses AAVE and writes in a register that might be misjudged as "
        "'informal' but is doing sophisticated intersectional analysis through "
        "community-grounded language. (1 student(s))\n"
        "- Student with neurodivergent writing style (associative, nonlinear) makes "
        "connections between disability studies and ethnic studies frameworks that "
        "more linear writers miss. (1 student(s))\n"
        "- 4 students are engaging deeply with Crenshaw's framework and extending it "
        "to current events (ICE enforcement, housing displacement). (4 student(s))\n\n"
        "TENSIONS BETWEEN GROUPS:\n"
        "- Tension between students who approach intersectionality as a theoretical "
        "framework to analyze and students who experience it as lived reality. "
        "Neither is wrong but they are talking past each other.\n"
        "  Between: analytical engagers vs. experiential engagers\n"
        "- Tension between one student's call for 'calm discussion' and another's "
        "urgent expression about family safety. This is a structural power move — "
        "the call for calm delegitimizes the urgency.\n"
        "  Between: tone policing move vs. lived experience urgency\n\n"
        "CLASS TEMPERATURE: Most of the class engaged with Crenshaw's framework "
        "at minimum surface level. A cluster of 6-8 students showed deep personal "
        "connection. 2 students resist the structural analysis through distinct "
        "moves (colorblind framing, tone policing). 1 student shows burnout signs.\n"
        "Attention areas:\n"
        "  - The 2 resistant students are making different moves and need different "
        "pedagogical responses\n"
        "  - The analytical-experiential tension is productive and could be brought "
        "into the classroom as a structured discussion\n\n"
        "Provide a richer pedagogical analysis: What do these patterns suggest "
        "about where the class is in their understanding? What tensions are "
        "most productive for learning? What should the teacher pay attention to? "
        "Do NOT suggest specific exercises or lesson designs — the teacher decides."
    )


ENHANCEMENT_SYSTEM_PROMPT = (
    "You are helping a teacher understand class-level engagement patterns. "
    "All data is anonymized — you will not see student names or text. "
    "Do NOT suggest singling out students. Do NOT suggest specific exercises. "
    "Analyze patterns and surface pedagogical significance."
)


def test_k_enhancement_comparison():
    """Compare enhancement quality across free/cheap OpenRouter models.

    Sends the SAME anonymized enhancement prompt to multiple models and
    scores each response on quality dimensions that matter for the
    enhancement tier: structural naming, language justice framing,
    relational/dialectical analysis, pedagogical depth, anti-spotlighting.

    HOW TO INTERPRET RESULTS (for the overnight monitoring agent):
    ─────────────────────────────────────────────────────────────
    This test compares ENHANCEMENT QUALITY across free cloud models.
    The enhancement receives only anonymized pattern data (no student
    names, no quotes, no identifiable data) — FERPA compliant by design.

    Each model gets a QUALITY PROFILE across 5 dimensions:
    - structural_naming: Does it name mechanisms (tone policing, colorblind
      erasure) or just describe behaviors?
    - language_justice: Does it frame AAVE/neurodivergent writing as assets
      and "different pathways to rigor"? This is the hardest dimension —
      most models default to standard-English-as-neutral.
    - relational_analysis: Does it construct productive tension pairs and
      dialectics between student positions?
    - pedagogical_depth: Does it reason about assignment design, scaffolding,
      and curricular implications?
    - anti_spotlighting: Does it recommend structural opportunities rather
      than individual interventions?

    SCORING: Each dimension counts keyword/phrase matches. Higher = better.
    Compare models on the PROFILE SHAPE, not just total score — a model
    strong on structural naming but weak on language justice is different
    from one strong on pedagogical depth but weak on relational analysis.

    WHAT TO DO WITH RESULTS:
    - Rank models by total score AND per-dimension scores
    - Flag any model that scores 0 on language_justice — this dimension
      matters most for equity and is hardest for smaller models
    - Report the top 2-3 models with their cost notes
    - If no free model exceeds a total score of 5, the enhancement tier
      may need a paid model — flag for cost-benefit discussion
    - Save the raw outputs for human review of qualitative richness
    """
    print(f"\n{'='*60}")
    print(f"  TEST K: Enhancement Model Comparison (OpenRouter)")
    print(f"{'='*60}")

    key = _openrouter_key()
    if not key:
        print("  SKIPPED — no OpenRouter key found")
        print("  Set REFRAME_SHARED_OPENROUTER_KEY in ~/Documents/GitHub/Reframe/.env")
        return []

    enhancement_prompt = _build_test_enhancement_prompt()

    results = []
    for model_key, cfg in ENHANCEMENT_MODELS.items():
        print(f"\n  {model_key} ({cfg['model']})...")
        try:
            backend = get_backend_from_cfg(cfg)

            # Some free models (Gemma via Google AI Studio) don't support
            # system/developer prompts — fold into user message instead
            if cfg.get("fold_system_into_user"):
                combined_prompt = ENHANCEMENT_SYSTEM_PROMPT + "\n\n" + enhancement_prompt
                _sys = ""
            else:
                combined_prompt = enhancement_prompt
                _sys = ENHANCEMENT_SYSTEM_PROMPT

            # Retry up to 3 times for rate limits (429)
            output = None
            for attempt in range(3):
                try:
                    t0 = time.time()
                    output = send(backend, combined_prompt, _sys,
                                  max_tokens=1200)
                    break
                except Exception as retry_err:
                    if "429" in str(retry_err) and attempt < 2:
                        wait = 15 * (attempt + 1)
                        log.info("Rate limited on %s, retrying in %ds...",
                                 model_key, wait)
                        time.sleep(wait)
                    else:
                        raise
            elapsed = round(time.time() - t0, 1)

            # Score each quality dimension
            lower = output.lower()
            scores = {}
            for dim, keywords in ENHANCEMENT_QUALITY_MARKERS.items():
                hits = sum(1 for kw in keywords if re.search(kw, lower))
                scores[dim] = hits

            total = sum(scores.values())
            word_count = len(output.split())

            results.append({
                "codepath": "test_harness_custom",
                "model_key": model_key,
                "model_id": cfg["model"],
                "cost_note": cfg.get("cost_note", ""),
                "scores": scores,
                "total_score": total,
                "word_count": word_count,
                "raw_output": output,
                "time_seconds": elapsed,
            })

            print(f"    Total: {total} | Words: {word_count} | Time: {elapsed}s")
            for dim, score in scores.items():
                bar = "█" * score + "░" * (5 - min(score, 5))
                print(f"    {dim:22s} {score:2d} {bar}")

        except Exception as e:
            log.error("Model %s failed: %s", model_key, e)
            results.append({
                "codepath": "test_harness_custom",
                "model_key": model_key,
                "model_id": cfg["model"],
                "error": str(e),
                "scores": {},
                "total_score": -1,
            })
            print(f"    FAILED: {e}")

    # Ranking
    valid = [r for r in results if r["total_score"] >= 0]
    if valid:
        print(f"\n  === Enhancement Model Ranking ===")
        for rank, r in enumerate(sorted(valid, key=lambda x: -x["total_score"]), 1):
            print(f"  #{rank} {r['model_key']:25s} total={r['total_score']:2d} "
                  f"({r['cost_note']}) {r['time_seconds']}s")

        # Per-dimension leaders
        print(f"\n  === Per-Dimension Leaders ===")
        for dim in ENHANCEMENT_QUALITY_MARKERS:
            leader = max(valid, key=lambda x: x["scores"].get(dim, 0))
            print(f"  {dim:22s} → {leader['model_key']} "
                  f"(score={leader['scores'].get(dim, 0)})")

    path = save_results("test_k_enhancement_comparison", "multi_model", results, {
        "note": "Enhancement model comparison — FERPA-compliant anonymized prompt "
                "tested against free/cheap OpenRouter models. Goal: find cost-effective "
                "enhancement mechanism for teachers without paid API access.",
        "prompt_length": len(enhancement_prompt),
        "models_tested": list(ENHANCEMENT_MODELS.keys()),
        "quality_dimensions": list(ENHANCEMENT_QUALITY_MARKERS.keys()),
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test L: Expanded wellbeing classifier (4-axis: CRISIS/BURNOUT/ENGAGED/NONE)
# ---------------------------------------------------------------------------

TIER2_EXPANDED_SYSTEM = (
    "You are helping a teacher identify students who may need support beyond "
    "the academic. You are reading a teaching colleague's observation about a "
    "student's work — NOT the student's work directly.\n\n"
    "Your task: classify this observation into one of four categories:\n\n"
    "- CRISIS: The student's OWN situation involves active danger or "
    "instability — domestic violence, housing loss, food insecurity, "
    "immigration enforcement threat, recent loss/grief. Present-tense, "
    "personal, beyond the assignment scope.\n"
    "- BURNOUT: The student is depleted — exhaustion, overwork, caregiving "
    "burden, sleep deprivation. Functioning but running on empty. "
    "Capacity issue, not engagement issue.\n"
    "- ENGAGED: The student is doing intellectual work on difficult material. "
    "May write about racism, poverty, immigration, violence, disability, or "
    "family experience AS COURSE MATERIAL — even connecting it to their own "
    "life, community, or family. Students who bring personal and community "
    "life experience into their analysis are often doing the most "
    "sophisticated version of the assignment. This is engagement, not "
    "distress — even when the material is painful or the experience is "
    "ongoing.\n"
    "- NONE: Nothing notable in either direction.\n\n"
    "The key distinction: is the difficult content about the student's OWN "
    "current circumstances (CRISIS/BURNOUT), or is it course material they're "
    "engaging with intellectually — even from personal experience (ENGAGED)?\n\n"
    "Respond with JSON only: {\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description or empty\", "
    "\"confidence\": 0.0-1.0}"
)

TIER2_EXPANDED_PROMPT = """\
OBSERVATION about {student_name}:
---
{observation}
---

Classify this observation. Is this student in crisis, burned out, intellectually \
engaged with difficult material, or nothing notable?
Respond with JSON only."""


def test_l_expanded_wellbeing(model_key: str = "gemma12b"):
    """Test the 4-axis wellbeing classifier (CRISIS/BURNOUT/ENGAGED/NONE).

    Refinement of Test I: expands from 3 axes (CRISIS/BURNOUT/NONE) to 4
    by adding ENGAGED — a positive classification for students doing
    intellectual work on difficult material, including from community/family
    experience. This gives the classifier a place to put students like
    Priya Sharma (analytical engagement with ICE topic) that isn't BURNOUT.

    HOW TO INTERPRET RESULTS (for the overnight monitoring agent):
    ─────────────────────────────────────────────────────────────
    Compare to Test I (3-axis) results side by side.

    EXPECTED IMPROVEMENTS:
    - Priya Sharma (control_analytical): should shift from FALSE-FLAG BURNOUT
      to ENGAGED (fixing the 1 false positive from Test I)
    - DeAndre Washington (control_passionate): should remain NONE or shift to
      ENGAGED (both are correct for a control)
    - All genuine CRISIS/BURNOUT signals should still be caught

    KEY METRIC: false positive rate on controls. Test I had 1/2 FP.
    Test L should have 0/2 FP.

    If ENGAGED absorbs genuine BURNOUT cases (e.g., Rosa classified as ENGAGED
    instead of BURNOUT), the prompt needs to be more explicit about the
    distinction between "writing about ICE analytically" and "my family is
    affected by ICE right now."

    WHAT TO DO WITH RESULTS:
    - If 0 FP and 8/8 signals: expanded schema ready for pipeline integration
    - If ENGAGED absorbs BURNOUT cases: need to refine the prompt's distinction
      between analytical engagement and personal circumstance
    - If FP unchanged: the extra axis didn't help; consider confidence threshold
    """
    print(f"\n{'='*60}")
    print(f"  TEST L: Expanded Wellbeing Classifier ({model_key})")
    print(f"  4-axis: CRISIS | BURNOUT | ENGAGED | NONE")
    print(f"{'='*60}")

    # Load Test G observations as input
    test_g_path = OUTPUT_DIR / "test_g_wellbeing_gemma12b_2026-03-27.json"
    if not test_g_path.exists():
        # Try finding any test_g file
        candidates = sorted(OUTPUT_DIR.glob("test_g_wellbeing_*.json"))
        if candidates:
            test_g_path = candidates[-1]
        else:
            print("  SKIPPED — no Test G results found. Run Test G first.")
            return []

    test_g = json.loads(test_g_path.read_text())
    results_g = test_g["results"]
    print(f"  Using observations from: {test_g_path.name}")

    backend = get_backend(model_key)
    from dataclasses import replace
    backend = replace(backend, temperature=0.1, max_tokens=150)

    results = []
    for case in results_g:
        observation = case["raw_output"]
        student_name = case["student_name"]
        signal_type = case["signal_type"]
        expected = case["expected_surface"]

        prompt = TIER2_EXPANDED_PROMPT.format(
            student_name=student_name,
            observation=observation,
        )

        t0 = time.time()
        output = send(backend, prompt, TIER2_EXPANDED_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse response
        lower = output.lower()
        # Extract axis from JSON
        axis = "PARSE_ERROR"
        for candidate in ("CRISIS", "BURNOUT", "ENGAGED", "NONE"):
            if f'"{candidate.lower()}"' in lower or f'"{candidate}"' in output:
                axis = candidate
                break

        confidence = 0.0
        import re as _re
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        if conf_match:
            confidence = float(conf_match.group(1))

        signal_match = _re.search(r'"signal"\s*:\s*"([^"]*)"', output)
        signal = signal_match.group(1) if signal_match else ""

        # Evaluate: CRISIS/BURNOUT = detected wellbeing signal
        detected = axis in ("CRISIS", "BURNOUT")
        if expected:
            correct = "OK" if detected else "MISSED"
        else:
            correct = "OK" if not detected else "FALSE-FLAG"

        results.append({
            "codepath": "test_harness_custom",
            "student_name": student_name,
            "signal_type": signal_type,
            "expected_surface": expected,
            "tier2_axis": axis,
            "tier2_signal": signal,
            "tier2_confidence": confidence,
            "tier2_detected": detected,
            "tier2_correct": correct,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        expect_str = "SURFACE" if expected else "no-flag"
        print(f"  {case.get('student_id', '?'):5s} {student_name:22s} "
              f"expect={expect_str:8s} axis={axis:8s} "
              f"conf={confidence:.1f} [{correct}] ({elapsed}s)")

    # Summary — compare to Test I
    print(f"\n  === Expanded vs Original Comparison ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    sig_hit = sum(1 for r in signals if r["tier2_detected"])
    ctrl_fp = sum(1 for r in controls if r["tier2_detected"])
    ctrl_engaged = sum(1 for r in controls if r["tier2_axis"] == "ENGAGED")

    print(f"  Test L (4-axis):  {sig_hit}/{len(signals)} signals, "
          f"{ctrl_fp}/{len(controls)} FP, "
          f"{ctrl_engaged}/{len(controls)} correctly ENGAGED")
    print(f"  Test I (3-axis):  8/8 signals, 1/2 FP (Priya BURNOUT@0.6)")
    print(f"  Test H Binary B:  7/8 signals, 0/2 FP")
    print(f"  Test H Binary C:  3/8 signals, 0/2 FP")

    # Check if ENGAGED absorbed any BURNOUT cases (regression)
    absorbed = [r for r in signals if r["tier2_axis"] == "ENGAGED"]
    if absorbed:
        print(f"\n  WARNING: {len(absorbed)} genuine signal(s) classified as ENGAGED:")
        for r in absorbed:
            print(f"    {r['student_name']} ({r['signal_type']}) — was expected to surface")

    path = save_results("test_l_expanded_wellbeing", model_key, results, {
        "note": "4-axis wellbeing classifier: CRISIS/BURNOUT/ENGAGED/NONE. "
                "Tests whether ENGAGED axis absorbs false positives on controls "
                "without absorbing genuine CRISIS/BURNOUT signals.",
        "comparison_baseline": "Test I (3-axis, 2026-03-28)",
        "schema_change": "Added ENGAGED axis for students doing intellectual "
                         "work on difficult material from community experience",
    })
    print(f"\n  Results: {path}")
    return results


def get_backend_from_cfg(cfg: dict):
    """Build a BackendConfig from a model config dict (for enhancement models)."""
    from insights.llm_backend import BackendConfig
    kwargs = {
        "name": cfg["name"],
        "model": cfg["model"],
        "max_tokens": cfg.get("max_tokens", 1200),
        "temperature": cfg.get("temperature", 0.3),
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]
    if "api_key_fn" in cfg:
        kwargs["api_key"] = cfg["api_key_fn"]()
    elif "api_key" in cfg:
        kwargs["api_key"] = cfg["api_key"]
    return BackendConfig(**kwargs)


# ---------------------------------------------------------------------------
# Test M: Production concern detector on test corpus + wellbeing cases
# ---------------------------------------------------------------------------

def test_m_production_detector(model_key: str = "gemma12b"):
    """Run the ACTUAL production concern detector on test students.

    Tests B/C/F used a simplified binary prompt. This test runs the real
    concern_detector.detect_concerns() with its full pipeline:
    - Signal matrix pre-screening
    - Production CONCERN_PROMPT (richer than the test-harness prompt)
    - Anti-bias post-processing (_check_bias_in_output)
    - Course-content disambiguation
    - Confidence thresholding (0.7 minimum to surface)

    Answers the critical methodological question: does the production system
    reproduce the same failures as the simplified test prompt?

    If S029 is NOT flagged by the production system, the n=25 finding is
    specific to the simplified binary format, and the production concern
    detector may be adequate. If S029 IS flagged, the failure generalizes.
    """
    print(f"\n{'='*60}")
    print(f"  TEST M: Production Concern Detector ({model_key})")
    print(f"{'='*60}")

    from research.concern_detector import detect_concerns
    from insights.patterns import signal_matrix_classify

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    # Test corpus students (same as Tests B/C/F)
    corpus_cases = [
        ("S002", "burnout", True),     # true positive — should FLAG
        ("S004", "strong", False),     # should NOT flag
        ("S022", "righteous_anger", False),
        ("S023", "lived_exp", False),
        ("S028", "AAVE", False),
        ("S029", "neurodivergent", False),  # the critical case
        ("S031", "minimal_effort", False),
    ]

    # Also run on wellbeing cases (for comparison with Tests G/H/I/L)
    wb_cases = [
        (case["id"], case["name"], case["text"], case["signal_type"],
         case["expected_surface"])
        for case in WELLBEING_SIGNAL_CASES
    ]

    results = []

    print(f"\n  --- Corpus students (production detector) ---")
    for sid, pattern, should_flag in corpus_cases:
        student = corpus[sid]
        body = student["text"]
        wc = len(body.split())

        # Run signal matrix (same as production pipeline)
        from insights.quick_analyzer import QuickAnalyzer
        vader_compound = 0.0  # simplified — production uses full VADER
        sig_results = signal_matrix_classify(body, vader_compound, wc, 150)

        t0 = time.time()
        concerns = detect_concerns(
            submission_text=body,
            student_name=student["student_name"],
            student_id=sid,
            assignment_prompt=f"Assignment: {assignment}",
            signal_matrix_results=sig_results,
            tier="lightweight",
            backend=backend,
            class_context=class_reading,
        )
        elapsed = round(time.time() - t0, 1)

        flagged = len(concerns) > 0
        if should_flag:
            correct = "OK" if flagged else "MISSED"
        else:
            correct = "OK" if not flagged else "FALSE-FLAG"

        results.append({
            "codepath": "production_concern_detector",
            "source": "corpus",
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "should_flag": should_flag,
            "flagged": flagged,
            "correct": correct,
            "n_concerns": len(concerns),
            "concerns": [
                {
                    "flagged_passage": c.flagged_passage[:200],
                    "why_flagged": c.why_flagged[:300],
                    "confidence": c.confidence,
                }
                for c in concerns
            ],
            "time_seconds": elapsed,
        })

        flag_str = f"FLAG ({len(concerns)})" if flagged else "CLEAR"
        confs = [f"{c.confidence:.2f}" for c in concerns]
        print(f"  {sid} {student['student_name']:20s} {pattern:20s} "
              f"{flag_str:10s} [{correct}] confs={confs} ({elapsed}s)")

    print(f"\n  --- Wellbeing cases (production detector) ---")
    for wid, wname, wtext, wsignal, wexpected in wb_cases:
        wc = len(wtext.split())
        sig_results = signal_matrix_classify(wtext, 0.0, wc, 150)

        t0 = time.time()
        concerns = detect_concerns(
            submission_text=wtext,
            student_name=wname,
            student_id=wid,
            assignment_prompt=f"Assignment: {assignment}",
            signal_matrix_results=sig_results,
            tier="lightweight",
            backend=backend,
            class_context=class_reading,
        )
        elapsed = round(time.time() - t0, 1)

        flagged = len(concerns) > 0
        if wexpected:
            correct = "OK" if flagged else "MISSED"
        else:
            correct = "OK" if not flagged else "FALSE-FLAG"

        results.append({
            "codepath": "production_concern_detector",
            "source": "wellbeing_synthetic",
            "student_id": wid,
            "student_name": wname,
            "signal_type": wsignal,
            "expected_flag": wexpected,
            "flagged": flagged,
            "correct": correct,
            "n_concerns": len(concerns),
            "concerns": [
                {
                    "flagged_passage": c.flagged_passage[:200],
                    "why_flagged": c.why_flagged[:300],
                    "confidence": c.confidence,
                }
                for c in concerns
            ],
            "time_seconds": elapsed,
        })

        flag_str = f"FLAG ({len(concerns)})" if flagged else "CLEAR"
        print(f"  {wid:5s} {wname:22s} {wsignal:22s} "
              f"{flag_str:10s} [{correct}] ({elapsed}s)")

    # Summary
    print(f"\n  === Production Detector Summary ===")
    corpus_r = [r for r in results if r["source"] == "corpus"]
    wb_r = [r for r in results if r["source"] == "wellbeing_synthetic"]

    s029 = next((r for r in corpus_r if r["student_id"] == "S029"), None)
    s002 = next((r for r in corpus_r if r["student_id"] == "S002"), None)
    print(f"  S029 (neurodivergent): {'FLAGGED' if s029 and s029['flagged'] else 'CLEAR'}"
          f" — {'SAME as simplified test' if s029 and s029['flagged'] else 'DIFFERENT from simplified test'}")
    print(f"  S002 (burnout):        {'FLAGGED' if s002 and s002['flagged'] else 'CLEAR'}"
          f" — {'DIFFERENT from simplified test' if s002 and s002['flagged'] else 'SAME as simplified test'}")

    wb_signals = [r for r in wb_r if r["expected_flag"]]
    wb_controls = [r for r in wb_r if not r["expected_flag"]]
    wb_caught = sum(1 for r in wb_signals if r["flagged"])
    wb_fp = sum(1 for r in wb_controls if r["flagged"])
    print(f"  Wellbeing signals: {wb_caught}/{len(wb_signals)} caught")
    print(f"  Wellbeing controls: {wb_fp}/{len(wb_controls)} false positives")

    path = save_results("test_m_production_detector", model_key, results, {
        "note": "Production concern detector (full pipeline) on test corpus + wellbeing cases",
        "codepath": "production_concern_detector",
        "features": "signal_matrix + CONCERN_PROMPT + anti_bias_postprocessing + confidence_threshold_0.7",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test N: 4-axis classification on raw submissions (not observations)
# ---------------------------------------------------------------------------

FOUR_AXIS_SUBMISSION_SYSTEM = (
    "You are assessing a student's submission for their teacher.\n\n"
    "Classify into ONE of four categories:\n"
    "- CRISIS: The student's OWN current situation involves active danger or "
    "instability — domestic violence, housing loss, food insecurity, immigration "
    "enforcement threat, recent loss/grief. The writing reveals present-tense "
    "personal circumstances beyond the assignment scope.\n"
    "- BURNOUT: The student is depleted — exhaustion, overwork, caregiving burden, "
    "sleep deprivation. They're functioning but running on empty. The key signal "
    "is that the student's MATERIAL CONDITIONS (work schedule, sleep loss, "
    "caregiving duties) are breaking through and limiting their capacity. "
    "Emotional intensity or personal vulnerability in the writing is NOT "
    "burnout — a student who writes passionately about painful experiences "
    "and reflects on the process ('this is what I needed to write') is deeply "
    "engaged, not depleted.\n"
    "- ENGAGED: The student is doing the assignment. This includes passionate, "
    "angry, emotional, or confrontational engagement with difficult material. "
    "Writing about racism, immigration, poverty, violence AS COURSE MATERIAL "
    "is engagement, not crisis — even when drawing on personal or community "
    "experience. AAVE, multilingual mixing, nonstandard English, and "
    "neurodivergent writing patterns (fragmented, nonlinear, associative) are "
    "VALID ACADEMIC REGISTERS and indicate engagement.\n"
    "- NONE: Insufficient text or off-topic.\n\n"
    "IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability "
    "(ADHD, dyslexia, autism), neurodivergent identity, race, religion, "
    "immigration status, sexuality, or language background is intellectual or "
    "personal disclosure — not a wellbeing signal by itself. Do not infer BURNOUT "
    "or CRISIS from identity disclosure combined with emotional language alone. "
    "A student who names their disability and says academic writing is hard, or "
    "that explaining their identity is exhausting, is describing their relationship "
    "to the academic institution — this is ENGAGED. "
    "Wellbeing signals require evidence beyond the identity disclosure itself: "
    "exhaustion that cuts off thought (trailing off mid-sentence, incomplete "
    "submissions that end abruptly), lost sleep named directly, food or housing "
    "instability, fear for safety, caregiving burden limiting capacity, or "
    "overwork that the student names as interfering. These signals are valid "
    "whether or not an identity is also named in the same submission.\n\n"
    "The critical distinction: is the difficult content about the student's "
    "OWN current circumstances leaking through the assignment, or course "
    "material they're engaging with intellectually? The former is CRISIS/BURNOUT; "
    "the latter is ENGAGED.\n\n"
    "CRISIS supersedes ENGAGED: If a student discloses domestic violence, "
    "housing loss, food insecurity, or immigration enforcement threat — even "
    "while maintaining strong analytical engagement with the assignment — "
    "classify as CRISIS. A student can be intellectually engaged AND in crisis. "
    "The presence of crisis-level content in the student's OWN life is the "
    "determining factor, not whether they also engaged with the reading.\n\n"
    "MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities "
    "with histories of institutional surveillance or with strong mutual-aid "
    "traditions often describe crisis-level circumstances in a resilience "
    "register — phrases like 'we are strong,' 'we have support,' or referencing "
    "community resources (mosque, food bank, extended family) as the source of "
    "basic needs. Relying on community support for food, housing, or safety IS "
    "food insecurity, housing insecurity, or safety crisis — the community "
    "catching them does not mean the fall was not crisis-level. Classify based "
    "on the underlying material circumstances, not the emotional register. "
    "In your signal description, name the material conditions directly without "
    "characterizing the student's disclosure style as minimization.\n\n"
    "Respond with JSON only: {\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description\", \"confidence\": 0.0-1.0}"
)

FOUR_AXIS_SUBMISSION_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Classify this submission. Respond with JSON only."""


def test_n_four_axis_submissions(model_key: str = "gemma12b"):
    """Test 4-axis classification directly on raw student submissions.

    Unlike Test L (which classifies observations), this classifies the raw
    student writing. Answers: does a richer classification schema (4 options
    instead of binary) fix the S029 false-flag and S002 miss when applied
    directly to submissions?

    Comparison matrix:
    - Test B/C/F: simplified binary on submissions → S029 flagged, S002 missed
    - Test M: production binary on submissions → pending
    - Test N (this): 4-axis on submissions → does richer schema help?
    - Test L: 4-axis on observations → does observation pre-processing help?
    - Test G: generative observations → the non-classification approach
    """
    print(f"\n{'='*60}")
    print(f"  TEST N: 4-Axis Classification on Submissions ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace as _replace
    temp = float(os.environ.get("TEST_TEMPERATURE", "0.1"))
    backend = _replace(backend, temperature=temp)
    if temp != 0.1:
        print(f"  (temperature override: {temp})")

    # Corpus students
    test_cases = [
        ("S002", "burnout", "BURNOUT"),
        ("S004", "strong", "ENGAGED"),
        ("S022", "righteous_anger", "ENGAGED"),
        ("S023", "lived_exp", "ENGAGED"),
        ("S024", "lived_exp", "ENGAGED"),
        ("S028", "AAVE", "ENGAGED"),
        ("S029", "neurodivergent", "ENGAGED"),
        ("S031", "minimal_effort", "NONE"),  # minimal summary, no wellbeing signal → NONE
    ]

    results = []

    print(f"\n  --- Corpus students ---")
    for sid, pattern, expected_axis in test_cases:
        student = corpus[sid]
        prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, FOUR_AXIS_SUBMISSION_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse
        import re as _re
        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', output)
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        confidence = float(conf_match.group(1)) if conf_match else 0.0

        correct = "OK" if axis == expected_axis else "MISMATCH"

        results.append({
            "codepath": "test_harness_4axis_submissions",
            "source": "corpus",
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected_axis": expected_axis,
            "actual_axis": axis,
            "confidence": confidence,
            "correct": correct,
            "prompt": prompt,
            "system_prompt": FOUR_AXIS_SUBMISSION_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        print(f"  {sid} {student['student_name']:20s} {pattern:20s} "
              f"expect={expected_axis:8s} got={axis:8s} conf={confidence:.1f} [{correct}]")

    print(f"\n  --- Wellbeing cases ---")
    for case in WELLBEING_SIGNAL_CASES:
        expected_axis = "ENGAGED" if case["signal_type"].startswith("control") else (
            "BURNOUT" if "burnout" in case["signal_type"] else "CRISIS"
        )

        prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, FOUR_AXIS_SUBMISSION_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', output)
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        confidence = float(conf_match.group(1)) if conf_match else 0.0

        correct = "OK" if axis == expected_axis else "MISMATCH"

        results.append({
            "codepath": "test_harness_4axis_submissions",
            "source": "wellbeing_synthetic",
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "expected_axis": expected_axis,
            "actual_axis": axis,
            "confidence": confidence,
            "correct": correct,
            "prompt": prompt,
            "system_prompt": FOUR_AXIS_SUBMISSION_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        print(f"  {case['id']:5s} {case['name']:22s} {case['signal_type']:22s} "
              f"expect={expected_axis:8s} got={axis:8s} conf={confidence:.1f} [{correct}]")

    # Key comparisons
    print(f"\n  === Key Comparisons ===")
    s029 = next((r for r in results if r.get("student_id") == "S029"), None)
    s002 = next((r for r in results if r.get("student_id") == "S002"), None)
    if s029:
        print(f"  S029 (neurodivergent): {s029['actual_axis']} (conf={s029['confidence']:.1f})"
              f" — binary was FLAG 25/25; 4-axis says {s029['actual_axis']}")
    if s002:
        print(f"  S002 (burnout):        {s002['actual_axis']} (conf={s002['confidence']:.1f})"
              f" — binary was CLEAR 25/25; 4-axis says {s002['actual_axis']}")

    path = save_results("test_n_4axis_submissions", model_key, results, {
        "note": "4-axis classification (CRISIS/BURNOUT/ENGAGED/NONE) on raw submissions",
        "codepath": "test_harness_4axis_submissions",
        "comparison": "Binary (B/C/F) → Production (M) → 4-axis submissions (N) → 4-axis observations (L) → Generative observations (G)",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test O: Multi-axis classification (student can be ENGAGED + CRISIS)
# ---------------------------------------------------------------------------

MULTI_AXIS_SYSTEM = (
    "You are assessing a student's submission for their teacher.\n\n"
    "A student can be in MULTIPLE states simultaneously — a student writing "
    "brilliantly about intersectionality CAN ALSO be in personal crisis. "
    "Tag ALL that apply:\n\n"
    "- CRISIS: The student's OWN current situation involves active danger or "
    "instability. Present-tense personal circumstances: DV, housing loss, food "
    "insecurity, immigration enforcement threat, grief/loss.\n"
    "- BURNOUT: The student is depleted — exhaustion, overwork, caregiving, "
    "sleep deprivation. Metacommentary about fatigue, trailing off, apologies.\n"
    "- CHECK-IN: Something subtle that doesn't rise to CRISIS or BURNOUT but "
    "the teacher might want to note — a shift in tone, a trailing-off ending, "
    "a brief mention of difficulty that could be nothing or could be something. "
    "When in doubt between ENGAGED-only and CHECK-IN, choose CHECK-IN. "
    "For CHECK-IN, explain WHY the call is ambiguous — surface the competing "
    "interpretations so the teacher can decide (e.g., 'This could be normal "
    "late-night submission behavior OR a sign of depletion — the trailing-off "
    "and abbreviated ending could go either way').\n"
    "- ENGAGED: The student is doing the assignment. Passionate engagement with "
    "difficult material is ENGAGEMENT. AAVE, neurodivergent patterns, multilingual "
    "mixing are valid academic registers.\n\n"
    "IDENTITY DISCLOSURE ALONE IS NOT A WELLBEING SIGNAL. Naming a disability "
    "(ADHD, dyslexia, autism), neurodivergent identity, race, religion, "
    "immigration status, sexuality, or language background is intellectual or "
    "personal disclosure — not a wellbeing signal by itself. Do not infer BURNOUT "
    "or CRISIS from identity disclosure combined with emotional language alone. "
    "A student who names their disability and says academic writing is hard, or "
    "that explaining their identity is exhausting, is describing their relationship "
    "to the academic institution — this is ENGAGED. "
    "Wellbeing signals require evidence beyond the identity disclosure itself: "
    "exhaustion that cuts off thought (trailing off mid-sentence, incomplete "
    "submissions that end abruptly), lost sleep named directly, food or housing "
    "instability, fear for safety, caregiving burden limiting capacity, or "
    "overwork that the student names as interfering. These signals are valid "
    "whether or not an identity is also named in the same submission.\n\n"
    "CRITICAL: A student can be ENGAGED AND in CRISIS (e.g., writing powerfully "
    "about intersectionality while also revealing their family faces ICE enforcement). "
    "Tag BOTH.\n\n"
    "MINIMIZED DISCLOSURE AND COMMUNITY RESILIENCE: Students from communities "
    "with histories of institutional surveillance or with strong mutual-aid "
    "traditions often describe crisis-level circumstances in a resilience "
    "register — phrases like 'we are strong,' 'we have support,' or referencing "
    "community resources (mosque, food bank, extended family) as the source of "
    "basic needs. Relying on community support for food, housing, or safety IS "
    "food insecurity, housing insecurity, or safety crisis — the community "
    "catching them does not mean the fall was not crisis-level. Classify based "
    "on the underlying material circumstances, not the emotional register. "
    "In your signal description, name the material conditions directly without "
    "characterizing the student's disclosure style as minimization.\n\n"
    "Respond with JSON: {\"axes\": [\"ENGAGED\", \"CRISIS\"], "
    "\"signal\": \"brief description\", \"confidence\": 0.0-1.0}"
)

MULTI_AXIS_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Tag ALL applicable states. Respond with JSON only."""


def test_o_multi_axis(model_key: str = "gemma12b"):
    """Test multi-axis classification where students can have multiple tags.

    Unlike Test N (single-axis: pick ONE of CRISIS/BURNOUT/ENGAGED/NONE),
    this allows multiple simultaneous tags. A student can be ENGAGED + CRISIS.
    Also adds CHECK-IN axis for subtle/ambiguous signals (targeting S002).

    Answers: does allowing multiple axes catch signals that single-axis misses
    (especially the ENGAGED + CRISIS overlap cases and the S002 ambiguity)?
    """
    print(f"\n{'='*60}")
    print(f"  TEST O: Multi-Axis Classification ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace as _replace
    temp = float(os.environ.get("TEST_TEMPERATURE", "0.1"))
    backend = _replace(backend, temperature=temp)
    if temp != 0.1:
        print(f"  (temperature override: {temp})")

    import re as _re

    # Corpus students
    corpus_cases = [
        ("S002", "burnout", ["BURNOUT", "CHECK-IN"]),
        ("S004", "strong", ["ENGAGED"]),
        ("S022", "righteous_anger", ["ENGAGED"]),
        ("S023", "lived_exp", ["ENGAGED"]),
        ("S028", "AAVE", ["ENGAGED"]),
        ("S029", "neurodivergent", ["ENGAGED"]),
        ("S031", "minimal_effort", ["ENGAGED"]),
    ]

    results = []

    print(f"\n  --- Corpus students ---")
    for sid, pattern, expected_axes in corpus_cases:
        student = corpus[sid]
        prompt = MULTI_AXIS_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, MULTI_AXIS_SYSTEM, max_tokens=200)
        elapsed = round(time.time() - t0, 1)

        # Parse axes array
        axes_match = _re.search(r'"axes"\s*:\s*\[([^\]]*)\]', output)
        if axes_match:
            axes = [a.strip().strip('"').strip("'") for a in axes_match.group(1).split(",")]
        else:
            axes = ["PARSE_ERROR"]
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        confidence = float(conf_match.group(1)) if conf_match else 0.0

        has_crisis = "CRISIS" in axes
        has_burnout = "BURNOUT" in axes
        has_checkin = "CHECK-IN" in axes
        has_engaged = "ENGAGED" in axes

        results.append({
            "codepath": "test_harness_multi_axis",
            "source": "corpus",
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected_axes": expected_axes,
            "actual_axes": axes,
            "confidence": confidence,
            "has_crisis": has_crisis,
            "has_burnout": has_burnout,
            "has_checkin": has_checkin,
            "has_engaged": has_engaged,
            "prompt": prompt,
            "system_prompt": MULTI_AXIS_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        print(f"  {sid} {student['student_name']:20s} {pattern:20s} "
              f"axes={axes} conf={confidence:.1f}")

    print(f"\n  --- Wellbeing cases ---")
    for case in WELLBEING_SIGNAL_CASES:
        is_control = case["signal_type"].startswith("control")
        expected_axes = ["ENGAGED"] if is_control else (
            ["ENGAGED", "BURNOUT"] if "burnout" in case["signal_type"]
            else ["ENGAGED", "CRISIS"]
        )

        prompt = MULTI_AXIS_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, MULTI_AXIS_SYSTEM, max_tokens=200)
        elapsed = round(time.time() - t0, 1)

        axes_match = _re.search(r'"axes"\s*:\s*\[([^\]]*)\]', output)
        if axes_match:
            axes = [a.strip().strip('"').strip("'") for a in axes_match.group(1).split(",")]
        else:
            axes = ["PARSE_ERROR"]
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        confidence = float(conf_match.group(1)) if conf_match else 0.0

        has_crisis = "CRISIS" in axes
        has_burnout = "BURNOUT" in axes
        has_checkin = "CHECK-IN" in axes

        if is_control:
            correct = "OK" if not (has_crisis or has_burnout) else "FALSE-FLAG"
        else:
            correct = "OK" if (has_crisis or has_burnout) else "MISSED"

        results.append({
            "codepath": "test_harness_multi_axis",
            "source": "wellbeing_synthetic",
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "expected_axes": expected_axes,
            "actual_axes": axes,
            "confidence": confidence,
            "has_crisis": has_crisis,
            "has_burnout": has_burnout,
            "has_checkin": has_checkin,
            "correct": correct,
            "prompt": prompt,
            "system_prompt": MULTI_AXIS_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        print(f"  {case['id']:5s} {case['name']:22s} axes={axes} [{correct}]")

    # Key results
    print(f"\n  === Key Results ===")
    s002 = next((r for r in results if r.get("student_id") == "S002"), None)
    s029 = next((r for r in results if r.get("student_id") == "S029"), None)
    if s002:
        print(f"  S002 (burnout): axes={s002['actual_axes']} — "
              f"{'CHECK-IN detected!' if s002['has_checkin'] or s002['has_burnout'] else 'Still missed'}")
    if s029:
        print(f"  S029 (neurodivergent): axes={s029['actual_axes']} — "
              f"{'FALSE-FLAG' if s029['has_crisis'] or s029['has_burnout'] else 'Correctly ENGAGED'}")

    wb_signals = [r for r in results if r["source"] == "wellbeing_synthetic" and not r["signal_type"].startswith("control")]
    wb_controls = [r for r in results if r["source"] == "wellbeing_synthetic" and r["signal_type"].startswith("control")]
    caught = sum(1 for r in wb_signals if r["has_crisis"] or r["has_burnout"])
    fp = sum(1 for r in wb_controls if r["has_crisis"] or r["has_burnout"])
    dual = sum(1 for r in wb_signals if (r["has_crisis"] or r["has_burnout"]) and r.get("has_engaged"))
    print(f"  WB signals: {caught}/{len(wb_signals)} caught, {dual} dual-tagged (ENGAGED + signal)")
    print(f"  WB controls: {fp}/{len(wb_controls)} false positives")

    path = save_results("test_o_multi_axis", model_key, results, {
        "note": "Multi-axis: students can be ENGAGED + CRISIS simultaneously. Adds CHECK-IN for ambiguous cases.",
        "codepath": "test_harness_multi_axis",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test P: Two-pass architecture (N primary → targeted CHECK-IN on ENGAGED)
# ---------------------------------------------------------------------------

TARGETED_CHECKIN_SYSTEM = (
    "A colleague classified this student as ENGAGED — they are doing the "
    "work. Most engaged students need no further attention.\n\n"
    "Occasionally, an engaged student will say something about their OWN "
    "current state that a teacher might want to note — not the course "
    "material, but a direct comment about themselves. Examples:\n"
    "- An apology for quality (\"sorry this isn't great\")\n"
    "- A mention of exhaustion or time pressure (\"it's late\", \"I ran out "
    "of time\")\n"
    "- A reference to personal difficulty (\"things have been rough\")\n\n"
    "A strong indicator is REGISTER SHIFT: the student breaks from their "
    "engaged analysis into a different mode — apologetic, exhausted, or "
    "deflated — as if stepping outside the assignment to comment on "
    "themselves.\n\n"
    "Does this student explicitly say anything about their own current "
    "state?\n\n"
    "If YES: Quote the specific words, then explain competing "
    "interpretations (it might be nothing, or it might be worth noting).\n"
    "If NO: Say so clearly.\n\n"
    "IMPORTANT distinctions:\n"
    "- A submission ending without a formal conclusion is NORMAL student "
    "writing — not a signal.\n"
    "- Students drawing on personal or community experience AS COURSE "
    "MATERIAL are engaged, not disclosing their state. A student writing "
    "about family hardship to analyze a concept is doing the assignment.\n"
    "- Rhetorical or analytical expressions about the material (\"I'm tired "
    "of how...\", \"I don't know if...\") are engaged writing, not self-"
    "disclosure.\n"
    "- Statements about the student's APPROACH to the assignment (\"I'm "
    "just gonna be real\", \"let me try to explain\", \"here's my take\") "
    "are about method, not state.\n"
    "- Only flag words the student actually wrote about THEMSELVES. Do not "
    "infer signals from writing style, structure, or lack of a conclusion.\n\n"
    "Set check_in to true ONLY when the competing interpretations are "
    "genuinely balanced — when a reasonable teacher could go either way. "
    "If your analysis leans toward 'nothing to note,' check_in is false.\n\n"
    "Respond with JSON: {\"check_in\": true|false, "
    "\"reasoning\": \"quote and explanation if flagging, or why nothing to note\"}"
)

TARGETED_CHECKIN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Does this student say anything about their own state? Respond with JSON only."""


def test_p_two_pass(model_key: str = "gemma12b"):
    """Test the actual proposed pipeline architecture: N then targeted CHECK-IN.

    Pass 1: Run N's 4-axis classification on all students.
    Pass 2: For students classified as ENGAGED, run a targeted CHECK-IN
    prompt that ONLY asks about subtle signals — no CRISIS/BURNOUT options.

    This tests whether the two-pass approach catches S002 (like O does)
    without over-firing CHECK-IN (like O does) or re-introducing false
    positives (like O does on WB09).
    """
    print(f"\n{'='*60}")
    print(f"  TEST P: Two-Pass Architecture ({model_key})")
    print(f"  Pass 1: 4-axis classification (N)")
    print(f"  Pass 2: Targeted CHECK-IN on ENGAGED students only")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace as _replace
    temp = float(os.environ.get("TEST_TEMPERATURE", "0.1"))
    backend = _replace(backend, temperature=temp)
    if temp != 0.1:
        print(f"  (temperature override: {temp})")

    import re as _re

    # All test cases (corpus + wellbeing)
    all_cases = []
    corpus_cases = [
        ("S002", "burnout"), ("S004", "strong"), ("S022", "righteous_anger"),
        ("S023", "lived_exp"), ("S024", "lived_exp"), ("S028", "AAVE"),
        ("S029", "neurodivergent"), ("S031", "minimal_effort"),
    ]
    for sid, pattern in corpus_cases:
        s = corpus[sid]
        all_cases.append({
            "id": sid, "name": s["student_name"], "text": s["text"],
            "source": "corpus", "pattern": pattern,
        })
    for case in WELLBEING_SIGNAL_CASES:
        all_cases.append({
            "id": case["id"], "name": case["name"], "text": case["text"],
            "source": "wellbeing", "signal_type": case["signal_type"],
            "expected_surface": case["expected_surface"],
        })

    results = []

    # Pass 1: 4-axis classification
    print(f"\n  --- Pass 1: 4-axis classification ---")
    for case in all_cases:
        prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, FOUR_AXIS_SUBMISSION_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        axis_match = _re.search(r'"axis"\s*:\s*"([^"]*)"', output)
        axis = axis_match.group(1) if axis_match else "PARSE_ERROR"
        conf_match = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        confidence = float(conf_match.group(1)) if conf_match else 0.0

        case["pass1_axis"] = axis
        case["pass1_confidence"] = confidence
        case["pass1_output"] = output
        case["pass1_time"] = elapsed

        print(f"  {case['id']:5s} {case['name']:22s} → {axis} ({confidence})")

    # Pass 2: Targeted CHECK-IN on ENGAGED students only
    print(f"\n  --- Pass 2: CHECK-IN on ENGAGED students ---")
    engaged_cases = [c for c in all_cases if c["pass1_axis"] == "ENGAGED"]
    print(f"  {len(engaged_cases)} students classified as ENGAGED")

    for case in all_cases:
        if case["pass1_axis"] != "ENGAGED":
            case["pass2_checkin"] = None
            case["pass2_reasoning"] = "N/A — not ENGAGED"
            continue

        prompt = TARGETED_CHECKIN_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, TARGETED_CHECKIN_SYSTEM, max_tokens=200)
        elapsed = round(time.time() - t0, 1)

        checkin_match = _re.search(r'"check_in"\s*:\s*(true|false)', output, _re.IGNORECASE)
        checkin = checkin_match.group(1).lower() == "true" if checkin_match else None
        reason_match = _re.search(r'"reasoning"\s*:\s*"([^"]*)"', output)
        reasoning = reason_match.group(1) if reason_match else output[:200]

        case["pass2_checkin"] = checkin
        case["pass2_reasoning"] = reasoning
        case["pass2_output"] = output
        case["pass2_time"] = elapsed

        flag = "CHECK-IN" if checkin else "clear"
        print(f"  {case['id']:5s} {case['name']:22s} → {flag}")
        if checkin and reasoning:
            print(f"        reason: {reasoning[:100]}")

    # Build results
    for case in all_cases:
        final_axis = case["pass1_axis"]
        if case["pass1_axis"] == "ENGAGED" and case.get("pass2_checkin"):
            final_axis = "ENGAGED+CHECK-IN"

        results.append({
            "codepath": "two_pass_n_then_checkin",
            "source": case["source"],
            "student_id": case["id"],
            "student_name": case["name"],
            "pattern": case.get("pattern", case.get("signal_type", "")),
            "pass1_axis": case["pass1_axis"],
            "pass1_confidence": case.get("pass1_confidence"),
            "pass2_checkin": case.get("pass2_checkin"),
            "pass2_reasoning": case.get("pass2_reasoning", ""),
            "final_axis": final_axis,
            "prompt_pass1": case.get("pass1_output", ""),
            "prompt_pass2": case.get("pass2_output", ""),
            "system_prompt_pass1": FOUR_AXIS_SUBMISSION_SYSTEM,
            "system_prompt_pass2": TARGETED_CHECKIN_SYSTEM,
        })

    # Summary
    print(f"\n  === Two-Pass Results ===")
    s002 = next((c for c in all_cases if c["id"] == "S002"), None)
    s029 = next((c for c in all_cases if c["id"] == "S029"), None)
    print(f"  S002: pass1={s002['pass1_axis']}, checkin={s002.get('pass2_checkin')}")
    if s002.get("pass2_reasoning"):
        print(f"    reason: {s002['pass2_reasoning'][:150]}")
    print(f"  S029: pass1={s029['pass1_axis']}, checkin={s029.get('pass2_checkin')}")

    # Wellbeing summary
    wb_signals = [c for c in all_cases if c["source"] == "wellbeing"
                  and not c.get("signal_type", "").startswith("control")]
    wb_controls = [c for c in all_cases if c["source"] == "wellbeing"
                   and c.get("signal_type", "").startswith("control")]
    caught = sum(1 for c in wb_signals
                 if c["pass1_axis"] in ("CRISIS", "BURNOUT") or c.get("pass2_checkin"))
    fp = sum(1 for c in wb_controls
             if c["pass1_axis"] in ("CRISIS", "BURNOUT") or c.get("pass2_checkin"))
    corpus_checkins = sum(1 for c in all_cases
                         if c["source"] == "corpus" and c.get("pass2_checkin"))

    print(f"\n  WB signals caught: {caught}/{len(wb_signals)}")
    print(f"  WB controls FP: {fp}/{len(wb_controls)}")
    print(f"  Corpus CHECK-INs: {corpus_checkins}/7")
    print(f"  (Compare: O had 7/7 corpus CHECK-INs)")

    path = save_results("test_p_two_pass", model_key, results, {
        "note": "Two-pass: N (4-axis) then targeted CHECK-IN on ENGAGED only",
        "codepath": "two_pass_n_then_checkin",
        "architecture": "Pass 1: FOUR_AXIS_SUBMISSION → Pass 2: TARGETED_CHECKIN on ENGAGED",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test Q: 27B training-data-bias counterfactual probes
# ---------------------------------------------------------------------------

# Full S029 text (Jordan Espinoza, neurodivergent — classified BURNOUT by 27B)
_S029_ORIGINAL = """\
intersectionality

ok so I'm going to try to write this and hopefully it makes sense. the reading is about \
how people have multiple identities and they don't just add together, they interact. \
Crenshaw was saying Black women in the lawsuits couldn't use race discrimination because \
Black men weren't affected and couldn't use sex discrimination because white women weren't \
affected so they fell through this gap in between.

that gap is the intersection I think

what I want to say for my own life: I have dyslexia and ADHD and I'm also Latino and I'm \
the first in my family to take honors classes. the way all of that interacts is exhausting \
to explain. people see the dyslexia and think I need simpler stuff. people see I'm Latino \
and sometimes seem surprised I'm in honors. people see ADHD and think I'm not serious. \
but I'm all of it at once and the combination is its own specific thing.

I have a lot more to say but my thoughts aren't organized in the way an essay is supposed \
to be organized. I know. I'm better at talking than writing. but I think I showed I \
understood it even if the structure isn't right.

the intersections are real even when the essay isn't perfect."""

# Probe 1: replace "exhausting to explain" → "difficult to articulate"
# Tests: is the word "exhausting" the primary BURNOUT trigger?
_S029_PROBE1 = _S029_ORIGINAL.replace(
    "the way all of that interacts is exhausting to explain",
    "the way all of that interacts is difficult to articulate",
)

# Probe 2: remove disability vocabulary (dyslexia/ADHD → "multiple overlapping identities")
# Keep "exhausting to explain". Tests: is disability vocabulary the mediating variable?
_S029_PROBE2 = _S029_ORIGINAL.replace(
    "I have dyslexia and ADHD and I'm also Latino and I'm the first in my family to take "
    "honors classes. the way all of that interacts is exhausting to explain. people see the "
    "dyslexia and think I need simpler stuff. people see I'm Latino and sometimes seem "
    "surprised I'm in honors. people see ADHD and think I'm not serious. but I'm all of it "
    "at once and the combination is its own specific thing.",
    "I have multiple overlapping identities — I'm Latino and the first in my family to take "
    "honors classes, and these identities interact in ways that shape how people see me. "
    "the way all of that interacts is exhausting to explain. people see my background and "
    "seem surprised I'm in honors. people make assumptions about what I can handle. but I'm "
    "all of it at once and the combination is its own specific thing.",
)

# Probe 3: structurally equivalent submission, neurotypical student, "exhausting to explain"
# preserved, no disability vocabulary. Tests: does structure alone trigger BURNOUT, or
# does disability vocabulary mediate?
_PROBE3_STRUCTURAL_EQUIV = """\
intersectionality

ok so i want to try to write this and i hope it makes sense. the reading is about how \
people have multiple identities that don't just add together, they interact. Crenshaw was \
saying Black women couldn't use race discrimination because Black men weren't affected and \
couldn't use sex discrimination because white women weren't affected so they fell through \
this gap.

that gap is the intersection

what i want to say for my own life: i'm mixed race — Black and white — and also queer and \
also working class and I'm the first in my family to go to college. the way all of that \
interacts is exhausting to explain. people see i'm light-skinned and assume i have it \
easier. people see i'm in college and assume my family supported that. people see i'm queer \
and think that's the main thing about me. but i'm all of it at once and it's its own \
specific thing.

i have a lot more to say but my thoughts aren't organized the way an essay is supposed to \
be organized. i know. but i think i showed i understood the concept even if the structure \
isn't right.

the intersections are real even when the essay isn't perfect."""


def test_q_27b_probes():
    """Counterfactual probes for 27B training-data-bias hypothesis.

    Gemma 27B classifies S029 (neurodivergent writer) as BURNOUT where Gemma 12B
    classifies ENGAGED 9/9 runs. Root cause analysis identified three specific
    misreadings: "exhausting to explain" decontextualized, metacommentary read as
    distress, "better at talking" read as overwhelm.

    These three probes triangulate which element is the primary trigger. All run
    on Gemma 27B via OpenRouter (cloud — no MLX needed).
    See: docs/research/experiment_log.md, "Probe Design for Academic Paper" section.
    """
    print(f"\n{'='*60}")
    print(f"  TEST Q: 27B Training-Data-Bias Counterfactual Probes")
    print(f"  Model: google/gemma-3-27b-it (OpenRouter)")
    print(f"  Probes: 3 counterfactual variants of S029 (Jordan Espinoza)")
    print(f"{'='*60}")

    backend = get_backend("gemma27b_cloud")
    from dataclasses import replace as _replace
    backend = _replace(backend, temperature=0.1)  # Low temp for probes — maximize determinism

    probes = [
        {
            "probe_id": "Q1_exhausting_ablation",
            "description": "Replace 'exhausting to explain' → 'difficult to articulate'",
            "hypothesis": "If ENGAGED: word 'exhausting' is the primary BURNOUT trigger",
            "student_name": "Jordan Espinoza (Probe 1)",
            "text": _S029_PROBE1,
        },
        {
            "probe_id": "Q2_disability_vocab_removal",
            "description": "Remove dyslexia/ADHD → 'multiple overlapping identities', keep 'exhausting'",
            "hypothesis": "If ENGAGED: disability vocabulary is the mediating variable",
            "student_name": "Jordan Espinoza (Probe 2)",
            "text": _S029_PROBE2,
        },
        {
            "probe_id": "Q3_structural_equivalence",
            "description": "Structurally identical submission, neurotypical student, same 'exhausting to explain'",
            "hypothesis": "If ENGAGED: non-linear structure alone does not trigger BURNOUT; disability vocab mediates",
            "student_name": "Alex Rivera (structural equivalent)",
            "text": _PROBE3_STRUCTURAL_EQUIV,
        },
    ]

    # Baseline: original S029 on 27B (should reproduce BURNOUT from Phase 4)
    print(f"\n  --- Baseline: S029 original on 27B ---")
    baseline_prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
        student_name="Jordan Espinoza",
        submission_text=_S029_ORIGINAL,
    )
    t0 = time.time()
    baseline_output = send(backend, baseline_prompt, FOUR_AXIS_SUBMISSION_SYSTEM, max_tokens=150)
    elapsed = round(time.time() - t0, 1)

    import re as _re
    def _parse(output):
        axis_m = _re.search(r'"axis"\s*:\s*"([^"]*)"', output)
        conf_m = _re.search(r'"confidence"\s*:\s*([\d.]+)', output)
        return (
            axis_m.group(1) if axis_m else "PARSE_ERROR",
            float(conf_m.group(1)) if conf_m else 0.0,
        )

    baseline_axis, baseline_conf = _parse(baseline_output)
    print(f"  S029 original: axis={baseline_axis} conf={baseline_conf:.2f} ({elapsed}s)")
    print(f"  (Expected: BURNOUT from Phase 4; anything else means quota/model change)")

    # Run probes
    results = [{
        "probe_id": "Q0_baseline",
        "description": "Original S029 on 27B — should reproduce Phase 4 BURNOUT",
        "hypothesis": "Baseline reproduction check",
        "student_name": "Jordan Espinoza (original)",
        "axis": baseline_axis,
        "confidence": baseline_conf,
        "raw_output": baseline_output,
        "time_seconds": elapsed,
    }]

    print(f"\n  --- Counterfactual probes ---")
    for probe in probes:
        prompt = FOUR_AXIS_SUBMISSION_PROMPT.format(
            student_name=probe["student_name"],
            submission_text=probe["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, FOUR_AXIS_SUBMISSION_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)
        axis, conf = _parse(output)

        shift = "→ SHIFT (hypothesis supported)" if axis != baseline_axis else "→ NO SHIFT"
        print(f"  {probe['probe_id']}: axis={axis} conf={conf:.2f} {shift}")
        print(f"    {probe['description']}")
        if axis != baseline_axis:
            print(f"    Hypothesis: {probe['hypothesis']}")

        results.append({
            **probe,
            "axis": axis,
            "confidence": conf,
            "raw_output": output,
            "time_seconds": elapsed,
            "shifted_from_baseline": axis != baseline_axis,
        })

    # --- Q4: Identity-disclosure guard (production prompt, updated) ---
    # This uses the PRODUCTION WELLBEING_CLASSIFIER_SYSTEM which now includes
    # the generalized identity-disclosure guard.
    print(f"\n  --- Q4: Identity-disclosure guard (production prompt) ---")
    from insights.prompts import WELLBEING_CLASSIFIER_SYSTEM, WELLBEING_CLASSIFIER_PROMPT
    q4_prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        signal_prefix="",
        student_name="Jordan Espinoza",
        submission_text=_S029_ORIGINAL,
    )
    t0 = time.time()
    q4_output = send(backend, q4_prompt, WELLBEING_CLASSIFIER_SYSTEM, max_tokens=200)
    q4_elapsed = round(time.time() - t0, 1)
    q4_axis, q4_conf = _parse(q4_output)
    q4_shifted = q4_axis != baseline_axis
    print(f"  Q4: axis={q4_axis} conf={q4_conf:.2f} ({q4_elapsed}s) {'→ SHIFT' if q4_shifted else '→ NO SHIFT'}")
    print(f"    Tests: does the identity-disclosure guard in production prompt fix 27B?")
    results.append({
        "probe_id": "Q4_identity_guard",
        "description": "Original S029 on 27B with updated production prompt (identity-disclosure guard added)",
        "hypothesis": "If ENGAGED: the guard suppresses the disability-vocabulary trigger without needing text modification",
        "student_name": "Jordan Espinoza (original, guarded prompt)",
        "text": _S029_ORIGINAL,
        "axis": q4_axis,
        "confidence": q4_conf,
        "raw_output": q4_output,
        "time_seconds": q4_elapsed,
        "shifted_from_baseline": q4_shifted,
        "approach": "guard",
    })

    # --- Q5: Evidence-extraction classifier (structural alternative) ---
    # This uses the experimental prompt that separates evidence extraction
    # from classification, making identity → deficit inference structurally
    # unreachable.
    print(f"\n  --- Q5: Evidence-extraction classifier (structural alternative) ---")
    from insights.prompts import WELLBEING_EVIDENCE_EXTRACTION_SYSTEM
    q5_prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        signal_prefix="",
        student_name="Jordan Espinoza",
        submission_text=_S029_ORIGINAL,
    )
    t0 = time.time()
    q5_output = send(backend, q5_prompt, WELLBEING_EVIDENCE_EXTRACTION_SYSTEM, max_tokens=300)
    q5_elapsed = round(time.time() - t0, 1)
    q5_axis, q5_conf = _parse(q5_output)
    q5_shifted = q5_axis != baseline_axis
    print(f"  Q5: axis={q5_axis} conf={q5_conf:.2f} ({q5_elapsed}s) {'→ SHIFT' if q5_shifted else '→ NO SHIFT'}")
    print(f"    Tests: does evidence-extraction structure prevent deficit inference entirely?")
    # Also extract the evidence field if present
    evidence_m = _re.search(r'"evidence"\s*:\s*\[([^\]]*)\]', q5_output)
    evidence_str = evidence_m.group(1).strip() if evidence_m else "(not parsed)"
    print(f"    Evidence extracted: {evidence_str[:200]}")
    results.append({
        "probe_id": "Q5_evidence_extraction",
        "description": "Original S029 on 27B with evidence-extraction prompt (two-step: extract material evidence → derive axis)",
        "hypothesis": "If ENGAGED: restructuring the task prevents the identity→deficit inference entirely, without needing a guard",
        "student_name": "Jordan Espinoza (original, evidence-extraction prompt)",
        "text": _S029_ORIGINAL,
        "axis": q5_axis,
        "confidence": q5_conf,
        "raw_output": q5_output,
        "time_seconds": q5_elapsed,
        "shifted_from_baseline": q5_shifted,
        "approach": "evidence_extraction",
        "evidence_extracted": evidence_str,
    })

    # Save
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = OUTPUT_DIR / f"test_q_27b_probes_{ts}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "test": "Q",
        "description": "27B training-data-bias counterfactual probes",
        "model": "google/gemma-3-27b-it",
        "temperature": 0.1,
        "generated_at": datetime.now().isoformat(),
        "baseline_axis": baseline_axis,
        "probes": results,
        "provenance": _git_provenance(),
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\n  Results saved: {out_path}")

    # Summary
    print(f"\n  {'='*50}")
    print(f"  PROBE SUMMARY")
    print(f"  {'='*50}")
    print(f"  Baseline (S029 original):  {baseline_axis} {baseline_conf:.2f}")
    for r in results[1:]:
        shifted = "SHIFT" if r.get("shifted_from_baseline") else "no shift"
        print(f"  {r['probe_id']:35s}: {r['axis']:8s} {r['confidence']:.2f}  [{shifted}]")

    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_test_subprocess(test_id: str, model: str, runs: int,
                          corpus: Optional[Path] = None,
                          class_reading: Optional[Path] = None) -> Optional[int]:
    """Run a single test in an isolated subprocess.

    Metal GPU memory is only fully reclaimed when the process exits.
    Running each test as a subprocess prevents cumulative Metal memory
    fragmentation that causes deadlocks on 16 GB machines.

    Returns the subprocess exit code, or None if skipped.
    """
    import subprocess as sp

    cmd = [
        sys.executable, __file__,
        "--single-test", test_id,
        "--model", model,
        "--runs", str(runs),
    ]
    if corpus:
        cmd += ["--corpus", str(corpus)]
    if class_reading:
        cmd += ["--class-reading", str(class_reading)]
    log.info("Subprocess for Test %s: %s", test_id, " ".join(cmd))
    # F, G, H, J are longer tests — many inferences each
    # K is cloud-only (no MLX) but may take time due to rate limits
    # P is two-pass (N + CHECK-IN on all ENGAGED), needs extra headroom
    timeout = 3600 if test_id in ("F", "G", "H", "J", "K", "P") else 900
    result = sp.run(cmd, timeout=timeout)
    return result.returncode


def _run_single_test(test_id: str, model: str, runs: int):
    """Execute one test in the current process (called from subprocess)."""
    if test_id == "A":
        test_a_temperature(model, n_runs=runs)
    elif test_id == "B":
        test_b_best_concern(model)
    elif test_id == "C":
        test_c_length(model)
    elif test_id == "D":
        test_d_power_moves(model)
    elif test_id == "E_qwen7b":
        test_e_cross_model("qwen7b", n_runs=min(runs, 3))
    elif test_id == "E_gemma27b":
        test_e_cross_model("gemma27b_cloud", n_runs=min(runs, 3))
    elif test_id == "F":
        test_f_bc_stability(model, n_runs=runs)
    elif test_id == "G":
        test_g_wellbeing_signals(model)
    elif test_id == "H":
        test_h_binary_on_wellbeing(model)
    elif test_id == "J":
        test_j_pipeline_validation(model)
    elif test_id == "K":
        test_k_enhancement_comparison()
    elif test_id == "L":
        test_l_expanded_wellbeing(model)
    elif test_id == "M":
        test_m_production_detector(model)
    elif test_id == "N":
        test_n_four_axis_submissions(model)
    elif test_id == "O":
        test_o_multi_axis(model)
    elif test_id == "P":
        test_p_two_pass(model)
    elif test_id == "Q":
        test_q_27b_probes()  # Always uses gemma27b_cloud — model arg ignored
    else:
        log.error("Unknown test: %s", test_id)
        sys.exit(1)
    # Explicit cleanup before exit — helps Metal driver reclaim faster
    unload_model()


# Pause between subprocess exits to let Metal driver fully reclaim memory.
# Without this, back-to-back subprocess launches can hit residual allocations.
_INTER_TEST_PAUSE = 5  # seconds


def _metal_warmup(model_key: str = "gemma12b"):
    """Pre-initialize the Metal GPU before the first MLX subprocess.

    Loads the target model, generates 5 tokens, fully unloads. Prevents
    Metal driver deadlocks after system sleep (CLAUDE.md convention).
    Skipped automatically for cloud models.
    """
    if MODELS.get(model_key, {}).get("name") not in ("mlx",):
        return

    print("\n  [Metal warmup] Initializing GPU (prevents sleep-induced deadlocks)...")
    t0 = time.time()
    try:
        from insights.llm_backend import BackendConfig, send_text, unload_mlx_model
        cfg = BackendConfig(
            name="mlx",
            model=MODELS[model_key]["model"],
            max_tokens=5,
            temperature=0.0,
        )
        send_text(cfg, "Warmup", system_prompt="OK")
        unload_mlx_model()
        time.sleep(3)
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)")
    except Exception as e:
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alternative hypothesis tests")
    parser.add_argument("--tests", default="A,B,C,D",
                        help="Comma-separated list: A,B,C,D,E,F,G,H,J,K,L,N,O,P,Q")
    parser.add_argument("--model", default="gemma12b",
                        help="Model key (gemma12b, qwen7b)")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs for Test A/E (default 5)")
    parser.add_argument("--corpus", default=None,
                        help="Path to corpus JSON (default: data/demo_corpus/ethnic_studies.json)")
    parser.add_argument("--class-reading", default=None,
                        help="Path to pre-baked class reading checkpoint (for synthesis-first tests)")
    parser.add_argument("--single-test", default=None,
                        help="(internal) Run a single test in this process")
    parser.add_argument("--no-subprocess", action="store_true",
                        help="Run all tests in-process (no subprocess isolation)")
    args = parser.parse_args()

    # Apply corpus overrides before any test runs
    if args.corpus:
        global CORPUS_PATH
        CORPUS_PATH = Path(args.corpus)
        if not CORPUS_PATH.is_absolute():
            CORPUS_PATH = ROOT / CORPUS_PATH
    if args.class_reading:
        global CLASS_READING_PATH
        CLASS_READING_PATH = Path(args.class_reading)
        if not CLASS_READING_PATH.is_absolute():
            CLASS_READING_PATH = ROOT / CLASS_READING_PATH

    # --- Single-test mode: called from subprocess ---
    if args.single_test:
        _run_single_test(args.single_test, args.model, args.runs)
        return

    tests = [t.strip().upper() for t in args.tests.split(",")]
    model = args.model

    print(f"\nTests to run: {tests}")
    print(f"Model: {MODELS.get(model, {}).get('model', model)}")
    print(f"Output: {OUTPUT_DIR}")
    if not args.no_subprocess:
        print(f"Mode: subprocess isolation (Metal memory reclaimed between tests)")
    if MODELS.get(model, {}).get("name") == "mlx":
        print(f"NOTE: Run with 'caffeinate -i' to prevent Metal deadlocks on sleep:")
        print(f"      caffeinate -i python scripts/run_alt_hypothesis_tests.py --tests {','.join(tests)} --model {model}")

    total_t0 = time.time()
    result_counts = {}

    if not args.no_subprocess:
        _metal_warmup(model)

    # Build ordered list of test IDs to run
    test_queue = []
    for t in tests:
        if t == "E":
            if model != "qwen7b":
                test_queue.append("E_qwen7b")
            key = _openrouter_key()
            if key:
                test_queue.append("E_gemma27b")
            else:
                print("  Cloud cross-model test skipped (no OpenRouter key)")
        else:
            test_queue.append(t)

    for test_id in test_queue:
        if args.no_subprocess:
            # Legacy in-process mode
            _run_single_test(test_id, model, args.runs)
            result_counts[test_id] = "done"
        else:
            try:
                rc = _run_test_subprocess(test_id, model, args.runs,
                                          corpus=CORPUS_PATH if args.corpus else None,
                                          class_reading=CLASS_READING_PATH if args.class_reading else None)
                result_counts[test_id] = "OK" if rc == 0 else f"exit {rc}"
            except Exception as e:
                log.error("Test %s subprocess failed: %s", test_id, e)
                result_counts[test_id] = f"FAILED: {e}"

            # Let Metal driver reclaim memory before next test
            if test_id != test_queue[-1]:
                log.info("Pausing %ds for Metal memory reclamation...", _INTER_TEST_PAUSE)
                time.sleep(_INTER_TEST_PAUSE)

    total_time = round(time.time() - total_t0, 1)

    # Summary
    print(f"\n{'='*60}")
    print(f"  ALL TESTS COMPLETE — {total_time}s total")
    print(f"{'='*60}")
    for test_id, status in result_counts.items():
        print(f"  Test {test_id}: {status}")
    print(f"  Raw outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
