from enum import Enum

class GitProvider(str, Enum):
    FORGEJO = "forgejo"
    GITHUB = "github"
    GITLAB = "gitlab"
    LOCAL = "local"
    OTHER = "other"
    BOTH = "both"

    @staticmethod
    def parse(value: str | None) -> "GitProvider":
        if isinstance(value, GitProvider):
            return value
        v = (value or "").strip().lower()
        if v in ("codeberg", "forgejo"):
            return GitProvider.FORGEJO
        if v in ("github", "gh"):
            return GitProvider.GITHUB
        if v in ("gitlab",):
            return GitProvider.GITLAB
        if v in ("local", "localhost"):
            return GitProvider.LOCAL
        if v in ("both", "all"):
            return GitProvider.BOTH
        return GitProvider.OTHER
