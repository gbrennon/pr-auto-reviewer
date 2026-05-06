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
    try:
        json_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No input or invalid JSON — treat as no comments
        return
    except Exception as e:
        # Unexpected error — write to stderr so caller or logs can capture it
        print(f"ERROR parsing comments JSON: {e}", file=sys.stderr)
        return

    comments = parse_comments(json_data)

    for c in comments:
        print(c)


if __name__ == "__main__":
    main()
