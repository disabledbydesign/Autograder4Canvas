"""
Template Editor Dialog — manage named assignment templates.

Three-panel layout:
  Left   — template list with Add / Delete / Reset buttons
  Centre — template identification + grading settings
  Right  — academic integrity check settings
"""
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QMessageBox, QListWidget, QListWidgetItem,
    QSizePolicy, QSplitter, QPlainTextEdit,
)
from gui.widgets.crt_combo import CRTComboBox
from gui.widgets.switch_toggle import SwitchToggle
from gui.dialogs.message_dialog import show_question
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, AMBER_BTN, TERM_GREEN, WARN_PINK, BURN_RED,
    BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_INSET, BG_PANEL,
    PANE_BG_GRADIENT,
    make_run_button, make_secondary_button, make_section_label, make_h_rule,
    combo_qss,
)
from assignment_templates import (
    load_templates, save_templates,
    DEFAULT_TEMPLATES, TEMPLATE_FIELD_DEFAULTS, SYSTEM_DEFAULT_NAMES,
    AIC_MODE_LABELS, AIC_MODE_WEIGHT_PRESETS,
    AIC_CONTEXT_LABELS, AIC_SENSITIVITY_LABELS,
    ASSIGNMENT_TYPE_LABELS, LETTER_GRADE_PERCENTAGES,
)

# ---------------------------------------------------------------------------
# Mode descriptions — teacher-facing
# ---------------------------------------------------------------------------

_AIC_MODE_DESCRIPTIONS: dict = {
    "auto":       "Picks the best mode automatically from the assignment name and keywords.",
    "notes":      "Bullet points and fragments count as authentic. Complete prose is suspicious.",
    "outline":    "Hierarchical lists and structured planning. Fragments are authentic; symmetrical AI-style outlines are flagged.",
    "discussion": "Real engagement with peers and course readings is the target signal.",
    "draft":      "Rough, in-progress writing is expected — messiness counts as authentic.",
    "personal":   "First-person voice and personal experience are strong authenticity signals.",
    "essay":      "Formal register expected. AI transitions and generic phrasing are flagged aggressively.",
    "lab":        "Course-specific experimental detail and data are the key authenticity signals.",
}

# ---------------------------------------------------------------------------
# Shared stylesheets
# ---------------------------------------------------------------------------

_PANE_QSS = (
    f"QFrame#templatePane {{"
    f"  background: {PANE_BG_GRADIENT};"
    f"  border: 1px solid {BORDER_DARK};"
    f"  border-top-color: {BORDER_AMBER};"
    f"  border-radius: 8px;"
    f"}}"
)

_LIST_QSS = f"""
    QListWidget {{
        background: {BG_INSET};
        border: none;
        font-size: {px(12)}px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-left: 3px solid transparent;
        border-radius: 0;
        color: {PHOSPHOR_GLOW};
    }}
    QListWidget::item:selected {{
        background: #2C1C08;
        color: {PHOSPHOR_HOT};
        border-left: 3px solid {ROSE_ACCENT};
        font-weight: 600;
    }}
    QListWidget::item:hover:!selected {{
        background: #1A1008;
        color: {PHOSPHOR_MID};
    }}
"""

_FIELD_LABEL_QSS = (
    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: normal;"
    f" letter-spacing: 0.5px; background: transparent; border: none;"
)

_SUBTEXT_QSS = (
    f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"
    f" background: transparent; border: none;"
)

_INPUT_QSS = f"""
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background: {BG_INSET};
        border: 1px solid {BORDER_DARK};
        border-radius: 3px;
        padding: 4px 8px;
        color: {PHOSPHOR_HOT};
        font-size: {px(12)}px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {BORDER_AMBER}; }}
"""

_COMBO_QSS = combo_qss()

_SMALL_BTN_QSS = (
    f"QPushButton {{"
    f" background: transparent; color: {PHOSPHOR_DIM};"
    f" border: 1px solid {BORDER_DARK}; border-radius: 3px;"
    f" padding: 3px 10px; font-size: {px(11)}px; }}"
    f"QPushButton:hover {{"
    f" border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}"
    f"QPushButton:pressed {{"
    f" color: {PHOSPHOR_HOT}; }}"
)

_DELETE_BTN_QSS = (
    f"QPushButton {{"
    f" background: transparent; color: rgba(192,64,32,0.70);"
    f" border: 1px solid rgba(192,64,32,0.35); border-radius: 3px;"
    f" padding: 3px 10px; font-size: {px(11)}px; }}"
    f"QPushButton:hover {{"
    f" border-color: rgba(192,64,32,0.80); color: {BURN_RED}; }}"
    f"QPushButton:disabled {{ color: {PHOSPHOR_GLOW}; border-color: {BORDER_DARK}; }}"
)

_ADV_BTN_QSS = (
    f"QPushButton {{"
    f" background: transparent; color: {PHOSPHOR_DIM};"
    f" border: 1px solid {BORDER_DARK}; border-radius: 3px;"
    f" padding: 4px 10px; font-size: {px(11)}px; text-align: left; }}"
    f"QPushButton:hover {{"
    f" border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}"
    f"QPushButton:checked {{"
    f" border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}"
)


# ---------------------------------------------------------------------------
# Helper factories (module-level so both form classes can use them)
# ---------------------------------------------------------------------------

def _field_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(_FIELD_LABEL_QSS)
    return lbl


def _subtext(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(_SUBTEXT_QSS)
    return lbl


def _section_header(text: str) -> QLabel:
    return make_section_label(text)


def _hsep() -> QFrame:
    return make_h_rule()


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        f"QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}"
    )
    scroll.setWidget(inner)
    return scroll


# ---------------------------------------------------------------------------
# _BasicGradingForm — centre panel
# ---------------------------------------------------------------------------

_DISC_TYPES = {"discussion_ci", "discussion_points", "discussion_letter",
               "discussion_forum", "mixed"}


class _BasicGradingForm(QWidget):
    """Template identification + grading settings."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_INSET};")
        form = QVBoxLayout(inner)
        form.setContentsMargins(14, 10, 14, 10)
        form.setSpacing(SPACING_SM)

        # ── Identification ──────────────────────────────────────────────
        form.addWidget(_section_header("IDENTIFICATION"))

        form.addWidget(_field_label("Template name"))
        self._name_edit = QLineEdit()
        self._name_edit.setStyleSheet(_INPUT_QSS)
        self._name_edit.setPlaceholderText("e.g. Weekly Reflection")
        self._name_edit.textChanged.connect(self._emit)
        form.addWidget(self._name_edit)

        form.addWidget(_field_label("Keywords"))
        self._kw_edit = QLineEdit()
        self._kw_edit.setStyleSheet(_INPUT_QSS)
        self._kw_edit.setPlaceholderText("e.g. reflection, journal, response")
        self._kw_edit.textChanged.connect(self._emit)
        form.addWidget(self._kw_edit)
        form.addWidget(_subtext("Comma-separated. Auto-matched to Canvas assignment group names."))

        form.addWidget(_hsep())

        # ── Grading ─────────────────────────────────────────────────────
        form.addWidget(_section_header("GRADING"))

        form.addWidget(_field_label("Assignment type"))
        self._type_combo = CRTComboBox()
        for key, label in ASSIGNMENT_TYPE_LABELS.items():
            self._type_combo.addItem(label, key)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addWidget(self._type_combo)

        # ── Non-discussion: single min word count ────────────────────────
        self._non_disc_widget = QWidget()
        self._non_disc_widget.setStyleSheet("background: transparent;")
        nd_lo = QVBoxLayout(self._non_disc_widget)
        nd_lo.setContentsMargins(0, 4, 0, 0)
        nd_lo.setSpacing(3)
        nd_lo.addWidget(_field_label("Min word count"))
        self._min_wc = QSpinBox()
        self._min_wc.setRange(0, 5000)
        self._min_wc.setSingleStep(25)
        self._min_wc.setStyleSheet(_INPUT_QSS)
        self._min_wc.valueChanged.connect(self._emit)
        nd_lo.addWidget(self._min_wc)
        form.addWidget(self._non_disc_widget)

        # ── Discussion shared: post + reply word counts ──────────────────
        self._disc_shared_widget = QWidget()
        self._disc_shared_widget.setStyleSheet("background: transparent;")
        ds_lo = QVBoxLayout(self._disc_shared_widget)
        ds_lo.setContentsMargins(0, 4, 0, 0)
        ds_lo.setSpacing(SPACING_SM)

        ds_lo.addWidget(_field_label("Minimum word counts"))
        wc_row = QHBoxLayout()
        wc_row.setSpacing(SPACING_MD)

        post_col = QVBoxLayout()
        post_col.setSpacing(3)
        post_col.addWidget(_field_label("Post"))
        self._post_wc = QSpinBox()
        self._post_wc.setRange(0, 5000)
        self._post_wc.setSingleStep(25)
        self._post_wc.setStyleSheet(_INPUT_QSS)
        self._post_wc.valueChanged.connect(self._emit)
        post_col.addWidget(self._post_wc)
        wc_row.addLayout(post_col)

        reply_col = QVBoxLayout()
        reply_col.setSpacing(3)
        reply_col.addWidget(_field_label("Reply"))
        self._reply_wc = QSpinBox()
        self._reply_wc.setRange(0, 2000)
        self._reply_wc.setSingleStep(10)
        self._reply_wc.setStyleSheet(_INPUT_QSS)
        self._reply_wc.valueChanged.connect(self._emit)
        reply_col.addWidget(self._reply_wc)
        wc_row.addLayout(reply_col)
        wc_row.addStretch()

        ds_lo.addLayout(wc_row)
        form.addWidget(self._disc_shared_widget)

        # ── Discussion C/I: min replies ──────────────────────────────────
        self._ci_widget = QWidget()
        self._ci_widget.setStyleSheet("background: transparent;")
        ci_lo = QVBoxLayout(self._ci_widget)
        ci_lo.setContentsMargins(0, 4, 0, 0)
        ci_lo.setSpacing(3)
        ci_lo.addWidget(_field_label("Min replies for Complete"))
        self._min_replies = QSpinBox()
        self._min_replies.setRange(0, 20)
        self._min_replies.setSingleStep(1)
        self._min_replies.setStyleSheet(_INPUT_QSS)
        self._min_replies.valueChanged.connect(self._emit)
        ci_lo.addWidget(self._min_replies)
        ci_lo.addWidget(_subtext(
            "Student must post and reply at least this many times to be marked Complete."
        ))
        form.addWidget(self._ci_widget)

        # ── Discussion Points: per-post and per-reply point values ───────
        self._pts_widget = QWidget()
        self._pts_widget.setStyleSheet("background: transparent;")
        pts_lo = QVBoxLayout(self._pts_widget)
        pts_lo.setContentsMargins(0, 4, 0, 0)
        pts_lo.setSpacing(SPACING_SM)

        pts_lo.addWidget(_field_label("Points"))
        pts_row = QHBoxLayout()
        pts_row.setSpacing(SPACING_MD)

        ppp_col = QVBoxLayout()
        ppp_col.setSpacing(3)
        ppp_col.addWidget(_field_label("Per post"))
        self._pts_per_post = QDoubleSpinBox()
        self._pts_per_post.setRange(0.0, 100.0)
        self._pts_per_post.setSingleStep(0.5)
        self._pts_per_post.setDecimals(1)
        self._pts_per_post.setStyleSheet(_INPUT_QSS)
        self._pts_per_post.valueChanged.connect(self._emit)
        ppp_col.addWidget(self._pts_per_post)
        pts_row.addLayout(ppp_col)

        ppr_col = QVBoxLayout()
        ppr_col.setSpacing(3)
        ppr_col.addWidget(_field_label("Per reply"))
        self._pts_per_reply = QDoubleSpinBox()
        self._pts_per_reply.setRange(0.0, 100.0)
        self._pts_per_reply.setSingleStep(0.5)
        self._pts_per_reply.setDecimals(1)
        self._pts_per_reply.setStyleSheet(_INPUT_QSS)
        self._pts_per_reply.valueChanged.connect(self._emit)
        ppr_col.addWidget(self._pts_per_reply)
        pts_row.addLayout(ppr_col)
        pts_row.addStretch()

        pts_lo.addLayout(pts_row)
        form.addWidget(self._pts_widget)

        # ── Discussion Letter Grade: reply thresholds ────────────────────
        self._lg_widget = QWidget()
        self._lg_widget.setStyleSheet("background: transparent;")
        lg_lo = QVBoxLayout(self._lg_widget)
        lg_lo.setContentsMargins(0, 4, 0, 0)
        lg_lo.setSpacing(SPACING_SM)

        lg_lo.addWidget(_field_label("Replies needed for each grade"))

        abc_row = QHBoxLayout()
        abc_row.setSpacing(SPACING_MD)
        for attr, lbl, default in [
            ("_replies_a", "A", 2),
            ("_replies_b", "B", 1),
            ("_replies_c", "C", 0),
        ]:
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addWidget(_field_label(lbl))
            spin = QSpinBox()
            spin.setRange(0, 20)
            spin.setValue(default)
            spin.setStyleSheet(_INPUT_QSS)
            spin.valueChanged.connect(self._emit)
            setattr(self, attr, spin)
            col.addWidget(spin)
            abc_row.addLayout(col)
        abc_row.addStretch()
        lg_lo.addLayout(abc_row)

        lg_lo.addWidget(_subtext(
            "C = posted (any number of qualifying replies).  No post = F."
        ))

        # D-tier enable toggle + spinbox
        d_row = QHBoxLayout()
        d_row.setSpacing(SPACING_SM)
        from gui.widgets.switch_toggle import SwitchToggle as _ST
        self._d_enable = _ST("Enable D tier")
        self._d_enable.toggled.connect(self._on_d_toggled)
        d_row.addWidget(self._d_enable)

        d_spin_col = QVBoxLayout()
        d_spin_col.setSpacing(3)
        d_spin_col.addWidget(_field_label("Replies for D"))
        self._replies_d = QSpinBox()
        self._replies_d.setRange(0, 20)
        self._replies_d.setValue(0)
        self._replies_d.setStyleSheet(_INPUT_QSS)
        self._replies_d.valueChanged.connect(self._emit)
        d_spin_col.addWidget(self._replies_d)
        d_row.addLayout(d_spin_col)
        d_row.addStretch()
        lg_lo.addLayout(d_row)

        # Canvas % conversion info
        pct_str = "  ".join(
            f"{k}→{v}%" for k, v in LETTER_GRADE_PERCENTAGES.items()
        )
        lg_lo.addWidget(_subtext(f"Canvas score:  {pct_str}"))

        form.addWidget(self._lg_widget)

        form.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_scroll_wrap(inner))

        self._set_enabled(False)

    # ── helpers ───────────────────────────────────────────────────────

    def _emit(self, *_) -> None:
        if not self._loading:
            self.changed.emit()

    def _set_enabled(self, enabled: bool) -> None:
        for w in (self._name_edit, self._kw_edit, self._type_combo,
                  self._min_wc, self._post_wc, self._reply_wc,
                  self._min_replies, self._pts_per_post, self._pts_per_reply,
                  self._replies_a, self._replies_b, self._replies_c,
                  self._d_enable, self._replies_d):
            w.setEnabled(enabled)

    def _on_type_changed(self, *_) -> None:
        key = self._type_combo.currentData() or "complete_incomplete"
        is_disc = key in _DISC_TYPES
        self._non_disc_widget.setVisible(not is_disc)
        self._disc_shared_widget.setVisible(is_disc)
        self._ci_widget.setVisible(key == "discussion_ci")
        self._pts_widget.setVisible(key == "discussion_points")
        self._lg_widget.setVisible(key == "discussion_letter")
        self._emit()

    def _on_d_toggled(self, checked: bool) -> None:
        self._replies_d.setEnabled(checked)
        self._emit()

    # ── public ────────────────────────────────────────────────────────

    def load(self, name: str, data: dict) -> None:
        self._loading = True
        self._set_enabled(True)
        self._name_edit.setText(name)
        self._kw_edit.setText(", ".join(data.get("keywords", [])))

        atype = data.get("assignment_type", "complete_incomplete")
        idx = self._type_combo.findData(atype)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self._min_wc.setValue(data.get("min_word_count", 200))
        self._post_wc.setValue(data.get("post_min_words", 150))
        self._reply_wc.setValue(data.get("reply_min_words", 50))

        self._min_replies.setValue(data.get("min_replies", 2))
        self._pts_per_post.setValue(float(data.get("points_per_post", 5.0)))
        self._pts_per_reply.setValue(float(data.get("points_per_reply", 1.0)))
        self._replies_a.setValue(data.get("replies_for_a", 2))
        self._replies_b.setValue(data.get("replies_for_b", 1))
        self._replies_c.setValue(data.get("replies_for_c", 0))

        d_val = data.get("replies_for_d", None)
        d_enabled = d_val is not None
        self._d_enable.setChecked(d_enabled)
        self._replies_d.setValue(d_val if d_val is not None else 0)
        self._replies_d.setEnabled(d_enabled)

        self._loading = False
        self._on_type_changed()

    def clear(self) -> None:
        self._set_enabled(False)
        self._name_edit.clear()
        self._kw_edit.clear()
        self._min_wc.setValue(200)
        self._post_wc.setValue(150)
        self._reply_wc.setValue(50)
        self._min_replies.setValue(2)
        self._pts_per_post.setValue(5.0)
        self._pts_per_reply.setValue(1.0)
        self._replies_a.setValue(2)
        self._replies_b.setValue(1)
        self._replies_c.setValue(0)
        self._d_enable.setChecked(False)
        self._replies_d.setValue(0)
        self._replies_d.setEnabled(False)

    def set_name_readonly(self, readonly: bool) -> None:
        self._name_edit.setReadOnly(readonly)

    def get_name(self) -> str:
        return self._name_edit.text().strip()

    def get_data(self) -> dict:
        kw_raw = self._kw_edit.text()
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
        d_enabled = self._d_enable.isChecked()
        return {
            "assignment_type": self._type_combo.currentData(),
            "min_word_count":  self._min_wc.value(),
            "post_min_words":  self._post_wc.value(),
            "reply_min_words": self._reply_wc.value(),
            "min_replies":     self._min_replies.value(),
            "points_per_post": self._pts_per_post.value(),
            "points_per_reply":self._pts_per_reply.value(),
            "replies_for_a":   self._replies_a.value(),
            "replies_for_b":   self._replies_b.value(),
            "replies_for_c":   self._replies_c.value(),
            "replies_for_d":   self._replies_d.value() if d_enabled else None,
            "keywords":        keywords,
        }


# ---------------------------------------------------------------------------
# _AICForm — right panel
# ---------------------------------------------------------------------------

class _AICForm(QWidget):
    """Academic Integrity Check settings."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_INSET};")
        form = QVBoxLayout(inner)
        form.setContentsMargins(14, 10, 14, 10)
        form.setSpacing(SPACING_SM)

        form.addWidget(_section_header("ACADEMIC INTEGRITY CHECK"))

        self._aic_cb = SwitchToggle("Run AIC on this assignment type")
        self._aic_cb.toggled.connect(self._on_aic_toggled)
        form.addWidget(self._aic_cb)

        # ── AIC group (hidden when toggle is off) ─────────────────────
        self._aic_group = QWidget()
        self._aic_group.setStyleSheet("background: transparent;")
        ag = QVBoxLayout(self._aic_group)
        ag.setContentsMargins(0, 6, 0, 0)
        ag.setSpacing(SPACING_SM)

        # ── Assignment mode ────────────────────────────────────────────
        ag.addWidget(_field_label("Assignment mode"))
        self._aic_profile = CRTComboBox()
        for key, label in AIC_MODE_LABELS.items():
            self._aic_profile.addItem(label, key)
        self._aic_profile.currentIndexChanged.connect(self._on_mode_changed)
        ag.addWidget(self._aic_profile)

        self._mode_desc = QLabel("")
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-style: italic;"
            f" background: transparent; border: none;"
        )
        ag.addWidget(self._mode_desc)

        ag.addWidget(_hsep())

        # ── Behavioral toggles ─────────────────────────────────────────
        ag.addWidget(_field_label("How to read this assignment"))

        self._pva_cb = SwitchToggle("Personal voice is an authenticity signal")
        self._pva_cb.setToolTip(
            "When enabled, first-person voice and emotional language count as evidence\n"
            "of human authorship. Enable for reflections and discussions; disable for\n"
            "formal essays and notes where personal voice isn't expected."
        )
        self._pva_cb.toggled.connect(self._emit)
        ag.addWidget(self._pva_cb)
        ag.addWidget(_subtext(
            "First-person language and personal experience count as real student writing."
        ))

        self._invert_ss_cb = SwitchToggle("Invert sentence structure signals")
        self._invert_ss_cb.setToolTip(
            "When enabled: smooth AI-style prose transitions score higher suspicion;\n"
            "sentence fragments and bullet structure score higher authenticity.\n"
            "Use this for notes and outlines where complete sentences are suspicious."
        )
        self._invert_ss_cb.toggled.connect(self._emit)
        ag.addWidget(self._invert_ss_cb)
        ag.addWidget(_subtext(
            "Treat fragments and bullets as authentic; flag smooth prose as suspicious."
        ))

        ag.addWidget(_hsep())

        # ── Flag threshold ─────────────────────────────────────────────
        ag.addWidget(_field_label("Flag threshold"))

        sc_row = QHBoxLayout()
        sc_row.setSpacing(SPACING_MD)

        sen_col = QVBoxLayout()
        sen_col.setSpacing(3)
        sen_col.addWidget(_field_label("Sensitivity"))
        self._aic_sensitivity = CRTComboBox()
        for key, label in AIC_SENSITIVITY_LABELS.items():
            self._aic_sensitivity.addItem(label, key)
        self._aic_sensitivity.currentIndexChanged.connect(self._emit)
        sen_col.addWidget(self._aic_sensitivity)
        sc_row.addLayout(sen_col)

        ctx_col = QVBoxLayout()
        ctx_col.setSpacing(3)
        ctx_col.addWidget(_field_label("School context"))
        self._aic_context = CRTComboBox()
        for key, label in AIC_CONTEXT_LABELS.items():
            self._aic_context.addItem(label, key)
        self._aic_context.currentIndexChanged.connect(self._emit)
        ctx_col.addWidget(self._aic_context)
        sc_row.addLayout(ctx_col)

        ag.addLayout(sc_row)

        ag.addWidget(_hsep())

        # ── Collapsible signal weights ─────────────────────────────────
        self._adv_btn = QPushButton("▸  Fine-tune signal weights")
        self._adv_btn.setStyleSheet(_ADV_BTN_QSS)
        self._adv_btn.setCheckable(True)
        self._adv_btn.toggled.connect(self._toggle_advanced)
        ag.addWidget(self._adv_btn)

        self._adv_body = QWidget()
        self._adv_body.setStyleSheet("background: transparent;")
        ab = QVBoxLayout(self._adv_body)
        ab.setContentsMargins(0, 4, 0, 0)
        ab.setSpacing(8)

        ab.addWidget(_subtext(
            "Multipliers adjust how strongly each signal type affects the analysis. "
            "1.0 = mode default.  Higher = stronger signal.  Lower = quieter."
        ))

        def _wt_row(lbl_text: str, help_text: str, min_v: float, max_v: float):
            row = QHBoxLayout()
            row.setSpacing(10)
            txt_col = QVBoxLayout()
            txt_col.setSpacing(1)
            name_lbl = QLabel(lbl_text)
            name_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            help_lbl = QLabel(help_text)
            help_lbl.setWordWrap(True)
            help_lbl.setStyleSheet(_SUBTEXT_QSS)
            txt_col.addWidget(name_lbl)
            txt_col.addWidget(help_lbl)
            spin = QDoubleSpinBox()
            spin.setRange(min_v, max_v)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)
            spin.setFixedWidth(70)
            spin.setStyleSheet(_INPUT_QSS)
            spin.valueChanged.connect(self._emit)
            row.addLayout(txt_col, 1)
            row.addWidget(spin, 0, Qt.AlignmentFlag.AlignVCenter)
            return row, spin

        r, self._wt_personal_voice = _wt_row(
            "Personal voice",
            "First-person language, opinion, and emotion",
            0.0, 2.5,
        )
        ab.addLayout(r)

        r, self._wt_ai_patterns = _wt_row(
            "AI patterns",
            "AI-style transitions and generic phrasing",
            0.5, 3.0,
        )
        ab.addLayout(r)

        r, self._wt_course_content = _wt_row(
            "Course content",
            "References to readings and course material",
            0.5, 2.5,
        )
        ab.addLayout(r)

        r, self._wt_rough_work = _wt_row(
            "Rough / draft work",
            "In-progress, imperfect, drafty quality",
            0.5, 2.5,
        )
        ab.addLayout(r)

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        self._reset_wt_btn = QPushButton("Reset to mode defaults")
        self._reset_wt_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._reset_wt_btn.clicked.connect(self._reset_weights)
        reset_row.addWidget(self._reset_wt_btn)
        ab.addLayout(reset_row)

        self._adv_body.setVisible(False)
        ag.addWidget(self._adv_body)

        form.addWidget(self._aic_group)

        # ── Short Submission Review guidance ──────────────────────────────
        form.addWidget(_hsep())
        form.addWidget(_section_header("SHORT SUBMISSION REVIEW"))
        form.addWidget(_field_label("Genre guidance (optional)"))
        form.addWidget(_subtext(
            "Describe the assignment format or engagement expectations. "
            "The AI reviewer uses this when assessing submissions below the word count threshold."
        ))
        self._short_sub_guidance = QPlainTextEdit()
        self._short_sub_guidance.setMaximumHeight(80)
        self._short_sub_guidance.setPlaceholderText(
            "e.g. 'Students write 1–2 paragraph reflections connecting the reading to personal experience.'"
        )
        self._short_sub_guidance.setStyleSheet(
            f"QPlainTextEdit {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 3px; padding: 4px 8px; color: {PHOSPHOR_HOT};"
            f" font-size: {px(12)}px; }}"
            f"QPlainTextEdit:focus {{ border-color: {BORDER_AMBER}; }}"
        )
        self._short_sub_guidance.textChanged.connect(self._emit)
        form.addWidget(self._short_sub_guidance)

        form.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_scroll_wrap(inner))

        self._set_enabled(False)
        self._on_aic_toggled(False)

    # ── helpers ───────────────────────────────────────────────────────

    def _emit(self, *_) -> None:
        if not self._loading:
            self.changed.emit()

    def _set_enabled(self, enabled: bool) -> None:
        for w in (self._aic_cb, self._aic_profile, self._pva_cb, self._invert_ss_cb,
                  self._aic_context, self._aic_sensitivity,
                  self._wt_personal_voice, self._wt_ai_patterns,
                  self._wt_course_content, self._wt_rough_work):
            w.setEnabled(enabled)

    def _on_aic_toggled(self, checked: bool) -> None:
        self._aic_group.setVisible(checked)
        self._emit()

    def _on_mode_changed(self, *_) -> None:
        if self._loading:
            return
        mode = self._aic_profile.currentData() or "auto"
        self._mode_desc.setText(_AIC_MODE_DESCRIPTIONS.get(mode, ""))
        preset = AIC_MODE_WEIGHT_PRESETS.get(mode, AIC_MODE_WEIGHT_PRESETS["auto"])
        for widget in (self._pva_cb, self._invert_ss_cb,
                       self._wt_personal_voice, self._wt_ai_patterns,
                       self._wt_course_content, self._wt_rough_work):
            widget.blockSignals(True)
        self._pva_cb.setChecked(preset["personal_voice_authentic"])
        self._invert_ss_cb.setChecked(preset["invert_sentence_signals"])
        self._wt_personal_voice.setValue(preset["weight_personal_voice"])
        self._wt_ai_patterns.setValue(preset["weight_ai_patterns"])
        self._wt_course_content.setValue(preset["weight_course_content"])
        self._wt_rough_work.setValue(preset["weight_rough_work"])
        for widget in (self._pva_cb, self._invert_ss_cb,
                       self._wt_personal_voice, self._wt_ai_patterns,
                       self._wt_course_content, self._wt_rough_work):
            widget.blockSignals(False)
        self._emit()

    def _toggle_advanced(self, checked: bool) -> None:
        self._adv_body.setVisible(checked)
        self._adv_btn.setText(
            f"{'▾' if checked else '▸'}  Fine-tune signal weights"
        )

    def _reset_weights(self) -> None:
        mode = self._aic_profile.currentData() or "auto"
        preset = AIC_MODE_WEIGHT_PRESETS.get(mode, AIC_MODE_WEIGHT_PRESETS["auto"])
        for widget, key in [
            (self._wt_personal_voice, "weight_personal_voice"),
            (self._wt_ai_patterns,    "weight_ai_patterns"),
            (self._wt_course_content, "weight_course_content"),
            (self._wt_rough_work,     "weight_rough_work"),
        ]:
            widget.blockSignals(True)
            widget.setValue(preset[key])
            widget.blockSignals(False)
        self._emit()

    # ── public ────────────────────────────────────────────────────────

    def load(self, data: dict) -> None:
        self._loading = True
        self._set_enabled(True)

        run_aic = bool(data.get("run_aic", False))
        self._aic_cb.setChecked(run_aic)

        for combo, key, labels in [
            (self._aic_profile,     "aic_mode",        AIC_MODE_LABELS),
            (self._aic_context,     "aic_context",     AIC_CONTEXT_LABELS),
            (self._aic_sensitivity, "aic_sensitivity", AIC_SENSITIVITY_LABELS),
        ]:
            val = data.get(key, list(labels.keys())[0])
            i = combo.findData(val)
            combo.setCurrentIndex(i if i >= 0 else 0)

        mode = self._aic_profile.currentData() or "auto"
        preset = AIC_MODE_WEIGHT_PRESETS.get(mode, AIC_MODE_WEIGHT_PRESETS["auto"])
        self._pva_cb.setChecked(
            bool(data.get("personal_voice_authentic", preset["personal_voice_authentic"]))
        )
        self._invert_ss_cb.setChecked(
            bool(data.get("invert_sentence_signals", preset["invert_sentence_signals"]))
        )
        self._wt_personal_voice.setValue(
            float(data.get("weight_personal_voice", preset["weight_personal_voice"]))
        )
        self._wt_ai_patterns.setValue(
            float(data.get("weight_ai_patterns", preset["weight_ai_patterns"]))
        )
        self._wt_course_content.setValue(
            float(data.get("weight_course_content", preset["weight_course_content"]))
        )
        self._wt_rough_work.setValue(
            float(data.get("weight_rough_work", preset["weight_rough_work"]))
        )
        self._mode_desc.setText(_AIC_MODE_DESCRIPTIONS.get(mode, ""))
        self._short_sub_guidance.setPlainText(data.get("short_sub_guidance", ""))

        self._loading = False
        self._on_aic_toggled(run_aic)

    def clear(self) -> None:
        self._set_enabled(False)
        self._aic_cb.setChecked(False)
        self._pva_cb.setChecked(True)
        self._invert_ss_cb.setChecked(False)
        self._wt_personal_voice.setValue(1.0)
        self._wt_ai_patterns.setValue(1.0)
        self._wt_course_content.setValue(1.0)
        self._wt_rough_work.setValue(1.0)
        self._short_sub_guidance.setPlainText("")

    def get_data(self) -> dict:
        return {
            "run_aic":                  self._aic_cb.isChecked(),
            "aic_mode":                 self._aic_profile.currentData(),
            "personal_voice_authentic": self._pva_cb.isChecked(),
            "invert_sentence_signals":  self._invert_ss_cb.isChecked(),
            "weight_personal_voice":    self._wt_personal_voice.value(),
            "weight_ai_patterns":       self._wt_ai_patterns.value(),
            "weight_course_content":    self._wt_course_content.value(),
            "weight_rough_work":        self._wt_rough_work.value(),
            "aic_context":              self._aic_context.currentData(),
            "aic_sensitivity":          self._aic_sensitivity.currentData(),
            "short_sub_guidance":       self._short_sub_guidance.toPlainText(),
        }


# ---------------------------------------------------------------------------
# TemplateEditorDialog
# ---------------------------------------------------------------------------

class TemplateEditorDialog(QDialog):
    """Modal dialog for viewing and editing assignment templates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Assignment Templates")
        self.setMinimumSize(1020, 560)
        self.resize(1120, 640)
        self.setModal(True)

        self._templates: dict = load_templates()
        self._current_name: Optional[str] = None
        self._dirty = False

        self._build_ui()
        self._populate_list()
        if self._templates:
            first = self._list.item(0)
            if first:
                self._list.setCurrentItem(first)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(SPACING_MD)

        title = QLabel("ASSIGNMENT TEMPLATES")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(15)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        root.addWidget(title)

        sub = QLabel(
            "Templates define grading rules for assignment types. "
            "They are auto-matched to Canvas assignment groups by keyword."
        )
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── Three-panel splitter ───────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {BORDER_DARK}; }}"
            f"QSplitter::handle:hover {{ background: {BORDER_AMBER}; }}"
        )

        # ── Panel 1: Template list ─────────────────────────────────────
        left = QFrame()
        left.setObjectName("templatePane")
        left.setStyleSheet(_PANE_QSS)
        left.setMinimumWidth(220)
        left_lo = QVBoxLayout(left)
        left_lo.setContentsMargins(10, 10, 10, 10)
        left_lo.setSpacing(SPACING_SM)

        list_hdr = QLabel("TEMPLATES")
        list_hdr.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; letter-spacing: 1px;"
            f" background: transparent; border: none;"
        )
        left_lo.addWidget(list_hdr)

        self._list = QListWidget()
        self._list.setStyleSheet(_LIST_QSS)
        self._list.currentItemChanged.connect(self._on_list_selection_changed)
        left_lo.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)

        self._del_btn = QPushButton("Delete")
        self._del_btn.setStyleSheet(_DELETE_BTN_QSS)
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._del_btn)

        btn_row.addStretch()

        self._reset_btn = QPushButton("Defaults")
        self._reset_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._reset_btn.setToolTip(
            "Restore all system default templates to their original settings (keeps custom ones)"
        )
        self._reset_btn.clicked.connect(self._on_reset_defaults)
        btn_row.addWidget(self._reset_btn)

        left_lo.addLayout(btn_row)
        splitter.addWidget(left)

        # ── Panel 2: Basic + Grading ───────────────────────────────────
        middle = QFrame()
        middle.setObjectName("templatePane")
        middle.setStyleSheet(_PANE_QSS)
        mid_lo = QVBoxLayout(middle)
        mid_lo.setContentsMargins(0, 10, 0, 0)
        mid_lo.setSpacing(0)

        mid_hdr_row = QHBoxLayout()
        mid_hdr_row.setContentsMargins(14, 0, 14, 8)
        self._mid_title = QLabel("SELECT A TEMPLATE")
        self._mid_title.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; letter-spacing: 1px;"
            f" background: transparent; border: none;"
        )
        mid_hdr_row.addWidget(self._mid_title)
        mid_hdr_row.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_template)
        mid_hdr_row.addWidget(self._save_btn)
        mid_lo.addLayout(mid_hdr_row)

        sep = make_h_rule()
        mid_lo.addWidget(sep)

        self._basic_form = _BasicGradingForm()
        self._basic_form.changed.connect(self._on_form_changed)
        mid_lo.addWidget(self._basic_form, 1)

        splitter.addWidget(middle)

        # ── Panel 3: AIC ───────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("templatePane")
        right.setStyleSheet(_PANE_QSS)
        right_lo = QVBoxLayout(right)
        right_lo.setContentsMargins(0, 10, 0, 0)
        right_lo.setSpacing(0)

        right_hdr_row = QHBoxLayout()
        right_hdr_row.setContentsMargins(14, 0, 14, 8)
        right_hdr_lbl = QLabel("INTEGRITY CHECK")
        right_hdr_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; letter-spacing: 1px;"
            f" background: transparent; border: none;"
        )
        right_hdr_row.addWidget(right_hdr_lbl)
        right_hdr_row.addStretch()
        right_lo.addLayout(right_hdr_row)

        sep2 = make_h_rule()
        right_lo.addWidget(sep2)

        self._aic_form = _AICForm()
        self._aic_form.changed.connect(self._on_form_changed)
        right_lo.addWidget(self._aic_form, 1)

        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([250, 330, 350])

        root.addWidget(splitter, 1)

        # ── Footer ─────────────────────────────────────────────────────
        root.addWidget(make_h_rule())

        footer = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;"
        )
        footer.addWidget(self._status_lbl)
        footer.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_SMALL_BTN_QSS)
        close_btn.clicked.connect(self._on_close)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _populate_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        all_names = sorted(self._templates.keys())
        sys_names  = [n for n in all_names if n in SYSTEM_DEFAULT_NAMES]
        user_names = [n for n in all_names if n not in SYSTEM_DEFAULT_NAMES]
        for name in sys_names:
            item = QListWidgetItem(name)
            item.setForeground(QColor(PHOSPHOR_GLOW))
            item.setToolTip("System default — can be edited but not deleted or renamed")
            self._list.addItem(item)
        for name in user_names:
            item = QListWidgetItem(name)
            item.setForeground(QColor(PHOSPHOR_DIM))
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _select_name(self, name: str) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).text() == name:
                self._list.setCurrentRow(i)
                return

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_list_selection_changed(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        if self._dirty and previous:
            reply = show_question(
                self, "Unsaved Changes",
                f"Save changes to '{previous.text()}' before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._commit_save(previous.text())
            elif reply == QMessageBox.StandardButton.Cancel:
                self._list.blockSignals(True)
                self._list.setCurrentItem(previous)
                self._list.blockSignals(False)
                return

        if current:
            name = current.text()
            self._current_name = name
            data = self._templates.get(name, {})
            is_sys = name in SYSTEM_DEFAULT_NAMES
            self._basic_form.load(name, data)
            self._aic_form.load(data)
            self._basic_form.set_name_readonly(is_sys)
            suffix = "  ·  SYSTEM DEFAULT" if is_sys else ""
            self._mid_title.setText(f"{name.upper()}{suffix}")
            self._del_btn.setEnabled(not is_sys)
            self._save_btn.setEnabled(False)
            self._dirty = False
        else:
            self._current_name = None
            self._basic_form.clear()
            self._aic_form.clear()
            self._mid_title.setText("SELECT A TEMPLATE")
            self._del_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._dirty = False

    def _on_form_changed(self) -> None:
        if self._current_name is not None:
            self._dirty = True
            self._save_btn.setEnabled(True)

    def _on_save_template(self) -> None:
        if self._current_name is None:
            return
        new_name = self._basic_form.get_name()
        if not new_name:
            self._flash_status("Template name cannot be empty.", error=True)
            return
        self._commit_save(self._current_name, new_name=new_name)

    def _commit_save(self, old_name: str, new_name: Optional[str] = None) -> None:
        if new_name is None:
            new_name = old_name
        data = {**self._basic_form.get_data(), **self._aic_form.get_data()}
        if new_name != old_name and old_name in self._templates:
            del self._templates[old_name]
        self._templates[new_name] = data
        save_templates(self._templates)
        self._current_name = new_name
        self._dirty = False
        self._save_btn.setEnabled(False)
        self._populate_list()
        self._select_name(new_name)
        self._flash_status(f"'{new_name}' saved.", error=False)

    def _on_add(self) -> None:
        base = "New Template"
        name = base
        count = 1
        while name in self._templates:
            name = f"{base} {count}"
            count += 1
        self._templates[name] = dict(TEMPLATE_FIELD_DEFAULTS)
        save_templates(self._templates)
        self._populate_list()
        self._select_name(name)
        self._flash_status(f"'{name}' created. Edit and save.", error=False)

    def _on_delete(self) -> None:
        if not self._current_name:
            return
        name = self._current_name
        if name in SYSTEM_DEFAULT_NAMES:
            return
        reply = show_question(
            self, "Delete Template",
            f"Delete '{name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._templates[name]
        save_templates(self._templates)
        self._current_name = None
        self._dirty = False
        self._populate_list()
        self._basic_form.clear()
        self._aic_form.clear()
        self._mid_title.setText("SELECT A TEMPLATE")
        self._del_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._flash_status(f"'{name}' deleted.", error=False)

    def _on_reset_defaults(self) -> None:
        reply = show_question(
            self, "Restore System Defaults",
            "Restore all system default templates to their original settings?\n\n"
            "Personal / Reflection, Formal Essay / Research, Draft, Outline, "
            "Reading Notes, Discussion Post (C/I), "
            "Discussion Forum (Points), Discussion Forum (Letter Grade)\n\n"
            "Your custom templates will not be affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for name, data in DEFAULT_TEMPLATES.items():
            self._templates[name] = dict(data)
        save_templates(self._templates)
        self._populate_list()
        self._flash_status("System default templates restored.", error=False)

    def _on_close(self) -> None:
        if self._dirty:
            reply = show_question(
                self, "Unsaved Changes",
                "You have unsaved changes. Close anyway?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                return
        self.accept()

    def _flash_status(self, msg: str, error: bool = False) -> None:
        color = BURN_RED if error else TERM_GREEN
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: {px(11)}px; background: transparent;"
        )
