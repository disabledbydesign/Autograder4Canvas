"""
Bulk Run page/dialog: select multiple courses, configure scope and options,
then run Preview Run or Run & Post Grades across all selected courses.
"""
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QCheckBox, QTextEdit,
    QProgressBar, QSizePolicy, QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette, QFont, QPainter, QPainterPath, QRadialGradient

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD,
    LEFT_PANEL_MIN, LEFT_PANEL_PREF,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    AMBER_BTN,
    make_run_button, make_secondary_button, make_monospace_textedit,
    make_section_label, make_h_rule, make_content_pane,
    GripSplitter,
)
from gui.widgets.phosphor_chip import PhosphorChip
from gui.widgets.switch_toggle import SwitchToggle
from gui.widgets.option_rocker import OptionRocker
from gui.widgets.segmented_toggle import SegmentedToggle
from gui.widgets.status_pip import draw_pip

# ---------------------------------------------------------------------------
# Modality display
# ---------------------------------------------------------------------------

_FORMAT_TAGS = {
    "on_campus": ("IP",  "#7DAB72"),
    "online":    ("OL",  "#5BA8C9"),
    "blended":   ("HY",  "#C97AB8"),
    "hybrid":    ("HY",  "#C97AB8"),
}

# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_SCROLL_QSS = f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}
"""

_CB_QSS = f"""
    QCheckBox {{
        color: {PHOSPHOR_MID};
        font-size: {px(12)}px;
        background: transparent;
        spacing: 6px;
    }}
    QCheckBox:hover {{ color: {PHOSPHOR_HOT}; }}
    QCheckBox::indicator {{
        width: 13px; height: 13px;
        border: 1px solid {BORDER_AMBER};
        border-radius: 3px;
        background: {BG_INSET};
    }}
    QCheckBox::indicator:checked {{
        background: {AMBER_BTN};
        border-color: {PHOSPHOR_HOT};
    }}
"""

_SCOPE_CB_QSS = f"""
    QCheckBox {{
        color: {PHOSPHOR_MID};
        font-size: {px(12)}px;
        background: transparent;
        spacing: 8px;
        padding: 4px 0;
    }}
    QCheckBox:hover {{ color: {PHOSPHOR_HOT}; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid {BORDER_AMBER};
        border-radius: 3px;
        background: {BG_INSET};
    }}
    QCheckBox::indicator:checked {{
        background: {AMBER_BTN};
        border-color: {PHOSPHOR_HOT};
    }}
"""

# Indented sub-option style (child of a parent scope checkbox)
_INDENT_CB_QSS = f"""
    QCheckBox {{
        color: {PHOSPHOR_MID};
        font-size: {px(12)}px;
        background: transparent;
        spacing: 8px;
        padding-left: 22px;
    }}
    QCheckBox:hover {{ color: {PHOSPHOR_HOT}; }}
    QCheckBox:disabled {{ color: {PHOSPHOR_DIM}; }}
    QCheckBox::indicator {{
        width: 13px; height: 13px;
        border: 1px solid {BORDER_AMBER};
        border-radius: 3px;
        background: {BG_INSET};
    }}
    QCheckBox::indicator:checked {{
        background: {AMBER_BTN};
        border-color: {PHOSPHOR_HOT};
    }}
    QCheckBox::indicator:disabled {{
        border-color: {BORDER_DARK};
        background: {BG_INSET};
    }}
"""

_PILL_QSS = f"""
    QPushButton {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.90,
            stop:0.00 #241A07,stop:0.60 #181205,stop:1.00 #111003);
        color: {PHOSPHOR_DIM};
        border: 1px solid rgba(90,60,8,0.55);
        border-radius: 12px;
        padding: 3px 14px;
        font-size: {px(12)}px;
        min-height: 24px;
    }}
    QPushButton:hover:!checked {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.90,
            stop:0.00 #352808,stop:0.60 #201808,stop:1.00 #151204);
        border-color: {BORDER_AMBER};
        color: {PHOSPHOR_MID};
    }}
    QPushButton:checked {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.90,
            stop:0.00 #4A3009,stop:0.55 #2A1C06,stop:1.00 #151004);
        color: {PHOSPHOR_HOT};
        border: 1px solid rgba(106,74,18,0.85);
        font-weight: 600;
    }}
    QPushButton:pressed {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.90,
            stop:0.00 #161205,stop:0.60 #111003,stop:1.00 #0D0B02);
        border-color: rgba(90,60,8,0.35);
        color: {PHOSPHOR_HOT};
    }}
"""


# ---------------------------------------------------------------------------
# PipCheckRow — checkbox-semantics row with pip indicator + radial row glow
# ---------------------------------------------------------------------------

class PipCheckRow(QWidget):
    """A QCheckBox replacement that draws a phosphor pip and glow background.

    Exposes the same interface as QCheckBox:
      isChecked / setChecked / blockSignals / setEnabled / toggled signal
    """

    toggled = Signal(bool)

    def __init__(self, label: str, indent: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self._indent  = indent
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Hidden real QCheckBox: owns the checked state and enabled logic.
        # Indicator is zeroed out — pip is drawn in our paintEvent instead.
        self._cb = QCheckBox(label)
        self._cb.setStyleSheet(
            "QCheckBox { spacing: 8px; background: transparent; border: none;"
            f" color: {PHOSPHOR_MID}; font-size: {px(12)}px; }}"
            "QCheckBox::indicator { width: 0px; height: 0px; border: none; }"
        )
        self._cb.toggled.connect(self.toggled)          # forward signal
        self._cb.toggled.connect(lambda _: self.update())

        lo = QHBoxLayout(self)
        left_pad = 20 if indent else 6
        lo.setContentsMargins(left_pad, 3, 8, 3)
        lo.setSpacing(0)
        lo.addWidget(self._cb)

    # ── State delegation ─────────────────────────────────────────────────
    def isChecked(self) -> bool:
        return self._cb.isChecked()

    def setChecked(self, v: bool) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(v)
        self._cb.blockSignals(False)
        self.update()

    def blockSignals(self, b: bool) -> bool:
        self._cb.blockSignals(b)
        return super().blockSignals(b)

    def setEnabled(self, v: bool) -> None:
        super().setEnabled(v)
        self._cb.setEnabled(v)
        self.update()

    def isEnabled(self) -> bool:
        return super().isEnabled()

    def setToolTip(self, text: str) -> None:
        super().setToolTip(text)
        self._cb.setToolTip(text)

    # ── Interaction ───────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._cb.setChecked(not self._cb.isChecked())
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        is_checked = self._cb.isChecked()
        is_enabled = self.isEnabled()
        is_hovered = self._hovered and is_enabled

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Pip x: centred in left margin (8 for non-indent, 12 for indent)
        pip_cx = 12.0 if self._indent else 8.0
        pip_cy = self.height() / 2.0

        if (is_checked or is_hovered) and is_enabled:
            glow_cx = self.width() * 0.35
            glow_cy = self.height() * 0.50

            center_col = QColor(240, 168, 48, 50 if is_checked else 28)
            bloom_col  = QColor(240, 168, 48, 22 if is_checked else 10)

            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)

            grad = QRadialGradient(glow_cx, glow_cy, self.width() * 0.80)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())
            p.restore()

            if is_checked:
                draw_pip(p, pip_cx, pip_cy, 5, 240, 168, 48,
                         bloom_alpha=45, core_alpha=190)
            else:
                draw_pip(p, pip_cx, pip_cy, 4, 240, 168, 48,
                         bloom_alpha=20, core_alpha=110)
        else:
            # Dim pip: checked=off, no hover
            if is_enabled:
                draw_pip(p, pip_cx, pip_cy, 4, 90, 60, 18,
                         bloom_alpha=0, core_alpha=75)
            else:
                draw_pip(p, pip_cx, pip_cy, 4, 58, 40, 8,
                         bloom_alpha=0, core_alpha=45)

        p.end()
        # Child QCheckBox label text is painted by Qt's child-widget system after
        # this returns — no super().paintEvent() call needed


# ---------------------------------------------------------------------------
# _CourseRow — two-line selectable course item (code on top, title below)
# ---------------------------------------------------------------------------

class _CourseRow(QWidget):
    toggled = Signal(int, bool)   # (course_id, checked)

    def __init__(self, course: dict, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._course = course
        cid  = course.get("id", 0)
        code  = course.get("code") or course.get("name", "")
        title = course.get("nickname") or course.get("title") or ""
        fmt   = (course.get("format") or "").lower()

        # Flat horizontal row: [CB(hidden)] [pip space] [pill] [VStack: code / title]
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 5)
        outer.setSpacing(0)

        # Hidden checkbox: state manager only — indicator drawn in paintEvent
        self._cb = QCheckBox()
        self._cb.setStyleSheet(
            "QCheckBox { spacing: 0; background: transparent; border: none; }"
            "QCheckBox::indicator { width: 0px; height: 0px; border: none; }"
        )
        self._cb.toggled.connect(lambda v: self.toggled.emit(cid, v))
        self._cb.toggled.connect(lambda _: self.update())
        outer.addWidget(self._cb)
        outer.addSpacing(18)   # room for pip (drawn at x≈8) + gap

        # Modality pill (fixed slot — courses without one get equivalent spacing)
        tag_info = _FORMAT_TAGS.get(fmt)
        _PILL_W = 26
        if tag_info:
            tag_label, tag_color = tag_info
            pill = QLabel(tag_label)
            pill.setFixedSize(_PILL_W, 16)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                f"color: {tag_color}; font-size: {px(9)}px; font-weight: bold;"
                f" border: 1px solid {tag_color}; border-radius: 3px;"
                f" background: transparent;"
            )
            outer.addWidget(pill)
        else:
            outer.addSpacing(_PILL_W)   # keep code column aligned across all rows
        outer.addSpacing(7)

        # Right text stack: code on top, title below
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)

        code_lbl = QLabel(code)
        code_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        text.addWidget(code_lbl)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            text.addWidget(title_lbl)

        outer.addLayout(text, 1)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def course_id(self) -> int:
        return self._course.get("id", 0)

    def fmt(self) -> str:
        return (self._course.get("format") or "").lower()

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, v: bool) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(v)
        self._cb.blockSignals(False)
        self.toggled.emit(self.course_id(), v)
        self.update()

    def mousePressEvent(self, event):
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

            # Void base (opaque — prevents transparent stylesheet from bleeding through)
            p.fillRect(self.rect(), QColor("#0A0800"))

            # Left-biased radial glow
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

            # Pip
            pip_cx = 10.0
            pip_cy = self.height() / 2.0
            if is_checked:
                draw_pip(p, pip_cx, pip_cy, 10, 204, 82, 130,
                         bloom_alpha=55, core_alpha=200)
            else:
                draw_pip(p, pip_cx, pip_cy, 8, 240, 168, 48,
                         bloom_alpha=28, core_alpha=130)
            p.end()
            # Do NOT call super() — that would repaint transparent background over our gradient
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# _TermSection — collapsible term header + course rows
# ---------------------------------------------------------------------------

class _TermSection(QWidget):
    def __init__(self, term_name: str, is_current: bool, parent=None):
        super().__init__(parent)
        self._term_name = term_name.upper()
        self._is_current = is_current
        self._collapsed = not is_current   # past terms start collapsed

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Clickable header
        self._hdr_btn = QPushButton()
        self._hdr_btn.setFlat(True)
        self._hdr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr_btn.clicked.connect(self._toggle)
        self._hdr_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {PHOSPHOR_HOT if is_current else PHOSPHOR_DIM};"
            f"  font-size: {px(10)}px; font-weight: bold; letter-spacing: 1px;"
            f"  background: transparent; border: none;"
            f"  text-align: left; padding: 8px 8px 3px 8px;"
            f"}}"
            f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
        )
        lo.addWidget(self._hdr_btn)

        # Container for course rows
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_lo = QVBoxLayout(self._container)
        self._container_lo.setContentsMargins(0, 0, 0, 4)
        self._container_lo.setSpacing(2)
        lo.addWidget(self._container)

        self._refresh_header()
        self._container.setVisible(not self._collapsed)

    def add_course_row(self, row: _CourseRow) -> None:
        self._container_lo.addWidget(row)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._container.setVisible(not self._collapsed)
        self._refresh_header()

    def _refresh_header(self) -> None:
        arrow = "v" if not self._collapsed else ">"
        dot   = "  ●" if self._is_current else ""
        self._hdr_btn.setText(f"{arrow}  {self._term_name}{dot}")


# ---------------------------------------------------------------------------
# BulkRunPage  (embeddable QWidget — used inline in the main window)
# ---------------------------------------------------------------------------

class BulkRunPage(QWidget):
    """Bulk run UI as an inline page (no dialog chrome)."""

    def __init__(self, api, demo_mode: bool = False, parent=None):
        super().__init__(parent)
        self._api = api
        self._demo_mode = demo_mode
        self._courses_by_term: list = []
        self._worker = None
        self._course_rows: List[_CourseRow] = []
        self._qs_btns: dict = {}
        self._course_scroll: QScrollArea = None  # set in _build_course_pane
        self._setup_ui()
        self._update_run_buttons()

    def refresh_courses(self, courses_by_term: list) -> None:
        """Rebuild the course list — call this each time the page becomes visible."""
        self._courses_by_term = courses_by_term
        self._course_rows.clear()
        if hasattr(self, "_mapping_panel"):
            self._mapping_panel.clear()

        content = QWidget()
        content.setStyleSheet(f"background: {BG_INSET};")
        content_lo = QVBoxLayout(content)
        content_lo.setContentsMargins(0, 2, 0, 4)
        content_lo.setSpacing(0)

        for term_id, term_name, is_current, courses in courses_by_term:
            section = _TermSection(term_name, is_current)
            for course in courses:
                row = _CourseRow(course)
                row.toggled.connect(self._on_course_toggled)
                self._course_rows.append(row)
                section.add_course_row(row)
            content_lo.addWidget(section)

        content_lo.addStretch()
        if self._course_scroll is not None:
            self._course_scroll.setWidget(content)

        self._update_qs_buttons()
        self._update_run_buttons()

        # Kick off a background preload of all assignment groups so they're
        # ready in the cache before the user starts checking courses.
        if hasattr(self, "_mapping_panel"):
            all_courses = [
                (c["id"], c["name"])
                for _, _, _, courses in courses_by_term
                for c in courses
            ]
            self._mapping_panel.preload_groups(all_courses)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(SPACING_MD)

        # Title
        title = QLabel("BULK RUN")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        sub = QLabel(
            "Select courses and configure the grading run. "
            "Applies to all autogradeable assignments matching the chosen scope."
        )
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(sub)

        sep = self._hsep()
        outer.addWidget(sep)

        # Main three-pane row: courses | mappings | config
        from gui.panels.mapping_panel import MappingPanel
        self._mapping_panel = MappingPanel(api=self._api)

        self._pane_splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        self._pane_splitter.setHandleWidth(10)
        self._pane_splitter.addWidget(self._build_course_pane())
        self._pane_splitter.addWidget(self._mapping_panel)
        self._pane_splitter.addWidget(self._build_config_pane())
        self._pane_splitter.setStretchFactor(0, 0)
        self._pane_splitter.setStretchFactor(1, 1)
        self._pane_splitter.setStretchFactor(2, 0)
        self._pane_splitter.setSizes([LEFT_PANEL_PREF, 400, 300])
        outer.addWidget(self._pane_splitter, 1)

        sep2 = self._hsep()
        outer.addWidget(sep2)

        # Footer: status label + action buttons
        footer = QHBoxLayout()
        self._status_lbl = QLabel("No courses selected")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;"
        )
        footer.addWidget(self._status_lbl)
        footer.addStretch()

        self._preview_btn = QPushButton("⊙  Preview Run")
        self._preview_btn.setToolTip(
            "Run grading logic and integrity check across selected courses,\n"
            "but do NOT post any grades to Canvas. Review the output first."
        )
        self._preview_btn.clicked.connect(lambda: self._on_run(dry_run=True))
        make_secondary_button(self._preview_btn)
        footer.addWidget(self._preview_btn)

        self._run_btn = QPushButton("▶  Run Autograder")
        self._run_btn.clicked.connect(lambda: self._on_run(dry_run=False))
        make_run_button(self._run_btn)
        footer.addWidget(self._run_btn)

        outer.addLayout(footer)

    def _build_course_pane(self) -> QFrame:
        pane = make_content_pane("bulkPane")
        pane.setMinimumWidth(LEFT_PANEL_MIN)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label("Select Courses"))

        # Quick-select — PhosphorChip filter chips
        def _qs_btn(label, fmt):
            btn = PhosphorChip(label, accent="amber")
            btn.toggled.connect(lambda _, f=fmt: self._quick_select(f))
            self._qs_btns[fmt] = (btn, label)
            return btn

        qs_row = QHBoxLayout()
        qs_row.setSpacing(4)
        for label, fmt in [("All", None), ("In Person", "on_campus"), ("Online", "online"), ("Hybrid", "blended")]:
            qs_row.addWidget(_qs_btn(label, fmt))
        qs_row.addStretch()
        lo.addLayout(qs_row)

        lo.addWidget(self._hsep())

        # Scrollable course list with collapsible term sections
        scroll = QScrollArea()
        scroll.setObjectName("bulkCourseScroll")
        scroll.setStyleSheet(_SCROLL_QSS)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._course_scroll = scroll   # stored so refresh_courses() can update it

        # Empty placeholder — refresh_courses() populates this
        placeholder = QWidget()
        placeholder.setStyleSheet(f"background: {BG_INSET};")
        scroll.setWidget(placeholder)
        lo.addWidget(scroll, 1)

        return pane

    def _build_config_pane(self) -> QFrame:
        pane = make_content_pane("bulkConfigPane")
        pane.setMinimumWidth(260)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(20, 20, 20, 20)
        lo.setSpacing(SPACING_SM)

        # ── Scope section ────────────────────────────────────────────────
        lo.addWidget(make_section_label("Scope"))
        lo.addSpacing(4)

        self._scope_last_week = SwitchToggle("Due last week only", wrap_width=160)
        self._scope_last_week.setChecked(True)
        self._scope_last_week.setToolTip(
            "Include assignments whose deadline fell within the last 7 days."
        )
        self._scope_last_week.toggled.connect(self._on_last_week_toggled)
        lo.addWidget(self._scope_last_week)

        self._scope_past_due = SwitchToggle("All past-due assignments", wrap_width=160)
        self._scope_past_due.setToolTip(
            "Expand scope to all past-due assignments — includes last week and earlier."
        )
        self._scope_past_due.toggled.connect(self._on_past_due_toggled)
        indent_row = QHBoxLayout()
        indent_row.setContentsMargins(20, 0, 0, 0)
        indent_row.addWidget(self._scope_past_due)
        lo.addLayout(indent_row)

        self._scope_submitted = SwitchToggle("Ungraded submissions", wrap_width=160)
        self._scope_submitted.setToolTip(
            "Include assignments that have ungraded student submissions,\n"
            "regardless of deadline."
        )
        self._scope_submitted.toggled.connect(lambda _: self._update_run_buttons())
        lo.addWidget(self._scope_submitted)

        lo.addWidget(self._hsep())

        # ── Options section ──────────────────────────────────────────────
        lo.addWidget(make_section_label("Options"))
        lo.addSpacing(4)

        self._opt_mark_incomplete = OptionRocker(
            "Mark absent\nwork as Incomplete",
            "Leave absent\nwork ungraded",
            value=False,
        )
        self._opt_mark_incomplete.setToolTip(
            "Grade as Incomplete: assign Incomplete to students who never submitted.\n"
            "Leave ungraded: skip absent students — do not post a grade."
        )
        lo.addWidget(self._opt_mark_incomplete)

        lo.addSpacing(6)

        self._opt_preserve = OptionRocker(
            "Grade new\nsubmissions only",
            "Regrade\nfrom scratch",
            value=True,
        )
        self._opt_preserve.setToolTip(
            "New submissions only: grade work Canvas marks as ungraded.\n"
            "Regrade from scratch: overwrite all grades as if none had been posted."
        )
        lo.addWidget(self._opt_preserve)

        lo.addWidget(self._hsep())
        lo.addWidget(make_section_label("Engagement Analysis"))
        lo.addSpacing(4)

        self._opt_run_aic = SegmentedToggle(
            ("Grade",         "grade_only"),
            ("Grade + AIC",   "grade_and_aic"),
            ("AIC",           "aic_only"),
            accent="rose",
        )
        self._opt_run_aic.setToolTip(
            "Grade only: skip the academic integrity check.\n"
            "Grade + AIC: grade and run the integrity check.\n"
            "AIC only: run the integrity check without posting grades."
        )
        lo.addWidget(self._opt_run_aic)

        # Restore persisted defaults
        try:
            from settings import load_settings
            s = load_settings()
            self._opt_run_aic.set_mode(s.get("aic_mode_default", "grade_and_aic"))
            self._opt_mark_incomplete.setChecked(
                bool(s.get("grade_missing_as_incomplete", False))
            )
            self._opt_preserve.setChecked(
                bool(s.get("preserve_existing_grades", True))
            )
        except Exception:
            pass

        lo.addStretch()
        return pane

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hsep() -> QFrame:
        return make_h_rule()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _quick_select(self, fmt) -> None:
        # Normalise: "blended" and "hybrid" are equivalent
        _aliases = {"blended": {"blended", "hybrid"}, "hybrid": {"blended", "hybrid"}}

        if fmt == "__clear__":
            for row in self._course_rows:
                row.set_checked(False)
            return

        # Determine which rows are in scope
        if fmt is None:  # "All"
            target_rows = self._course_rows
        else:
            match_fmts = _aliases.get(fmt, {fmt})
            target_rows = [r for r in self._course_rows if r.fmt() in match_fmts]

        # Toggle: if all targets are already checked, uncheck; otherwise check all
        all_checked = target_rows and all(r.is_checked() for r in target_rows)
        for row in target_rows:
            row.set_checked(not all_checked)
        self._update_qs_buttons()
        self._update_run_buttons()

    def _on_course_toggled(self, course_id: int, checked: bool) -> None:
        # Forward to mapping panel so it can load/unload group rows
        row = next((r for r in self._course_rows if r.course_id() == course_id), None)
        if row is not None and hasattr(self, "_mapping_panel"):
            course_name = row._course.get("name", "")
            self._mapping_panel.on_course_toggled(
                course_id, course_name, checked, self._api
            )
        self._update_qs_buttons()
        self._update_run_buttons()

    def _update_qs_buttons(self) -> None:
        """Sync active state of quick-select chips to actual row selection."""
        _aliases = {"blended": {"blended", "hybrid"}}
        for fmt, (btn, label) in self._qs_btns.items():
            if fmt is None:
                target = self._course_rows
            else:
                match_fmts = _aliases.get(fmt, {fmt})
                target = [r for r in self._course_rows if r.fmt() in match_fmts]
            all_on = bool(target) and all(r.is_checked() for r in target)
            btn.blockSignals(True)
            btn.setChecked(all_on)
            btn.blockSignals(False)

    def _on_last_week_toggled(self, checked: bool) -> None:
        if not checked:
            # Unchecking "last week" also clears the broader "all past-due"
            self._scope_past_due.blockSignals(True)
            self._scope_past_due.setChecked(False)
            self._scope_past_due.blockSignals(False)
        self._update_run_buttons()

    def _on_past_due_toggled(self, checked: bool) -> None:
        if checked:
            # Checking "all past-due" pulls "last week only" along with it
            self._scope_last_week.blockSignals(True)
            self._scope_last_week.setChecked(True)
            self._scope_last_week.blockSignals(False)
        self._update_run_buttons()

    def _update_run_buttons(self) -> None:
        n_courses = sum(1 for r in self._course_rows if r.is_checked())
        scope_ok = (self._scope_last_week.isChecked()
                    or self._scope_submitted.isChecked())
        enabled = n_courses > 0 and scope_ok
        self._run_btn.setEnabled(enabled)
        self._preview_btn.setEnabled(enabled)

        if n_courses == 0:
            self._status_lbl.setText("No courses selected")
        elif not scope_ok:
            self._status_lbl.setText(f"{n_courses} course(s) selected — choose at least one scope")
        else:
            self._status_lbl.setText(f"{n_courses} course(s) selected")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self, dry_run: bool) -> None:
        selected_courses = [
            (r.course_id(),
             r._course.get("name", ""),
             r._course.get("term_id", 0))
            for r in self._course_rows if r.is_checked()
        ]
        if not selected_courses:
            return

        if not self._api:
            if self._demo_mode:
                from gui.workers import DemoRunWorker
                all_assignments = [
                    a
                    for groups in self._mapping_panel._groups_cache.values()
                    for g in groups
                    for a in g.get("assignments", [])
                ]
                self._worker = DemoRunWorker(selected_items=all_assignments)
                self._run_btn.setEnabled(False)
                self._preview_btn.setEnabled(False)
                self._worker.finished.connect(lambda _s, _m: self._update_run_buttons())
                self._progress_window = BulkProgressWindow(
                    worker=self._worker,
                    dry_run=dry_run,
                    n_courses=len(selected_courses),
                    parent=self.window(),
                )
                self._worker.start()
                self._progress_window.show()
            return

        # "Due last week only" = any past-due scope is active
        # "All past-due" (child) = expand beyond last 7 days to all time
        scope = {
            "past_due":       self._scope_last_week.isChecked(),
            "submitted":      self._scope_submitted.isChecked(),
            "last_week_only": self._scope_last_week.isChecked()
                              and not self._scope_past_due.isChecked(),
        }
        options = {
            "run_aic":              self._opt_run_aic.mode != "grade_only",
            "preserve_grades":      self._opt_preserve.isChecked(),
            "mark_incomplete":      self._opt_mark_incomplete.isChecked(),
            "min_word_count":       200,
            "post_min_words":       200,
            "reply_min_words":      50,
        }

        group_overrides = {}
        if hasattr(self, "_mapping_panel"):
            group_overrides = self._mapping_panel.get_group_overrides()

        from gui.workers import BulkRunWorker
        self._worker = BulkRunWorker(
            api=self._api,
            course_entries=selected_courses,
            scope=scope,
            options=options,
            dry_run=dry_run,
            group_overrides=group_overrides,
        )

        self._run_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._worker.finished.connect(lambda _s, _m: self._update_run_buttons())

        self._progress_window = BulkProgressWindow(
            worker=self._worker,
            dry_run=dry_run,
            n_courses=len(selected_courses),
            parent=self.window(),
        )
        self._worker.start()
        self._progress_window.show()


# ---------------------------------------------------------------------------
# BulkProgressWindow — detached window, same chrome as RunDialog progress page
# ---------------------------------------------------------------------------

class BulkProgressWindow(QDialog):
    """Detached progress window for bulk grading runs.

    Uses _PhosphorProgressBar from run_dialog — one source of truth.
    """

    def __init__(self, worker, dry_run: bool, n_courses: int, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._n_courses = n_courses
        mode_label = "PREVIEW RUN" if dry_run else "LIVE RUN — grades WILL be posted"
        self.setWindowTitle(f"{'Preview' if dry_run else 'Live'} Run — {n_courses} course(s)")
        self.setMinimumWidth(560)
        self.resize(660, 520)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")

        self._setup_ui(mode_label, n_courses)

        worker.log_line.connect(self._append_log)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)

    def _setup_ui(self, mode_label: str, n_courses: int) -> None:
        from gui.dialogs.run_dialog import _PhosphorProgressBar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        self._heading = QLabel(mode_label)
        self._heading.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        layout.addWidget(self._heading)

        self._status_lbl = QLabel("Starting…")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        layout.addWidget(self._status_lbl)

        self._progress_bar = _PhosphorProgressBar()
        self._progress_bar.setMaximum(n_courses)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat(f"{mode_label}  %v / %m courses")
        layout.addWidget(self._progress_bar)

        log_pane = make_content_pane("bulkProgressLogPane")
        log_inner = QVBoxLayout(log_pane)
        log_inner.setContentsMargins(4, 4, 4, 4)
        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        make_monospace_textedit(self._log_output)
        self._log_output.setMinimumHeight(240)
        log_inner.addWidget(self._log_output)
        layout.addWidget(log_pane, 1)

        layout.addWidget(make_h_rule())

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.setSpacing(10)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        self._open_btn = QPushButton("Open Output")
        self._open_btn.clicked.connect(self._on_open_output)
        btn_row.addWidget(self._open_btn)

        btn_row.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    def _append_log(self, line: str) -> None:
        self._log_output.append(line)
        sb = self._log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

        # Parse student-level progress from log for finer bar granularity
        import re
        m = re.search(r'(\d+)/(\d+)\s+student', line)
        if m:
            sub_done = int(m.group(1))
            sub_total = int(m.group(2))
            course_done = getattr(self, "_course_done", 0)
            course_total = getattr(self, "_course_total", 1)
            if course_total > 0 and sub_total > 0:
                slice_pct = 100.0 / course_total
                base = course_done * slice_pct
                sub_pct = sub_done / sub_total
                overall = int(base + sub_pct * slice_pct)
                self._progress_bar.setValue(min(overall, 99))

    def _on_progress(self, done: int, total: int) -> None:
        # Track course-level progress for the overall bar
        self._course_done = done
        self._course_total = total
        # Update bar: each course gets an equal slice, student progress fills within
        course_pct = int(done / total * 100) if total > 0 else 0
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(min(course_pct, 99))
        self._status_lbl.setText(
            f"Course {done} of {total} complete…" if done < total else "Finishing up…"
        )

    def _on_finished(self, success: bool, message: str) -> None:
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        icon = "Done" if success else "Error"
        self._append_log(f"\n[{icon}] {message}")
        self._heading.setText("COMPLETE" if success else "ERROR")
        if success:
            self._progress_bar.setValue(100)
        try:
            from settings import load_settings
            from autograder_utils import open_folder, get_output_base_dir
            s = load_settings()
            if s.get("auto_open_folder"):
                open_folder(get_output_base_dir())
        except Exception:
            pass

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("\n[Stopped] Cancellation requested.")
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

    def _on_open_output(self) -> None:
        try:
            from autograder_utils import open_folder, get_output_base_dir
            open_folder(get_output_base_dir())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# BulkRunDialog  (thin modal wrapper around BulkRunPage — kept for compat)
# ---------------------------------------------------------------------------

class BulkRunDialog(QDialog):
    """Modal wrapper around BulkRunPage — kept for any external callers."""

    def __init__(self, api, courses_by_term: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Run")
        self.setMinimumSize(810, 520)
        self.resize(910, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._page = BulkRunPage(api=api, parent=self)
        self._page.refresh_courses(courses_by_term)
        layout.addWidget(self._page)
