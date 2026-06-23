"""Provider-agnostic LLM adapter (Layer 3 / Enhancement #6).

One interface, swappable backend (Claude default, OpenAI fallback) chosen by
`settings.ai_provider`. Returns parsed JSON validated by the caller. Providers
are lazy-imported so the package loads without the SDKs present.

This is the *minimal* adapter needed by Phase 4's classification tiebreak; the
full validation/repair prompts land in Phase 7 reusing this same surface.
"""
from __future__ import annotations

import json
import logging

from app.config import settings
from app.core.exceptions import AIValidationError

log = logging.getLogger("freight.llm")


class LLMAdapter:
    def __init__(self) -> None:
        self.provider = settings.ai_provider

    # --- public surface ---------------------------------------------------- #
    def complete_json(self, *, system: str, user: str, model: str, max_tokens: int = 1024) -> dict:
        """Run a single completion expected to return a JSON object."""
        raw = self._complete(system=system, user=user, model=model, max_tokens=max_tokens)
        return self._parse_json(raw)

    # --- providers --------------------------------------------------------- #
    def _complete(self, *, system: str, user: str, model: str, max_tokens: int) -> str:
        if self.provider == "anthropic":
            return self._anthropic(system, user, model, max_tokens)
        if self.provider == "openai":
            return self._openai(system, user, model, max_tokens)
        raise AIValidationError(f"unknown ai_provider {self.provider!r}")

    def _anthropic(self, system: str, user: str, model: str, max_tokens: int) -> str:
        try:
            import anthropic  # lazy
        except ImportError as exc:  # pragma: no cover
            raise AIValidationError("anthropic SDK not installed") from exc
        if not settings.anthropic_api_key:
            raise AIValidationError("FREIGHT_ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    def _openai(self, system: str, user: str, model: str, max_tokens: int) -> str:
        try:
            from openai import OpenAI  # lazy
        except ImportError as exc:  # pragma: no cover
            raise AIValidationError("openai SDK not installed") from exc
        if not settings.openai_api_key:
            raise AIValidationError("FREIGHT_OPENAI_API_KEY not set")
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "{}"

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        # tolerate ```json fences
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{"): raw.rfind("}") + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIValidationError(f"LLM returned non-JSON: {raw[:200]!r}") from exc


llm = LLMAdapter()
