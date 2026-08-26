from ._shared import *
from .prompt_budget import PromptBudget


class PromptBuilder:
    """Build the prompt sent to the LLM from a diff + review context.

    Parameters
    ----------
    template_dir:
        Directory containing Jinja2 templates. Defaults to ``templates/``.
    max_tokens:
        Soft cap on total prompt tokens. ``0`` = unlimited (legacy mode).
    max_file_chars:
        Maximum characters per file in the file-contents section.
    max_files:
        Maximum number of files to include in the file-contents section.
    max_structure_lines:
        Maximum lines in the repository-structure section.
    use_compact_template:
        Use ``review_prompt_compact.j2`` (~4 KB) instead of the full template.
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        max_tokens: int = 0,
        max_file_chars: int = 3000,
        max_files: int = 10,
        max_structure_lines: int = 100,
        use_compact_template: bool = False,
    ) -> None:
        self._max_tokens = max_tokens
        self._max_file_chars = max_file_chars
        self._max_files = max_files
        self._max_structure_lines = max_structure_lines
        self._use_compact_template = use_compact_template
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir or _TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )

    def build(self, diff: PullRequestDiff, context: RepositoryContext) -> str:
        """Build a prompt using token-budget-aware allocation.

        When ``self._max_tokens > 0``, sections are prioritised and
        trimmed to fit within the budget. In legacy mode (max_tokens=0),
        all sections are included as-is for backward compatibility.
        """
        template_name = (
            "review_prompt_compact.j2" if self._use_compact_template
            else "review_prompt.j2"
        )
        template = self._env.get_template(template_name)

        conventions = context.conventions or diff.conventions
        repo_structure = context.repository_structure or diff.repository_structure
        annotated_diff = _annotate_diff(diff.diff_content)

        if self._max_tokens <= 0:
            return template.render(
                architecture_hint=(
                    context.architecture_hint if context.architecture_hint else None
                ),
                conventions=conventions if conventions else None,
                repository_structure=repo_structure if repo_structure else None,
                file_contents=diff.file_contents if diff.file_contents else None,
                annotated_diff=annotated_diff,
                pr_title=context.pr_title if context.pr_title else None,
                pr_description=(
                    context.pr_description if context.pr_description else None
                ),
                commit_messages=(
                    diff.commit_messages if diff.commit_messages else None
                ),
                issue_category_values=IssueCategory.prompt_values(),
                issue_severity_values=ItemSeverity.prompt_values(),
            )

        budget = PromptBudget(max_tokens=self._max_tokens)

        budget.consume(context.pr_title or "")
        budget.consume(context.pr_description or "")
        for msg in (diff.commit_messages or []):
            budget.consume(msg)

        if budget.would_fit(annotated_diff):
            budget.consume(annotated_diff)
        else:
            allowed_diff_tokens = max(
                int(self._max_tokens * 0.6),
                self._max_tokens - budget._consumed - 500,
            )
            annotated_diff = _annotate_diff(
                _trim_diff(diff.diff_content, allowed_diff_tokens)
            )
            budget.consume(annotated_diff)

        file_contents = None
        if diff.file_contents and budget.remaining_tokens > 500:
            trimmed_fc = _trim_file_contents(
                diff.file_contents,
                diff.diff_content,
                max_files=self._max_files,
                max_chars_per_file=self._max_file_chars,
            )
            if trimmed_fc and budget.would_fit(str(trimmed_fc)):
                file_contents = trimmed_fc
                budget.consume(str(trimmed_fc))

        if conventions and budget.remaining_tokens > 200:
            budget.consume(conventions)

        if context.architecture_hint and budget.remaining_tokens > 100:
            budget.consume(context.architecture_hint)

        if repo_structure and budget.remaining_tokens > 200:
            trimmed_structure = _trim_repo_structure(
                repo_structure, self._max_structure_lines
            )
            if budget.would_fit(trimmed_structure):
                repo_structure = trimmed_structure
                budget.consume(trimmed_structure)
            else:
                repo_structure = None

        return template.render(
            architecture_hint=(
                context.architecture_hint if context.architecture_hint else None
            ),
            conventions=conventions if conventions else None,
            repository_structure=repo_structure if repo_structure else None,
            file_contents=file_contents,
            annotated_diff=annotated_diff,
            pr_title=context.pr_title if context.pr_title else None,
            pr_description=(
                context.pr_description if context.pr_description else None
            ),
            commit_messages=(
                diff.commit_messages if diff.commit_messages else None
            ),
            issue_category_values=IssueCategory.prompt_values(),
            issue_severity_values=ItemSeverity.prompt_values(),
        )

