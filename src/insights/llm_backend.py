"""
Unified LLM backend for the Insights Engine.

Adapted from EvalEye's llm_backend.py. Text-only (no vision tasks).

FERPA-safe local backends (recommended):
  - ollama:  Local models via Ollama REST API (localhost:11434)
  - mlx:     Apple Silicon text inference via mlx-vlm

External backends (FERPA warning — student data leaves this machine):
  - cloud:   Any OpenAI-compatible API endpoint

All backends implement: send_text(backend, prompt, system_prompt) -> str
"""

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception,
        before_sleep_log,
    )
    _TENACITY = True
except ImportError:
    _TENACITY = False

_OUTLINES = False


def _check_outlines() -> bool:
    """Lazy, cached check for outlines[mlxlm] availability.

    Returns True only when outlines is installed AND exposes the
    from_mlxlm API (added in outlines 0.1+).  Matches the _TENACITY
    pattern — avoids a heavy import at module load time.
    """
    global _OUTLINES
    if _OUTLINES:
        return True
    try:
        import outlines  # noqa: F401
        if not hasattr(outlines, "from_mlxlm"):
            return False
        _OUTLINES = True
        return True
    except ImportError:
        return False


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FERPA warning
# ---------------------------------------------------------------------------

FERPA_WARNING = (
    "\u26a0\ufe0f  FERPA WARNING: The cloud backend sends student submission "
    "data to an external API at {base_url}. This may not be FERPA-compliant "
    "unless your institution has a Data Processing Agreement (DPA) with the "
    "API provider.\n\n"
    "To use FERPA-safe local processing, use Ollama or MLX — student data "
    "never leaves your machine."
)


# ---------------------------------------------------------------------------
# Backend config
# ---------------------------------------------------------------------------

@dataclass
class BackendConfig:
    """Configuration for one LLM backend."""
    name: str                  # "ollama", "mlx", "cloud"
    model: str = ""            # model name/path
    base_url: str = ""         # API base URL (ollama/cloud)
    api_key: str = ""          # API key (cloud only)
    api_format: str = "openai" # "openai" or "anthropic"
    max_tokens: int = 4096
    temperature: float = 0.1   # low temp for structured output
    num_ctx: int = 8192        # Ollama context window (ignored by MLX/cloud)


# ---------------------------------------------------------------------------
# Model tier mapping
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "lightweight": "gemma3:12b",
    "medium": "gemma3:27b",
    "deep_thinking": "",  # requires cloud API — user must configure
}


def get_default_model(tier: str) -> str:
    """Return the default Ollama model name for a tier."""
    return DEFAULT_MODELS.get(tier, "gemma3:12b")


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_hardware() -> dict:
    """Detect hardware capabilities for AI model selection.

    Returns dict with: apple_silicon, ram_gb, can_run_12b, can_run_27b,
    description (human-readable summary).
    """
    import platform as _platform

    info = {
        "apple_silicon": False,
        "ram_gb": 0.0,
        "can_run_12b": False,
        "can_run_27b": False,
        "description": "Unknown hardware",
    }

    if _platform.system() == "Darwin" and _platform.machine() == "arm64":
        info["apple_silicon"] = True

    if _platform.system() == "Darwin":
        try:
            r = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            info["ram_gb"] = int(r.stdout.strip()) / (1024 ** 3)
        except Exception:
            pass
    elif _platform.system() == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        info["ram_gb"] = int(line.split()[1]) / (1024 * 1024)
                        break
        except Exception:
            pass

    info["can_run_12b"] = info["ram_gb"] >= 14
    info["can_run_27b"] = info["ram_gb"] >= 28

    parts = []
    if info["apple_silicon"]:
        parts.append("Apple Silicon")
    parts.append(f"{info['ram_gb']:.0f} GB RAM")
    info["description"] = " \u00b7 ".join(parts)

    return info


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("RateLimitError", "APIStatusError", "HTTPStatusError",
                "TimeoutException", "ConnectError"):
        return True
    module = getattr(type(exc), "__module__", "") or ""
    return module.startswith("httpx")


def _with_retry(fn):
    if not _TENACITY:
        return fn
    return retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )(fn)


# ---------------------------------------------------------------------------
# Ollama availability detection (reuses reply_quality_checker pattern)
# ---------------------------------------------------------------------------

_ollama_available: Optional[bool] = None


def check_ollama(base_url: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running. Auto-launches if not."""
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available

    import requests

    # Try to reach Ollama
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        if r.status_code == 200:
            _ollama_available = True
            return True
    except Exception:
        pass

    # Try to launch it
    log.info("Ollama not running — attempting to start...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(10):
            time.sleep(1)
            try:
                r = requests.get(f"{base_url}/api/tags", timeout=2)
                if r.status_code == 200:
                    log.info("Ollama started successfully")
                    _ollama_available = True
                    return True
            except Exception:
                pass
        log.warning("Ollama didn't come up in time")
    except FileNotFoundError:
        log.warning("ollama command not found")
    except Exception as e:
        log.warning("Failed to launch Ollama: %s", e)

    _ollama_available = False
    return False


def check_ollama_model(model: str, base_url: str = "http://localhost:11434") -> bool:
    """Check if a specific model is available in Ollama."""
    import requests
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return any(
                m == model or m.startswith(model.split(":")[0])
                for m in models
            )
    except Exception:
        pass
    return False


def reset_ollama_cache() -> None:
    """Reset the cached Ollama availability check."""
    global _ollama_available
    _ollama_available = None


# ---------------------------------------------------------------------------
# MLX availability
# ---------------------------------------------------------------------------

# MLX serialization lock — MLX's Metal kernel does not support concurrent calls
# from multiple threads sharing the same loaded model.  All MLX generate() calls
# must be serialized.  Orphaned threads from timed-out calls will block here until
# the previous call completes before the next one starts.
_mlx_lock = threading.Lock()

# MLX throttle — minimum seconds between calls.  Metal can hang if calls arrive
# back-to-back with no breathing room.  Loaded from insights_throttle_delay
# setting; default matches the settings default (20 s).  Raised from 15s after
# observation stage added a third inference pass per student.
_mlx_throttle_delay: float = 20.0
_last_mlx_call: float = 0.0


def set_mlx_throttle(seconds: float) -> None:
    """Set the minimum gap (seconds) between MLX generate() calls."""
    global _mlx_throttle_delay
    _mlx_throttle_delay = max(0.0, float(seconds))


def unload_mlx_model() -> None:
    """Release the cached MLX model and free unified memory.

    Call between pipeline stages (e.g., after coding, before observations)
    to give Metal a clean slate.  The model will be re-loaded on the next
    send_text() call — costs ~15-20s but prevents the cumulative memory
    fragmentation that causes Metal deadlocks on 16 GB machines.
    """
    if hasattr(_mlx_text_inner, "_cache") and _mlx_text_inner._cache:
        log.info("Unloading MLX model(s) to free Metal memory...")

        # Clear in dependency order: generators reference outlines_model,
        # outlines_model references raw model — innermost first.
        if hasattr(_mlx_text_inner, "_generators"):
            _mlx_text_inner._generators.clear()

        if hasattr(_mlx_text_inner, "_outlines_model"):
            _mlx_text_inner._outlines_model.clear()

        # Explicitly delete model/tokenizer references before clearing the dict.
        # This ensures Python refcounts drop to zero so Metal buffers are released
        # when gc.collect() runs, rather than lingering until the dict is reaped.
        for key in list(_mlx_text_inner._cache.keys()):
            model, tokenizer = _mlx_text_inner._cache.pop(key)
            del model, tokenizer
        _mlx_text_inner._cache.clear()
        import gc
        gc.collect()
        try:
            import mlx.core as mx
            # Flush the Metal cache after gc has dropped all array references.
            (mx.clear_cache if hasattr(mx, "clear_cache") else mx.metal.clear_cache)()
            # Temporarily set cache limit to 0 to force Metal to release all
            # reclaimable buffers, then restore.  On MLX versions without
            # set_cache_limit this is a no-op.
            _set_limit = getattr(mx, "set_cache_limit",
                                   getattr(mx.metal, "set_cache_limit", None))
            if _set_limit:
                _set_limit(0)
                _set_limit(2 ** 31)  # restore ~2 GB default
        except Exception:
            pass
        gc.collect()
        # Give the Metal driver time to asynchronously reclaim freed buffers.
        # Without this pause, the next model load can race the driver's cleanup
        # and hit OOM on 16 GB machines — same reason test scripts sleep 5s
        # between subprocesses.
        import time as _time
        _time.sleep(5)
        log.info("MLX model unloaded.")

_mlx_available: Optional[bool] = None


def check_mlx() -> bool:
    """Check if MLX text inference is available.

    Tries mlx_lm (text-only) first, then mlx_vlm (vision+language).
    Either package suffices for text generation.
    """
    global _mlx_available
    if _mlx_available is not None:
        return _mlx_available
    try:
        from mlx_lm import load, generate  # noqa: F401
        _mlx_available = True
    except ImportError:
        try:
            from mlx_vlm import load, generate  # noqa: F401
            _mlx_available = True
        except ImportError:
            _mlx_available = False
    return _mlx_available


# ---------------------------------------------------------------------------
# Auto-detect best available backend
# ---------------------------------------------------------------------------

def auto_detect_backend(
    tier: str = "lightweight",
    settings: Optional[dict] = None,
) -> Optional[BackendConfig]:
    """Auto-detect the best available backend for the given tier.

    When tier is "auto", checks for the best locally-available model:
    gemma3:27b first (medium tier), then gemma3:12b (lightweight).
    This means teachers with 32 GB+ RAM who have 27b installed get
    full-quality analysis automatically — no cloud enhancement needed.

    Returns None if no LLM backend is available.
    """
    s = settings or {}

    # --- Auto-tier: pick the best model that's already installed ----------
    if tier == "auto":
        ollama_url = s.get("insights_ollama_url", "http://localhost:11434")
        if check_ollama(ollama_url):
            if check_ollama_model("gemma3:27b", ollama_url):
                tier = "medium"
                log.info("Auto-tier: gemma3:27b available → medium")
            elif check_ollama_model("gemma3:12b", ollama_url):
                tier = "lightweight"
                log.info("Auto-tier: gemma3:12b available → lightweight")
            else:
                tier = "lightweight"  # fallback; will try other models
        else:
            tier = "lightweight"

    # Check for user-configured cloud API first (for medium/deep tiers)
    # Support both key names: GUI saves insights_cloud_url/key,
    # legacy code used insights_cloud_api_url/key
    cloud_url = s.get("insights_cloud_url", "") or s.get("insights_cloud_api_url", "")
    cloud_key = s.get("insights_cloud_key", "") or s.get("insights_cloud_api_key", "")
    cloud_model = s.get("insights_cloud_model", "")

    if tier == "deep_thinking" and cloud_url and cloud_key:
        return BackendConfig(
            name="cloud",
            model=cloud_model,
            base_url=cloud_url,
            api_key=cloud_key,
            api_format=s.get("insights_cloud_api_format", "openai"),
        )

    # Determine preferred backend order.
    # On Apple Silicon, default to MLX — it runs locally without Ollama and
    # uses 128K context natively. On other platforms, Ollama is the default.
    import platform as _platform
    _arm = _platform.machine() == "arm64"
    _default_backend = "mlx" if _arm else "ollama"
    preferred = s.get("insights_llm_backend", _default_backend)

    ollama_model = s.get("insights_translation_model", "")
    ollama_url = s.get("insights_ollama_url", "http://localhost:11434")
    if not ollama_model:
        ollama_model = get_default_model(tier)

    def _try_mlx():
        if check_mlx():
            return BackendConfig(
                name="mlx",
                model=s.get("insights_mlx_model",
                            "mlx-community/gemma-3-12b-it-4bit"),
            )
        return None

    def _try_ollama():
        if check_ollama(ollama_url):
            if check_ollama_model(ollama_model, ollama_url):
                return BackendConfig(
                    name="ollama", model=ollama_model, base_url=ollama_url,
                )
            if ollama_model != "gemma3:12b" and check_ollama_model("gemma3:12b", ollama_url):
                log.warning("Model '%s' not found, falling back to gemma3:12b", ollama_model)
                return BackendConfig(
                    name="ollama", model="gemma3:12b", base_url=ollama_url,
                )
            log.warning("Ollama running but no suitable model found")
        return None

    # Try preferred backend first, then the other
    if preferred == "mlx":
        result = _try_mlx() or _try_ollama()
    else:
        result = _try_ollama() or _try_mlx()

    if result:
        return result

    # Try cloud as last resort (any tier)
    if cloud_url and cloud_key:
        return BackendConfig(
            name="cloud",
            model=cloud_model,
            base_url=cloud_url,
            api_key=cloud_key,
            api_format=s.get("insights_cloud_api_format", "openai"),
        )

    return None


# ---------------------------------------------------------------------------
# send_text — unified interface
# ---------------------------------------------------------------------------

def send_text(
    backend: BackendConfig,
    prompt: str,
    system_prompt: str = "",
    max_tokens: Optional[int] = None,
    response_schema: Optional[type] = None,
) -> str:
    """Send a text prompt to the configured backend. Returns response text.

    Parameters
    ----------
    max_tokens : int, optional
        Override backend.max_tokens for this call only.  Use this to set
        tighter limits for stages that don't need long responses (e.g.,
        theme generation: 1500 tokens, vs. coding: 4096).
    response_schema : Pydantic model class, optional
        When provided and the backend supports it, enables constrained
        generation so the output is guaranteed to be valid JSON matching
        the schema.  Honoured by Ollama (v0.5+ format parameter) and
        MLX (Outlines FSM, when outlines[mlxlm] is installed).
        Ignored silently on cloud — that path still returns free-form text.

    Raises RuntimeError if the backend is unavailable or fails.
    """
    # Apply per-call max_tokens override without mutating the shared config
    effective = backend
    if max_tokens is not None and max_tokens != backend.max_tokens:
        from dataclasses import replace
        effective = replace(backend, max_tokens=max_tokens)

    if effective.name == "ollama":
        return _ollama_text(effective, prompt, system_prompt,
                            response_schema=response_schema)
    elif effective.name == "mlx":
        return _mlx_text(effective, prompt, system_prompt,
                         response_schema=response_schema)
    elif effective.name == "cloud":
        return _cloud_text(effective, prompt, system_prompt)
    else:
        raise ValueError(f"Unknown backend: {effective.name}")


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _ollama_text_impl(
    backend: BackendConfig,
    prompt: str,
    system_prompt: str,
    response_schema: Optional[type] = None,
) -> str:
    import requests

    base = backend.base_url or "http://localhost:11434"
    model = backend.model or "llama3.1:8b"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": backend.temperature,
            "num_predict": backend.max_tokens,
            "num_ctx": backend.num_ctx,
        },
    }

    # Constrained generation: Ollama v0.5+ accepts a JSON schema via the
    # `format` key and uses llama.cpp's GBNF grammar engine to enforce it
    # at token-generation time.  This eliminates parse failures entirely
    # for Ollama users — the output is valid JSON by construction.
    if response_schema is not None:
        try:
            payload["format"] = response_schema.model_json_schema()
            log.debug(
                "Ollama constrained generation enabled for schema: %s",
                response_schema.__name__,
            )
        except Exception as exc:
            log.warning(
                "Could not extract JSON schema from %s (%s) — "
                "falling back to unconstrained generation",
                response_schema, exc,
            )

    r = requests.post(
        f"{base}/api/chat",
        json=payload,
        timeout=600,  # 10 min — theme generation can be slow on 8B
    )
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


_ollama_text = _with_retry(_ollama_text_impl)


# ---------------------------------------------------------------------------
# MLX backend
# ---------------------------------------------------------------------------

def _mlx_text_impl(
    backend: BackendConfig, prompt: str, system_prompt: str,
    response_schema: Optional[type] = None,
) -> str:
    global _last_mlx_call
    # Serialize all MLX calls — Metal kernel doesn't support concurrent access
    # from multiple threads on the same loaded model.
    with _mlx_lock:
        # Throttle: wait until minimum gap since last call has elapsed.
        # Prevents Metal from hanging on rapid back-to-back calls.
        if _mlx_throttle_delay > 0 and _last_mlx_call > 0:
            elapsed = time.time() - _last_mlx_call
            if elapsed < _mlx_throttle_delay:
                wait = _mlx_throttle_delay - elapsed
                log.debug("MLX throttle: waiting %.1fs before next call", wait)
                time.sleep(wait)
        result = _mlx_text_inner(backend, prompt, system_prompt,
                                 response_schema=response_schema)
        # Release intermediate Metal buffers after each call.
        # Without this, repeated inference fragments the unified memory pool
        # on 16 GB machines, eventually causing Metal command buffer deadlocks.
        try:
            import mlx.core as mx
            (mx.clear_cache if hasattr(mx, 'clear_cache') else mx.metal.clear_cache)()
        except Exception:
            pass
        _last_mlx_call = time.time()
        return result


def _mlx_text_inner(
    backend: BackendConfig, prompt: str, system_prompt: str,
    response_schema: Optional[type] = None,
) -> str:
    # Try mlx_lm first (text-only, simpler API), fall back to mlx_vlm
    try:
        from mlx_lm import load as mlx_load, generate as mlx_generate
        _use_vlm = False
    except ImportError:
        from mlx_vlm import load as mlx_load, generate as mlx_generate  # type: ignore[no-redef]
        _use_vlm = True

    model_name = backend.model or "mlx-community/Qwen2.5-7B-Instruct-4bit"

    # Module-level cache (attached to the inner function, not the dispatcher)
    if not hasattr(_mlx_text_inner, "_cache"):
        _mlx_text_inner._cache = {}

    if model_name not in _mlx_text_inner._cache:
        model, tokenizer = mlx_load(model_name)
        _mlx_text_inner._cache[model_name] = (model, tokenizer)

    model, tokenizer = _mlx_text_inner._cache[model_name]

    # Constrained generation via Outlines (optional — falls back to unconstrained)
    if response_schema is not None and not _use_vlm and _check_outlines():
        try:
            return _mlx_constrained_generate(
                model, tokenizer, model_name,
                backend, prompt, system_prompt, response_schema,
            )
        except Exception as exc:
            log.warning(
                "Outlines constrained generation failed (%s) — "
                "falling back to unconstrained MLX generation", exc,
            )
            # Fall through to existing unconstrained path

    # Build chat-formatted prompt
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    if _use_vlm:
        # mlx_vlm path (vision-language models)
        from mlx_vlm.prompt_utils import apply_chat_template  # type: ignore[import]
        from mlx_vlm.utils import load_config  # type: ignore[import]
        config = load_config(model_name)
        formatted = apply_chat_template(tokenizer, config, full_prompt, num_images=0)
        result = mlx_generate(model, tokenizer, formatted, max_tokens=backend.max_tokens, verbose=False)
        return result.text if hasattr(result, "text") else str(result)
    else:
        # mlx_lm path — apply chat template via tokenizer if available
        if hasattr(tokenizer, "apply_chat_template"):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            formatted = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
        else:
            formatted = full_prompt
        return mlx_generate(
            model, tokenizer, prompt=formatted,
            max_tokens=backend.max_tokens, verbose=False,
        )


def _mlx_constrained_generate(
    model: object,
    tokenizer: object,
    model_name: str,
    backend: BackendConfig,
    prompt: str,
    system_prompt: str,
    response_schema: type,
) -> str:
    """Run MLX inference with Outlines FSM-constrained JSON generation.

    Uses a two-tier cache on top of the raw model/tokenizer cache:
      _mlx_text_inner._outlines_model[model_name]        — lightweight wrapper
      _mlx_text_inner._generators[(model_name, schema)]  — compiled FSM

    The FSM is compiled once per (model, schema) pair — typically <5s for
    _CodingOutput's 13 simple fields.  Subsequent calls reuse the compiled
    generator with zero overhead.

    Returns a JSON string (the Pydantic instance serialised via
    model_dump_json()) — preserves the send_text() -> str contract so
    callers' parse_json_response() still works unchanged.
    """
    import outlines
    import outlines.generate as og

    # --- Outlines model wrapper (lightweight — same Metal buffers as raw model) ---
    if not hasattr(_mlx_text_inner, "_outlines_model"):
        _mlx_text_inner._outlines_model = {}

    if model_name not in _mlx_text_inner._outlines_model:
        log.info("Building Outlines mlxlm wrapper for %s", model_name)
        _mlx_text_inner._outlines_model[model_name] = outlines.from_mlxlm(
            model, tokenizer
        )

    outlines_model = _mlx_text_inner._outlines_model[model_name]

    # --- FSM-compiled generator (compiled once per schema class) ---
    if not hasattr(_mlx_text_inner, "_generators"):
        _mlx_text_inner._generators = {}

    gen_key = (model_name, response_schema)
    if gen_key not in _mlx_text_inner._generators:
        log.info(
            "Compiling Outlines FSM for schema %s on model %s — "
            "one-time cost, cached for subsequent calls",
            response_schema.__name__, model_name,
        )
        _mlx_text_inner._generators[gen_key] = og.json(
            outlines_model, response_schema
        )

    generator = _mlx_text_inner._generators[gen_key]

    # --- Format prompt with chat template (mirrors unconstrained path) ---
    if hasattr(tokenizer, "apply_chat_template"):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        formatted = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
    else:
        formatted = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    log.debug("MLX constrained generation via Outlines for schema %s",
              response_schema.__name__)

    result = generator(
        formatted,
        max_tokens=backend.max_tokens,
        temperature=backend.temperature,
    )

    # Outlines returns a Pydantic model instance — serialise to JSON string
    # so the send_text() -> str contract is preserved.
    return result.model_dump_json()


_mlx_text = _mlx_text_impl  # no retry needed for local


# ---------------------------------------------------------------------------
# Cloud backend (OpenAI-compatible or Anthropic)
# ---------------------------------------------------------------------------

def _cloud_text_impl(
    backend: BackendConfig, prompt: str, system_prompt: str
) -> str:
    if backend.api_format == "anthropic":
        return _anthropic_text(backend, prompt, system_prompt)
    return _openai_text(backend, prompt, system_prompt)


def _openai_text(backend: BackendConfig, prompt: str, system_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=backend.api_key, base_url=backend.base_url)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=backend.model,
        max_tokens=backend.max_tokens,
        temperature=backend.temperature,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _anthropic_text(backend: BackendConfig, prompt: str, system_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(
        api_key=backend.api_key,
        base_url=backend.base_url or None,
    )
    kwargs = {
        "model": backend.model,
        "max_tokens": backend.max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = client.messages.create(**kwargs)
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


_cloud_text = _with_retry(_cloud_text_impl)


# ---------------------------------------------------------------------------
# JSON parsing utility
# ---------------------------------------------------------------------------

def _clean_llm_json(text: str) -> str:
    """Pre-process LLM output to fix common JSON generation artifacts.

    Handles two predictable 8B model failure modes:

    1. Double-brace artifact: model outputs {{ }} instead of { }
       (Python f-string template confusion from training data).
       In JSON, {{ is never valid, so collapsing is always safe.

    2. Invalid escape sequences: model writes \\s, \\c, \\d etc. inside
       string values.  Only \\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t,
       and \\uNNNN are valid JSON escapes.  Stray backslashes are doubled
       so they parse as literal backslashes in the string value.
    """
    import re

    # 1. Collapse Python-style double braces to single JSON braces
    #    Do this before escape-fixing so {{ doesn't confuse the regex.
    text = text.replace("{{", "{").replace("}}", "}")

    # 2. Fix invalid escape sequences inside JSON string values.
    #    Replace \X where X is not a valid JSON escape character with \\X.
    #    Valid single-char escapes: " \ / b f n r t
    #    Valid unicode escape: u followed by 4 hex digits (lookahead keeps 'u')
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)

    # 3. Fix \uXXXX where the 4 chars after 'u' are not all hex digits.
    #    The pass above preserves \u because 'u' is in the allowed set, but
    #    json.loads still raises "Invalid \uXXXX escape" when the hex digits
    #    are invalid (e.g. \uFOO, \u003, \uXYZW).  Double the backslash so
    #    it parses as a literal backslash + 'u' instead.
    text = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', text)

    return text


def parse_json_response(text: str) -> dict:
    """Parse JSON from an LLM response, handling markdown code fences
    and common 8B model generation artifacts (double-braces, bad escapes).
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try to find JSON object/array boundaries
    start = -1
    for i, c in enumerate(text):
        if c in "{[":
            start = i
            break
    if start > 0:
        text = text[start:]

    # Find matching end
    if text.startswith("{"):
        depth = 0
        for i, c in enumerate(text):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    text = text[: i + 1]
                    break
    elif text.startswith("["):
        depth = 0
        for i, c in enumerate(text):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    text = text[: i + 1]
                    break

    # First attempt: parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second attempt: apply artifact cleanup and retry before logging failure
    cleaned = _clean_llm_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.warning("JSON parse error: %s — raw: %.200s", e, text)
        return {"_parse_error": str(e), "_raw": text[:1000]}
