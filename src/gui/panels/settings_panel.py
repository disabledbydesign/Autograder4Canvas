"""
Settings tab — redesigned to match the amber terminal aesthetic.

Layout:
  ┌─ CANVAS CONNECTION ────────┬─ DATA RETENTION ──────────────┐
  │  profile, URL, token, test │  auto-delete + category chips │
  │  AIC calibration           │                               │
  └────────────────────────────┴───────────────────────────────┘
                                              [Save Settings ▶]
"""
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar,
    QComboBox, QSpinBox, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer

from gui.widgets.crt_combo import CRTComboBox
from gui.widgets.phosphor_chip import PhosphorChip
from gui.widgets.switch_toggle import SwitchToggle

_EDU_LEVEL_OPTIONS = [
    ("community_college", "Community College  (default)"),
    ("high_school",       "High School"),
    ("four_year",         "Four-Year College / Liberal Arts"),
    ("university",        "Research University"),
    ("online",            "Online / Distance Learning"),
]

# ESL enrollment rates: low < 10%, moderate 10–25%, high > 25%
_ESL_LEVEL_OPTIONS = [
    ("none",     "Default"),
    ("low",      "Low  (< 10% of enrollment)"),
    ("moderate", "Moderate  (10–25%)"),
    ("high",     "High  (> 25%)"),
]

# First-generation college student rates: low < 20%, moderate 20–45%, high > 45%
_FIRST_GEN_LEVEL_OPTIONS = [
    ("none",     "Default"),
    ("low",      "Low  (< 20% of enrollment)"),
    ("moderate", "Moderate  (20–45%)"),
    ("high",     "High  (> 45%)"),
]

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    BG_VOID, BG_INSET, BORDER_DARK,
    STATUS_OK, STATUS_ERR, STATUS_WARN,
    BORDER_AMBER, AMBER_BTN,
    make_run_button, make_secondary_button,
    make_section_label, make_h_rule, make_content_pane,
)

# ---------------------------------------------------------------------------
# Small local helpers
# ---------------------------------------------------------------------------

def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-weight: 500;"
        f" letter-spacing: 0.8px; background: transparent; border: none;"
        f" text-transform: uppercase;"
    )
    return lbl


# ---------------------------------------------------------------------------
# SettingsPanel
# ---------------------------------------------------------------------------

class SettingsPanel(QWidget):
    """Settings page — Canvas connection, output, data retention, grading defaults."""

    settings_saved = Signal()

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(800)  # debounce 800ms
        self._autosave_timer.timeout.connect(self._on_save)
        self._setup_ui()
        self._load_current_settings()
        self._connect_autosave()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll, 1)

        page = QWidget()
        page.setObjectName("settingsPage")
        page.setStyleSheet(f"QWidget#settingsPage {{ background: {BG_VOID}; }}")
        scroll.setWidget(page)

        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        vbox.setSpacing(SPACING_MD)

        # Page header
        title = QLabel("SETTINGS")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        sub = QLabel("Configure Canvas connection and data retention.")
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        vbox.addWidget(title)
        vbox.addWidget(sub)
        vbox.addWidget(make_h_rule())

        # Two-column row: left = Canvas Connection, right = Output + Grading Defaults + Data Retention
        cols = QHBoxLayout()
        cols.setSpacing(SPACING_MD)

        left_pane = make_content_pane("settingsConnPane")
        left_lo = QVBoxLayout(left_pane)
        left_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        left_lo.setSpacing(SPACING_SM)
        self._build_connection_section(left_lo)
        cols.addWidget(left_pane, stretch=3)
        left_pane.setMaximumWidth(520)

        right_col = QVBoxLayout()
        right_col.setSpacing(SPACING_SM)

        ret_pane = make_content_pane("settingsRetPane")
        ret_lo = QVBoxLayout(ret_pane)
        ret_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        ret_lo.setSpacing(SPACING_SM)
        self._build_retention_section(ret_lo)
        right_col.addWidget(ret_pane)

        acc_pane = make_content_pane("settingsAccPane")
        acc_lo = QVBoxLayout(acc_pane)
        acc_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        acc_lo.setSpacing(SPACING_SM)
        self._build_accessibility_section(acc_lo)
        right_col.addWidget(acc_pane)

        right_col.addStretch()
        cols.addLayout(right_col, stretch=1)
        vbox.addLayout(cols)

        # Engagement Analysis pane (full-width, between connection and insights)
        aic_pane = make_content_pane("settingsAICPane")
        aic_lo = QVBoxLayout(aic_pane)
        aic_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        aic_lo.setSpacing(SPACING_SM)
        self._build_engagement_section(aic_lo)
        vbox.addWidget(aic_pane)

        # Insights & AI section (full-width below the two columns)
        insights_pane = make_content_pane("settingsInsightsPane")
        ins_lo = QVBoxLayout(insights_pane)
        ins_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        ins_lo.setSpacing(SPACING_SM)
        self._build_insights_section(ins_lo)
        vbox.addWidget(insights_pane)

        vbox.addStretch()

        # Footer lives OUTSIDE the scroll area so QGraphicsDropShadowEffect
        # is not clipped by the scroll viewport — matches assignment_panel pattern.
        from PySide6.QtWidgets import QFrame as _QFrame
        footer_sep = _QFrame()
        footer_sep.setFixedHeight(1)
        footer_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        root.addWidget(footer_sep)

        footer_bar = _QFrame()
        footer_bar.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        footer_lo = QHBoxLayout(footer_bar)
        footer_lo.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        self._save_status = QLabel("")
        self._save_status.setStyleSheet(
            f"font-size: {px(11)}px; background: transparent; border: none;"
        )
        footer_lo.addStretch()
        footer_lo.addWidget(self._save_status)
        footer_lo.addSpacing(SPACING_SM)
        save_btn = QPushButton("▶  Save Settings")
        save_btn.clicked.connect(self._on_save)
        make_run_button(save_btn)
        footer_lo.addWidget(save_btn)
        root.addWidget(footer_bar)

    def _build_connection_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Canvas Connection"))
        lo.addWidget(make_h_rule())

        # Profile first
        lo.addWidget(_field_label("Institution Profile"))
        profile_row = QHBoxLayout()
        self._profile_combo = CRTComboBox()
        self._profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_switched)
        profile_row.addWidget(self._profile_combo)
        manage_btn = QPushButton("Manage Profiles…")
        make_secondary_button(manage_btn)
        manage_btn.clicked.connect(self._on_manage_profiles)
        profile_row.addWidget(manage_btn)
        lo.addLayout(profile_row)

        lo.addWidget(make_h_rule())

        lo.addWidget(_field_label("Canvas URL"))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://yourschool.instructure.com")
        lo.addWidget(self._url_edit)

        lo.addSpacing(4)
        lo.addWidget(_field_label("API Token"))
        token_row = QHBoxLayout()
        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("Paste your API token here")
        token_row.addWidget(self._token_edit)
        self._test_btn = QPushButton("Test Connection")
        make_secondary_button(self._test_btn)
        self._test_btn.clicked.connect(self._on_test_connection)
        token_row.addWidget(self._test_btn)
        lo.addLayout(token_row)

        self._test_status = QLabel("")
        self._test_status.setStyleSheet(f"font-size: {px(12)}px; padding: 2px 0; background: transparent;")
        lo.addWidget(self._test_status)

    def _build_engagement_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Engagement Analysis — Per-Profile Calibration"))
        lo.addWidget(make_h_rule())
        aic_note = QLabel(
            "These settings travel with the institution profile. "
            "Weights adjust to your school's specific student population."
        )
        aic_note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent; padding: 2px 0;"
        )
        aic_note.setWordWrap(True)
        lo.addWidget(aic_note)

        lo.addWidget(_field_label("Education Level"))
        self._edu_level_combo = CRTComboBox()
        self._edu_level_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._edu_level_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _EDU_LEVEL_OPTIONS:
            self._edu_level_combo.addItem(plabel, pid)
        edu_row = QHBoxLayout()
        edu_row.addWidget(self._edu_level_combo)
        edu_row.addStretch()
        lo.addLayout(edu_row)

        lo.addSpacing(4)
        pop_row = QHBoxLayout()
        pop_row.setSpacing(16)

        esl_col = QVBoxLayout()
        esl_col.setSpacing(2)
        esl_col.addWidget(_field_label("ESL Population"))
        self._pop_esl_combo = CRTComboBox()
        self._pop_esl_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._pop_esl_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _ESL_LEVEL_OPTIONS:
            self._pop_esl_combo.addItem(plabel, pid)
        esl_col.addWidget(self._pop_esl_combo)
        pop_row.addLayout(esl_col)

        fg_col = QVBoxLayout()
        fg_col.setSpacing(2)
        fg_col.addWidget(_field_label("First-Gen Population"))
        self._pop_first_gen_combo = CRTComboBox()
        self._pop_first_gen_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._pop_first_gen_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _FIRST_GEN_LEVEL_OPTIONS:
            self._pop_first_gen_combo.addItem(plabel, pid)
        fg_col.addWidget(self._pop_first_gen_combo)
        pop_row.addLayout(fg_col)

        pop_row.addStretch()
        lo.addLayout(pop_row)

        lo.addSpacing(4)
        self._pop_nd_check = SwitchToggle("Neurodivergent-aware scoring", wrap_width=400)
        lo.addWidget(self._pop_nd_check)

        lo.addSpacing(8)
        tune_btn = QPushButton("Fine-Tune Signals…")
        make_secondary_button(tune_btn)
        tune_btn.clicked.connect(self._on_open_signal_tuning)
        tune_row = QHBoxLayout()
        tune_row.addWidget(tune_btn)
        tune_row.addStretch()
        lo.addLayout(tune_row)

    def _build_insights_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Insights"))
        lo.addWidget(make_h_rule())

        # Setup wizard launch row
        wiz_row = QHBoxLayout()
        wiz_row.setSpacing(SPACING_SM)
        wiz_desc = QLabel(
            "Configure the AI models used by Generate Insights.\n"
            "Local models keep student data on your machine (FERPA-safe)."
        )
        wiz_desc.setWordWrap(True)
        wiz_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        wiz_row.addWidget(wiz_desc, 1)
        wiz_btn = QPushButton("Run Setup Wizard\u2026")
        make_secondary_button(wiz_btn)
        wiz_btn.clicked.connect(self._on_launch_insights_wizard)
        wiz_row.addWidget(wiz_btn)
        lo.addLayout(wiz_row)

        # Two-column: left = local model, right = cloud/institutional
        cols = QHBoxLayout()
        cols.setSpacing(SPACING_LG)

        # ── Left: Local Model ──
        left = QVBoxLayout()
        left.setSpacing(SPACING_SM)

        left.addWidget(_field_label("Local Model Backend"))
        self._llm_backend_combo = CRTComboBox()
        from gui.dialogs.insights_setup_dialog import _is_apple_silicon
        if _is_apple_silicon():
            self._llm_backend_combo.addItem("MLX (Apple Silicon — recommended)", "mlx")
            self._llm_backend_combo.addItem("Ollama", "ollama")
        else:
            self._llm_backend_combo.addItem("Ollama", "ollama")
        self._llm_backend_combo.currentIndexChanged.connect(
            self._on_llm_backend_changed
        )
        left.addWidget(self._llm_backend_combo)

        # -- MLX model fields (shown when MLX selected) --
        self._mlx_text_label = _field_label("MLX Text Model")
        left.addWidget(self._mlx_text_label)
        self._mlx_text_edit = QLineEdit()
        self._mlx_text_edit.setPlaceholderText("mlx-community/Qwen2.5-7B-Instruct-4bit")
        self._mlx_text_edit.setText("mlx-community/Qwen2.5-7B-Instruct-4bit")
        left.addWidget(self._mlx_text_edit)

        self._mlx_vision_label = _field_label("MLX Vision Model")
        left.addWidget(self._mlx_vision_label)
        self._mlx_vision_edit = QLineEdit()
        self._mlx_vision_edit.setPlaceholderText("mlx-community/Qwen2.5-VL-3B-Instruct-4bit")
        self._mlx_vision_edit.setText("mlx-community/Qwen2.5-VL-3B-Instruct-4bit")
        left.addWidget(self._mlx_vision_edit)

        # -- Ollama model fields (shown when Ollama selected) --
        self._ollama_model_label = _field_label("Ollama Text Model")
        left.addWidget(self._ollama_model_label)
        self._llm_model_edit = QLineEdit()
        self._llm_model_edit.setPlaceholderText("llama3.1:8b")
        self._llm_model_edit.setText("llama3.1:8b")
        left.addWidget(self._llm_model_edit)

        self._ollama_url_label = _field_label("Ollama URL")
        left.addWidget(self._ollama_url_label)
        self._ollama_url_edit = QLineEdit()
        self._ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self._ollama_url_edit.setText("http://localhost:11434")
        left.addWidget(self._ollama_url_edit)

        # Status check
        self._llm_status = QLabel("")
        self._llm_status.setStyleSheet(
            f"font-size: {px(11)}px; background: transparent; border: none;"
        )
        left.addWidget(self._llm_status)

        btn_row = QHBoxLayout()
        check_btn = QPushButton("Check Model")
        make_secondary_button(check_btn)
        check_btn.clicked.connect(self._check_llm_status)
        btn_row.addWidget(check_btn)

        self._install_mlx_btn = QPushButton("Install MLX")
        make_secondary_button(self._install_mlx_btn)
        self._install_mlx_btn.setVisible(False)
        self._install_mlx_btn.clicked.connect(self._install_mlx)
        btn_row.addWidget(self._install_mlx_btn)
        btn_row.addStretch()
        left.addLayout(btn_row)

        left.addStretch()
        cols.addLayout(left, stretch=1)

        # ── Right: Cloud / Institutional API ──
        right = QVBoxLayout()
        right.setSpacing(SPACING_SM)

        right.addWidget(_field_label("Institutional / Cloud API (optional)"))
        _cloud_desc = QLabel(
            "If your institution provides an AI API, configure it here. "
            "Used for Medium and Deep Thinking analysis tiers. "
            "Check with your IT department for FERPA compliance."
        )
        _cloud_desc.setWordWrap(True)
        _cloud_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        right.addWidget(_cloud_desc)

        right.addWidget(_field_label("API Base URL"))
        self._cloud_url_edit = QLineEdit()
        self._cloud_url_edit.setPlaceholderText(
            "e.g., https://your-institution.openai.azure.com/v1"
        )
        right.addWidget(self._cloud_url_edit)

        right.addWidget(_field_label("API Key"))
        self._cloud_key_edit = QLineEdit()
        self._cloud_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_key_edit.setPlaceholderText("Paste institutional API key")
        right.addWidget(self._cloud_key_edit)

        right.addWidget(_field_label("Model Name"))
        self._cloud_model_edit = QLineEdit()
        self._cloud_model_edit.setPlaceholderText("e.g., gpt-4o, claude-sonnet-4-20250514")
        right.addWidget(self._cloud_model_edit)

        self._ferpa_label = QLabel(
            "⚠ Cloud APIs send student text to external servers.\n"
            "Only use if your institution has a data processing agreement."
        )
        self._ferpa_label.setWordWrap(True)
        self._ferpa_label.setStyleSheet(
            f"color: {STATUS_WARN}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 4px 0;"
        )
        right.addWidget(self._ferpa_label)

        right.addStretch()
        cols.addLayout(right, stretch=1)

        lo.addLayout(cols)

        # ── Deepening pass toggle ──
        lo.addWidget(make_h_rule())
        dp_row = QHBoxLayout()
        dp_row.setSpacing(SPACING_SM)
        dp_row.addWidget(_field_label("Deepening Pass"))
        self._deepening_toggle = SwitchToggle(
            "Re-examine flagged students", wrap_width=200
        )
        dp_row.addWidget(self._deepening_toggle)
        dp_row.addStretch()
        lo.addLayout(dp_row)
        desc = QLabel(
            "Refines concern accuracy by asking the model to reconsider "
            "flagged passages. Adds ~30s per flagged student."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" font-style: italic; background: transparent; padding-left: 44px;"
        )
        lo.addWidget(desc)

        # ── Bottom row: throttle + whisper ──
        lo.addWidget(make_h_rule())
        bottom = QHBoxLayout()
        bottom.setSpacing(SPACING_LG)

        # Throttle
        throttle_col = QVBoxLayout()
        throttle_col.addWidget(_field_label("Pause Between Prompts"))
        self._throttle_spin = QSpinBox()
        self._throttle_spin.setRange(0, 30)
        self._throttle_spin.setValue(0)
        self._throttle_spin.setSuffix(" seconds")
        throttle_col.addWidget(self._throttle_spin)
        _throttle_desc = QLabel(
            "How long to pause between AI prompts. "
            "0 = fastest (best for overnight / while you sleep). "
            "10–15 keeps your computer responsive if you're still working while the analysis runs."
        )
        _throttle_desc.setWordWrap(True)
        _throttle_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        throttle_col.addWidget(_throttle_desc)
        bottom.addLayout(throttle_col, stretch=1)

        # Whisper model
        whisper_col = QVBoxLayout()
        whisper_col.addWidget(_field_label("Whisper Model (Audio Transcription)"))
        self._whisper_combo = CRTComboBox()
        self._whisper_combo.addItem("tiny — fastest, lowest quality", "tiny")
        self._whisper_combo.addItem("base — compact, ~150MB", "base")
        self._whisper_combo.addItem("small — better quality, ~500MB", "small")
        self._whisper_combo.addItem("medium — high quality, ~1.5GB (recommended)", "medium")
        self._whisper_combo.addItem("large-v3 — best quality, ~3GB", "large-v3")
        self._whisper_combo.addItem("large-v3-turbo — large quality, faster, ~1.5GB", "large-v3-turbo")
        self._whisper_combo.setCurrentIndex(3)  # medium
        whisper_col.addWidget(self._whisper_combo)
        _whisper_desc = QLabel(
            "Used for transcribing audio/video submissions. Runs locally — no audio data leaves your machine."
        )
        _whisper_desc.setWordWrap(True)
        _whisper_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        whisper_col.addWidget(_whisper_desc)
        bottom.addLayout(whisper_col, stretch=1)

        # Keep Awake
        awake_col = QVBoxLayout()
        awake_col.addWidget(_field_label("Overnight Analysis"))
        self._keep_awake_toggle = SwitchToggle(
            "Keep awake while analysis runs", wrap_width=220
        )
        self._keep_awake_toggle.setChecked(True)
        awake_col.addWidget(self._keep_awake_toggle)
        import platform
        if platform.system() == "Darwin":
            awake_note = (
                "Prevents your Mac from sleeping during analysis. "
                "For lid-closed operation: enable 'Prevent sleeping when display is off' "
                "in System Settings → Battery → Options, and keep the computer plugged in."
            )
        elif platform.system() == "Windows":
            awake_note = (
                "Disables sleep while analysis runs (AC power). "
                "Normal sleep settings are restored when done."
            )
        else:
            awake_note = (
                "Prevents system sleep while analysis runs. "
                "Uses systemd-inhibit if available."
            )
        _awake_desc = QLabel(awake_note)
        _awake_desc.setWordWrap(True)
        _awake_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        awake_col.addWidget(_awake_desc)
        bottom.addLayout(awake_col, stretch=1)

        lo.addLayout(bottom)

        # ── Draft Feedback toggle ──
        lo.addWidget(make_h_rule())
        fb_row = QHBoxLayout()
        fb_row.setSpacing(SPACING_SM)
        fb_row.addWidget(_field_label("Draft Student Feedback"))
        self._draft_feedback_toggle = SwitchToggle(
            "Generate draft feedback for each student", wrap_width=400
        )
        fb_row.addWidget(self._draft_feedback_toggle)
        fb_row.addStretch()
        lo.addLayout(fb_row)
        _fb_desc = QLabel(
            "When enabled, the insights pipeline drafts personalized feedback for each student "
            "based on your analysis lens. You review and approve each draft before anything is posted."
        )
        _fb_desc.setWordWrap(True)
        _fb_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        lo.addWidget(_fb_desc)

    def _on_llm_backend_changed(self, index: int) -> None:
        is_ollama = self._llm_backend_combo.currentData() == "ollama"
        is_mlx = not is_ollama
        # Ollama fields
        self._ollama_model_label.setVisible(is_ollama)
        self._llm_model_edit.setVisible(is_ollama)
        self._ollama_url_label.setVisible(is_ollama)
        self._ollama_url_edit.setVisible(is_ollama)
        # MLX fields
        self._mlx_text_label.setVisible(is_mlx)
        self._mlx_text_edit.setVisible(is_mlx)
        self._mlx_vision_label.setVisible(is_mlx)
        self._mlx_vision_edit.setVisible(is_mlx)
        self._install_mlx_btn.setVisible(False)
        self._llm_status.setText("")

    def _check_llm_status(self) -> None:
        """Test if the configured LLM backend is reachable."""
        import requests as _req
        backend = self._llm_backend_combo.currentData()
        if backend == "ollama":
            url = self._ollama_url_edit.text().strip() or "http://localhost:11434"
            model = self._llm_model_edit.text().strip() or "llama3.1:8b"
            try:
                r = _req.get(f"{url}/api/tags", timeout=5)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    if any(m == model or m.startswith(model.split(":")[0])
                           for m in models):
                        self._llm_status.setText(f"✓ {model} available")
                        self._llm_status.setStyleSheet(
                            f"color: {STATUS_OK}; font-size: {px(11)}px;"
                            f" background: transparent; border: none;"
                        )
                    else:
                        available = ", ".join(models[:5])
                        self._llm_status.setText(
                            f"✗ {model} not found. Available: {available}"
                        )
                        self._llm_status.setStyleSheet(
                            f"color: {STATUS_ERR}; font-size: {px(11)}px;"
                            f" background: transparent; border: none;"
                        )
                else:
                    self._llm_status.setText("✗ Ollama not responding")
                    self._llm_status.setStyleSheet(
                        f"color: {STATUS_ERR}; font-size: {px(11)}px;"
                        f" background: transparent; border: none;"
                    )
            except Exception:
                self._llm_status.setText(
                    "✗ Cannot reach Ollama. Is it running? "
                    "(Terminal: ollama serve)"
                )
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_ERR}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
        elif backend == "mlx":
            from gui.dialogs.insights_setup_dialog import _check_mlx
            if _check_mlx():
                self._llm_status.setText("✓ MLX available")
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_OK}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                self._install_mlx_btn.setVisible(False)
            else:
                self._llm_status.setText(
                    "✗ mlx-lm not installed"
                )
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_ERR}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )
                self._install_mlx_btn.setVisible(True)

    def _install_mlx(self) -> None:
        """Install mlx-lm in-app using the setup dialog's installer."""
        from gui.dialogs.insights_setup_dialog import (
            _InstallerWorker, _is_externally_managed,
        )

        install_mode = "global"
        if _is_externally_managed():
            from PySide6.QtWidgets import QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle("Install MLX")
            dlg.setFixedWidth(480)
            dlg.setStyleSheet(f"QDialog {{ background: {BG_CARD}; }}")
            lo = QVBoxLayout(dlg)
            lo.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
            lo.setSpacing(SPACING_MD)

            title = QLabel("HOMEBREW PYTHON DETECTED")
            title.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px;"
                f" font-weight: bold; letter-spacing: 2px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(title)

            desc = QLabel(
                "Your Python is managed by Homebrew (PEP 668), which "
                "restricts direct package installs. Choose where to "
                "install the MLX framework:"
            )
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(desc)

            lo.addWidget(make_h_rule())

            # Option 1: Global
            g_title = QLabel("Install Globally")
            g_title.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" font-weight: bold; background: transparent; border: none;"
            )
            lo.addWidget(g_title)
            g_desc = QLabel(
                "Runs: pip install --break-system-packages mlx-lm\n"
                "Installs alongside your other Python packages."
            )
            g_desc.setWordWrap(True)
            g_desc.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(g_desc)

            lo.addSpacing(SPACING_SM)

            # Option 2: App Venv
            v_title = QLabel("Install in App Venv")
            v_title.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" font-weight: bold; background: transparent; border: none;"
            )
            lo.addWidget(v_title)
            v_desc = QLabel(
                "Creates an isolated virtual environment at:\n"
                "~/.autograder4canvas/venv/\n"
                "Keeps your system Python untouched."
            )
            v_desc.setWordWrap(True)
            v_desc.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(v_desc)

            lo.addWidget(make_h_rule())

            # Buttons: [Install Globally] [Cancel] [Install in App Venv]
            btn_row = QHBoxLayout()
            btn_row.setSpacing(SPACING_SM)
            global_btn = QPushButton("Install Globally")
            make_run_button(global_btn)
            cancel_btn = QPushButton("Cancel")
            make_secondary_button(cancel_btn)
            venv_btn = QPushButton("Install in App Venv")
            make_secondary_button(venv_btn)
            btn_row.addWidget(global_btn)
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(venv_btn)
            lo.addLayout(btn_row)

            result = {"mode": None}
            global_btn.clicked.connect(lambda: (result.update(mode="global"), dlg.accept()))
            venv_btn.clicked.connect(lambda: (result.update(mode="venv"), dlg.accept()))
            cancel_btn.clicked.connect(dlg.reject)

            if dlg.exec() != QDialog.Accepted or result["mode"] is None:
                return
            install_mode = result["mode"]

        self._install_mlx_btn.setEnabled(False)
        self._install_mlx_btn.setText("Installing…")
        self._mlx_worker = _InstallerWorker("mlx_install", install_mode)
        self._mlx_worker.progress.connect(
            lambda msg: self._llm_status.setText(msg)
        )
        self._mlx_worker.finished.connect(self._on_mlx_install_done)
        self._mlx_worker.start()

    def _on_mlx_install_done(self, success: bool, msg: str) -> None:
        self._install_mlx_btn.setText("Install MLX")
        self._install_mlx_btn.setEnabled(True)
        if success:
            self._llm_status.setText(f"✓ {msg}")
            self._llm_status.setStyleSheet(
                f"color: {STATUS_OK}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            self._install_mlx_btn.setVisible(False)
        else:
            self._llm_status.setText(f"✗ {msg}")
            self._llm_status.setStyleSheet(
                f"color: {STATUS_ERR}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )

    def _build_retention_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Data Retention"))
        lo.addWidget(make_h_rule())

        desc = QLabel(
            "Grading, AIC, and Insights data are stored internally. "
            "Auto-delete aged records on each app launch."
        )
        desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; padding: 2px 0;"
        )
        desc.setWordWrap(True)
        lo.addWidget(desc)

        # Auto-delete master toggle
        self._retention_enabled_cb = SwitchToggle("Auto-delete internal data", wrap_width=160)
        lo.addWidget(self._retention_enabled_cb)

        # Threshold: years + days
        age_row = QHBoxLayout()
        age_row.addSpacing(43)
        older_lbl = QLabel("older than")
        older_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;"
        )
        age_row.addWidget(older_lbl)

        self._retention_years = QSpinBox()
        self._retention_years.setRange(0, 10)
        self._retention_years.setValue(0)
        age_row.addWidget(self._retention_years)
        yr_lbl = QLabel("years")
        yr_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;")
        age_row.addWidget(yr_lbl)

        self._retention_days = QSpinBox()
        self._retention_days.setRange(0, 364)
        self._retention_days.setValue(180)
        age_row.addWidget(self._retention_days)
        days_lbl = QLabel("days")
        days_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;")
        age_row.addWidget(days_lbl)
        age_row.addStretch()
        lo.addLayout(age_row)

        # Category selection chips
        cats_row = QHBoxLayout()
        cats_row.addSpacing(43)
        self._retention_grading_cb = PhosphorChip("Grading Reports", accent="amber")
        self._retention_grading_cb.setChecked(True)
        cats_row.addWidget(self._retention_grading_cb)
        cats_row.addSpacing(6)
        self._retention_aic_cb = PhosphorChip("AIC Data", accent="amber")
        self._retention_aic_cb.setChecked(True)
        cats_row.addWidget(self._retention_aic_cb)
        cats_row.addSpacing(6)
        self._retention_insights_cb = PhosphorChip("Insights Data", accent="amber")
        self._retention_insights_cb.setChecked(True)
        cats_row.addWidget(self._retention_insights_cb)
        cats_row.addStretch()
        lo.addLayout(cats_row)

        # Teacher notes — separate toggle + its own timer
        self._retention_notes_cb = SwitchToggle("Also delete teacher notes", wrap_width=180)
        self._retention_notes_cb.setChecked(False)
        lo.addWidget(self._retention_notes_cb)

        self._notes_age_row = QHBoxLayout()
        self._notes_age_row_widgets = []   # track for enable/disable
        self._notes_age_row.addSpacing(43)
        notes_older_lbl = QLabel("notes older than")
        notes_older_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;")
        self._notes_age_row.addWidget(notes_older_lbl)
        self._notes_age_row_widgets.append(notes_older_lbl)

        self._retention_notes_years = QSpinBox()
        self._retention_notes_years.setRange(0, 10)
        self._retention_notes_years.setValue(3)
        self._notes_age_row.addWidget(self._retention_notes_years)
        self._notes_age_row_widgets.append(self._retention_notes_years)
        notes_yr_lbl = QLabel("years")
        notes_yr_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;")
        self._notes_age_row.addWidget(notes_yr_lbl)
        self._notes_age_row_widgets.append(notes_yr_lbl)

        self._retention_notes_days = QSpinBox()
        self._retention_notes_days.setRange(0, 364)
        self._retention_notes_days.setValue(0)
        self._notes_age_row.addWidget(self._retention_notes_days)
        self._notes_age_row_widgets.append(self._retention_notes_days)
        notes_days_lbl = QLabel("days")
        notes_days_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;")
        self._notes_age_row.addWidget(notes_days_lbl)
        self._notes_age_row_widgets.append(notes_days_lbl)
        self._notes_age_row.addStretch()
        lo.addLayout(self._notes_age_row)

        self._retention_notes_cb.toggled.connect(self._on_notes_retention_toggled)
        self._on_notes_retention_toggled(False)

        self._retention_enabled_cb.toggled.connect(self._on_retention_toggled)
        self._on_retention_toggled(self._retention_enabled_cb.isChecked())

        lo.addStretch()
        lo.addWidget(make_h_rule())

        cleanup_row = QHBoxLayout()
        cleanup_row.addStretch()
        cleanup_btn = QPushButton("Clean Up Now\u2026")
        cleanup_btn.clicked.connect(self._on_run_cleanup)
        make_secondary_button(cleanup_btn)
        cleanup_row.addWidget(cleanup_btn)
        lo.addLayout(cleanup_row)

    def _build_accessibility_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Accessibility"))
        lo.addWidget(make_h_rule())

        lo.addWidget(_field_label("Text Size"))
        self._text_size_combo = CRTComboBox()
        self._text_size_combo.addItem("Small", 1.0)
        self._text_size_combo.addItem("Default", 1.25)
        self._text_size_combo.addItem("Large", 1.5)
        lo.addWidget(self._text_size_combo)

        note = QLabel("Takes effect after saving and restarting.")
        note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        note.setWordWrap(True)
        lo.addWidget(note)

        lo.addSpacing(SPACING_SM)
        lo.addWidget(make_section_label("Warnings"))
        lo.addWidget(make_h_rule())

        warn_row = QHBoxLayout()
        warn_lbl = QLabel("Warn when grades will be reinterpreted")
        warn_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        warn_lbl.setWordWrap(True)
        self._warn_reinterpret_toggle = SwitchToggle("")
        warn_row.addWidget(warn_lbl, 1)
        warn_row.addWidget(self._warn_reinterpret_toggle, 0)
        lo.addLayout(warn_row)

        lo.addSpacing(SPACING_SM)
        lo.addWidget(make_section_label("Submission Processing"))
        lo.addWidget(make_h_rule())

        _pp_qss = (f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;")

        def _pp_row(label_text: str) -> tuple:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(_pp_qss)
            lbl.setWordWrap(True)
            toggle = SwitchToggle("")
            row.addWidget(lbl, 1)
            row.addWidget(toggle, 0)
            return row, toggle

        r1, self._pp_translate_toggle = _pp_row("Translate non-English submissions")
        lo.addLayout(r1)
        r2, self._pp_transcribe_toggle = _pp_row("Transcribe audio/video submissions")
        lo.addLayout(r2)
        r3, self._pp_image_toggle = _pp_row("Transcribe handwritten submissions")
        lo.addLayout(r3)

        pp_note = QLabel("Requires a local LLM (Ollama or MLX) or cloud API.")
        pp_note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        pp_note.setWordWrap(True)
        lo.addWidget(pp_note)

        lo.addStretch()

    def _on_open_signal_tuning(self) -> None:
        from gui.dialogs.signal_tuning_dialog import SignalTuningDialog
        dlg = SignalTuningDialog(parent=self)
        dlg.exec()

    def _on_launch_insights_wizard(self) -> None:
        from gui.dialogs.insights_wizard import InsightsWizard
        dlg = InsightsWizard(parent=self)
        if dlg.exec() == InsightsWizard.DialogCode.Accepted:
            self._load_current_settings()  # refresh fields from saved settings

    # ------------------------------------------------------------------
    # Signals / slots
    # ------------------------------------------------------------------

    def _on_retention_toggled(self, enabled: bool) -> None:
        self._retention_years.setEnabled(enabled)
        self._retention_days.setEnabled(enabled)
        self._retention_grading_cb.setEnabled(enabled)
        self._retention_aic_cb.setEnabled(enabled)
        self._retention_insights_cb.setEnabled(enabled)
        self._retention_notes_cb.setEnabled(enabled)
        self._on_notes_retention_toggled(
            enabled and self._retention_notes_cb.isChecked())

    def _on_notes_retention_toggled(self, enabled: bool) -> None:
        # Also require master toggle
        active = enabled and self._retention_enabled_cb.isChecked()
        for w in self._notes_age_row_widgets:
            w.setEnabled(active)

    def _on_test_connection(self) -> None:
        from automation.canvas_helpers import CanvasAutomationAPI
        from gui.workers import TestConnectionWorker

        url = self._url_edit.text().strip()
        token = self._token_edit.text().strip()
        if not url or not token:
            self._test_status.setText("Enter URL and token first")
            return

        self._test_status.setText("Testing…")
        self._test_btn.setEnabled(False)

        test_api = CanvasAutomationAPI(base_url=url, api_token=token)
        self._test_worker = TestConnectionWorker(test_api)
        self._test_worker.result_ready.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, ok: bool, name: str) -> None:
        self._test_btn.setEnabled(True)
        if ok:
            label = f"Connected as {name}" if name else "Connected"
            self._test_status.setText(f"✓ {label}")
            self._test_status.setStyleSheet(f"color: {STATUS_OK}; font-weight: 600; background: transparent;")
        else:
            self._test_status.setText(f"✗ {name or 'Connection failed'}")
            self._test_status.setStyleSheet(f"color: {STATUS_ERR}; font-weight: 600; background: transparent;")

    def _on_run_cleanup(self) -> None:
        from gui.dialogs.cleanup_dialog import CleanupDialog
        dlg = CleanupDialog(parent=self)
        dlg.exec()

    def _on_manage_profiles(self) -> None:
        from gui.dialogs.profile_dialog import ProfileDialog
        dlg = ProfileDialog(parent=self)
        dlg.exec()
        from credentials import load_credentials
        self._refresh_profile_combo(load_credentials())

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        try:
            from credentials import load_credentials
            from settings import load_settings

            s = load_settings()

            # Data retention — prefer new keys, fall back to legacy cleanup keys
            retention_enabled = s.get("data_retention_enabled",
                                       s.get("cleanup_mode", "none") != "none")
            self._retention_enabled_cb.setChecked(bool(retention_enabled))

            self._retention_years.setValue(int(s.get("data_retention_years", 0)))
            legacy_days = s.get("cleanup_threshold_days", 180)
            self._retention_days.setValue(int(s.get("data_retention_days", legacy_days)))

            self._retention_grading_cb.setChecked(bool(s.get("data_retention_grading", True)))
            self._retention_aic_cb.setChecked(bool(s.get("data_retention_aic", True)))
            self._retention_insights_cb.setChecked(bool(s.get("data_retention_insights", True)))

            notes_enabled = bool(s.get("data_retention_notes", False))
            self._retention_notes_cb.setChecked(notes_enabled)
            self._retention_notes_years.setValue(int(s.get("data_retention_notes_years", 3)))
            self._retention_notes_days.setValue(int(s.get("data_retention_notes_days", 0)))

            self._on_retention_toggled(bool(retention_enabled))

            # Insights & AI settings
            from gui.dialogs.insights_setup_dialog import _is_apple_silicon
            default_backend = "mlx" if _is_apple_silicon() else "ollama"
            backend = s.get("insights_llm_backend", default_backend)
            idx = self._llm_backend_combo.findData(backend)
            if idx >= 0:
                self._llm_backend_combo.setCurrentIndex(idx)
            self._llm_model_edit.setText(
                s.get("insights_translation_model", "llama3.1:8b")
            )
            self._ollama_url_edit.setText(
                s.get("insights_ollama_url", "http://localhost:11434")
            )
            self._mlx_text_edit.setText(
                s.get("insights_mlx_model",
                      "mlx-community/Qwen2.5-7B-Instruct-4bit")
            )
            self._mlx_vision_edit.setText(
                s.get("insights_mlx_vision_model",
                      "mlx-community/Qwen2.5-VL-3B-Instruct-4bit")
            )
            # Sync field visibility and run initial check
            self._on_llm_backend_changed(self._llm_backend_combo.currentIndex())
            self._check_llm_status()

            self._cloud_url_edit.setText(s.get("insights_cloud_url", ""))
            self._cloud_key_edit.setText(s.get("insights_cloud_key", ""))
            self._cloud_model_edit.setText(s.get("insights_cloud_model", ""))
            self._throttle_spin.setValue(
                int(s.get("insights_throttle_delay", 2))
            )
            whisper = s.get("insights_whisper_model", "base")
            widx = self._whisper_combo.findData(whisper)
            if widx >= 0:
                self._whisper_combo.setCurrentIndex(widx)
            self._keep_awake_toggle.setChecked(
                bool(s.get("insights_keep_awake", True))
            )
            self._draft_feedback_toggle.setChecked(
                bool(s.get("insights_draft_feedback", False))
            )
            self._deepening_toggle.setChecked(
                bool(s.get("insights_deepening_pass", True))
            )

            # Accessibility
            font_scale = float(s.get("font_scale", 1.0))
            sidx = self._text_size_combo.findData(font_scale)
            if sidx >= 0:
                self._text_size_combo.setCurrentIndex(sidx)
            self._warn_reinterpret_toggle.setChecked(
                bool(s.get("warn_grading_type_reinterpret", True))
            )
            self._pp_translate_toggle.setChecked(
                bool(s.get("insights_translate_enabled", True))
            )
            self._pp_transcribe_toggle.setChecked(
                bool(s.get("insights_transcribe_enabled", True))
            )
            self._pp_image_toggle.setChecked(
                bool(s.get("insights_image_transcribe_enabled", True))
            )

            data = load_credentials()
            self._refresh_profile_combo(data)

        except Exception:
            pass

    def _refresh_profile_combo(self, data: dict) -> None:
        from credentials import get_active_profile
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        profiles = data.get("profiles", {})
        active_name, active_profile = get_active_profile(data)
        for name in sorted(profiles):
            display = name.replace("_", " ").replace("-", " ").title()
            self._profile_combo.addItem(display, userData=name)
        if active_name:
            idx = self._profile_combo.findData(active_name)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
            self._url_edit.setText(active_profile.get("canvas_base_url", ""))
            token = active_profile.get("canvas_api_token", "")
            self._token_edit.setText(token if token else "")
            self._token_edit.setPlaceholderText("saved" if token else "Paste your API token here")
            self._load_aic_from_profile(active_profile)
        self._profile_combo.blockSignals(False)

    def _on_profile_switched(self, index: int) -> None:
        name = self._profile_combo.itemData(index)
        if not name:
            return
        from credentials import load_credentials
        data = load_credentials()
        profile = data.get("profiles", {}).get(name, {})
        self._url_edit.setText(profile.get("canvas_base_url", ""))
        token = profile.get("canvas_api_token", "")
        self._token_edit.setText(token if token else "")
        self._token_edit.setPlaceholderText("saved" if token else "Paste your API token here")
        self._load_aic_from_profile(profile)

    def _load_aic_from_profile(self, profile: dict) -> None:
        """Populate the AIC calibration controls from a credential profile dict."""
        edu = profile.get("education_level", "community_college")
        idx = self._edu_level_combo.findData(edu)
        if idx >= 0:
            self._edu_level_combo.setCurrentIndex(idx)

        esl = profile.get("population_esl", "none")
        idx = self._pop_esl_combo.findData(esl)
        if idx >= 0:
            self._pop_esl_combo.setCurrentIndex(idx)

        fg = profile.get("population_first_gen", "none")
        idx = self._pop_first_gen_combo.findData(fg)
        if idx >= 0:
            self._pop_first_gen_combo.setCurrentIndex(idx)

        self._pop_nd_check.setChecked(bool(profile.get("population_neurodivergent_aware", False)))

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------

    def _schedule_autosave(self) -> None:
        """Restart the debounce timer — saves 800ms after last change."""
        self._autosave_timer.start()

    def _connect_autosave(self) -> None:
        """Wire every settings widget's change signal to auto-save."""
        trigger = self._schedule_autosave

        # Toggles / checkboxes
        for toggle in (
            self._keep_awake_toggle,
            self._draft_feedback_toggle,
            self._deepening_toggle,
            self._warn_reinterpret_toggle,
            self._pp_translate_toggle,
            self._pp_transcribe_toggle,
            self._pp_image_toggle,
            self._retention_enabled_cb,
            self._retention_grading_cb,
            self._retention_aic_cb,
            self._retention_insights_cb,
            self._retention_notes_cb,
            self._pop_nd_check,
        ):
            toggle.toggled.connect(trigger)

        # Combo boxes
        for combo in (
            self._llm_backend_combo,
            self._edu_level_combo,
            self._pop_esl_combo,
            self._pop_first_gen_combo,
            self._whisper_combo,
            self._text_size_combo,
        ):
            combo.currentIndexChanged.connect(trigger)

        # Spin boxes
        for spin in (
            self._retention_years,
            self._retention_days,
            self._retention_notes_years,
            self._retention_notes_days,
            self._throttle_spin,
        ):
            spin.valueChanged.connect(trigger)

        # Line edits — use editingFinished so we don't save on every keystroke
        for edit in (
            self._url_edit,
            self._token_edit,
            self._llm_model_edit,
            self._ollama_url_edit,
            self._mlx_text_edit,
            self._mlx_vision_edit,
            self._cloud_url_edit,
            self._cloud_key_edit,
            self._cloud_model_edit,
        ):
            edit.editingFinished.connect(trigger)

    def _on_save(self) -> None:
        try:
            from credentials import (
                load_credentials, save_credentials, get_active_profile,
                profile_name_from_url,
            )
            from settings import save_settings, load_settings

            # Credentials
            url = self._url_edit.text().strip()
            token = self._token_edit.text().strip()
            data = load_credentials()
            active_name, _ = get_active_profile(data)
            profile_name = (
                self._profile_combo.currentData()
                or active_name
                or profile_name_from_url(url)
                or "default"
            )
            if "profiles" not in data:
                data["profiles"] = {}
            if profile_name not in data["profiles"]:
                data["profiles"][profile_name] = {}
            if url:
                data["profiles"][profile_name]["canvas_base_url"] = url
            if token:
                data["profiles"][profile_name]["canvas_api_token"] = token
            # AIC per-profile calibration settings
            data["profiles"][profile_name]["education_level"] = (
                self._edu_level_combo.currentData() or "community_college"
            )
            data["profiles"][profile_name]["population_esl"] = (
                self._pop_esl_combo.currentData() or "none"
            )
            data["profiles"][profile_name]["population_first_gen"] = (
                self._pop_first_gen_combo.currentData() or "none"
            )
            data["profiles"][profile_name]["population_neurodivergent_aware"] = (
                self._pop_nd_check.isChecked()
            )
            if url or token:
                data["active_profile"] = profile_name
            save_credentials(data)

            s = load_settings()

            # Data retention — save new keys and also translate to legacy cleanup keys
            enabled = self._retention_enabled_cb.isChecked()
            years = self._retention_years.value()
            days = self._retention_days.value()
            incl_grading = self._retention_grading_cb.isChecked()
            incl_aic = self._retention_aic_cb.isChecked()
            incl_insights = self._retention_insights_cb.isChecked()
            incl_notes = self._retention_notes_cb.isChecked()

            s["data_retention_enabled"] = enabled
            s["data_retention_years"] = years
            s["data_retention_days"] = days
            s["data_retention_grading"] = incl_grading
            s["data_retention_aic"] = incl_aic
            s["data_retention_insights"] = incl_insights
            s["data_retention_notes"] = incl_notes
            s["data_retention_notes_years"] = self._retention_notes_years.value()
            s["data_retention_notes_days"] = self._retention_notes_days.value()

            # Legacy cleanup keys (used by TUI and cleanup.py)
            s["cleanup_mode"] = "trash" if enabled else "none"
            s["cleanup_threshold_days"] = days
            targets = []
            if incl_grading:
                targets += ["ci_csv", "df_csv"]
            if incl_aic:
                targets += ["ad_csv", "ad_excel", "ad_txt"]
            s["cleanup_targets"] = "all" if len(targets) == 5 else ",".join(targets)

            # Insights & AI
            s["insights_llm_backend"] = (
                self._llm_backend_combo.currentData() or "ollama"
            )
            s["insights_translation_model"] = (
                self._llm_model_edit.text().strip() or "llama3.1:8b"
            )
            s["insights_ollama_url"] = (
                self._ollama_url_edit.text().strip() or "http://localhost:11434"
            )
            s["insights_mlx_model"] = (
                self._mlx_text_edit.text().strip()
                or "mlx-community/Qwen2.5-7B-Instruct-4bit"
            )
            s["insights_mlx_vision_model"] = (
                self._mlx_vision_edit.text().strip()
                or "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"
            )
            s["insights_cloud_url"] = self._cloud_url_edit.text().strip()
            s["insights_cloud_key"] = self._cloud_key_edit.text().strip()
            s["insights_cloud_model"] = self._cloud_model_edit.text().strip()
            s["insights_throttle_delay"] = self._throttle_spin.value()
            s["insights_whisper_model"] = (
                self._whisper_combo.currentData() or "medium"
            )
            s["insights_keep_awake"] = self._keep_awake_toggle.isChecked()
            s["insights_draft_feedback"] = self._draft_feedback_toggle.isChecked()
            s["insights_deepening_pass"] = self._deepening_toggle.isChecked()

            # Accessibility
            s["font_scale"] = self._text_size_combo.currentData() or 1.0
            s["warn_grading_type_reinterpret"] = self._warn_reinterpret_toggle.isChecked()
            s["insights_translate_enabled"] = self._pp_translate_toggle.isChecked()
            s["insights_transcribe_enabled"] = self._pp_transcribe_toggle.isChecked()
            s["insights_image_transcribe_enabled"] = self._pp_image_toggle.isChecked()

            save_settings(s)
            self.settings_saved.emit()
            self._flash_save_status("Settings saved.", ok=True)

        except Exception as exc:
            self._flash_save_status(f"Save failed: {exc}", ok=False)

    def _flash_save_status(self, msg: str, ok: bool) -> None:
        from PySide6.QtCore import QTimer
        color = STATUS_OK if ok else STATUS_ERR
        self._save_status.setStyleSheet(
            f"color: {color}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        self._save_status.setText(msg)
        QTimer.singleShot(3000, lambda: self._save_status.setText(""))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_api_credentials(self):
        """Returns (url, token) from the current field values."""
        return self._url_edit.text().strip(), self._token_edit.text().strip()
