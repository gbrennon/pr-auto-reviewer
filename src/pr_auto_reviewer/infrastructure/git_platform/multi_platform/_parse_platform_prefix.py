from __future__ import annotations


def split_repository_prefix(full_repository: str) -> tuple[str, str]:
    if ":" in full_repository:
        platform, _, name = full_repository.partition(":")
        if platform == "codeberg":
            platform = "forgejo"
        return platform, name
    return "forgejo", full_repository
