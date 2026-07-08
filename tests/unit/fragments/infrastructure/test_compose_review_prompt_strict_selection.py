import pytest
from unittest.mock import Mock

from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext

class TestStrictSelection:
    def test_strict_selection_includes_explicit_and_content_matches(self):
        mock_repo = Mock()

        lang_frag = PromptFragment(
            id="lang1",
            content="# LangFrag\n{{ code }}",
            language="python",
            priority=50,
            category="errors",
        )

        universal_kw = PromptFragment(
            id="kw",
            content="# KW fragment",
            language=None,
            priority=40,
            category="helpers",
            metadata={"keywords": "specialkeyword"},
        )

        universal_no = PromptFragment(
            id="no",
            content="# Not relevant",
            language=None,
            priority=30,
            category="misc",
        )

        system_frag = PromptFragment(
            id="sys",
            content="# System fragment",
            language=None,
            priority=10,
            category="system",
        )

        mock_repo.find_by_language.return_value = [lang_frag]
        mock_repo.find_universal.return_value = [universal_kw, universal_no, system_frag]

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def foo():\n+    specialkeyword = True\n",
        )

        adapter = ComposeReviewPromptAdapter(repository=mock_repo, use_strict_selection=True)
        result = adapter.execute(context)

        assert "lang1" in result.fragments_used
        assert "kw" in result.fragments_used
        assert "sys" in result.fragments_used
        assert "no" not in result.fragments_used

    def test_strict_selection_fallback_returns_all_when_filtered_empty(self):
        mock_repo = Mock()

        mock_repo.find_by_language.return_value = []

        u1 = PromptFragment(id="u1", content="alpha", language=None, priority=10, category="misc")
        u2 = PromptFragment(id="u2", content="beta", language=None, priority=20, category="misc")
        mock_repo.find_universal.return_value = [u1, u2]

        context = ReviewContext(language="ruby", file_paths=["a.rb"], diff="+nothing")

        adapter = ComposeReviewPromptAdapter(repository=mock_repo, use_strict_selection=True)
        result = adapter.execute(context)

        assert result.fragments_used == ["u2", "u1"]
