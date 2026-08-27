"""Allowlist for environment variables forwarded into the agent container.

Agents bring their own model API keys. The platform passes a small, explicitly
allowed set of variables to the *agent* container only (never the task-env
container), and records only the variable **names** — never their values.
"""

from __future__ import annotations

import re

from faraday.exceptions import FaradayError

_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ALLOWED_PREFIXES = (
    "OPENAI_",
    "ANTHROPIC_",
    "AZURE_OPENAI_",
    "GOOGLE_",
    "GEMINI_",
    "MISTRAL_",
    "GROQ_",
    "TOGETHER_",
    "OPENROUTER_",
    "DEEPSEEK_",
    "FARADAY_",
)


class EnvPolicyError(FaradayError):
    """Raised when a submitted env var is not on the allowlist."""


def _is_allowed(name: str) -> bool:
    if not _NAME.match(name):
        return False
    return name.endswith("_API_KEY") or name.startswith(_ALLOWED_PREFIXES)


def sanitize_agent_env(env: dict[str, str] | None) -> dict[str, str]:
    """Return ``env`` unchanged if every key is allowed and every value a string.

    Raises :class:`EnvPolicyError` naming the offending keys otherwise.
    ``None`` and ``{}`` return ``{}``.
    """
    if not env:
        return {}
    bad_names = sorted(k for k in env if not _is_allowed(k))
    if bad_names:
        raise EnvPolicyError(
            "disallowed agent env var(s): "
            + ", ".join(bad_names)
            + " (allowed: *_API_KEY or a known provider prefix)"
        )
    bad_values = sorted(k for k, v in env.items() if not isinstance(v, str))
    if bad_values:
        raise EnvPolicyError(f"agent env values must be strings: {', '.join(bad_values)}")
    return dict(env)
