from enum import Enum



class GitProvider(str, Enum):
    CODEBERG = "codeberg"
    GITHUB = "github"
    GITLAB = "gitlab"
    FORGEJO = "forgejo"
    LOCAL = "local"
    OTHER = "other"
    BOTH = "both"

    @staticmethod
    def parse(value: str | None) -> "GitProvider":
        if isinstance(value, GitProvider):
            return value
        v = (value or "").strip().lower()
        if v in ("codeberg", "forgejo"):
            return GitProvider.CODEBERG
        if v in ("github", "gh"):
            return GitProvider.GITHUB
        if v in ("gitlab",):
            return GitProvider.GITLAB
        if v in ("local", "localhost"):
            return GitProvider.LOCAL
        if v in ("both", "all"):
            return GitProvider.BOTH
        return GitProvider.OTHER
