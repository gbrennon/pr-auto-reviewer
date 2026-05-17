#!/usr/bin/env python3
"""Compare legacy PromptBuilder vs fragment-based prompt composition.

Generates prompts using both systems side-by-side and writes them to disk
so you can inspect the differences.

Usage:
    cd pr-auto-reviewer
    PYTHONPATH=src:. python scripts/compare_prompts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure we can import the project
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def build_legacy_prompt() -> str:
    """Build a prompt using the old monolithic PromptBuilder."""
    from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
        PullRequestDiff,
    )
    from pr_auto_reviewer.domain.value_objects.repository_context import (
        RepositoryContext,
    )
    from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder

    diff = PullRequestDiff(
        pr_id=None,
        head_sha=None,
        diff_content="""diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,12 @@
 def login(username: str, password: str) -> bool:
+    if not username or not password:
+        raise ValueError("Username and password required")
     try:
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
         return check_password(user, password)
     except:
         pass""",
        file_contents={
            "src/auth.py": "def login(username, password): ...",
            "src/utils.py": "def helper(): pass",
        },
    )

    context = RepositoryContext(
        architecture_hint="hexagonal",
        conventions="Use type hints everywhere",
        repository_structure="src/\n  auth.py\n  utils.py",
    )

    return PromptBuilder().build(diff, context)


def build_fragment_prompt() -> str | None:
    """Build a prompt using the new fragment-based system."""
    from pr_auto_reviewer.domain.fragments.entities.review_context import (
        ReviewContext,
    )
    from pr_auto_reviewer.infrastructure.fragments.repositories import (
        FileSystemFragmentRepository,
    )
    from pr_auto_reviewer.infrastructure.fragments.renderers import Jinja2Renderer
    from pr_auto_reviewer.application.services.compose_review_prompt_service import (
        ComposeReviewPromptService,
    )

    fragments_dir = Path("fragments")
    if not fragments_dir.is_dir():
        print("[FRAGMENT] No fragments/ directory found — skipping fragment build")
        return None

    repo = FileSystemFragmentRepository(base_path=fragments_dir)
    renderer = Jinja2Renderer()
    service = ComposeReviewPromptService(
        repository=repo, renderer=renderer, max_tokens=4000,
    )

    context = ReviewContext(
        language="python",
        file_paths=["src/auth.py", "src/utils.py"],
        diff="""+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )""",
    )

    composed = service.execute(context)
    print(
        f"[FRAGMENT] Composed: {composed.total_tokens} tokens, "
        f"fragments={composed.fragments_used}"
    )
    return composed.content


def main() -> None:
    output_dir = Path("comparison_output")
    output_dir.mkdir(exist_ok=True)

    # Legacy
    print("=" * 60)
    print("Building LEGACY prompt (PromptBuilder)...")
    print("=" * 60)
    legacy = build_legacy_prompt()
    legacy_file = output_dir / "prompt_LEGACY.md"
    legacy_file.write_text(legacy)
    print(f"Written: {legacy_file} ({len(legacy)} chars)")
    print()

    # Fragment
    print("=" * 60)
    print("Building FRAGMENT prompt (FragmentSelector + PromptComposer)...")
    print("=" * 60)
    fragment = build_fragment_prompt()
    if fragment:
        fragment_file = output_dir / "prompt_FRAGMENT.md"
        fragment_file.write_text(fragment)
        print(f"Written: {fragment_file} ({len(fragment)} chars)")
    print()

    # Summary
    print("=" * 60)
    print("COMPARISON")
    print("=" * 60)
    if legacy_file.exists():
        print(f"  LEGACY:    {len(legacy):>6} chars")
    if fragment and (output_dir / "prompt_FRAGMENT.md").exists():
        print(f"  FRAGMENT:  {len(fragment):>6} chars")
    print()
    print("Run: diff comparison_output/prompt_LEGACY.md comparison_output/prompt_FRAGMENT.md")


if __name__ == "__main__":
    main()
