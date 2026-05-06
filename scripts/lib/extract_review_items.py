#!/usr/bin/env python3
"""Extract review items (issues and suggestions) from a review body."""

import sys
import re
import os


def extract_review_items(review_body, debug=False):
    """Extract issues and suggestions from a review body.

    Args:
        review_body: The review text to parse
        debug: If True, output debug info to stderr

    Returns:
        List of strings in format: num|severity|type|location|text
    """
    if debug:
        print(f"[DEBUG] Input review body length: {len(review_body)}", file=sys.stderr)
        print(f"[DEBUG] First 500 chars: {review_body[:500]}", file=sys.stderr)

    issues = []
    suggestions = []

    lines = review_body.split("\n")
    in_issues = False
    in_suggestions = False
    next_num = 1

    for line in lines:
        line = line.strip()
        if line.lower() == "### issues" or line.lower() == "### issues\n":
            in_issues = True
            in_suggestions = False
            if debug:
                print("[DEBUG] Entered ### Issues section", file=sys.stderr)
            continue
        elif line.lower() == "### suggestions" or line.lower() == "### suggestions\n":
            in_suggestions = True
            in_issues = False
            if debug:
                print("[DEBUG] Entered ### Suggestions section", file=sys.stderr)
            continue
        elif line.lower().startswith("### "):
            in_issues = False
            in_suggestions = False
            continue

        if in_issues or in_suggestions:
            match = re.match(r"^\d+[\.\)]\s+(.*)", line)
            if match:
                num_match = re.match(r"^(\d+)", line)
                num = int(num_match.group(1)) if num_match else next_num
                text = match.group(1).strip()

                severity = ""
                issue_type = ""
                location = ""

                matches = re.findall(r"\[(\w+)\]", text)
                if len(matches) >= 1:
                    severity = matches[0]
                if len(matches) >= 2:
                    issue_type = matches[1]

                remaining = text
                for _ in matches:
                    remaining = re.sub(r"\[\w+\]\s*", "", remaining, count=1)
                remaining = remaining.strip()

                if remaining:
                    loc_match = re.match(r"^([^:]+:\d+)", remaining)
                    if loc_match:
                        location = loc_match.group(1)
                    else:
                        loc_match = re.match(r"^(\S+)", remaining)
                        if loc_match:
                            location = loc_match.group(1)

                item = f"{num}|{severity}|{issue_type}|{location}|{text}"
                if in_issues:
                    issues.append(item)
                    if debug:
                        print(f"[DEBUG] Found issue: {item[:80]}...", file=sys.stderr)
                else:
                    suggestions.append(item)
                    if debug:
                        print(
                            f"[DEBUG] Found suggestion: {item[:80]}...", file=sys.stderr
                        )
            elif line.startswith("- ") or line.startswith("* "):
                text = line.lstrip("-* ")
                if text:
                    if in_issues:
                        issues.append(f"{next_num}|| | |{text}")
                    else:
                        suggestions.append(f"{next_num}|| | |{text}")
                    next_num += 1

    if debug:
        print(
            f"[DEBUG] Extracted {len(issues)} issues and {len(suggestions)} suggestions",
            file=sys.stderr,
        )

    result = issues + suggestions
    return result


def main():
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    review_body = sys.stdin.read()
    items = extract_review_items(review_body, debug=debug)

    for item in items:
        print(item)


if __name__ == "__main__":
    main()
