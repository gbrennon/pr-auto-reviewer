"""Tests for InteractiveGitCredentialPrompter."""


from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials
from pr_auto_reviewer.infrastructure.git_credentials.interactive_git_credential_prompter import (
    InteractiveGitCredentialPrompter,
)


class TestInteractiveGitCredentialPrompter:

    def test_prompt_returns_credentials_from_user(self, capsys) -> None:
        prompter = InteractiveGitCredentialPrompter(
            input_fn=lambda _prompt: "alice",
            prompt_fn=lambda _prompt: "tok123",
            isatty_fn=lambda: True,
        )

        creds = prompter.prompt("https", "codeberg.org")

        assert isinstance(creds, GitCredentials)
        assert creds.protocol == "https"
        assert creds.username == "alice"
        assert creds.secret == "tok123"

    def test_prompt_prints_protocol_host_and_username(self, capsys) -> None:
        prompter = InteractiveGitCredentialPrompter(
            input_fn=lambda _prompt: "bob",
            prompt_fn=lambda _prompt: "pw",
            isatty_fn=lambda: True,
        )

        prompter.prompt("ssh", "github.com")

        out = capsys.readouterr().out
        assert "github.com" in out
        assert "ssh" in out
        assert "bob" in out

    def test_prompt_returns_none_when_not_a_tty(self) -> None:
        prompter = InteractiveGitCredentialPrompter(
            input_fn=lambda _prompt: "alice",
            prompt_fn=lambda _prompt: "pw",
            isatty_fn=lambda: False,
        )

        assert prompter.prompt("https", "codeberg.org") is None

    def test_prompt_returns_none_when_secret_missing(self, capsys) -> None:
        prompter = InteractiveGitCredentialPrompter(
            input_fn=lambda _prompt: "alice",
            prompt_fn=lambda _prompt: "",
            isatty_fn=lambda: True,
        )

        assert prompter.prompt("https", "codeberg.org") is None
