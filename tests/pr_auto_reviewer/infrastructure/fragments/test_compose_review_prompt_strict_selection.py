"""Tests for strict fragment selection using stub repository."""


from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from tests.fakes import FakeFragmentRepository


class TestStrictSelection:
    def test_strict_selection_includes_explicit_and_content_matches(self):
        repo = FakeFragmentRepository(
            by_language=[
                PromptFragment(
                    id="lang1",
                    content="# LangFrag\n{{ code }}",
                    language="python",
                    priority=50,
                    category="errors",
                ),
            ],
            universal=[
                PromptFragment(
                    id="kw",
                    content="# KW fragment",
                    language=None,
                    priority=40,
                    category="helpers",
                    metadata={"keywords": "specialkeyword"},
                ),
                PromptFragment(
                    id="no",
                    content="# Not relevant",
                    language=None,
                    priority=30,
                    category="misc",
                ),
                PromptFragment(
                    id="sys",
                    content="# System fragment",
                    language=None,
                    priority=10,
                    category="system",
                ),
            ],
        )

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def foo():\n+    specialkeyword = True\n",
        )

        adapter = ComposeReviewPromptAdapter(repository=repo, use_strict_selection=True)
        result = adapter.execute(context)

        assert "lang1" in result.fragments_used
        assert "kw" in result.fragments_used
        assert "sys" in result.fragments_used
        assert "no" not in result.fragments_used

    def test_strict_selection_fallback_returns_all_when_filtered_empty(self):
        u1 = PromptFragment(id="u1", content="alpha", language=None, priority=10, category="misc")
        u2 = PromptFragment(id="u2", content="beta", language=None, priority=20, category="misc")

        repo = FakeFragmentRepository(by_language=[], universal=[u1, u2])

        context = ReviewContext(language="ruby", file_paths=["a.rb"], diff="+nothing")

        adapter = ComposeReviewPromptAdapter(repository=repo, use_strict_selection=True)
        result = adapter.execute(context)

        assert result.fragments_used == ["u2", "u1"]
