#!/usr/bin/env python3
"""Build review comment body from Ollama JSON response."""

import sys
import json
import os
import re


def extract_json(text):
    """Try to extract valid JSON from text that may contain markdown or other content."""
    if not text:
        return None

    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except:
        pass

    # Try to find JSON in markdown code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass

    # Try to find any {...} block
    match = re.search(r'\{[^{}]*"[^"]+":\s*[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass

    return None


def determine_verdict(review):
    """Determine review verdict based on issues.

    Returns:
        'approved' if no critical/high issues
        'changes_requested' if there are critical/high issues
    """
    issues = review.get("issues", [])

    for issue in issues:
        severity = issue.get("severity", "").lower()
        if severity in ("critical", "high"):
            return "changes_requested"

    return "approved"


def main():
    review_json = os.environ.get("REVIEW_JSON", "")

    # Try to extract and parse JSON from the response
    review = extract_json(review_json)

    if review is None:
        # If no valid JSON found, treat the whole thing as summary
        review = {"summary": review_json, "issues": [], "suggestions": [], "praise": []}

    issues = review.get("issues", [])
    suggestions = review.get("suggestions", [])
    praise = review.get("praise", [])
    summary = review.get("summary", "")
    model = os.environ.get("OLLAMA_MODEL", "ollama")

    # Determine verdict
    verdict = determine_verdict(review)

    # Determine emoji and text for verdict
    if verdict == "approved":
        verdict_emoji = "✅"
        verdict_text = "Approved"
    else:
        verdict_emoji = "❌"
        verdict_text = "Changes Requested"

    body = f"## AI Code Review {verdict_emoji}\n\n"
    body += f"**Verdict:** {verdict_text}\n\n"

    if issues:
        body += "### Issues\n"
        for i in issues:
            sev = i.get("severity", "medium").upper()
            typ = i.get("type", "")
            file = i.get("file", "")
            line = i.get("line", "?")
            desc = i.get("description", "")

            location = f"{file}:{line}" if file and line else (file or line or "?")
            type_tag = f" [{typ}]" if typ else ""
            body += f"- [{sev}]{type_tag} {location}: {desc}\n"
        body += "\n"

    if suggestions:
        body += "### Suggestions\n"
        for s in suggestions:
            file = s.get("file", "")
            line = s.get("line", "?")
            desc = s.get("description", "")

            location = f"{file}:{line}" if file and line else (file or line or "?")
            body += f"- {location}: {desc}\n"
        body += "\n"

    if praise:
        body += "### Praise\n"
        for p in praise:
            file = p.get("file", "")
            desc = p.get("description", "")
            body += f"- {file}: {desc}\n" if file else f"- {desc}\n"
        body += "\n"

    if summary:
        body += f"**Summary:** {summary}\n"

    body += f"\n---\n*Review by {model} via local Forgejo*"

    # Print verdict to stdout for capture by caller
    print(verdict)
    print(body)


if __name__ == "__main__":
    main()
