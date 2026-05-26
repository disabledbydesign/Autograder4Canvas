"""
Insights Panel — Generate Insights feature.

Three states: Setup, Running, Review.
  Setup:   select assignments + configure analysis options
  Running: progress display with early Quick Analysis results
  Review:  left sidebar of completed runs, right layered content

UX language is intentional:
  - "hear what your students said" (subtitle)
  - "What are you listening for?" (teacher input header)
  - "Patterns" not "Quick Stats", "Student Work" not "Codings"
  - Frames student work as thinking worth hearing, not data to extract.

Phase 1: Patterns layer (non-LLM Quick Analysis).
Phase 2: Student Work, Themes, Outliers, Report layers (LLM pipeline).
Phase 3+: Feedback layer (placeholder).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPainterPath, QRadialGradient

from gui.widgets.status_pip import draw_pip

from gui.styles import (
    px,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, ROSE_DIM, TERM_GREEN, BURN_RED, AMBER_BTN,
    STATUS_WARN,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    BORDER_DARK, BORDER_AMBER, PANE_BG_GRADIENT,
    ASSET_CHIP_BG, ASSET_CHIP_BORDER, ASSET_CHIP_TEXT,
    make_run_button, make_secondary_button,
    make_section_label, make_h_rule, make_content_pane,
    apply_phosphor_glow,
    GripSplitter,
    MONO_FONT, PANEL_GRADIENT,
    combo_qss,
)
from gui.widgets.crt_combo import CRTComboBox
from gui.widgets.switch_toggle import SwitchToggle
from gui.widgets.segmented_toggle import SegmentedToggle
from gui.dialogs.bulk_run_dialog import _CourseRow, _TermSection
from gui.widgets.view_toggle import ViewToggle
from gui.widgets.phosphor_chip import PhosphorChip


# ---------------------------------------------------------------------------
# Local stylesheets
# ---------------------------------------------------------------------------

_SCROLL_QSS = f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}
"""

# Timeline section colors (match assignment_panel.py)
_PAST_COLOR   = "#F0A830"   # amber hot  — deadline passed
_WEEK_COLOR   = "#C87C10"   # deep gold  — due this week
_FUTURE_COLOR = "#6B4F2A"   # warm brown — upcoming
_NONE_COLOR   = "#3A2808"   # barely-there — no deadline

_SEVEN_DAYS = 7 * 24 * 3600   # seconds


def _classify_deadline(due_at: str) -> str:
    """Return 'PAST', 'WEEK', 'FUTURE', or 'NONE'."""
    if not due_at:
        return "NONE"
    try:
        dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta < 0:
            return "PAST"
        if delta <= _SEVEN_DAYS:
            return "WEEK"
        return "FUTURE"
    except Exception:
        return "NONE"


# ---------------------------------------------------------------------------
# _AssignRow — two-line selectable assignment item
# ---------------------------------------------------------------------------

class _AssignRow(QWidget):
    """Two-line assignment row mirroring _CourseRow style.

    Top line:    assignment name (PHOSPHOR_MID bold)
    Bottom line: course code + due date (PHOSPHOR_DIM)
    Defaults to checked=True when added to the list.
    Rose glow when checked; amber glow on hover.
    """

    toggled = Signal(bool)

    def __init__(self, course: dict, assignment: dict, course_pill: str = "", parent=None):
        super().__init__(parent)
        self._hovered = False
        self.course_dict = course
        self.assign_dict = assignment

        name = assignment.get("name", "Unknown")
        due  = assignment.get("due_at", "")
        if due:
            try:
                dt  = datetime.fromisoformat(due.replace("Z", "+00:00"))
                due = dt.strftime("due %m/%d")
            except (ValueError, TypeError):
                due = ""

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 5)
        outer.setSpacing(0)

        self._cb = QCheckBox()
        self._cb.setStyleSheet(
            "QCheckBox { spacing: 0; background: transparent; border: none; }"
            "QCheckBox::indicator { width: 0px; height: 0px; border: none; }"
        )
        self._cb.setChecked(False)
        self._cb.toggled.connect(self.toggled)
        self._cb.toggled.connect(lambda _: self.update())
        outer.addWidget(self._cb)
        outer.addSpacing(18)

        _PILL_W = 44
        if course_pill:
            cpill = QLabel(course_pill)
            cpill.setFixedSize(_PILL_W, 16)
            cpill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cpill.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; font-weight: bold;"
                f" border: 1px solid {BORDER_DARK}; border-radius: 3px;"
                f" background: transparent;"
            )
            outer.addWidget(cpill)
        else:
            outer.addSpacing(_PILL_W)
        outer.addSpacing(6)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        text.addWidget(name_lbl)

        # Subtitle: due date + submission count (count populated async)
        self._sub_lbl = QLabel(due if due else "")
        self._sub_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        self._due_text = due
        text.addWidget(self._sub_lbl)

        outer.addLayout(text, 1)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_submission_count(self, count: int) -> None:
        """Update the subtitle with actual submission count (called async)."""
        if count < 0:
            return  # Error fetching — don't change display
        parts = []
        if self._due_text:
            parts.append(self._due_text)
        parts.append(f"{count} submissions")
        self._sub_lbl.setText("  \u00b7  ".join(parts))

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, v: bool) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(v)
        self._cb.blockSignals(False)
        self.update()

    def mousePressEvent(self, event) -> None:
        self._cb.setChecked(not self._cb.isChecked())

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        is_checked = self._cb.isChecked()
        is_hovered = self._hovered

        if is_checked or is_hovered:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            p.fillRect(self.rect(), QColor("#0A0800"))

            glow_cx = self.width() * 0.25
            glow_cy = self.height() * 0.50
            if is_checked:
                center_col = QColor(204, 82, 130, 65)
                bloom_col  = QColor(204, 82, 130, 30)
            else:
                center_col = QColor(240, 168, 48, 45)
                bloom_col  = QColor(240, 168, 48, 18)

            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)

            grad = QRadialGradient(glow_cx, glow_cy, self.width() * 0.85)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.6, QColor(center_col.red(), center_col.green(),
                                        center_col.blue(), 15))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())

            bloom = QRadialGradient(glow_cx, glow_cy, self.width() * 0.42)
            bloom.setColorAt(0.0, bloom_col)
            bloom.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(bloom)
            p.drawRect(self.rect())
            p.restore()

            pip_cx = 10.0
            pip_cy = self.height() / 2.0
            if is_checked:
                draw_pip(p, pip_cx, pip_cy, 10, 204, 82, 130,
                         bloom_alpha=55, core_alpha=200)
            else:
                draw_pip(p, pip_cx, pip_cy, 8, 240, 168, 48,
                         bloom_alpha=28, core_alpha=130)
            p.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# _DeadlineSection — non-collapsible timeline bucket header
# ---------------------------------------------------------------------------

class _DeadlineSection(QWidget):
    """Non-collapsible colored header for a deadline timeline bucket."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 2)
        lo.setSpacing(6)

        # Colored left accent bar
        bar = QFrame()
        bar.setFixedSize(2, 12)
        bar.setStyleSheet(f"background: {color}; border: none;")
        lo.addWidget(bar)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {px(9)}px; font-weight: bold;"
            f" letter-spacing: 1.5px; background: transparent; border: none;"
        )
        lo.addWidget(lbl)
        lo.addStretch()


# ---------------------------------------------------------------------------
# _GroupSection — collapsible assignment-group section
# ---------------------------------------------------------------------------

class _GroupSection(QWidget):
    """Collapsible assignment-group section for the 'group' view."""

    def __init__(self, group_name: str, parent=None):
        super().__init__(parent)
        self._group_name = group_name.upper()
        self._collapsed = False

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        self._hdr_btn = QPushButton()
        self._hdr_btn.setFlat(True)
        self._hdr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr_btn.clicked.connect(self._toggle)
        self._hdr_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {PHOSPHOR_MID};"
            f"  font-size: {px(10)}px; font-weight: bold; letter-spacing: 1px;"
            f"  background: transparent; border: none;"
            f"  text-align: left; padding: 8px 8px 3px 8px;"
            f"}}"
            f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
        )
        lo.addWidget(self._hdr_btn)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_lo = QVBoxLayout(self._container)
        self._container_lo.setContentsMargins(0, 0, 0, 4)
        self._container_lo.setSpacing(2)
        lo.addWidget(self._container)

        self._refresh_header()

    def add_row(self, row) -> None:
        self._container_lo.addWidget(row)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._container.setVisible(not self._collapsed)
        self._refresh_header()

    def _refresh_header(self) -> None:
        arrow = "v" if not self._collapsed else ">"
        self._hdr_btn.setText(f"{arrow}  {self._group_name}")


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-weight: 500;"
        f" letter-spacing: 0.8px; background: transparent; border: none;"
        f" text-transform: uppercase;"
    )
    return lbl


def _muted_label(text: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
        f" background: transparent; border: none; padding: 2px 0;"
    )
    return lbl



def _placeholder_layer(name: str) -> QWidget:
    """Styled placeholder for layers not yet implemented."""
    w = QWidget()
    lo = QVBoxLayout(w)
    lo.setContentsMargins(SPACING_LG, SPACING_LG * 2, SPACING_LG, SPACING_LG)
    lo.addStretch()
    title = QLabel(name.upper())
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(16)}px; letter-spacing: 4px;"
        f" background: transparent; border: none;"
    )
    lo.addWidget(title)
    sub = QLabel("Available after LLM analysis (Phase 2)")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setStyleSheet(
        f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
        f" background: transparent; border: none;"
    )
    lo.addWidget(sub)
    lo.addStretch()
    return w


# ---------------------------------------------------------------------------
# InsightsPanel
# ---------------------------------------------------------------------------

class InsightsPanel(QWidget):
    """Main panel for the Generate Insights feature.

    Replaces the placeholder in main_window.py.
    """

    analysis_started = Signal()
    paused_count_changed = Signal(int)   # emitted when incomplete-run count changes

    def __init__(self, api=None, store=None, demo_mode: bool = False, parent=None):
        super().__init__(parent)
        self._api = api
        self._store = store
        self._demo_mode = demo_mode
        self._courses_by_term: list = []
        self._assignments_cache: dict = {}
        self._current_run_id: Optional[str] = None
        self._loaded_layers: set = set()
        self._worker = None
        self._rerun_worker = None
        self._profile_mgr = None  # lazily initialized on first review
        self._assign_view_mode: str = "deadline"
        self._course_rows: list = []   # list of _CourseRow widgets
        self._assign_rows: list = []   # list of _AssignRow widgets
        self._course_scroll: QScrollArea = None
        self._assign_scroll: QScrollArea = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top navigation toggle (always visible) ──
        self._view_toggle = SegmentedToggle(
            ("Live Feed", "running"),
            ("Results", "review"),
            accent="amber",
        )
        self._view_toggle.mode_changed.connect(self._on_view_toggle)
        root.addWidget(self._view_toggle)

        self._state_stack = QStackedWidget()
        root.addWidget(self._state_stack, 1)

        # Three states (setup kept internally for running-state transitions)
        self._state_stack.addWidget(self._build_setup_view())     # 0 (internal)
        self._state_stack.addWidget(self._build_running_view())   # 1 live feed
        self._state_stack.addWidget(self._build_review_view())    # 2 results

        self._state_stack.setCurrentIndex(2)

    def _on_view_toggle(self, mode: str) -> None:
        """Handle top-level view toggle clicks."""
        idx = {"running": 1, "review": 2}.get(mode, 2)
        self._state_stack.setCurrentIndex(idx)

    def _switch_view(self, idx: int) -> None:
        """Switch state stack and sync the top navigation toggle."""
        # idx=0 (setup) is internal-only — redirect to Results so user sees content
        if idx == 0:
            idx = 2
        self._state_stack.setCurrentIndex(idx)
        mode = {1: "running", 2: "review"}.get(idx, "review")
        self._view_toggle.set_mode(mode)

    # ── Setup view ─────────────────────────────────────────────────────

    def _build_setup_view(self) -> QWidget:
        from PySide6.QtGui import QPalette, QColor

        page = QWidget()
        page.setAutoFillBackground(True)
        pal = page.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        page.setPalette(pal)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        outer.setSpacing(SPACING_MD)

        # Header
        title = QLabel("GENERATE INSIGHTS")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        sub = QLabel("Hear what your students said.")
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        outer.addWidget(title)
        outer.addWidget(sub)
        outer.addWidget(make_h_rule())

        # Incomplete-run notice (hidden until store has paused runs)
        self._incomplete_notice = QFrame()
        self._incomplete_notice.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER_AMBER}; "
            f"border-radius: 4px;"
        )
        _notice_lo = QHBoxLayout(self._incomplete_notice)
        _notice_lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        _notice_lo.setSpacing(SPACING_MD)
        self._incomplete_count_label = QLabel("")
        self._incomplete_count_label.setStyleSheet(
            f"color: {STATUS_WARN}; font-size: {px(11)}px; "
            f"background: transparent; border: none;"
        )
        _notice_lo.addWidget(self._incomplete_count_label, 1)
        _resume_notice_btn = QPushButton("View")
        make_secondary_button(_resume_notice_btn)
        _resume_notice_btn.setFixedWidth(60)
        _resume_notice_btn.clicked.connect(self._on_show_incomplete_run)
        _notice_lo.addWidget(_resume_notice_btn)
        self._incomplete_notice.setVisible(False)
        outer.addWidget(self._incomplete_notice)
        self._refresh_incomplete_notice()

        # Two-column: left = assignment selection, right = options
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)

        # ── Left: assignment selection ──
        left_pane = make_content_pane("insightsSelectPane")
        left_lo = QVBoxLayout(left_pane)
        left_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        left_lo.setSpacing(SPACING_SM)
        self._build_selection_pane(left_lo)
        splitter.addWidget(left_pane)

        # ── Right: options ──
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_pane = make_content_pane("insightsOptionsPane")
        right_lo = QVBoxLayout(right_pane)
        right_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        right_lo.setSpacing(SPACING_SM)
        self._build_options_pane(right_lo)
        right_scroll.setWidget(right_pane)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        # Footer
        outer.addWidget(make_h_rule())

        footer = QHBoxLayout()
        footer.setContentsMargins(0, SPACING_SM, 0, 0)
        self._setup_summary = QLabel("")
        self._setup_summary.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        footer.addWidget(self._setup_summary)
        footer.addStretch()

        self._review_btn = QPushButton("Prior Runs")
        make_secondary_button(self._review_btn)
        self._review_btn.clicked.connect(self._show_prior_insights)
        footer.addWidget(self._review_btn)

        setup_assistant_btn = QPushButton("Setup Assistant")
        make_secondary_button(setup_assistant_btn)
        setup_assistant_btn.clicked.connect(self._show_setup_assistant)
        footer.addWidget(setup_assistant_btn)

        self._start_btn = QPushButton("▶  Start Analysis")
        self._start_btn.clicked.connect(self._on_start_analysis)
        make_run_button(self._start_btn)
        footer.addWidget(self._start_btn)
        outer.addLayout(footer)

        return page

    def _build_selection_pane(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Select Assignments"))
        lo.addWidget(make_h_rule())
        lo.addWidget(_muted_label(
            "Check courses, then check assignments to analyze. "
            "Each course is analyzed separately — results never conflated."
        ))

        lists = QHBoxLayout()
        lists.setSpacing(SPACING_SM)

        # ── Course column ─────────────────────────────────────────────────
        course_col = QVBoxLayout()
        course_col.setSpacing(2)
        course_col.addWidget(_field_label("Courses"))

        self._course_scroll = QScrollArea()
        self._course_scroll.setWidgetResizable(True)
        self._course_scroll.setStyleSheet(_SCROLL_QSS)
        _empty_courses = QWidget()
        _empty_courses.setStyleSheet(f"background: {BG_INSET};")
        self._course_scroll.setWidget(_empty_courses)
        course_col.addWidget(self._course_scroll, 1)
        lists.addLayout(course_col, 1)

        # ── Assignment column ─────────────────────────────────────────────
        assign_col = QVBoxLayout()
        assign_col.setSpacing(2)

        # Header row: label + view toggle
        assign_hdr = QHBoxLayout()
        assign_hdr.setSpacing(SPACING_SM)
        assign_hdr.addWidget(_field_label("Assignments"))
        assign_hdr.addStretch()
        self._assign_view_toggle = ViewToggle(
            left_label="Deadline", right_label="Group",
            left_mode="deadline", right_mode="group",
        )
        self._assign_view_toggle.mode_changed.connect(self._on_assign_view_changed)
        assign_hdr.addWidget(self._assign_view_toggle)
        assign_col.addLayout(assign_hdr)

        # Quick-select chips
        qs_row = QHBoxLayout()
        qs_row.setSpacing(4)
        qs_row.setContentsMargins(0, 2, 0, 2)
        self._qs_this_week = PhosphorChip("This Week", accent="amber", action=True)
        self._qs_this_week.toggled.connect(self._qs_select_this_week)
        self._qs_past_due = PhosphorChip("Past Due", accent="amber", action=True)
        self._qs_past_due.toggled.connect(self._qs_select_past_due)
        self._qs_with_subs = PhosphorChip("With Submissions", accent="amber", action=True)
        self._qs_with_subs.toggled.connect(self._qs_select_with_submissions)
        _qs_none = PhosphorChip("None", accent="rose", action=True)
        _qs_none.toggled.connect(lambda _: [r.set_checked(False) for r in self._assign_rows] or self._update_summary())
        qs_row.addWidget(self._qs_this_week)
        qs_row.addWidget(self._qs_past_due)
        qs_row.addWidget(self._qs_with_subs)
        qs_row.addWidget(_qs_none)
        qs_row.addStretch()
        assign_col.addLayout(qs_row)

        self._assign_scroll = QScrollArea()
        self._assign_scroll.setWidgetResizable(True)
        self._assign_scroll.setStyleSheet(_SCROLL_QSS)
        _empty_assigns = QWidget()
        _empty_assigns.setStyleSheet(f"background: {BG_INSET};")
        self._assign_scroll.setWidget(_empty_assigns)
        assign_col.addWidget(self._assign_scroll, 1)
        lists.addLayout(assign_col, 2)

        lo.addLayout(lists, 1)

    def _build_options_pane(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Analysis Options"))
        lo.addWidget(make_h_rule())

        # Analysis depth
        lo.addWidget(_field_label("Analysis Depth"))
        self._depth_toggle = SegmentedToggle(
            ("Quick", "quick"),
            ("Lightweight", "lightweight"),
            ("Medium", "medium"),
            ("Deep Thinking", "deep_thinking"),
            accent="amber",
        )
        # Restore last-used tier from settings (Issue 9)
        from settings import load_settings as _load_s
        _saved_tier = _load_s().get("insights_model_tier", "auto")
        if _saved_tier != "auto":
            self._depth_toggle.set_mode(_saved_tier)
        self._depth_toggle.mode_changed.connect(self._on_depth_changed)
        self._depth_toggle.mode_changed.connect(lambda _: self._update_summary())
        lo.addWidget(self._depth_toggle)
        self._depth_desc = _muted_label(
            "Quick: patterns only, no AI — instant results. "
            "Lightweight: local 8B model, many focused prompts, best overnight."
        )
        lo.addWidget(self._depth_desc)

        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("Preprocessing"))

        self._translate_toggle = SwitchToggle(
            "Translate non-English submissions", wrap_width=200
        )
        self._translate_toggle.setChecked(True)
        lo.addWidget(self._translate_toggle)

        self._transcribe_toggle = SwitchToggle(
            "Transcribe audio/video submissions", wrap_width=200
        )
        self._transcribe_toggle.setChecked(True)
        lo.addWidget(self._transcribe_toggle)

        self._handwriting_toggle = SwitchToggle(
            "Transcribe handwritten notes (photos)", wrap_width=220
        )
        self._handwriting_toggle.setChecked(False)
        lo.addWidget(self._handwriting_toggle)
        self._handwriting_warn = _muted_label(
            "Slow (30-60s/image). Requires vision model in Ollama. "
            "You will verify each transcription before it enters analysis."
        )
        lo.addWidget(self._handwriting_warn)

        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("Draft Feedback"))

        self._feedback_toggle = SwitchToggle(
            "Generate draft feedback for each student", wrap_width=220
        )
        lo.addWidget(self._feedback_toggle)
        lo.addWidget(_muted_label(
            "Based on your analysis lens. You review and approve before posting."
        ))

        # Per-run enhancement toggle (Issue 15c)
        from settings import load_settings as _load_settings
        _s = _load_settings()
        _cloud_privacy = _s.get("insights_cloud_privacy", "")
        if _cloud_privacy in ("free_enhancement", "privacy_enhancement"):
            lo.addWidget(make_h_rule())
            self._enhance_toggle = SwitchToggle(
                "Enhance analysis with cloud service", wrap_width=220
            )
            self._enhance_toggle.setChecked(True)
            lo.addWidget(self._enhance_toggle)
            lo.addWidget(_muted_label(
                "Sends anonymized class patterns after local analysis "
                "completes. ~20 seconds."
            ))
        else:
            self._enhance_toggle = None

        # AI use policy (Issue 12) — resets to default each time
        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("AI USE POLICY"))
        self._ai_policy_combo = CRTComboBox()
        self._ai_policy_combo.addItem("AI use not expected", "not_expected")
        self._ai_policy_combo.addItem("AI prohibited for this assignment", "prohibited")
        self._ai_policy_combo.addItem("AI allowed / encouraged", "allowed")
        self._ai_policy_combo.setFixedWidth(280)
        lo.addWidget(self._ai_policy_combo)
        lo.addWidget(_muted_label(
            "How the system handles submissions flagged as likely AI-generated."
        ))

        lo.addWidget(make_h_rule())

        # Subject template picker
        lo.addWidget(make_section_label("Subject Area"))
        self._subject_combo = CRTComboBox()
        from insights.lens_templates import get_template_choices, get_template
        for key, display in get_template_choices():
            self._subject_combo.addItem(display, key)
        self._subject_combo.currentIndexChanged.connect(self._on_template_changed)
        lo.addWidget(self._subject_combo)
        lo.addWidget(_muted_label(
            "Populates defaults below. You can edit everything."
        ))

        # Course profile selector
        lo.addSpacing(4)
        lo.addWidget(make_section_label("Course Profile"))
        profile_row = QHBoxLayout()
        self._profile_combo = CRTComboBox()
        self._profile_combo.addItem("Default (shared)", "default")
        profile_row.addWidget(self._profile_combo, 1)
        manage_profile_btn = QPushButton("Manage…")
        make_secondary_button(manage_profile_btn)
        manage_profile_btn.clicked.connect(self._on_manage_profiles)
        profile_row.addWidget(manage_profile_btn)
        lo.addLayout(profile_row)
        lo.addWidget(_muted_label(
            "Each course saves its own concern vocabulary and patterns. "
            "Ethnic Studies and Native Studies each get their own profile."
        ))
        self._refresh_profile_combo()

        lo.addWidget(make_h_rule())

        # Teacher input (collapsible sections — autopopulated from template)
        lo.addWidget(make_section_label("What are you listening for?"))
        lo.addWidget(_muted_label(
            "Defaults from your subject template. Edit to customize."
        ))

        self._lens_input = self._build_collapsible("Analysis Lens", lo,
            "What kinds of thinking are you looking for?")
        self._focus_input = self._build_collapsible("Focus Areas", lo,
            "What matters most? Rank your top priorities.")
        self._equity_input = self._build_collapsible("Equity Surfacing", lo,
            "What structural patterns should the analysis surface?")
        self._week_input = self._build_collapsible("This Week", lo,
            "Context for the analysis. e.g., 'We just discussed racial formation theory'")
        self._next_week_input = self._build_collapsible("Next Week", lo,
            "What's coming next? Helps forward-looking recommendations.")

        # Word count warning for teacher inputs (8B context budget)
        self._input_warning = QLabel("")
        self._input_warning.setWordWrap(True)
        self._input_warning.setStyleSheet(
            f"color: {STATUS_WARN}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 2px 0;"
        )
        self._input_warning.setVisible(False)
        lo.addWidget(self._input_warning)

        # Connect text changes to word count check
        for te in (self._lens_input, self._focus_input, self._equity_input,
                    self._week_input, self._next_week_input):
            te.textChanged.connect(self._check_input_length)

        # Restore defaults button
        restore_btn = QPushButton("Restore Defaults")
        restore_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
            f" padding: 3px 10px; font-size: {px(11)}px; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_MID};"
            f" border-color: {BORDER_AMBER}; }}"
        )
        restore_btn.clicked.connect(self._restore_template_defaults)
        lo.addWidget(restore_btn)

        # Populate from default template
        self._on_template_changed(0)

        lo.addStretch()

    def _on_template_changed(self, index: int) -> None:
        """Autopopulate fields from the selected subject template."""
        from insights.lens_templates import get_template
        key = self._subject_combo.currentData()
        if not key:
            return
        tmpl = get_template(key)
        if not tmpl:
            return

        # Populate analysis lens
        self._lens_input.setPlainText("\n".join(tmpl.analysis_lens))

        # Populate focus areas
        self._focus_input.setPlainText("\n".join(tmpl.default_interests))

        # Populate equity surfacing with teacher-facing framing
        self._equity_input.setPlainText(tmpl.equity_attention_framing)

        # Save subject to profile
        if self._profile_mgr:
            self._profile_mgr.record_subject_area(key)

    def _restore_template_defaults(self) -> None:
        """Reset all teacher input fields to the current template defaults."""
        self._on_template_changed(self._subject_combo.currentIndex())

    def _refresh_profile_combo(self) -> None:
        """Reload the course profile dropdown from the store."""
        if not self._store:
            return
        current = self._profile_combo.currentData() or "default"
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItem("Default (shared)", "default")
        for pid in self._store.list_profiles():
            if pid == "default":
                continue
            # Show display name if stored, else raw profile_id
            raw = self._store.get_profile(pid) or {}
            display = raw.get("custom_patterns", {}).get("_display_name", "") or pid
            self._profile_combo.addItem(display, pid)
        idx = self._profile_combo.findData(current)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)

    def _on_manage_profiles(self) -> None:
        """Open the Course Profile dialog."""
        if not self._store:
            return
        from gui.dialogs.course_profile_dialog import CourseProfileDialog
        current_pid = self._profile_combo.currentData() or "default"
        dlg = CourseProfileDialog(self._store, current_pid, parent=self)
        if dlg.exec():
            self._refresh_profile_combo()
            idx = self._profile_combo.findData(dlg.selected_profile_id)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
        else:
            self._refresh_profile_combo()

    def _check_input_length(self) -> None:
        """Warn if combined teacher input is too long for 8B context."""
        total_words = 0
        for te in (self._lens_input, self._focus_input, self._equity_input,
                    self._week_input, self._next_week_input):
            total_words += len(te.toPlainText().split())

        if total_words > 300:
            self._input_warning.setText(
                f"Your instructions are {total_words} words. For Lightweight "
                f"(8B) models, keeping this under 200 words gives the best "
                f"results — the model needs room to think about your students' "
                f"work. Medium and Deep Thinking models handle longer "
                f"instructions well."
            )
            self._input_warning.setVisible(True)
        elif total_words > 200:
            self._input_warning.setText(
                f"Your instructions are {total_words} words. This works fine "
                f"for Medium and Deep Thinking, but a Lightweight (8B) model "
                f"may not be able to attend to all of it. The most important "
                f"items should be near the top."
            )
            self._input_warning.setVisible(True)
        else:
            self._input_warning.setVisible(False)

    def _on_depth_changed(self, mode: str) -> None:
        """Enable/disable LLM-dependent options based on analysis depth."""
        is_quick = (mode == "quick")

        # Translation needs an LLM for the translation calls
        self._translate_toggle.setChecked(not is_quick and self._translate_toggle.isChecked())
        self._translate_toggle.setEnabled(not is_quick)

        # Draft feedback requires LLM
        self._feedback_toggle.setChecked(False if is_quick else self._feedback_toggle.isChecked())
        self._feedback_toggle.setEnabled(not is_quick)

        # Transcription uses Whisper (not an LLM) — stays available at all tiers
        # self._transcribe_toggle stays enabled

        # Update description
        descriptions = {
            "quick": (
                "Patterns only — no AI model needed. Keyword analysis, "
                "sentiment, clusters, and concern signals. Instant results."
            ),
            "lightweight": (
                "Uses your local 8B model. Breaks analysis into many "
                "focused prompts. Best run overnight."
            ),
            "medium": (
                "Uses a ~70B local model or institutional API. Fewer, "
                "richer prompts. Better at nuanced concerns and themes."
            ),
            "deep_thinking": (
                "Uses a frontier model (institutional API). Maximum "
                "analytical depth — nuanced cultural analysis, subtle "
                "pattern detection, interpretive synthesis."
            ),
        }
        self._depth_desc.setText(descriptions.get(mode, ""))

    def _build_collapsible(
        self, title: str, parent_lo: QVBoxLayout, placeholder: str
    ) -> QTextEdit:
        """Build a collapsible text input section. Returns the QTextEdit."""
        btn = QPushButton(f"▸ {title}")
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_MID};"
            f" border: none; text-align: left; padding: 4px 0;"
            f" font-size: {px(12)}px; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        te = QTextEdit()
        te.setPlaceholderText(placeholder)
        te.setMaximumHeight(60)
        te.setVisible(False)
        te.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" padding: 4px; }}"
        )

        def _toggle():
            visible = not te.isVisible()
            te.setVisible(visible)
            btn.setText(f"{'▾' if visible else '▸'} {title}")

        btn.clicked.connect(_toggle)
        parent_lo.addWidget(btn)
        parent_lo.addWidget(te)
        return te

    # ── Running view ───────────────────────────────────────────────────

    def _build_running_view(self) -> QWidget:
        from PySide6.QtGui import QPalette, QColor
        from PySide6.QtWidgets import QProgressBar

        page = QWidget()
        page.setAutoFillBackground(True)
        pal = page.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        page.setPalette(pal)

        lo = QVBoxLayout(page)
        lo.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        lo.setSpacing(SPACING_XS)

        # Header row: title + stage label
        header = QHBoxLayout()
        title = QLabel("GENERATE INSIGHTS")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        header.addWidget(title)
        header.addStretch()

        self._progress_label = QLabel("Preparing analysis...")
        self._progress_label.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        header.addWidget(self._progress_label)
        lo.addLayout(header)

        # Progress bar — thin amber gradient
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(10)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{"
            f"  background: {BG_INSET};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-radius: 3px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {AMBER_BTN}, stop:1 {PHOSPHOR_HOT});"
            f"  border-radius: 2px;"
            f"}}"
        )
        lo.addWidget(self._progress_bar)

        # Stage info row: stage description (primary, left) + elapsed (secondary, right)
        stage_row = QHBoxLayout()
        stage_row.setContentsMargins(0, SPACING_XS, 0, SPACING_XS)
        self._stage_desc_label = QLabel("")
        self._stage_desc_label.setWordWrap(True)
        self._stage_desc_label.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-style: italic; background: transparent; border: none;"
        )
        stage_row.addWidget(self._stage_desc_label, 1)
        self._elapsed_label = QLabel("")
        self._elapsed_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        stage_row.addWidget(self._elapsed_label)
        lo.addLayout(stage_row)

        # Elapsed timer
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._elapsed_start = None

        # Split pane: left = system log, right = live results
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)

        # ── Left: system log ──
        log_frame = QFrame()
        log_frame.setStyleSheet(f"QFrame {{ background: transparent; border: none; }}")
        log_lo = QVBoxLayout(log_frame)
        log_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        log_lo.setSpacing(SPACING_XS)
        log_lo.addWidget(make_section_label("System Log"))

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {BG_INSET};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-radius: 6px;"
            f"  color: {PHOSPHOR_DIM};"
            f"  font-family: 'JetBrains Mono', 'Cascadia Code', 'Menlo',"
            f"   'Consolas', monospace;"
            f"  font-size: {px(10)}px;"
            f"  padding: 6px;"
            f"  selection-background-color: {PHOSPHOR_GLOW};"
            f"  selection-color: {PHOSPHOR_HOT};"
            f"}}"
        )
        log_lo.addWidget(self._log_output, 1)
        splitter.addWidget(log_frame)

        # ── Right: live results feed ──
        results_frame = QFrame()
        results_frame.setStyleSheet(f"QFrame {{ background: transparent; border: none; }}")
        results_lo = QVBoxLayout(results_frame)
        results_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        results_lo.setSpacing(SPACING_XS)
        results_lo.addWidget(make_section_label("Live Results"))

        # Assignment header — updated when analysis starts
        self._live_header = QLabel("")
        self._live_header.setWordWrap(True)
        self._live_header.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none; padding: 2px 0;"
        )
        self._live_header.setVisible(False)
        results_lo.addWidget(self._live_header)

        self._live_scroll = QScrollArea()
        self._live_scroll.setWidgetResizable(True)
        self._live_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._live_container = QWidget()
        self._live_container.setStyleSheet(f"background: {BG_VOID};")
        self._live_lo = QVBoxLayout(self._live_container)
        self._live_lo.setContentsMargins(0, 0, SPACING_SM, 0)
        self._live_lo.setSpacing(SPACING_SM)
        self._live_lo.addStretch()
        self._live_scroll.setWidget(self._live_container)
        results_lo.addWidget(self._live_scroll, 1)

        splitter.addWidget(results_frame)
        splitter.setSizes([300, 600])
        lo.addWidget(splitter, 1)

        # Kept for compatibility
        self._progress_detail = QLabel("")
        self._progress_detail.setVisible(False)

        # Footer: cancel only — teacher navigates away freely
        footer = QHBoxLayout()
        footer.addStretch()
        self._cancel_btn = QPushButton("Cancel Analysis")
        self._cancel_btn.clicked.connect(self._on_cancel)
        footer.addWidget(self._cancel_btn)
        lo.addLayout(footer)

        return page

    def _append_log(self, message: str) -> None:
        """Append a line to the system log and auto-scroll."""
        from PySide6.QtGui import QTextCursor
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        if message.startswith("[") or "Stage" in message or "complete" in message.lower():
            color = PHOSPHOR_HOT
        elif "error" in message.lower() or "failed" in message.lower():
            color = BURN_RED
        elif "✓" in message or "ready" in message.lower():
            color = TERM_GREEN
        else:
            color = PHOSPHOR_DIM
        html = (
            f'<span style="color:{PHOSPHOR_DIM};">{ts}</span>'
            f'  <span style="color:{color};">{message}</span>'
        )
        self._log_output.append(html)
        cursor = self._log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_output.setTextCursor(cursor)

    def _append_live_result(self, result_type: str, data) -> None:
        """Add a live result card to the results feed as it comes in."""
        try:
            self._append_live_result_inner(result_type, data)
        except Exception as e:
            # Don't let a rendering error kill the live feed
            self._append_log(f"Live preview error: {e}")

    def _append_live_result_inner(self, result_type: str, data) -> None:
        if not isinstance(data, dict):
            try:
                data = data if isinstance(data, dict) else {}
            except Exception:
                data = {}

        # Insert before the stretch at the bottom
        insert_idx = max(0, self._live_lo.count() - 1)

        if result_type == "coding":
            # Per-student coding result — show name, themes, quote
            name = data.get("student_name", "Unknown")
            tags = data.get("theme_tags", [])
            quotes = data.get("notable_quotes", [])
            register = data.get("emotional_register", "")
            concerns = data.get("concerns", [])

            accent_color = ROSE_ACCENT if concerns else BORDER_AMBER
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {BG_CARD};"
                f" border: 1px solid {BORDER_DARK}; border-radius: 6px;"
                f" border-left: 3px solid {accent_color}; }}"
            )
            clo = QVBoxLayout(card)
            clo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            clo.setSpacing(2)

            # Name + register on one line
            reg_text = f"  \u00b7  {register}" if register else ""
            header = QLabel(f"{name}{reg_text}")
            header.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            clo.addWidget(header)

            # Student's original text (so teacher sees what was analyzed)
            orig_text = data.get("_original_text", "")
            if orig_text:
                display_orig = orig_text[:250]
                if len(orig_text) > 250:
                    display_orig += "..."
                orig_lbl = QLabel(display_orig)
                orig_lbl.setWordWrap(True)
                orig_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                    f" padding: 2px 0 4px 0;"
                )
                clo.addWidget(orig_lbl)

            # Theme tags as inline wrapped text (subtle, not glowy chips)
            if tags:
                tag_text = "  \u00b7  ".join(tags[:5])
                tag_lbl = QLabel(tag_text)
                tag_lbl.setWordWrap(True)
                tag_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                    f" padding: 1px 0;"
                )
                clo.addWidget(tag_lbl)

            # Best quote — or original text if model returned nothing
            quote_text = ""
            if quotes:
                q = quotes[0]
                quote_text = q.get("text", "") if isinstance(q, dict) else str(q)

            if not quote_text and not tags:
                # Sparse result — show the student's own words
                orig = data.get("_original_text", "")
                if orig:
                    quote_text = orig
                    sparse_note = QLabel("(model returned limited analysis — student text shown)")
                    sparse_note.setWordWrap(True)
                    sparse_note.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
                        f" background: transparent; border: none;"
                    )
                    clo.addWidget(sparse_note)

            if quote_text:
                display = quote_text[:300]
                if len(quote_text) > 300:
                    display += "..."
                qlbl = QLabel(f"\u201c{display}\u201d")
                qlbl.setWordWrap(True)
                qlbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" font-style: italic;"
                    f" background: transparent; border: none;"
                    f" padding: 2px 0;"
                )
                clo.addWidget(qlbl)

            # Concern flag
            if concerns:
                flag = QLabel(f"\u26a0 {len(concerns)} passage{'s' if len(concerns) != 1 else ''} flagged for review")
                flag.setWordWrap(True)
                flag.setStyleSheet(
                    f"color: {ROSE_ACCENT}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                clo.addWidget(flag)

            self._live_lo.insertWidget(insert_idx, card)

        elif result_type == "theme":
            # Theme result — show theme name + student count
            name = data.get("name", "Unnamed")
            freq = data.get("frequency", 0)
            desc = data.get("description", "")

            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {BG_CARD};"
                f" border: 1px solid {AMBER_BTN}; border-radius: 6px;"
                f" border-left: 3px solid {AMBER_BTN}; }}"
            )
            clo = QVBoxLayout(card)
            clo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            clo.setSpacing(2)

            header = QLabel(f"\u25c6 {name}  ({freq} students)")
            header.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            clo.addWidget(header)

            if desc:
                dlbl = QLabel(desc[:150])
                dlbl.setWordWrap(True)
                dlbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                clo.addWidget(dlbl)

            self._live_lo.insertWidget(insert_idx, card)

        elif result_type == "contradiction":
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {BG_CARD};"
                f" border: 1px solid {STATUS_WARN}; border-radius: 6px;"
                f" border-left: 3px solid {STATUS_WARN}; }}"
            )
            clo = QVBoxLayout(card)
            clo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            clo.setSpacing(2)

            header = QLabel(f"\u26a1 Tension: {data.get('description', '')[:100]}")
            header.setWordWrap(True)
            header.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            clo.addWidget(header)
            self._live_lo.insertWidget(insert_idx, card)

        elif result_type == "outlier":
            name = data.get("student_name", "Unknown")
            why = data.get("why_notable", "")

            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {BG_CARD};"
                f" border: 1px solid {TERM_GREEN}; border-radius: 6px;"
                f" border-left: 3px solid {TERM_GREEN}; }}"
            )
            clo = QVBoxLayout(card)
            clo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            clo.setSpacing(2)

            header = QLabel(f"\u2726 {name} — unique voice")
            header.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            clo.addWidget(header)

            if why:
                wlbl = QLabel(why[:120])
                wlbl.setWordWrap(True)
                wlbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                clo.addWidget(wlbl)

            self._live_lo.insertWidget(insert_idx, card)

        elif result_type == "reading":
            # Student's actual text — shown while LLM is processing
            name = data.get("student_name", "")
            text = data.get("text", "")
            wc = data.get("word_count", 0)

            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {BG_INSET};"
                f" border: 1px solid {BORDER_DARK}; border-radius: 6px;"
                f" border-left: 3px solid {PHOSPHOR_DIM}; }}"
            )
            clo = QVBoxLayout(card)
            clo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            clo.setSpacing(2)

            header = QLabel(f"{name}  ·  {wc} words  ·  reading...")
            header.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            clo.addWidget(header)

            # Show the actual student text (truncated)
            preview = text[:400]
            if len(text) > 400:
                preview += "..."
            txt_lbl = QLabel(preview)
            txt_lbl.setWordWrap(True)
            txt_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
                f" font-style: italic; padding: 2px 0;"
            )
            clo.addWidget(txt_lbl)

            self._live_lo.insertWidget(insert_idx, card)

        elif result_type == "stage":
            # Stage transition marker
            stage_text = data.get("stage", "")
            label = QLabel(f"── {stage_text} ──")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
                f" letter-spacing: 1px; background: transparent; border: none;"
                f" padding: 4px 0;"
            )
            self._live_lo.insertWidget(insert_idx, label)

            # Update the header when batch moves to a new assignment
            if stage_text.startswith("RUN "):
                # Strip "RUN 2/3: " prefix to get the assignment info
                header_text = stage_text.split(": ", 1)[-1] if ": " in stage_text else stage_text
                self._live_header.setText(header_text)

        # Auto-scroll to bottom
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._live_scroll.verticalScrollBar().setValue(
            self._live_scroll.verticalScrollBar().maximum()
        ))

    # ── Review view ────────────────────────────────────────────────────

    def _build_review_view(self) -> QWidget:
        from PySide6.QtGui import QPalette, QColor

        page = QWidget()
        page.setAutoFillBackground(True)
        pal = page.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        page.setPalette(pal)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        outer.setSpacing(SPACING_MD)

        # Results header: section label + New Analysis action
        results_hdr = QHBoxLayout()
        results_hdr.setSpacing(SPACING_SM)
        results_hdr.addStretch()
        self._new_analysis_btn = QPushButton("+ New Analysis")
        make_secondary_button(self._new_analysis_btn)
        self._new_analysis_btn.clicked.connect(
            lambda: self._state_stack.setCurrentIndex(0)
        )
        results_hdr.addWidget(self._new_analysis_btn)
        outer.addLayout(results_hdr)

        # Layer tabs
        self._layer_toggle = SegmentedToggle(
            ("Patterns", "patterns"),
            ("Student Work", "codings"),
            ("Themes", "themes"),
            ("Outliers", "outliers"),
            ("Report", "report"),
            accent="amber",
        )
        self._layer_toggle.mode_changed.connect(self._on_layer_changed)

        # Layer toggle row: tabs + action buttons + re-run dropdown
        layer_row = QHBoxLayout()
        layer_row.setSpacing(SPACING_SM)
        layer_row.addWidget(self._layer_toggle, 1)

        self._resume_btn = QPushButton("▶  Resume")
        self._resume_btn.clicked.connect(self._on_resume_run)
        make_run_button(self._resume_btn)
        self._resume_btn.setVisible(False)
        layer_row.addWidget(self._resume_btn)

        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._on_export_chatbot)
        make_secondary_button(self._export_btn)
        self._export_btn.setVisible(False)
        layer_row.addWidget(self._export_btn)

        self._rerun_combo = CRTComboBox()
        self._rerun_combo.addItems([
            "Re-run...",
            "Re-generate Themes",
            "Re-generate Report",
            "Re-generate All (themes + report)",
        ])
        self._rerun_combo.setFixedWidth(175)
        self._rerun_combo.activated.connect(self._on_rerun_selected)
        layer_row.addWidget(self._rerun_combo)

        outer.addLayout(layer_row)

        # Placeholder shown when no run is loaded
        self._review_placeholder = QLabel(
            "Select an assignment to view insights."
        )
        self._review_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._review_placeholder.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(13)}px;"
            f" background: transparent; border: none;"
        )

        # Layer content stack
        self._layer_stack = QStackedWidget()
        self._patterns_scroll = self._build_patterns_layer()
        self._layer_stack.addWidget(self._patterns_scroll)           # 0: patterns
        self._codings_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._codings_scroll)            # 1: codings
        self._themes_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._themes_scroll)             # 2: themes
        self._outliers_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._outliers_scroll)           # 3: outliers
        self._report_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._report_scroll)             # 4: report
        self._feedback_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._feedback_scroll)              # 5: feedback
        self._semester_scroll = self._build_scrollable_layer()
        self._layer_stack.addWidget(self._semester_scroll)              # 6: semester

        # Wrapper stack: placeholder vs layer content
        self._review_content_stack = QStackedWidget()
        self._review_content_stack.addWidget(self._review_placeholder)  # 0: placeholder
        self._review_content_stack.addWidget(self._layer_stack)         # 1: layers
        self._review_content_stack.setCurrentIndex(0)

        outer.addWidget(self._review_content_stack, 1)
        return page

    def _build_patterns_layer(self) -> QScrollArea:
        """Build the scrollable Patterns layer for the review view."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet(f"background: {BG_VOID};")
        self._patterns_lo = QVBoxLayout(container)
        self._patterns_lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_MD)
        self._patterns_lo.setSpacing(SPACING_MD)

        # Placeholder until results are loaded
        self._patterns_placeholder = QLabel("Select a completed run to view patterns.")
        self._patterns_placeholder.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none; padding: 20px;"
        )
        self._patterns_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._patterns_lo.addWidget(self._patterns_placeholder)
        self._patterns_lo.addStretch()

        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Populate patterns from QuickAnalysisResult
    # ------------------------------------------------------------------

    def _display_patterns(self, qa_json: str) -> None:
        """Populate the Patterns layer from a QuickAnalysisResult JSON."""
        try:
            from insights.models import QuickAnalysisResult
            qa = QuickAnalysisResult.model_validate_json(qa_json)
        except Exception as e:
            self._patterns_placeholder.setText(f"Error loading results: {e}")
            return

        # Clear existing content
        while self._patterns_lo.count():
            item = self._patterns_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ── Header ──
        header = QLabel(
            f"{qa.assignment_name}  ·  {qa.stats.total_submissions} submissions"
        )
        header.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        self._patterns_lo.addWidget(header)

        # ── Submission Patterns ──
        self._add_stats_card(qa)

        # ── Top Terms ──
        self._add_terms_card(qa)

        # ── Sentiment Distribution ──
        self._add_sentiment_card(qa)

        # ── Natural Clusters ──
        self._add_clusters_card(qa)

        # ── Keyword Patterns ──
        self._add_keywords_card(qa)

        # ── Concern Signals ──
        self._add_concerns_card(qa)

        # ── Shared References ──
        self._add_references_card(qa)

        # ── Contradictions ──
        if qa.contradictions:
            self._add_contradictions_card(qa)

        self._patterns_lo.addStretch()

    def _add_stats_card(self, qa) -> None:
        pane = make_content_pane("patternsStats")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Submission Patterns"))

        s = qa.stats
        lines = [
            f"Word count:  avg {s.word_count_mean:.0f},  "
            f"median {s.word_count_median:.0f},  "
            f"range {s.word_count_min}–{s.word_count_max}",
        ]
        if s.format_breakdown:
            parts = [f"{c} {fmt}" for fmt, c in sorted(
                s.format_breakdown.items(), key=lambda x: -x[1]
            )]
            lines.append(f"Formats:  {', '.join(parts)}")
        if s.timing:
            parts = [f"{c} {k.replace('_', ' ')}" for k, c in s.timing.items() if c > 0]
            lines.append(f"Timing:  {', '.join(parts)}")

        for line in lines:
            lbl = QLabel(line)
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(lbl)

        self._patterns_lo.addWidget(pane)

    def _add_terms_card(self, qa) -> None:
        if not qa.top_terms and not qa.tfidf_terms:
            return
        pane = make_content_pane("patternsTerms")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("What Students Are Talking About"))
        lo.addWidget(_muted_label(
            "Distinctive terms from across submissions, shown with context."
        ))

        # Build term → example context lookup from keyword_hits
        import re as _re

        def _term_in_text(term: str, text: str) -> bool:
            """Word-boundary match to avoid 'race' matching 'embrace'."""
            return bool(_re.search(
                r'\b' + _re.escape(term.lower()) + r'\b', text.lower()
            ))

        term_contexts: Dict[str, List[str]] = {}
        for hit_name, hit in qa.keyword_hits.items():
            for ex in hit.examples[:3]:
                for t in (qa.tfidf_terms or []):
                    if _term_in_text(t.term, ex):
                        term_contexts.setdefault(t.term, []).append(ex)
                for t in (qa.top_terms or []):
                    if _term_in_text(t.term, ex):
                        term_contexts.setdefault(t.term, []).append(ex)

        # TF-IDF terms with context
        if qa.tfidf_terms:
            lo.addWidget(_muted_label(
                "Distinctive terms (what stands out in this class's writing):"
            ))
            for t in qa.tfidf_terms[:10]:
                term_row = QVBoxLayout()
                term_row.setSpacing(1)

                term_lbl = QLabel(f"\u25b8  {t.term}  (score: {t.score:.3f})")
                term_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                    f" font-weight: bold; background: transparent; border: none;"
                )
                term_row.addWidget(term_lbl)

                # Show example contexts
                contexts = term_contexts.get(t.term, [])
                for ctx in contexts[:2]:
                    ctx_lbl = QLabel(f"    {ctx[:120]}")
                    ctx_lbl.setWordWrap(True)
                    ctx_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                        f" font-style: italic;"
                        f" background: transparent; border: none;"
                    )
                    term_row.addWidget(ctx_lbl)

                # Which clusters this term appears in
                for cl in qa.clusters:
                    if t.term in cl.top_terms:
                        names = ", ".join(cl.student_names[:3])
                        extra = f" + {cl.size - 3} more" if cl.size > 3 else ""
                        cl_lbl = QLabel(
                            f"    Cluster {cl.cluster_id + 1}: {names}{extra}"
                        )
                        cl_lbl.setStyleSheet(
                            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                            f" background: transparent; border: none;"
                        )
                        term_row.addWidget(cl_lbl)
                        break  # show first cluster only

                lo.addLayout(term_row)

        # Frequency terms (condensed)
        if qa.top_terms:
            lo.addWidget(_muted_label("Most frequent terms:"))
            freq_terms = ", ".join(
                f"{t.term} ({t.count})" for t in qa.top_terms[:12]
            )
            freq_lbl = QLabel(freq_terms)
            freq_lbl.setWordWrap(True)
            freq_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(freq_lbl)

        self._patterns_lo.addWidget(pane)

    def _add_sentiment_card(self, qa) -> None:
        if not qa.sentiment_distribution:
            return
        pane = make_content_pane("patternsSentiment")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Sentiment Distribution"))

        parts = [
            f"{k.title()}: {v}" for k, v in
            sorted(qa.sentiment_distribution.items(), key=lambda x: -x[1])
        ]
        lbl = QLabel("  |  ".join(parts))
        lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(lbl)

        self._patterns_lo.addWidget(pane)

    def _add_clusters_card(self, qa) -> None:
        if not qa.clusters:
            return
        pane = make_content_pane("patternsClusters")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Natural Clusters"))
        lo.addWidget(_muted_label("Embedding-based groupings of similar submissions"))

        for cl in qa.clusters:
            names = ", ".join(cl.student_names[:5])
            if len(cl.student_names) > 5:
                names += f" + {len(cl.student_names) - 5} more"
            terms = ", ".join(cl.top_terms[:5]) if cl.top_terms else "\u2014"

            cl_lo = QVBoxLayout()
            cl_lo.setSpacing(1)

            header = QLabel(
                f"Cluster {cl.cluster_id + 1}  ({cl.size} students)  "
                f"\u00b7  {terms}"
            )
            header.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" font-weight: bold; background: transparent; border: none;"
            )
            cl_lo.addWidget(header)

            # Centroid text — representative excerpt
            if cl.centroid_text:
                centroid = QLabel(
                    f"  \u201c{cl.centroid_text[:150]}"
                    f"{'...' if len(cl.centroid_text) > 150 else ''}\u201d"
                )
                centroid.setWordWrap(True)
                centroid.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" font-style: italic;"
                    f" background: transparent; border: none;"
                )
                cl_lo.addWidget(centroid)

            names_lbl = QLabel(f"  {names}")
            names_lbl.setWordWrap(True)
            names_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none; padding: 0 0 4px 0;"
            )
            cl_lo.addWidget(names_lbl)
            lo.addLayout(cl_lo)

        if qa.embedding_outlier_ids:
            outlier_names = []
            for sid in qa.embedding_outlier_ids:
                sub = qa.per_submission.get(sid)
                if sub:
                    outlier_names.append(sub.student_name)
                else:
                    outlier_names.append(f"Student {sid}")
            lbl = QLabel(
                f"Outliers ({len(outlier_names)} students — may contain unique "
                f"perspectives):  {', '.join(outlier_names)}"
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {AMBER_BTN}; font-size: {px(12)}px;"
                f" background: transparent; border: none; padding: 2px 0;"
            )
            lo.addWidget(lbl)

        self._patterns_lo.addWidget(pane)

    def _add_keywords_card(self, qa) -> None:
        if not qa.keyword_hits:
            return
        pane = make_content_pane("patternsKeywords")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Keyword Patterns"))

        for name, hit in sorted(
            qa.keyword_hits.items(), key=lambda x: -x[1].count
        ):
            display = name.replace("_", " ").title()
            n_students = len(hit.student_ids)
            lbl = QLabel(
                f"{display}:  {hit.count} hits across {n_students} submissions"
            )
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(lbl)
            if hit.examples:
                for ex in hit.examples[:2]:
                    ex_lbl = QLabel(f"    {ex}")
                    ex_lbl.setWordWrap(True)
                    ex_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-style: italic;"
                        f" background: transparent; border: none;"
                    )
                    lo.addWidget(ex_lbl)

        self._patterns_lo.addWidget(pane)

    def _add_concerns_card(self, qa) -> None:
        if not qa.concern_signals:
            return
        pane = make_content_pane("patternsConcerns")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Concern Signals"))
        lo.addWidget(_muted_label(
            "Pre-screening from VADER sentiment + keyword patterns. "
            "These are signals for teacher review, not verdicts."
        ))

        # Group by signal type
        by_type: Dict[str, list] = {}
        for sig in qa.concern_signals:
            by_type.setdefault(sig.signal_type, []).append(sig)

        for stype in ("CONCERN", "CHECK IN", "POSSIBLE CONCERN",
                       "LOW ENGAGEMENT", "VERIFY", "SURFACE COMPLIANCE"):
            sigs = by_type.get(stype, [])
            if not sigs:
                continue
            # Color by severity
            if stype in ("CONCERN",):
                color = ROSE_ACCENT
            elif stype in ("CHECK IN", "POSSIBLE CONCERN"):
                color = AMBER_BTN
            else:
                color = PHOSPHOR_DIM

            type_lbl = QLabel(f"⚠ {stype}  ({len(sigs)} submissions)")
            type_lbl.setStyleSheet(
                f"color: {color}; font-size: {px(12)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(type_lbl)

            for sig in sigs:
                detail = QLabel(
                    f"    {sig.student_name}: {sig.interpretation}"
                )
                detail.setWordWrap(True)
                detail.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                lo.addWidget(detail)

        self._patterns_lo.addWidget(pane)

    def _add_references_card(self, qa) -> None:
        if not qa.shared_references:
            return
        pane = make_content_pane("patternsRefs")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Shared References"))
        lo.addWidget(_muted_label(
            "Texts, authors, and concepts mentioned by multiple students."
        ))

        # Build contradiction lookup for sentiment split
        contradiction_map: Dict[str, tuple] = {}
        for c in qa.contradictions:
            contradiction_map[c.reference] = (
                c.positive_students, c.negative_students
            )

        for ref in qa.shared_references[:10]:
            # Get student names
            names = []
            for sid in ref.student_ids[:5]:
                sub = qa.per_submission.get(sid)
                if sub:
                    names.append(sub.student_name)
            name_text = ", ".join(names)
            if ref.count > 5:
                name_text += f" + {ref.count - 5} more"

            # Check for sentiment split
            pos, neg = contradiction_map.get(ref.reference, ([], []))
            if pos and neg:
                sentiment_text = (
                    f"  \u00b7  {len(pos)} positive, {len(neg)} negative"
                )
                color = STATUS_WARN
            else:
                sentiment_text = ""
                color = PHOSPHOR_MID

            ref_lbl = QLabel(
                f'"{ref.reference}": {ref.count} submissions{sentiment_text}'
            )
            ref_lbl.setStyleSheet(
                f"color: {color}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(ref_lbl)

            if names:
                names_lbl = QLabel(f"    {name_text}")
                names_lbl.setWordWrap(True)
                names_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                lo.addWidget(names_lbl)

        self._patterns_lo.addWidget(pane)

    def _add_contradictions_card(self, qa) -> None:
        pane = make_content_pane("patternsContradictions")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        lo.setSpacing(4)
        lo.addWidget(make_section_label("Contradictions Detected"))
        lo.addWidget(_muted_label(
            "Opposing views on the same topic — pedagogically productive tensions."
        ))

        for c in qa.contradictions:
            lbl = QLabel(c.description)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {AMBER_BTN}; font-size: {px(12)}px;"
                f" background: transparent; border: none; padding: 2px 0;"
            )
            lo.addWidget(lbl)

        self._patterns_lo.addWidget(pane)

    # ------------------------------------------------------------------
    # Generic scrollable layer builder
    # ------------------------------------------------------------------

    def _build_scrollable_layer(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet(f"background: {BG_VOID};")
        lo = QVBoxLayout(container)
        lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_MD)
        lo.setSpacing(SPACING_MD)
        placeholder = QLabel("Select a completed run to view results.")
        placeholder.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none; padding: 20px;"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(placeholder)
        lo.addStretch()
        scroll.setWidget(container)
        return scroll

    def _clear_scroll_layout(self, scroll: QScrollArea) -> QVBoxLayout:
        """Clear a scrollable layer and return its layout."""
        container = scroll.widget()
        lo = container.layout()
        while lo.count():
            item = lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        return lo

    # ------------------------------------------------------------------
    # Student Work layer (coding records)
    # ------------------------------------------------------------------

    def _display_codings(self, run_id: str) -> None:
        """Populate the Student Work layer with interactive editing."""
        lo = self._clear_scroll_layout(self._codings_scroll)
        self._ensure_profile_mgr()

        if not self._store:
            lo.addWidget(_muted_label("No store available."))
            lo.addStretch()
            return

        codings = self._store.get_codings(run_id)
        if not codings:
            lo.addWidget(_muted_label("No coding records. Run LLM analysis to populate."))
            lo.addStretch()
            return

        # Collect all theme names for the add-tag combo
        all_tags = set()
        for row in codings:
            rec = row.get("coding_record", {})
            if isinstance(rec, str):
                try:
                    rec = json.loads(rec)
                except Exception:
                    rec = {}
            all_tags.update(rec.get("theme_tags", []))

        lo.addWidget(make_section_label(f"Student Work  ({len(codings)} submissions)"))
        lo.addWidget(make_h_rule())

        # ── Sort / filter bar ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACING_SM)

        sort_combo = CRTComboBox()
        sort_combo.addItems(["Sort: Name A–Z", "Sort: Name Z–A",
                             "Sort: Concerns first", "Sort: Word count ↓",
                             "Sort: Register"])
        sort_combo.setFixedWidth(170)
        filter_row.addWidget(sort_combo)

        filter_combo = CRTComboBox()
        filter_combo.addItems(["Show: All students",
                               "Show: Flagged concerns only",
                               "Show: Wellbeing signals",
                               "Show: Has analysis only",
                               "Show: Insufficient text"])
        filter_combo.setFixedWidth(200)
        filter_row.addWidget(filter_combo)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by name...")
        search_input.setFixedWidth(160)
        search_input.setStyleSheet(
            f"QLineEdit {{ background: {BG_INSET}; color: {PHOSPHOR_MID};"
            f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
            f" padding: 4px 8px; font-size: {px(11)}px; }}"
            f"QLineEdit:focus {{ border-color: {BORDER_AMBER}; }}"
        )
        filter_row.addWidget(search_input)

        filter_row.addStretch()
        lo.addLayout(filter_row)

        # Parse all records for sorting/filtering
        parsed_rows = []
        for row in codings:
            record = row.get("coding_record", {})
            if isinstance(record, str):
                try:
                    record = json.loads(record)
                except Exception:
                    record = {}
            parsed_rows.append((row, record))

        # Track container widget and layout for dynamic re-sorting
        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        cards_lo = QVBoxLayout(cards_container)
        cards_lo.setContentsMargins(0, 0, 0, 0)
        cards_lo.setSpacing(SPACING_SM)
        lo.addWidget(cards_container, 1)

        def _rebuild_cards():
            # Clear existing cards
            while cards_lo.count():
                item = cards_lo.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            sort_mode = sort_combo.currentText()
            filter_mode = filter_combo.currentText()

            # Filter
            visible = []
            for row_data, record in parsed_rows:
                concerns = list(record.get("concerns", []))
                tags = list(record.get("theme_tags", []))
                _skip_tags = {
                    "insufficient text for analysis",
                    "file upload — text not extracted",
                    "blank submission",
                }
                has_no_analysis = bool(_skip_tags & set(tags))

                if filter_mode == "Show: Flagged concerns only" and not concerns:
                    continue
                if filter_mode == "Show: Wellbeing signals":
                    _wb = record.get("wellbeing_axis", "")
                    _ci = record.get("checkin_flag")
                    if _wb not in ("CRISIS", "BURNOUT") and not _ci:
                        continue
                if filter_mode == "Show: Has analysis only" and has_no_analysis:
                    continue
                if filter_mode == "Show: Insufficient text" and not has_no_analysis:
                    continue
                visible.append((row_data, record))

            # Sort
            def _sort_key(item):
                _, rec = item
                name = rec.get("student_name", "")
                concerns = rec.get("concerns", [])
                wc = rec.get("word_count", 0)
                register = rec.get("emotional_register", "")
                if sort_mode == "Sort: Concerns first":
                    return (-len(concerns), name.lower())
                elif sort_mode == "Sort: Word count ↓":
                    return (-wc, name.lower())
                elif sort_mode == "Sort: Register":
                    return (register, name.lower())
                return name.lower()

            visible.sort(
                key=_sort_key,
                reverse=(sort_mode == "Sort: Name Z–A"),
            )
            # CRISIS and BURNOUT always float to the top regardless of sort mode.
            # Python's sort is stable, so relative order within each tier is
            # preserved from the user-selected sort above.
            visible.sort(key=lambda item: (
                0 if item[1].get("wellbeing_axis") == "CRISIS" else
                1 if item[1].get("wellbeing_axis") == "BURNOUT" else 2
            ))

            # Name search filter
            search_text = search_input.text().strip().lower()
            if search_text:
                visible = [c for c in visible if search_text in
                    (c[1].get("student_name", "") or c[0].get("student_name", "")).lower()]

            for row_data, record in visible:
                card = self._build_coding_card(
                    run_id, row_data, record, all_tags,
                )
                cards_lo.addWidget(card)

            cards_lo.addStretch()

        sort_combo.currentIndexChanged.connect(lambda _: _rebuild_cards())
        filter_combo.currentIndexChanged.connect(lambda _: _rebuild_cards())
        search_input.textChanged.connect(lambda _: _rebuild_cards())

        # Initial build
        _rebuild_cards()

        lo.addStretch()
        return

    def _build_coding_card(
        self, run_id: str, row: dict, record: dict, all_tags: set
    ) -> QWidget:
        """Build a single student coding card for the Student Work layer."""
        from gui.widgets.phosphor_chip import PhosphorChip

        sid = row.get("student_id", "")
        name = record.get("student_name", row.get("student_name", "Unknown"))
        tags = list(record.get("theme_tags", []))
        concerns = list(record.get("concerns", []))
        register = record.get("emotional_register", "")
        quotes = record.get("notable_quotes", [])
        wc = record.get("word_count", 0)
        existing_note = row.get("teacher_notes", "") or ""
        preprocessing = record.get("preprocessing") or {}
        is_image_transcribed = preprocessing.get("was_image_transcribed", False)

        pane = make_content_pane(f"coding_{sid}")
        pane_lo = QVBoxLayout(pane)
        pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        pane_lo.setSpacing(4)

        # ── Two-line header ──────────────────────────────────────────────────
        # Line 1: student name (left) + word count (right)
        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        header_row.addWidget(name_lbl, 1)
        if wc:
            wc_lbl = QLabel(f"{wc} words")
            wc_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            header_row.addWidget(wc_lbl)
        pane_lo.addLayout(header_row)

        # ── Observation (primary content — from observation architecture) ──
        obs_text = record.get("observation", "")
        if obs_text:
            obs_frame = self._build_observation_frame(record)
            pane_lo.addWidget(obs_frame)
            pane_lo.addWidget(make_h_rule())

        # ── Skip record: prior submission text + current submitted text ──
        # For blank/short submissions with no analysis, surface the student's
        # prior engagement so the teacher sees the full context on this card.
        _SKIP_TAG_SET = {
            "blank submission", "insufficient text for analysis",
            "audio/video submission", "image submission",
            "unsupported format", "non-analyzable text",
        }
        is_skip = bool(_SKIP_TAG_SET & set(tags))
        if is_skip and self._store:
            _run_meta = self._store.get_run(run_id)
            _course_id = str(_run_meta.get("course_id", "")) if _run_meta else ""
            if _course_id:
                _prior = self._store.get_most_recent_substantial_submission(
                    sid, _course_id, exclude_run_id=run_id
                )
                if _prior:
                    prior_frame = QFrame()
                    prior_frame.setStyleSheet(
                        f"QFrame {{ background: rgba(184,140,0,0.07);"
                        f" border-left: 3px solid {BORDER_AMBER};"
                        f" border-radius: 4px; }}"
                    )
                    pf_lo = QVBoxLayout(prior_frame)
                    pf_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
                    pf_lo.setSpacing(4)

                    _pa_name = _prior.get("assignment_name", "prior assignment")
                    _pa_wc = _prior.get("word_count", 0)
                    _pa_reg = _prior.get("emotional_register", "")
                    _pa_text = _prior.get("submission_text", "")

                    _hdr_parts = [_pa_name, f"{_pa_wc} words"]
                    if _pa_reg:
                        _hdr_parts.append(_pa_reg)
                    prior_hdr = QLabel(
                        "\u23ce Prior submission \u2014 " + "  \u00b7  ".join(_hdr_parts)
                    )
                    prior_hdr.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
                        f" font-family: {MONO_FONT}; background: transparent; border: none;"
                    )
                    pf_lo.addWidget(prior_hdr)

                    if _pa_text.strip():
                        prior_te = QTextBrowser()
                        _display_text = _pa_text[:900]
                        if len(_pa_text) > 900:
                            _display_text += "…"
                        prior_te.setPlainText(_display_text)
                        prior_te.setMaximumHeight(130)
                        prior_te.setStyleSheet(
                            f"QTextBrowser {{ background: {BG_INSET};"
                            f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
                            f" color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                            f" font-family: {MONO_FONT}; padding: 4px; }}"
                        )
                        pf_lo.addWidget(prior_te)

                    pane_lo.addWidget(prior_frame)
                    pane_lo.addWidget(make_h_rule())

            # Show what was actually submitted for this assignment (if any text)
            _sub_text = row.get("submission_text", "") or ""
            if _sub_text.strip() and wc > 0:
                curr_frame = QFrame()
                curr_frame.setStyleSheet(
                    f"QFrame {{ background: {BG_INSET};"
                    f" border-left: 2px solid {BORDER_DARK}; border-radius: 4px; }}"
                )
                cf_lo = QVBoxLayout(curr_frame)
                cf_lo.setContentsMargins(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS)
                cf_lo.setSpacing(2)
                curr_lbl = QLabel("Submitted text:")
                curr_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" font-family: {MONO_FONT}; background: transparent; border: none;"
                )
                cf_lo.addWidget(curr_lbl)
                curr_te = QTextBrowser()
                curr_te.setPlainText(_sub_text[:300])
                curr_te.setMaximumHeight(40)
                curr_te.setStyleSheet(
                    f"QTextBrowser {{ background: transparent; border: none;"
                    f" color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" font-family: {MONO_FONT}; padding: 0; }}"
                )
                cf_lo.addWidget(curr_te)
                pane_lo.addWidget(curr_frame)
                pane_lo.addWidget(make_h_rule())

        # ── Wellbeing classification (4-axis: Issue 16) ──
        wb_axis = record.get("wellbeing_axis", "")
        wb_signal = record.get("wellbeing_signal", "")
        wb_confidence = record.get("wellbeing_confidence", 0.0)
        checkin_flag = record.get("checkin_flag")
        checkin_reasoning = record.get("checkin_reasoning", "")

        # Show chips for non-ENGAGED axes (ENGAGED is the default — no chip)
        has_wb_display = (
            wb_axis in ("CRISIS", "BURNOUT")
            or (wb_axis == "ENGAGED" and checkin_flag)
        )
        if has_wb_display:
            wb_row = QHBoxLayout()
            wb_row.setSpacing(4)

            if wb_axis == "CRISIS":
                crisis_chip = PhosphorChip(
                    "\u26a0 CRISIS", active=True, accent="rose"
                )
                wb_row.addWidget(crisis_chip)
            elif wb_axis == "BURNOUT":
                burn_chip = PhosphorChip(
                    "\u25cb BURNOUT", active=True, accent="amber"
                )
                wb_row.addWidget(burn_chip)

            if checkin_flag:
                checkin_chip = PhosphorChip(
                    "? CHECK-IN", active=False, accent="amber"
                )
                wb_row.addWidget(checkin_chip)

            if wb_confidence > 0:
                conf_text = f"Confidence: {wb_confidence:.0%}"
                if wb_confidence < 0.75:
                    conf_text += " \u2014 review suggested"
                conf_lbl = QLabel(conf_text)
                conf_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                wb_row.addWidget(conf_lbl)

            wb_row.addStretch()
            pane_lo.addLayout(wb_row)

            # Signal explanation (the teacher-valuable part)
            signal_text = wb_signal or checkin_reasoning
            if signal_text:
                sig_frame = QFrame()
                sig_color = ROSE_ACCENT if wb_axis == "CRISIS" else PHOSPHOR_DIM
                sig_frame.setStyleSheet(
                    f"QFrame {{ background: {BG_INSET};"
                    f" border-left: 3px solid {sig_color};"
                    f" border-radius: 4px; padding: {SPACING_SM}px; }}"
                )
                sig_lo = QVBoxLayout(sig_frame)
                sig_lo.setContentsMargins(
                    SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM
                )
                sig_lo.setSpacing(SPACING_XS)

                sig_lbl = QLabel(signal_text)
                sig_lbl.setWordWrap(True)
                sig_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" font-style: italic; font-family: {MONO_FONT};"
                    f" background: transparent; border: none;"
                )
                sig_lo.addWidget(sig_lbl)
                pane_lo.addWidget(sig_frame)

            # Suggested actions
            if wb_axis == "CRISIS":
                action_lbl = QLabel(
                    "\u26a0 Consider connecting this student with your "
                    "school counselor."
                )
                action_lbl.setWordWrap(True)
                action_lbl.setStyleSheet(
                    f"color: {ROSE_ACCENT}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(action_lbl)
            elif wb_axis == "BURNOUT":
                action_lbl = QLabel(
                    "\u25cb Consider flexible timing or a check-in "
                    "about workload."
                )
                action_lbl.setWordWrap(True)
                action_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(action_lbl)
            # CHECK-IN: no prescribed action — signal text presents
            # competing interpretations, teacher decides

            pane_lo.addWidget(make_h_rule())

        # ── Integrity flag banner (Tier 1 — above engagement chips) ──
        integrity_flags = record.get("integrity_flags") or {}
        if integrity_flags:
            integrity_row = QHBoxLayout()
            integrity_row.setSpacing(4)

            if integrity_flags.get("smoking_gun"):
                sg_chip = PhosphorChip(
                    "\u26a0 Chatbot paste artifacts detected",
                    active=True, accent="rose",
                )
                details = integrity_flags.get("smoking_gun_details", [])
                if details:
                    sg_chip.setToolTip(
                        "Observed:\n" + "\n".join(
                            f"  \u2022 {d}" for d in details[:5]
                        )
                    )
                integrity_row.addWidget(sg_chip)

            if integrity_flags.get("unicode_manipulation"):
                um_details = integrity_flags.get(
                    "unicode_manipulation_details", []
                )
                # Sum invisible character counts from "Nx NAME" entries
                _um_total = 0
                for _d in um_details:
                    try:
                        _um_total += int(_d.split("x")[0])
                    except (ValueError, IndexError):
                        _um_total += 1
                um_text = "Text manipulation detected"
                if _um_total > 0:
                    um_text += f" ({_um_total} invisible character"
                    if _um_total != 1:
                        um_text += "s"
                    um_text += ")"
                um_chip = PhosphorChip(
                    um_text, active=True, accent="rose",
                )
                if um_details:
                    um_chip.setToolTip(
                        "Observed:\n" + "\n".join(
                            f"  \u2022 {d}" for d in um_details[:5]
                        )
                    )
                integrity_row.addWidget(um_chip)

            if integrity_flags.get("gibberish"):
                gib_reason = integrity_flags.get("gibberish_reason", "")
                gib_text = "Submission flagged"
                if gib_reason:
                    gib_text += f": {gib_reason}"
                gib_chip = PhosphorChip(
                    gib_text, active=True, accent="rose",
                )
                gib_detail = integrity_flags.get("gibberish_detail", "")
                if gib_detail:
                    gib_chip.setToolTip(gib_detail)
                integrity_row.addWidget(gib_chip)

            integrity_row.addStretch()
            pane_lo.addLayout(integrity_row)

        # Line 2: chip row — register + engagement depth + truncation
        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)

        if register:
            reg_chip = PhosphorChip(register, active=True, accent="amber")
            chip_row.addWidget(reg_chip)

        # Linguistic asset chips (green/teal — community cultural wealth framing)
        _ling_assets = (
            record.get("linguistic_assets", [])
            if isinstance(record, dict)
            else getattr(record, "linguistic_assets", [])
        )
        for _la in (_ling_assets or [])[:2]:  # max 2 chips per card
            _la_text = _la if isinstance(_la, str) else str(_la)
            _la_chip = QLabel(f" {_la_text} ")
            _la_chip.setStyleSheet(
                f"color: {ASSET_CHIP_TEXT}; background: {ASSET_CHIP_BG};"
                f" border: 1px solid {ASSET_CHIP_BORDER}; border-radius: 8px;"
                f" font-size: {px(10)}px; padding: 2px 8px;"
            )
            _la_chip.setToolTip("Linguistic asset (community cultural wealth)")
            chip_row.addWidget(_la_chip)

        engagement_signals = record.get("engagement_signals") or {}
        engagement_depth = engagement_signals.get("engagement_depth", "")
        if engagement_depth and engagement_depth != "unavailable":
            if engagement_depth == "strong":
                # PhosphorChip only supports "amber" and "rose"; use QLabel fallback for green
                eng_chip = QLabel(" strong \u2191 ")
                eng_chip.setStyleSheet(
                    f"color: {TERM_GREEN}; background: rgba(114,184,90,0.12);"
                    f" border: 1px solid rgba(114,184,90,0.3); border-radius: 8px;"
                    f" font-size: {px(10)}px; padding: 2px 8px;"
                )
            elif engagement_depth == "moderate":
                eng_chip = PhosphorChip("moderate", active=False, accent="amber")
            else:
                eng_chip = PhosphorChip(engagement_depth, active=False, accent="rose")
            chip_row.addWidget(eng_chip)

        # Cohort deviation chip — class-relative writing pattern context
        # Uses z-score (standard deviations from class mean) rather than
        # percentile buckets, so the teacher sees HOW FAR a student deviates.
        # Only shown when deviation is notable (|z| >= 1.0).
        # Signals measured: sentence variety, vocabulary complexity,
        # punctuation density, voice authenticity — structural patterns only.
        _cohort_z = record.get("cohort_z_score")
        if _cohort_z is not None and abs(_cohort_z) >= 1.0:
            _z_abs = abs(_cohort_z)
            _z_label = f"{_z_abs:.1f}SD"
            _tip_base = (
                "Writing patterns (sentence variety, word complexity, "
                "punctuation density, voice authenticity) compared to "
                "this class.\n\nThese are structural signals — they "
                "describe HOW the student writes, not what."
            )
            if _cohort_z > 0:
                _coh_chip = QLabel(f" \u2191 {_z_label} above class ")
                _coh_chip.setStyleSheet(
                    f"color: {TERM_GREEN}; background: rgba(114,184,90,0.10);"
                    f" border: 1px solid rgba(114,184,90,0.25); border-radius: 8px;"
                    f" font-size: {px(10)}px; padding: 2px 8px;"
                )
                _coh_chip.setToolTip(
                    f"Writing patterns are {_z_abs:.1f} standard deviations "
                    f"above the class average.\n\n{_tip_base}"
                )
            else:
                _coh_chip = PhosphorChip(
                    f"\u2193 {_z_label} below class", active=False, accent="rose"
                )
                _coh_chip.setToolTip(
                    f"Writing patterns are {_z_abs:.1f} standard deviations "
                    f"below the class average.\n\n{_tip_base}"
                )
            chip_row.addWidget(_coh_chip)

        if engagement_signals.get("conversation_opportunity"):
            checkin_chip = PhosphorChip("\U0001f4ac check in", active=False, accent="rose")
            chip_row.addWidget(checkin_chip)

        if record.get("is_possibly_truncated"):
            trunc_chip = PhosphorChip("possibly incomplete", active=False, accent="rose")
            chip_row.addWidget(trunc_chip)

        chip_row.addStretch()
        pane_lo.addLayout(chip_row)
        pane_lo.addWidget(make_h_rule())

        # ── Handwriting verification banner ──
        if is_image_transcribed:
            verify_frame = QFrame()
            verify_frame.setStyleSheet(
                f"QFrame {{ background: rgba(200,124,16,0.1);"
                f" border: 1px solid {STATUS_WARN}; border-radius: 4px; }}"
            )
            vf_lo = QVBoxLayout(verify_frame)
            vf_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            vf_lo.setSpacing(4)

            warn_lbl = QLabel(
                "\u270d  Transcribed from handwritten image — please verify"
            )
            warn_lbl.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            vf_lo.addWidget(warn_lbl)

            warn_detail = QLabel(
                "This text was read from a photo of handwritten notes "
                "using AI vision. The transcription may contain errors. "
                "Edit below to correct, then click Approve."
            )
            warn_detail.setWordWrap(True)
            warn_detail.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            vf_lo.addWidget(warn_detail)

            # Editable transcription text
            verify_te = QTextEdit()
            original_text = preprocessing.get("original_text", "")
            verify_te.setPlainText(original_text or "(original transcription not stored)")
            verify_te.setMaximumHeight(80)
            verify_te.setStyleSheet(
                f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
                f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
                f" font-family: 'Menlo', 'Consolas', monospace; padding: 4px; }}"
                f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
            )
            vf_lo.addWidget(verify_te)

            approve_btn = QPushButton("\u2713  Approve Transcription")
            approve_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {TERM_GREEN};"
                f" border: 1px solid {TERM_GREEN}; border-radius: 3px;"
                f" font-size: {px(10)}px; padding: 3px 10px; }}"
                f"QPushButton:hover {{ background: rgba(114,184,90,0.15); }}"
            )
            approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def _on_approve(btn=approve_btn, te=verify_te, frame=verify_frame):
                btn.setText("\u2713  Approved")
                btn.setEnabled(False)
                # Collapse the edit area
                te.setVisible(False)
                warn_detail.setVisible(False)
                warn_lbl.setText("\u2713  Handwritten transcription verified by teacher")
                warn_lbl.setStyleSheet(
                    f"color: {TERM_GREEN}; font-size: {px(11)}px; font-weight: bold;"
                    f" background: transparent; border: none;"
                )
                frame.setStyleSheet(
                    f"QFrame {{ background: rgba(114,184,90,0.05);"
                    f" border: 1px solid {TERM_GREEN}; border-radius: 4px; }}"
                )

            approve_btn.clicked.connect(_on_approve)
            vf_lo.addWidget(approve_btn)

            pane_lo.addWidget(verify_frame)

        # ── A2: Truncation banner ────────────────────────────────────────────
        if record.get("is_possibly_truncated"):
            trunc_frame = QFrame()
            trunc_frame.setStyleSheet(
                f"QFrame {{ background: rgba(200,124,16,0.08);"
                f" border: 1px solid {STATUS_WARN}; border-radius: 4px; }}"
            )
            trunc_lo = QVBoxLayout(trunc_frame)
            trunc_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            note = record.get("truncation_note", "This submission may be incomplete.")
            trunc_lbl = QLabel(f"  \u270e  {note}")
            trunc_lbl.setWordWrap(True)
            trunc_lbl.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            trunc_lo.addWidget(trunc_lbl)
            pane_lo.addWidget(trunc_frame)

        # ── Theme tags: chips with x-remove + add combo ──
        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        for tag in tags[:5]:
            chip = PhosphorChip(tag, active=True, accent="amber")
            x_btn = QPushButton("\u00d7")
            x_btn.setFixedSize(18, 18)
            x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            x_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {ROSE_ACCENT};"
                f" border: none; font-size: {px(13)}px; font-weight: bold; }}"
                f"QPushButton:hover {{ color: {BURN_RED}; }}"
            )
            x_btn.clicked.connect(
                lambda _=False, r=run_id, s=sid, t=tag:
                self._on_remove_tag(r, s, t)
            )
            tag_row.addWidget(chip)
            tag_row.addWidget(x_btn)

        add_combo = CRTComboBox()
        add_combo.addItem("+ tag")
        for t in sorted(all_tags):
            if t not in tags:
                add_combo.addItem(t)
        add_combo.setFixedWidth(100)
        add_combo.activated.connect(
            lambda idx, cb=add_combo, r=run_id, s=sid:
            self._on_add_tag(r, s, cb.currentText()) if idx > 0 else None
        )
        tag_row.addWidget(add_combo)
        tag_row.addStretch()
        pane_lo.addLayout(tag_row)
        pane_lo.addWidget(make_h_rule())

        # ── Concern flags (banner pattern) ──────────────────────────────────
        for ci, c in enumerate(concerns):
            passage = c.get("flagged_passage", "")[:100]
            why = c.get("why_flagged", "")[:80]

            concern_frame = QFrame()
            concern_frame.setStyleSheet(
                f"QFrame {{ background: rgba(204,82,130,0.08);"
                f" border: 1px solid {ROSE_DIM}; border-radius: 4px; }}"
            )
            cf_lo = QVBoxLayout(concern_frame)
            cf_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            cf_lo.setSpacing(4)

            concern_lbl = QLabel(f"  \u26a0 {why}: \"{passage}...\"")
            concern_lbl.setWordWrap(True)
            concern_lbl.setStyleSheet(
                f"color: {ROSE_ACCENT}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            cf_lo.addWidget(concern_lbl)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(4)
            btn_row.addStretch()

            ack_btn = QPushButton("Acknowledge")
            ack_btn.setFixedHeight(20)
            ack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ack_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {TERM_GREEN};"
                f" border: 1px solid {TERM_GREEN}; border-radius: 3px;"
                f" font-size: {px(10)}px; padding: 1px 6px; }}"
                f"QPushButton:hover {{ background: rgba(114,184,90,0.15); }}"
            )
            ack_btn.clicked.connect(
                lambda _=False, r=run_id, s=sid, idx=ci:
                self._on_concern_action(r, s, idx, "acknowledge")
            )
            btn_row.addWidget(ack_btn)

            dis_btn = QPushButton("Dismiss")
            dis_btn.setFixedHeight(20)
            dis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dis_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
                f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
                f" font-size: {px(10)}px; padding: 1px 6px; }}"
                f"QPushButton:hover {{ background: rgba(90,60,8,0.15); }}"
            )
            dis_btn.clicked.connect(
                lambda _=False, r=run_id, s=sid, idx=ci:
                self._on_concern_action(r, s, idx, "dismiss")
            )
            btn_row.addWidget(dis_btn)
            cf_lo.addLayout(btn_row)
            pane_lo.addWidget(concern_frame)

        # ── A3: Theme/concern contradiction notes ────────────────────────────
        theme_concern_notes = record.get("theme_concern_notes") or []
        for note in theme_concern_notes:
            tension_lbl = QLabel(f"  \u2194  {note}")
            tension_lbl.setWordWrap(True)
            tension_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; font-style: italic;"
                f" background: transparent; border: none;"
            )
            pane_lo.addWidget(tension_lbl)

        if concerns or theme_concern_notes:
            pane_lo.addWidget(make_h_rule())

        # Notable quotes
        for q in quotes[:2]:
            text = q.get("text", "") if isinstance(q, dict) else ""
            sig = q.get("significance", "") if isinstance(q, dict) else ""
            if text:
                q_lbl = QLabel(f'  \u201c{text[:120]}...\u201d')
                q_lbl.setWordWrap(True)
                q_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; font-style: italic;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(q_lbl)
                if sig:
                    s_lbl = QLabel(f"    {sig}")
                    s_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                        f" background: transparent; border: none;"
                    )
                    pane_lo.addWidget(s_lbl)

        if quotes:
            pane_lo.addWidget(make_h_rule())

        # ── Teacher note: collapsible text area ──
        note_btn = QPushButton(
            f"{'▾' if existing_note else '▸'} Teacher Note"
        )
        note_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: none; text-align: left; font-size: {px(10)}px;"
            f" padding: 2px 0; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
        )
        note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        note_te = QTextEdit()
        note_te.setPlaceholderText("Add a note about this student's work...")
        note_te.setMaximumHeight(50)
        note_te.setVisible(bool(existing_note))
        note_te.setPlainText(existing_note)
        note_te.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
            f" font-family: 'Menlo', 'Consolas', monospace; padding: 4px; }}"
            f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
        )

        def _toggle_note(te=note_te, btn=note_btn):
            v = not te.isVisible()
            te.setVisible(v)
            btn.setText(f"{'▾' if v else '▸'} Teacher Note")

        note_btn.clicked.connect(_toggle_note)

        class _NoteSaver(QObject):
            def __init__(self, store, rid, stid, te_widget):
                super().__init__(te_widget)
                self.store = store
                self.rid = rid
                self.stid = stid
                self.te = te_widget
                self.te.installEventFilter(self)

            def eventFilter(self, obj, event):
                from PySide6.QtCore import QEvent
                if obj is self.te and event.type() == QEvent.Type.FocusOut:
                    text = self.te.toPlainText().strip()
                    if self.store:
                        self.store.update_coding_note(
                            self.rid, self.stid, text
                        )
                return False

        saver = _NoteSaver(self._store, run_id, sid, note_te)
        note_te._saver = saver

        pane_lo.addWidget(note_btn)
        pane_lo.addWidget(note_te)

        return pane

    # ------------------------------------------------------------------
    # Themes layer
    # ------------------------------------------------------------------

    def _display_themes(self, run_id: str) -> None:
        """Populate the Themes layer with interactive editing."""
        lo = self._clear_scroll_layout(self._themes_scroll)
        self._ensure_profile_mgr()

        if not self._store:
            lo.addWidget(_muted_label("No store available."))
            lo.addStretch()
            return

        row = self._store.get_themes(run_id)

        if not row or not row.get("theme_set"):
            lo.addWidget(_muted_label("No themes generated. Run LLM analysis to populate."))
            lo.addStretch()
            return

        try:
            data = json.loads(row["theme_set"])
        except Exception:
            lo.addWidget(_muted_label("Error loading theme data."))
            lo.addStretch()
            return

        themes = data.get("themes", [])
        contradictions = data.get("contradictions", [])

        # Header + merge button
        header_row = QHBoxLayout()
        header_row.addWidget(make_section_label(f"Themes  ({len(themes)} identified)"))
        header_row.addStretch()

        merge_btn = QPushButton("Merge Selected")
        make_secondary_button(merge_btn)
        merge_btn.setVisible(False)
        header_row.addWidget(merge_btn)
        lo.addLayout(header_row)
        lo.addWidget(make_h_rule())

        # Track merge checkboxes
        merge_checks: List[tuple] = []  # (QCheckBox, theme_index)

        for ti, t in enumerate(themes):
            pane = make_content_pane(f"theme_{t.get('name', '')[:20].replace(' ', '_')}")
            pane_lo = QVBoxLayout(pane)
            pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            pane_lo.setSpacing(4)

            freq = t.get("frequency", 0)
            conf = t.get("confidence", 0)
            conf_color = TERM_GREEN if conf >= 0.7 else (PHOSPHOR_MID if conf >= 0.4 else STATUS_WARN)

            # ── Inline-editable name ──
            name_row = QHBoxLayout()
            name_row.setSpacing(4)

            # Merge checkbox
            cb = QCheckBox()
            cb.setStyleSheet(f"QCheckBox {{ background: transparent; }}")
            name_row.addWidget(cb)
            merge_checks.append((cb, ti))

            name_edit = QLineEdit(t.get("name", "Unnamed"))
            name_edit.setStyleSheet(
                f"QLineEdit {{ background: transparent; color: {PHOSPHOR_HOT};"
                f" font-size: {px(13)}px; font-weight: bold; border: none;"
                f" border-bottom: 1px solid transparent; }}"
                f"QLineEdit:focus {{ background: {BG_INSET};"
                f" border-bottom: 1px solid {BORDER_AMBER}; }}"
            )
            original_name = t.get("name", "")
            name_edit.editingFinished.connect(
                lambda ne=name_edit, orig=original_name, r=run_id:
                self._on_theme_rename(r, orig, ne.text())
            )
            name_row.addWidget(name_edit, 1)

            freq_lbl = QLabel(f"({freq} students)")
            freq_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            name_row.addWidget(freq_lbl)
            pane_lo.addLayout(name_row)

            conf_lbl = QLabel(f"Confidence: {conf:.0%}")
            conf_lbl.setStyleSheet(
                f"color: {conf_color}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            pane_lo.addWidget(conf_lbl)

            desc = t.get("description", "")
            if desc:
                d_lbl = QLabel(desc)
                d_lbl.setWordWrap(True)
                d_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(d_lbl)

            for q in t.get("supporting_quotes", [])[:3]:
                text = q.get("text", "")
                if text:
                    q_lbl = QLabel(f'  \u201c{text[:150]}...\u201d')
                    q_lbl.setWordWrap(True)
                    q_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; font-style: italic;"
                        f" background: transparent; border: none;"
                    )
                    pane_lo.addWidget(q_lbl)

            # ── Action buttons: Split, Delete ──
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            split_btn = QPushButton("Split")
            make_secondary_button(split_btn)
            split_btn.clicked.connect(
                lambda _=False, r=run_id, tname=original_name:
                self._on_theme_split(r, tname)
            )
            btn_row.addWidget(split_btn)

            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
                f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
                f" font-size: {px(10)}px; padding: 2px 8px; }}"
                f"QPushButton:hover {{ color: {BURN_RED}; border-color: {BURN_RED}; }}"
            )
            del_btn.clicked.connect(
                lambda _=False, r=run_id, tname=original_name:
                self._on_theme_delete(r, tname)
            )
            btn_row.addWidget(del_btn)
            pane_lo.addLayout(btn_row)

            lo.addWidget(pane)

        # Wire merge button visibility
        def _update_merge_vis():
            checked = sum(1 for cb, _ in merge_checks if cb.isChecked())
            merge_btn.setVisible(checked >= 2)

        for cb, _ in merge_checks:
            cb.stateChanged.connect(lambda _: _update_merge_vis())

        merge_btn.clicked.connect(
            lambda: self._on_theme_merge(
                run_id,
                [themes[ti].get("name", "") for cb, ti in merge_checks if cb.isChecked()],
            )
        )

        # Contradictions
        if contradictions:
            lo.addWidget(make_section_label("Contradictions & Tensions"))
            lo.addWidget(make_h_rule())
            lo.addWidget(_muted_label(
                "Opposing views \u2014 pedagogically productive tensions."
            ))

            for c in contradictions:
                pane = make_content_pane("contradiction")
                pane_lo = QVBoxLayout(pane)
                pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
                pane_lo.setSpacing(4)

                desc_lbl = QLabel(c.get("description", ""))
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet(
                    f"color: {AMBER_BTN}; font-size: {px(12)}px; font-weight: bold;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(desc_lbl)

                a_lbl = QLabel(f"  Side A: {c.get('side_a', '')} ({len(c.get('side_a_students', []))} students)")
                a_lbl.setWordWrap(True)
                a_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(a_lbl)

                b_lbl = QLabel(f"  Side B: {c.get('side_b', '')} ({len(c.get('side_b_students', []))} students)")
                b_lbl.setWordWrap(True)
                b_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(b_lbl)

                sig = c.get("pedagogical_significance", "")
                if sig:
                    s_lbl = QLabel(f"  Significance: {sig}")
                    s_lbl.setWordWrap(True)
                    s_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                        f" background: transparent; border: none;"
                    )
                    pane_lo.addWidget(s_lbl)

                lo.addWidget(pane)

        lo.addStretch()

    # ------------------------------------------------------------------
    # Outliers layer
    # ------------------------------------------------------------------

    def _display_outliers(self, run_id: str) -> None:
        """Populate the Outliers layer with Add to Theme / Create Theme actions."""
        lo = self._clear_scroll_layout(self._outliers_scroll)

        if not self._store:
            lo.addWidget(_muted_label("No store available."))
            lo.addStretch()
            return

        row = self._store.get_themes(run_id)

        if not row or not row.get("outlier_report"):
            lo.addWidget(_muted_label("No outliers identified. Run LLM analysis to populate."))
            lo.addStretch()
            return

        try:
            outlier_data = json.loads(row["outlier_report"])
        except Exception:
            lo.addWidget(_muted_label("Error loading outlier data."))
            lo.addStretch()
            return

        outliers = outlier_data.get("outliers", [])
        if not outliers:
            lo.addWidget(_muted_label("No outliers identified \u2014 all submissions matched themes."))
            lo.addStretch()
            return

        # Get theme names for the combo
        theme_names = []
        if row.get("theme_set"):
            try:
                ts = json.loads(row["theme_set"])
                theme_names = [t.get("name", "") for t in ts.get("themes", [])]
            except Exception:
                pass

        lo.addWidget(make_section_label(f"Outliers  ({len(outliers)} submissions)"))
        lo.addWidget(make_h_rule())
        lo.addWidget(_muted_label(
            "Submissions that don't fit the identified themes. "
            "Often the most pedagogically important findings."
        ))

        for o in outliers:
            sid = o.get("student_id", "")
            pane = make_content_pane(f"outlier_{sid}")
            pane_lo = QVBoxLayout(pane)
            pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            pane_lo.setSpacing(4)

            name_lbl = QLabel(o.get("student_name", "Unknown"))
            name_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            pane_lo.addWidget(name_lbl)

            why = o.get("why_notable", "")
            if why:
                w_lbl = QLabel(why)
                w_lbl.setWordWrap(True)
                w_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(w_lbl)

            rel = o.get("relationship_to_themes", "")
            if rel:
                r_lbl = QLabel(f"Relationship to themes: {rel}")
                r_lbl.setWordWrap(True)
                r_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(r_lbl)

            quote = o.get("notable_quote")
            if isinstance(quote, dict) and quote.get("text"):
                q_lbl = QLabel(f'  \u201c{quote["text"][:150]}...\u201d')
                q_lbl.setWordWrap(True)
                q_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; font-style: italic;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(q_lbl)

            rec = o.get("teacher_recommendation", "")
            if rec:
                rec_lbl = QLabel(f"Recommendation: {rec}")
                rec_lbl.setStyleSheet(
                    f"color: {AMBER_BTN}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                pane_lo.addWidget(rec_lbl)

            # ── Action row: Add to Theme / Create Theme ──
            action_row = QHBoxLayout()
            action_row.addStretch()

            add_combo = CRTComboBox()
            add_combo.addItem("Add to Theme...")
            for tn in theme_names:
                add_combo.addItem(tn)
            add_combo.setFixedWidth(150)
            add_combo.activated.connect(
                lambda idx, cb=add_combo, r=run_id, s=sid:
                self._on_outlier_add_to_theme(r, s, cb.currentText())
                if idx > 0 else None
            )
            action_row.addWidget(add_combo)

            create_btn = QPushButton("Create Theme")
            make_secondary_button(create_btn)
            create_btn.clicked.connect(
                lambda _=False, r=run_id, s=sid, sname=o.get("student_name", ""):
                self._on_outlier_create_theme(r, s, sname)
            )
            action_row.addWidget(create_btn)
            pane_lo.addLayout(action_row)

            lo.addWidget(pane)

        lo.addStretch()

    # ------------------------------------------------------------------
    # Report layer
    # ------------------------------------------------------------------

    def _display_report(self, run_id: str) -> None:
        """Populate the Report layer with editable sections."""
        lo = self._clear_scroll_layout(self._report_scroll)

        if not self._store:
            lo.addWidget(_muted_label("No store available."))
            lo.addStretch()
            return

        row = self._store.get_themes(run_id)

        if not row or not row.get("synthesis_report"):
            lo.addWidget(_muted_label("No synthesis report. Run LLM analysis to populate."))
            lo.addStretch()
            return

        try:
            data = json.loads(row["synthesis_report"])
        except Exception:
            lo.addWidget(_muted_label("Error loading report data."))
            lo.addStretch()
            return

        # Detect GuidedSynthesisResult (new) vs SynthesisReport (legacy)
        if "class_temperature" in data:
            obs_text = (row.get("observation_synthesis") or "").strip()
            if obs_text:
                # New architecture: observation synthesis with master-detail
                codings = self._store.get_codings(run_id) if self._store else []
                self._display_obs_report(lo, data, obs_text, codings, run_id)
            else:
                # Guided synthesis without observation narrative
                self._display_guided_synthesis(lo, data, run_id)
            return

        sections = data.get("sections", {})
        confidence = data.get("confidence", 0)

        # Store original for reset
        self._report_original_sections = dict(sections)

        # Confidence header
        if confidence >= 0.7:
            conf_text, conf_color = "HIGH", TERM_GREEN
        elif confidence >= 0.4:
            conf_text, conf_color = "MEDIUM", PHOSPHOR_MID
        else:
            conf_text, conf_color = "LOW", STATUS_WARN

        header = QLabel(f"SYNTHESIS REPORT  \u00b7  Confidence: {conf_text}")
        header.setStyleSheet(
            f"color: {conf_color}; font-size: {px(14)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(header)
        lo.addWidget(make_h_rule())

        section_titles = {
            "what_students_said": "What Your Students Said",
            "emergent_themes": "Emergent Themes",
            "tensions_and_contradictions": "Tensions & Contradictions",
            "surprises": "What Surprised the Analysis",
            "focus_areas": "Your Focus Areas",
            "concerns": "What Your Students Need You to See",
            "divergent_approaches": "Divergent Approaches",
            "linguistic_diversity": "Linguistic Diversity",
            "looking_ahead": "Looking Ahead",
            "students_to_check_in_with": "Students Carrying More Than Their Share",
        }

        self._report_editors: Dict[str, QTextEdit] = {}

        for key, title in section_titles.items():
            content = sections.get(key, "")
            if not content:
                continue

            # Section header + edit/reset buttons
            sec_row = QHBoxLayout()
            sec_row.addWidget(make_section_label(title))
            sec_row.addStretch()

            edit_btn = QPushButton("Edit")
            make_secondary_button(edit_btn)
            sec_row.addWidget(edit_btn)

            reset_btn = QPushButton("Reset")
            reset_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
                f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
                f" font-size: {px(10)}px; padding: 2px 6px; }}"
                f"QPushButton:hover {{ color: {STATUS_WARN}; border-color: {STATUS_WARN}; }}"
            )
            reset_btn.setVisible(False)
            sec_row.addWidget(reset_btn)
            lo.addLayout(sec_row)

            # Editable text area (starts read-only)
            te = QTextEdit()
            te.setPlainText(content)
            te.setReadOnly(True)
            te.setStyleSheet(
                f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
                f" border-radius: 4px; color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" font-family: 'Menlo', 'Consolas', monospace; padding: 8px; }}"
                f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
            )
            te.setMinimumHeight(60)
            te.setMaximumHeight(300)
            lo.addWidget(te)
            self._report_editors[key] = te

            def _toggle_edit(
                te_w=te, edit_b=edit_btn, reset_b=reset_btn,
                sec_key=key, rid=run_id,
            ):
                is_ro = te_w.isReadOnly()
                te_w.setReadOnly(not is_ro)
                if is_ro:
                    edit_b.setText("Save")
                    reset_b.setVisible(True)
                    te_w.setFocus()
                else:
                    edit_b.setText("Edit")
                    reset_b.setVisible(False)
                    self._on_report_section_save(rid, sec_key, te_w.toPlainText())

            edit_btn.clicked.connect(_toggle_edit)

            def _reset(
                te_w=te, sec_key=key, edit_b=edit_btn, reset_b=reset_btn,
            ):
                original = self._report_original_sections.get(sec_key, "")
                te_w.setPlainText(original)
                te_w.setReadOnly(True)
                edit_b.setText("Edit")
                reset_b.setVisible(False)

            reset_btn.clicked.connect(_reset)

        # Export buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        export_md = QPushButton("Export Markdown")
        make_secondary_button(export_md)
        export_md.clicked.connect(lambda: self._export_report(run_id, "markdown"))
        btn_row.addWidget(export_md)

        export_anon = QPushButton("Export Anonymous")
        make_secondary_button(export_anon)
        export_anon.clicked.connect(lambda: self._export_report(run_id, "anonymous"))
        btn_row.addWidget(export_anon)

        lo.addLayout(btn_row)
        lo.addStretch()

    # ------------------------------------------------------------------
    # Guided Synthesis view (GuidedSynthesisResult — new pipeline)
    # ------------------------------------------------------------------

    def _display_guided_synthesis(
        self, lo: QVBoxLayout, data: dict, run_id: str
    ) -> None:
        """Render a GuidedSynthesisResult in the Report layer.

        Four cards in priority order:
          1. Class Temperature (always)
          2. Engagement Highlights (if present)
          3. Concern Patterns (if present)
          4. Tensions (if present)
        Followed by optional cloud narrative and export buttons.
        """
        from gui.widgets.phosphor_chip import PhosphorChip

        # ── Card 1: Class Temperature ────────────────────────────────────
        temp_pane = make_content_pane("synthTemperature")
        temp_lo = QVBoxLayout(temp_pane)
        temp_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        temp_lo.setSpacing(SPACING_XS)
        temp_lo.addWidget(make_section_label("CLASS TEMPERATURE"))

        temp_text = data.get("class_temperature", "")
        if temp_text:
            temp_lbl = QLabel(temp_text)
            temp_lbl.setWordWrap(True)
            temp_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px;"
                f" background: transparent; border: none;"
            )
            temp_lo.addWidget(temp_lbl)

        attention_areas = data.get("attention_areas") or []
        if attention_areas:
            area_row = QHBoxLayout()
            area_row.setSpacing(4)
            for area in attention_areas:
                area_chip = PhosphorChip(area, active=False, accent="amber")
                area_row.addWidget(area_chip)
            area_row.addStretch()
            temp_lo.addLayout(area_row)

        calls_completed = data.get("calls_completed", 0)
        calls_attempted = data.get("calls_attempted", 0)
        if calls_attempted:
            reliability_lbl = QLabel(
                f"Based on {calls_completed} of {calls_attempted} analyses"
            )
            reliability_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            temp_lo.addWidget(reliability_lbl)

        lo.addWidget(temp_pane)

        # ── Card 2: Engagement Highlights ────────────────────────────────
        highlights = data.get("engagement_highlights") or []
        if highlights:
            hi_pane = make_content_pane("synthHighlights")
            # Override top border to green
            current_qss = hi_pane.styleSheet()
            hi_pane.setStyleSheet(current_qss.replace(
                f"border-top-color: {BORDER_AMBER}",
                f"border-top-color: {TERM_GREEN}"
            ))
            hi_lo = QVBoxLayout(hi_pane)
            hi_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            hi_lo.setSpacing(SPACING_XS)
            hi_lo.addWidget(make_section_label("WHAT YOUR STUDENTS ARE DOING WELL"))

            for item in highlights:
                desc = item.get("description", "")
                names = item.get("student_names") or []
                if desc:
                    desc_lbl = QLabel(desc)
                    desc_lbl.setWordWrap(True)
                    desc_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                        f" background: transparent; border: none;"
                    )
                    hi_lo.addWidget(desc_lbl)
                if names:
                    names_lbl = QLabel(", ".join(names))
                    names_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
                        f" font-weight: bold;"
                        f" background: transparent; border: none;"
                    )
                    hi_lo.addWidget(names_lbl)
                if len(highlights) > 1:
                    hi_lo.addWidget(make_h_rule())

            lo.addWidget(hi_pane)

        # ── Card 3: Concern Patterns ──────────────────────────────────────
        concern_patterns = data.get("concern_patterns") or []
        if concern_patterns:
            cp_pane = make_content_pane("synthConcerns")
            # Override top border to rose
            current_qss = cp_pane.styleSheet()
            cp_pane.setStyleSheet(current_qss.replace(
                f"border-top-color: {BORDER_AMBER}",
                f"border-top-color: {ROSE_ACCENT}"
            ))
            cp_lo = QVBoxLayout(cp_pane)
            cp_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            cp_lo.setSpacing(SPACING_XS)
            cp_lo.addWidget(make_section_label("WHAT YOUR STUDENTS NEED YOU TO SEE"))

            for item in concern_patterns:
                desc = item.get("description", "")
                names = item.get("student_names") or []
                if desc:
                    desc_lbl = QLabel(desc)
                    desc_lbl.setWordWrap(True)
                    desc_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                        f" background: transparent; border: none;"
                    )
                    cp_lo.addWidget(desc_lbl)
                if names:
                    names_lbl = QLabel(", ".join(names))
                    names_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
                        f" font-weight: bold;"
                        f" background: transparent; border: none;"
                    )
                    cp_lo.addWidget(names_lbl)

            concern_differences = data.get("concern_differences") or []
            if concern_differences:
                cp_lo.addWidget(make_h_rule())
                cp_lo.addWidget(make_section_label("KEY DIFFERENCES"))
                for diff in concern_differences:
                    diff_lbl = QLabel(f"\u2022  {diff}")
                    diff_lbl.setWordWrap(True)
                    diff_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                        f" background: transparent; border: none;"
                    )
                    cp_lo.addWidget(diff_lbl)

            lo.addWidget(cp_pane)

        # ── Card 4: Tensions ──────────────────────────────────────────────
        tensions = data.get("tensions") or []
        if tensions:
            t_pane = make_content_pane("synthTensions")
            t_lo = QVBoxLayout(t_pane)
            t_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            t_lo.setSpacing(SPACING_XS)
            t_lo.addWidget(make_section_label("WHERE YOUR STUDENTS DIVERGE"))

            for item in tensions:
                desc = item.get("description", "")
                between = item.get("between") or []
                if desc:
                    desc_lbl = QLabel(desc)
                    desc_lbl.setWordWrap(True)
                    desc_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                        f" background: transparent; border: none;"
                    )
                    t_lo.addWidget(desc_lbl)
                if between:
                    grp_row = QHBoxLayout()
                    grp_row.setSpacing(4)
                    for grp in between:
                        grp_chip = PhosphorChip(str(grp), active=False, accent="amber")
                        grp_row.addWidget(grp_chip)
                    grp_row.addStretch()
                    t_lo.addLayout(grp_row)

            framing = QLabel("These tensions are often where learning happens.")
            framing.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-style: italic;"
                f" background: transparent; border: none;"
            )
            t_lo.addWidget(framing)

            lo.addWidget(t_pane)

        # ── Card 5: Linguistic Diversity (if present) ────────────────────
        ling_diversity = data.get("linguistic_diversity") or {}
        ld_summary = ling_diversity.get("summary", "")
        ld_assets = ling_diversity.get("assets") or []
        if ld_summary or ld_assets:
            ld_pane = make_content_pane("synthLingDiversity")
            # Override top border to teal
            current_qss = ld_pane.styleSheet()
            ld_pane.setStyleSheet(current_qss.replace(
                f"border-top-color: {BORDER_AMBER}",
                f"border-top-color: {ASSET_CHIP_TEXT}"
            ))
            ld_lo = QVBoxLayout(ld_pane)
            ld_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            ld_lo.setSpacing(SPACING_XS)
            ld_lo.addWidget(make_section_label("LINGUISTIC DIVERSITY"))

            if ld_summary:
                ld_lbl = QLabel(ld_summary)
                ld_lbl.setWordWrap(True)
                ld_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
                ld_lo.addWidget(ld_lbl)

            if ld_assets:
                asset_row = QHBoxLayout()
                asset_row.setSpacing(4)
                for asset_text in ld_assets[:6]:
                    _a_chip = QLabel(f" {asset_text} ")
                    _a_chip.setStyleSheet(
                        f"color: {ASSET_CHIP_TEXT}; background: {ASSET_CHIP_BG};"
                        f" border: 1px solid {ASSET_CHIP_BORDER};"
                        f" border-radius: 8px;"
                        f" font-size: {px(10)}px; padding: 2px 8px;"
                    )
                    asset_row.addWidget(_a_chip)
                asset_row.addStretch()
                ld_lo.addLayout(asset_row)

            ld_framing = QLabel(
                "Linguistic diversity is a classroom resource, not a deficit."
            )
            ld_framing.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" font-style: italic;"
                f" background: transparent; border: none;"
            )
            ld_lo.addWidget(ld_framing)

            lo.addWidget(ld_pane)

        # ── Cloud narrative (optional) ─────────────────────────────────────
        cloud_narrative = data.get("cloud_narrative", "")
        if cloud_narrative:
            lo.addWidget(make_h_rule())
            lo.addWidget(make_section_label("DEEPER ANALYSIS"))
            cloud_te = QTextEdit()
            cloud_te.setPlainText(cloud_narrative)
            cloud_te.setReadOnly(True)
            cloud_te.setStyleSheet(
                f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
                f" border-radius: 4px; color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" font-family: 'Menlo', 'Consolas', monospace; padding: 8px; }}"
                f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
            )
            cloud_te.setMinimumHeight(80)
            cloud_te.setMaximumHeight(400)
            lo.addWidget(cloud_te)

        # ── Enhancement failure banner (Issue 15d) ──
        from settings import load_settings as _ls
        _cloud_priv = _ls().get("insights_cloud_privacy", "")
        if not cloud_narrative and _cloud_priv in (
            "free_enhancement", "privacy_enhancement"
        ):
            fail_frame = QFrame()
            fail_frame.setStyleSheet(
                f"QFrame {{ background: rgba(216,112,32,0.08);"
                f" border: 1px solid {STATUS_WARN}; border-radius: 4px;"
                f" padding: {SPACING_SM}px; }}"
            )
            fail_lo_inner = QVBoxLayout(fail_frame)
            fail_lo_inner.setContentsMargins(
                SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM
            )
            fail_lo_inner.setSpacing(SPACING_XS)
            fail_lbl = QLabel(
                "Cloud enhancement was attempted but the service was "
                "unavailable. Showing local analysis only."
            )
            fail_lbl.setWordWrap(True)
            fail_lbl.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            fail_lo_inner.addWidget(fail_lbl)

            fail_btn_row = QHBoxLayout()
            retry_btn = QPushButton("Retry Enhancement")
            make_secondary_button(retry_btn)
            retry_btn.clicked.connect(
                lambda: self._on_enhance_clicked(run_id)
            )
            fail_btn_row.addWidget(retry_btn)

            fail_copy = QPushButton("Copy for Chatbot")
            make_secondary_button(fail_copy)
            fail_copy.clicked.connect(lambda d=data: self._copy_for_chatbot_from_data(d))
            fail_btn_row.addWidget(fail_copy)
            fail_btn_row.addStretch()
            fail_lo_inner.addLayout(fail_btn_row)
            lo.addWidget(fail_frame)

        # ── Browser handoff row (always visible — Issue 15e) ──
        lo.addWidget(make_h_rule())
        handoff_row = QHBoxLayout()
        handoff_label = QLabel(
            "Or enhance by pasting into your school\u2019s AI tool \u2192"
        )
        handoff_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none; font-style: italic;"
        )
        handoff_row.addWidget(handoff_label)

        handoff_copy = QPushButton("Copy for Chatbot")
        make_secondary_button(handoff_copy)
        handoff_copy.clicked.connect(lambda d=data: self._copy_for_chatbot_from_data(d))
        handoff_row.addWidget(handoff_copy)
        handoff_row.addStretch()
        lo.addLayout(handoff_row)

        # ── Export buttons ────────────────────────────────────────────────
        lo.addWidget(make_h_rule())
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        export_md = QPushButton("Export Markdown")
        make_secondary_button(export_md)
        export_md.clicked.connect(lambda: self._export_report(run_id, "markdown"))
        btn_row.addWidget(export_md)

        export_anon = QPushButton("Export Anonymous")
        make_secondary_button(export_anon)
        export_anon.clicked.connect(lambda: self._export_report(run_id, "anonymous"))
        btn_row.addWidget(export_anon)

        copy_btn = QPushButton("Copy for Chatbot")
        make_secondary_button(copy_btn)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _copy_for_chatbot(d=data):
            from PySide6.QtWidgets import QApplication
            lines = []
            temp = d.get("class_temperature", "")
            if temp:
                lines.append(f"CLASS TEMPERATURE\n{temp}\n")
            areas = d.get("attention_areas") or []
            if areas:
                lines.append("ATTENTION AREAS\n" + "\n".join(f"- {a}" for a in areas) + "\n")
            patterns = d.get("concern_patterns") or []
            if patterns:
                lines.append("CONCERN PATTERNS")
                for p in patterns:
                    lines.append(f"- {p.get('description', '')}")
                lines.append("")
            hi = d.get("engagement_highlights") or []
            if hi:
                lines.append("ENGAGEMENT HIGHLIGHTS")
                for h in hi:
                    lines.append(f"- {h.get('description', '')}")
                lines.append("")
            QApplication.clipboard().setText("\n".join(lines))

        copy_btn.clicked.connect(_copy_for_chatbot)
        btn_row.addWidget(copy_btn)

        lo.addLayout(btn_row)
        lo.addStretch()

    def _export_report(self, run_id: str, mode: str) -> None:
        """Export the synthesis report as Markdown or anonymous version."""
        if not self._store:
            return
        import json as _json
        from PySide6.QtWidgets import QFileDialog

        row = self._store.get_themes(run_id)
        if not row or not row.get("synthesis_report"):
            return

        data = _json.loads(row["synthesis_report"])
        sections = data.get("sections", {})

        section_titles = {
            "what_students_said": "What Your Students Said",
            "emergent_themes": "Emergent Themes",
            "tensions_and_contradictions": "Tensions & Contradictions",
            "surprises": "What Surprised the Analysis",
            "focus_areas": "Your Focus Areas",
            "concerns": "What Your Students Need You to See",
            "divergent_approaches": "Divergent Approaches",
            "linguistic_diversity": "Linguistic Diversity",
            "looking_ahead": "Looking Ahead",
            "students_to_check_in_with": "Students Carrying More Than Their Share",
        }

        lines = ["# Insights Report\n"]
        for key, title in section_titles.items():
            content = sections.get(key, "")
            if not content:
                continue
            if mode == "anonymous":
                import re
                content = re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '[Student]', content)
            lines.append(f"## {title}\n\n{content}\n")

        text = "\n".join(lines)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "", "Markdown (*.md)"
        )
        if path:
            with open(path, "w") as f:
                f.write(text)

    # ------------------------------------------------------------------
    # Observation helpers (Issues 4 + 5 — shared by cards & detail panel)
    # ------------------------------------------------------------------

    def _build_observation_frame(self, record: dict) -> QFrame:
        """Build the observation inset frame for a student.

        Used in Student Work cards and the Report detail panel.
        """
        obs = record.get("observation", "")
        reaching = record.get("what_student_is_reaching_for", "")

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: qradialgradient("
            f"cx:0.5,cy:0.5,radius:0.9,"
            f"stop:0.00 #141008,stop:0.70 #0E0A02,stop:1.00 #090702);"
            f" border-left: 3px solid {PHOSPHOR_DIM};"
            f" border-radius: 4px; padding: {SPACING_SM}px; }}"
        )
        frame_lo = QVBoxLayout(frame)
        frame_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        frame_lo.setSpacing(SPACING_XS)

        if obs:
            obs_lbl = QLabel(obs)
            obs_lbl.setWordWrap(True)
            obs_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" font-style: italic; font-family: {MONO_FONT};"
                f" background: transparent; border: none;"
                f" line-height: 1.5;"
            )
            frame_lo.addWidget(obs_lbl)

        if reaching:
            reach_lbl = QLabel(f"\u2192 Reaching for: {reaching}")
            reach_lbl.setWordWrap(True)
            reach_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" font-family: {MONO_FONT}; background: transparent;"
                f" border: none;"
            )
            frame_lo.addWidget(reach_lbl)

        return frame

    def _build_student_detail_content(self, record: dict) -> QWidget:
        """Build the student detail view for the Report layer detail panel.

        Shows observation, tags, register, concerns — everything the
        teacher needs to understand this student's work.
        """
        coding = record.get("coding_record", {})
        if isinstance(coding, str):
            try:
                coding = json.loads(coding)
            except Exception:
                coding = {}

        widget = QWidget()
        lo = QVBoxLayout(widget)
        lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        lo.setSpacing(SPACING_SM)

        # Header: name + word count
        name = coding.get("student_name", "Unknown")
        wc = coding.get("word_count", 0)
        header = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        apply_phosphor_glow(name_lbl, PHOSPHOR_HOT, blur=8, strength=0.60)
        header.addWidget(name_lbl)
        header.addStretch()
        if wc:
            wc_lbl = QLabel(f"{wc} words")
            wc_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            header.addWidget(wc_lbl)
        lo.addLayout(header)
        lo.addWidget(make_h_rule())

        # Observation (primary content)
        obs = coding.get("observation", "")
        if obs:
            obs_frame = self._build_observation_frame(coding)
            lo.addWidget(obs_frame)
            lo.addWidget(make_h_rule())

        # Wellbeing classification (Issue 16)
        _wb_axis = coding.get("wellbeing_axis", "")
        _wb_signal = coding.get("wellbeing_signal", "")
        _checkin = coding.get("checkin_flag")
        _checkin_reason = coding.get("checkin_reasoning", "")
        if _wb_axis in ("CRISIS", "BURNOUT") or _checkin:
            wb_chips = QHBoxLayout()
            wb_chips.setSpacing(4)
            if _wb_axis == "CRISIS":
                wb_chips.addWidget(PhosphorChip("\u26a0 CRISIS", active=True, accent="rose"))
            elif _wb_axis == "BURNOUT":
                wb_chips.addWidget(PhosphorChip("\u25cb BURNOUT", active=True, accent="amber"))
            if _checkin:
                wb_chips.addWidget(PhosphorChip("? CHECK-IN", active=False, accent="amber"))
            wb_chips.addStretch()
            lo.addLayout(wb_chips)

            _sig = _wb_signal or _checkin_reason
            if _sig:
                sig_lbl = QLabel(_sig)
                sig_lbl.setWordWrap(True)
                sig_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" font-style: italic; background: transparent; border: none;"
                )
                lo.addWidget(sig_lbl)
            lo.addWidget(make_h_rule())

        # Theme tags
        tags = coding.get("theme_tags", [])
        if tags:
            tag_row = QHBoxLayout()
            tag_row.setSpacing(SPACING_XS)
            for tag in tags[:5]:
                chip = PhosphorChip(tag, active=False, accent="amber")
                tag_row.addWidget(chip)
            tag_row.addStretch()
            lo.addLayout(tag_row)

        # Register + linguistic assets (metadata line)
        reg = coding.get("emotional_register", "")
        assets = coding.get("linguistic_assets", [])
        if reg or assets:
            meta_parts = []
            if reg:
                meta_parts.append(f"Register: {reg}")
            if assets:
                meta_parts.append(f"Linguistic: {', '.join(str(a) for a in assets[:2])}")
            meta_lbl = QLabel(" \u00b7 ".join(meta_parts))
            meta_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(meta_lbl)

        # Concerns (rose frames)
        concerns = coding.get("concerns", [])
        for concern in concerns:
            lo.addWidget(make_h_rule())
            c_frame = QFrame()
            c_frame.setStyleSheet(
                f"QFrame {{ background: rgba(204,82,130,0.08);"
                f" border-left: 3px solid {ROSE_ACCENT};"
                f" border-radius: 4px; padding: {SPACING_SM}px; }}"
            )
            c_lo = QVBoxLayout(c_frame)
            c_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            c_lo.setSpacing(SPACING_XS)
            c_type = concern.get("type", "concern")
            c_text = concern.get("why_flagged", concern.get("description", ""))
            type_lbl = QLabel(c_type.upper())
            type_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
                f" font-weight: bold; background: transparent; border: none;"
            )
            c_lo.addWidget(type_lbl)
            if c_text:
                c_desc = QLabel(c_text)
                c_desc.setWordWrap(True)
                c_desc.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
                c_lo.addWidget(c_desc)
            lo.addWidget(c_frame)

        # "View submission in Canvas" link — always shown when available,
        # critical for skip records where teacher needs to see the raw submission.
        sub_url = coding.get("submission_url")
        if sub_url:
            canvas_link = QLabel(
                f'<a href="{sub_url}" style="color: {PHOSPHOR_DIM}; font-style: italic;">'
                f'View submission in Canvas \u2197</a>'
            )
            canvas_link.setCursor(Qt.CursorShape.PointingHandCursor)
            canvas_link.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none; padding-top: 4px;"
            )
            canvas_link.setOpenExternalLinks(False)
            canvas_link.linkActivated.connect(
                lambda url: QDesktopServices.openUrl(QUrl(url))
            )
            lo.addWidget(canvas_link)

        lo.addStretch()
        return widget

    # ------------------------------------------------------------------
    # Observation synthesis display (Issue 5 — Report layer master-detail)
    # ------------------------------------------------------------------

    def _render_obs_synthesis_with_links(
        self, text: str, codings: list
    ) -> QWidget:
        """Render observation synthesis with student names as clickable links."""
        import re

        # Build name → student_id lookup from coding records
        name_map: Dict[str, str] = {}
        for c in codings:
            rec = c.get("coding_record", {})
            if isinstance(rec, str):
                try:
                    rec = json.loads(rec)
                except Exception:
                    rec = {}
            sname = rec.get("student_name") or c.get("student_name", "")
            sid = str(c.get("student_id", ""))
            if sname and sid:
                name_map[sname] = sid

        container = QWidget()
        lo = QVBoxLayout(container)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(SPACING_XS)

        # Sort names longest-first so "Ingrid Vasquez" matches before "Ingrid"
        sorted_names = sorted(name_map.keys(), key=len, reverse=True)

        for para in text.split("\n\n"):
            if not para.strip():
                continue

            # Section headers (## or **)
            stripped = para.strip()
            if stripped.startswith("##") or (
                stripped.startswith("**") and stripped.endswith("**")
            ):
                header_text = stripped.lstrip("#").strip().strip("*").strip()
                lo.addWidget(make_section_label(header_text))
                lo.addWidget(make_h_rule())
                continue

            # Regular paragraphs: QTextBrowser with HTML links for names
            html = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # Replace student names with clickable links
            for name in sorted_names:
                if name in para:
                    escaped_name = name.replace("&", "&amp;")
                    sid = name_map[name]
                    link = (
                        f'<a href="student://{sid}" style="color: {PHOSPHOR_HOT};'
                        f' text-decoration: underline; font-weight: bold;">'
                        f'{escaped_name}</a>'
                    )
                    html = html.replace(escaped_name, link)

            browser = QTextBrowser()
            browser.setOpenLinks(False)
            browser.setReadOnly(True)
            browser.setTextInteractionFlags(
                Qt.TextInteractionFlag.LinksAccessibleByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
            )
            browser.setHtml(
                f'<div style="color: {PHOSPHOR_MID}; font-family: {MONO_FONT};'
                f' font-size: {px(12)}px; line-height: 1.6;">{html}</div>'
            )
            browser.anchorClicked.connect(self._on_student_link_clicked)
            browser.setStyleSheet(
                f"QTextBrowser {{ background: transparent; border: none;"
                f" color: {PHOSPHOR_MID}; }}"
            )
            browser.setTabChangesFocus(False)  # Tab navigates links, not focus
            # Auto-resize to content height
            browser.document().setTextWidth(500)
            doc_height = int(browser.document().size().height()) + SPACING_SM
            browser.setFixedHeight(max(doc_height, 30))
            browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            lo.addWidget(browser)

        return container

    def _on_student_link_clicked(self, url: QUrl) -> None:
        """Handle click on a student name in the observation synthesis."""
        if url.scheme() == "student":
            sid = url.host() or url.path().lstrip("/")
            if sid:
                self._show_student_detail(sid)

    def _show_student_detail(self, student_id: str) -> None:
        """Populate and reveal the right-side detail panel in Report layer."""
        if not self._current_run_id or not self._store:
            return

        record = self._store.get_coding_record(self._current_run_id, student_id)
        if not record:
            return

        detail_panel = getattr(self, "_report_detail_scroll", None)
        if detail_panel is None:
            return

        # Build detail content
        detail_widget = self._build_student_detail_content(record)

        # Wrap with close button and "View all students" link
        wrapper = QWidget()
        wrapper_lo = QVBoxLayout(wrapper)
        wrapper_lo.setContentsMargins(0, SPACING_SM, 0, 0)
        wrapper_lo.setSpacing(SPACING_SM)

        # Close button row
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: 1px solid {BORDER_DARK}; border-radius: 12px;"
            f" font-size: {px(14)}px; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_HOT};"
            f" border-color: {BORDER_AMBER}; }}"
        )
        close_btn.clicked.connect(self._hide_student_detail)
        close_row.addWidget(close_btn)
        wrapper_lo.addLayout(close_row)

        wrapper_lo.addWidget(detail_widget, 1)

        # "View all students" link at bottom
        all_link = QLabel(
            f'<a style="color: {PHOSPHOR_DIM}; font-style: italic;">'
            f'View all students \u2192</a>'
        )
        all_link.setCursor(Qt.CursorShape.PointingHandCursor)
        all_link.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        all_link.mousePressEvent = lambda _: self._layer_toggle.set_mode("codings")
        wrapper_lo.addWidget(all_link)

        detail_panel.setWidget(wrapper)
        detail_panel.setVisible(True)

    def _hide_student_detail(self) -> None:
        """Hide the student detail panel in the Report layer."""
        detail_panel = getattr(self, "_report_detail_scroll", None)
        if detail_panel:
            detail_panel.setVisible(False)

    def _navigate_to_student(self, student_id: str) -> None:
        """Navigate to a student in the Student Work layer."""
        # Switch to Student Work layer
        if hasattr(self, "_layer_toggle"):
            self._layer_toggle.set_mode("codings")
        # TODO: scroll to the specific student card once layer loads

    def _copy_for_chatbot_from_data(self, data: dict) -> None:
        """Copy GuidedSynthesisResult to clipboard in chatbot-friendly format."""
        from PySide6.QtWidgets import QApplication
        lines = []
        temp = data.get("class_temperature", "")
        if temp:
            lines.append(f"CLASS TEMPERATURE\n{temp}\n")
        areas = data.get("attention_areas") or []
        if areas:
            lines.append("ATTENTION AREAS\n" + "\n".join(f"- {a}" for a in areas) + "\n")
        patterns = data.get("concern_patterns") or []
        if patterns:
            lines.append("CONCERN PATTERNS")
            for p in patterns:
                lines.append(f"- {p.get('description', '')}")
            lines.append("")
        hi = data.get("engagement_highlights") or []
        if hi:
            lines.append("ENGAGEMENT HIGHLIGHTS")
            for h in hi:
                lines.append(f"- {h.get('description', '')}")
            lines.append("")
        QApplication.clipboard().setText("\n".join(lines))
        self._show_toast("Copied to clipboard")

    def _on_enhance_clicked(self, run_id: str) -> None:
        """Show enhancement preview and send if confirmed."""
        if not self._store:
            return
        from gui.dialogs.enhancement_preview_dialog import EnhancementPreviewDialog
        from settings import load_settings as _ls
        from insights.synthesizer import run_cloud_enhancement

        _s = _ls()
        _priv = _s.get("insights_cloud_privacy", "")
        provider_map = {
            "free_enhancement": "Google Gemma 27B (free, via OpenRouter)",
            "privacy_enhancement": "Mistral Small (privacy-first, via Venice)",
        }
        provider = provider_map.get(_priv, "Cloud service")

        # Build anonymized payload
        codings = self._store.get_codings(run_id)
        if not codings:
            self._show_toast("No coding records to enhance.")
            return

        # Build the payload preview text
        records = []
        for c in codings:
            rec = c.get("coding_record", {})
            if isinstance(rec, str):
                try:
                    rec = json.loads(rec)
                except Exception:
                    rec = {}
            records.append(rec)

        row = self._store.get_themes(run_id)
        assignment_name = ""
        if row:
            assignment_name = row.get("assignment_name", "")

        # Simple payload preview (teacher sees what leaves the machine)
        payload_lines = ["[Anonymized class patterns — no student names or text]", ""]
        themes = set()
        registers = {}
        for rec in records:
            for t in rec.get("theme_tags", []):
                themes.add(t)
            r = rec.get("emotional_register", "")
            if r:
                registers[r] = registers.get(r, 0) + 1
        if themes:
            payload_lines.append(f"Themes: {', '.join(sorted(themes))}")
        if registers:
            payload_lines.append(f"Registers: {registers}")
        payload_lines.append(f"Students: {len(records)}")

        dlg = EnhancementPreviewDialog(
            "\n".join(payload_lines), provider, parent=self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Run enhancement
        try:
            narrative = run_cloud_enhancement(records, assignment_name, _s)
            if narrative:
                self._store.save_themes(
                    run_id, synthesis_report_json=narrative
                )
                self._show_toast("Enhancement complete!")
                # Refresh the report layer
                self._invalidate_layers("report")
                self._display_report(run_id)
            else:
                self._show_toast("Enhancement returned no results.")
        except Exception as e:
            self._show_toast(f"Enhancement failed: {e}")

    def _display_obs_report(
        self,
        lo: QVBoxLayout,
        data: dict,
        obs_text: str,
        codings: list,
        run_id: str,
    ) -> None:
        """Render the Report layer with observation synthesis master-detail.

        Left pane: observation synthesis narrative + guided synthesis cards.
        Right pane: student detail panel (hidden until a name is clicked).
        """
        # Create splitter
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)

        # ── Left pane: scrollable narrative ──
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        left_widget = QWidget()
        left_lo = QVBoxLayout(left_widget)
        left_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        left_lo.setSpacing(SPACING_MD)

        # Primary: observation synthesis with clickable student names
        left_lo.addWidget(make_section_label("CLASS OBSERVATIONS"))
        left_lo.addWidget(make_h_rule())
        obs_widget = self._render_obs_synthesis_with_links(obs_text, codings)
        left_lo.addWidget(obs_widget)

        # Silence visibility: how many students are discussed vs total
        n_total = len(codings)
        if n_total > 0:
            # Count students whose names appear in the synthesis
            n_discussed = 0
            for c in codings:
                rec = c.get("coding_record", {})
                if isinstance(rec, str):
                    try:
                        rec = json.loads(rec)
                    except Exception:
                        rec = {}
                sname = rec.get("student_name") or c.get("student_name", "")
                if sname and sname in obs_text:
                    n_discussed += 1
            coverage_row = QHBoxLayout()
            coverage_lbl = QLabel(
                f"This summary discusses {n_discussed} of {n_total} "
                f"students explicitly."
            )
            coverage_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" font-style: italic; background: transparent; border: none;"
            )
            coverage_row.addWidget(coverage_lbl)
            view_all = QPushButton("View all students \u2192")
            view_all.setCursor(Qt.CursorShape.PointingHandCursor)
            view_all.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
                f" border: none; font-size: {px(11)}px; font-style: italic;"
                f" text-decoration: underline; }}"
                f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
            )
            view_all.clicked.connect(
                lambda: self._layer_toggle.set_mode("codings")
            )
            coverage_row.addWidget(view_all)
            coverage_row.addStretch()
            left_lo.addLayout(coverage_row)

        # Supporting: 4-card guided synthesis below
        left_lo.addWidget(make_h_rule())
        left_lo.addWidget(make_section_label("ANALYSIS DETAIL"))
        self._display_guided_synthesis(left_lo, data, run_id)

        left_scroll.setWidget(left_widget)

        # ── Right pane: student detail (hidden until click) ──
        self._report_detail_scroll = QScrollArea()
        self._report_detail_scroll.setWidgetResizable(True)
        self._report_detail_scroll.setVisible(False)
        self._report_detail_scroll.setMinimumWidth(320)
        self._report_detail_scroll.setStyleSheet(
            f"QScrollArea {{ background: {PANEL_GRADIENT};"
            f" border-left: 1px solid {BORDER_DARK}; }}"
        )

        splitter.addWidget(left_scroll)
        splitter.addWidget(self._report_detail_scroll)
        splitter.setStretchFactor(0, 3)  # 60% narrative
        splitter.setStretchFactor(1, 2)  # 40% detail

        lo.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Feedback layer (Phase 4)
    # ------------------------------------------------------------------

    def _display_feedback(self, run_id: str) -> None:
        """Populate the Feedback layer with the review queue."""
        lo = self._clear_scroll_layout(self._feedback_scroll)
        self._ensure_profile_mgr()

        if not self._store:
            lo.addWidget(_muted_label("No store available."))
            lo.addStretch()
            return

        rows = self._store.get_feedback(run_id)
        if not rows:
            lo.addWidget(_muted_label(
                "No feedback drafts. Enable 'Draft feedback' in setup and "
                "run an LLM analysis to generate drafts."
            ))
            lo.addStretch()
            return

        # Count by status
        counts = {"pending": 0, "approved": 0, "posted": 0,
                  "rejected": 0, "manual": 0}
        for r in rows:
            conf = r.get("confidence") or 0.0
            if conf < 0.6 and r.get("status") == "pending":
                counts["manual"] += 1
            else:
                counts[r.get("status", "pending")] += 1

        summary_parts = []
        if counts["pending"]:
            summary_parts.append(f"{counts['pending']} drafts ready")
        if counts["approved"]:
            summary_parts.append(f"{counts['approved']} approved")
        if counts["posted"]:
            summary_parts.append(f"{counts['posted']} posted")
        if counts["rejected"]:
            summary_parts.append(f"{counts['rejected']} rejected")
        if counts["manual"]:
            summary_parts.append(f"{counts['manual']} need manual review")

        header = QLabel("DRAFT FEEDBACK")
        header.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        lo.addWidget(header)
        lo.addWidget(_muted_label(
            "Review before posting \u2014 each draft needs individual approval."
        ))

        summary_lbl = QLabel(" \u00b7 ".join(summary_parts))
        summary_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none; padding: 4px 0;"
        )
        lo.addWidget(summary_lbl)
        lo.addWidget(make_h_rule())

        # Post All Reviewed button (ONLY posts already-approved)
        post_row = QHBoxLayout()
        post_row.addStretch()
        self._post_btn = QPushButton(
            f"Post {counts['approved']} Approved to Canvas"
            if counts["approved"] else "No Approved Drafts to Post"
        )
        self._post_btn.setEnabled(counts["approved"] > 0)
        make_run_button(self._post_btn)
        self._post_btn.clicked.connect(lambda: self._on_post_feedback(run_id))
        post_row.addWidget(self._post_btn)
        lo.addLayout(post_row)
        lo.addWidget(make_h_rule())

        for row in rows:
            self._build_feedback_card(lo, run_id, row)

        lo.addStretch()

    def _build_feedback_card(
        self, lo: QVBoxLayout, run_id: str, row: Dict,
    ) -> None:
        """Build one feedback review card."""
        sid = row.get("student_id", "")
        name = row.get("student_name", f"Student {sid}")
        draft = row.get("draft_text", "")
        status = row.get("status", "pending")
        confidence = row.get("confidence") or 0.0
        is_manual = confidence < 0.6 and status == "pending"

        if status == "approved":
            border_color = TERM_GREEN
        elif status == "posted":
            border_color = PHOSPHOR_DIM
        elif status == "rejected":
            border_color = PHOSPHOR_GLOW
        elif is_manual:
            border_color = ROSE_ACCENT
        else:
            border_color = BORDER_DARK

        if confidence >= 0.7:
            conf_text, conf_color = "HIGH", TERM_GREEN
        elif confidence >= 0.4:
            conf_text, conf_color = "MEDIUM", PHOSPHOR_MID
        elif confidence > 0:
            conf_text, conf_color = "LOW", STATUS_WARN
        else:
            conf_text, conf_color = "MANUAL REVIEW NEEDED", ROSE_ACCENT

        pane = QFrame()
        pn = f"fb_{sid}"
        pane.setObjectName(pn)
        pane.setStyleSheet(
            f"QFrame#{pn} {{"
            f"  background: {PANE_BG_GRADIENT};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: 8px;"
            f"}}"
        )
        pane_lo = QVBoxLayout(pane)
        pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        pane_lo.setSpacing(4)

        # Header: name + confidence
        hdr = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        hdr.addWidget(name_lbl)
        hdr.addStretch()
        conf_lbl = QLabel(
            f"confidence: {conf_text}" if status != "posted" else "POSTED"
        )
        conf_lbl.setStyleSheet(
            f"color: {conf_color if status != 'posted' else PHOSPHOR_DIM};"
            f" font-size: {px(10)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        hdr.addWidget(conf_lbl)
        pane_lo.addLayout(hdr)

        # Posted: read-only, no actions
        if status == "posted":
            lbl = QLabel(row.get("approved_text") or draft)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
                f" background: transparent; border: none; font-style: italic;"
            )
            pane_lo.addWidget(lbl)
            lo.addWidget(pane)
            return

        # Manual review card
        if is_manual:
            self._build_manual_card(pane_lo, lo, pane, pn, run_id, sid, name, draft)
            lo.addWidget(pane)
            return

        # Normal draft card
        self._build_draft_card(
            pane_lo, lo, pane, pn, run_id, sid, name, draft, status
        )
        lo.addWidget(pane)

    def _build_manual_card(
        self, pane_lo, parent_lo, pane, pn, run_id, sid, name, draft,
    ) -> None:
        """Manual review card: rose border, write-your-own."""
        reason_lbl = QLabel(draft)
        reason_lbl.setWordWrap(True)
        reason_lbl.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        pane_lo.addWidget(reason_lbl)

        te = QTextEdit()
        te.setPlaceholderText("Write feedback for this student...")
        te.setMaximumHeight(100)
        te.setVisible(False)
        te.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" padding: 4px; }}"
            f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
        )
        pane_lo.addWidget(te)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        write_btn = QPushButton("Write Feedback")
        make_secondary_button(write_btn)
        btn_row.addWidget(write_btn)

        save_btn = QPushButton("Save & Approve")
        save_btn.setVisible(False)
        make_run_button(save_btn)
        btn_row.addWidget(save_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
            f" font-size: {px(10)}px; padding: 2px 8px; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_MID};"
            f" border-color: {PHOSPHOR_MID}; }}"
        )
        btn_row.addWidget(skip_btn)
        pane_lo.addLayout(btn_row)

        def _show_write(t=te, wb=write_btn, sb=save_btn):
            t.setVisible(True)
            wb.setVisible(False)
            sb.setVisible(True)
            t.setFocus()

        write_btn.clicked.connect(_show_write)

        def _save(t=te, r=run_id, s=sid, n=name, p=pane, pname=pn):
            text = t.toPlainText().strip()
            if not text:
                return
            if len(text) > 10000:
                self._show_toast(
                    f"Feedback for {n} is {len(text):,} characters — "
                    f"Canvas may reject comments over ~10,000. "
                    f"Please shorten before saving."
                )
                return
            if self._store:
                self._store.update_feedback_text(r, s, text)
                self._store.update_feedback_status(r, s, "approved", approved_text=text)
                p.setStyleSheet(
                    f"QFrame#{pname} {{ background: {PANE_BG_GRADIENT};"
                    f" border: 1px solid {TERM_GREEN}; border-radius: 8px; }}"
                )
                self._show_toast(f"Approved: {n}")
                self._invalidate_layers("feedback")

        save_btn.clicked.connect(_save)
        skip_btn.clicked.connect(
            lambda _=False, r=run_id, s=sid: self._on_feedback_reject(r, s)
        )

    def _build_draft_card(
        self, pane_lo, parent_lo, pane, pn, run_id, sid, name, draft, status,
    ) -> None:
        """Normal draft card with Edit / Approve / Reject / Preview."""
        te = QTextEdit()
        te.setPlainText(draft)
        te.setReadOnly(True)
        te.setMaximumHeight(120)
        te.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" padding: 6px; }}"
            f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
        )
        pane_lo.addWidget(te)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        edit_btn = QPushButton("Edit")
        make_secondary_button(edit_btn)
        btn_row.addWidget(edit_btn)

        approve_btn = QPushButton("Approve" if status != "approved" else "Approved")
        approve_btn.setEnabled(status != "approved")
        approve_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TERM_GREEN};"
            f" border: 1px solid {TERM_GREEN}; border-radius: 4px;"
            f" font-size: {px(11)}px; padding: 4px 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: rgba(114,184,90,0.15); }}"
        )
        btn_row.addWidget(approve_btn)

        reject_btn = QPushButton("Reject")
        reject_btn.setEnabled(status != "rejected")
        reject_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
            f" font-size: {px(10)}px; padding: 3px 10px; }}"
            f"QPushButton:hover {{ color: {BURN_RED}; border-color: {BURN_RED}; }}"
        )
        btn_row.addWidget(reject_btn)

        preview_btn = QPushButton("Preview as Student")
        preview_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
            f" border: 1px solid {PHOSPHOR_DIM}; border-radius: 3px;"
            f" font-size: {px(10)}px; padding: 3px 10px; }}"
            f"QPushButton:hover {{ color: {PHOSPHOR_MID};"
            f" border-color: {PHOSPHOR_MID}; }}"
        )
        btn_row.addWidget(preview_btn)
        pane_lo.addLayout(btn_row)

        if status == "rejected":
            te.setStyleSheet(
                f"QTextEdit {{ background: {BG_INSET};"
                f" border: 1px solid {PHOSPHOR_GLOW}; border-radius: 4px;"
                f" color: {PHOSPHOR_DIM}; font-size: {px(12)}px; padding: 6px; }}"
            )

        # Wire edit toggle
        def _toggle_edit(
            t=te, eb=edit_btn, r=run_id, s=sid, n=name,
            p=pane, pname=pn, orig=draft,
        ):
            is_ro = t.isReadOnly()
            t.setReadOnly(not is_ro)
            if is_ro:
                eb.setText("Save")
                t.setFocus()
                t.setStyleSheet(
                    f"QTextEdit {{ background: {BG_INSET};"
                    f" border: 1px solid {BORDER_AMBER}; border-radius: 4px;"
                    f" color: {PHOSPHOR_HOT}; font-size: {px(12)}px; padding: 6px; }}"
                )
            else:
                eb.setText("Edit")
                new_text = t.toPlainText().strip()
                t.setStyleSheet(
                    f"QTextEdit {{ background: {BG_INSET};"
                    f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
                    f" color: {PHOSPHOR_MID}; font-size: {px(12)}px; padding: 6px; }}"
                )
                if new_text != orig and self._store:
                    self._store.update_feedback_text(r, s, new_text)
                    self._store.save_calibration(
                        (self._profile_mgr._profile_id
                         if self._profile_mgr else "default"),
                        "",
                        json.dumps({"feedback": orig}),
                        json.dumps({"feedback": new_text}),
                        "feedback_edit",
                    )
                    self._show_toast(f"Saved edit for {n}")

        edit_btn.clicked.connect(_toggle_edit)

        # Wire approve
        def _approve(
            t=te, r=run_id, s=sid, n=name,
            ab=approve_btn, p=pane, pname=pn,
        ):
            text = t.toPlainText().strip()
            if not text:
                return
            # Canvas comment length guard (~10K chars safe limit)
            if len(text) > 10000:
                self._show_toast(
                    f"Feedback for {n} is {len(text):,} characters — "
                    f"Canvas may reject comments over ~10,000. "
                    f"Please shorten before approving."
                )
                return
            if self._store:
                self._store.update_feedback_status(r, s, "approved", approved_text=text)
                ab.setText("Approved")
                ab.setEnabled(False)
                p.setStyleSheet(
                    f"QFrame#{pname} {{ background: {PANE_BG_GRADIENT};"
                    f" border: 1px solid {TERM_GREEN}; border-radius: 8px; }}"
                )
                self._show_toast(f"Approved: {n}")

        approve_btn.clicked.connect(_approve)

        reject_btn.clicked.connect(
            lambda _=False, r=run_id, s=sid: self._on_feedback_reject(r, s)
        )
        preview_btn.clicked.connect(
            lambda _=False, t=te, n=name: self._preview_as_student(n, t.toPlainText())
        )

    def _on_feedback_reject(self, run_id: str, student_id: str) -> None:
        """Reject a feedback draft."""
        if self._store:
            self._store.update_feedback_status(run_id, student_id, "rejected")
            self._invalidate_layers("feedback")
            self._show_toast("Feedback rejected.")

    def _preview_as_student(self, student_name: str, text: str) -> None:
        """Show ONLY what the student sees. No metadata, no flags."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Student View: {student_name}")
        dlg.setMinimumWidth(500)
        dlg.setStyleSheet("QDialog { background: #ffffff; }")
        dlo = QVBoxLayout(dlg)
        dlo.setContentsMargins(24, 24, 24, 24)
        dlo.setSpacing(12)

        hdr = QLabel("Teacher comment on your submission:")
        hdr.setStyleSheet(
            f"color: #333333; font-size: {px(13)}px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        dlo.addWidget(hdr)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: #2d3b45; font-size: {px(13)}px; line-height: 1.5;"
            " background: #f5f5f5; border: 1px solid #c7cdd1;"
            " border-radius: 4px; padding: 12px;"
            " font-family: 'Lato', 'Helvetica Neue', sans-serif;"
        )
        dlo.addWidget(body)

        note = QLabel(
            "This is what the student will see. No metadata, "
            "no analytical labels, no concern flags."
        )
        note.setStyleSheet(
            f"color: #999999; font-size: {px(10)}px; background: transparent;"
            " border: none;"
        )
        dlo.addWidget(note)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        dlo.addWidget(bb)
        dlg.exec()

    def _on_post_feedback(self, run_id: str) -> None:
        """Post approved feedback to Canvas after confirmation."""
        if not self._store or not self._api:
            self._show_toast("Canvas API not configured.")
            return

        approved = self._store.get_approved_feedback(run_id)
        n = len(approved)
        if n == 0:
            self._show_toast("No approved drafts to post.")
            return

        # Pre-post length check
        too_long = []
        for fb in approved:
            text = fb.get("approved_text") or fb.get("draft_text") or ""
            if len(text) > 10000:
                too_long.append(fb.get("student_name", "Unknown"))
        if too_long:
            names = ", ".join(too_long[:5])
            self._show_toast(
                f"Cannot post — feedback too long for: {names}. "
                f"Edit to under 10,000 characters."
            )
            return

        run = self._store.get_run(run_id)
        if not run:
            return
        course_id = run.get("course_id", "")
        assignment_id = run.get("assignment_id", "")

        # Confirmation — cannot be undone
        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Post")
        dlg.setStyleSheet(
            f"QDialog {{ background: {BG_CARD}; }}"
            f"QLabel {{ color: {PHOSPHOR_MID}; background: transparent;"
            f" border: none; }}"
        )
        dlo = QVBoxLayout(dlg)
        dlo.addWidget(QLabel(
            f"Post feedback for {n} student{'s' if n != 1 else ''} "
            f"to Canvas?\n\nThis cannot be undone."
        ))
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Post")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        dlo.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        from gui.workers import FeedbackPostWorker
        self._post_worker = FeedbackPostWorker(
            self._api,
            store=self._store,
            run_id=run_id,
            course_id=course_id,
            assignment_id=assignment_id,
        )
        self._post_worker.post_progress.connect(
            lambda msg: self._show_toast(msg)
        )
        self._post_worker.post_complete.connect(self._on_post_complete)
        self._post_worker.error.connect(
            lambda msg: self._show_toast(f"Post error: {msg}")
        )
        self._post_worker.start()
        self._show_toast("Posting feedback...")

    def _on_post_complete(self, success: int, fail: int) -> None:
        msg = f"Posted {success} comment{'s' if success != 1 else ''}."
        if fail:
            msg += f" {fail} failed."
        self._show_toast(msg)
        self._invalidate_layers("feedback")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_courses(
        self,
        courses_by_term: list,
        assignments_cache: Optional[dict] = None,
    ) -> None:
        """Populate the course/assignment selection lists.

        courses_by_term: [(term_id, term_name, is_current, [course_dicts])]
        assignments_cache: {course_id: [assignment_group_dicts]}
        """
        self._courses_by_term = courses_by_term
        if assignments_cache:
            self._assignments_cache = assignments_cache

        self._course_rows.clear()

        content = QWidget()
        content.setStyleSheet(f"background: {BG_INSET};")
        content_lo = QVBoxLayout(content)
        content_lo.setContentsMargins(0, 2, 0, 4)
        content_lo.setSpacing(0)

        for term_id, term_name, is_current, courses in courses_by_term:
            section = _TermSection(term_name, is_current)
            for c in courses:
                row = _CourseRow(c)
                row.toggled.connect(self._on_course_row_toggled)
                self._course_rows.append(row)
                section.add_course_row(row)
            content_lo.addWidget(section)

        content_lo.addStretch()
        if self._course_scroll is not None:
            self._course_scroll.setWidget(content)

        # Clear assignments since no courses are checked yet
        self._assign_rows.clear()
        if self._assign_scroll is not None:
            _empty = QWidget()
            _empty.setStyleSheet(f"background: {BG_INSET};")
            self._assign_scroll.setWidget(_empty)
        self._update_summary()

    def show_review(self, run_id: str) -> None:
        """Switch to review state and display the given run."""
        self._switch_view(2)
        self._load_run(run_id)

    def load_assignment(self, course_id: str, assignment_id: str) -> None:
        """Load most recent insights run for an assignment (called by shared ReviewSidebar)."""
        if not self._store:
            return
        # Switch to review view
        self._switch_view(2)
        # Find the most recent run for this assignment
        runs = self._store.get_runs(course_id=course_id)
        for run in runs:
            if str(run.get("assignment_id", "")) == str(assignment_id):
                self._load_run(run.get("run_id", ""))
                return
        # No run found — show placeholder
        self._current_run_id = None
        self._resume_btn.setVisible(False)
        self._export_btn.setVisible(False)
        self._review_content_stack.setCurrentIndex(0)
        self._review_placeholder.setText(
            "No insights run found for this assignment.\n"
            "Use New Analysis to generate one."
        )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_course_row_toggled(self, course_id: int, checked: bool) -> None:
        """When a course row is checked/unchecked, rebuild the assignment list."""
        self._refresh_assignment_list()
        self._update_summary()

    def _on_assign_view_changed(self, mode: str) -> None:
        """Switch between deadline and group view."""
        self._assign_view_mode = mode
        self._refresh_assignment_list()
        self._update_summary()

    def _qs_select_this_week(self, _: bool) -> None:
        """Check all 'due this week' assignments."""
        for row in self._assign_rows:
            is_week = _classify_deadline(row.assign_dict.get("due_at", "")) == "WEEK"
            row.set_checked(is_week)
        self._update_summary()

    def _qs_select_past_due(self, _: bool) -> None:
        """Check all past-due assignments."""
        for row in self._assign_rows:
            is_past = _classify_deadline(row.assign_dict.get("due_at", "")) == "PAST"
            row.set_checked(is_past)
        self._update_summary()

    def _qs_select_with_submissions(self, _: bool) -> None:
        """Check all assignments that have submitted (or ungraded) submissions."""
        for row in self._assign_rows:
            a = row.assign_dict
            has_subs = bool(
                a.get("has_submitted_submissions")
                or a.get("needs_grading_count", 0) > 0
            )
            row.set_checked(has_subs)
        self._update_summary()

    def _refresh_assignment_list(self) -> None:
        """Rebuild assignment rows for all checked courses (deadline or group view)."""
        self._assign_rows.clear()

        # Collect (course, assignment) pairs for checked courses
        pairs: list = []
        for row in self._course_rows:
            if not row.is_checked():
                continue
            course = row._course
            cid    = course.get("id")
            groups = self._assignments_cache.get(cid, [])
            for group in groups:
                for a in group.get("assignments", []):
                    pairs.append((course, a, group.get("name", "Assignments")))

        # Determine whether to show course pill (multi-course selection)
        checked_course_ids = {row._course.get("id") for row in self._course_rows if row.is_checked()}
        show_pill = len(checked_course_ids) > 1

        content = QWidget()
        content.setStyleSheet(f"background: {BG_INSET};")
        content_lo = QVBoxLayout(content)
        content_lo.setContentsMargins(0, 2, 0, 4)
        content_lo.setSpacing(0)

        if self._assign_view_mode == "deadline":
            self._build_deadline_view(content_lo, pairs, show_pill)
        else:
            self._build_group_view(content_lo, pairs, show_pill)

        content_lo.addStretch()
        if self._assign_scroll is not None:
            self._assign_scroll.setWidget(content)

        # Fetch submission counts in background
        self._fetch_submission_counts()

    def _build_deadline_view(self, lo: QVBoxLayout, pairs: list, show_pill: bool) -> None:
        """Build the deadline-grouped assignment list."""
        _SECTION_META = [
            ("PAST",   "DEADLINE PASSED", _PAST_COLOR),
            ("WEEK",   "DUE THIS WEEK",   _WEEK_COLOR),
            ("FUTURE", "UPCOMING",         _FUTURE_COLOR),
            ("NONE",   "NO DEADLINE",      _NONE_COLOR),
        ]
        buckets: dict = {k: [] for k, _, _ in _SECTION_META}
        for course, a, _group_name in pairs:
            key = _classify_deadline(a.get("due_at", ""))
            buckets[key].append((course, a))

        for key, label, color in _SECTION_META:
            items = buckets[key]
            if not items:
                continue
            lo.addWidget(_DeadlineSection(label, color))
            for course, a in items:
                pill = (course.get("course_code") or course.get("code", ""))[:8] if show_pill else ""
                arow = _AssignRow(course, a, course_pill=pill)
                arow.toggled.connect(self._update_summary)
                self._assign_rows.append(arow)
                lo.addWidget(arow)
            lo.addSpacing(4)

    def _build_group_view(self, lo: QVBoxLayout, pairs: list, show_pill: bool) -> None:
        """Build the assignment-group-grouped list with collapsible sections."""
        # Preserve insertion order of groups
        group_order: list = []
        groups: dict = {}
        for course, a, group_name in pairs:
            key = group_name
            if key not in groups:
                group_order.append(key)
                groups[key] = []
            groups[key].append((course, a))

        for group_name in group_order:
            section = _GroupSection(group_name)
            for course, a in groups[group_name]:
                pill = (course.get("course_code") or course.get("code", ""))[:8] if show_pill else ""
                arow = _AssignRow(course, a, course_pill=pill)
                arow.toggled.connect(self._update_summary)
                self._assign_rows.append(arow)
                section.add_row(arow)
            lo.addWidget(section)

    def _update_summary(self) -> None:
        """Update the footer summary text."""
        checked = self._get_checked_assignments()
        courses = set()
        for c, a in checked:
            courses.add(c.get("id"))
        n_assign = len(checked)
        n_courses = len(courses)
        if n_assign:
            tier = self._depth_toggle.mode
            tier_hint = {
                "quick": " \u00b7 instant results, no model needed",
                "lightweight": " \u00b7 best run overnight (8B model)",
                "medium": " \u00b7 ~70B model or institutional API",
                "deep_thinking": " \u00b7 frontier model (institutional API)",
            }.get(tier, "")

            # Quick estimate of total students from checked assignments
            total_students = 0
            for c, a in checked:
                # Try cached count first
                ngc = a.get("needs_grading_count")
                if ngc is not None:
                    total_students += int(ngc)
                else:
                    # Estimate from enrollment if available
                    total_students += c.get("total_students", 0)

            student_text = ""
            if total_students > 0:
                student_text = f" \u00b7 ~{total_students} students"

            self._setup_summary.setText(
                f"{n_assign} assignment{'s' if n_assign != 1 else ''} "
                f"across {n_courses} course{'s' if n_courses != 1 else ''}"
                f"{student_text}{tier_hint}"
            )
            self._start_btn.setEnabled(True)
        else:
            self._setup_summary.setText("Select assignments to analyze.")
            self._start_btn.setEnabled(False)

    def _get_checked_assignments(self) -> List[tuple]:
        """Return [(course_dict, assignment_dict), ...] for checked rows."""
        return [
            (r.course_dict, r.assign_dict)
            for r in self._assign_rows
            if r.is_checked()
        ]

    # ------------------------------------------------------------------
    # Profile manager + toast + invalidation + edit handlers
    # ------------------------------------------------------------------

    def _ensure_profile_mgr(self) -> None:
        """Lazily initialize the TeacherProfileManager for the current run.

        Uses the course_profile_id stored on the run so that Ethnic Studies
        and Native Studies (or any two courses) each get their own accumulated
        profile rather than sharing a single "default" one.
        """
        if self._profile_mgr is None and self._store:
            from insights.teacher_profile import TeacherProfileManager
            profile_id = "default"
            if self._current_run_id:
                run = self._store.get_run(self._current_run_id)
                if run:
                    profile_id = run.get("course_profile_id") or "default"
            self._profile_mgr = TeacherProfileManager(self._store, profile_id)

    def _show_toast(self, msg: str) -> None:
        """Show a temporary overlay message that fades after 3 seconds."""
        toast = QLabel(msg, self)
        toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toast.setStyleSheet(
            f"QLabel {{ background: {BG_CARD}; color: {PHOSPHOR_HOT};"
            f" border: 1px solid {BORDER_AMBER}; border-radius: 6px;"
            f" font-size: {px(12)}px; padding: 8px 16px; }}"
        )
        toast.adjustSize()
        toast.move(
            self.width() // 2 - toast.width() // 2,
            self.height() - toast.height() - 40,
        )
        toast.show()
        QTimer.singleShot(3000, toast.deleteLater)

    def _invalidate_layers(self, *names: str) -> None:
        """Clear named layers from cache. Reloads if currently visible."""
        for name in names:
            self._loaded_layers.discard(name)
        # Reload the currently visible layer if invalidated
        current_mode = getattr(self, "_layer_toggle", None)
        if current_mode:
            mode = current_mode.mode
            if mode in names:
                self._load_layer(mode)

    def _trigger_partial_rerun(self, start_stage: str) -> None:
        """Launch a PartialRerunWorker for downstream re-generation."""
        run_id = self._current_run_id
        if not run_id or not self._store:
            return

        from gui.workers import PartialRerunWorker
        self._rerun_worker = PartialRerunWorker(
            self._api,
            run_id=run_id,
            start_stage=start_stage,
            store=self._store,
            settings=self._get_settings(),
        )
        self._rerun_worker.progress_update.connect(
            lambda msg: self._show_toast(msg)
        )
        self._rerun_worker.rerun_complete.connect(self._on_rerun_complete)
        self._rerun_worker.error.connect(
            lambda msg: self._show_toast(f"Re-run error: {msg}")
        )
        self._rerun_worker.start()
        self._show_toast(f"Re-running from {start_stage}...")

    def _on_rerun_complete(self, run_id: str, stages: list) -> None:
        """Handle partial rerun completion — invalidate downstream layers."""
        stage_to_layer = {
            "themes": "themes",
            "outliers": "outliers",
            "synthesis": "report",
        }
        layers = [stage_to_layer.get(s, s) for s in stages]
        self._invalidate_layers(*layers)
        self._show_toast("Re-run complete.")

    # ── Tag edit handlers ──

    def _on_remove_tag(self, run_id: str, student_id: str, tag: str) -> None:
        """Remove a theme tag from a student's coding record."""
        if not self._store:
            return
        row = self._store.get_coding_record(run_id, student_id)
        if not row:
            return
        record = row.get("coding_record", {})
        if isinstance(record, str):
            record = json.loads(record)
        tags = record.get("theme_tags", [])
        if tag in tags:
            tags.remove(tag)
        record["theme_tags"] = tags
        edits = row.get("teacher_edits") or {}
        if isinstance(edits, str):
            edits = json.loads(edits)
        edits.setdefault("tag_removals", []).append(tag)

        record_json = json.dumps(record)
        self._store.update_coding_tags(run_id, student_id, record_json, edits)

        # Calibration
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"theme_tags": tags + [tag]}),
            json.dumps({"theme_tags": tags}), "tag_remove",
        )
        if self._profile_mgr:
            self._profile_mgr.record_tag_edit(student_id, [], [tag])

        self._invalidate_layers("codings")
        self._trigger_partial_rerun("themes")
        self._show_toast(f"Removed tag: {tag}")

    def _on_add_tag(self, run_id: str, student_id: str, tag: str) -> None:
        """Add a theme tag to a student's coding record."""
        if not self._store or tag == "+ tag":
            return
        row = self._store.get_coding_record(run_id, student_id)
        if not row:
            return
        record = row.get("coding_record", {})
        if isinstance(record, str):
            record = json.loads(record)
        tags = record.get("theme_tags", [])
        if tag not in tags:
            tags.append(tag)
        record["theme_tags"] = tags
        edits = row.get("teacher_edits") or {}
        if isinstance(edits, str):
            edits = json.loads(edits)
        edits.setdefault("tag_additions", []).append(tag)

        record_json = json.dumps(record)
        self._store.update_coding_tags(run_id, student_id, record_json, edits)

        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"theme_tags": [t for t in tags if t != tag]}),
            json.dumps({"theme_tags": tags}), "tag_add",
        )
        if self._profile_mgr:
            self._profile_mgr.record_tag_edit(student_id, [tag], [])

        self._invalidate_layers("codings")
        self._trigger_partial_rerun("themes")
        self._show_toast(f"Added tag: {tag}")

    # ── Concern action handlers ──

    def _on_concern_action(
        self, run_id: str, student_id: str, concern_idx: int, action: str,
    ) -> None:
        """Handle Acknowledge or Dismiss on a concern. NEVER batchable."""
        if not self._store:
            return
        row = self._store.get_coding_record(run_id, student_id)
        if not row:
            return
        record = row.get("coding_record", {})
        if isinstance(record, str):
            record = json.loads(record)
        concerns = record.get("concerns", [])
        if concern_idx >= len(concerns):
            return

        concern = concerns[concern_idx]
        edits = row.get("teacher_edits") or {}
        if isinstance(edits, str):
            edits = json.loads(edits)

        if action == "dismiss":
            concerns.pop(concern_idx)
            edits.setdefault("concerns_dismissed", []).append(
                concern.get("flagged_passage", "")[:60]
            )
        else:
            concern["teacher_acknowledged"] = True
            edits.setdefault("concerns_acknowledged", []).append(
                concern.get("flagged_passage", "")[:60]
            )

        record["concerns"] = concerns
        record_json = json.dumps(record)
        self._store.update_coding_concerns(run_id, student_id, record_json, edits)

        # Profile calibration
        wellbeing_note = None
        if self._profile_mgr:
            wellbeing_note = self._profile_mgr.record_concern_action(
                concern.get("why_flagged", ""), action
            )
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", "", json.dumps(concern),
            f"concern_{action}",
        )

        self._invalidate_layers("codings")
        if wellbeing_note:
            self._show_toast(wellbeing_note)
        else:
            self._show_toast(
                f"Concern {'acknowledged' if action == 'acknowledge' else 'dismissed'}."
            )

    # ── Theme edit handlers ──

    def _on_theme_rename(self, run_id: str, old_name: str, new_name: str) -> None:
        """Rename a theme in the theme set."""
        if not self._store or old_name == new_name or not new_name.strip():
            return
        row = self._store.get_themes(run_id)
        if not row or not row.get("theme_set"):
            return
        data = json.loads(row["theme_set"])
        for t in data.get("themes", []):
            if t.get("name") == old_name:
                t["name"] = new_name.strip()
                break
        edits = {"renames": {old_name: new_name.strip()}}
        self._store.update_theme_set(run_id, json.dumps(data), edits)

        if self._profile_mgr:
            self._profile_mgr.record_theme_rename(old_name, new_name.strip())
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"name": old_name}),
            json.dumps({"name": new_name.strip()}), "theme_rename",
        )

        self._invalidate_layers("themes")
        self._trigger_partial_rerun("outliers")
        self._show_toast(f"Renamed: {old_name} \u2192 {new_name.strip()}")

    def _on_theme_split(self, run_id: str, theme_name: str) -> None:
        """Open a dialog to split a theme into children."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Split: {theme_name}")
        dlg.setStyleSheet(
            f"QDialog {{ background: {BG_CARD}; }}"
            f"QLabel {{ color: {PHOSPHOR_MID}; background: transparent; border: none; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.addWidget(QLabel(f"Split \"{theme_name}\" into sub-themes.\nEnter one name per line:"))
        te = QTextEdit()
        te.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" font-family: 'Menlo', 'Consolas', monospace; padding: 4px; }}"
        )
        te.setMaximumHeight(100)
        lo.addWidget(te)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lo.addWidget(bb)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            children = [
                line.strip() for line in te.toPlainText().split("\n")
                if line.strip()
            ]
            if len(children) >= 2:
                self._apply_theme_split(run_id, theme_name, children)

    def _apply_theme_split(
        self, run_id: str, original: str, children: List[str],
    ) -> None:
        """Replace a theme with its children in the theme set."""
        if not self._store:
            return
        row = self._store.get_themes(run_id)
        if not row or not row.get("theme_set"):
            return
        data = json.loads(row["theme_set"])
        themes = data.get("themes", [])

        # Find original and split it
        original_theme = None
        new_themes = []
        for t in themes:
            if t.get("name") == original:
                original_theme = t
            else:
                new_themes.append(t)

        if original_theme:
            for child_name in children:
                new_themes.append({
                    "name": child_name,
                    "description": f"Sub-theme of: {original}",
                    "frequency": 0,
                    "student_ids": [],
                    "supporting_quotes": [],
                    "confidence": original_theme.get("confidence", 0.5),
                    "sub_themes": None,
                })
        data["themes"] = new_themes
        edits = {"splits": {original: children}}
        self._store.update_theme_set(run_id, json.dumps(data), edits)

        if self._profile_mgr:
            self._profile_mgr.record_theme_split(original, children)

        self._invalidate_layers("themes")
        self._trigger_partial_rerun("outliers")
        self._show_toast(f"Split \"{original}\" into {len(children)} themes")

    def _on_theme_delete(self, run_id: str, theme_name: str) -> None:
        """Delete a theme from the theme set."""
        if not self._store:
            return
        row = self._store.get_themes(run_id)
        if not row or not row.get("theme_set"):
            return
        data = json.loads(row["theme_set"])
        data["themes"] = [
            t for t in data.get("themes", [])
            if t.get("name") != theme_name
        ]
        edits = {"deletions": [theme_name]}
        self._store.update_theme_set(run_id, json.dumps(data), edits)

        # Profile calibration
        if self._profile_mgr:
            self._profile_mgr.record_theme_delete(theme_name)
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"theme": theme_name}), "",
            "theme_delete",
        )

        self._invalidate_layers("themes")
        self._trigger_partial_rerun("outliers")
        self._show_toast(f"Deleted theme: {theme_name}")

    def _on_theme_merge(self, run_id: str, theme_names: List[str]) -> None:
        """Merge selected themes into one. Prompts for target name."""
        if not self._store or len(theme_names) < 2:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Merge Themes")
        dlg.setStyleSheet(
            f"QDialog {{ background: {BG_CARD}; }}"
            f"QLabel {{ color: {PHOSPHOR_MID}; background: transparent; border: none; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.addWidget(QLabel(f"Merging: {', '.join(theme_names)}"))
        lo.addWidget(QLabel("Name for merged theme:"))
        name_edit = QLineEdit(theme_names[0])
        name_edit.setStyleSheet(
            f"QLineEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" padding: 4px; }}"
        )
        lo.addWidget(name_edit)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lo.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        target_name = name_edit.text().strip() or theme_names[0]
        row = self._store.get_themes(run_id)
        if not row or not row.get("theme_set"):
            return
        data = json.loads(row["theme_set"])

        merged_sids = []
        merged_quotes = []
        merged_freq = 0
        new_themes = []
        for t in data.get("themes", []):
            if t.get("name") in theme_names:
                merged_sids.extend(t.get("student_ids", []))
                merged_quotes.extend(t.get("supporting_quotes", []))
                merged_freq += t.get("frequency", 0)
            else:
                new_themes.append(t)

        new_themes.append({
            "name": target_name,
            "description": f"Merged from: {', '.join(theme_names)}",
            "frequency": merged_freq,
            "student_ids": list(set(merged_sids)),
            "supporting_quotes": merged_quotes[:6],
            "confidence": 0.7,
            "sub_themes": theme_names,
        })
        data["themes"] = new_themes
        edits = {"merges": {"sources": theme_names, "target": target_name}}
        self._store.update_theme_set(run_id, json.dumps(data), edits)

        if self._profile_mgr:
            self._profile_mgr.record_theme_merge(theme_names, target_name)

        self._invalidate_layers("themes")
        self._trigger_partial_rerun("outliers")
        self._show_toast(f"Merged {len(theme_names)} themes \u2192 {target_name}")

    # ── Outlier edit handlers ──

    def _on_outlier_add_to_theme(
        self, run_id: str, student_id: str, theme_name: str,
    ) -> None:
        """Move an outlier student into an existing theme."""
        if not self._store:
            return
        row = self._store.get_themes(run_id)
        if not row:
            return

        # Add student to theme
        if row.get("theme_set"):
            ts_data = json.loads(row["theme_set"])
            for t in ts_data.get("themes", []):
                if t.get("name") == theme_name:
                    sids = t.get("student_ids", [])
                    if student_id not in sids:
                        sids.append(student_id)
                    t["student_ids"] = sids
                    t["frequency"] = len(sids)
                    break
            self._store.update_theme_set(
                run_id, json.dumps(ts_data),
                {"outlier_to_theme": {student_id: theme_name}},
            )

        # Remove from outlier report
        if row.get("outlier_report"):
            or_data = json.loads(row["outlier_report"])
            or_data["outliers"] = [
                o for o in or_data.get("outliers", [])
                if o.get("student_id") != student_id
            ]
            self._store.update_outlier_report(run_id, json.dumps(or_data))

        # Profile calibration
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"student_id": student_id}),
            json.dumps({"theme": theme_name}),
            "outlier_to_theme",
        )

        self._invalidate_layers("themes", "outliers")
        self._trigger_partial_rerun("synthesis")
        self._show_toast(f"Added to theme: {theme_name}")

    def _on_outlier_create_theme(
        self, run_id: str, student_id: str, student_name: str,
    ) -> None:
        """Create a new theme from an outlier."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Create Theme from Outlier")
        dlg.setStyleSheet(
            f"QDialog {{ background: {BG_CARD}; }}"
            f"QLabel {{ color: {PHOSPHOR_MID}; background: transparent; border: none; }}"
        )
        lo = QVBoxLayout(dlg)
        lo.addWidget(QLabel(f"Create new theme for {student_name}:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Theme name...")
        name_edit.setStyleSheet(
            f"QLineEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" padding: 4px; }}"
        )
        lo.addWidget(name_edit)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lo.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        theme_name = name_edit.text().strip()
        if not theme_name:
            return

        row = self._store.get_themes(run_id)
        if not row:
            return

        # Add new theme
        if row.get("theme_set"):
            ts_data = json.loads(row["theme_set"])
            ts_data.get("themes", []).append({
                "name": theme_name,
                "description": f"Created from outlier: {student_name}",
                "frequency": 1,
                "student_ids": [student_id],
                "supporting_quotes": [],
                "confidence": 0.5,
                "sub_themes": None,
            })
            self._store.update_theme_set(
                run_id, json.dumps(ts_data),
                {"created_from_outlier": {student_id: theme_name}},
            )

        # Remove from outlier report
        if row.get("outlier_report"):
            or_data = json.loads(row["outlier_report"])
            or_data["outliers"] = [
                o for o in or_data.get("outliers", [])
                if o.get("student_id") != student_id
            ]
            self._store.update_outlier_report(run_id, json.dumps(or_data))

        # Profile calibration
        self._store.save_calibration(
            self._profile_mgr._profile_id if self._profile_mgr else "default",
            "", json.dumps({"student_id": student_id}),
            json.dumps({"theme": theme_name}),
            "outlier_create_theme",
        )

        self._invalidate_layers("themes", "outliers")
        self._trigger_partial_rerun("synthesis")
        self._show_toast(f"Created theme: {theme_name}")

    # ── Report edit handler ──

    def _on_report_section_save(
        self, run_id: str, section_key: str, new_text: str,
    ) -> None:
        """Save a directly edited report section."""
        if not self._store:
            return
        row = self._store.get_themes(run_id)
        if not row or not row.get("synthesis_report"):
            return
        data = json.loads(row["synthesis_report"])
        data.setdefault("sections", {})[section_key] = new_text
        self._store.update_synthesis_report(run_id, json.dumps(data))
        self._show_toast(f"Saved: {section_key.replace('_', ' ').title()}")

    # ------------------------------------------------------------------
    # Start analysis (supports batch mode)
    # ------------------------------------------------------------------

    def _fetch_submission_counts(self) -> None:
        """Kick off background workers to fetch submission counts per assignment."""
        if not self._api or not self._assign_rows:
            return

        # Cancel any previous count worker
        if hasattr(self, "_count_worker") and self._count_worker and self._count_worker.isRunning():
            self._count_worker.cancel()
            self._count_worker.wait(1000)

        # Group assignments by course for efficient fetching
        from collections import defaultdict
        by_course = defaultdict(list)
        self._assign_id_to_row = {}
        for arow in self._assign_rows:
            cid = arow.course_dict.get("id")
            aid = arow.assign_dict.get("id")
            if cid and aid:
                by_course[cid].append(aid)
                self._assign_id_to_row[aid] = arow

        # Fetch for the first course (we can extend to multiple later)
        # For simplicity, flatten all courses into one worker per course
        from gui.workers import LoadSubmissionCountsWorker
        all_aids = []
        first_cid = None
        for cid, aids in by_course.items():
            if not first_cid:
                first_cid = cid
            all_aids.extend(aids)

        if not first_cid or not all_aids:
            return

        # Use a single worker per course — for multi-course, we chain them
        self._count_courses = list(by_course.items())
        self._count_idx = 0
        self._run_next_count_worker()

    def _run_next_count_worker(self) -> None:
        if self._count_idx >= len(self._count_courses):
            return
        cid, aids = self._count_courses[self._count_idx]
        self._count_idx += 1

        from gui.workers import LoadSubmissionCountsWorker
        self._count_worker = LoadSubmissionCountsWorker(
            self._api, cid, aids
        )
        self._count_worker.count_ready.connect(self._on_sub_count_ready)
        self._count_worker.finished.connect(self._run_next_count_worker)
        self._count_worker.start()

    def _on_sub_count_ready(self, assignment_id: int, count: int) -> None:
        """Buffer submission counts — display all at once when complete."""
        if not hasattr(self, "_pending_counts"):
            self._pending_counts = {}
        self._pending_counts[assignment_id] = count

        # Check if all assignments have been counted
        total_expected = len(getattr(self, "_assign_id_to_row", {}))
        if len(self._pending_counts) >= total_expected:
            # All done — update all rows at once
            for aid, cnt in self._pending_counts.items():
                arow = self._assign_id_to_row.get(aid)
                if arow:
                    arow.set_submission_count(cnt)
            self._pending_counts = {}

    def _show_prior_insights(self) -> None:
        """Switch to review view."""
        self._switch_view(2)

    def _show_setup_assistant(self) -> None:
        """Show the Insights setup assistant dialog."""
        from gui.dialogs.insights_setup_dialog import InsightsSetupDialog
        dlg = InsightsSetupDialog(self)
        dlg.exec()

    def _on_start_analysis(self) -> None:
        """Start the analysis pipeline."""
        if self._worker and self._worker.isRunning():
            return
        checked = self._get_checked_assignments()
        if not checked:
            return

        if not self._api and not self._demo_mode:
            self._setup_summary.setText(
                "Configure Canvas credentials in Settings first."
            )
            return

        # Check if LLM is needed but not available
        tier = self._depth_toggle.mode
        if tier != "quick":
            from gui.dialogs.insights_setup_dialog import (
                _check_ollama_running, _check_ollama_model,
            )
            if not _check_ollama_running() or not _check_ollama_model():
                self._setup_summary.setText(
                    "AI model not ready. Click Setup Assistant below."
                )
                self._show_setup_assistant()
                return

        # Switch to running state
        self._switch_view(1)
        self._progress_label.setText("Starting analysis...")
        self._progress_bar.setValue(0)
        # Start elapsed timer
        import time as _time_mod
        self._elapsed_start = _time_mod.time()
        self._elapsed_label.setText("Elapsed: 0m 0s")
        self._stage_desc_label.setText("")
        self._elapsed_timer.start(1000)
        self._log_output.clear()
        # Clear live results feed
        while self._live_lo.count():
            item = self._live_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._live_lo.addStretch()
        self._append_log("Starting analysis pipeline...")
        self._progress_detail.setText("")

        # Persist selected tier for next session (Issue 9)
        from settings import load_settings as _load_s2, save_settings as _save_s2
        _cur = _load_s2()
        _cur["insights_model_tier"] = tier
        _save_s2(_cur)

        # Show which assignment is being analyzed
        checked = self._get_checked_assignments()
        if checked:
            c, a = checked[0]
            # Match course select display: nickname > name, with course_code
            title = c.get("friendly_name") or c.get("original_name") or c.get("name", "")
            code = c.get("course_code", "")
            if title and code and code not in title:
                course_display = f"{code} — {title}"
            else:
                course_display = title or code
            assign_name = a.get("name", "")
            self._live_header.setText(f"{course_display}  \u00b7  {assign_name}")
            self._live_header.setVisible(True)

        # Group by course — each course's assignments are separate runs
        from collections import defaultdict
        by_course: Dict[int, list] = defaultdict(list)
        for course, assignment in checked:
            by_course[course["id"]].append((course, assignment))

        # Gather teacher input
        teacher_context = self._week_input.toPlainText().strip()
        next_week = self._next_week_input.toPlainText().strip()

        lens_text = self._lens_input.toPlainText().strip()
        analysis_lens = None
        if lens_text:
            analysis_lens = {"analysis_lens": lens_text}

        focus_text = self._focus_input.toPlainText().strip()
        teacher_interests = None
        if focus_text:
            teacher_interests = [line.strip() for line in focus_text.split("\n") if line.strip()]

        # Equity surfacing text — appended to teacher context for prompt injection
        equity_text = self._equity_input.toPlainText().strip()
        if equity_text:
            teacher_context += f"\n\nEQUITY SURFACING (teacher-defined):\n{equity_text}"

        # Persist teacher inputs to profile for future run defaults
        if self._profile_mgr:
            if teacher_interests:
                self._profile_mgr.record_interest_areas(teacher_interests)
            if analysis_lens:
                self._profile_mgr.record_analysis_lens(analysis_lens)

        # Read AI policy for this run
        _ai_pol = (
            self._ai_policy_combo.currentData()
            if hasattr(self, "_ai_policy_combo") and self._ai_policy_combo
            else "not_expected"
        )

        # Batch mode when >1 assignment selected
        if len(checked) > 1:
            from gui.workers import BatchInsightsWorker
            self._worker = BatchInsightsWorker(
                self._api,
                assignments=checked,
                store=self._store,
                translate_enabled=self._translate_toggle.isChecked(),
                transcribe_enabled=self._transcribe_toggle.isChecked(),
                model_tier=self._depth_toggle.mode,
                teacher_context=teacher_context,
                analysis_lens=analysis_lens,
                teacher_interests=teacher_interests,
                settings=self._get_settings(),
                course_profile_id=self._profile_combo.currentData() or "default",
                next_week_topic=next_week,
                teacher_lens=lens_text,
                ai_policy=_ai_pol,
            )
            self._worker.progress_update.connect(self._on_progress)
            self._worker.result_ready.connect(self._append_live_result)
            self._worker.batch_complete.connect(self._on_batch_complete)
            self._worker.error.connect(self._on_analysis_error)
            self._worker.start()
        else:
            from gui.workers import InsightsWorker
            first_course = checked[0][0]
            first_assign = checked[0][1]
            is_discussion = first_assign.get("submission_types", []) == ["discussion_topic"]

            self._worker = InsightsWorker(
                self._api,
                store=self._store,
                course_id=first_course["id"],
                course_name=first_course.get("name", ""),
                assignment_id=first_assign["id"],
                assignment_name=first_assign.get("name", ""),
                is_discussion=is_discussion,
                translate_enabled=self._translate_toggle.isChecked(),
                transcribe_enabled=self._transcribe_toggle.isChecked(),
                model_tier=self._depth_toggle.mode,
                teacher_context=teacher_context,
                analysis_lens=analysis_lens,
                teacher_interests=teacher_interests,
                settings=self._get_settings(),
                course_profile_id=self._profile_combo.currentData() or "default",
                next_week_topic=next_week,
                teacher_lens=lens_text,
                ai_policy=_ai_pol,
            )
            self._worker.progress_update.connect(self._on_progress)
            self._worker.result_ready.connect(self._append_live_result)
            self._worker.analysis_complete.connect(self._on_analysis_complete)
            self._worker.error.connect(self._on_analysis_error)
            self._worker.start()

    def _get_settings(self) -> dict:
        """Collect current settings for the engine."""
        try:
            from settings import load_settings
            s = load_settings()
        except Exception:
            s = {}
        # Pass through toggles from setup UI
        s["insights_draft_feedback"] = self._feedback_toggle.isChecked()
        s["insights_handwriting_enabled"] = self._handwriting_toggle.isChecked()
        return s

    def _on_progress(self, message: str) -> None:
        self._progress_label.setText(message)
        self._append_log(message)

        # Extract progress from messages like "Run 2/3" and "(6/28)"
        # Track both run-level and submission-level progress for overall bar
        import re

        run_match = re.search(r'Run\s+(\d+)/(\d+)', message)
        sub_match = re.search(r'[\(\[]?(\d+)/(\d+)[\)\]]?:', message)

        if run_match:
            self._batch_run_idx = int(run_match.group(1)) - 1  # 0-based
            self._batch_run_total = int(run_match.group(2))

        if sub_match:
            sub_current = int(sub_match.group(1))
            sub_total = int(sub_match.group(2))
            run_idx = getattr(self, "_batch_run_idx", 0)
            run_total = getattr(self, "_batch_run_total", 1)

            if run_total > 0 and sub_total > 0:
                # Each run gets an equal slice of the bar
                run_slice = 100.0 / run_total
                run_base = run_idx * run_slice
                sub_pct = sub_current / sub_total
                overall = int(run_base + sub_pct * run_slice)
                self._progress_bar.setValue(min(overall, 99))

        # Stage descriptions for teacher context (Issue 7)
        _STAGE_DESCRIPTIONS = {
            "class_reading": (
                "Reading all submissions together \u2014 some patterns are "
                "only visible when student work is read as a conversation."
            ),
            "coding": "Generating detailed observations for each student.",
            "observation": "Generating detailed observations for each student.",
            "concerns": "Checking for students who may need support.",
            "themes": "Identifying shared themes across student work.",
            "synthesis": "Writing the class summary from observations.",
            "feedback": "Drafting feedback for each student.",
        }
        msg_lower = message.lower()
        for stage_key, desc in _STAGE_DESCRIPTIONS.items():
            if stage_key in msg_lower:
                self._stage_desc_label.setText(desc)
                break

        # Stage-level progress for non-submission stages
        if not sub_match:
            stage_keywords = {
                "generating themes": 70,
                "re-generating themes": 70,
                "surfacing outlier": 80,
                "generating synthesis": 90,
                "re-generating synthesis": 90,
                "drafting feedback": 95,
                "analysis complete": 100,
                "re-run complete": 100,
                "batch complete": 100,
            }
            for keyword, pct in stage_keywords.items():
                if keyword in msg_lower:
                    self._progress_bar.setValue(pct)
                    break

    def _update_elapsed(self) -> None:
        """Update the elapsed time display in the running view."""
        if self._elapsed_start:
            import time as _time_mod
            elapsed = int(_time_mod.time() - self._elapsed_start)
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            if h:
                self._elapsed_label.setText(f"Elapsed: {h}h {m}m")
            else:
                self._elapsed_label.setText(f"Elapsed: {m}m {s}s")

    def _stop_elapsed_timer(self) -> None:
        """Stop the elapsed timer."""
        self._elapsed_timer.stop()
        self._elapsed_start = None

    def _on_analysis_complete(self, run_id: str) -> None:
        self._stop_elapsed_timer()
        self._progress_label.setText("Analysis complete!")
        self._progress_bar.setValue(100)
        self._append_log("✓ Analysis complete! Switching to results...")
        self._refresh_incomplete_notice()

        self._switch_view(2)
        self._load_run(run_id)

    def _on_batch_complete(self, run_ids: list) -> None:
        """Handle batch insights completion."""
        self._stop_elapsed_timer()
        n = len(run_ids)
        self._progress_label.setText(f"Batch complete! {n} run{'s' if n != 1 else ''}.")
        self._progress_detail.setText("Switching to review...")
        self._refresh_incomplete_notice()
        self._switch_view(2)
        if run_ids:
            self._load_run(run_ids[0])

    def _on_analysis_error(self, message: str) -> None:
        self._stop_elapsed_timer()
        self._progress_label.setText(f"Error: {message}")
        self._progress_detail.setText("Start a new analysis from Bulk Run.")

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker.wait(3000)  # wait up to 3 seconds for clean shutdown
        self._switch_view(0)

    def _on_rerun_selected(self, index: int) -> None:
        """Handle re-run dropdown selection."""
        if index == 0:
            return  # "Re-run..." placeholder
        self._rerun_combo.setCurrentIndex(0)  # reset to placeholder
        if self._worker and self._worker.isRunning():
            return

        run_id = self._current_run_id
        if not run_id or not self._store:
            return

        stage_map = {
            1: "themes",      # Re-generate Themes
            2: "synthesis",   # Re-generate Report
            3: "themes",      # Re-generate All
        }
        start_stage = stage_map.get(index)
        if not start_stage:
            return

        # Switch to running view
        self._switch_view(1)
        self._progress_label.setText(f"Re-running from {start_stage}...")
        self._progress_bar.setValue(0)
        self._log_output.clear()
        while self._live_lo.count():
            item = self._live_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._live_lo.addStretch()
        self._append_log(f"Re-running analysis from {start_stage}...")

        from gui.workers import RerunWorker
        self._worker = RerunWorker(
            self._store,
            run_id=run_id,
            start_stage=start_stage,
            settings=self._get_settings(),
        )
        self._worker.progress_update.connect(self._on_progress)
        self._worker.analysis_complete.connect(self._on_analysis_complete)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_export_chatbot(self) -> None:
        """Open the chatbot export dialog for the current run."""
        if not self._current_run_id or not self._store:
            return
        from gui.dialogs.chatbot_export_dialog import ChatbotExportDialog
        dlg = ChatbotExportDialog(
            store=self._store,
            run_id=self._current_run_id,
            parent=self,
        )
        dlg.exec()

    def _refresh_incomplete_notice(self) -> None:
        """Update the paused-run banner in the setup view."""
        if not hasattr(self, "_incomplete_notice") or not self._store:
            return
        try:
            runs = self._store.get_runs()
        except Exception:
            return
        incomplete = [r for r in runs if r.get("completed_at") is None]
        n = len(incomplete)
        self.paused_count_changed.emit(n)
        if incomplete:
            most_recent = incomplete[0]
            name = most_recent.get("assignment_name", "analysis")
            if n == 1:
                self._incomplete_count_label.setText(
                    f"Analysis paused mid-run: {name}"
                )
            else:
                self._incomplete_count_label.setText(
                    f"{n} analyses paused — most recent: {name}"
                )
            self._incomplete_notice.setVisible(True)
        else:
            self._incomplete_notice.setVisible(False)

    def _on_show_incomplete_run(self) -> None:
        """Navigate to the most recent incomplete run in the review view."""
        if not self._store:
            return
        try:
            runs = self._store.get_runs()
        except Exception:
            return
        for run in runs:
            if run.get("completed_at") is None:
                self._switch_view(2)
                self._load_run(run.get("run_id", ""))
                return

    def _on_resume_run(self) -> None:
        """Resume a partial run from where it stopped."""
        if self._worker and self._worker.isRunning():
            return
        run_id = self._current_run_id
        if not run_id or not self._store:
            return

        run = self._store.get_run(run_id)
        if not run:
            return

        stages = run.get("stages_completed", [])
        if isinstance(stages, str):
            try:
                stages = json.loads(stages)
            except Exception:
                stages = []

        # Determine next stage to run
        all_stages = [
            "data_fetch", "preprocessing", "quick_analysis",
            "coding", "concerns", "themes", "outliers", "synthesis",
        ]
        completed_set = set(stages)

        # Find first incomplete stage
        next_stage = None
        for s in all_stages:
            if s not in completed_set:
                next_stage = s
                break

        if next_stage is None:
            return  # Already complete

        # Clear live results feed
        while self._live_lo.count():
            item = self._live_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._live_lo.addStretch()

        # For stages after coding, use run_partial
        if next_stage in ("themes", "outliers", "synthesis"):
            self._switch_view(1)
            self._progress_label.setText(f"Resuming from {next_stage}...")
            self._progress_bar.setValue(0)
            self._log_output.clear()
            self._append_log(f"Resuming run from {next_stage}...")

            from gui.workers import RerunWorker
            self._worker = RerunWorker(
                self._store,
                run_id=run_id,
                start_stage=next_stage,
                settings=self._get_settings(),
            )
            self._worker.progress_update.connect(self._on_progress)
            self._worker.analysis_complete.connect(self._on_analysis_complete)
            self._worker.error.connect(self._on_analysis_error)
            self._worker.start()
        else:
            # For earlier stages (coding, concerns), need full re-run
            # with skip logic — use run_analysis with resume awareness
            self._switch_view(1)
            self._progress_label.setText(f"Resuming from {next_stage}...")
            self._progress_bar.setValue(0)
            self._log_output.clear()
            self._append_log(
                f"Resuming run — {len(stages)} stages complete, "
                f"starting from {next_stage}..."
            )

            from gui.workers import ResumeInsightsWorker
            self._worker = ResumeInsightsWorker(
                self._api,
                store=self._store,
                run_id=run_id,
                settings=self._get_settings(),
            )
            self._worker.progress_update.connect(self._on_progress)
            self._worker.result_ready.connect(self._append_live_result)
            self._worker.analysis_complete.connect(self._on_analysis_complete)
            self._worker.error.connect(self._on_analysis_error)
            self._worker.start()

    # ------------------------------------------------------------------
    # Growth reports (Issue 18)
    # ------------------------------------------------------------------

    def _generate_growth_reports(
        self, course_id: str, course_name: str, container_lo: QVBoxLayout
    ) -> None:
        """Launch growth report generation in a worker thread."""
        from insights.llm_backend import auto_detect_backend
        from settings import load_settings as _ls

        _s = _ls()
        backend = auto_detect_backend(
            tier=_s.get("insights_model_tier", "auto"), settings=_s
        )
        if not backend:
            self._show_toast("No LLM backend available for report generation.")
            return

        # Add progress label to container
        progress_lbl = QLabel("Generating reports...")
        progress_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-style: italic; background: transparent; border: none;"
        )
        container_lo.addWidget(progress_lbl)

        # Run in background thread
        from concurrent.futures import ThreadPoolExecutor

        def _run():
            from insights.trajectory_report import generate_course_trajectory_reports

            def _progress(name, idx, total):
                progress_lbl.setText(
                    f"Generating report {idx}/{total}: {name}..."
                )

            return generate_course_trajectory_reports(
                backend=backend,
                store=self._store,
                course_id=course_id,
                course_name=course_name,
                progress_callback=_progress,
            )

        def _done(future):
            try:
                reports = future.result()
                n = sum(1 for v in reports.values() if v)
                progress_lbl.setText(f"Generated {n} report(s).")
                self._show_toast(f"Generated {n} growth reports.")
                # Refresh semester view
                if self._current_run_id:
                    self._invalidate_layers("semester")
                    self._display_semester(self._current_run_id)
            except Exception as e:
                progress_lbl.setText(f"Error: {e}")

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_run)
        future.add_done_callback(_done)

    def _export_growth_reports(
        self, reports: dict, course_name: str, mode: str = "teacher"
    ) -> None:
        """Export growth reports as a single markdown file.

        mode="teacher": full report including Teacher Notes
        mode="student": strips Teacher Notes, uses second person
        """
        from PySide6.QtWidgets import QFileDialog

        suffix = "teacher_records" if mode == "teacher" else "student_reports"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Growth Reports",
            f"{course_name}_{suffix}.md",
            "Markdown (*.md)",
        )
        if not path:
            return

        lines = [f"# Growth Reports — {course_name}\n"]

        for sid, text in reports.items():
            if not text:
                continue
            if mode == "student":
                # Strip Teacher Notes section
                import re
                text = re.sub(
                    r"## Teacher Notes.*?(?=\n## |\Z)",
                    "", text, flags=re.DOTALL
                ).strip()
                # Convert third person to second person (basic)
                # The LLM should generate with second-person option; this is fallback
            lines.append(text)
            lines.append("\n---\n")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._show_toast(f"Exported {len(reports)} reports to {path}")
        except Exception as e:
            self._show_toast(f"Export failed: {e}")

    def _post_growth_reports_to_canvas(
        self, reports: dict, course_id: str, course_name: str
    ) -> None:
        """Create Canvas assignment and post reports as submission comments."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        # Dialog to confirm assignment creation
        dlg = QDialog(self)
        dlg.setWindowTitle("Post Growth Reports to Canvas")
        dlg.setMinimumWidth(450)
        dlg.setStyleSheet(f"background: {BG_VOID};")

        dlg_lo = QVBoxLayout(dlg)
        dlg_lo.setSpacing(SPACING_MD)

        dlg_lo.addWidget(make_section_label("POST GROWTH REPORTS"))
        dlg_lo.addWidget(make_h_rule())

        dlg_lo.addWidget(_muted_label(
            "This will create a Canvas assignment and post each student's "
            "growth report as a submission comment. Students will see their "
            "own report only. Teacher Notes are not included."
        ))

        # Assignment name field
        name_label = _field_label("Assignment Name")
        dlg_lo.addWidget(name_label)
        name_edit = QLineEdit()
        name_edit.setText("Semester Growth Reflection")
        name_edit.setStyleSheet(
            f"QLineEdit {{ background: {BG_INSET}; color: {PHOSPHOR_MID};"
            f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
            f" padding: 6px; font-size: {px(12)}px; }}"
        )
        dlg_lo.addWidget(name_edit)

        # Description field
        desc_label = _field_label("Assignment Description")
        dlg_lo.addWidget(desc_label)
        desc_edit = QTextEdit()
        desc_edit.setPlainText(
            "Your semester growth report. This narrative summarizes your "
            "intellectual journey across the semester — the themes you "
            "explored, the connections you made, and the strengths you "
            "developed. Please read it and respond with your own reflection."
        )
        desc_edit.setMaximumHeight(100)
        desc_edit.setStyleSheet(
            f"QTextEdit {{ background: {BG_INSET}; color: {PHOSPHOR_MID};"
            f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
            f" padding: 6px; font-size: {px(12)}px; }}"
        )
        dlg_lo.addWidget(desc_edit)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Create Assignment & Post"
        )
        make_run_button(buttons.button(QDialogButtonBox.StandardButton.Ok))
        make_secondary_button(
            buttons.button(QDialogButtonBox.StandardButton.Cancel)
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg_lo.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        assign_name = name_edit.text().strip() or "Semester Growth Reflection"
        assign_desc = desc_edit.toPlainText().strip()

        # Create assignment + post comments via Canvas API
        if not self._api:
            self._show_toast("No Canvas API configured.")
            return

        import re

        try:
            # Create assignment (no submission, no points)
            assign_data = self._api.create_assignment(
                course_id,
                name=assign_name,
                description=assign_desc,
                submission_types=["none"],
                points_possible=0,
                published=True,
            )
            assign_id = assign_data.get("id")
            if not assign_id:
                self._show_toast("Failed to create Canvas assignment.")
                return

            # Post each report as a submission comment
            posted = 0
            for sid, text in reports.items():
                if not text:
                    continue
                # Strip Teacher Notes for student-facing version
                student_text = re.sub(
                    r"## Teacher Notes.*?(?=\n## |\Z)",
                    "", text, flags=re.DOTALL
                ).strip()
                if not student_text:
                    continue
                try:
                    self._api.post_submission_comment(
                        course_id, assign_id, sid, student_text
                    )
                    posted += 1
                except Exception as e:
                    _log = logging.getLogger(__name__)
                    _log.warning(
                        "Failed to post report for %s: %s", sid, e
                    )

            self._show_toast(
                f"Created '{assign_name}' and posted {posted} reports."
            )
        except Exception as e:
            self._show_toast(f"Canvas posting failed: {e}")

    def cleanup(self) -> None:
        """Clean shutdown — call from MainWindow.closeEvent."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)

    def _load_run(self, run_id: str) -> None:
        """Load and display results for the given run."""
        if not run_id or not self._store:
            self._resume_btn.setVisible(False)
            self._export_btn.setVisible(False)
            return

        run = self._store.get_run(run_id)
        if not run:
            self._resume_btn.setVisible(False)
            self._export_btn.setVisible(False)
            return

        # Show resume button for partial runs, export for any run with codings
        is_complete = run.get("completed_at") is not None
        stages = run.get("stages_completed", [])
        has_codings = "coding" in stages if isinstance(stages, list) else False
        self._resume_btn.setVisible(not is_complete)
        self._export_btn.setVisible(has_codings)

        self._current_run_id = run_id
        self._loaded_layers = set()
        self._profile_mgr = None  # reset so _ensure_profile_mgr re-loads for this run

        # Show the layer content (not the placeholder)
        self._review_content_stack.setCurrentIndex(1)

        # Always load patterns (default layer)
        qa_json = run.get("quick_analysis")
        if qa_json:
            self._display_patterns(qa_json)
            self._loaded_layers.add("patterns")

        # Load the currently visible layer if it's not patterns
        current_mode = self._layer_toggle.mode
        if current_mode != "patterns":
            self._load_layer(current_mode)
        else:
            self._layer_stack.setCurrentIndex(0)
            self._layer_toggle.set_mode("patterns")

    def _on_layer_changed(self, mode: str) -> None:
        """Switch the layer content stack, lazily loading data."""
        layer_map = {
            "patterns": 0, "codings": 1, "themes": 2,
            "outliers": 3, "report": 4,
        }
        self._layer_stack.setCurrentIndex(layer_map.get(mode, 0))
        self._load_layer(mode)

    def _load_layer(self, mode: str) -> None:
        """Load data for the given layer if not already loaded for this run."""
        run_id = self._current_run_id
        if not run_id:
            return
        loaded = getattr(self, "_loaded_layers", set())
        if mode in loaded:
            return
        loaded.add(mode)
        self._loaded_layers = loaded

        if mode == "codings":
            self._display_codings(run_id)
        elif mode == "themes":
            self._display_themes(run_id)
        elif mode == "outliers":
            self._display_outliers(run_id)
        elif mode == "report":
            self._display_report(run_id)
        elif mode == "feedback":
            self._display_feedback(run_id)
        elif mode == "semester":
            self._display_semester(run_id)

    # ------------------------------------------------------------------
    # Semester trajectory view (Phase 5)
    # ------------------------------------------------------------------

    def _display_semester(self, run_id: str) -> None:
        """Populate the Semester layer with cross-run trajectory data."""
        if not self._store:
            return

        # Get course_id from current run
        run = self._store.get_run(run_id)
        if not run:
            return
        course_id = run.get("course_id", "")
        if not course_id:
            return

        # Compute trajectory
        from insights.trajectory import TrajectoryAnalyzer
        analyzer = TrajectoryAnalyzer(self._store)
        traj = analyzer.analyze_course_trajectory(course_id)

        # Clear and get layout
        lo = self._clear_scroll_layout(self._semester_scroll)

        if traj is None:
            empty = QLabel(
                "Need at least 2 completed runs for this course "
                "to show semester trajectory."
            )
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
                f" background: transparent; border: none; padding: 40px;"
            )
            lo.addWidget(empty)
            lo.addStretch()
            return

        # ── Summary card ──
        summary_pane = make_content_pane("semesterSummaryPane")
        s_lo = QVBoxLayout(summary_pane)
        s_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        s_lo.setSpacing(SPACING_SM)

        s_lo.addWidget(make_section_label("Semester Overview"))
        s_lo.addWidget(make_h_rule())

        header = QLabel(
            f"{traj.course_name}  |  {traj.run_count} runs  |  {traj.date_range}"
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        s_lo.addWidget(header)
        lo.addWidget(summary_pane)

        # ── Engagement trend sparkline ──
        if traj.engagement_trend:
            eng_pane = make_content_pane("semesterEngagementPane")
            e_lo = QVBoxLayout(eng_pane)
            e_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
            e_lo.setSpacing(SPACING_SM)

            e_lo.addWidget(make_section_label("Engagement Trend"))
            e_lo.addWidget(make_h_rule())

            # Word count trend using unicode block chars
            wc_row = QHBoxLayout()
            wc_row.setSpacing(SPACING_XS)
            vals = [m.avg_words for m in traj.engagement_trend]
            max_val = max(vals) if vals else 1
            for m in traj.engagement_trend:
                col = QVBoxLayout()
                col.setSpacing(2)

                # Bar (unicode block)
                bar_h = int((m.avg_words / max(max_val, 1)) * 5)
                blocks = "\u2588" * max(bar_h, 1)
                bar_lbl = QLabel(blocks)
                bar_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
                bar_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(14)}px;"
                    f" background: transparent; border: none;"
                )
                col.addWidget(bar_lbl)

                # Value
                val_lbl = QLabel(f"{m.avg_words:.0f}")
                val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                val_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
                    f" background: transparent; border: none;"
                )
                col.addWidget(val_lbl)

                # Label
                name_lbl = QLabel(m.label[:12])
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(8)}px;"
                    f" background: transparent; border: none;"
                )
                col.addWidget(name_lbl)
                wc_row.addLayout(col)

            wc_row.addStretch()
            e_lo.addLayout(wc_row)

            # Submission rate row
            rates = [m.submission_rate for m in traj.engagement_trend]
            if any(r < 1.0 for r in rates):
                rate_text = "  ".join(
                    f"{m.label[:8]}: {m.submission_rate:.0%}"
                    for m in traj.engagement_trend
                )
                rate_lbl = QLabel(f"Submission rates: {rate_text}")
                rate_lbl.setWordWrap(True)
                rate_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                e_lo.addWidget(rate_lbl)

            lo.addWidget(eng_pane)

        # ── Exhaustion trend (structural signal) ──
        if traj.exhaustion_trend:
            total_exhaustion = sum(
                m.late_count + m.short_count + m.silence_count
                for m in traj.exhaustion_trend
            )
            if total_exhaustion > 0:
                ex_pane = make_content_pane("semesterExhaustionPane")
                x_lo = QVBoxLayout(ex_pane)
                x_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
                x_lo.setSpacing(SPACING_SM)

                x_lo.addWidget(make_section_label("Exhaustion Indicators"))
                x_lo.addWidget(make_h_rule())

                # Check if trending up
                late_vals = [m.late_count for m in traj.exhaustion_trend]
                short_vals = [m.short_count for m in traj.exhaustion_trend]
                silence_vals = [m.silence_count for m in traj.exhaustion_trend]
                trending_up = (
                    len(late_vals) >= 3
                    and late_vals[-1] > late_vals[0]
                    and short_vals[-1] + silence_vals[-1] > short_vals[0] + silence_vals[0]
                )

                framing_color = ROSE_ACCENT if trending_up else PHOSPHOR_DIM
                framing = QLabel(
                    "Late submissions and short reflections are increasing \u2014 "
                    "this may be a structural signal about workload or timing."
                    if trending_up else
                    "No clear upward trend in exhaustion indicators."
                )
                framing.setWordWrap(True)
                framing.setStyleSheet(
                    f"color: {framing_color}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                x_lo.addWidget(framing)

                # Per-week breakdown
                for m in traj.exhaustion_trend:
                    if m.late_count + m.short_count + m.silence_count == 0:
                        continue
                    parts = []
                    if m.late_count:
                        parts.append(f"{m.late_count} late")
                    if m.short_count:
                        parts.append(f"{m.short_count} short")
                    if m.silence_count:
                        parts.append(f"{m.silence_count} missing")
                    row_lbl = QLabel(f"{m.label}:  {', '.join(parts)}")
                    row_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                        f" background: transparent; border: none;"
                    )
                    x_lo.addWidget(row_lbl)

                lo.addWidget(ex_pane)

        # ── Concern trend ──
        if traj.concern_trend and any(m.concern_count > 0 for m in traj.concern_trend):
            c_pane = make_content_pane("semesterConcernPane")
            c_lo = QVBoxLayout(c_pane)
            c_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
            c_lo.setSpacing(SPACING_SM)

            c_lo.addWidget(make_section_label("Concern Signals Over Time"))
            c_lo.addWidget(make_h_rule())

            for m in traj.concern_trend:
                if m.concern_count == 0:
                    continue
                types_str = f"  ({', '.join(m.concern_types)})" if m.concern_types else ""
                row_lbl = QLabel(f"{m.label}:  {m.concern_count} flag(s){types_str}")
                row_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                c_lo.addWidget(row_lbl)

            lo.addWidget(c_pane)

        # ── Theme evolution ──
        if traj.theme_evolution:
            t_pane = make_content_pane("semesterThemePane")
            t_lo = QVBoxLayout(t_pane)
            t_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
            t_lo.setSpacing(SPACING_SM)

            t_lo.addWidget(make_section_label("Theme Evolution"))
            t_lo.addWidget(make_h_rule())

            from gui.widgets.phosphor_chip import PhosphorChip

            # Group by status
            for status in ("recurring", "new", "fading", "one-time"):
                themes = [t for t in traj.theme_evolution if t.status == status]
                if not themes:
                    continue
                status_labels = {
                    "recurring": "Recurring themes",
                    "new": "Appeared this run",
                    "fading": "Fading themes",
                    "one-time": "One-time themes",
                }
                grp_lbl = QLabel(status_labels.get(status, status).upper())
                grp_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; font-weight: bold;"
                    f" letter-spacing: 1px; background: transparent; border: none;"
                    f" padding-top: 4px;"
                )
                t_lo.addWidget(grp_lbl)

                # Flow layout of chips + week indicators
                flow = QHBoxLayout()
                flow.setSpacing(SPACING_XS)
                for te in themes:
                    weeks_str = ",".join(str(w + 1) for w in te.weeks_present)
                    chip = PhosphorChip(
                        f"{te.theme_name} (wk {weeks_str})",
                        active=(status == "recurring"),
                        accent="amber",
                    )
                    flow.addWidget(chip)
                flow.addStretch()
                t_lo.addLayout(flow)

            lo.addWidget(t_pane)

        # ── Top readings ──
        if traj.top_readings:
            r_pane = make_content_pane("semesterReadingsPane")
            r_lo = QVBoxLayout(r_pane)
            r_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
            r_lo.setSpacing(SPACING_SM)

            r_lo.addWidget(make_section_label("Most-Engaging Readings"))
            r_lo.addWidget(make_h_rule())

            for i, rd in enumerate(traj.top_readings[:10]):
                ref_lbl = QLabel(
                    f"{i + 1}. {rd.reading}  \u2014  "
                    f"referenced {rd.times_referenced}x, "
                    f"avg {rd.avg_word_count:.0f} words"
                )
                ref_lbl.setWordWrap(True)
                ref_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                r_lo.addWidget(ref_lbl)

            lo.addWidget(r_pane)

        # ── Student trajectories ──
        if traj.student_trajectories:
            st_pane = make_content_pane("semesterStudentPane")
            st_lo = QVBoxLayout(st_pane)
            st_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
            st_lo.setSpacing(SPACING_SM)

            st_lo.addWidget(make_section_label("Student Trajectories"))
            st_lo.addWidget(make_h_rule())

            st_lo.addWidget(_muted_label(
                "Week-by-week status: "
                "\u25cf on time  "
                "\u25cf late  "
                "\u25cb missing  "
                "\u25c6 concern flagged"
            ))

            # Status dot color map
            dot_colors = {
                "on_time": TERM_GREEN,
                "late": AMBER_BTN,
                "missing": PHOSPHOR_DIM,
            }

            for arc in traj.student_trajectories:
                arc_row = QHBoxLayout()
                arc_row.setSpacing(SPACING_SM)

                # Student name (clickable — jumps to Student Work layer)
                name_lbl = QLabel(arc.student_name[:20])
                name_lbl.setFixedWidth(140)
                name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                name_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                    f" text-decoration: underline;"
                )
                _sid = arc.student_id
                name_lbl.mousePressEvent = (
                    lambda _, sid=_sid: self._navigate_to_student(sid)
                )
                arc_row.addWidget(name_lbl)

                # Status dots
                dots_parts = []
                for i, status in enumerate(arc.weekly_submission_status):
                    color = dot_colors.get(status, PHOSPHOR_DIM)
                    has_concern = (
                        i < len(arc.weekly_concern_flags)
                        and arc.weekly_concern_flags[i] > 0
                    )
                    if has_concern:
                        dots_parts.append(
                            f'<span style="color:{ROSE_ACCENT}">\u25c6</span>'
                        )
                    elif status == "missing":
                        dots_parts.append(
                            f'<span style="color:{color}">\u25cb</span>'
                        )
                    else:
                        dots_parts.append(
                            f'<span style="color:{color}">\u25cf</span>'
                        )

                dots_lbl = QLabel("  ".join(dots_parts))
                dots_lbl.setTextFormat(Qt.TextFormat.RichText)
                dots_lbl.setStyleSheet(
                    f"font-size: {px(14)}px; background: transparent; border: none;"
                )
                arc_row.addWidget(dots_lbl)

                # Trend label
                trend_colors = {
                    "improving": TERM_GREEN,
                    "declining": ROSE_ACCENT,
                    "steady": PHOSPHOR_DIM,
                    "irregular": AMBER_BTN,
                }
                trend_symbols = {
                    "improving": "\u2197",
                    "declining": "\u2198",
                    "steady": "\u2192",
                    "irregular": "\u223f",
                }
                trend_lbl = QLabel(
                    f"{trend_symbols.get(arc.trend, '')} {arc.trend}"
                )
                trend_lbl.setStyleSheet(
                    f"color: {trend_colors.get(arc.trend, PHOSPHOR_DIM)};"
                    f" font-size: {px(10)}px; background: transparent; border: none;"
                )
                arc_row.addWidget(trend_lbl)
                arc_row.addStretch()

                st_lo.addLayout(arc_row)

            lo.addWidget(st_pane)

        # ── Confidence & cross-validation ──
        if run_id:
            run_data = self._store.get_run(run_id)
            confidence = run_data.get("pipeline_confidence", {}) if run_data else {}
            if isinstance(confidence, dict) and confidence.get("overall"):
                cv_pane = make_content_pane("semesterConfidencePane")
                cv_lo = QVBoxLayout(cv_pane)
                cv_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
                cv_lo.setSpacing(SPACING_SM)

                cv_lo.addWidget(make_section_label("Pipeline Confidence"))
                cv_lo.addWidget(make_h_rule())

                overall = confidence.get("overall", 0)
                overall_lbl = QLabel(f"Overall: {overall:.0%}")
                overall_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
                    f" background: transparent; border: none;"
                )
                cv_lo.addWidget(overall_lbl)

                for key in ("data_quality", "coding_reliability", "theme_coherence"):
                    val = confidence.get(key, 0)
                    if val:
                        metric_lbl = QLabel(
                            f"  {key.replace('_', ' ').title()}: {val:.0%}"
                        )
                        metric_lbl.setStyleSheet(
                            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                            f" background: transparent; border: none;"
                        )
                        cv_lo.addWidget(metric_lbl)

                for note in confidence.get("concerns", []):
                    note_lbl = QLabel(f"\u26a0  {note}")
                    note_lbl.setWordWrap(True)
                    note_lbl.setStyleSheet(
                        f"color: {ROSE_ACCENT}; font-size: {px(11)}px;"
                        f" background: transparent; border: none;"
                    )
                    cv_lo.addWidget(note_lbl)

                lo.addWidget(cv_pane)

        # ── Growth Reports ── (Issue 18)
        gr_pane = make_content_pane("semesterGrowthPane")
        gr_lo = QVBoxLayout(gr_pane)
        gr_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        gr_lo.setSpacing(SPACING_SM)

        gr_lo.addWidget(make_section_label("STUDENT GROWTH REPORTS"))
        gr_lo.addWidget(make_h_rule())

        gr_lo.addWidget(_muted_label(
            "Generate a narrative trajectory report for each student, "
            "summarizing their intellectual growth across the semester. "
            "Reports can be exported as teacher records or shared with "
            "students."
        ))

        # Check for existing reports (list of dicts from store)
        existing_reports: dict = {}
        try:
            raw_reports = self._store.get_course_trajectory_reports(course_id) or []
            for rpt in raw_reports:
                sid = rpt.get("student_id", "")
                text = rpt.get("report_text", "")
                if sid and text:
                    existing_reports[sid] = text
        except Exception:
            pass

        if existing_reports:
            stale_note = _muted_label(
                f"{len(existing_reports)} report(s) already generated. "
                f"Generate again to update with latest data."
            )
            gr_lo.addWidget(stale_note)

        # Generate button + progress area
        gen_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Growth Reports")
        make_run_button(gen_btn)
        gen_btn.clicked.connect(
            lambda: self._generate_growth_reports(course_id, course_name, gr_lo)
        )
        gen_row.addWidget(gen_btn)
        gen_row.addStretch()

        # Export buttons (visible when reports exist)
        if existing_reports:
            export_teacher = QPushButton("Export All (Teacher)")
            make_secondary_button(export_teacher)
            export_teacher.clicked.connect(
                lambda: self._export_growth_reports(
                    existing_reports, course_name, mode="teacher"
                )
            )
            gen_row.addWidget(export_teacher)

            export_student = QPushButton("Export All (Student-Facing)")
            make_secondary_button(export_student)
            export_student.clicked.connect(
                lambda: self._export_growth_reports(
                    existing_reports, course_name, mode="student"
                )
            )
            gen_row.addWidget(export_student)

            canvas_btn = QPushButton("Post to Canvas")
            make_secondary_button(canvas_btn)
            canvas_btn.clicked.connect(
                lambda: self._post_growth_reports_to_canvas(
                    existing_reports, course_id, course_name
                )
            )
            gen_row.addWidget(canvas_btn)

        gr_lo.addLayout(gen_row)

        # Collapsible student report cards
        if existing_reports:
            for sid, report_text in existing_reports.items():
                if not report_text:
                    continue
                # Extract student name from first line
                first_line = report_text.split("\n")[0].strip()
                sname = first_line.lstrip("#").strip() if first_line else sid

                card = make_content_pane(f"growthCard_{sid}")
                card_lo = QVBoxLayout(card)
                card_lo.setContentsMargins(
                    SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM
                )
                card_lo.setSpacing(SPACING_XS)

                # Collapsed header (clickable)
                card_header = QHBoxLayout()
                expand_lbl = QLabel(f"\u25b8 {sname}")
                expand_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                expand_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                    f" font-weight: bold; background: transparent; border: none;"
                )
                card_header.addWidget(expand_lbl)

                # Staleness badge
                try:
                    staleness = self._store.get_trajectory_report_staleness(sid, course_id)
                    if staleness and staleness > 0:
                        stale_lbl = QLabel(f"new work since report · ↻ update")
                        stale_lbl.setStyleSheet(
                            f"color: {STATUS_WARN}; font-size: {px(10)}px;"
                            f" background: transparent; border: none;"
                        )
                        card_header.addWidget(stale_lbl)
                except Exception:
                    pass

                card_header.addStretch()

                # Per-student export button
                export_btn = QPushButton("⬇")
                export_btn.setFixedSize(24, 24)
                export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                export_btn.setToolTip("Export this student's report (parent-safe)")
                export_btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {PHOSPHOR_DIM};"
                    f" border: 1px solid {BORDER_DARK}; border-radius: 12px;"
                    f" font-size: {px(12)}px; }}"
                    f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; border-color: {BORDER_AMBER}; }}"
                )
                def _export_single(text=report_text, name=sname):
                    import re
                    from PySide6.QtWidgets import QFileDialog
                    clean = re.sub(r"## Teacher Notes.*", "", text, flags=re.DOTALL).strip()
                    path, _ = QFileDialog.getSaveFileName(
                        self, "Export Growth Report", f"{name}_growth_report.md", "Markdown (*.md)"
                    )
                    if path:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(clean)
                export_btn.clicked.connect(_export_single)
                card_header.addWidget(export_btn)

                card_lo.addLayout(card_header)

                # Report text (initially hidden)
                report_te = QTextEdit()
                report_te.setPlainText(report_text)
                report_te.setReadOnly(False)  # Editable by teacher
                report_te.setVisible(False)
                report_te.setMinimumHeight(200)
                report_te.setMaximumHeight(500)
                report_te.setStyleSheet(
                    f"QTextEdit {{ background: {BG_INSET};"
                    f" border: 1px solid {BORDER_DARK}; border-radius: 4px;"
                    f" color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" font-family: {MONO_FONT}; padding: 8px; }}"
                    f"QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
                )
                card_lo.addWidget(report_te)

                # Toggle expand/collapse
                def _toggle(te=report_te, lbl=expand_lbl, name=sname):
                    vis = not te.isVisible()
                    te.setVisible(vis)
                    lbl.setText(f"\u25be {name}" if vis else f"\u25b8 {name}")

                expand_lbl.mousePressEvent = lambda _, fn=_toggle: fn()

                gr_lo.addWidget(card)

        lo.addWidget(gr_pane)

        lo.addStretch()
