#!/usr/bin/env python3
"""Parse PR comments from API response."""

import sys
import json

def parse_comments(json_data):
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
        return
    except Exception as e:
        print(f"ERROR parsing comments JSON: {e}", file=sys.stderr)
        return

    comments = parse_comments(json_data)

    for c in comments:
        print(c)

if __name__ == "__main__":
    main()
