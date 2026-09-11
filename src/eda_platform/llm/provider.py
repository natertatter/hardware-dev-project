"""LLM provider abstraction for operations narrative parsing (BYOK)."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Protocol

logger = logging.getLogger(__name__)


class NarrativeParser(Protocol):
    """Parse free-form operations narrative into discrete step descriptions."""

    def parse_narrative_to_steps(self, narrative: str) -> list[str]: ...


class DeterministicNarrativeParser:
    """Line/sentence split — no API key required."""

    def parse_narrative_to_steps(self, narrative: str) -> list[str]:
        raw_lines = narrative.replace(".", ".\n").splitlines()
        steps: list[str] = []
        for line in raw_lines:
            text = line.strip()
            if text:
                steps.append(text)
        return steps


class AnthropicNarrativeParser:
    """Use Anthropic to structure vibe input into ordered steps."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key
        self._model = model

    def parse_narrative_to_steps(self, narrative: str) -> list[str]:
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic package not installed — falling back to deterministic parser")
            return DeterministicNarrativeParser().parse_narrative_to_steps(narrative)

        client = anthropic.Anthropic(api_key=self._api_key)
        prompt = (
            "Parse the following hardware operations narrative into an ordered JSON array "
            'of step description strings. Return ONLY valid JSON like ["step one", "step two"].\n\n'
            f"Narrative:\n{narrative}"
        )
        try:
            message = client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text if message.content else "[]"
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if not match:
                raise ValueError("no JSON array in LLM response")
            steps = json.loads(match.group())
            if not isinstance(steps, list):
                raise ValueError("LLM response is not a list")
            return [str(s).strip() for s in steps if str(s).strip()]
        except Exception as exc:
            logger.warning("Anthropic narrative parse failed (%s) — using deterministic fallback", exc)
            return DeterministicNarrativeParser().parse_narrative_to_steps(narrative)


def get_narrative_parser() -> NarrativeParser:
    """Return Anthropic parser when ANTHROPIC_API_KEY is set, else deterministic."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        return AnthropicNarrativeParser(api_key=api_key, model=model)
    return DeterministicNarrativeParser()
