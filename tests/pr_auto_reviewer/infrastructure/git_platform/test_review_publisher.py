"""Tests for GitReviewPublisherAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.github.github_review_publisher import (
    GithubReviewPublisher,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)
from pr_auto_reviewer.infrastructure.review_publishers.review_publishing_service import (
    ReviewPublishingService,
)
GitReviewPublisherAdapter = GithubReviewPublisher
format_review_body = ReviewBodyFormatter().format

class TestGitReviewPublisherAdapter:
    """Tests for GitReviewPublisherAdapter using captured fixture data."""

    # ---- _find_diff_position tests ----

    DIFF = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    return True
diff --git a/src/utils.py b/src/utils.py
index def456..ghi789 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,6 +10,7 @@ def helper():
     pass

 def util():
-    old_code
+    new_code
     context_line
@@ -20,4 +21,5 @@ def another():
     return 0
+
+def added_func():
+    return 1"""

    @pytest.fixture
    def adapter(self, patched_private_client):
        return GitReviewPublisherAdapter(patched_private_client, patched_private_client)

    def test_publish(self, adapter):
        """Publish sends a formal PR review."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    @pytest.mark.parametrize("verdict", [
        ReviewVerdict.APPROVED,
        ReviewVerdict.CHANGES_REQUESTED,
        ReviewVerdict.COMMENTED,
    ])
    def test_publish_maps_verdict(self, adapter, verdict):
        """Publish maps ReviewVerdict to correct event."""
        review = CodeReview(verdict=verdict, summary="Test", items=[], model_used="t")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_summary(self, adapter):
        """_format_body handles None summary."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary=None, items=[], model_used=None)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_model(self, adapter):
        """_format_body handles None model_used."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used=None)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_file_path(self, adapter):
        """_format_body handles None file_path."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="s",
            items=[ReviewItem(number=1, category="c", severity=ItemSeverity.INFO,
                              description="d", file_path=None)],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_empty_items(self, adapter):
        """_format_body handles empty items list."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_publish_succeeds_with_only_review_post(self, patched_private_client, monkeypatch):
        """publish() posts review — no longer requests reviewer (Bug 4 fix)."""
        call_paths = []
        def fake_post(path, body, *, repo=None):
            call_paths.append(path)
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        adapter = GitReviewPublisherAdapter(patched_private_client, patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert len(call_paths) == 1

    def test_find_diff_position_none_file_path(self, adapter):
        result = adapter._publishing.find_diff_position("diff", None, "code")
        assert result is None

    def test_find_diff_position_empty_current_code(self, adapter):
        result = adapter._publishing.find_diff_position("diff", "f.py", "")
        assert result is None

    def test_find_diff_position_empty_snippet(self, adapter):
        result = adapter._publishing.find_diff_position("diff", "f.py", "\n  \n")
        assert result is None

    def test_find_diff_position_file_not_found(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "nonexistent.py", "some_code"
        )
        assert result is None

    def test_find_diff_position_added_line(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/main.py", "return True"
        )
        assert result is not None
        assert result["new_line"] is not None
        assert result["old_line"] is None

    def test_find_diff_position_removed_line(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py", "old_code"
        )
        assert result is not None
        assert result["old_line"] is not None
        assert result["new_line"] is None

    def test_find_diff_position_context_line(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py", "context_line"
        )
        assert result is not None
        assert result["old_line"] is not None
        assert result["new_line"] is not None

    def test_find_diff_position_snippet_not_found(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/main.py", "nonexistent_function"
        )
        assert result is None

    def test_find_diff_position_in_second_file(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py", "added_func"
        )
        assert result is not None
        assert result["new_line"] is not None
    def test_find_diff_position_multi_line_full_match(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py",
            "    return 0\n\ndef added_func():\n    return 1"
        )
        assert result is not None
        assert result["new_line"] is not None

    def test_find_diff_position_multi_line_first_only_matches(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py",
            "    return 0\nnonexistent_hallucinated_code"
        )
        assert result is None

    def test_find_diff_position_multi_line_non_consecutive(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py",
            "def util():\n    return 1"
        )
        assert result is None

    def test_find_diff_position_multi_line_added_lines(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/utils.py",
            "def added_func():\n    return 1"
        )
        assert result is not None

    def test_find_diff_position_multi_line_across_file_boundary(self, adapter):
        result = adapter._publishing.find_diff_position(
            self.DIFF, "src/main.py",
            "    return True\ndef added_func():\n    pass"
        )
        assert result is None
    # ---- inline comment and error path tests ----

    def test_publish_with_items_adds_inline_comments(self, patched_private_client, monkeypatch):
        """Publish with review items builds inline comments."""
        post_payloads = []
        def fake_post(path, body, *, repo=None):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "get_raw",
                            lambda path, headers=None, *, repo=None: self.DIFF)

        adapter = GitReviewPublisherAdapter(patched_private_client, patched_private_client)
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MAJOR, category="bug",
                              description="Use return True", file_path="src/main.py",
                              current_code="return True", suggested_fix="x")],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

        review_call = post_payloads[-1]
        assert "reviews" in review_call[0]
        assert "comments" in review_call[1]

    def test_publish_inline_comment_error_non_fatal(self, patched_private_client, monkeypatch, caplog):
        """Inline comment resolution failure is logged, review still posted."""
        post_payloads = []
        def fake_post(path, body, *, repo=None):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "get_raw",
                            lambda path, headers=None, *, repo=None: (_ for _ in ()).throw(Exception("diff fetch failed")))

        adapter = GitReviewPublisherAdapter(patched_private_client, patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert "Failed to resolve inline comments" in caplog.text

    def test_publish_post_review_403_raises(self, patched_private_client, monkeypatch):
        """403 on review post raises ReviewPublishError."""
        def fake_post(path, body, *, repo=None):
            raise Exception("403 Forbidden")
        monkeypatch.setattr(patched_private_client, "post", fake_post)

        adapter = GitReviewPublisherAdapter(patched_private_client, patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)

        with pytest.raises(ReviewPublishError):
            adapter.publish(pr_id, review)

    def test_publish_non_403_raises_review_publish_error(self, patched_private_client, monkeypatch):
        """Non-403 error on review post raises ReviewPublishError."""
        def fake_post(path, body, *, repo=None):
            raise Exception("500 Internal Server Error")
        monkeypatch.setattr(patched_private_client, "post", fake_post)

        adapter = GitReviewPublisherAdapter(patched_private_client, patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)

        with pytest.raises(ReviewPublishError):
            adapter.publish(pr_id, review)

    # ===== new tests =====

    def test_count_existing_items_returns_zero_on_api_failure(
        self, patched_private_client, monkeypatch,
    ):
        monkeypatch.setattr(patched_private_client, "get",
                            lambda path, **kw: (_ for _ in ()).throw(Exception("boom")))
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        result = adapter._publishing.count_existing_items(
            PullRequestId(repository="o/r", number=1),
        )
        assert result == 0

    def test_count_existing_items_counts_items_not_reviews(
        self, patched_private_client, monkeypatch,
    ):
        reviews = [
            {"id": 1, "body": "0. [maintainability] [MINOR]\n\nFirst issue\n1. [bug] [MAJOR] src/x.py:1\n\nSecond issue"},
            {"id": 2, "body": "2. [docs] [MINOR] README.md:5\n\nThird issue\n3. [style] [INFO]\n\nFourth issue"},
        ]
        monkeypatch.setattr(
            patched_private_client, "get", lambda path, **kw: reviews,
        )
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        result = adapter._publishing.count_existing_items(
            PullRequestId(repository="o/r", number=1),
        )
        assert result == 4


    def test_publish_comment_logs_debug(
        self, patched_private_client, monkeypatch, caplog,
    ):
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        caplog.set_level("DEBUG")
        adapter._publishing.publish_comment(
            PullRequestId(repository="o/r", number=1), "test body",
        )
        assert "Comment posted" in caplog.text

    def test_publish_comment_handles_post_failure(
        self, patched_private_client, monkeypatch, caplog,
    ):
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        def raise_err(*_a, **_kw):
            raise Exception("post failed")
        monkeypatch.setattr(patched_private_client, "post", raise_err)
        adapter._publishing.publish_comment(
            PullRequestId(repository="o/r", number=1), "test body",
        )
        assert "Failed to post comment" in caplog.text

    def test_build_inline_comments_github_mode(
        self, patched_private_client,
    ):
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "index abc1234..def5678 100644\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,3 +1,4 @@\n"
            " unchanged\n"
            "+return True\n"
        )
        items = [
            ReviewItem(
                number=1, severity=ItemSeverity.MAJOR, category="bug",
                description="Blocking", file_path="src/main.py",
                current_code="return True",
            ),
        ]
        result = adapter._publishing.build_inline_comments(
            diff, items, [], platform="github",
        )
        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"
        assert result[0]["body"] == "Blocking"
        assert "position" in result[0]

    def test_build_inline_comments_with_suggestions_forgejo(
        self, patched_private_client,
    ):
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "index abc1234..def5678 100644\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,3 +1,4 @@\n"
            " unchanged\n"
            "+return True\n"
        )
        suggestions = [
            ReviewSuggestion(file="src/main.py", current_code="return True",
                             description="Use a constant instead"),
        ]
        result = adapter._publishing.build_inline_comments(
            diff, [], suggestions, platform="forgejo",
        )
        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"
        assert result[0]["body"] == "Use a constant instead"
        assert result[0]["old_position"] == 0
        assert result[0]["new_position"] == 2
    def test_comment_verdict_filters_blocking_items(
        self, patched_private_client, monkeypatch,
    ):
        post_payloads = []
        def fake_post(path, body, *, repo=None):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        review = CodeReview(
            verdict=ReviewVerdict.COMMENTED, summary="s",
            items=[
                ReviewItem(number=1, severity=ItemSeverity.MAJOR, category="bug",
                           description="Blocking", file_path="f.py",
                           current_code="x"),
                ReviewItem(number=2, severity=ItemSeverity.MINOR, category="style",
                           description="Nit", file_path="f.py",
                           current_code="x"),
            ],
            praise=[ReviewPraise(description="nice")],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        comment_calls = [p for p in post_payloads if "/comments" in p[0]]
        assert len(comment_calls) == 1
        body = comment_calls[0][1]["body"]
        assert "Nit" in body
        assert "Blocking" not in body

    def test_formal_review_excludes_non_blocking_from_body(
        self, patched_private_client, monkeypatch,
    ):
        post_payloads = []
        def fake_post(path, body, *, repo=None):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[
                ReviewItem(number=1, severity=ItemSeverity.MAJOR, category="bug",
                           description="Blocking", file_path="f.py",
                           current_code="x"),
                ReviewItem(number=2, severity=ItemSeverity.MINOR, category="style",
                           description="Nit", file_path="f.py",
                           current_code="x"),
            ],
            praise=[ReviewPraise(description="nice")],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        review_calls = [p for p in post_payloads if "/reviews" in p[0]]
        comment_calls = [p for p in post_payloads if "/comments" in p[0]]
        assert len(review_calls) == 1
        assert len(comment_calls) == 0
        review_body = review_calls[0][1]["body"]
        assert "Blocking" in review_body
        assert "Nit" in review_body
    def test_build_inline_comments_skips_suggestion_without_file(
        self, patched_private_client, monkeypatch,
    ):
        """Suggestions missing file or code are skipped."""
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1,2 @@\n"
            "+x\n"
        )
        suggestions = [
            ReviewSuggestion(file="", current_code="x", description="no file"),
            ReviewSuggestion(file="f.py", current_code="", description="no code"),
        ]
        result = adapter._publishing.build_inline_comments(
            diff, [], suggestions, platform="github",
        )
        assert result == []

    def test_build_inline_comments_suggestions_github_mode(
        self, patched_private_client,
    ):
        """Suggestions build GitHub-style inline comments."""
        adapter = GitReviewPublisherAdapter(
            patched_private_client, patched_private_client,
        )
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "@@ -1,3 +1,4 @@\n"
            " unchanged\n"
            "+return True\n"
        )
        suggestions = [
            ReviewSuggestion(file="src/main.py", current_code="return True",
                             description="Use a constant"),
        ]
        result = adapter._publishing.build_inline_comments(
            diff, [], suggestions, platform="github",
        )
        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"
        assert result[0]["body"] == "Use a constant"
        assert "position" in result[0]
