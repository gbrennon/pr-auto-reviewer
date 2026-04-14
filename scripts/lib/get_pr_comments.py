#!/usr/bin/env python3
"""Parse PR comments from API response."""

import sys
import json


def parse_comments(json_data):
    """Parse comments from API response.

    Args:
        json_data: Parsed JSON from Forgejo API

    Returns:
        List of strings in format: id|created_at|body
    """
    if isinstance(json_data, list):
        comments = json_data
    else:
        comments = json_data.get("data", [])

    results = []
    for c in comments:
        body = c.get("body", "")
        comment_id = c.get("id", "")
        created = c.get("created_at", "")
        if body:
            results.append(f"{comment_id}|{created}|{body}")

    return results


def main():
    json_data = json.load(sys.stdin)
    comments = parse_comments(json_data)

    for c in comments:
        print(c)


if __name__ == "__main__":
    main()
