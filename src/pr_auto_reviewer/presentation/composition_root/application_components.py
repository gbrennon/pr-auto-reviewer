from ._shared import *


@dataclass
class ApplicationComponents:
    """All application components wired together."""

    review_service: ReviewPullRequestPort
    process_commands_service: ProcessIssueCommandsPort
    review_reader: ReviewReaderPort
    pr_lister: PrListerPort
    repo_lister: RepoListerPort
    review_item_parser: ReviewItemParser
    cli_runner: CliRunner
    list_allowed_repositories: ListAllowedRepositories
    notifier: NotifierPort | None = None
    token_verifier: TokenVerifierPort | None = None
    command_bus: InMemoryCommandBus | None = None
    conversation_logger: ConversationLoggerPort | None = None

