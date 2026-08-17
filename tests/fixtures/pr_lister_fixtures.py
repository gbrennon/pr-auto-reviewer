from __future__ import annotations


def pr_dict(number: int, title: str = "Test", draft: bool = False) -> dict:
    return {
        "number": number,
        "title": title,
        "body": f"Description for PR #{number}",
        "draft": draft,
        "head": {"sha": "a" * 40},
        "state": "open",
    }

def pr_dicts(count: int = 3) -> list[dict]:
    return [pr_dict(i + 1, f"PR #{i + 1}: Add feature") for i in range(count)]
