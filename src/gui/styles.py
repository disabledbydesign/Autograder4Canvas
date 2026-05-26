"""
Design system for Canvas Autograder GUI.

Aesthetic direction: Retro-Futurist Amber Terminal
- Warm near-black backgrounds (phosphor CRT void)
- Amber phosphor text hierarchy
- Dusty rose for active states / primary actions
- Terminal green for success, burn red for errors
- Monospace throughout
"""

# ---------------------------------------------------------------------------
# Font scale — global accessibility multiplier
# ---------------------------------------------------------------------------
# Loaded from settings once at startup.  Every pixel-based font size and
# scale-sensitive dimension should go through px() so the entire UI
# respects the user's text-size preference.
#
# Values:  1.0 = default,  1.25 = large,  1.5 = extra large

_FONT_SCALE: float = 1.0

def _load_font_scale() -> float:
    """Read font_scale from settings (safe to call at import time)."""
    try:
        from settings import load_settings
        s = load_settings()
        v = float(s.get("font_scale", 1.0))
        return max(0.75, min(2.0, v))   # clamp to sane range
    except Exception:
        return 1.0

_FONT_SCALE = _load_font_scale()


def px(base: int) -> int:
    """Scale a pixel value by the user's font-size preference."""
    return max(1, round(base * _FONT_SCALE))


def set_font_scale(scale: float) -> None:
    """Update the global font scale (takes effect on next QSS rebuild)."""
    global _FONT_SCALE
    _FONT_SCALE = max(0.75, min(2.0, scale))


# ---------------------------------------------------------------------------
# Spacing scale
# ---------------------------------------------------------------------------
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24

# ---------------------------------------------------------------------------
# Font sizes (base values — pass through px() when used in stylesheets)
# ---------------------------------------------------------------------------
FONT_SMALL  = 11
FONT_NORMAL = 13
FONT_LARGE  = 15
FONT_MONO   = 13

# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------
WIN_MIN_W      = 900
WIN_MIN_H      = 650
WIN_DEFAULT_W  = 1280
WIN_DEFAULT_H  = 860

LEFT_PANEL_MIN  = 260
LEFT_PANEL_PREF = 300

# ---------------------------------------------------------------------------
# Amber terminal colour palette
# ---------------------------------------------------------------------------

# Backgrounds — warm near-void
BG_VOID       = "#0A0800"   # outer void (window bg)
BG_PANEL      = "#130E04"   # sidebar / panel surface
BG_CARD       = "#1C1508"   # card / content surface
BG_INSET      = "#0E0A02"   # recessed areas (inputs, data)

# Phosphor text hierarchy
PHOSPHOR_HOT  = "#F0A830"   # bright — primary text, highlights
PHOSPHOR_MID  = "#C08820"   # mid — secondary text
PHOSPHOR_DIM  = "#7A5418"   # dim — placeholders, muted labels
PHOSPHOR_GLOW = "#4A3210"   # subtle — disabled text, faint hints

# Accents
AMBER_BTN     = "#C87C10"   # amber — secondary action buttons
ROSE_ACCENT   = "#CC5282"   # rose — primary run/go action (resting text)
ROSE_HOT      = "#E8709E"   # bright rose — run button hover text / active glow
ROSE_DIM      = "#7A3458"   # rose hover / border
WARN_PINK     = "#C4708A"   # soft rose — warning toast text

# Status
TERM_GREEN    = "#72B85A"   # connected / ok
BURN_RED      = "#C04020"   # error

# Linguistic asset chip colors (green/teal — distinct from amber register and red concern)
ASSET_CHIP_BG = "rgba(0, 180, 140, 0.15)"
ASSET_CHIP_BORDER = "rgba(0, 180, 140, 0.4)"
ASSET_CHIP_TEXT = "#00B48C"

# Borders
BORDER_DARK   = "#3A2808"   # subtle warm border
BORDER_AMBER  = "#6A4A12"   # glowing amber border

# ---------------------------------------------------------------------------
# Backwards-compatible aliases (existing code imports these by name)
# ---------------------------------------------------------------------------
SIDEBAR_BG       = BG_PANEL
SIDEBAR_TEXT     = PHOSPHOR_MID
SIDEBAR_BORDER   = BORDER_DARK
SIDEBAR_SEL_BG   = "#2C1C08"
SIDEBAR_SEL_TEXT = PHOSPHOR_HOT
SIDEBAR_HOVER    = "#1A1205"

CONTENT_BG       = BG_VOID
SURFACE_BG       = BG_CARD
BORDER_COLOR     = BORDER_DARK
BORDER_FOCUS     = PHOSPHOR_HOT

TEXT_PRIMARY     = PHOSPHOR_HOT
TEXT_SECONDARY   = PHOSPHOR_MID
TEXT_PLACEHOLDER = PHOSPHOR_DIM

ACCENT_BLUE      = AMBER_BTN       # secondary button accent
ACCENT_AMBER     = ROSE_ACCENT     # primary run button
ACCENT_AMBER_HOV = "#A83E68"
ACCENT_AMBER_TXT = PHOSPHOR_HOT

STATUS_OK        = TERM_GREEN
STATUS_ERR       = BURN_RED
STATUS_WARN      = "#D87020"

GROUP_HEADER_BG  = "#1A1208"
GROUP_HEADER_FG  = PHOSPHOR_MID

# ---------------------------------------------------------------------------
# Shared gradient backgrounds  (import these instead of redefining per-file)
#
# IMPORTANT — QWidget vs QFrame:
#   QWidget ignores stylesheet `background:` unless WA_StyledBackground is set.
#   QFrame paints stylesheet backgrounds automatically.
#   Any panel that needs a gradient background MUST inherit QFrame, not QWidget.
# ---------------------------------------------------------------------------
CARD_GRADIENT  = ("qradialgradient(cx:0.52,cy:0.44,radius:0.90,fx:0.48,fy:0.40,"
                  "stop:0.00 #2C2212,stop:0.60 #171208,stop:1.00 #100C03)")
PANEL_GRADIENT = ("qradialgradient(cx:0.50,cy:0.46,radius:0.88,fx:0.53,fy:0.42,"
                  "stop:0.00 #201A08,stop:0.60 #121006,stop:1.00 #090702)")

MONO_FONT = '"Menlo", "Consolas", "Courier New", monospace'


def menu_qss() -> str:
    """CRT-styled QMenu stylesheet — call on every QMenu instance for reliability.

    macOS popup menus sometimes bypass app-level stylesheets, so applying
    this directly on each QMenu guarantees the CRT look.
    """
    return f"""
        QMenu {{
            background: qradialgradient(cx:0.25,cy:0.18,radius:1.15,
                stop:0.00 #221A0A,stop:0.45 #150F05,stop:1.00 #0B0802);
            border: 1px solid {BORDER_AMBER};
            border-radius: 6px;
            padding: 6px 0;
            font-family: "Menlo", "Consolas", "Courier New", monospace;
            font-size: {px(12)}px;
        }}
        QMenu::item {{
            padding: 6px 28px 6px 14px;
            color: {PHOSPHOR_MID};
            border-left: 2px solid transparent;
            margin: 1px 4px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background: qradialgradient(cx:0.15,cy:0.50,radius:1.00,
                stop:0.00 rgba(240,168,48,50),
                stop:0.55 rgba(240,168,48,12),
                stop:1.00 rgba(240,168,48,0));
            color: {PHOSPHOR_HOT};
            border-left: 2px solid {PHOSPHOR_HOT};
        }}
        QMenu::item:disabled {{
            color: {PHOSPHOR_GLOW};
        }}
        QMenu::separator {{
            height: 1px;
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(106,74,18,0),
                stop:0.20 rgba(106,74,18,0.45),
                stop:0.80 rgba(106,74,18,0.45),
                stop:1.00 rgba(106,74,18,0));
            margin: 5px 10px;
        }}
    """


def combo_qss() -> str:
    """Return an empty string — QComboBox styling is now handled by CRTComboBox.

    Kept as a no-op so existing ``setStyleSheet(combo_qss())`` calls don't
    break. New code should use ``CRTComboBox`` from ``gui.widgets.crt_combo``
    instead of styling a plain QComboBox.
    """
    return ""


def make_crt_combo(parent=None):
    """Create a CRTComboBox — convenience so callers don't need the import."""
    from gui.widgets.crt_combo import CRTComboBox
    return CRTComboBox(parent)


# ---------------------------------------------------------------------------
# Application-wide QSS
# Button gradients — CRT phosphor glow from centre, matching ViewToggle style
# ---------------------------------------------------------------------------
# Resting: faint warm ember at centre, near-void at edges
_BTN_BG     = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
               "stop:0.00 rgba(240,168,48,30),stop:0.55 #111003,stop:1.00 #0E0A02)")
# Hover: pronounced amber radial bloom — same glow as ViewToggle active side
_BTN_HOV_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
               "stop:0.00 rgba(240,168,48,65),stop:0.50 #1C1608,stop:1.00 #0E0A02)")
# Pressed: inset — glow collapses inward
_BTN_PRE_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.60,"
               "stop:0.00 rgba(240,168,48,28),stop:0.55 #0E0A02,stop:1.00 #0E0A02)")
# Checked: strong phosphor backlight
_BTN_CHK_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
               "stop:0.00 rgba(240,168,48,90),stop:0.50 #2A1C06,stop:1.00 #0E0A02)")
# Rose-accent resting (faint rose ember at centre)
_BTN_RUN_BG     = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
                   "stop:0.00 rgba(204,82,130,30),stop:0.55 #120610,stop:1.00 #0E0A02)")
# Rose-accent hover
_BTN_RUN_HOV_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
                   "stop:0.00 rgba(204,82,130,65),stop:0.50 #1C0A14,stop:1.00 #0E0A02)")
# Rose-accent pressed
_BTN_RUN_PRE_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.60,"
                   "stop:0.00 rgba(204,82,130,28),stop:0.55 #0E0A0C,stop:1.00 #0E0A02)")
# Rose-accent checked
_BTN_RUN_CHK_BG = ("qradialgradient(cx:0.38,cy:0.36,radius:0.90,"
                   "stop:0.00 rgba(204,82,130,90),stop:0.50 #241018,stop:1.00 #0E0A02)")
# Secondary-amber hover
_BTN_SEC_HOV_BG = ("qradialgradient(cx:0.50,cy:0.50,radius:0.90,"
                   "stop:0.00 rgba(200,124,16,65),stop:0.50 #1A1406,stop:1.00 #0E0A02)")
# Secondary-amber checked
_BTN_SEC_CHK_BG = ("qradialgradient(cx:0.50,cy:0.50,radius:0.90,"
                   "stop:0.00 rgba(200,124,16,90),stop:0.50 #251806,stop:1.00 #0E0A02)")

def build_app_qss() -> str:
    """Build the application-wide QSS with current px() scale."""
    return f"""

/* ── Global ──────────────────────────────────────────────────────────────── */
QWidget {{
    font-family: "Menlo", "Consolas", "Courier New", monospace;
    font-size: {px(13)}px;
    color: {TEXT_PRIMARY};
    background: {CONTENT_BG};
}}

QMainWindow, QDialog {{
    background: {CONTENT_BG};
}}

/* ── Menu bar ─────────────────────────────────────────────────────────────── */
QMenuBar {{
    background: {SIDEBAR_BG};
    color: {SIDEBAR_TEXT};
    padding: 2px 0;
    border-bottom: 1px solid {SIDEBAR_BORDER};
}}
QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}}
QMenuBar::item:selected {{
    background: qradialgradient(cx:0.50,cy:0.50,radius:0.90,
        stop:0.00 #3A2408,stop:0.65 #2C1C08,stop:1.00 {SIDEBAR_BG});
    color: {SIDEBAR_SEL_TEXT};
}}
QMenu {{
    background: qradialgradient(cx:0.30,cy:0.20,radius:1.10,
        stop:0.00 #201808,stop:0.50 #140E04,stop:1.00 #0C0902);
    border: 1px solid {BORDER_AMBER};
    border-radius: 6px;
    padding: 6px 0;
    font-family: "Menlo", "Consolas", "Courier New", monospace;
    font-size: {px(12)}px;
}}
QMenu::item {{
    padding: 6px 28px 6px 14px;
    color: {PHOSPHOR_MID};
    border-left: 2px solid transparent;
    margin: 1px 4px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: qradialgradient(cx:0.20,cy:0.50,radius:1.00,
        stop:0.00 rgba(240,168,48,45),stop:0.60 rgba(240,168,48,10),stop:1.00 rgba(240,168,48,0));
    color: {PHOSPHOR_HOT};
    border-left: 2px solid {PHOSPHOR_HOT};
}}
QMenu::item:disabled {{
    color: {PHOSPHOR_GLOW};
}}
QMenu::separator {{
    height: 1px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0.00 rgba(106,74,18,0),
        stop:0.25 rgba(106,74,18,0.50),
        stop:0.75 rgba(106,74,18,0.50),
        stop:1.00 rgba(106,74,18,0));
    margin: 5px 10px;
}}
QMenu::indicator {{
    width: 10px;
    height: 10px;
    margin-left: 4px;
}}

/* ── Tool bar ─────────────────────────────────────────────────────────────── */
QToolBar {{
    background: {SIDEBAR_BG};
    border: none;
    border-bottom: 1px solid {SIDEBAR_BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    color: {SIDEBAR_TEXT};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: {px(12)}px;
}}
QToolBar QToolButton:hover {{
    background: {SIDEBAR_HOVER};
    border-color: {SIDEBAR_BORDER};
    color: {PHOSPHOR_HOT};
}}
QToolBar QToolButton:pressed {{
    background: {SIDEBAR_SEL_BG};
}}
QToolBar::separator {{
    width: 1px;
    background: {SIDEBAR_BORDER};
    margin: 4px 6px;
}}

/* ── Tab widget ───────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER_DARK};
    background: {CONTENT_BG};
}}
QTabBar {{
    background: {SIDEBAR_BG};
}}
QTabBar::tab {{
    background: {SIDEBAR_BG};
    color: {PHOSPHOR_DIM};
    padding: 8px 20px;
    border-bottom: 2px solid transparent;
    font-size: {px(13)}px;
}}
QTabBar::tab:selected {{
    color: {PHOSPHOR_HOT};
    border-bottom: 2px solid {ROSE_ACCENT};
    font-weight: bold;
    background: qradialgradient(cx:0.50,cy:1.00,radius:1.10,
        stop:0.00 #2A1E08,stop:0.70 #181408,stop:1.00 {SIDEBAR_BG});
}}
QTabBar::tab:hover:!selected {{
    background: {SIDEBAR_HOVER};
    color: {PHOSPHOR_MID};
}}

/* ── Status bar ───────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {SIDEBAR_BG};
    color: {SIDEBAR_TEXT};
    border-top: 1px solid {SIDEBAR_BORDER};
    font-size: {px(12)}px;
}}
QStatusBar QLabel {{
    padding: 3px 6px;
    color: {SIDEBAR_TEXT};
}}

/* ── Group boxes ──────────────────────────────────────────────────────────── */
QGroupBox {{
    font-weight: 600;
    font-size: {px(11)}px;
    color: {PHOSPHOR_DIM};
    border: 1px solid {BORDER_DARK};
    border-radius: 6px;
    padding-top: 18px;
    margin-top: 8px;
    background: {BG_CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {PHOSPHOR_DIM};
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: {px(11)}px;
}}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
/* Radial gradient gives a warm backlit phosphor glow from the centre.        */
QPushButton {{
    background: {_BTN_BG};
    color: {PHOSPHOR_MID};
    border: 1px solid rgba(90, 60, 8, 0.55);
    border-radius: 4px;
    padding: 6px 14px;
    font-size: {px(13)}px;
    min-height: {px(22)}px;
}}
QPushButton:hover {{
    background: {_BTN_HOV_BG};
    border-color: {BORDER_AMBER};
    color: {PHOSPHOR_HOT};
}}
QPushButton:pressed {{
    background: {_BTN_PRE_BG};
    padding-top: 7px; padding-bottom: 5px;
    padding-left: 15px; padding-right: 13px;
    border-color: rgba(90, 60, 8, 0.35);
}}
QPushButton:checked {{
    background: {_BTN_CHK_BG};
    color: {PHOSPHOR_HOT};
    border: 1px solid rgba(106,74,18,0.85);
    font-weight: 600;
}}
QPushButton:disabled {{
    color: {PHOSPHOR_GLOW};
    border-color: rgba(58, 40, 8, 0.3);
    background: {_BTN_BG};
}}

/* Run / primary accent (rose/pink) */
QPushButton#runButton, QPushButton[accent="true"] {{
    background: {_BTN_RUN_BG};
    color: {ROSE_ACCENT};
    border: 1px solid rgba(204, 82, 130, 0.65);
    font-weight: 600;
    padding: 7px 18px;
}}
QPushButton#runButton:hover, QPushButton[accent="true"]:hover {{
    background: {_BTN_RUN_HOV_BG};
    border-color: rgba(232, 112, 158, 0.90);
    color: {ROSE_HOT};
}}
QPushButton#runButton:pressed, QPushButton[accent="true"]:pressed {{
    background: {_BTN_RUN_PRE_BG};
    padding-top: 8px; padding-bottom: 6px;
    padding-left: 19px; padding-right: 17px;
    border-color: rgba(204, 82, 130, 0.35);
    color: {ROSE_ACCENT};
}}
QPushButton#runButton:checked, QPushButton[accent="true"]:checked {{
    background: {_BTN_RUN_CHK_BG};
    color: {ROSE_HOT};
    border: 1px solid rgba(204, 82, 130, 0.85);
    font-weight: 600;
}}
QPushButton#runButton:disabled, QPushButton[accent="true"]:disabled {{
    color: rgba(80, 40, 60, 0.50);
    border-color: rgba(60, 20, 40, 0.30);
}}

/* Blue accent buttons (AIC) */
QPushButton[accentBlue="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(50, 80, 120, 0.85), stop:1 rgba(30, 50, 80, 0.85));
    color: #90C8F0;
    border: 1px solid rgba(120, 180, 220, 0.65);
    font-weight: 600;
    padding: 7px 18px;
}}
QPushButton[accentBlue="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(60, 100, 150, 0.90), stop:1 rgba(40, 65, 100, 0.90));
    border-color: rgba(144, 200, 240, 0.90);
    color: #B0DEFF;
}}
QPushButton[accentBlue="true"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(25, 45, 70, 0.85), stop:1 rgba(35, 60, 90, 0.85));
    padding-top: 8px; padding-bottom: 6px;
    padding-left: 19px; padding-right: 17px;
    border-color: rgba(120, 180, 220, 0.35);
    color: #90C8F0;
}}
QPushButton[accentBlue="true"]:disabled {{
    color: rgba(60, 90, 120, 0.50);
    border-color: rgba(40, 60, 80, 0.30);
}}

/* Secondary amber buttons */
QPushButton[secondary="true"] {{
    background: {_BTN_BG};
    color: {AMBER_BTN};
    border: 1px solid rgba(200, 124, 16, 0.50);
    font-weight: 500;
}}
QPushButton[secondary="true"]:hover {{
    background: {_BTN_SEC_HOV_BG};
    border-color: rgba(200, 124, 16, 0.90);
    color: {PHOSPHOR_HOT};
}}
QPushButton[secondary="true"]:checked {{
    background: {_BTN_SEC_CHK_BG};
    color: {PHOSPHOR_HOT};
    border: 1px solid rgba(200, 124, 16, 0.80);
    font-weight: 600;
}}
QPushButton[secondary="true"]:disabled {{
    color: rgba(200, 124, 16, 0.30);
    border-color: rgba(200, 124, 16, 0.20);
}}

/* ── Line edits ───────────────────────────────────────────────────────────── */
QLineEdit {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    padding: 5px 8px;
    color: {PHOSPHOR_HOT};
    selection-background-color: {PHOSPHOR_GLOW};
    selection-color: {PHOSPHOR_HOT};
}}
QLineEdit:focus {{
    border-color: {PHOSPHOR_HOT};
    outline: none;
}}
QLineEdit:disabled {{
    background: {BG_VOID};
    color: {PHOSPHOR_DIM};
}}

/* ── Combo box (fallback for plain QComboBox; prefer CRTComboBox) ─────── */
QComboBox {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 5px;
    padding: 5px 28px 5px 10px;
    color: {PHOSPHOR_HOT};
    min-height: {px(22)}px;
}}
QComboBox:hover {{
    border-color: {BORDER_AMBER};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

/* ── Spin box ─────────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    padding: 4px 8px;
    color: {PHOSPHOR_HOT};
}}
QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{
    border-color: {PHOSPHOR_HOT};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
}}

/* ── Checkboxes / radio buttons ───────────────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {PHOSPHOR_MID};
    spacing: 6px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {PHOSPHOR_DIM};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {px(14)}px;
    height: {px(14)}px;
    border: 1px solid {BORDER_AMBER};
    border-radius: 3px;
    background: {BG_INSET};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.50,cy:0.50,radius:0.75,
        stop:0.00 rgba(200,130,20,0.80),
        stop:0.60 rgba(140,90,14,0.55),
        stop:1.00 rgba(30,20,4,0.60));
    border-color: rgba(200,140,30,0.70);
}}

/* ── List widget (course list) ────────────────────────────────────────────── */
QListWidget {{
    background: {SIDEBAR_BG};
    border: none;
    border-right: 1px solid {SIDEBAR_BORDER};
    color: {SIDEBAR_TEXT};
    outline: none;
    font-size: {px(13)}px;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 0;
    border-left: 3px solid transparent;
}}
QListWidget::item:selected {{
    background: qradialgradient(cx:0.15,cy:0.50,radius:1.30,
        stop:0.00 #3A2408,stop:0.65 #2C1C08,stop:1.00 #1A1205);
    color: {SIDEBAR_SEL_TEXT};
    border-left: 3px solid {ROSE_ACCENT};
}}
QListWidget::item:hover:!selected {{
    background: qradialgradient(cx:0.15,cy:0.50,radius:1.20,
        stop:0.00 #231A06,stop:0.70 #191406,stop:1.00 #141003);
    color: {PHOSPHOR_HOT};
}}

/* ── Tree widget (assignments) ────────────────────────────────────────────── */
QTreeWidget {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    alternate-background-color: {GROUP_HEADER_BG};
    color: {PHOSPHOR_MID};
    outline: none;
}}
QTreeWidget::item {{
    padding: 4px 4px;
    color: {PHOSPHOR_MID};
}}
QTreeWidget::item:selected {{
    background: qradialgradient(cx:0.15,cy:0.50,radius:1.30,
        stop:0.00 #3A2408,stop:0.65 #2C1C08,stop:1.00 #1A1205);
    color: {PHOSPHOR_HOT};
}}
QTreeWidget::item:hover:!selected {{
    background: qradialgradient(cx:0.15,cy:0.50,radius:1.20,
        stop:0.00 #231A06,stop:0.70 #191406,stop:1.00 #141003);
}}
QHeaderView::section {{
    background: {GROUP_HEADER_BG};
    color: {PHOSPHOR_DIM};
    border: none;
    border-right: 1px solid {BORDER_DARK};
    border-bottom: 1px solid {BORDER_DARK};
    padding: 5px 8px;
    font-weight: 600;
    font-size: {px(11)}px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QHeaderView::section:first {{
    border-left: none;
}}

/* ── Scroll areas ─────────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: {CONTENT_BG};
}}
QScrollArea > QWidget > QWidget {{
    background: {CONTENT_BG};
}}
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_AMBER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PHOSPHOR_MID};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_PANEL};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_AMBER};
    border-radius: 4px;
    min-width: 30px;
}}

/* ── Splitter handle ──────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {SIDEBAR_BORDER};
}}
QSplitter::handle:hover {{
    background: {AMBER_BTN};
}}

/* ── Text edit (log output) ───────────────────────────────────────────────── */
QTextEdit, QTextBrowser {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    color: {PHOSPHOR_MID};
    selection-background-color: {PHOSPHOR_GLOW};
    selection-color: {PHOSPHOR_HOT};
}}
QTextEdit[monospace="true"] {{
    background: {BG_INSET};
    color: {PHOSPHOR_MID};
    font-family: "JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", monospace;
    font-size: {px(12)}px;
    border-color: {BORDER_DARK};
    border-radius: 4px;
    padding: 4px;
}}

/* ── Dialog ───────────────────────────────────────────────────────────────── */
QDialog {{
    background: {CONTENT_BG};
}}

/* ── Message boxes ────────────────────────────────────────────────────────── */
QMessageBox {{
    background: {BG_CARD};
}}

/* ── Labels ───────────────────────────────────────────────────────────────── */
QLabel[heading="true"] {{
    font-size: {px(15)}px;
    font-weight: 700;
    color: {PHOSPHOR_HOT};
}}
QLabel[muted="true"] {{
    color: {PHOSPHOR_DIM};
    font-size: {px(12)}px;
}}
QLabel[status_ok="true"] {{
    color: {STATUS_OK};
    font-weight: 600;
}}
QLabel[status_err="true"] {{
    color: {STATUS_ERR};
    font-weight: 600;
}}

/* ── Form layout label column ─────────────────────────────────────────────── */
QFormLayout QLabel {{
    color: {PHOSPHOR_DIM};
    font-size: {px(11)}px;
    font-weight: 500;
    letter-spacing: 1px;
    padding-right: 4px;
    text-transform: uppercase;
}}

"""

# Built once at import time; rebuild with build_app_qss() after changing scale
APP_QSS = build_app_qss()

# ---------------------------------------------------------------------------
# Convenience: apply visual property shorthand
# ---------------------------------------------------------------------------

def apply_phosphor_glow(widget, color: str = PHOSPHOR_MID,
                        blur: int = 12, strength: float = 0.55,
                        xOffset: float = 0.0, yOffset: float = 0.0) -> None:
    """Wrap a widget in a QGraphicsDropShadowEffect to produce an outer
    phosphor halo — the warm light that bleeds beyond the button edge on
    a real CRT phosphor screen.

    Parameters
    ----------
    widget  : any QWidget subclass
    color   : hex colour string for the glow (default: amber PHOSPHOR_MID)
    blur    : blur radius in pixels (larger = softer / wider spread)
    strength: alpha 0–1 for the glow colour
    xOffset : horizontal bloom shift (small values give uneven phosphor feel)
    yOffset : vertical bloom shift
    """
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    from PySide6.QtGui import QColor
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(xOffset, yOffset)
    c = QColor(color)
    c.setAlphaF(strength)
    effect.setColor(c)
    widget.setGraphicsEffect(effect)


def remove_glow(widget) -> None:
    """Remove any QGraphicsEffect applied to a widget."""
    widget.setGraphicsEffect(None)


def make_run_button(btn) -> None:
    """Style a QPushButton as the primary Run action (rose/pink glow)."""
    btn.setProperty("accent", "true")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    apply_phosphor_glow(btn, color=ROSE_ACCENT, blur=14, strength=0.50)


def make_blue_button(btn) -> None:
    """Style a QPushButton as a blue accent action (AIC blue glow)."""
    btn.setProperty("accentBlue", "true")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    apply_phosphor_glow(btn, color="#78B4DC", blur=14, strength=0.50)


def make_glow_bulb_button(text: str, parent=None):
    """Create a GlowBulbButton — analog backlit pushbutton with baby-blue glow.

    Returns a fully styled GlowBulbButton instance (not a plain QPushButton).
    Use this for high-visibility actions like "Run AIC".
    """
    from gui.widgets.glow_bulb_button import GlowBulbButton
    return GlowBulbButton(text, parent)


def make_secondary_button(btn) -> None:
    """Style a QPushButton as an amber secondary action (amber glow)."""
    btn.setProperty("secondary", "true")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    apply_phosphor_glow(btn, color=AMBER_BTN, blur=10, strength=0.45)


def make_monospace_textedit(te) -> None:
    """Style a QTextEdit as dark monospace terminal output."""
    te.setProperty("monospace", "true")
    te.style().unpolish(te)
    te.style().polish(te)


def make_glow_label(label, color: str = PHOSPHOR_HOT,
                    blur: int = 8, strength: float = 0.60) -> None:
    """Apply a phosphor text-glow to a QLabel.

    Works by adding a QGraphicsDropShadowEffect with zero offset so the
    shadow radiates symmetrically — mimicking how phosphor text blooms on
    a CRT screen.
    """
    apply_phosphor_glow(label, color=color, blur=blur, strength=strength)


# ---------------------------------------------------------------------------
# Shared panel / section building blocks
#
# Use these in every panel and page to keep the amber terminal aesthetic
# consistent without duplicating QSS strings.
# ---------------------------------------------------------------------------

#: Radial gradient string for content pane backgrounds.
PANE_BG_GRADIENT = (
    "qradialgradient(cx:0.5,cy:0.5,radius:0.9,"
    "stop:0.00 #201A08,stop:0.70 #130E04,stop:1.00 #090702)"
)


def make_section_label(text: str) -> "QLabel":
    """Return an all-caps muted section header label (SCOPE / OUTPUT / etc.)."""
    from PySide6.QtWidgets import QLabel
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
        f" letter-spacing: 1.5px; background: transparent; border: none;"
        f" padding: 6px 0 2px 0;"
    )
    return lbl


def make_h_rule() -> "QFrame":
    """Return a 1 px amber gradient separator — bright at centre, fading at edges."""
    from PySide6.QtWidgets import QFrame
    rule = QFrame()
    rule.setFixedHeight(1)
    rule.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(240,168,48,0),
                stop:0.20 rgba(240,168,48,89),
                stop:0.50 rgba(240,168,48,179),
                stop:0.80 rgba(240,168,48,89),
                stop:1.00 rgba(240,168,48,0));
            border: none;
        }
    """)
    return rule


def make_content_pane(object_name: str = "contentPane") -> "QFrame":
    """Return a QFrame styled as a content pane (radial gradient + amber top border).

    The object_name must be unique per call site so the stylesheet selector
    ``QFrame#<name>`` targets only this frame.
    """
    from PySide6.QtWidgets import QFrame
    pane = QFrame()
    pane.setObjectName(object_name)
    pane.setStyleSheet(
        f"QFrame#{object_name} {{"
        f"  background: {PANE_BG_GRADIENT};"
        f"  border: 1px solid {BORDER_DARK};"
        f"  border-top-color: {BORDER_AMBER};"
        f"  border-radius: 8px;"
        f"}}"
    )
    return pane


# ---------------------------------------------------------------------------
# Shared splitter with grip-dot handle
# ---------------------------------------------------------------------------

class GripSplitter:
    """Factory that returns a QSplitter with a custom void-background handle.

    Usage::

        from gui.styles import GripSplitter
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)
    """

    @staticmethod
    def create(orientation):
        from PySide6.QtWidgets import QSplitter, QSplitterHandle
        from PySide6.QtGui import QPainter, QColor
        from PySide6.QtCore import Qt

        class _GripHandle(QSplitterHandle):
            _BG    = QColor(BG_VOID)
            _DOT   = QColor(PHOSPHOR_DIM)
            _DOT_H = QColor("#8A5E1A")

            def __init__(self, orientation, parent):
                super().__init__(orientation, parent)
                # Override global QSplitter::handle QSS so paintEvent controls rendering
                self.setStyleSheet("QSplitterHandle { background: transparent; }")

            def paintEvent(self, event):
                p = QPainter(self)
                p.fillRect(self.rect(), self._BG)
                p.fillRect(0, 0, 1, self.height(), QColor(BORDER_DARK))
                dot = self._DOT_H if self.underMouse() else self._DOT
                p.setBrush(dot)
                p.setPen(Qt.PenStyle.NoPen)
                cx = self.width() // 2
                cy = self.height() // 2
                for dy in (-6, 0, 6):
                    p.drawEllipse(cx - 2, cy + dy - 2, 4, 4)
                p.end()

            def enterEvent(self, event):
                self.update()
                super().enterEvent(event)

            def leaveEvent(self, event):
                self.update()
                super().leaveEvent(event)

        class _GripSplitter(QSplitter):
            def createHandle(self):
                return _GripHandle(self.orientation(), self)

        return _GripSplitter(orientation)
