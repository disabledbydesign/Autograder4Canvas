#!/usr/bin/env python3
"""
Canvas Autograder Bootstrap
Cross-platform setup: Python check, venv, pip install, credentials, then launch.
Stdlib-only (runs before venv exists).
"""

import os
import sys
import subprocess
import platform
import shutil
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. UTF-8 encoding fix for Windows cmd.exe
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7

# ---------------------------------------------------------------------------
# 2. Python version check (3.7+)
# ---------------------------------------------------------------------------
def check_python_version():
    v = sys.version_info
    if v >= (3, 7):
        return
    print(f"Python 3.7+ is required (you have {v.major}.{v.minor}.{v.micro}).")
    print("Download from: https://www.python.org/downloads/")
    try:
        import webbrowser
        webbrowser.open("https://www.python.org/downloads/")
    except Exception:
        pass
    input("Press Enter to exit...")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Microsoft Store stub detection (Windows)
# ---------------------------------------------------------------------------
def is_ms_store_python():
    if sys.platform != "win32":
        return False
    return "WindowsApps" in sys.executable

# ---------------------------------------------------------------------------
# 4. Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()          # src/ or Resources/
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"
AUTOGRADER_SCRIPT = SCRIPT_DIR / "run_autograder.py"

def _get_venv_dir():
    """Determine venv location."""
    if "Contents/Resources" in str(SCRIPT_DIR):
        return Path.home() / ".canvas_autograder_venv"
    return SCRIPT_DIR.parent / ".venv"

VENV_DIR = _get_venv_dir()

def _venv_python():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

def _venv_pip():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"

# ---------------------------------------------------------------------------
# 5. Venv creation / validation
# ---------------------------------------------------------------------------
def ensure_venv():
    """Create or repair the virtual environment."""
    venv_py = _venv_python()

    # If venv python exists, health-check it
    if venv_py.exists():
        try:
            subprocess.run(
                [str(venv_py), "-c", ""],
                capture_output=True, timeout=10
            ).check_returncode()
            return  # healthy
        except Exception:
            print("  Virtual environment is broken -- rebuilding...")
            shutil.rmtree(VENV_DIR, ignore_errors=True)

    print("  Creating virtual environment (one-time setup)...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True
    )
    if result.returncode != 0:
        print("  ERROR: Could not create virtual environment.")
        print(result.stderr.decode(errors="replace"))
        if sys.platform == "win32":
            print()
            print("  This may happen with Microsoft Store Python.")
            print("  Install Python from https://www.python.org/downloads/")
            try:
                import webbrowser
                webbrowser.open("https://www.python.org/downloads/")
            except Exception:
                pass
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        input("Press Enter to exit...")
        sys.exit(1)
    print("  Virtual environment created.")

# ---------------------------------------------------------------------------
# 6. pip install
# ---------------------------------------------------------------------------
def ensure_dependencies():
    """Install packages from requirements.txt if any are missing."""
    if not REQUIREMENTS_FILE.exists():
        return

    pip_exe = _venv_pip()
    venv_py = _venv_python()

    if not pip_exe.exists() or not venv_py.exists():
        # venv broken somehow
        ensure_venv()

    # Quick check: are all required packages installed?
    try:
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            reqs = [
                line.strip().split("==")[0].split(">=")[0].split("[")[0].lower()
                for line in f if line.strip() and not line.startswith("#")
            ]
        result = subprocess.run(
            [str(pip_exe), "list", "--format=freeze"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            installed = {
                line.split("==")[0].lower()
                for line in result.stdout.strip().splitlines()
                if "==" in line
            }
            if all(r in installed for r in reqs):
                return  # all present
    except Exception:
        pass

    print("  Installing required packages...")
    # Upgrade pip first
    subprocess.run(
        [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        capture_output=True
    )
    result = subprocess.run(
        [str(pip_exe), "install", "--quiet", "-r", str(REQUIREMENTS_FILE)],
        capture_output=True
    )
    if result.returncode != 0:
        print("  ERROR: Package installation failed.")
        print(result.stderr.decode(errors="replace"))
        print("  Check your internet connection and try again.")
        input("Press Enter to exit...")
        sys.exit(1)
    print("  Packages installed.")

# ---------------------------------------------------------------------------
# 7. Apple Silicon extras (mlx-lm + outlines) — non-blocking
# ---------------------------------------------------------------------------

def _pip_install_silent(venv_pip_path, *packages):
    """Install one or more packages quietly. Returns True on success."""
    result = subprocess.run(
        [str(venv_pip_path), "install", "--quiet"] + list(packages),
        capture_output=True,
    )
    return result.returncode == 0


def ensure_spacy_model():
    """Download en_core_web_sm if spaCy is installed but the model is missing.

    Non-blocking — logs a note on failure but never prevents launch.
    Named entity recognition and assignment fingerprinting silently skip
    when this model is absent, so this prevents a quiet feature gap.
    """
    venv_py = _venv_python()
    if not venv_py.exists():
        return
    try:
        result = subprocess.run(
            [str(venv_py), "-c", "import spacy; spacy.load('en_core_web_sm')"],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            return  # already installed
        # spaCy present but model missing — download it
        print("  Downloading spaCy language model (en_core_web_sm)...")
        dl = subprocess.run(
            [str(venv_py), "-m", "spacy", "download", "en_core_web_sm"],
            capture_output=True, timeout=120,
        )
        if dl.returncode == 0:
            print("  spaCy model ready.")
        else:
            print("  Note: spaCy model download failed (NER features will be skipped).")
    except Exception:
        pass  # non-blocking


def ensure_apple_silicon_extras():
    """Install MLX inference and constrained-generation packages on arm64 Macs.

    These are optional — failures print a note but never block launch.
    The Insights setup dialog also offers these installs, but doing it here
    means Apple Silicon users get them on first launch without any extra steps.
    """
    if not (platform.system() == "Darwin" and platform.machine() == "arm64"):
        return

    pip_exe = _venv_pip()
    if not pip_exe.exists():
        return

    # Check what's already installed to avoid slow no-op pip calls
    try:
        result = subprocess.run(
            [str(pip_exe), "list", "--format=freeze"],
            capture_output=True, text=True,
        )
        installed = {
            line.split("==")[0].lower()
            for line in result.stdout.strip().splitlines()
            if "==" in line
        }
    except Exception:
        installed = set()

    if "mlx-lm" not in installed:
        print("  Apple Silicon detected — installing MLX inference framework...")
        if _pip_install_silent(pip_exe, "mlx-lm"):
            print("  MLX installed.")
        else:
            print("  Note: MLX install failed (non-critical — Ollama will be used instead).")

    if "outlines" not in installed:
        print("  Installing Outlines constrained generation...")
        if _pip_install_silent(pip_exe, "outlines[mlxlm]"):
            print("  Outlines installed.")
        else:
            print("  Note: Outlines install failed (non-critical — unconstrained generation will be used).")


# ---------------------------------------------------------------------------
# 9. Credential management (JSON-based, multi-profile)
# ---------------------------------------------------------------------------
#
# credentials.json format:
# {
#   "active_profile": "cabrillo",
#   "profiles": {
#     "cabrillo": {
#       "canvas_base_url": "https://cabrillo.instructure.com",
#       "canvas_api_token": "..."
#     }
#   }
# }

def _get_config_dir():
    """Platform config directory (mirrors autograder_utils.get_config_dir)."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        d = base / "CanvasAutograder"
    elif system == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        d = Path.home() / ".config" / "CanvasAutograder"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _creds_file():
    return _get_config_dir() / "credentials.json"

def _load_creds():
    cf = _creds_file()
    if cf.exists():
        try:
            with open(cf, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def _save_creds(data):
    cf = _creds_file()
    cf.parent.mkdir(parents=True, exist_ok=True)
    with open(cf, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _profile_name_from_url(url):
    """Derive a short profile name from a Canvas URL."""
    # https://cabrillo.instructure.com -> cabrillo
    # https://canvas.university.edu    -> canvas.university.edu
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or url
    except Exception:
        host = url
    if host.endswith(".instructure.com"):
        return host.replace(".instructure.com", "")
    return host

def _get_active_profile(data):
    """Return (name, profile_dict) for the active profile, or (None, {})."""
    profiles = data.get("profiles", {})
    active = data.get("active_profile", "")
    if active and active in profiles:
        return active, profiles[active]
    # Fallback: first profile
    if profiles:
        name = next(iter(profiles))
        return name, profiles[name]
    return None, {}

def _migrate_old_credentials():
    """Migrate from old flat format, credentials.bat, or env vars."""
    data = _load_creds()

    # Already in profile format?
    if "profiles" in data and data["profiles"]:
        return data

    # Collect old flat credentials (from previous bootstrap format)
    url = data.get("canvas_base_url", "")
    token = data.get("canvas_api_token", "")

    # Try old credentials.bat files
    if not (url and token):
        bat_paths = []
        project_root = SCRIPT_DIR.parent
        bat_paths.append(project_root / "scripts" / "windows" / "credentials.bat")
        bat_paths.append(project_root / "credentials.bat")
        old_creds_env = os.environ.get("AUTOGRADER_CREDS_FILE", "")
        if old_creds_env:
            bat_paths.insert(0, Path(old_creds_env))

        for bat_path in bat_paths:
            if bat_path.exists():
                try:
                    with open(bat_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.lower().startswith("set "):
                                rest = line[4:]
                                if "=" in rest:
                                    k, v = rest.split("=", 1)
                                    k = k.strip().upper()
                                    if k == "CANVAS_BASE_URL" and v and "yourschool" not in v:
                                        url = url or v
                                    elif k == "CANVAS_API_TOKEN" and v and v != "your_api_token_here":
                                        token = token or v
                except Exception:
                    pass
                if url and token:
                    break

    # Env vars
    if not url:
        env_url = os.environ.get("CANVAS_BASE_URL", "")
        if env_url and "yourschool" not in env_url:
            url = env_url
    if not token:
        env_tok = os.environ.get("CANVAS_API_TOKEN", "")
        if env_tok and env_tok != "your_api_token_here":
            token = env_tok

    # Convert to profile format
    if url and token:
        name = _profile_name_from_url(url)
        data = {
            "active_profile": name,
            "profiles": {
                name: {"canvas_base_url": url, "canvas_api_token": token}
            }
        }
        _save_creds(data)
        print("  Migrated existing credentials to new profile format.")
    elif not data.get("profiles"):
        data = {"active_profile": "", "profiles": {}}

    return data

def _prompt_canvas_url_inline():
    """Simplified Canvas URL prompt (inline version for bootstrap, no deps)."""
    print()
    print("  " + "=" * 56)
    print("   Welcome to Canvas Autograder!")
    print("  " + "=" * 56)
    print()
    print("  Let's connect to your school's Canvas.")
    print()
    print("  Most Canvas sites look like:")
    print("    https://YOURSCHOOL.instructure.com")
    print()
    print("  Just type the part unique to your school.")
    print("  Example: if your Canvas is at myschool.instructure.com,")
    print("           type: myschool")
    print()
    print("  If your school uses a custom address (not instructure.com),")
    print("  type the full address instead, like: canvas.myuniversity.edu")
    print()

    while True:
        try:
            answer = input("  Your school name (or full address): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(1)
        if not answer:
            print("  Nothing entered -- you'll be asked again next time you launch.")
            sys.exit(1)

        if "." in answer or "/" in answer:
            url = answer.rstrip("/")
            if not url.startswith("http"):
                url = "https://" + url
        else:
            url = f"https://{answer}.instructure.com"

        print()
        print(f"  Your Canvas URL: {url}")
        try:
            ok = input("  Is this correct? (Y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(1)
        if ok in ("", "y", "yes"):
            return url
        print("  Let's try again.")
        print()


def _prompt_credentials(data):
    """Interactive first-time credential setup if no complete profile exists."""
    _, profile = _get_active_profile(data)

    if profile.get("canvas_base_url") and profile.get("canvas_api_token"):
        return data  # already have a complete profile

    # Need to create a new profile
    url = profile.get("canvas_base_url") or _prompt_canvas_url_inline()
    token = profile.get("canvas_api_token")

    if not token:
        print()
        print("  " + "=" * 56)
        print("   API Token Setup")
        print("  " + "=" * 56)
        print()
        print("  Now we need an API token so the program can read your")
        print("  Canvas courses and grades.")
        print()
        print("  How to get your token:")
        print(f"    1. Log in to Canvas at {url}")
        print("    2. Click your profile picture (top right)")
        print("    3. Click Settings")
        print("    4. Scroll to Approved Integrations")
        print("    5. Click + New Access Token, give it a name, click Generate")
        print("    6. Copy the token -- you won't be able to see it again!")
        print("    7. Paste it here")
        print()
        try:
            token = input("  API Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(1)
        if not token:
            print("  No token entered -- you'll be asked again next time you launch.")
            sys.exit(1)

    name = _profile_name_from_url(url)
    if "profiles" not in data:
        data["profiles"] = {}
    data["profiles"][name] = {"canvas_base_url": url, "canvas_api_token": token}
    data["active_profile"] = name
    _save_creds(data)
    print()
    print(f"  Profile '{name}' saved. You won't be asked again.")

    return data

def setup_credentials():
    """Load/migrate/prompt for credentials, set env vars."""
    data = _migrate_old_credentials()
    data = _prompt_credentials(data)

    _, profile = _get_active_profile(data)
    if profile.get("canvas_base_url"):
        os.environ["CANVAS_BASE_URL"] = profile["canvas_base_url"]
    if profile.get("canvas_api_token"):
        os.environ["CANVAS_API_TOKEN"] = profile["canvas_api_token"]

# ---------------------------------------------------------------------------
# 10. Launch autograder
# ---------------------------------------------------------------------------
def launch():
    """Exec into venv python + run_autograder.py."""
    venv_py = str(_venv_python())
    script = str(AUTOGRADER_SCRIPT)

    if not Path(script).exists():
        print(f"  ERROR: {script} not found.")
        input("Press Enter to exit...")
        sys.exit(1)

    args = [venv_py, script] + sys.argv[1:]

    if sys.platform == "win32":
        # os.execv doesn't truly replace on Windows; use subprocess
        rc = subprocess.run(args).returncode
        sys.exit(rc)
    else:
        os.execv(venv_py, args)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("========================================")
    print("   Canvas Autograder")
    print("========================================")
    print()

    check_python_version()

    if is_ms_store_python():
        print("  WARNING: Microsoft Store Python detected.")
        print("  This may not work correctly. Install from https://www.python.org/downloads/")
        print()

    ensure_venv()
    ensure_dependencies()
    ensure_spacy_model()
    ensure_apple_silicon_extras()
    setup_credentials()
    print()
    launch()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("  Bootstrap error")
        print("=" * 60)
        traceback.print_exc()
        print()
        input("Press Enter to close...")
        sys.exit(1)
