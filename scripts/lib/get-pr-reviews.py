#!/usr/bin/env python3
"""Get and sort PR reviews, returning the most recent one."""

import sys
import json
import os


def get_latest_review_json(json_data):
    """Find the most recent review from API response.

    The API returns reviews in unspecified order. We need to sort by
    created_at to get the most recent one.

    Args:
        json_data: Parsed JSON from Forgejo API

    Returns:
        The most recent review dict with body, or None
    """
    if isinstance(json_data, list):
        reviews = json_data
    else:
        reviews = json_data.get("data", [])

    if not reviews:
        return None

    valid_reviews = [r for r in reviews if r.get("body")]
    if not valid_reviews:
        return None

    def get_created_at(review):
        created = review.get("created_at", "")
        if not created:
            return "1970-01-01T00:00:00Z"
        return created

    valid_reviews.sort(key=get_created_at, reverse=True)

    return valid_reviews[0]


def main():
    json_data = json.load(sys.stdin)
    review = get_latest_review_json(json_data)

    if review:
        body = review.get("body", "")
        verdict = review.get("state", "")
        review_id = review.get("id", "")
        created = review.get("created_at", "")

        print(f"{review_id}|{verdict}|{created}|{body}")
    else:
        print("")


if __name__ == "__main__":
    main()
