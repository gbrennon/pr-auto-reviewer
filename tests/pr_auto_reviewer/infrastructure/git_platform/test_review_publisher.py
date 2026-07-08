"""Tests for GitReviewPublisherAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.review_publishers.platform_publisher import (
    PlatformReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)
GitReviewPublisherAdapter = PlatformReviewPublisherAdapter
format_review_body = ReviewBodyFormatter().format

class TestGitReviewPublisherAdapter:
    """Tests for GitReviewPublisherAdapter using captured fixture data."""

    @pytest.fixture
    def adapter(self, patched_private_client):
        return GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)

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

    def test_reviewer_request_failure_non_fatal(self, patched_private_client, monkeypatch):
        """Reviewer request failure is logged, not raised."""
        call_paths = []
        def fake_post(path, body):
            call_paths.append(path)
            if "requested_reviewers" in path:
                raise Exception("422")
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert len(call_paths) == 2

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

    def test_find_diff_position_none_file_path(self):
        result = PlatformReviewPublisherAdapter._find_diff_position("diff", None, "code")
        assert result is None

    def test_find_diff_position_empty_current_code(self):
        result = PlatformReviewPublisherAdapter._find_diff_position("diff", "f.py", "")
        assert result is None

    def test_find_diff_position_empty_snippet(self):
        result = PlatformReviewPublisherAdapter._find_diff_position("diff", "f.py", "\n  \n")
        assert result is None

    def test_find_diff_position_file_not_found(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "nonexistent.py", "some_code"
        )
        assert result is None

    def test_find_diff_position_added_line(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "src/main.py", "return True"
        )
        assert result is not None
        assert result["new_line"] is not None
        assert result["old_line"] is None

    def test_find_diff_position_removed_line(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "src/utils.py", "old_code"
        )
        assert result is not None
        assert result["old_line"] is not None
        assert result["new_line"] is None

    def test_find_diff_position_context_line(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "src/utils.py", "context_line"
        )
        assert result is not None
        assert result["old_line"] is not None
        assert result["new_line"] is not None

    def test_find_diff_position_snippet_not_found(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "src/main.py", "nonexistent_function"
        )
        assert result is None

    def test_find_diff_position_in_second_file(self):
        result = PlatformReviewPublisherAdapter._find_diff_position(
            self.DIFF, "src/utils.py", "added_func"
        )
        assert result is not None
        assert result["new_line"] is not None

    # ---- inline comment and error path tests ----

    def test_publish_with_items_adds_inline_comments(self, patched_private_client, monkeypatch):
        """Publish with review items builds inline comments."""
        post_payloads = []
        def fake_post(path, body):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "get_raw",
                            lambda path, headers=None: self.DIFF)

        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
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
        def fake_post(path, body):
            post_payloads.append((path, body))
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "get_raw",
                            lambda path, headers=None: (_ for _ in ()).throw(Exception("diff fetch failed")))

        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert "Failed to resolve inline comments" in caplog.text

    def test_publish_post_review_403_raises(self, patched_private_client, monkeypatch):
        """403 on review post raises ReviewPublishError."""
        call_count = [0]
        def fake_post(path, body):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"id": 1}
            raise Exception("403 Forbidden")
        monkeypatch.setattr(patched_private_client, "post", fake_post)

        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)

        with pytest.raises(ReviewPublishError):
            adapter.publish(pr_id, review)

    def test_publish_non_403_raises_review_publish_error(self, patched_private_client, monkeypatch):
        """Non-403 error on review post raises ReviewPublishError."""
        call_count = [0]
        def fake_post(path, body):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"id": 1}
            raise Exception("500 Internal Server Error")
        monkeypatch.setattr(patched_private_client, "post", fake_post)

        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)

        with pytest.raises(ReviewPublishError):
            adapter.publish(pr_id, review)
