"""CompositionRoot — wires all layers and exposes application entry points."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pr_auto_reviewer.application.ports.inbound.process_issue_commands_port import (
    ProcessIssueCommandsPort,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_port import (
    ReviewPullRequestPort,
)
from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    ConversationLoggerPort,
)
from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort
from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)
from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.infrastructure.client.repo_update_tracker import RepoUpdateTracker
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.config import load_config
from pr_auto_reviewer.infrastructure.container import Container
from pr_auto_reviewer.infrastructure.temp_file_cleaner import clean_temp_files
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort

from .application_components import ApplicationComponents
from .composition_root import CompositionRoot

logger = logging.getLogger(__name__)


def bootstrap(*, notifier: NotifierPort | None = None) -> ApplicationComponents:
    """Backward-compatible entry point.  Delegates to CompositionRoot."""
    try:
        deleted = clean_temp_files()
        if deleted:
            logger.info("Cleaned up %d stale temp file(s) on startup", deleted)
    except Exception:
        logger.warning("Temp file cleanup failed, continuing", exc_info=True)

    root = CompositionRoot(notifier=notifier)
    return root.components


def run_daemon(components: ApplicationComponents | None = None) -> None:
    """Backward-compatible daemon runner."""
    if components is None:
        root = CompositionRoot()
        root.run_daemon()
    else:
        root = CompositionRoot()
        root._components = components
        root.run_daemon()


__all__ = ['CliRunner', 'Container', 'ConversationLoggerPort', 'InMemoryCommandBus', 'IssueBodyBuilder', 'IssueCommandParser', 'NotifierPort', 'PollingDaemon', 'PollingDaemonConfig', 'PrListerPort', 'ProcessIssueCommandsPort', 'ProcessIssueCommandsService', 'RepoListerPort', 'RepoUpdateTracker', 'ReviewItemParser', 'ReviewPullRequestPort', 'ReviewPullRequestService', 'ReviewReaderPort', 'TokenVerifierPort', 'annotations', 'bootstrap', 'clean_temp_files', 'dataclass', 'load_config', 'logger', 'logging', 'run_daemon']
