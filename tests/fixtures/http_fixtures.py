"""HTTP request/response fixtures for git platform adapter tests.

Provides reusable mock responses for success and failure scenarios.
"""

from __future__ import annotations

from typing import Any



def make_success_response(
    json_data: Any = None,
    text_data: str = None,
    status_code: int = 200,
) -> Any:
    """Create a mock successful HTTP response."""
    mock_resp = type(
        "MockResponse",
        (),
        {
            "status_code": status_code,
            "json": lambda self: json_data or {},
            "text": text_data or "",
            "raise_for_status": lambda self: None,
        },
    )()
    return mock_resp


def mock_pr_list_response() -> list[dict[str, Any]]:
    """Successful response for listing PRs."""
    return [
        {
            "number": 95,
            "title": "Add new feature",
            "state": "open",
            "draft": False,
            "head": {"sha": "abc123def456"},
            "base": {"sha": "def456abc123"},
        },
        {
            "number": 96,
            "title": "Fix bug in parser",
            "state": "open",
            "draft": False,
            "head": {"sha": "ghi789jkl012"},
            "base": {"sha": "def456abc123"},
        },
    ]


def mock_pr_reviews_response() -> list[dict[str, Any]]:
    """Successful response for listing PR reviews."""
    return [
        {
            "id": 1,
            "user": {"login": "reviewer1"},
            "state": "APPROVED",
            "body": "Looks good!",
            "commit_id": "abc123",
        }
    ]


def mock_repo_tree_response() -> dict[str, Any]:
    """Successful response for repository tree."""
    return {
        "tree": [
            {"path": "src/main.py", "type": "blob"},
            {"path": "README.md", "type": "blob"},
            {"path": "src/utils", "type": "tree"},
        ]
    }


def mock_diff_response() -> str:
    """Successful diff response (raw text)."""
    return """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    return True
"""


def mock_post_review_response() -> dict[str, Any]:
    """Successful response for posting a review."""
    return {
        "id": 123,
        "state": "APPROVED",
        "body": "## AI Code Review\n\nLooks good!",
        "user": {"login": "ai-reviewer"},
    }


def mock_post_issue_response() -> dict[str, Any]:
    """Successful response for creating an issue."""
    return {
        "id": 456,
        "number": 42,
        "title": "Issue from review",
        "body": "Issue description",
        "state": "open",
    }



class MockHTTPError(Exception):
    """Mock HTTP error with response attribute."""

    def __init__(self, status_code: int, message: str = "HTTP Error") -> None:
        self.response = type(
            "MockResponse",
            (),
            {
                "status_code": status_code,
                "text": message,
            },
        )()
        super().__init__(f"{status_code}: {message}")


def mock_401_unauthorized() -> None:
    """Simulate 401 Unauthorized error."""
    raise MockHTTPError(401, "Unauthorized")


def mock_403_forbidden() -> None:
    """Simulate 403 Forbidden error."""
    raise MockHTTPError(403, "Forbidden")


def mock_404_not_found() -> None:
    """Simulate 404 Not Found error."""
    raise MockHTTPError(404, "Not Found")


def mock_422_validation_error() -> None:
    """Simulate 422 Validation Error (bad payload)."""
    raise MockHTTPError(422, "Validation Failed")


def mock_500_server_error() -> None:
    """Simulate 500 Internal Server Error."""
    raise MockHTTPError(500, "Internal Server Error")



def create_mock_get(
    success_data: Any = None,
    success_text: str = None,
    should_raise: bool = False,
    raise_func: Any = None,
) -> Any:
    """Create a mock for requests.get with configurable behavior."""

    def mock_get(*args, **kwargs):
        if should_raise and raise_func:
            raise_func()
        resp = make_success_response(
            json_data=success_data,
            text_data=success_text,
        )
        return resp

    return mock_get


def create_mock_post(
    success_data: Any = None,
    should_raise: bool = False,
    raise_func: Any = None,
) -> Any:
    """Create a mock for requests.post with configurable behavior."""

    def mock_post(*args, **kwargs):
        if should_raise and raise_func:
            raise_func()
        resp = make_success_response(json_data=success_data)
        return resp

    return mock_post
