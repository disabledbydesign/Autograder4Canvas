"""
Run Autograder dialog — CRT amber terminal redesign.

Two-page QStackedWidget:
  Page 0 — CONFIG:    grading scope, options, switches, run button
  Page 1 — PROGRESS:  phosphor progress bar, live log, stop/close
"""
import datetime
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QScrollArea,
    QFrame, QSizePolicy, QWidget, QStackedWidget,
)
from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QIntValidator, QPainter, QPainterPath,
    QBrush, QLinearGradient, QPen, QRadialGradient,
)

from gui.styles import (
    px,
    BG_VOID, BG_INSET, BG_CARD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    BORDER_DARK, BORDER_AMBER, AMBER_BTN,
    ROSE_ACCENT, TERM_GREEN, BURN_RED, STATUS_WARN,
    make_run_button, make_monospace_textedit,
    make_content_pane, make_section_label, make_h_rule,
    apply_phosphor_glow, GripSplitter,
    SPACING_XS, SPACING_SM,
)
from gui.widgets.switch_toggle import SwitchToggle
from gui.widgets.option_pair import OptionPair
from assignment_templates import aic_config_from_mode

import re
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # misc symbols, emoticons, etc.
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # ZWJ
    "\U000025A0-\U000025FF"  # geometric shapes
    "]+", re.UNICODE,
)

def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# CRT Phosphor Progress Bar
# ---------------------------------------------------------------------------

class _PhosphorProgressBar(QWidget):
    """Amber-phosphor CRT progress bar — QPainter-based, no native widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._maximum = 100
        self._format = "%p%"
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setValue(self, v: int) -> None:
        self._value = max(0, min(v, self._maximum))
        self.update()

    def setMaximum(self, m: int) -> None:
        self._maximum = max(1, m)
        self.update()

    def setFormat(self, fmt: str) -> None:
        self._format = fmt
        self.update()

    def _pct(self) -> float:
        return self._value / self._maximum if self._maximum > 0 else 0.0

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        track_path = QPainterPath()
        track_path.addRoundedRect(0.5, 0.5, w - 1, h - 1, r, r)
        p.fillPath(track_path, QColor(BG_INSET))
        p.setPen(QColor(BORDER_DARK))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(track_path)

        pct = self._pct()
        fill_w = max(0.0, (w - 2) * pct)
        if fill_w > 1:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(1, 1, fill_w, h - 2, r - 0.5, r - 0.5)

            grad = QLinearGradient(0, 0, fill_w + 1, 0)
            grad.setColorAt(0.00, QColor(90, 60, 8, 180))
            grad.setColorAt(0.55, QColor(160, 100, 15, 200))
            grad.setColorAt(0.82, QColor(210, 140, 22, 220))
            grad.setColorAt(1.00, QColor(240, 168, 48, 255))
            p.fillPath(fill_path, QBrush(grad))

            if fill_w > 6:
                edge_x = 1 + fill_w
                p.setPen(Qt.PenStyle.NoPen)
                glow = QLinearGradient(edge_x - 5, 0, edge_x + 3, 0)
                glow.setColorAt(0.0, QColor(240, 168, 48, 0))
                glow.setColorAt(0.6, QColor(240, 168, 48, 110))
                glow.setColorAt(1.0, QColor(255, 200, 80, 0))
                p.setBrush(QBrush(glow))
                p.drawRect(int(edge_x - 5), 1, 8, h - 2)

        pct_int = int(pct * 100)
        text = (self._format
                .replace("%p", str(pct_int))
                .replace("%v", str(self._value))
                .replace("%m", str(self._maximum)))
        p.setPen(QColor(PHOSPHOR_HOT) if pct > 0.15 else QColor(PHOSPHOR_DIM))
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        p.end()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num_field(value: int = 150, max_val: int = 9999, width: int = 55) -> QLineEdit:
    """Small numeric text field — no arrows, no suffix, just a number."""
    field = QLineEdit(str(value))
    field.setValidator(QIntValidator(0, max_val))
    field.setFixedWidth(width)
    field.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return field


def _int_val(field: QLineEdit, fallback: int = 0) -> int:
    """Read an int from a QLineEdit, returning *fallback* on empty/invalid."""
    try:
        return int(field.text())
    except (ValueError, TypeError):
        return fallback


def _make_crt_well(name: str) -> QFrame:
    """Recessed CRT screen well — inset bevel with faint phosphor inner glow.

    Simulates the look of a recessed display area on vintage hardware:
    darker top/left edges (shadow), slightly brighter bottom/right (light catch),
    warm amber radial glow from the centre.
    """
    well = QFrame()
    well.setObjectName(name)
    well.setStyleSheet(f"""
        QFrame#{name} {{
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.9,
                stop:0.0 rgba(240, 168, 48, 0.04),
                stop:1.0 rgba(240, 168, 48, 0.00));
            border-top:    1px solid rgba(0, 0, 0, 0.30);
            border-left:   1px solid rgba(0, 0, 0, 0.20);
            border-bottom: 1px solid rgba(255, 200, 80, 0.10);
            border-right:  1px solid rgba(255, 200, 80, 0.08);
            border-radius: 5px;
        }}
        QFrame#{name} QLabel {{
            background: transparent;
            border: none;
        }}
    """)
    return well


def _make_scanline_sep() -> QFrame:
    """Amber-phosphor scanline separator — matches setup_dialog divider style."""
    sep = QFrame()
    sep.setFixedHeight(2)
    sep.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(240,168,48, 0),
                stop:0.15 rgba(240,168,48, 0.25),
                stop:0.40 rgba(240,168,48, 0.70),
                stop:0.50 rgba(255,200,80, 1.00),
                stop:0.60 rgba(240,168,48, 0.70),
                stop:0.85 rgba(240,168,48, 0.25),
                stop:1.00 rgba(240,168,48, 0));
            border: none;
        }
    """)
    return sep


def _classify_selection(selected_items: list) -> tuple:
    """Return (n_discussions, n_ci, df_grading_type).

    df_grading_type is read from Canvas assignment data:
      "points"               → letter-grade / points mode
      "complete_incomplete"  → pass/fail mode
    """
    n_df = 0
    has_points = False
    for a in selected_items:
        if "discussion_topic" in (a.get("submission_types") or []):
            n_df += 1
            if a.get("grading_type") == "points":
                has_points = True
    df_gt = "points" if has_points else "complete_incomplete"
    return n_df, len(selected_items) - n_df, df_gt


# ---------------------------------------------------------------------------
# Run Dialog
# ---------------------------------------------------------------------------

class RunDialog(QDialog):
    """Modal dialog to configure and execute a grading job.

    Parameters
    ----------
    selections : list of (course_name, course_id, [assignment_dicts])
        One entry per course. Courses are run sequentially.
    """

    def __init__(self, api,
                 selections: List[tuple],
                 term_id: int, demo_mode: bool = False, parent=None):
        super().__init__(parent)
        self._api        = api
        self._selections = selections   # [(course_name, course_id, [items]), ...]
        self._term_id    = term_id
        self._demo_mode  = demo_mode
        self._worker     = None
        self._run_queue: List[tuple] = []
        self._all_ssr_pending: dict = {}  # accumulated pending SSR reviews across all courses

        # Classify the flat union of all assignments for the config pane
        all_items = [a for _, _, items in selections for a in items]
        self._n_df, self._n_ci, self._df_grading_type = _classify_selection(all_items)

        self.setWindowTitle("Run Autograder4Canvas")
        self.setMinimumWidth(380)
        self.resize(690, 560)
        self._setup_ui()
        self._load_settings_defaults()
        self._update_visibility()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_config_page())
        self._stack.addWidget(self._build_progress_page())
        self._stack.setCurrentIndex(0)

    # ── Page 0: Config ──────────────────────────────────────────────────────

    def _build_config_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("configPage")
        page.setStyleSheet(f"QWidget#configPage {{ background: {BG_VOID}; }}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        n_courses = len(self._selections)
        all_items = [a for _, _, items in self._selections for a in items]
        n_total   = len(all_items)

        if n_courses == 1:
            # display_name arrives as "Title (CODE)" — split into parts
            raw = self._selections[0][0]
            import re as _re
            m = _re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', raw)
            if m:
                course_title, course_code = m.group(1).strip(), m.group(2).strip()
            else:
                course_title, course_code = "", raw
            heading_text = course_code.upper()
            subtitle_text = course_title
        else:
            heading_text = f"{n_total} ASSIGNMENTS  ·  {n_courses} COURSES"
            subtitle_text = ""

        title_lbl = QLabel(heading_text)
        title_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        apply_phosphor_glow(title_lbl, color=PHOSPHOR_HOT, blur=10, strength=0.40)
        layout.addWidget(title_lbl)

        if subtitle_text:
            course_title_lbl = QLabel(subtitle_text)
            course_title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            layout.addWidget(course_title_lbl)

        layout.addSpacing(10)
        layout.addWidget(_make_scanline_sep())
        layout.addSpacing(16)

        # ── Word counts (bare — no box) ──────────────────────────────────────
        self._build_word_counts(layout)

        layout.addSpacing(14)

        # ── Option pairs (each in its own CRT well) ──────────────────────────
        opts_row = QHBoxLayout()
        opts_row.setContentsMargins(0, 0, 0, 0)
        opts_row.setSpacing(10)

        well_a = _make_crt_well("wellAbsent")
        wa_lo = QVBoxLayout(well_a)
        wa_lo.setContentsMargins(12, 10, 12, 10)
        self._mark_incomplete_opt = OptionPair(
            "Mark absent as Incomplete",
            "Leave absent ungraded",
            value=False,
        )
        self._mark_incomplete_opt.changed.connect(
            lambda v: self._save_setting("grade_missing_as_incomplete", v))
        wa_lo.addWidget(self._mark_incomplete_opt)
        opts_row.addWidget(well_a)

        well_b = _make_crt_well("wellRegrade")
        wb_lo = QVBoxLayout(well_b)
        wb_lo.setContentsMargins(12, 10, 12, 10)
        self._preserve_grades_opt = OptionPair(
            "New submissions only",
            "Regrade from scratch",
            value=True,
        )
        self._preserve_grades_opt.changed.connect(
            lambda v: self._save_setting("preserve_existing_grades", v))
        wb_lo.addWidget(self._preserve_grades_opt)
        opts_row.addWidget(well_b)

        layout.addLayout(opts_row)

        layout.addSpacing(14)

        # ── Analysis toggles (in a CRT well) ─────────────────────────────────
        analysis_well = _make_crt_well("wellAnalysis")
        analysis_inner = QVBoxLayout(analysis_well)
        analysis_inner.setContentsMargins(14, 12, 14, 12)
        analysis_inner.setSpacing(0)
        self._build_toggles_row(analysis_inner)
        layout.addWidget(analysis_well)

        layout.addStretch()

        # ── Button row ──────────────────────────────────────────────────────
        layout.addSpacing(14)
        layout.addWidget(_make_scanline_sep())
        layout.addSpacing(10)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()

        n_total = sum(len(items) for _, _, items in self._selections)
        n_courses = len(self._selections)
        if n_courses > 1:
            run_label = f"▶  Run All  ({n_total})"
        else:
            run_label = "▶  Run Autograder"
        self._run_btn = QPushButton(run_label)
        self._run_btn.clicked.connect(self._on_run)
        make_run_button(self._run_btn)
        btn_row.addWidget(self._run_btn)

        layout.addLayout(btn_row)
        return page

    def _build_word_counts(self, layout: QVBoxLayout) -> None:
        """Add word-count fields directly into *layout* (no surrounding box)."""

        _lbl_qss = (f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                     f" background: transparent; border: none;")
        _name_qss = (f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                      f" background: transparent; border: none;")
        _dim_qss = (f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                     f" background: transparent; border: none;")

        # Collect assignment names by type for listing
        all_items = [a for _, _, items in self._selections for a in items]
        ci_names = [a["name"] for a in all_items
                    if "discussion_topic" not in (a.get("submission_types") or [])]
        df_names = [a["name"] for a in all_items
                    if "discussion_topic" in (a.get("submission_types") or [])]

        # ── Submissions ──────────────────────────────────────────────────────
        self._sub_section = QWidget()
        sub_lo = QVBoxLayout(self._sub_section)
        sub_lo.setContentsMargins(0, 0, 0, 0)
        sub_lo.setSpacing(6)

        n_ci_text = (f"{self._n_ci} Assignment{'s' if self._n_ci != 1 else ''}"
                     if self._n_ci > 0 else "Submissions")
        sub_lo.addWidget(make_section_label(n_ci_text))

        if ci_names:
            ci_list = ", ".join(ci_names[:3])
            if len(ci_names) > 3:
                ci_list += f"  +{len(ci_names) - 3} more"
            ci_lbl = QLabel(ci_list)
            ci_lbl.setWordWrap(True)
            ci_lbl.setStyleSheet(_name_qss)
            ci_lbl.setContentsMargins(8, 0, 0, 0)
            sub_lo.addWidget(ci_lbl)

        # ── Manual word count fields (visible when templates off) ─────────
        self._manual_wc = QWidget()
        self._manual_wc.setStyleSheet("background: transparent;")
        _mwc_lo = QHBoxLayout(self._manual_wc)
        _mwc_lo.setContentsMargins(8, 0, 0, 0)
        _mwc_lo.setSpacing(10)
        wc_lbl = QLabel("Min. words")
        wc_lbl.setStyleSheet(_lbl_qss)
        _mwc_lo.addWidget(wc_lbl)
        self._min_word_field = _num_field(150)
        _mwc_lo.addWidget(self._min_word_field)
        _mwc_lo.addStretch()
        sub_lo.addWidget(self._manual_wc)

        # ── Template summary (visible when templates on) ──────────────────
        self._template_summary = QLabel(
            "Using Bulk Run template settings"
        )
        self._template_summary.setStyleSheet(_dim_qss)
        self._template_summary.setContentsMargins(8, 2, 0, 2)
        self._template_summary.setVisible(False)
        sub_lo.addWidget(self._template_summary)

        # ── "Use Templates" toggle ────────────────────────────────────────
        _tpl_row = QHBoxLayout()
        _tpl_row.setContentsMargins(8, 2, 0, 0)
        _tpl_row.setSpacing(8)
        self._use_templates_toggle = SwitchToggle(
            "Use Templates", wrap_width=100,
        )
        self._use_templates_toggle.setChecked(False)
        self._use_templates_toggle.toggled.connect(self._on_template_mode_changed)
        _tpl_row.addWidget(self._use_templates_toggle)
        _tpl_hint = QLabel("per-group settings from Bulk Run")
        _tpl_hint.setStyleSheet(_dim_qss)
        _tpl_row.addWidget(_tpl_hint)
        _tpl_row.addStretch()
        sub_lo.addLayout(_tpl_row)

        layout.addWidget(self._sub_section)

        # ── Discussions ──────────────────────────────────────────────────────
        self._df_section = QWidget()
        df_lo = QVBoxLayout(self._df_section)
        df_lo.setContentsMargins(0, 0, 0, 0)
        df_lo.setSpacing(6)

        self._df_sep = QWidget()
        _sep_lo = QVBoxLayout(self._df_sep)
        _sep_lo.setContentsMargins(0, 8, 0, 8)
        _thin_line = QFrame()
        _thin_line.setFixedHeight(1)
        _thin_line.setStyleSheet("background: rgba(255, 200, 80, 0.12);")
        _sep_lo.addWidget(_thin_line)
        df_lo.addWidget(self._df_sep)

        n_df_text = (f"{self._n_df} Discussion{'s' if self._n_df != 1 else ''}"
                     if self._n_df > 0 else "Discussions")
        df_lo.addWidget(make_section_label(n_df_text))

        if df_names:
            df_list = ", ".join(df_names[:3])
            if len(df_names) > 3:
                df_list += f"  +{len(df_names) - 3} more"
            df_lbl = QLabel(df_list)
            df_lbl.setWordWrap(True)
            df_lbl.setStyleSheet(_name_qss)
            df_lbl.setContentsMargins(8, 0, 0, 0)
            df_lo.addWidget(df_lbl)

        self._df_manual_fields = QWidget()
        self._df_manual_fields.setStyleSheet("background: transparent;")
        _df_mf_lo = QHBoxLayout(self._df_manual_fields)
        _df_mf_lo.setContentsMargins(8, 0, 0, 0)
        _df_mf_lo.setSpacing(10)
        post_lbl = QLabel("Post min. words")
        post_lbl.setStyleSheet(_lbl_qss)
        _df_mf_lo.addWidget(post_lbl)
        self._post_min_field = _num_field(150)
        _df_mf_lo.addWidget(self._post_min_field)
        _df_mf_lo.addSpacing(24)
        reply_lbl = QLabel("Reply min. words")
        reply_lbl.setStyleSheet(_lbl_qss)
        _df_mf_lo.addWidget(reply_lbl)
        self._reply_min_field = _num_field(50)
        _df_mf_lo.addWidget(self._reply_min_field)
        _df_mf_lo.addSpacing(24)
        replies_lbl = QLabel("Min. replies")
        replies_lbl.setStyleSheet(_lbl_qss)
        _df_mf_lo.addWidget(replies_lbl)
        self._min_replies_field = _num_field(2, max_val=20, width=40)
        _df_mf_lo.addWidget(self._min_replies_field)
        _df_mf_lo.addStretch()
        df_lo.addWidget(self._df_manual_fields)

        layout.addWidget(self._df_section)

    def _build_toggles_row(self, layout: QVBoxLayout) -> None:
        """Add three analysis toggles stacked vertically into *layout*."""

        _desc_qss = (f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                      f" background: transparent; border: none;")

        # Fixed left margin for descriptions so they align across all rows
        _DESC_LEFT = 200

        def _toggle_row(toggle, desc_text):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)
            row.addWidget(toggle)
            row.addSpacing(10)
            desc = QLabel(desc_text)
            desc.setStyleSheet(_desc_qss)
            desc.setMinimumWidth(_DESC_LEFT)
            row.addWidget(desc, 1)
            return row

        # ── AIC toggle — baby blue ───────────────────────────────────────────
        _baby_blue = QColor(120, 180, 255)
        self._aic_toggle = SwitchToggle(
            "Integrity Check",
            hover_color=_baby_blue,
        )
        self._aic_toggle.setChecked(True)
        self._aic_toggle.toggled.connect(self._on_aic_toggle_changed)
        layout.addLayout(_toggle_row(self._aic_toggle, "assess academic integrity"))
        layout.addSpacing(4)

        # Sub-option: Notes mode toggle (indented, visible when AIC on + manual mode)
        self._aic_mode_row = QWidget()
        self._aic_mode_row.setStyleSheet("background: transparent;")
        _mode_lo = QHBoxLayout(self._aic_mode_row)
        _mode_lo.setContentsMargins(28, 0, 0, 0)
        _mode_lo.setSpacing(10)
        self._notes_mode_toggle = SwitchToggle(
            "Notes Mode", hover_color=_baby_blue,
        )
        self._notes_mode_toggle.setChecked(False)
        self._notes_mode_toggle.toggled.connect(
            lambda v: self._save_setting(
                "quick_run_aic_mode", "notes" if v else "auto"))
        _mode_lo.addWidget(self._notes_mode_toggle)
        _mode_desc = QLabel("bullets, fragments, outlines")
        _mode_desc.setStyleSheet(_desc_qss)
        _mode_lo.addWidget(_mode_desc, 1)
        layout.addWidget(self._aic_mode_row)

        layout.addSpacing(14)

        # ── Short submission review — amber ──────────────────────────────────
        _amber = QColor(PHOSPHOR_HOT)
        self._short_sub_toggle = SwitchToggle(
            "Short Sub Review",
            hover_color=_amber,
        )
        self._short_sub_toggle.setChecked(False)
        self._short_sub_toggle.toggled.connect(self._on_llm_toggle_changed)
        layout.addLayout(_toggle_row(self._short_sub_toggle, "AI review of submissions below wordcount"))
        layout.addSpacing(4)

        # Sub-option: auto-post (indented, visible only when SSR is on)
        self._ssr_auto_post_row = QWidget()
        self._ssr_auto_post_row.setStyleSheet("background: transparent;")
        _ap_lo = QHBoxLayout(self._ssr_auto_post_row)
        _ap_lo.setContentsMargins(28, 0, 0, 0)
        _ap_lo.setSpacing(10)
        self._ssr_auto_post_toggle = SwitchToggle("Auto-Post Credits", hover_color=_amber)
        self._ssr_auto_post_toggle.setChecked(False)
        self._ssr_auto_post_toggle.toggled.connect(
            lambda v: self._save_setting("quick_run_short_sub_auto_post", v))
        _ap_lo.addWidget(self._ssr_auto_post_toggle)
        _ap_desc = QLabel("post ≥70% confidence credits to Canvas automatically")
        _ap_desc.setStyleSheet(_desc_qss)
        _ap_lo.addWidget(_ap_desc, 1)
        self._ssr_auto_post_row.setVisible(False)
        layout.addWidget(self._ssr_auto_post_row)

        layout.addSpacing(14)

        # ── Insights toggle — pink ───────────────────────────────────────────
        _pink = QColor(255, 96, 144)
        self._insights_toggle = SwitchToggle(
            "Class Insights",
            hover_color=_pink,
        )
        self._insights_toggle.setChecked(False)
        self._insights_toggle.toggled.connect(self._on_llm_toggle_changed)
        layout.addLayout(_toggle_row(self._insights_toggle, "class-wide themes and patterns"))

        # LLM time note — always reserves space; text hidden via transparent color
        layout.addSpacing(10)
        self._llm_warn = QLabel(
            "Local AI — short review: minutes, insights: hours"
        )
        self._llm_warn_visible = False
        self._llm_warn.setStyleSheet(
            f"color: transparent; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding-left: 4px;"
        )
        layout.addWidget(self._llm_warn)

    # ── Page 1: Progress ─────────────────────────────────────────────────────

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("progressPage")
        page.setStyleSheet(f"QWidget#progressPage {{ background: {BG_VOID}; }}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        # ── Header row: title left, status right ─────────────────────────
        hdr = QHBoxLayout()
        self._progress_heading = QLabel("RUNNING")
        self._progress_heading.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        hdr.addWidget(self._progress_heading)
        hdr.addStretch()
        self._progress_status = QLabel("Preparing…")
        self._progress_status.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        hdr.addWidget(self._progress_status)
        layout.addLayout(hdr)

        self._progress_bar = _PhosphorProgressBar()
        layout.addWidget(self._progress_bar)

        # ── Split pane: system log (left) | live surface (right) ─────────
        splitter = GripSplitter.create(Qt.Horizontal)

        # Left: System Log
        left = QFrame()
        left.setStyleSheet("background: transparent; border: none;")
        left_lo = QVBoxLayout(left)
        left_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        left_lo.setSpacing(4)
        left_lo.addWidget(make_section_label("System Log"))

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        make_monospace_textedit(self._log_output)
        self._log_output.setStyleSheet(
            f"background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 6px; color: {PHOSPHOR_DIM};"
            f" font-size: {px(10)}px; padding: 6px;"
        )
        left_lo.addWidget(self._log_output, 1)
        splitter.addWidget(left)

        # Right: Live Surface
        right = QFrame()
        right.setStyleSheet("background: transparent; border: none;")
        right_lo = QVBoxLayout(right)
        right_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        right_lo.setSpacing(4)
        right_lo.addWidget(make_section_label("Surfacing"))

        self._surface_scroll = QScrollArea()
        self._surface_scroll.setWidgetResizable(True)
        self._surface_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        surface_container = QWidget()
        surface_container.setStyleSheet(f"background: {BG_VOID};")
        self._surface_lo = QVBoxLayout(surface_container)
        self._surface_lo.setContentsMargins(0, 0, SPACING_SM, 0)
        self._surface_lo.setSpacing(SPACING_SM)
        self._surface_lo.addStretch()
        self._surface_scroll.setWidget(surface_container)
        right_lo.addWidget(self._surface_scroll, 1)
        splitter.addWidget(right)

        splitter.setSizes([280, 520])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        layout.addWidget(_make_scanline_sep())

        self._progress_btn_row = QHBoxLayout()
        self._progress_btn_row.setContentsMargins(0, 6, 0, 0)
        self._progress_btn_row.setSpacing(10)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        self._progress_btn_row.addWidget(self._stop_btn)

        self._progress_btn_row.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        self._progress_btn_row.addWidget(self._close_btn)

        layout.addLayout(self._progress_btn_row)
        return page

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings_defaults(self) -> None:
        try:
            from settings import load_settings
            s = load_settings()
            self._mark_incomplete_opt.setChecked(
                bool(s.get("grade_missing_as_incomplete", False)))
            self._preserve_grades_opt.setChecked(
                bool(s.get("preserve_existing_grades", True)))
            self._aic_toggle.setChecked(bool(s.get("quick_run_aic", True)))
            aic_on = self._aic_toggle.isChecked()
            saved_mode = s.get("quick_run_aic_mode", "auto")
            self._notes_mode_toggle.setChecked(saved_mode == "notes")
            tpl_on = bool(s.get("quick_run_use_templates", False))
            self._use_templates_toggle.setChecked(tpl_on)
            self._manual_wc.setVisible(not tpl_on)
            self._template_summary.setVisible(tpl_on)
            self._df_manual_fields.setVisible(not tpl_on)
            self._aic_mode_row.setVisible(aic_on and not tpl_on)
            self._short_sub_toggle.setChecked(bool(s.get("quick_run_short_sub_review", False)))
            self._ssr_auto_post_toggle.setChecked(bool(s.get("quick_run_short_sub_auto_post", False)))
            self._ssr_auto_post_row.setVisible(self._short_sub_toggle.isChecked())
            self._insights_toggle.setChecked(bool(s.get("quick_run_insights", False)))
            either = self._short_sub_toggle.isChecked() or self._insights_toggle.isChecked()
            self._set_llm_warn(either)

            # Restore persisted quick-run word count defaults
            qr = s.get("quick_run_defaults", {})
            if "submission_min_words" in qr:
                self._min_word_field.setText(str(int(qr["submission_min_words"])))
            if "discussion_post_min_words" in qr:
                self._post_min_field.setText(str(int(qr["discussion_post_min_words"])))
            if "discussion_reply_min_words" in qr:
                self._reply_min_field.setText(str(int(qr["discussion_reply_min_words"])))
            if "discussion_min_replies" in qr:
                self._min_replies_field.setText(str(int(qr["discussion_min_replies"])))
        except Exception:
            self._preserve_grades_opt.setChecked(True)

    def _save_setting(self, key: str, value) -> None:
        try:
            from settings import load_settings, save_settings
            s = load_settings()
            s[key] = value
            save_settings(s)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Visibility logic
    # ------------------------------------------------------------------

    def _on_aic_toggle_changed(self, on: bool) -> None:
        self._save_setting("quick_run_aic", on)
        tpl = self._use_templates_toggle.isChecked()
        self._aic_mode_row.setVisible(on and not tpl)

    def _on_template_mode_changed(self, on: bool) -> None:
        self._save_setting("quick_run_use_templates", on)
        self._manual_wc.setVisible(not on)
        self._template_summary.setVisible(on)
        # Hide AIC mode selector when templates are active (templates define it)
        aic_on = self._aic_toggle.isChecked()
        self._aic_mode_row.setVisible(aic_on and not on)
        # Also hide discussion manual fields when templates are on
        self._df_manual_fields.setVisible(not on)

    def _on_llm_toggle_changed(self, _on: bool = False) -> None:
        ssr_on = self._short_sub_toggle.isChecked()
        either = ssr_on or self._insights_toggle.isChecked()
        self._set_llm_warn(either)
        self._ssr_auto_post_row.setVisible(ssr_on)
        self._save_setting("quick_run_short_sub_review", ssr_on)
        self._save_setting("quick_run_insights", self._insights_toggle.isChecked())

    def _set_llm_warn(self, show: bool) -> None:
        color = PHOSPHOR_DIM if show else "transparent"
        self._llm_warn.setStyleSheet(
            f"color: {color}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding-left: 4px;"
        )

    def _update_visibility(self) -> None:
        has_df = self._n_df > 0
        has_ci = self._n_ci > 0

        self._sub_section.setVisible(has_ci)
        self._df_section.setVisible(has_df)
        # Only show the separator between sections when both are visible
        self._df_sep.setVisible(has_ci and has_df)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        self._persist_quick_run_defaults()
        self._run_queue = list(self._selections)
        n_total = sum(len(items) for _, _, items in self._selections)

        self._stack.setCurrentIndex(1)
        self._progress_heading.setText("RUNNING")
        self._progress_status.setText("Starting…")
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(max(1, n_total))
        self._stop_btn.setEnabled(True)
        self._close_btn.setEnabled(False)
        self._log_output.clear()
        self._run_next_course()

    def _run_next_course(self) -> None:
        if not self._run_queue:
            self._on_all_done()
            return

        course_name, course_id, selected = self._run_queue.pop(0)
        n_courses   = len(self._selections)
        done_count  = n_courses - len(self._run_queue) - 1
        if n_courses > 1:
            self._progress_status.setText(
                f"Running {course_name}  ({done_count + 1} of {n_courses})…"
            )
        else:
            self._progress_status.setText("Starting…")

        effective_aic = self._aic_toggle.isChecked()

        n_df, n_ci, df_gt = _classify_selection(selected)
        if n_df > 0 and n_ci > 0:
            atype = "mixed"
        elif n_df > 0:
            atype = "discussion_forum"
        else:
            atype = "complete_incomplete"

        mode_settings = self._resolve_mode_settings()

        if self._use_templates_toggle.isChecked():
            overrides = self._resolve_template_overrides(course_id, selected)
            mode_settings["group_overrides"] = overrides

        if self._demo_mode:
            from gui.workers import DemoRunWorker
            self._worker = DemoRunWorker(selected_items=selected)
        else:
            from gui.workers import RunWorker
            self._worker = RunWorker(
                api=self._api,
                course_id=course_id,
                course_name=course_name,
                selected_assignments=selected,
                assignment_type=atype,
                min_word_count=mode_settings["min_word_count"],
                post_min_words=mode_settings["post_min_words"],
                reply_min_words=mode_settings["reply_min_words"],
                grading_type=df_gt,
                post_points=1.0,
                reply_points=0.5,
                min_posts=1,
                min_replies=mode_settings["min_replies"],
                run_adc=effective_aic,
                run_insights=self._insights_toggle.isChecked(),
                run_short_sub_review=self._short_sub_toggle.isChecked(),
                short_sub_auto_post=self._ssr_auto_post_toggle.isChecked(),
                preserve_grades=self._preserve_grades_opt.isChecked(),
                mark_incomplete=self._mark_incomplete_opt.isChecked(),
                dry_run=False,
                mode_settings=mode_settings,
            )
        self._worker.log_line.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.surface.connect(self._on_surface)
        self._worker.finished.connect(self._on_course_finished)
        if hasattr(self._worker, "short_sub_reviews_ready"):
            self._worker.short_sub_reviews_ready.connect(self._on_ssr_reviews_ready)
        self._worker.start()

    def _on_course_finished(self, success: bool, message: str) -> None:
        icon = "Done" if success else "Error"
        self._append_log(f"\n[{icon}] {message}")
        if self._run_queue:
            self._run_next_course()
        else:
            self._on_all_done()

    def _on_ssr_reviews_ready(self, reviews: dict) -> None:
        self._all_ssr_pending.update(reviews)

    def _on_all_done(self) -> None:
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        n_total = sum(len(items) for _, _, items in self._selections)
        self._progress_bar.setValue(self._progress_bar._maximum)
        self._progress_heading.setText("COMPLETE")
        self._progress_status.setText(f"Done — {n_total} assignment{'s' if n_total != 1 else ''} graded.")

        if self._all_ssr_pending:
            n = len(self._all_ssr_pending)
            self._review_ssr_btn = QPushButton(f"Review Short Submissions ({n})")
            self._review_ssr_btn.setStyleSheet(
                f"QPushButton {{ color: {PHOSPHOR_HOT}; border: 1px solid {PHOSPHOR_HOT};"
                f" border-radius: 4px; padding: 4px 12px; background: transparent; }}"
                f" QPushButton:hover {{ background: rgba(255,176,0,0.12); }}"
            )
            self._review_ssr_btn.clicked.connect(self._open_ssr_review_dialog)
            idx = self._progress_btn_row.indexOf(self._close_btn)
            self._progress_btn_row.insertWidget(idx, self._review_ssr_btn)

    def _open_ssr_review_dialog(self) -> None:
        from gui.dialogs.short_sub_review_dialog import ShortSubReviewDialog
        dlg = ShortSubReviewDialog(
            reviews=self._all_ssr_pending,
            api=self._api,
            parent=self,
        )
        dlg.exec()

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)
        pct = int(done / total * 100) if total > 0 else 0
        if done < total:
            self._progress_status.setText(f"Step {done} of {total}  ({pct}%)")
        else:
            self._progress_status.setText(f"Finishing up…  ({pct}%)")

    def _append_log(self, line: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        clean = _strip_emoji(line)
        if not clean:
            return
        # Color-code by keyword
        low = clean.lower()
        if "grade(s) submitted" in low or clean.startswith("[Done]"):
            color = TERM_GREEN
        elif any(w in low[:40] for w in ("error", "failed", "warning", "stopped")):
            color = BURN_RED
        elif clean.startswith("=") or any(w in low[:40]
                for w in ("academic", "integrity", "grading", "insight",
                          "fetching", "analyzing", "running")):
            color = PHOSPHOR_HOT
        else:
            color = PHOSPHOR_DIM
        html = (f'<span style="color:{PHOSPHOR_DIM}">[{ts}]</span> '
                f'<span style="color:{color}">{clean}</span>')
        self._log_output.append(html)
        sb = self._log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Right-panel surface cards
    # ------------------------------------------------------------------

    def _on_surface(self, card_type: str, data: dict) -> None:
        """Render a live card in the right panel."""
        card = self._make_surface_card(card_type, data)
        if card:
            insert_idx = max(0, self._surface_lo.count() - 1)  # before stretch
            self._surface_lo.insertWidget(insert_idx, card)
            QTimer.singleShot(50, lambda: self._surface_scroll.verticalScrollBar().setValue(
                self._surface_scroll.verticalScrollBar().maximum()
            ))

    def _make_surface_card(self, card_type: str, data: dict):
        """Build a styled QFrame card based on type."""
        if card_type == "stage":
            return self._card_stage(data)
        elif card_type == "grading":
            return self._card_grading(data)
        elif card_type == "aic":
            return self._card_aic(data)
        elif card_type == "coding":
            return self._card_coding(data)
        elif card_type == "theme":
            return self._card_theme(data)
        elif card_type == "outlier":
            return self._card_outlier(data)
        elif card_type == "contradiction":
            return self._card_contradiction(data)
        return None

    # ── Stage divider ────────────────────────────────────────────────────

    def _card_stage(self, data: dict) -> QLabel:
        text = data.get("text", "")
        lbl = QLabel(f"── {text} ──")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
            f" letter-spacing: 1px; padding: 4px 0;"
            f" background: transparent; border: none;"
        )
        return lbl

    # ── Grading summary ──────────────────────────────────────────────────

    def _card_grading(self, data: dict) -> QFrame:
        aname = data.get("assignment", "")
        complete = data.get("complete", 0)
        incomplete = data.get("incomplete", 0)
        skipped = data.get("skipped", 0)
        incomplete_students = data.get("incomplete_students", [])
        is_disc = data.get("is_discussion", False)

        has_issues = incomplete > 0
        border = ROSE_ACCENT if has_issues else BORDER_AMBER
        accent = ROSE_ACCENT if has_issues else AMBER_BTN
        card = self._styled_card(border, accent)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr = QLabel(aname)
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        parts = [f"{complete} complete", f"{incomplete} incomplete"]
        if skipped:
            parts.append(f"{skipped} already graded")
        summary = QLabel(" · ".join(parts))
        summary.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(summary)

        # Show incomplete student details
        if incomplete_students:
            for s in incomplete_students:
                name = s.get("name", "")
                flags = s.get("flags", [])
                reason = ", ".join(flags) if flags else "No submission"
                fl = QLabel(f"  {name}: {reason}")
                fl.setWordWrap(True)
                fl.setStyleSheet(
                    f"color: {ROSE_ACCENT}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                lo.addWidget(fl)

        return card

    # ── AIC summary ──────────────────────────────────────────────────────

    def _card_aic(self, data: dict) -> QFrame:
        aname = data.get("assignment", "")
        analyzed = data.get("analyzed", 0)
        elevated = data.get("elevated", 0)
        low = data.get("low", 0)
        highlights = data.get("highlights", [])
        students = data.get("students", [])

        accent = ROSE_ACCENT if elevated else BORDER_AMBER
        card = self._styled_card(accent, accent if elevated else AMBER_BTN)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr = QLabel(f"Integrity Review — {aname}")
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        parts = [f"{analyzed} analyzed"]
        if elevated:
            parts.append(f"{elevated} elevated")
        if low:
            parts.append(f"{low} low concern")
        no_concern = analyzed - elevated - low
        if no_concern > 0:
            parts.append(f"{no_concern} clear")
        summary = QLabel(" · ".join(parts))
        summary.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(summary)

        # Show top markers triggered across the cohort
        if highlights:
            hl = QLabel("Markers: " + " · ".join(highlights))
            hl.setWordWrap(True)
            hl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(hl)

        for s in students:
            name = s.get("name", "")
            concern = s.get("concern", "")
            gun = " [smoking gun]" if s.get("smoking_gun") else ""
            sl = QLabel(f"  {name} — {concern}{gun}")
            sl.setWordWrap(True)
            sl.setStyleSheet(
                f"color: {ROSE_ACCENT}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(sl)

        return card

    # ── Insights: per-student coding card ────────────────────────────────

    def _card_coding(self, data: dict) -> QFrame:
        name = data.get("student_name", "")
        register = data.get("emotional_register", "")
        themes = data.get("themes", [])
        quote = data.get("best_quote", "")
        concerns = data.get("concerns", [])
        text_preview = data.get("text_preview", "")

        has_concerns = bool(concerns)
        accent = ROSE_ACCENT if has_concerns else BORDER_AMBER
        card = self._styled_card(accent, accent)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr_text = f"{name}  ·  {register}" if register else name
        hdr = QLabel(hdr_text)
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        if text_preview:
            preview = text_preview[:250] + ("…" if len(text_preview) > 250 else "")
            pl = QLabel(preview)
            pl.setWordWrap(True)
            pl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" padding: 2px 0 4px 0;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(pl)

        if themes:
            tag_text = " · ".join(themes[:5])
            tl = QLabel(tag_text)
            tl.setWordWrap(True)
            tl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(tl)

        if quote:
            qt = quote[:300] + ("…" if len(quote) > 300 else "")
            ql = QLabel(f"\"{qt}\"")
            ql.setWordWrap(True)
            ql.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" font-style: italic; padding: 2px 0;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(ql)

        if has_concerns:
            n = len(concerns)
            cl = QLabel(f"⚠ {n} passage{'s' if n != 1 else ''} flagged for review")
            cl.setStyleSheet(
                f"color: {ROSE_ACCENT}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(cl)

        return card

    # ── Insights: emerging theme ─────────────────────────────────────────

    def _card_theme(self, data: dict) -> QFrame:
        name = data.get("name", "")
        freq = data.get("frequency", 0)
        desc = data.get("description", "")

        card = self._styled_card(AMBER_BTN, AMBER_BTN)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr = QLabel(f"◆ {name}  ({freq} students)")
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        if desc:
            dl = QLabel(desc[:150] + ("…" if len(desc) > 150 else ""))
            dl.setWordWrap(True)
            dl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(dl)

        return card

    # ── Insights: outlier / unique voice ─────────────────────────────────

    def _card_outlier(self, data: dict) -> QFrame:
        name = data.get("name", "")
        why = data.get("why_notable", "")

        card = self._styled_card(TERM_GREEN, TERM_GREEN)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr = QLabel(f"✦ {name} — unique voice")
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {TERM_GREEN}; font-size: {px(11)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        if why:
            wl = QLabel(why[:120] + ("…" if len(why) > 120 else ""))
            wl.setWordWrap(True)
            wl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(wl)

        return card

    # ── Insights: contradiction / tension ────────────────────────────────

    def _card_contradiction(self, data: dict) -> QFrame:
        desc = data.get("description", "")

        card = self._styled_card(STATUS_WARN, STATUS_WARN)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(2)

        hdr = QLabel(f"⚡ Tension: {desc[:100]}")
        hdr.setWordWrap(True)
        hdr.setStyleSheet(
            f"color: {STATUS_WARN}; font-size: {px(11)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(hdr)

        return card

    # ── Card factory ─────────────────────────────────────────────────────

    def _styled_card(self, border_color: str, accent_color: str) -> QFrame:
        """Return a QFrame styled as a surface card with left accent border."""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD};"
            f" border: 1px solid {border_color};"
            f" border-left: 3px solid {accent_color};"
            f" border-radius: 6px; }}"
        )
        return card

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("\n[Stopped] Cancellation requested.")
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)


    def _resolve_mode_settings(self) -> dict:
        """Return aic_config and word counts from the dialog spinboxes."""
        # Essay mode (top option) → "auto"; Notes mode (bottom) → "notes"
        aic_mode = "notes" if self._notes_mode_toggle.isChecked() else "auto"
        return {
            "aic_mode":        aic_mode,
            "aic_config":      aic_config_from_mode(aic_mode),
            "min_word_count":  _int_val(self._min_word_field, 150),
            "post_min_words":  _int_val(self._post_min_field, 150),
            "reply_min_words": _int_val(self._reply_min_field, 50),
            "min_replies":     _int_val(self._min_replies_field, 2),
        }

    def _resolve_template_overrides(self, course_id: int, assignments: list) -> dict:
        """Build group_id → template_settings from Bulk Run mappings."""
        from assignment_templates import (
            load_templates, load_mappings, resolve_group, get_aic_config,
        )
        templates = load_templates()
        mappings = load_mappings()
        overrides: dict = {}
        seen_groups: set = set()
        for a in assignments:
            gid = a.get("assignment_group_id") or a.get("group_id")
            if gid is None or gid in seen_groups:
                continue
            seen_groups.add(gid)
            gname = a.get("group_name", "")
            tname, _src = resolve_group(course_id, gname, templates, mappings)
            if tname and tname in templates:
                tpl = templates[tname]
                overrides[gid] = {
                    "min_word_count":  tpl.get("min_word_count", 150),
                    "post_min_words":  tpl.get("post_min_words", 150),
                    "reply_min_words": tpl.get("reply_min_words", 50),
                    "run_aic":         tpl.get("run_aic", True),
                    "assignment_type": tpl.get("assignment_type", "complete_incomplete"),
                    "aic_config":      get_aic_config(tpl),
                }
        return overrides

    def _persist_quick_run_defaults(self) -> None:
        """Save current spinbox values so they're restored next time."""
        try:
            from settings import load_settings, save_settings
            s = load_settings()
            s["quick_run_defaults"] = {
                "submission_min_words":       _int_val(self._min_word_field, 150),
                "discussion_post_min_words":  _int_val(self._post_min_field, 150),
                "discussion_reply_min_words": _int_val(self._reply_min_field, 50),
                "discussion_min_replies":     _int_val(self._min_replies_field, 2),
            }
            s["quick_run_aic_mode"] = (
                "notes" if self._notes_mode_toggle.isChecked() else "auto"
            )
            save_settings(s)
        except Exception:
            pass
