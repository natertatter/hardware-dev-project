"""Tests for LLM narrative parser abstraction."""

from eda_platform.llm import DeterministicNarrativeParser, get_narrative_parser


class TestLLMProvider:
    def test_deterministic_parser_splits_lines(self):
        parser = DeterministicNarrativeParser()
        steps = parser.parse_narrative_to_steps("Enable power.\nPoll sensor.")
        assert steps == ["Enable power.", "Poll sensor."]

    def test_get_parser_without_api_key_is_deterministic(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        parser = get_narrative_parser()
        assert isinstance(parser, DeterministicNarrativeParser)
