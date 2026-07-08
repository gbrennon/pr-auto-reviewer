import os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

GIT_PLATFORM = SRC / "pr_auto_reviewer/infrastructure/git_platform"
FORGEJO = SRC / "pr_auto_reviewer/infrastructure/forgejo"
GITHUB = SRC / "pr_auto_reviewer/infrastructure/github"

FORGEJO_FILES = [
    "changeset_fetcher.py",
    "pr_lister_adapter.py",
    "repo_lister_adapter.py",
    "comment_publisher.py",
    "comment_reader.py",
    "issue_tracker.py",
    "repository_context.py",
    "review_reader.py",
]

RENAME_MAP = {
    "pr_lister_adapter.py": "pr_lister.py",
    "repo_lister_adapter.py": "repo_lister.py",
}

CLASS_RENAMES = {
    "GitPrListerAdapter": "ForgejoPrListerAdapter",
    "GitRepoListerAdapter": "ForgejoRepoListerAdapter",
    "GitChangesetFetcherAdapter": "ForgejoChangesetFetcherAdapter",
    "GitCommentPublisherAdapter": "ForgejoCommentPublisherAdapter",
    "GitCommentReaderAdapter": "ForgejoCommentReaderAdapter",
    "GitIssueTrackerAdapter": "ForgejoIssueTrackerAdapter",
    "GitRepositoryContextAdapter": "ForgejoRepositoryContextAdapter",
    "GitReviewReaderAdapter": "ForgejoReviewReaderAdapter",
}

for filename in FORGEJO_FILES:
    src_path = GIT_PLATFORM / filename
    dest_name = RENAME_MAP.get(filename, filename)
    dest_path = FORGEJO / dest_name
    if src_path.exists():
        content = src_path.read_text()
        for old_name, new_name in CLASS_RENAMES.items():
            content = content.replace(old_name, new_name)
        for old_mod, new_mod in RENAME_MAP.items():
            old_import = f"from .{old_mod[:-3]} import"
            new_import = f"from .{new_mod[:-3]} import"
            content = content.replace(old_import, new_import)
        dest_path.write_text(content)
        print(f"Copied: {src_path} → {dest_path}")

print("\nDone with forgejo copies.")
