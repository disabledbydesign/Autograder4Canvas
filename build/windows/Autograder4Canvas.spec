# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Autograder4Canvas GUI (Windows).
Targets the PySide6 GUI (gui_main.py) — NOT the legacy TUI.

Heavy ML packages (faster_whisper, sentence_transformers, torch) are excluded
to keep the bundle size manageable. Those features gracefully degrade when the
bundled exe runs without them. Users who need transcription/embedding can pip-
install into the exe's bundled environment separately.

Build from the repo root's build/windows/ directory:
    cd build\windows
    pip install pyinstaller PySide6
    pyinstaller Autograder4Canvas.spec --noconfirm

Or use build_exe.bat (handles pip installs automatically).

Output: build\windows\dist\Autograder4Canvas\Autograder4Canvas.exe
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# SPECPATH is set by PyInstaller to the directory containing this .spec file.
# Repo structure: build/windows/Autograder4Canvas.spec  →  ../../src/
SRC_DIR   = os.path.normpath(os.path.join(SPECPATH, '..', '..', 'src'))
ICON_PATH = os.path.join(SPECPATH, 'Autograder4Canvas', 'icon.ico')

# Collect all PySide6 assets: Qt plugins, translations, platform backends, etc.
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all('PySide6')

a = Analysis(
    [os.path.join(SRC_DIR, 'gui_main.py')],
    pathex=[SRC_DIR],
    binaries=pyside6_binaries,
    datas=pyside6_datas + [
        # Static data directories that the app reads at runtime
        (os.path.join(SRC_DIR, 'config'),        'config'),
        (os.path.join(SRC_DIR, 'demo_assets'),   'demo_assets'),
        (os.path.join(SRC_DIR, 'assets'),        'assets'),
        (os.path.join(SRC_DIR, 'requirements.txt'), '.'),
    ],
    hiddenimports=pyside6_hiddenimports + [
        # ── GUI ──────────────────────────────────────────────────────────
        'gui', 'gui.app', 'gui.main_window', 'gui.styles',
        'gui.workers', 'gui.aic_palette', 'gui.scheduler',
        # Panels
        'gui.panels',
        'gui.panels.assignment_panel',
        'gui.panels.automation_panel',
        'gui.panels.course_panel',
        'gui.panels.grading_results_panel',
        'gui.panels.insights_panel',
        'gui.panels.mapping_panel',
        'gui.panels.prior_runs_panel',
        'gui.panels.review_panel',
        'gui.panels.settings_panel',
        # Widgets
        'gui.widgets',
        'gui.widgets.crt_combo',
        'gui.widgets.glow_bulb_button',
        'gui.widgets.option_pair',
        'gui.widgets.option_rocker',
        'gui.widgets.phosphor_chip',
        'gui.widgets.review_sidebar',
        'gui.widgets.segmented_toggle',
        'gui.widgets.signal_triad',
        'gui.widgets.status_pip',
        'gui.widgets.switch_toggle',
        'gui.widgets.view_toggle',
        # Dialogs
        'gui.dialogs',
        'gui.dialogs.aic_info_dialog',
        'gui.dialogs.bulk_run_dialog',
        'gui.dialogs.bulk_shift_dialog',
        'gui.dialogs.chatbot_export_dialog',
        'gui.dialogs.cleanup_dialog',
        'gui.dialogs.course_profile_dialog',
        'gui.dialogs.date_picker_dialog',
        'gui.dialogs.enhancement_preview_dialog',
        'gui.dialogs.export_reports_dialog',
        'gui.dialogs.help_dialog',
        'gui.dialogs.insights_setup_dialog',
        'gui.dialogs.insights_wizard',
        'gui.dialogs.message_dialog',
        'gui.dialogs.profile_dialog',
        'gui.dialogs.run_aic_dialog',
        'gui.dialogs.run_dialog',
        'gui.dialogs.setup_dialog',
        'gui.dialogs.short_sub_review_dialog',
        'gui.dialogs.signal_tuning_dialog',
        'gui.dialogs.template_editor_dialog',
        # ── Backend: automation ───────────────────────────────────────────
        'automation',
        'automation.automation_engine',
        'automation.canvas_helpers',
        'automation.command_reference',
        'automation.config_wizard',
        'automation.course_config',
        'automation.data_retention',
        'automation.demo_store',
        'automation.flag_aggregator',
        'automation.grade_checker',
        'automation.notification_manager',
        'automation.reply_quality_checker',
        'automation.run_store',
        # ── Backend: insights pipeline ────────────────────────────────────
        'insights',
        'insights.chatbot_export',
        'insights.citation_checker',
        'insights.class_reader',
        'insights.class_trajectory_context',
        'insights.cross_validator',
        'insights.data_fetcher',
        'insights.engine',
        'insights.feedback_drafter',
        'insights.gibberish_gate',
        'insights.insights_store',
        'insights.lens_templates',
        'insights.llm_backend',
        'insights.models',
        'insights.patterns',
        'insights.process_keepalive',
        'insights.prompts',
        'insights.quick_analyzer',
        'insights.short_sub_models',
        'insights.short_sub_reviewer',
        'insights.submission_coder',
        'insights.synthesizer',
        'insights.teacher_profile',
        'insights.theme_generator',
        'insights.trajectory',
        'insights.trajectory_context',
        'insights.trajectory_report',
        # ── Backend: AIC modules ──────────────────────────────────────────
        'modules',
        'modules.assignment_config',
        'modules.citation_verifier',
        'modules.cohort_calibration',
        'modules.consent_system',
        'modules.context_analyzer',
        'modules.demographic_collector',
        'modules.draft_comparison',
        'modules.feedback_tracker',
        'modules.human_presence_detector',
        'modules.linguistic_features',
        'modules.marker_loader',
        'modules.organizational_analyzer',
        'modules.peer_comparison',
        # ── Backend: inbox ────────────────────────────────────────────────
        'inbox',
        'inbox.cli',
        'inbox.config',
        'inbox.context_engine',
        'inbox.conversations',
        'inbox.db',
        'inbox.learning',
        'inbox.models',
        # ── Root-level modules ────────────────────────────────────────────
        'credentials',
        'settings',
        'autograder_utils',
        'canvas_editor',
        'cleanup',
        'demo_data',
        'assignment_templates',
        # ── External packages ─────────────────────────────────────────────
        'requests', 'urllib3', 'certifi',
        'yaml', 'pyyaml',
        'dateutil', 'pytz',
        'openpyxl',
        'pandas', 'numpy',
        'pydantic', 'pydantic_core',
        'langdetect',
        'textstat',
        'vaderSentiment', 'vaderSentiment.vaderSentiment',
        'striprtf',
        'odfpy', 'odf',
        'docx', 'python_docx',
        'pdfminer', 'pdfminer.high_level', 'pdfminer.layout',
        'sklearn', 'scipy', 'joblib',
        'spacy',
        'json', 'csv', 'sqlite3', 'webbrowser',
    ],
    excludes=[
        # Heavy ML packages excluded — bundle would exceed 2 GB with them.
        # Transcription (faster_whisper) and embedding (sentence_transformers)
        # features will be unavailable in the bundled exe.
        'faster_whisper',
        'ctranslate2',
        'sentence_transformers',
        'torch',
        'torchaudio',
        'torchvision',
        'transformers',
        'tokenizers',
        'huggingface_hub',
        # Dev / test tools
        'pytest',
        'sphinx',
        'jupyter',
        'IPython',
        'matplotlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Autograder4Canvas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # GUI mode — no terminal window
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Autograder4Canvas',
)
