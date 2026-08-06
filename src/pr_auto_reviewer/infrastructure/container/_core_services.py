"""Core service wiring — LLM, fragments, persistence, and non-platform services."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.notifier.linux_notifier import (
    LinuxNotifier,
)
from pr_auto_reviewer.infrastructure.fragments.file_system_fragment_repository import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.fragments.jinja2_renderer import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
        CommandBusPort,
    )
    from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
        ComposeReviewPromptPort,
    )
    from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
        FragmentRepositoryPort,
    )
    from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
        LlmReviewPort,
    )
    from pr_auto_reviewer.application.ports.outbound.notifier_port import (
        NotifierPort,
    )
    from pr_auto_reviewer.application.ports.outbound.prompt_renderer_port import (
        PromptRendererPort,
    )
    from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
        PullRequestRepository,
    )
    from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
        RepositoryContextPort,
    )
    from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
        ReviewContextFactoryPort,
    )


@dataclass
class CoreServices:
    """All core (non-platform-specific) services."""

    pr_repository: PullRequestRepository
    llm_review: LlmReviewPort
    command_bus: CommandBusPort
    notifier: NotifierPort
    fragment_repository: FragmentRepositoryPort
    fragment_renderer: PromptRendererPort
    fragment_max_tokens: int | None
    review_context_factory: ReviewContextFactoryPort




def wire_core_services(
    config: Config,
    repository_context: RepositoryContextPort,
    *,
    _config_dir: Path | None = None,
) -> CoreServices:
    """Build and wire all core (non-platform) services."""

    if _config_dir is not None:
        config_dir = str(_config_dir)
    else:
        config_dir = os.path.expanduser("~/.config/pr-auto-reviewer")
    os.makedirs(config_dir, exist_ok=True)
    pr_repository = JsonFilePullRequestRepository(
        os.path.join(config_dir, "state.json")
    )
    llm_review: LlmReviewPort = OllamaExploratoryChatAdapter(
        model=config.llm_model or "code-review:latest",
        host=config.llm_host,
        ollama_timeout=config.ollama_timeout,
        max_retries=config.llm_max_retries,
    )
    command_bus = InMemoryCommandBus()
    notifier = LinuxNotifier(run_command=subprocess.run)

    fragments_dir = config.fragments_dir or None
    fragment_repository = (
        FileSystemFragmentRepository(Path(fragments_dir))
        if fragments_dir
        else FileSystemFragmentRepository()
    )
    fragment_renderer = Jinja2Renderer()
    fragment_max_tokens: int | None = getattr(
        config, "fragment_max_tokens", None
    )

    prompt_adapter: ComposeReviewPromptPort = ComposeReviewPromptAdapter(
        repository=fragment_repository,
        renderer=fragment_renderer,
        max_tokens=fragment_max_tokens,
        max_total_chars=config.max_prompt_tokens * 4
        if config.max_prompt_tokens > 0
        else 60_000,
        use_strict_selection=getattr(
            config, "use_strict_fragment_selection", False
        ),
    )

    review_context_factory = ReviewContextFactory(
        repository_context=repository_context,
        compose_review_prompt=prompt_adapter,
        local_clone_base_dir=config.local_clone_base_dir,
    )

    return CoreServices(
        pr_repository=pr_repository,
        llm_review=llm_review,
        command_bus=command_bus,
        notifier=notifier,
        fragment_repository=fragment_repository,
        fragment_renderer=fragment_renderer,
        fragment_max_tokens=fragment_max_tokens,
        review_context_factory=review_context_factory,
    )
