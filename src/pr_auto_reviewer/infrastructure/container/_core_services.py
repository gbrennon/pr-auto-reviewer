"""Core service wiring — LLM, fragments, persistence, and non-platform services."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.messages.events.conversation_completed_event import (
    ConversationCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.findings_aggregated_event import (
    FindingsAggregatedEvent,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.application.services.event_logging_handler import (
    EventLoggingHandler,
)
from pr_auto_reviewer.application.services.finding_aggregator import (
    FindingAggregator,
)
from pr_auto_reviewer.application.services.finding_verifier import (
    FindingVerifier,
)
from pr_auto_reviewer.application.services.multi_phase_review_orchestrator import (
    MultiPhaseReviewOrchestrator,
)
from pr_auto_reviewer.application.services.turn_parser import TurnParser
from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase
from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.infrastructure.fragments.file_system_fragment_repository import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.fragments.jinja2_renderer import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_agent_adapter import (
    OllamaAgentAdapter,
)
from pr_auto_reviewer.infrastructure.conversation_logger import (
    MarkdownConversationLogger,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)
from pr_auto_reviewer.infrastructure.notifier.linux_notifier import (
    LinuxNotifier,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from pr_auto_reviewer.infrastructure.review_publishers._shared import (
    ReasonBuilder,
)

logger = logging.getLogger(__name__)

_PHASE_PROMPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "fragments"
    / "content"
    / "universal"
)

_PHASES: list[tuple[str, str]] = [
    ("bug-hunt-diff", "Bug Hunt — Diff"),
    ("bug-hunt-branch", "Bug Hunt — Branch"),
    ("architecture-review", "Architecture Review"),
]

_METHODOLOGY = (
    "\n## ANTI-HALLUCINATION RULES\n\n"
    "Before identifying any issue in a file, you MUST read that file first.\n"
    "Never reference a file path or symbol you have not confirmed exists\n"
    "via read_file, search_codebase, or list_directory.\n"
    "Every finding MUST be grounded in code you actually observed.\n"
    "If a tool returns an error (e.g. file not found, permission denied),\n"
    "do NOT report that error as a finding. Either retry with a corrected\n"
    "path or skip the file entirely. Tool errors are not code issues.\n"
    "If the repository appears to be in a language you do not understand,\n"
    "say so — never fabricate findings in a different language.\n"
    "After reading each file, describe what you observed before forming judgments.\n"
    "Only include findings whose evidence comes from code you successfully read.\n"
    "Before reporting a class as missing any method (especially __init__),\n"
    "read the superclass to verify the method is not inherited. If a class\n"
    "body is simply 'pass', it inherits all behavior from its parent —\n"
    "verify before reporting anything missing.\n"
    "Never emit a final verdict until you have inspected at least one changed\n"
    "file with the exploration tools; a verdict with zero tool calls is\n"
    "rejected and you will be asked to explore.\n"
)


def _build_review_plan() -> ReviewPlan:
    """Load phase prompts from disk and build a ``ReviewPlan``."""
    phases: list[ReviewPhase] = []
    for phase_id, phase_name in _PHASES:
        path = _PHASE_PROMPT_DIR / f"{phase_id}.md"
        raw = path.read_text()
        prompt = ReviewResponseParser.strip_frontmatter(raw)
        phases.append(ReviewPhase(
            phase_id=phase_id,
            phase_name=phase_name,
            system_prompt=prompt,
        ))
    return ReviewPlan(phases=tuple(phases), methodology=_METHODOLOGY)

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
    conversation_logger: MarkdownConversationLogger
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
    chat_client = OllamaChatClient(
        model=config.llm_model or "code-review:latest",
        host=config.llm_host,
        timeout=config.ollama_timeout,
        max_retries=config.llm_max_retries,
    )
    command_bus = InMemoryCommandBus()
    conversation_logger = MarkdownConversationLogger(
        base_dir=Path(config_dir) / "conversations"
    )
    turn_parser = TurnParser(ReviewResponseParser())
    conversation_service = AgentConversationService(
        chat_port=chat_client,
        command_bus=command_bus,
        conversation_logger=conversation_logger,
    )
    verify_prompt_path = _PHASE_PROMPT_DIR / "verify-findings.md"
    verify_prompt = ReviewResponseParser.strip_frontmatter(
        verify_prompt_path.read_text()
    )
    verifier = FindingVerifier(
        chat_port=chat_client,
        verify_prompt=verify_prompt,
        tool_factory=lambda repo_path, changed_files: ExplorationToolService(
            repo_path, changed_files=changed_files
        ),
    )
    aggregator = FindingAggregator(ReasonBuilder())
    orchestrator = MultiPhaseReviewOrchestrator(
        command_bus=command_bus,
        tool_factory=lambda repo_path, changed_files: ExplorationToolService(
            repo_path, changed_files=changed_files
        ),
    )
    command_bus.register(
        RunAgentConversationCommand, conversation_service.execute
    )
    command_bus.register(RunMultiPhaseReviewCommand, orchestrator.execute)
    command_bus.register(
        AggregateReviewFindingsCommand, aggregator.execute
    )
    command_bus.register(VerifyFindingsCommand, verifier.execute)
    command_bus.register(ParseReviewTurnCommand, turn_parser.execute)
    event_logger = EventLoggingHandler()
    command_bus.register(
        ReviewTurnParsedEvent, event_logger.handle_review_turn_parsed
    )
    command_bus.register(
        ConversationCompletedEvent, event_logger.handle_conversation_completed
    )
    command_bus.register(
        PhaseCompletedEvent, event_logger.handle_phase_completed
    )
    command_bus.register(
        FindingsAggregatedEvent, event_logger.handle_findings_aggregated
    )
    plan = _build_review_plan()
    llm_review: LlmReviewPort = OllamaAgentAdapter(
        chat_client=chat_client,
        orchestrator=orchestrator,
        plan=plan,
    )
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
    )

    return CoreServices(
        pr_repository=pr_repository,
        llm_review=llm_review,
        command_bus=command_bus,
        conversation_logger=conversation_logger,
        notifier=notifier,
        fragment_repository=fragment_repository,
        fragment_renderer=fragment_renderer,
        fragment_max_tokens=fragment_max_tokens,
        review_context_factory=review_context_factory,
    )
