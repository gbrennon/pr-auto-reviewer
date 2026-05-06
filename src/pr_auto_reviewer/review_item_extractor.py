"""Review item extractor module for PR Auto Reviewer."""

from typing import List, Dict, Any
import re

class ReviewItemExtractor:
    """Extracts review items from PR reviews and comments."""

    def extract_from_review(self, review_text: str) -> List[Dict[str, str]]:
        """Extract review items from a review text.

        Args:
            review_text: The review text to extract from

        Returns:
            List of review item dictionaries.
        """
        items = []
        lines = review_text.split("\n")

        current_item = None
        for line in lines:
            if line.startswith("## "):
                # New section
                if current_item:
                    items.append(current_item)
                current_item = None
            elif line.startswith("- [ ] ") or line.startswith("- [x] "):
                # Review item
                if not current_item:
                    current_item = {"title": "", "body": ""}
                current_item["title"] = line[4:].strip()
            elif current_item and line.strip():
                # Part of current item body
                current_item["body"] += line + "\n"

        if current_item:
            items.append(current_item)

        return items

    def extract_from_comment(self, comment_text: str) -> List[Dict[str, str]]:
        """Extract review items from a comment text.

        Args:
            comment_text: The comment text to extract from

        Returns:
            List of review item dictionaries.
        """
        return self.extract_from_review(comment_text)