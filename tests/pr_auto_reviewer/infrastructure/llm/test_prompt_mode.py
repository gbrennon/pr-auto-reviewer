import pytest

from pr_auto_reviewer.infrastructure.llm.prompt_mode import PromptMode


class TestPromptMode:

    @pytest.mark.parametrize(
        "raw, expected",
        [
            pytest.param("fragments", PromptMode.FRAGMENTS, id="fragments_canonical"),
            pytest.param("fragment",  PromptMode.FRAGMENTS, id="fragments_singular"),
            pytest.param("frags",     PromptMode.FRAGMENTS, id="fragments_abbrev"),
            pytest.param("FRAGMENTS", PromptMode.FRAGMENTS, id="fragments_uppercase"),
            pytest.param("  frags  ", PromptMode.FRAGMENTS, id="fragments_whitespace"),
            pytest.param("monolithic", PromptMode.MONOLITHIC, id="monolithic_canonical"),
            pytest.param("anything",   PromptMode.MONOLITHIC, id="monolithic_unknown_value"),
            pytest.param("",           PromptMode.MONOLITHIC, id="monolithic_empty_string"),
            pytest.param("   ",        PromptMode.MONOLITHIC, id="monolithic_whitespace_only"),
        ],
    )
    def test_parse_returns_expected_mode(self, raw: str, expected: PromptMode) -> None:
        assert PromptMode.parse(raw) == expected

    @pytest.mark.parametrize(
        "raw, unexpected",
        [
            pytest.param("fragments", PromptMode.MONOLITHIC, id="fragments_is_not_monolithic"),
            pytest.param("",          PromptMode.FRAGMENTS,  id="empty_is_not_fragments"),
            pytest.param("anything",  PromptMode.FRAGMENTS,  id="unknown_is_not_fragments"),
        ],
    )
    def test_parse_does_not_return_wrong_mode(self, raw: str, unexpected: PromptMode) -> None:
        assert PromptMode.parse(raw) != unexpected
