#!/usr/bin/env python3
"""Parse issue creation commands from PR comments."""

import sys
import re

def parse_issue_command(comment):
    """Parse issue creation command from a comment.

    Supports:
    - "create issue for 1, 2, 3"
    - "issue 1, 2"
    - "create issue for 1 2 3"
    - "issue 1"

    Args:
        comment: The comment text to parse

    Returns:
        Comma-separated string of item numbers, or empty string if no command found
    """
    comment = comment.strip().lower()

    pattern = r"(?:create\s+issue\s+for\s+|issue\s+)([0-9,\s]+)"
    match = re.search(pattern, comment)

    if match:
        nums = match.group(1)
        numbers = [
            n.strip()
            for n in re.split(r"[,\s]+", nums)
            if n.strip() and n.strip().isdigit()
        ]
        if numbers:
            return ",".join(numbers)

    return ""

def main():
    comment = sys.stdin.read().strip()
    result = parse_issue_command(comment)
    print(result)

if __name__ == "__main__":
    main()
