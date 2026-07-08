from __future__ import annotations

def user_dict(username: str = "testuser") -> dict:
    return {"login": username, "username": username}

def repo_dicts() -> list[dict]:
    return [
        {"full_name": "testuser/repo-a", "owner": {"login": "testuser"}},
        {"full_name": "testuser/repo-b", "owner": {"login": "testuser"}},
        {"full_name": "other/repo-c", "owner": {"login": "other"}},
    ]
