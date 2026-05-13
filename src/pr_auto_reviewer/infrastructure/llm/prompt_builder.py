"""PromptBuilder — constructs the LLM prompt from a diff and repository context."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class PromptBuilder:
    """Build the prompt sent to the LLM from a diff + review context."""

    @staticmethod
    def build(diff: PullRequestDiff, context: RepositoryContext) -> str:
        parts: list[str] = [
            "You are a Senior Principal Software Engineer and Code Reviewer "
            "with deep expertise in software architecture, design patterns, "
            "SOLID principles, and engineering excellence. "
            "Your role is to provide constructive, actionable code reviews "
            "for pull requests.",
            "",
            "## REVIEW PRIORITY",
            "",
            "1. **Critical Issues** (must fix):",
            "   - Security vulnerabilities",
            "   - Memory leaks or resource leaks",
            "   - Race conditions",
            "   - Unhandled exceptions",
            "   - Null pointer dereferences",
            "",
            "2. **Architectural Issues** (should fix):",
            "   - SOLID violations",
            "   - Architectural boundary breaches",
            "   - God objects",
            "   - Tight coupling without abstraction",
            "",
            "3. **Code Quality** (consider fixing):",
            "   - Naming conventions",
            "   - Code duplication",
            "   - Missing documentation",
            "   - Inefficient algorithms",
            "",
            "4. **Suggestions** (optional):",
            "   - Code style preferences",
            "   - Minor optimizations",
            "   - Cosmetic improvements",
            "",
            "## RESPONSE FORMAT",
            "",
            "Output ONLY valid JSON (no markdown, no explanation):",
            "",
            "{",
            '  "issues": [',
            '    {"file": "path/to/file", "line": "123", '
            '"severity": "critical|high|medium|low", '
            '"type": "security|architecture|solid|test|quality", '
            '"description": "specific issue description"}',
            "  ],",
            '  "suggestions": [',
            '    {"file": "path/to/file", "line": "456", '
            '"description": "improvement suggestion"}',
            "  ],",
            '  "praise": [',
            '    {"file": "path/to/file", "description": "what was done well"}',
            "  ],",
            '  "summary": "2-3 sentence overall assessment of the PR"',
            "}",
            "",
            "## GUIDELINES",
            "",
            "- Be specific: cite file names, line numbers, and function names",
            "- Explain WHY something is an issue, not just WHAT is wrong",
            "- Provide actionable feedback: tell the author HOW to fix it",
            "- Be constructive: acknowledge good patterns alongside problems",
            "- Focus on what matters: don't nitpick style when "
            "architecture is wrong",
            "- Prioritize: critical issues first, then architectural, then quality",
            "- No emojis in any output",
            "- Reply in English only",
            "- **CRITICAL: NEVER suggest removing the modified code.** "
            "Your job is to review changes, not undo them. "
            "If you find issues with the modified code, suggest how to "
            "improve it — refactor, restructure, fix — but never propose "
            "reverting or deleting the change. "
            "The author intentionally made this modification; "
            "help them make it better, not discard it.",
            "- **CRITICAL: READ the full file contents and diff CAREFULLY "
            "before reporting issues.**  Do NOT generate formulaic or "
            "template feedback (e.g. 'missing shebang', 'add comments') "
            "without first verifying that the problem actually exists in "
            "the provided code.  If the code already has a shebang, "
            "comments, error handling, or other boilerplate, do NOT "
            "suggest adding them — doing so is a hallucination.",
            "",
            "---",
        ]

        if context.architecture_hint:
            parts.append(
                f"## Architecture / context\n"
                f"{context.architecture_hint}\n"
            )

        conventions = context.conventions or diff.conventions
        if conventions:
            parts.append(f"## Project conventions\n{conventions}\n")

        repo_structure = (
            context.repository_structure or diff.repository_structure
        )
        if repo_structure:
            parts.append(
                f"## Repository structure\n{repo_structure}\n"
            )

        # Include full file contents so the LLM can read clean code
        # (not just diff markers).  This drastically reduces hallucinations
        # about missing shebangs, comments, or other boilerplate.
        if diff.file_contents:
            parts.append("## Full file contents (the actual files, not diffs)")
            parts.append("")
            for file_path, content in sorted(diff.file_contents.items()):
                parts.append(f"### {file_path}")
                parts.append("```")
                parts.append(content)
                parts.append("```")
                parts.append("")

        parts.append("## Diff\n```diff")
        parts.append(diff.diff_content)
        parts.append("```")

        return "\n".join(parts)
