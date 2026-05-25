"""
Inbox module configuration.
Designed as a Pydantic model so the future GUI can override paths/settings
without touching this file.
"""
from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseModel, Field
import platform
import os


def _default_app_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "CanvasAutograder"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        return Path.home() / ".config" / "CanvasAutograder"


def _default_teaching_dir() -> Path:
    return Path.home() / "Documents" / "Teaching" / "2026courseplanning"


class InboxConfig(BaseModel):
    """
    All configuration for the inbox module.
    Defaults work out-of-the-box for Dr. Bloch's setup.
    Override fields when constructing for testing or different environments.
    """

    # App data directory (shared with Autograder credentials)
    app_dir: Path = Field(default_factory=_default_app_dir)

    # Teaching project root (for voicing guide, frameworks, grading config)
    teaching_dir: Path = Field(default_factory=_default_teaching_dir)

    # Canvas API
    canvas_base_url: str = "https://cabrillo.instructure.com"
    canvas_api_token: Optional[str] = None  # Loaded from credentials if None

    # Semester tag — update each semester
    current_semester: str = "spring_2026"

    # Course map: course_id → metadata
    courses: Dict[int, Dict] = Field(default_factory=lambda: {
        44853: {"code": "ETHN-1 02", "name": "ETHN-1 In-Person",  "family": "ethn1",  "modality": "in_person"},
        44106: {"code": "ETHN-1 03", "name": "ETHN-1 Online",     "family": "ethn1",  "modality": "online"},
        44672: {"code": "ETHN-27BN", "name": "ETHN-27BN In-Person","family": "ethn27", "modality": "in_person"},
        44673: {"code": "ETHN-27AN", "name": "ETHN-27AN Online",   "family": "ethn27", "modality": "online"},
    })

    # Temporal decay thresholds (days)
    syllabus_cache_max_age_days: int = 7
    tier3_max_age_days: int = 28          # Announcements hard cutoff
    tier2_decay_days: Dict[str, float] = Field(default_factory=lambda: {
        "14": 1.0,
        "28": 0.8,
        "56": 0.6,
        "90": 0.3,
    })

    # Learning / similarity
    tfidf_similarity_threshold: float = 0.15
    max_similar_responses: int = 5

    # Topic taxonomy for auto-tagging
    topic_keywords: Dict[str, list] = Field(default_factory=lambda: {
        "extension":       ["extension", "late", "more time", "extra time", "deadline", "due date", "submit late", "turn in late"],
        "assignment_help": ["how do i", "format", "where do i find", "instructions", "requirements", "confused about", "what do you want", "what should i"],
        "grade_question":  ["grade", "points", "score", "my grade", "gradebook", "why did i get", "missing grade"],
        "absence":         ["absent", "miss class", "missed class", "can't attend", "won't be there", "sick", "won't make it"],
        "personal_crisis": ["emergency", "hospital", "family emergency", "struggling", "mental health", "crisis", "really hard", "overwhelmed", "not okay"],
        "canvas_tech":     ["canvas", "login", "can't access", "submit", "upload", "error", "page not loading", "can't find", "not showing"],
        "accommodation":   ["disability", "accommodation", "dsps", "extra time", "accessibility"],
        "course_content":  ["reading", "concept", "don't understand", "confused about the", "what does", "what is", "can you explain"],
        "enrollment":      ["add code", "waitlist", "enroll", "section", "transfer", "drop"],
    })

    # Priority order for processing (lower = higher priority)
    topic_priority: Dict[str, int] = Field(default_factory=lambda: {
        "personal_crisis":  0,
        "extension":        1,
        "absence":          2,
        "grade_question":   3,
        "accommodation":    4,
        "assignment_help":  5,
        "canvas_tech":      6,
        "course_content":   7,
        "enrollment":       8,
        "other":            9,
    })

    # Icons for display
    topic_icons: Dict[str, str] = Field(default_factory=lambda: {
        "personal_crisis":  "🔴",
        "extension":        "⚡",
        "absence":          "📅",
        "grade_question":   "📊",
        "accommodation":    "♿",
        "assignment_help":  "📚",
        "canvas_tech":      "🔧",
        "course_content":   "💭",
        "enrollment":       "📋",
        "other":            "✉️",
    })

    # Paths to context documents
    @property
    def db_path(self) -> Path:
        return self.app_dir / "inbox_data.db"

    @property
    def syllabus_cache_dir(self) -> Path:
        return self.app_dir / "syllabus_cache"

    @property
    def voicing_guide_path(self) -> Path:
        return self.teaching_dir / "Guides4Humanz" / "VOICING_GUIDE_FOR_EMAIL_DRAFTING.md"

    @property
    def pedagogy_path(self) -> Dict[str, Path]:
        return {
            "ethn1":  self.teaching_dir / "ETHN-1_02_InPerson" / "planning" / "PEDAGOGICAL_FRAMEWORKS.md",
            "ethn27": self.teaching_dir / "ETHN-27bn" / "PEDAGOGICAL_FRAMEWORKS.md",
        }

    @property
    def grading_config_path(self) -> Dict[str, Path]:
        return {
            "online":    self.teaching_dir / "grading_config.yaml",
            "in_person": self.teaching_dir / "grading_config_inperson.yaml",
        }

    def get_course(self, course_id: int) -> Optional[Dict]:
        return self.courses.get(course_id)

    def ensure_dirs(self) -> None:
        """Create app data directories if they don't exist."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.syllabus_cache_dir.mkdir(parents=True, exist_ok=True)


# Module-level default config instance
_default_config: Optional[InboxConfig] = None


def get_config() -> InboxConfig:
    """Get (or create) the default config, loading Canvas token from credentials."""
    global _default_config
    if _default_config is None:
        _default_config = _load_default_config()
    return _default_config


def _load_default_config() -> InboxConfig:
    """Build default config, pulling Canvas token from Autograder credentials."""
    import sys
    # Try importing from the Autograder credentials module
    src_dir = Path(__file__).parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    canvas_token = None
    canvas_base_url = "https://cabrillo.instructure.com"
    try:
        from credentials import load_credentials, get_active_profile
        data = load_credentials()
        _, profile = get_active_profile(data)
        canvas_token = profile.get("canvas_api_token")
        if profile.get("canvas_base_url"):
            canvas_base_url = profile["canvas_base_url"]
    except Exception:
        # Fall back to environment variable
        canvas_token = os.environ.get("CANVAS_API_TOKEN")

    cfg = InboxConfig(
        canvas_api_token=canvas_token,
        canvas_base_url=canvas_base_url,
    )
    cfg.ensure_dirs()
    return cfg
