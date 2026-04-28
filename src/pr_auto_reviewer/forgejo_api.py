"""Forgejo API client module for PR Auto Reviewer."""

import json
import requests
from typing import Optional, List, Dict, Any, Tuple
from .config import Config

class ForgejoAPI:
    """Client for interacting with Forgejo/Codeberg API."""

    def __init__(self, config: Config) -> None:
        """Initialize the Forgejo API client.

        Args:
            config: Configuration object.
        """
        self.config = config
        self.api_base = f"{config.forgejo_host}/api/v1"

    def get_repos(self) -> List[str]:
        """Get list of repositories owned by the authenticated user.

        Returns:
            List of repository full names (owner/repo).
        """
        if not self.config.forgejo_token:
            return []

        try:
            user_response = requests.get(
                f"{self.api_base}/user",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            user_response.raise_for_status()

            user_data = user_response.json()
            username = user_data.get("login") or user_data.get("username")
            if not username:
                return []

            response = requests.get(
                f"{self.api_base}/user/repos?limit=50",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            def is_owned(repo: Dict[str, Any]) -> bool:
                full_name = repo.get("full_name", "")
                owner = repo.get("owner", {}) if isinstance(repo.get("owner", {}), dict) else {}
                repo_owner = owner.get("login") or owner.get("username") or ""
                return full_name.startswith(f"{username}/") or repo_owner == username

            if isinstance(data, list):
                return [repo["full_name"] for repo in data if "full_name" in repo and is_owned(repo)]
            if isinstance(data, dict):
                repos = data.get("data", [])
                return [repo["full_name"] for repo in repos if "full_name" in repo and is_owned(repo)]
            return []
        except (requests.RequestException, json.JSONDecodeError):
            return []

    def get_open_prs(self, repo: str) -> List[Dict[str, Any]]:
        """Get open PRs for a repository.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            List of PR dictionaries with number, sha, and title.
        """
        try:
            response = requests.get(
                f"{self.api_base}/repos/{repo}/pulls?state=open&limit=20",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            prs = data if isinstance(data, list) else data.get("data", [])

            result = []
            for pr in prs:
                if pr.get("draft", False):
                    continue
                num = pr.get("number")
                sha = pr.get("head", {}).get("sha")
                title = pr.get("title", "")
                if num and sha:
                    result.append({
                        "number": str(num),
                        "sha": sha,
                        "title": title
                    })
            return result
        except (requests.RequestException, json.JSONDecodeError):
            return []

    def get_diff(self, repo: str, pr_number: str) -> Optional[str]:
        """Get the diff for a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number

        Returns:
            Diff content or None if failed.
        """
        try:
            response = requests.get(
                f"{self.api_base}/repos/{repo}/pulls/{pr_number}.diff",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            return None

    def get_pr_comments(self, repo: str, pr_number: str) -> List[Dict[str, Any]]:
        """Get comments for a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number

        Returns:
            List of comment dictionaries.
        """
        try:
            response = requests.get(
                f"{self.api_base}/repos/{repo}/issues/{pr_number}/comments?limit=50",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            comments = data if isinstance(data, list) else data.get("data", [])

            result = []
            for comment in comments:
                body = comment.get("body")
                if body:
                    result.append({
                        "id": str(comment.get("id", "")),
                        "created_at": comment.get("created_at", ""),
                        "body": body
                    })
            return result
        except (requests.RequestException, json.JSONDecodeError):
            return []

    def get_pr_reviews(self, repo: str, pr_number: str) -> List[Dict[str, Any]]:
        """Get reviews for a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number

        Returns:
            List of review dictionaries.
        """
        try:
            response = requests.get(
                f"{self.api_base}/repos/{repo}/pulls/{pr_number}/reviews?limit=10",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            reviews = data if isinstance(data, list) else data.get("data", [])

            result = []
            for review in reviews:
                body = review.get("body")
                verdict = review.get("state")
                review_id = review.get("id")
                if body:
                    result.append({
                        "id": str(review_id),
                        "state": verdict,
                        "body": body
                    })
            return result
        except (requests.RequestException, json.JSONDecodeError):
            return []

    def post_review(self, repo: str, pr_number: str, event: str, body: str) -> Optional[Dict[str, Any]]:
        """Post a formal review to a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number
            event: Review event (APPROVED, REQUEST_CHANGES, COMMENT)
            body: Review body content

        Returns:
            Review response or None if failed.
        """
        if not self.config.forgejo_reviewer_token:
            return None

        try:
            response = requests.post(
                f"{self.api_base}/repos/{repo}/pulls/{pr_number}/reviews",
                headers={
                    "Authorization": f"token {self.config.forgejo_reviewer_token}",
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                json={"event": event, "body": body},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError):
            return None

    def request_reviewer(self, repo: str, pr_number: str, reviewer: str) -> bool:
        """Request a reviewer for a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number
            reviewer: Reviewer username

        Returns:
            True if successful, False otherwise.
        """
        try:
            response = requests.post(
                f"{self.api_base}/repos/{repo}/pulls/{pr_number}/requested_reviewers",
                headers={
                    "Authorization": f"token {self.config.forgejo_token}",
                    "Content-Type": "application/json"
                },
                json={"reviewers": [reviewer]},
                timeout=30
            )
            return response.status_code == 201
        except requests.RequestException:
            return False

    def post_comment(self, repo: str, pr_number: str, body: str) -> bool:
        """Post a comment to a PR.

        Args:
            repo: Repository in format 'owner/repo'
            pr_number: PR number
            body: Comment body

        Returns:
            True if successful, False otherwise.
        """
        try:
            response = requests.post(
                f"{self.api_base}/repos/{repo}/pulls/{pr_number}/comments",
                headers={
                    "Authorization": f"token {self.config.forgejo_token}",
                    "Content-Type": "application/json"
                },
                json={"body": body},
                timeout=30
            )
            return response.status_code == 201
        except requests.RequestException:
            return False

    def get_repo_tree(self, repo: str, ref: str = "main") -> Optional[str]:
        """Get the repository file tree structure.

        Args:
            repo: Repository in format 'owner/repo'
            ref: Git ref (branch, tag, SHA). Defaults to 'main'.

        Returns:
            Tree listing as string, or None if failed.
        """
        try:
            response = requests.get(
                f"{self.api_base}/repos/{repo}/git/trees/{ref}?recursive=true",
                headers={"Authorization": f"token {self.config.forgejo_token}"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            tree = data.get("tree", [])
            lines = []
            for entry in tree:
                path = entry.get("path", "")
                entry_type = "dir" if entry.get("type") == "tree" else "file"
                suffix = "/" if entry_type == "dir" else ""
                lines.append(f"{path}{suffix}")
            return "\n".join(lines)
        except (requests.RequestException, json.JSONDecodeError):
            return None

    def create_issue(self, repo: str, title: str, body: str) -> Optional[int]:
        """Create an issue in a repository.

        Args:
            repo: Repository in format 'owner/repo'
            title: Issue title
            body: Issue body

        Returns:
            Issue number or None if failed.
        """
        try:
            response = requests.post(
                f"{self.api_base}/repos/{repo}/issues",
                headers={
                    "Authorization": f"token {self.config.forgejo_token}",
                    "Content-Type": "application/json"
                },
                json={"title": title, "body": body},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("number")
        except (requests.RequestException, json.JSONDecodeError):
            return None
