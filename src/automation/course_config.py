"""
Canvas Autograder - Course Configuration Management
Handles configuration schema, validation, and persistence for automated grading.
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class AssignmentRule:
    """Configuration rule for an assignment group."""

    rule_id: str
    assignment_group_name: str
    assignment_group_id: int
    assignment_type: str  # "complete_incomplete", "discussion_forum", or "mixed"

    # Complete/Incomplete settings
    min_word_count: Optional[int] = None

    # Discussion forum settings
    post_min_words: Optional[int] = None
    reply_min_words: Optional[int] = None
    discussion_grading_mode: Optional[str] = None  # "separate" or "combined"
    grading_type: Optional[str] = None  # "complete_incomplete" or "points"
    post_points: Optional[float] = None  # Points for a qualifying post (points mode)
    reply_points: Optional[float] = None  # Points per qualifying reply (points mode)
    min_posts: Optional[int] = None  # Min qualifying posts (separate mode)
    min_replies: Optional[int] = None  # Min qualifying replies (separate mode)

    # Academic dishonesty check
    run_adc: bool = True

    # Grade preservation
    preserve_existing_grades: bool = True

    # Whether to grade unsubmitted past-due assignments as Incomplete
    mark_missing_as_incomplete: bool = False

    # Whether to grade unsubmitted past-due assignments as 0 (points mode)
    mark_missing_as_zero: bool = False

    # LLM reply quality check
    use_llm_reply_check: bool = False

    # Separate reply-credit assignment (not_graded Canvas assignment, no percentage display)
    # When set, reply points are deposited here instead of on the discussion assignment itself.
    # Maps discussion assignment name fragment → Canvas assignment ID, e.g.:
    #   {"Week 1": 970488, "Week 2": 970489, "Week 3": 970490}
    reply_credit_assignment_ids: Optional[Dict[str, int]] = None

    def __post_init__(self):
        """Validate rule configuration."""
        if self.assignment_type not in ["complete_incomplete", "discussion_forum", "mixed"]:
            raise ValueError(f"Invalid assignment_type: {self.assignment_type}")

        if self.assignment_type == "complete_incomplete":
            if self.min_word_count is None:
                raise ValueError("min_word_count required for complete_incomplete type")

        if self.assignment_type == "discussion_forum":
            mode = self.discussion_grading_mode or "separate"
            if mode == "separate":
                if self.post_min_words is None and self.reply_min_words is None:
                    raise ValueError("At least one of post_min_words or reply_min_words required for separate mode")
            elif mode == "combined":
                if self.post_min_words is None:
                    raise ValueError("post_min_words required for combined mode (used as total word threshold)")

        if self.assignment_type == "mixed":
            # Mixed type needs both complete_incomplete and discussion_forum settings
            if self.min_word_count is None:
                raise ValueError("min_word_count required for mixed type (used for text submissions)")
            if self.post_min_words is None:
                raise ValueError("post_min_words required for mixed type (used for discussion posts)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssignmentRule':
        """Create from dictionary."""
        # Provide defaults for fields added after initial release so old configs load cleanly
        data.setdefault('reply_credit_assignment_ids', None)
        data.setdefault('mark_missing_as_zero', False)
        return cls(**data)


@dataclass
class CourseConfig:
    """Configuration for a single course."""

    course_id: int
    course_name: str
    semester_term_id: int
    enabled: bool = True
    assignment_rules: List[AssignmentRule] = field(default_factory=list)

    def add_rule(self, rule: AssignmentRule):
        """Add an assignment rule to this course."""
        # Check for duplicate rule IDs
        if any(r.rule_id == rule.rule_id for r in self.assignment_rules):
            raise ValueError(f"Rule ID already exists: {rule.rule_id}")

        # Check for duplicate assignment group IDs
        if any(r.assignment_group_id == rule.assignment_group_id for r in self.assignment_rules):
            raise ValueError(f"Assignment group already has a rule: {rule.assignment_group_name}")

        self.assignment_rules.append(rule)

    def remove_rule(self, rule_id: str):
        """Remove an assignment rule by ID."""
        self.assignment_rules = [r for r in self.assignment_rules if r.rule_id != rule_id]

    def get_rule_by_group_id(self, group_id: int) -> Optional[AssignmentRule]:
        """Get rule for a specific assignment group."""
        for rule in self.assignment_rules:
            if rule.assignment_group_id == group_id:
                return rule
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'course_id': self.course_id,
            'course_name': self.course_name,
            'semester_term_id': self.semester_term_id,
            'enabled': self.enabled,
            'assignment_rules': [r.to_dict() for r in self.assignment_rules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CourseConfig':
        """Create from dictionary."""
        rules_data = data.pop('assignment_rules', [])
        config = cls(**data)
        config.assignment_rules = [AssignmentRule.from_dict(r) for r in rules_data]
        return config


@dataclass
class GlobalSettings:
    """Global automation settings."""

    current_semester_term_ids: List[int]
    skip_future_assignments: bool = True
    skip_no_submissions: bool = True
    log_file_path: str = ""
    flag_excel_path: str = ""
    auto_update_enabled: bool = True
    notify_email: str = ""
    n8n_webhook_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalSettings':
        """Create from dictionary."""
        return cls(**data)


class AutomationConfig:
    """Main configuration manager for the automation system."""

    VERSION = "1.0"

    def __init__(self):
        self.courses: Dict[int, CourseConfig] = {}
        self.global_settings: Optional[GlobalSettings] = None
        self.last_updated: Optional[str] = None
        self.version: str = self.VERSION

    def add_course(self, course: CourseConfig):
        """Add a course configuration."""
        if course.course_id in self.courses:
            raise ValueError(f"Course already configured: {course.course_name}")
        self.courses[course.course_id] = course

    def remove_course(self, course_id: int):
        """Remove a course configuration."""
        if course_id in self.courses:
            del self.courses[course_id]

    def get_course(self, course_id: int) -> Optional[CourseConfig]:
        """Get a course configuration."""
        return self.courses.get(course_id)

    def get_enabled_courses(self) -> List[CourseConfig]:
        """Get all enabled courses."""
        return [c for c in self.courses.values() if c.enabled]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'last_updated': datetime.now().isoformat(),
            'global_settings': self.global_settings.to_dict() if self.global_settings else {},
            'courses': {
                str(course_id): course.to_dict()
                for course_id, course in self.courses.items()
            }
        }

    def save(self, config_path: Path):
        """Save configuration to JSON file."""
        # Create backup if file exists
        if config_path.exists():
            backup_path = config_path.with_suffix('.json.backup')
            shutil.copy2(config_path, backup_path)

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write configuration
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, config_path: Path) -> 'AutomationConfig':
        """Load configuration from JSON file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = cls()
        config.version = data.get('version', '1.0')
        config.last_updated = data.get('last_updated')

        # Load global settings
        if 'global_settings' in data:
            config.global_settings = GlobalSettings.from_dict(data['global_settings'])

        # Load courses
        courses_data = data.get('courses', {})
        for course_id_str, course_data in courses_data.items():
            course = CourseConfig.from_dict(course_data)
            config.courses[int(course_id_str)] = course

        return config

    @classmethod
    def create_default(cls, term_ids: List[int],
                      log_path: str, flag_path: str) -> 'AutomationConfig':
        """Create a default configuration."""
        config = cls()
        config.global_settings = GlobalSettings(
            current_semester_term_ids=term_ids,
            skip_future_assignments=True,
            skip_no_submissions=True,
            log_file_path=log_path,
            flag_excel_path=flag_path,
            auto_update_enabled=True
        )
        return config


class ConfigValidator:
    """Validates configuration for conflicts and errors."""

    @staticmethod
    def validate_config(config: AutomationConfig) -> List[str]:
        """
        Validate entire configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check global settings exist
        if config.global_settings is None:
            errors.append("Global settings not configured")

        # Check at least one course enabled
        if not config.get_enabled_courses():
            errors.append("No courses enabled for automation")

        # Validate each course
        for course in config.courses.values():
            course_errors = ConfigValidator.validate_course(course)
            errors.extend([f"Course {course.course_name}: {e}" for e in course_errors])

        return errors

    @staticmethod
    def validate_course(course: CourseConfig) -> List[str]:
        """
        Validate a course configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check at least one rule
        if not course.assignment_rules:
            errors.append("No assignment rules configured")

        # Check for duplicate rule IDs
        rule_ids = [r.rule_id for r in course.assignment_rules]
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("Duplicate rule IDs found")

        # Check for duplicate assignment group IDs
        group_ids = [r.assignment_group_id for r in course.assignment_rules]
        if len(group_ids) != len(set(group_ids)):
            errors.append("Duplicate assignment group IDs found")

        # Validate each rule
        for rule in course.assignment_rules:
            rule_errors = ConfigValidator.validate_rule(rule)
            errors.extend([f"Rule {rule.rule_id}: {e}" for e in rule_errors])

        return errors

    @staticmethod
    def validate_rule(rule: AssignmentRule) -> List[str]:
        """
        Validate an assignment rule.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Type-specific validation
        if rule.assignment_type == "complete_incomplete":
            if rule.min_word_count is None:
                errors.append("min_word_count is required")
            elif rule.min_word_count < 1:
                errors.append("min_word_count must be positive")

        elif rule.assignment_type == "discussion_forum":
            if rule.post_min_words is None:
                errors.append("post_min_words is required")
            elif rule.post_min_words < 1:
                errors.append("post_min_words must be positive")

            if rule.reply_min_words is None:
                errors.append("reply_min_words is required")
            elif rule.reply_min_words < 1:
                errors.append("reply_min_words must be positive")

            if rule.reply_points is not None and rule.reply_points < 0:
                errors.append("reply_points must be non-negative")

        return errors
