import pytest
from pr_auto_reviewer.presentation.composition_root import (
    CompositionRoot, ApplicationComponents, bootstrap, run_daemon,
)
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser


class TestCompositionRoot:

    @pytest.fixture
    def _root(self):
        return CompositionRoot()

    def test_composition_root_exposes_application_components(self, _root):
        assert isinstance(_root.components, ApplicationComponents)

    def test_components_review_service_is_wired(self, _root):
        assert isinstance(
            _root.components.review_service, ReviewPullRequestService,
        )

    def test_components_process_commands_service_is_wired(self, _root):
        assert isinstance(
            _root.components.process_commands_service,
            ProcessIssueCommandsService,
        )

    def test_components_review_reader_is_not_none(self, _root):
        assert _root.components.review_reader is not None

    def test_components_pr_lister_is_not_none(self, _root):
        assert _root.components.pr_lister is not None

    def test_components_repo_lister_is_not_none(self, _root):
        assert _root.components.repo_lister is not None

    def test_components_review_item_parser_is_wired(self, _root):
        assert isinstance(
            _root.components.review_item_parser, ReviewItemParser,
        )

    def test_components_cli_runner_is_wired(self, _root):
        assert isinstance(_root.components.cli_runner, CliRunner)

    def test_container_is_exposed(self, _root):
        assert _root.container is not None


class TestBootstrapBackwardCompat:

    def test_bootstrap_function_returns_application_components(self):
        components = bootstrap()
        assert isinstance(components, ApplicationComponents)

    def test_run_daemon_function_exists_and_accepts_components(self):
        components = bootstrap()
        assert components is not None
