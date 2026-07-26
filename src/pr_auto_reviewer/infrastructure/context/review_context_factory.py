"""ReviewContextFactory — implements ReviewContextFactoryPort."""

from __future__ import annotations

import logging
from pathlib import Path
from pr_auto_reviewer.infrastructure.git_platform.multi_platform._parse_platform_prefix import (
    split_repository_prefix,
)


from dataclasses import replace

from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
)
from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)

class ReviewContextFactory(ReviewContextFactoryPort):
    """Composes ``RepositoryContextPort`` + ``ComposeReviewPromptPort``
    behind a single outbound port.

    Eliminates the data-clump anti-pattern in ``ReviewPullRequestService``.
    """

    def __init__(
        self,
        repository_context: RepositoryContextPort,
        compose_review_prompt: ComposeReviewPromptPort,
        local_clone_base_dir: str = "",
    ) -> None:
        self._repository_context = repository_context
        self._compose_review_prompt = compose_review_prompt
        self._local_clone_base_dir = local_clone_base_dir

    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
        target_branch: str = "",
    ) -> ComposedPrompt:
        logger.info(
            "ReviewContextFactory.build(%s, diff=%d chars, pr_title='%s', has_description=%s, target_branch='%s')",
            pr_id, len(diff.diff_content), (pr_title or "")[:80],
            "yes" if pr_description else "no",
            target_branch or "main",
        )
        repo_context = self._repository_context.fetch(pr_id, target_branch=target_branch)
        repo_context = replace(
            repo_context,
            pr_title=pr_title,
            pr_description=pr_description,
        )

        file_paths = sorted(diff.file_contents.keys())
        language, serialized = self._repository_context.build_fragment_context(
            repo_context, file_paths, diff.commit_messages or None,
        )

        review_context = ReviewContext(
            language=language,
            file_paths=file_paths,
            diff=diff.diff_content,
            repository_context=serialized,
        )

        logger.info(
            "Built ReviewContext: language=%s, files=%d, diff_chars=%d, "
            "has_repo_context=%s",
            language,
            len(diff.file_contents),
            len(diff.diff_content),
            serialized is not None,
        )

        composed = self._compose_review_prompt.execute(review_context)
        if self._local_clone_base_dir:
            _, clean_repo = split_repository_prefix(pr_id.repository)
            dir_name = f"{clean_repo.replace('/', '_')}_{pr_id.number}"
            composed = replace(
                composed,
                repo_path=str(Path(self._local_clone_base_dir) / dir_name),
            )
        logger.info(
            "ReviewContextFactory return: prompt=%d chars tokens=%d fragments=%s repo_path=%s",
            len(composed.content), composed.total_tokens,
            composed.fragments_used,
            composed.repo_path or "(none)",
        )
        return composed
