"""Test issue creation from PR review."""

from typing import Optional

from .config import Config
from .forgejo_api import ForgejoAPI
from .review_item_extractor import ReviewItemExtractor
from .issue_creator import IssueCreator

class TestIssueCreation:
    """Test issue creation from PR review."""

    def __init__(
        self,
        config: Config,
        repo: str,
        pr_number: int,
    ) -> None:
        """Initialize the tester.

        Args:
            config: Configuration object
            repo: Repository in format owner/repo
            pr_number: PR number
        """
        self.config = config
        self.repo = repo
        self.pr_number = pr_number

        self.forgejo_api = ForgejoAPI(config)
        self.review_item_extractor = ReviewItemExtractor()
        self.issue_creator = IssueCreator(config)

    def run(self) -> None:
        """Run the test."""
        print(f"Testing issue creation for PR #{self.pr_number} in {self.repo}")

        review_body = self.forgejo_api.get_latest_review(self.repo, self.pr_number)

        if not review_body:
            print(f"No review found for PR #{self.pr_number}")
            return

        print(f"Review body ({len(review_body)} chars):")
        print("\n".join(f"  {line}" for line in review_body.split("\n")[:5]))
        print("Extracting review items...")

        review_items = self.review_item_extractor.extract(review_body)

        if not review_items:
            print("No actionable items found in review")
            return

        print(f"Found {len(review_items)} review items:")
        for item in review_items[:5]:
            print(f"  {item}")

        print("Testing issue creation...")

        # Test creating an issue from the first review item
        if review_items:
            item_data = review_items[0]

            parts = item_data.split("|")
            severity = parts[1] if len(parts) > 1 else ""
            item_type = parts[2] if len(parts) > 2 else ""
            location = parts[3] if len(parts) > 3 else ""
            item_text = parts[4] if len(parts) > 4 else item_data

            clean_title = item_text
            for tag in [severity, item_type]:
                if tag:
                    clean_title = clean_title.replace(f"[{tag}]", "").replace(f"[{tag}] ", "")
            clean_title = clean_title.replace(location, "").replace(": ", "").strip()
            clean_title = clean_title[:200]

            issue_title = f"[TEST] [PR #{self.pr_number}] {clean_title}"
            issue_body = f"""## Test Issue Creation (PR #{self.pr_number})

**Description:**
{item_text}

{location and f"- **File:** {location}"}
{item_type and f"- **Category:** {item_type}"}
{severity and f"- **Severity:** {severity}"}

---
*Test issue created from PR #{self.pr_number} via PR AI Reviewer*"""

            issue_num = self.issue_creator.create_issue(self.repo, issue_title, issue_body)

            if issue_num:
                print(f"Test issue created: #{issue_num}")
            else:
                print("Failed to create test issue")
        else:
            print("No review items to test")


def test_issue_creation() -> None:
    """CLI entry point for test-issue-creation command."""
    from .config import load_config
    config = load_config()
    tester = TestIssueCreation(config=config, repo="owner/repo", pr_number=1)
    tester.run()