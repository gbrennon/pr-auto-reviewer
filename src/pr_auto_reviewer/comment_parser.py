"""Comment parser module for PR Auto Reviewer."""

from typing import List, Dict, Any
import re

class CommentParser:
    """Parses PR comments for review items."""

    def parse_comment(self, comment_text: str) -> List[Dict[str, str]]:
        """Parse a comment for review items.

        Args:
            comment_text: The comment text to parse

        Returns:
            List of review item dictionaries.
        """
        items = []
        lines = comment_text.split("\n")

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

    def extract_review_items(self, text: str) -> List[Dict[str, str]]:
        """Extract review items from text.

        Args:
            text: Text to extract from

        Returns:
            List of review item dictionaries.
        """
        return self.parse_comment(text)