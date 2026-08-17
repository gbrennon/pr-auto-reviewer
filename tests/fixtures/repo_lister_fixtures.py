from __future__ import annotations


def user_dict(username: str = "testuser") -> dict:
    return {"login": username, "username": username}

def repo_dicts() -> list[dict]:
    return [
        {"full_name": "testuser/repo-a", "owner": {"login": "testuser"}, "pushed_at": "2024-01-01T00:00:00Z"},
        {"full_name": "testuser/repo-b", "owner": {"login": "testuser"}, "pushed_at": "2024-01-02T00:00:00Z"},
        {"full_name": "other/repo-c", "owner": {"login": "other"}, "pushed_at": "2024-01-03T00:00:00Z"},
    ]
