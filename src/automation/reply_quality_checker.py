"""
Discussion Reply Quality Checker.

Evaluates whether a student's discussion forum reply substantively
engages with the original post, or is just generic agreement/padding.

Backend priority (Apple Silicon): MLX → Ollama → word-count-only fallback.
"""

import re
import logging
import sys
from pathlib import Path

# Allow importing llm_backend from the insights package
sys.path.insert(0, str(Path(__file__).parent.parent))

SYSTEM_PROMPT = """You evaluate whether a student's discussion forum reply shows ANY intellectual engagement at all.

Mark the reply SUBSTANTIVE if it does ANY of these (even just one, even briefly):
- Mentions a specific idea, concept, event, or detail from the course or the post
- Connects the topic to the student's own life, identity, background, or experience
- Reflects on how the topic made them think or feel about something specific
- Applies a course concept or framework, even while agreeing
- Asks a genuine question or raises a what-if
- Offers a different angle, even a small one

Mark the reply NOT SUBSTANTIVE only if ALL of these are true:
- The student does not engage with any specific idea — they only express agreement or praise
- There is no personal reflection, no new connection, and no application of concepts
- The reply could be copy-pasted onto any post in the class and still make sense because it says nothing specific

When in doubt, mark SUBSTANTIVE. A reply that tries to engage intellectually — even clumsily — earns credit.

Respond with only: SUBSTANTIVE or NOT SUBSTANTIVE"""


class ReplyQualityChecker:
    """
    Checks discussion reply quality using the best available local LLM.

    On Apple Silicon: prefers MLX (no server needed, no cold-start timeouts).
    Elsewhere: uses Ollama.
    Falls back to word-count-only (always PASS) if no LLM is available.
    """

    def __init__(self):
        self.logger = logging.getLogger("autograder_automation")
        self._backend = None
        self._backend_checked = False

    def _get_backend(self):
        if self._backend_checked:
            return self._backend
        self._backend_checked = True
        try:
            from insights.llm_backend import auto_detect_backend
            backend = auto_detect_backend(tier="lightweight")
            if backend:
                self.logger.info(f"      🤖 Reply checker using backend: {backend.name} ({backend.model})")
                self._backend = backend
            else:
                self.logger.warning("      ⚠️  No LLM backend available — using word-count-only fallback")
        except Exception as e:
            self.logger.warning(f"      ⚠️  Could not load LLM backend ({e}) — using word-count-only fallback")
        return self._backend

    def _clean_html(self, text: str) -> str:
        return re.sub(r'<[^>]+>', ' ', text or "").strip()

    def _truncate(self, text: str, max_words: int = 300) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    def is_substantive(self, original_post: str, reply: str) -> bool:
        """
        Returns True if the reply substantively engages with the original post.
        Defaults to True on any error (lean toward granting credit).
        """
        backend = self._get_backend()
        if backend is None:
            return True  # no LLM — grant credit

        clean_post = self._truncate(self._clean_html(original_post))
        clean_reply = self._truncate(self._clean_html(reply))
        user_prompt = f"ORIGINAL POST:\n{clean_post}\n\nSTUDENT REPLY:\n{clean_reply}"

        try:
            from insights.llm_backend import send_text
            response = send_text(
                backend,
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                max_tokens=10,
            ).strip().upper()

            if "NOT SUBSTANTIVE" in response:
                return False
            elif "SUBSTANTIVE" in response:
                return True
            else:
                self.logger.warning(f"        ⚠️  Unparseable LLM response: '{response[:50]}' — defaulting to substantive")
                return True

        except Exception as e:
            self.logger.warning(f"        ⚠️  LLM check failed ({e}) — defaulting to substantive")
            return True


# ---------------------------------------------------------------------------
# Backwards-compatibility shim — existing code instantiates OllamaReplyChecker
# ---------------------------------------------------------------------------
class OllamaReplyChecker(ReplyQualityChecker):
    """Legacy name kept for compatibility. Now delegates to ReplyQualityChecker."""
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        super().__init__()
        # model/base_url ignored — backend is auto-detected
