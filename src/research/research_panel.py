"""
Research comparison panel — 3-way classification side-by-side display.

Launched from scripts/launch_research.py only (not the main GUI).
Left sidebar: course/assignment selector + controls.
Right pane: summary table + per-student 3-column comparison cards.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles import (
    BORDER_AMBER,
    BORDER_DARK,
    BG_CARD,
    BG_INSET,
    BG_PANEL,
    BG_VOID,
    BURN_RED,
    PHOSPHOR_DIM,
    PHOSPHOR_GLOW,
    PHOSPHOR_HOT,
    PHOSPHOR_MID,
    PANE_BG_GRADIENT,
    ROSE_ACCENT,
    ROSE_DIM,
    TERM_GREEN,
    make_content_pane,
    make_h_rule,
    make_run_button,
    make_secondary_button,
    make_section_label,
    px,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pill colors by axis value
# ---------------------------------------------------------------------------
_PILL_COLOR = {
    "FLAG":     BURN_RED,
    "CRISIS":   BURN_RED,
    "BURNOUT":  "#D87020",
    "ENGAGED":  TERM_GREEN,
    "NONE":     PHOSPHOR_DIM,
    "CLEAR":    PHOSPHOR_DIM,
    "CHECK-IN": ROSE_ACCENT,
}


def _axis_pill(text: str) -> QLabel:
    color = _PILL_COLOR.get(text.upper(), PHOSPHOR_DIM)
    lbl = QLabel(text.upper())
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color: {color}; font-size: {px(10)}px; font-weight: bold;"
        f" border: 1px solid {color}; border-radius: 3px;"
        f" background: transparent; padding: 1px 6px;"
    )
    lbl.setMaximumWidth(120)
    return lbl


def _dim_label(text: str, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(size)}px;"
        f" background: transparent; border: none;"
    )
    return lbl


def _mid_label(text: str, italic: bool = False, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    style = (
        f"color: {PHOSPHOR_MID}; font-size: {px(size)}px;"
        f" background: transparent; border: none;"
    )
    if italic:
        style += " font-style: italic;"
    lbl.setStyleSheet(style)
    return lbl


def _glow_label(text: str, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_GLOW}; font-size: {px(size)}px;"
        f" background: transparent; border: none; font-style: italic;"
    )
    return lbl


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        sub = item.layout()
        if sub:
            _clear_layout(sub)


# ---------------------------------------------------------------------------
# _ResearchAssignRow — single-select radio style
# ---------------------------------------------------------------------------

class _ResearchAssignRow(QWidget):
    selected = Signal(int, str)   # (assignment_id, assignment_name)

    def __init__(self, assignment: dict, parent=None):
        super().__init__(parent)
        self._assign = assignment
        self._selected = False
        self._hovered = False

        name = assignment.get("name", "Untitled")
        due  = assignment.get("due_at", "")
        if due:
            try:
                dt  = datetime.fromisoformat(due.replace("Z", "+00:00"))
                due = dt.strftime("%m/%d")
            except (ValueError, TypeError):
                due = ""

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 5, 8, 5)
        outer.setSpacing(6)
        outer.addSpacing(14)   # space for radio dot drawn in paintEvent

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)

        self._name_lbl = QLabel(name)
        self._name_lbl.setWordWrap(False)
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        text.addWidget(self._name_lbl)

        if due:
            due_lbl = QLabel(f"due {due}")
            due_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            text.addWidget(due_lbl)

        outer.addLayout(text, 1)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def assignment_id(self) -> int:
        return self._assign.get("id", 0)

    def assignment_name(self) -> str:
        return self._assign.get("name", "")

    def set_selected(self, v: bool) -> None:
        self._selected = v
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT if v else PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        self.update()

    def mousePressEvent(self, event):
        if not self._selected:
            self.selected.emit(self.assignment_id(), self.assignment_name())

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        is_sel = self._selected
        is_hov = self._hovered
        if is_sel or is_hov:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), QColor("#0A0800"))
            glow_cx = self.width() * 0.18
            glow_cy = self.height() * 0.50
            center_col = QColor(204, 82, 130, 60) if is_sel else QColor(240, 168, 48, 38)
            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            grad = QRadialGradient(glow_cx, glow_cy, self.width() * 0.80)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.7, QColor(center_col.red(), center_col.green(),
                                        center_col.blue(), 8))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())
            p.restore()
            dot_x, dot_y = 8.0, self.height() / 2.0
            p.setPen(Qt.PenStyle.NoPen)
            dot_color = QColor(ROSE_ACCENT) if is_sel else QColor(PHOSPHOR_DIM)
            p.setBrush(dot_color)
            p.drawEllipse(int(dot_x - 3), int(dot_y - 3), 6, 6)
            p.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# _OfflineRunRow — clickable row for DB-backed run browser (no Canvas)
# ---------------------------------------------------------------------------

class _OfflineRunRow(QWidget):
    selected = Signal(object)   # emits the run dict

    def __init__(self, run: dict, parent=None):
        super().__init__(parent)
        self._run      = run
        self._selected = False
        self._hovered  = False

        date_raw = run.get("completed_at") or run.get("started_at") or ""
        date_str = ""
        if date_raw:
            try:
                dt       = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                date_str = dt.strftime("%b %-d")
            except (ValueError, TypeError):
                date_str = date_raw[:10]

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 5, 8, 5)
        outer.setSpacing(6)
        outer.addSpacing(14)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)

        self._name_lbl = QLabel(run.get("assignment_name", "Untitled"))
        self._name_lbl.setWordWrap(True)
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        text.addWidget(self._name_lbl)

        if date_str:
            date_lbl = QLabel(date_str)
            date_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            text.addWidget(date_lbl)

        outer.addLayout(text, 1)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def run_id(self) -> str:
        return self._run.get("run_id", "")

    def set_selected(self, v: bool) -> None:
        self._selected = v
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT if v else PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        self.update()

    def mousePressEvent(self, event):
        if not self._selected:
            self.selected.emit(self._run)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        is_sel = self._selected
        is_hov = self._hovered
        if is_sel or is_hov:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), QColor("#0A0800"))
            glow_cx = self.width() * 0.18
            glow_cy = self.height() * 0.50
            center_col = QColor(204, 82, 130, 60) if is_sel else QColor(240, 168, 48, 38)
            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            grad = QRadialGradient(glow_cx, glow_cy, self.width() * 0.80)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.7, QColor(center_col.red(), center_col.green(),
                                        center_col.blue(), 8))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())
            p.restore()
            dot_x, dot_y = 8.0, self.height() / 2.0
            p.setPen(Qt.PenStyle.NoPen)
            dot_color = QColor(ROSE_ACCENT) if is_sel else QColor(PHOSPHOR_DIM)
            p.setBrush(dot_color)
            p.drawEllipse(int(dot_x - 3), int(dot_y - 3), 6, 6)
            p.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# ResearchPanel
# ---------------------------------------------------------------------------

class ResearchPanel(QFrame):
    """3-way classification comparison panel for research data collection."""

    def __init__(self, api=None, store=None, parent=None):
        super().__init__(parent)
        self._api   = api
        self._store = store

        self._worker        = None
        self._assign_worker = None
        self._current_result: Optional[dict] = None
        self._course_id:    Optional[int] = None
        self._course_name:  str = ""
        self._assignment_id:   Optional[int] = None
        self._assignment_name: str = ""
        self._prior_run_id:  Optional[str] = None
        self._prior_run_date: str = ""
        self._assign_rows:   List[_ResearchAssignRow] = []
        self._term_sections: list = []
        self._course_rows:   list = []  # all _CourseRow refs for single-select
        # student_id -> {"card": QFrame, "track_a": QFrame, ...}
        self._student_cards: Dict[str, dict] = {}

        self._offline_run_rows: List[_OfflineRunRow] = []

        self._build_ui()
        if self._api is None and self._store:
            self._populate_offline_runs()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from gui.styles import GripSplitter

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Banner
        banner = QFrame()
        banner.setObjectName("resBanner")
        banner.setFixedHeight(36)
        banner.setStyleSheet(
            "QFrame#resBanner {"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 #1A0A1C, stop:0.5 #200A10, stop:1 #0A0800);"
            f"  border-bottom: 1px solid {ROSE_DIM};"
            "}"
        )
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(0)
        banner_lbl = QLabel("RESEARCH COMPARISON  ·  3-TRACK CLASSIFICATION")
        banner_lbl.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: {px(11)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        bl.addWidget(banner_lbl)
        bl.addStretch()
        note = QLabel("not for production use")
        note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
            " border: none; font-style: italic;"
        )
        bl.addWidget(note)
        lo.addWidget(banner)

        # Splitter: sidebar | results
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        lo.addWidget(splitter, 1)

        sidebar = self._build_sidebar()
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(380)
        splitter.addWidget(sidebar)

        self._results_outer = self._build_results_pane()
        splitter.addWidget(self._results_outer)
        splitter.setSizes([300, 1100])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setStyleSheet(f"ResearchPanel {{ background: {BG_VOID}; }}")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("resSidebar")
        sidebar.setStyleSheet(
            "QFrame#resSidebar {"
            f"  background: {BG_PANEL};"
            f"  border-right: 1px solid {BORDER_DARK};"
            "}"
        )
        lo = QVBoxLayout(sidebar)
        lo.setContentsMargins(0, 8, 0, 8)
        lo.setSpacing(0)

        # ── Courses / Stored Runs ──
        _offline = self._api is None
        lo.addWidget(make_section_label("  Stored Runs" if _offline else "  Courses"))
        lo.addSpacing(2)

        self._course_scroll = QScrollArea()
        self._course_scroll.setWidgetResizable(True)
        self._course_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._course_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_INSET}; }}"
            + _scrollbar_qss()
        )
        self._course_scroll.setMinimumHeight(150)
        if not _offline:
            self._course_scroll.setMaximumHeight(260)

        self._course_content = QWidget()
        self._course_content.setStyleSheet(f"background: {BG_INSET};")
        self._course_lo = QVBoxLayout(self._course_content)
        self._course_lo.setContentsMargins(0, 0, 0, 0)
        self._course_lo.setSpacing(1)
        self._course_lo.addStretch()
        self._course_scroll.setWidget(self._course_content)
        lo.addWidget(self._course_scroll, 1 if _offline else 0)

        if not _offline:
            lo.addSpacing(4)
            lo.addWidget(make_h_rule())
            lo.addSpacing(4)

        # ── Assignments (online only) ──
        self._assign_section_lbl = make_section_label("  Assignments")
        self._assign_section_lbl.setVisible(not _offline)
        lo.addWidget(self._assign_section_lbl)
        lo.addSpacing(2)

        self._assign_scroll = QScrollArea()
        self._assign_scroll.setWidgetResizable(True)
        self._assign_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._assign_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_INSET}; }}"
            + _scrollbar_qss()
        )
        self._assign_scroll.setMinimumHeight(0 if _offline else 100)
        self._assign_scroll.setMaximumHeight(0 if _offline else 200)
        self._assign_scroll.setVisible(not _offline)

        self._assign_content = QWidget()
        self._assign_content.setStyleSheet(f"background: {BG_INSET};")
        self._assign_lo = QVBoxLayout(self._assign_content)
        self._assign_lo.setContentsMargins(0, 0, 0, 0)
        self._assign_lo.setSpacing(1)
        self._assign_placeholder_lbl = QLabel("  select a course")
        self._assign_placeholder_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 8px;"
        )
        self._assign_lo.addWidget(self._assign_placeholder_lbl)
        self._assign_lo.addStretch()
        self._assign_scroll.setWidget(self._assign_content)
        lo.addWidget(self._assign_scroll)

        lo.addSpacing(4)
        lo.addWidget(make_h_rule())
        lo.addSpacing(8)

        # ── Prior run indicator ──
        self._prior_frame = QFrame()
        self._prior_frame.setObjectName("priorFrame")
        self._prior_frame.setStyleSheet(
            "QFrame#priorFrame {"
            f"  background: {BG_CARD}; border: 1px solid {BORDER_DARK};"
            f"  border-radius: 4px; margin: 0 8px;"
            "}"
        )
        plo = QVBoxLayout(self._prior_frame)
        plo.setContentsMargins(8, 6, 8, 6)
        plo.setSpacing(3)

        self._prior_lbl = QLabel("no prior run")
        self._prior_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        plo.addWidget(self._prior_lbl)

        self._prior_track_lbl = QLabel("")
        self._prior_track_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        plo.addWidget(self._prior_track_lbl)
        lo.addWidget(self._prior_frame)
        lo.addSpacing(10)
        if _offline:
            self._prior_frame.setVisible(False)

        # ── Run buttons ──
        btn_wrap = QFrame()
        btn_wrap.setStyleSheet("background: transparent; border: none;")
        blo = QVBoxLayout(btn_wrap)
        blo.setContentsMargins(8, 0, 8, 0)
        blo.setSpacing(6)

        self._btn_run_missing = QPushButton(
            "Run Track A" if _offline else "Run Missing: Track A"
        )
        if _offline:
            make_run_button(self._btn_run_missing)
        else:
            make_secondary_button(self._btn_run_missing)
        self._btn_run_missing.setMinimumHeight(32 if _offline else 30)
        self._btn_run_missing.setVisible(False)
        self._btn_run_missing.clicked.connect(self._on_run_missing)
        blo.addWidget(self._btn_run_missing)

        self._btn_run_all = QPushButton("Run Full Comparison")
        make_run_button(self._btn_run_all)
        self._btn_run_all.setMinimumHeight(32)
        self._btn_run_all.setEnabled(False)
        self._btn_run_all.setVisible(not _offline)
        self._btn_run_all.clicked.connect(self._on_run_all)
        blo.addWidget(self._btn_run_all)

        lo.addWidget(btn_wrap)
        lo.addSpacing(6)

        # ── Progress ──
        self._progress_lbl = QLabel("")
        self._progress_lbl.setWordWrap(True)
        self._progress_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )
        lo.addWidget(self._progress_lbl)

        if not _offline:
            lo.addStretch()
        lo.addWidget(make_h_rule())
        lo.addSpacing(6)

        # ── Export buttons ──
        exp_wrap = QFrame()
        exp_wrap.setStyleSheet("background: transparent; border: none;")
        elo = QHBoxLayout(exp_wrap)
        elo.setContentsMargins(8, 0, 8, 0)
        elo.setSpacing(6)

        self._btn_export_json = QPushButton("Export JSON")
        make_secondary_button(self._btn_export_json)
        self._btn_export_json.setMinimumHeight(28)
        self._btn_export_json.setEnabled(False)
        self._btn_export_json.clicked.connect(self._on_export_json)
        elo.addWidget(self._btn_export_json)

        self._btn_export_csv = QPushButton("CSV (anon)")
        make_secondary_button(self._btn_export_csv)
        self._btn_export_csv.setMinimumHeight(28)
        self._btn_export_csv.setEnabled(False)
        self._btn_export_csv.setToolTip(
            "Anonymized CSV — student IDs replaced with anon_001, anon_002 etc. "
            "For research / sharing externally."
        )
        self._btn_export_csv.clicked.connect(self._on_export_csv)
        elo.addWidget(self._btn_export_csv)

        self._btn_export_csv_named = QPushButton("CSV (named)")
        make_secondary_button(self._btn_export_csv_named)
        self._btn_export_csv_named.setMinimumHeight(28)
        self._btn_export_csv_named.setEnabled(False)
        self._btn_export_csv_named.setToolTip(
            "CSV with real student names + all 3 tracks. "
            "For your own teaching use — do not share externally."
        )
        self._btn_export_csv_named.clicked.connect(self._on_export_csv_named)
        elo.addWidget(self._btn_export_csv_named)

        lo.addWidget(exp_wrap)
        return sidebar

    def _build_results_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("resResults")
        pane.setStyleSheet(
            "QFrame#resResults { background: " + BG_VOID + "; border: none; }"
        )
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(8)

        # Summary (hidden until results arrive)
        self._summary_frame = QFrame()
        self._summary_frame.setObjectName("resSummary")
        self._summary_frame.setVisible(False)
        self._summary_frame.setStyleSheet(
            "QFrame#resSummary {"
            f"  background: {PANE_BG_GRADIENT};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-top-color: {BORDER_AMBER};"
            f"  border-radius: 6px;"
            "}"
        )
        self._summary_lo = QVBoxLayout(self._summary_frame)
        self._summary_lo.setContentsMargins(14, 10, 14, 10)
        self._summary_lo.setSpacing(4)
        lo.addWidget(self._summary_frame)

        # Context strip (replaces static column headers)
        lo.addWidget(self._build_context_strip())

        # Scroll area for student cards
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._cards_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_VOID}; }}"
            + _scrollbar_qss(width=8)
        )

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet(f"background: {BG_VOID};")
        self._cards_lo = QVBoxLayout(self._cards_widget)
        self._cards_lo.setContentsMargins(0, 0, 0, 0)
        self._cards_lo.setSpacing(8)

        empty_text = (
            "Select a stored run to begin." if self._api is None
            else "Select an assignment to begin."
        )
        self._empty_lbl = QLabel(empty_text)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(13)}px;"
            f" background: transparent; border: none; padding: 40px;"
        )
        self._cards_lo.addWidget(self._empty_lbl)
        self._cards_lo.addStretch()
        self._cards_scroll.setWidget(self._cards_widget)
        lo.addWidget(self._cards_scroll, 1)

        return pane

    def _build_context_strip(self) -> QFrame:
        """Strip showing currently-selected run context: course · assignment · N · date."""
        hdr = QFrame()
        hdr.setObjectName("ctxStrip")
        hdr.setStyleSheet(
            "QFrame#ctxStrip {"
            f"  background: transparent; border: none;"
            f"  border-bottom: 1px solid {BORDER_DARK};"
            "}"
        )
        hlo = QHBoxLayout(hdr)
        hlo.setContentsMargins(8, 4, 8, 8)
        hlo.setSpacing(10)

        self._ctx_course_lbl = QLabel("")
        self._ctx_course_lbl.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: {px(11)}px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        hlo.addWidget(self._ctx_course_lbl)

        self._ctx_assign_lbl = QLabel("")
        self._ctx_assign_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        hlo.addWidget(self._ctx_assign_lbl)

        hlo.addStretch()

        self._ctx_meta_lbl = QLabel("")
        self._ctx_meta_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        hlo.addWidget(self._ctx_meta_lbl)

        return hdr

    def _update_context_strip(self) -> None:
        """Refresh the context strip from current run state."""
        if not hasattr(self, "_ctx_course_lbl"):
            return
        course = self._course_name or ""
        assign = self._assignment_name or ""
        n      = len(self._student_cards)
        date   = self._prior_run_date or ""

        self._ctx_course_lbl.setText(course)
        self._ctx_assign_lbl.setText(f"·  {assign}" if assign else "")
        meta_parts = []
        if n:
            meta_parts.append(f"{n} students")
        if date:
            meta_parts.append(f"run {date}")
        self._ctx_meta_lbl.setText("  ·  ".join(meta_parts))

    def _clear_context_strip(self) -> None:
        if hasattr(self, "_ctx_course_lbl"):
            self._ctx_course_lbl.setText("")
            self._ctx_assign_lbl.setText("")
            self._ctx_meta_lbl.setText("")

    # ── Course/assignment loading ─────────────────────────────────────────────

    def on_terms_loaded(self, terms: list) -> None:
        from gui.dialogs.bulk_run_dialog import _TermSection
        # Clear existing (keep trailing stretch)
        while self._course_lo.count() > 1:
            item = self._course_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._term_sections = []
        self._course_rows.clear()
        for tid, name, is_current in terms:
            section = _TermSection(name, is_current)
            self._course_lo.insertWidget(self._course_lo.count() - 1, section)
            self._term_sections.append((tid, section))

    def on_courses_loaded(self, term_id: int, courses: list) -> None:
        from gui.dialogs.bulk_run_dialog import _CourseRow
        for tid, section in self._term_sections:
            if tid == term_id:
                for course in courses:
                    row = _CourseRow(course)
                    cid   = course.get("id", 0)
                    cname = course.get("name", "")
                    row.toggled.connect(
                        lambda _cid, checked, _cname=cname, _id=cid: (
                            self._on_course_clicked(_id, _cname) if checked else None
                        )
                    )
                    section.add_course_row(row)
                    self._course_rows.append(row)
                break

    def on_courses_done(self) -> None:
        self._course_content.adjustSize()

    def _on_course_clicked(self, course_id: int, course_name: str) -> None:
        if self._course_id == course_id:
            return
        # Single-select: uncheck all other course rows
        for row in self._course_rows:
            if row.course_id() != course_id and row.is_checked():
                row.set_checked(False)
        self._course_id   = course_id
        self._course_name = course_name
        self._assignment_id   = None
        self._assignment_name = ""
        self._prior_run_id    = None
        self._prior_run_date  = ""
        self._btn_run_all.setEnabled(False)
        self._btn_run_missing.setVisible(False)
        self._update_prior_indicator()
        self._load_assignments(course_id)

    def _load_assignments(self, course_id: int) -> None:
        if self._assign_worker:
            self._assign_worker.cancel()
            self._assign_worker = None
        self._assign_rows.clear()
        _clear_layout(self._assign_lo)

        loading = QLabel("  loading...")
        loading.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 8px;"
        )
        self._assign_lo.addWidget(loading)
        self._assign_lo.addStretch()

        if not self._api:
            return

        from gui.workers import LoadAssignmentsWorker
        self._assign_worker = LoadAssignmentsWorker(self._api, course_id)
        self._assign_worker.assignments_loaded.connect(self._on_assignments_loaded)
        self._assign_worker.start()

    def _on_assignments_loaded(self, groups: list) -> None:
        _clear_layout(self._assign_lo)
        self._assign_rows.clear()

        if not groups or not any(g.get("assignments") for g in groups):
            empty = QLabel("  no assignments")
            empty.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
                f" background: transparent; border: none; padding: 8px;"
            )
            self._assign_lo.addWidget(empty)
            self._assign_lo.addStretch()
            return

        for group in groups:
            for assign in group.get("assignments", []):
                row = _ResearchAssignRow(assign)
                row.selected.connect(self._on_assignment_clicked)
                self._assign_lo.addWidget(row)
                self._assign_rows.append(row)
        self._assign_lo.addStretch()

    def _on_assignment_clicked(self, assignment_id: int, assignment_name: str) -> None:
        self._assignment_id   = assignment_id
        self._assignment_name = assignment_name
        for row in self._assign_rows:
            row.set_selected(row.assignment_id() == assignment_id)
        self._check_prior_run()
        self._btn_run_all.setEnabled(True)

    # ── Offline run browser ───────────────────────────────────────────────────

    def _populate_offline_runs(self) -> None:
        """Fill the course scroll with stored runs grouped by course (no Canvas)."""
        try:
            runs = self._store.get_completed_runs()
        except Exception as exc:
            log.warning("Could not load stored runs: %s", exc)
            return

        # Group by course name, preserving newest-first order within each group
        from collections import defaultdict
        by_course: dict = defaultdict(list)
        seen_courses: list = []
        for r in runs:
            cn = r.get("course_name") or "Unknown Course"
            if cn not in seen_courses:
                seen_courses.append(cn)
            by_course[cn].append(r)

        _clear_layout(self._course_lo)
        self._offline_run_rows = []

        for course_name in seen_courses:
            hdr = QLabel(course_name)
            hdr.setWordWrap(True)
            hdr.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px; font-weight: bold;"
                f" background: {BG_INSET}; border: none;"
                f" padding: 8px 10px 4px 10px; letter-spacing: 0.5px;"
            )
            self._course_lo.insertWidget(self._course_lo.count(), hdr)

            for run in by_course[course_name]:
                row = _OfflineRunRow(run)
                row.selected.connect(self._on_stored_run_clicked)
                self._course_lo.insertWidget(self._course_lo.count(), row)
                self._offline_run_rows.append(row)

        self._course_lo.addStretch()
        self._course_content.adjustSize()

    def _on_stored_run_clicked(self, run: dict) -> None:
        """Handle selection of a stored run in offline mode."""
        self._course_id       = run.get("course_id")
        self._course_name     = run.get("course_name", "")
        self._assignment_id   = run.get("assignment_id")
        self._assignment_name = run.get("assignment_name", "")
        self._prior_run_id    = run.get("run_id")
        self._prior_run_date  = (run.get("completed_at") or "")[:10]

        for row in self._offline_run_rows:
            row.set_selected(row.run_id() == self._prior_run_id)

        self._prior_frame.setVisible(True)
        self._update_prior_indicator(found=True)
        self._btn_run_missing.setVisible(True)
        self._btn_export_csv_named.setEnabled(True)
        self._load_prior_run(self._prior_run_id)
        self._update_context_strip()

    # ── Prior run detection ───────────────────────────────────────────────────

    def _check_prior_run(self) -> None:
        if not self._store or not self._course_id or not self._assignment_id:
            self._prior_run_id = None
            self._update_prior_indicator()
            return

        try:
            runs = self._store.get_runs(str(self._course_id))
        except Exception:
            runs = []

        best = None
        for run in runs:
            if str(run.get("assignment_id")) == str(self._assignment_id):
                if run.get("completed_at"):
                    if best is None or run["completed_at"] > best["completed_at"]:
                        best = run

        if best:
            self._prior_run_id   = best["run_id"]
            self._prior_run_date = best.get("completed_at", "")[:10]
            self._update_prior_indicator(found=True)
            self._btn_run_missing.setVisible(True)
            self._btn_export_csv_named.setEnabled(True)
            self._load_prior_run(self._prior_run_id)
        else:
            self._prior_run_id   = None
            self._prior_run_date = ""
            self._update_prior_indicator(found=False)
            self._btn_run_missing.setVisible(False)
            self._reset_cards()

    def _update_prior_indicator(self, found: bool = False) -> None:
        if found:
            label = "run loaded" if self._api is None else f"prior run: {self._prior_run_date}"
            self._prior_lbl.setText(label)
            self._prior_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            self._prior_track_lbl.setText("Tracks B + C loaded  |  click Run Track A"
                                          if self._api is None else
                                          "Tracks B + C available  |  Track A missing")
            self._prior_track_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
        else:
            self._prior_lbl.setText("no prior run")
            self._prior_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            self._prior_track_lbl.setText("")

    def _load_prior_run(self, run_id: str) -> None:
        """Populate Tracks B + C from stored data; leave Track A as [not run]."""
        if not self._store:
            return
        try:
            codings = self._store.get_codings(run_id)
        except Exception as exc:
            log.warning("Could not load prior codings: %s", exc)
            return

        self._reset_cards()

        for record in codings:
            student_id     = record.get("student_id", "")
            student_name   = record.get("student_name", student_id)
            submission_txt = record.get("submission_text", "") or ""
            raw = record.get("coding_record") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}

            track_b = {
                "axis":              raw.get("wellbeing_axis", ""),
                "signal":            raw.get("wellbeing_signal", ""),
                "confidence":        raw.get("wellbeing_confidence"),
                "prescan_signals":   raw.get("prescan_signals") or [],
                "checkin_flag":      raw.get("checkin_flag"),
                "checkin_reasoning": raw.get("checkin_reasoning", ""),
            }
            track_c    = {"observation": raw.get("observation", "")}
            track_a    = raw.get("track_a_research") or {}
            track_a_wb = raw.get("track_a_research_wb") or {}

            self._ensure_card(student_id, student_name, submission_txt)
            self._populate_track(student_id, "track_b", track_b)
            self._populate_track(student_id, "track_c", track_c)
            if track_a:
                self._populate_track(student_id, "track_a", track_a)
            if track_a_wb:
                self._populate_track(student_id, "track_a_wb", track_a_wb)

        self._empty_lbl.setVisible(False)
        self._update_context_strip()

    # ── Run controls ──────────────────────────────────────────────────────────

    def _on_run_all(self) -> None:
        if self._worker and self._worker.isRunning():
            self._on_cancel()
            return
        if not self._assignment_id:
            return

        self._reset_cards()
        self._student_cards.clear()
        self._btn_run_all.setText("Cancel")
        self._btn_run_missing.setEnabled(False)
        self._btn_export_json.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._progress_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )
        self._progress_lbl.setText("initializing...")
        self._current_result = None

        from gui.workers import ResearchComparisonWorker
        self._worker = ResearchComparisonWorker(
            self._api,
            store=self._store,
            course_id=self._course_id,
            course_name=self._course_name,
            assignment_id=self._assignment_id,
            assignment_name=self._assignment_name,
            is_discussion=False,
            model_tier="medium",
            settings={},
            run_mode="full",
        )
        self._connect_worker(self._worker)
        self._worker.start()

    def _on_run_missing(self) -> None:
        if self._worker and self._worker.isRunning():
            self._on_cancel()
            return
        if not self._prior_run_id:
            return

        self._btn_run_missing.setText("Cancel")
        self._btn_run_all.setEnabled(False)
        self._btn_export_json.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._progress_lbl.setText("running Track A on stored submissions...")
        self._current_result = None

        from gui.workers import ResearchComparisonWorker
        self._worker = ResearchComparisonWorker(
            self._api,
            store=self._store,
            course_id=self._course_id,
            course_name=self._course_name,
            assignment_id=self._assignment_id,
            assignment_name=self._assignment_name,
            is_discussion=False,
            model_tier="medium",
            settings={},
            run_mode="track_a_only",
            prior_run_id=self._prior_run_id,
        )
        self._connect_worker(self._worker)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._progress_lbl.setText("cancelling...")

    def _connect_worker(self, worker) -> None:
        worker.progress_update.connect(self._on_progress)
        worker.track_result.connect(self._on_track_result)
        worker.comparison_complete.connect(self._on_complete)
        worker.error.connect(self._on_error)
        worker.finished.connect(self._on_worker_finished)

    def _on_worker_finished(self) -> None:
        if self._api is not None:
            self._btn_run_all.setText("Run Full Comparison")
            self._btn_run_all.setEnabled(bool(self._assignment_id))
            self._btn_run_missing.setText("Run Missing: Track A")
        else:
            self._btn_run_missing.setText("Run Track A")
        self._btn_run_missing.setEnabled(True)
        if self._prior_run_id:
            self._btn_run_missing.setVisible(True)

    # ── Worker callbacks ──────────────────────────────────────────────────────

    def _on_progress(self, message: str) -> None:
        self._progress_lbl.setText(message)

    def _on_track_result(self, track: str, student_id: str, data: dict) -> None:
        name = data.get("student_name", student_id)
        self._ensure_card(student_id, name)
        self._populate_track(student_id, track, data)
        self._empty_lbl.setVisible(False)
        self._update_context_strip()

        # Persist binary-concern track results so they survive panel restarts.
        # Track A (combined) → coding_record.track_a_research
        # Track A_wb (wellbeing-only) → coding_record.track_a_research_wb
        # Tracks B and C are already persisted by the production pipeline.
        persist_keys = {
            "track_a":    "track_a_research",
            "track_a_wb": "track_a_research_wb",
        }
        if track in persist_keys and self._store and self._prior_run_id:
            try:
                self._store.save_track_a_result(
                    self._prior_run_id, student_id, data,
                    key=persist_keys[track],
                )
            except Exception as exc:
                log.warning("Could not persist %s result for %s: %s",
                            track, student_id, exc)

    def _on_complete(self, result: dict) -> None:
        self._current_result = result
        n = result.get("total_students", 0)
        self._progress_lbl.setText(f"complete — {n} students")
        self._btn_export_json.setEnabled(True)
        self._btn_export_csv.setEnabled(True)
        self._rebuild_summary(result)

    def _on_error(self, msg: str) -> None:
        self._progress_lbl.setText(f"error: {msg[:120]}")
        self._progress_lbl.setStyleSheet(
            f"color: {BURN_RED}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )

    # ── Card management ───────────────────────────────────────────────────────

    def _reset_cards(self) -> None:
        """Remove all student cards and reset to empty state."""
        _clear_layout(self._cards_lo)
        self._student_cards = {}
        self._clear_context_strip()

        empty_text = (
            "Select a stored run to begin." if self._api is None
            else "Select an assignment to begin."
        )
        self._empty_lbl = QLabel(empty_text)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(13)}px;"
            f" background: transparent; border: none; padding: 40px;"
        )
        self._cards_lo.addWidget(self._empty_lbl)
        self._cards_lo.addStretch()
        self._summary_frame.setVisible(False)
        _clear_layout(self._summary_lo)

    def _ensure_card(
        self, student_id: str, student_name: str, submission_text: str = ""
    ) -> None:
        if student_id in self._student_cards:
            # If card already exists but submission is now available, fill it
            if submission_text:
                info = self._student_cards[student_id]
                if not info.get("submission_filled"):
                    self._set_submission_text(student_id, submission_text)
            return

        # Insert before trailing stretch
        stretch_idx = self._cards_lo.count() - 1
        card = self._build_card_skeleton(student_id, student_name, submission_text)
        self._cards_lo.insertWidget(stretch_idx, card)

    def _build_card_skeleton(
        self, student_id: str, student_name: str, submission_text: str = ""
    ) -> QFrame:
        """Card layout (banner-with-tracks + side-by-side reading):
              ┌────────────────────────────────────────────────────────┐
              │ NAME   [TrackA pill]  [TrackB pill]  [CHECK-IN if flag]│
              ├──────────────────────────┬─────────────────────────────┤
              │ SUBMISSION (scrollable)  │ OBSERVATION (scrollable)     │
              └──────────────────────────┴─────────────────────────────┘
        """
        card = make_content_pane(f"card_{abs(hash(student_id)) % 100000:05d}")
        card.setMinimumHeight(280)
        card_lo = QVBoxLayout(card)
        card_lo.setContentsMargins(0, 0, 0, 0)
        card_lo.setSpacing(0)

        # ── Row 1: Name banner with tracks A and B inline ──
        name_banner = QFrame()
        name_banner.setObjectName(f"banner_{abs(hash(student_id)) % 100000:05d}")
        name_banner.setStyleSheet(
            f"QFrame#{name_banner.objectName()} {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 #1A1208, stop:0.5 #221408, stop:1 #0A0800);"
            f"  border: none; border-bottom: 1px solid {BORDER_AMBER};"
            f"}}"
        )
        nblo = QHBoxLayout(name_banner)
        nblo.setContentsMargins(14, 6, 14, 6)
        nblo.setSpacing(8)
        nlbl = QLabel(student_name)
        nlbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" letter-spacing: 0.5px; background: transparent; border: none;"
        )
        nblo.addWidget(nlbl)
        nblo.addStretch()

        # Track A (combined) inline slot — labeled "A1"
        nblo.addWidget(_dim_label("A1·", size=10))
        track_a_slot = QFrame()
        track_a_slot.setObjectName(f"{student_id}_track_a_body")
        track_a_slot.setStyleSheet("background: transparent; border: none;")
        ta_lo = QHBoxLayout(track_a_slot)
        ta_lo.setContentsMargins(0, 0, 0, 0)
        ta_lo.setSpacing(4)
        ta_lo.addWidget(_glow_label("[not run]"))
        nblo.addWidget(track_a_slot)

        # divider dot
        nblo.addWidget(_dim_label("·", size=12))

        # Track A_wb (wellbeing-only) inline slot — labeled "A2"
        nblo.addWidget(_dim_label("A2·", size=10))
        track_a_wb_slot = QFrame()
        track_a_wb_slot.setObjectName(f"{student_id}_track_a_wb_body")
        track_a_wb_slot.setStyleSheet("background: transparent; border: none;")
        ta_wb_lo = QHBoxLayout(track_a_wb_slot)
        ta_wb_lo.setContentsMargins(0, 0, 0, 0)
        ta_wb_lo.setSpacing(4)
        ta_wb_lo.addWidget(_glow_label("[not run]"))
        nblo.addWidget(track_a_wb_slot)

        # divider dot
        nblo.addWidget(_dim_label("·", size=12))

        # Track B inline slot — labeled "B"
        nblo.addWidget(_dim_label("B·", size=10))
        track_b_slot = QFrame()
        track_b_slot.setObjectName(f"{student_id}_track_b_body")
        track_b_slot.setStyleSheet("background: transparent; border: none;")
        tb_lo = QHBoxLayout(track_b_slot)
        tb_lo.setContentsMargins(0, 0, 0, 0)
        tb_lo.setSpacing(4)
        tb_lo.addWidget(_glow_label("[not run]"))
        nblo.addWidget(track_b_slot)

        card_lo.addWidget(name_banner)

        # ── Row 1.5: Rationale row (visible reasoning for tracks A and B) ──
        rationale_frame = QFrame()
        rationale_frame.setStyleSheet(
            f"QFrame {{ background: {BG_INSET}; border: none;"
            f" border-bottom: 1px solid {BORDER_DARK}; }}"
        )
        rlo = QVBoxLayout(rationale_frame)
        rlo.setContentsMargins(14, 6, 14, 6)
        rlo.setSpacing(3)

        track_a_rationale = QLabel("")
        track_a_rationale.setWordWrap(True)
        track_a_rationale.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        track_a_rationale.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        track_a_rationale.setVisible(False)
        rlo.addWidget(track_a_rationale)

        track_a_wb_rationale = QLabel("")
        track_a_wb_rationale.setWordWrap(True)
        track_a_wb_rationale.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        track_a_wb_rationale.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        track_a_wb_rationale.setVisible(False)
        rlo.addWidget(track_a_wb_rationale)

        track_b_rationale = QLabel("")
        track_b_rationale.setWordWrap(True)
        track_b_rationale.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        track_b_rationale.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        track_b_rationale.setVisible(False)
        rlo.addWidget(track_b_rationale)

        # Hide the whole frame until at least one rationale is filled
        rationale_frame.setVisible(False)
        card_lo.addWidget(rationale_frame)

        # ── Row 2: Submission (left) and Observation (right) — both scrollable ──
        body_row = QFrame()
        body_row.setStyleSheet("background: transparent; border: none;")
        body_lo = QHBoxLayout(body_row)
        body_lo.setContentsMargins(0, 0, 0, 0)
        body_lo.setSpacing(0)

        sub_frame = self._build_scroll_section(
            f"{student_id}_submission", "SUBMISSION", PHOSPHOR_GLOW
        )
        body_lo.addWidget(sub_frame, 1)

        # vertical divider
        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        body_lo.addWidget(vline)

        obs_frame = self._build_scroll_section(
            f"{student_id}_track_c", "TRACK C  ·  OBSERVATION", TERM_GREEN
        )
        body_lo.addWidget(obs_frame, 1)

        card_lo.addWidget(body_row, 1)

        self._student_cards[student_id] = {
            "card":              card,
            "track_a":           track_a_slot,
            "track_a_wb":        track_a_wb_slot,
            "track_b":           track_b_slot,
            "track_c":           obs_frame.findChild(QFrame, f"{student_id}_track_c_body"),
            "submission":        sub_frame.findChild(QFrame, f"{student_id}_submission_body"),
            "submission_filled": False,
            "rationale_frame":   rationale_frame,
            "track_a_rationale":     track_a_rationale,
            "track_a_wb_rationale":  track_a_wb_rationale,
            "track_b_rationale":     track_b_rationale,
        }

        if submission_text:
            self._set_submission_text(student_id, submission_text)

        return card

    def _build_scroll_section(
        self, body_id: str, label: str, color: str
    ) -> QFrame:
        """Build a labeled, scrollable text section for the card body."""
        wrap = QFrame()
        wrap.setStyleSheet("background: transparent; border: none;")
        wlo = QVBoxLayout(wrap)
        wlo.setContentsMargins(12, 8, 12, 10)
        wlo.setSpacing(4)

        hdr = QLabel(label)
        hdr.setStyleSheet(
            f"color: {color}; font-size: {px(9)}px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        wlo.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(180)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {BORDER_DARK}; background: {BG_INSET};"
            f"  border-radius: 3px; }}"
            + _scrollbar_qss(width=6)
        )

        body = QFrame()
        body.setObjectName(f"{body_id}_body")
        body.setStyleSheet(f"background: {BG_INSET}; border: none;")
        body_lo = QVBoxLayout(body)
        body_lo.setContentsMargins(8, 6, 8, 6)
        body_lo.setSpacing(4)
        body_lo.addWidget(_glow_label("[empty]"))
        body_lo.addStretch()
        scroll.setWidget(body)

        wlo.addWidget(scroll, 1)
        return wrap

    def _set_submission_text(self, student_id: str, text: str) -> None:
        info = self._student_cards.get(student_id)
        if not info:
            return
        body: QFrame = info.get("submission")
        if not body:
            return
        lo = body.layout()
        _clear_layout(lo)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lo.addWidget(lbl)
        lo.addStretch()
        info["submission_filled"] = True

    def _populate_track(self, student_id: str, track: str, data: dict) -> None:
        info = self._student_cards.get(student_id)
        if not info:
            return
        col: QFrame = info.get(track)
        if not col:
            return
        lo = col.layout()
        _clear_layout(lo)

        if track == "track_a":
            self._fill_track_a(lo, data, info, rationale_key="track_a_rationale",
                               label_prefix="BINARY (combined)")
        elif track == "track_a_wb":
            self._fill_track_a(lo, data, info, rationale_key="track_a_wb_rationale",
                               label_prefix="BINARY (wellbeing-only)")
        elif track == "track_b":
            self._fill_track_b(lo, data, info)
        else:
            self._fill_track_c(lo, data)

    def _fill_track_a(
        self, lo, data: dict, info: dict,
        *, rationale_key: str = "track_a_rationale",
        label_prefix: str = "BINARY CONCERN",
    ) -> None:
        """Fill a binary-concern track — pill + count in banner, rationale below.

        Used for both Track A (combined scope) and Track A_wb (wellbeing-only).
        rationale_key selects which rationale label to populate; label_prefix
        is the header text in the rationale row.
        """
        flagged    = data.get("flagged", False)
        concerns   = data.get("concerns") or []
        bias_warns = data.get("bias_warnings") or []

        pill_text = "FLAG" if flagged else "CLEAR"
        pill = _axis_pill(pill_text)
        lo.addWidget(pill)

        if flagged and concerns:
            count_lbl = QLabel(f"({len(concerns)})")
            count_lbl.setStyleSheet(
                f"color: {BURN_RED}; font-size: {px(10)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(count_lbl)

        if bias_warns:
            warn = QLabel("⚠")
            warn.setToolTip(f"{len(bias_warns)} bias flag(s) detected in model output")
            warn.setStyleSheet(
                f"color: #D87020; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(warn)

        # Visible rationale below banner
        rationale_lbl = info.get(rationale_key)
        if rationale_lbl is not None:
            if flagged and concerns:
                lines = [f"{label_prefix}  ·  flagged"]
                for c in concerns[:3]:
                    passage = (c.get("flagged_passage") or "").strip()[:200]
                    why     = (c.get("why_flagged") or "").strip()[:400]
                    conf    = c.get("confidence")
                    is_bias = "⚠" in why
                    parts = []
                    if passage:
                        parts.append(f'"{passage}"')
                    if why:
                        parts.append(why)
                    if conf is not None:
                        parts.append(f"(conf {float(conf):.2f})")
                    prefix = "⚠ " if is_bias else "  • "
                    lines.append(prefix + " — ".join(parts))
                rationale_lbl.setText("\n".join(lines))
                rationale_lbl.setVisible(True)
            else:
                rationale_lbl.setVisible(False)
            self._sync_rationale_visibility(info)

    def _fill_track_b(self, lo, data: dict, info: dict) -> None:
        """Fill Track B — axis pill + check-in pill in banner; signal/reasoning below."""
        axis     = (data.get("axis") or "").strip()
        signal   = (data.get("signal") or "").strip()
        conf     = data.get("confidence")
        prescan  = data.get("prescan_signals") or []
        checkin  = data.get("checkin_flag")
        checkin_r = (data.get("checkin_reasoning") or "").strip()

        axis_pill = _axis_pill(axis if axis else "—")
        lo.addWidget(axis_pill)

        if checkin:
            ci_pill = _axis_pill("CHECK-IN")
            lo.addWidget(ci_pill)

        # Visible rationale below banner
        rationale_lbl = info.get("track_b_rationale")
        if rationale_lbl is not None:
            lines = []
            if axis:
                head = f"4-AXIS  ·  {axis}"
                if conf is not None:
                    head += f"  (conf {float(conf):.2f})"
                lines.append(head)
            if signal:
                lines.append(f"  • {signal}")
            if prescan:
                for s in prescan[:3]:
                    lines.append(f"  · prescan: \"{s[:200]}\"")
            if checkin:
                lines.append("CHECK-IN  ·  flagged")
                if checkin_r:
                    lines.append(f"  • {checkin_r}")
            if lines:
                rationale_lbl.setText("\n".join(lines))
                rationale_lbl.setVisible(True)
            else:
                rationale_lbl.setVisible(False)
            self._sync_rationale_visibility(info)

    def _sync_rationale_visibility(self, info: dict) -> None:
        """Show the rationale frame iff at least one track's rationale has content.

        Uses isHidden() rather than isVisible() — the latter requires the parent
        window to be shown, which fails in tests and on initial load.
        """
        frame = info.get("rationale_frame")
        if not frame:
            return
        any_shown = False
        for key in ("track_a_rationale", "track_a_wb_rationale", "track_b_rationale"):
            lbl = info.get(key)
            if lbl is not None and not lbl.isHidden():
                any_shown = True
                break
        frame.setVisible(any_shown)

    def _fill_track_c(self, lo: QVBoxLayout, data: dict) -> None:
        """Fill Track C body (inside scroll area) — full observation prose."""
        obs = data.get("observation", "")
        if obs:
            lbl = QLabel(obs)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            lo.addWidget(lbl)
        else:
            lo.addWidget(_glow_label("[no observation]"))
        lo.addStretch()

    # ── Summary ───────────────────────────────────────────────────────────────

    def _rebuild_summary(self, result: dict) -> None:
        _clear_layout(self._summary_lo)

        comparisons = result.get("comparisons", {})
        n    = len(comparisons)
        meta = result.get("metadata", {})
        be   = meta.get("backend", {})

        # Top row
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(_mid_label(
            f"students: {n}   ·   model: {be.get('model_name', 'unknown')}",
            size=11
        ))
        top.addStretch()
        prior_tracks = meta.get("tracks_from_prior", [])
        if prior_tracks:
            letters = ", ".join(t[-1].upper() for t in sorted(prior_tracks))
            top.addWidget(_dim_label(
                f"[prior run: {self._prior_run_date}  ·  Track {letters} loaded]",
                size=10
            ))
        self._summary_lo.addLayout(top)
        self._summary_lo.addWidget(make_h_rule())

        # Counts
        (a_flag, a_clear, b_crisis, b_burn, b_eng, b_none,
         b_ci, c_obs,
         d_ae, d_an, d_acb, d_bca) = self._count_results(comparisons)

        counts_lo = QHBoxLayout()
        counts_lo.setSpacing(20)

        if a_flag + a_clear:
            pct = 100 * a_flag / (a_flag + a_clear)
            al = QLabel(f"A flagged: {a_flag}/{a_flag+a_clear} ({pct:.0f}%)")
            al.setStyleSheet(
                f"color: {BURN_RED}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(al)

        if b_crisis + b_burn + b_eng + b_none:
            bl = QLabel(
                f"B  CRISIS:{b_crisis}  BURNOUT:{b_burn}"
                f"  ENGAGED:{b_eng}  NONE:{b_none}  CI:{b_ci}"
            )
            bl.setStyleSheet(
                f"color: #D87020; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(bl)

        if c_obs:
            cl = QLabel(f"C observations: {c_obs}/{n}")
            cl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(cl)

        counts_lo.addStretch()
        self._summary_lo.addLayout(counts_lo)

        # Disagreements
        total_dis = d_ae + d_an + d_acb + d_bca
        if total_dis:
            self._summary_lo.addWidget(make_h_rule())
            self._summary_lo.addWidget(make_section_label("Disagreements"))
            for text, color in [
                (f"A flagged + B ENGAGED: {d_ae}",            BURN_RED),
                (f"A flagged + B NONE: {d_an}",               BURN_RED),
                (f"A clear + B CRISIS/BURNOUT: {d_acb}",      "#D87020"),
                (f"B CHECK-IN + A clear: {d_bca}",            ROSE_ACCENT),
            ]:
                row_lo = QHBoxLayout()
                row_lo.setContentsMargins(0, 0, 0, 0)
                lbl = QLabel(text)
                lbl.setStyleSheet(
                    f"color: {color}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                row_lo.addWidget(lbl)
                row_lo.addStretch()
                self._summary_lo.addLayout(row_lo)

        self._summary_frame.setVisible(True)

    def _count_results(self, comparisons: dict):
        a_flag = a_clear = b_crisis = b_burn = b_eng = b_none = b_ci = c_obs = 0
        d_ae = d_an = d_acb = d_bca = 0
        for sc in comparisons.values():
            ta = sc.get("track_a") or {}
            tb = sc.get("track_b") or {}
            tc = sc.get("track_c") or {}
            if ta:
                if ta.get("flagged"):
                    a_flag += 1
                else:
                    a_clear += 1
            if tb:
                ax = (tb.get("axis") or "").upper()
                if ax == "CRISIS":   b_crisis += 1
                elif ax == "BURNOUT": b_burn += 1
                elif ax == "ENGAGED": b_eng += 1
                elif ax == "NONE":    b_none += 1
                if tb.get("checkin_flag"):
                    b_ci += 1
            if tc and tc.get("observation"):
                c_obs += 1
            if ta and tb:
                ax = (tb.get("axis") or "").upper()
                if ta.get("flagged") and ax == "ENGAGED":
                    d_ae += 1
                if ta.get("flagged") and ax == "NONE":
                    d_an += 1
                if not ta.get("flagged") and ax in ("CRISIS", "BURNOUT"):
                    d_acb += 1
                if tb.get("checkin_flag") and not ta.get("flagged"):
                    d_bca += 1
        return a_flag, a_clear, b_crisis, b_burn, b_eng, b_none, b_ci, c_obs, d_ae, d_an, d_acb, d_bca

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_json(self) -> None:
        if not self._current_result:
            return
        safe_name = self._assignment_name[:30].replace(" ", "_").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Research JSON",
            f"research_{safe_name}.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            payload = self._build_export_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self._progress_lbl.setText(f"exported: {os.path.basename(path)}")
        except Exception as exc:
            self._progress_lbl.setText(f"export error: {exc}")

    def _on_export_csv(self) -> None:
        if not self._current_result:
            return
        safe_name = self._assignment_name[:30].replace(" ", "_").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Research CSV",
            f"research_{safe_name}.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            payload = self._build_export_dict()
            rows = []
            for anon_id, sc in payload.get("students", {}).items():
                ta = sc.get("track_a") or {}
                tb = sc.get("track_b") or {}
                tc = sc.get("track_c") or {}
                bias_warn = any(
                    c.get("has_bias_warning", False) for c in ta.get("concerns", [])
                )
                concerns = ta.get("concerns", [])
                rows.append({
                    "anon_id":             anon_id,
                    "word_count":          sc.get("word_count", ""),
                    "a_flagged":           ta.get("flagged", ""),
                    "a_concern_count":     ta.get("concern_count", ""),
                    "a_max_confidence":    max(
                        (c.get("confidence") or 0 for c in concerns),
                        default="",
                    ),
                    "a_flagged_passages":  " || ".join(
                        (c.get("flagged_passage") or "").strip() for c in concerns
                    ),
                    "a_why_flagged":       " || ".join(
                        (c.get("why_flagged") or "").strip() for c in concerns
                    ),
                    "a_confidences":       " || ".join(
                        f"{float(c.get('confidence') or 0):.2f}" for c in concerns
                    ),
                    "a_bias_warning":      bias_warn,
                    "b_axis":              tb.get("axis", ""),
                    "b_signal":            tb.get("signal", ""),
                    "b_confidence":        tb.get("confidence", ""),
                    "b_checkin":           tb.get("checkin_flag", ""),
                    "b_checkin_reasoning": tb.get("checkin_reasoning", ""),
                    "c_observation":       tc.get("observation", ""),
                })
            if not rows:
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            self._progress_lbl.setText(f"exported: {os.path.basename(path)}")
        except Exception as exc:
            self._progress_lbl.setText(f"export error: {exc}")

    def _on_export_csv_named(self) -> None:
        """Export CSV with real student names + all 3 tracks.

        Track B+C come from the DB (always available once a run is loaded);
        Track A comes from the in-memory result if Track A has been run.
        Available even before Track A runs — A columns will just be empty.
        """
        if not self._prior_run_id and not self._current_result:
            return
        safe_name = (self._assignment_name or "run")[:30]
        safe_name = safe_name.replace(" ", "_").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV (with student names)",
            f"{safe_name}_named.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return

        # Track B + C + submission text come from the DB codings
        coding_by_id: dict = {}
        if self._store and self._prior_run_id:
            try:
                for c in self._store.get_codings(self._prior_run_id) or []:
                    coding_by_id[c.get("student_id", "")] = c
            except Exception as exc:
                log.warning("Could not load codings for export: %s", exc)

        # Track A (combined) and Track A_wb (wellbeing-only) — prefer in-memory
        # result if Track A was just run, fall back to DB-persisted copies.
        track_a_by_id: dict = {}
        track_a_wb_by_id: dict = {}
        if self._current_result:
            for sid, sc in (self._current_result.get("comparisons") or {}).items():
                if sc.get("track_a"):
                    track_a_by_id[sid] = sc["track_a"]
                if sc.get("track_a_wb"):
                    track_a_wb_by_id[sid] = sc["track_a_wb"]
        # Pull persisted versions for any students not covered by live result
        for sid, coding in coding_by_id.items():
            raw = coding.get("coding_record") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}
            if sid not in track_a_by_id:
                persisted = raw.get("track_a_research")
                if persisted:
                    track_a_by_id[sid] = persisted
            if sid not in track_a_wb_by_id:
                persisted_wb = raw.get("track_a_research_wb")
                if persisted_wb:
                    track_a_wb_by_id[sid] = persisted_wb

        # Union of student IDs from all sources
        all_ids = set(coding_by_id.keys()) | set(track_a_by_id.keys()) | set(track_a_wb_by_id.keys())

        def _summarize_track_a(ta: dict) -> dict:
            """Return spreadsheet-friendly fields for a binary classifier result."""
            concerns = ta.get("concerns") or [] if ta else []
            return {
                "flagged":          ta.get("flagged", "") if ta else "",
                "concern_count":    len(concerns),
                "max_confidence":   max(
                    (float(c.get("confidence") or 0) for c in concerns),
                    default="",
                ),
                "flagged_passages": " || ".join(
                    (c.get("flagged_passage") or "").strip() for c in concerns
                ),
                "why_flagged":      " || ".join(
                    (c.get("why_flagged") or "").strip() for c in concerns
                ),
                "confidences":      " || ".join(
                    f"{float(c.get('confidence') or 0):.2f}" for c in concerns
                ),
                "bias_warning":     any(
                    "⚠" in (c.get("why_flagged") or "") for c in concerns
                ),
            }

        rows = []
        for sid in all_ids:
            coding = coding_by_id.get(sid, {})
            raw    = coding.get("coding_record") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}

            a_combined = _summarize_track_a(track_a_by_id.get(sid, {}))
            a_wb       = _summarize_track_a(track_a_wb_by_id.get(sid, {}))

            name = coding.get("student_name") or ""

            rows.append({
                "student_name":                  name,
                "word_count":                    raw.get("word_count", ""),
                "submission_text":               coding.get("submission_text", "") or "",
                # Track A — combined scope (wellbeing + power-moves)
                "track_a_flagged":               a_combined["flagged"],
                "track_a_concern_count":         a_combined["concern_count"],
                "track_a_max_confidence":        a_combined["max_confidence"],
                "track_a_flagged_passages":      a_combined["flagged_passages"],
                "track_a_why_flagged":           a_combined["why_flagged"],
                "track_a_confidences":           a_combined["confidences"],
                "track_a_bias_warning":          a_combined["bias_warning"],
                # Track A_wb — wellbeing-only scope
                "track_a_wb_flagged":            a_wb["flagged"],
                "track_a_wb_concern_count":      a_wb["concern_count"],
                "track_a_wb_max_confidence":     a_wb["max_confidence"],
                "track_a_wb_flagged_passages":   a_wb["flagged_passages"],
                "track_a_wb_why_flagged":        a_wb["why_flagged"],
                "track_a_wb_confidences":        a_wb["confidences"],
                "track_a_wb_bias_warning":       a_wb["bias_warning"],
                # Track B — 4-axis wellbeing + check-in
                "track_b_axis":                  raw.get("wellbeing_axis", ""),
                "track_b_signal":                raw.get("wellbeing_signal", ""),
                "track_b_confidence":            raw.get("wellbeing_confidence", ""),
                "track_b_prescan_signals":       " | ".join(
                    str(s) for s in (raw.get("prescan_signals") or [])
                ),
                "track_b_checkin_flag":          raw.get("checkin_flag", ""),
                "track_b_checkin_reasoning":     raw.get("checkin_reasoning", ""),
                # Track C — generative observation
                "track_c_observation":           raw.get("observation", ""),
            })

        rows.sort(key=lambda r: (r["student_name"] or "").lower())

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            self._progress_lbl.setText(f"exported: {os.path.basename(path)}")
        except Exception as exc:
            self._progress_lbl.setText(f"export error: {exc}")

    def _build_export_dict(self) -> dict:
        """Build anonymized export payload from current result."""
        result      = self._current_result
        comparisons = result.get("comparisons", {})
        sorted_ids  = sorted(comparisons.keys())
        id_map      = {sid: f"anon_{i+1:03d}" for i, sid in enumerate(sorted_ids)}

        students = {}
        for sid in sorted_ids:
            sc  = comparisons[sid]
            aid = id_map[sid]
            ta  = sc.get("track_a")
            tb  = sc.get("track_b")
            tc  = sc.get("track_c")

            anon_a = None
            if ta:
                c_list = []
                for c in (ta.get("concerns") or []):
                    c_list.append({
                        "flagged_passage":  c.get("flagged_passage", ""),
                        "why_flagged":      c.get("why_flagged", ""),
                        "confidence":       c.get("confidence"),
                        "has_bias_warning": "⚠" in (c.get("why_flagged") or ""),
                    })
                anon_a = {
                    "flagged":       ta.get("flagged"),
                    "concern_count": len(c_list),
                    "concerns":      c_list,
                }

            anon_b = None
            if tb:
                anon_b = {
                    "axis":              tb.get("axis"),
                    "signal":            tb.get("signal"),
                    "confidence":        tb.get("confidence"),
                    "prescan_signals":   tb.get("prescan_signals") or [],
                    "checkin_flag":      tb.get("checkin_flag"),
                    "checkin_reasoning": tb.get("checkin_reasoning", ""),
                }

            anon_c = None
            if tc:
                anon_c = {"observation": tc.get("observation", "")}

            students[aid] = {
                "word_count": sc.get("word_count", 0),
                "track_a":    anon_a,
                "track_b":    anon_b,
                "track_c":    anon_c,
            }

        meta = result.get("metadata", {})
        (a_flag, a_clear, b_crisis, b_burn, b_eng, b_none,
         b_ci, c_obs, d_ae, d_an, d_acb, d_bca) = self._count_results(comparisons)
        n = a_flag + a_clear

        return {
            "metadata": {
                "run_id":               meta.get("run_id"),
                "export_date":          datetime.now().isoformat(),
                "course_name":          "[redacted]",
                "assignment_name":      "[redacted]",
                "total_students":       len(sorted_ids),
                "backend":              meta.get("backend", {}),
                "track_timings":        meta.get("track_timings", {}),
                "tracks_freshly_run":   meta.get("tracks_freshly_run", []),
                "tracks_from_prior_run": meta.get("tracks_from_prior", []),
                "prior_run_id":         meta.get("prior_run_id"),
                "git_hash":             meta.get("git_hash", ""),
                "software_version":     meta.get("software_version", ""),
            },
            "summary": {
                "track_a": {
                    "flagged":     a_flag,
                    "clear":       a_clear,
                    "flagged_pct": round(100 * a_flag / n, 1) if n else 0.0,
                },
                "track_b": {
                    "crisis":   b_crisis, "burnout": b_burn,
                    "engaged":  b_eng,    "none":    b_none,
                    "checkin_count": b_ci,
                    "checkin_of_engaged_pct": round(
                        100 * b_ci / b_eng, 1
                    ) if b_eng else 0.0,
                },
                "track_c": {"observations_generated": c_obs},
                "disagreements": {
                    "a_flag_b_engaged":            d_ae,
                    "a_flag_b_none":               d_an,
                    "a_clear_b_crisis_or_burnout":  d_acb,
                    "b_checkin_a_clear":            d_bca,
                },
            },
            "students": students,
        }

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        for w in (self._worker, self._assign_worker):
            if w and w.isRunning():
                w.cancel()
                w.wait(3000)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scrollbar_qss(width: int = 6) -> str:
    return (
        f"QScrollBar:vertical {{ background: {BG_VOID}; width: {width}px; border: none; }}"
        f"QScrollBar::handle:vertical {{ background: {BORDER_AMBER}; border-radius: {width//2}px;"
        f"  min-height: 20px; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
    )
