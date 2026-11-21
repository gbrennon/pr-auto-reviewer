"""Tests for loading authentication assignments from settings.toml."""

from pathlib import Path


def test_load_config_reads_auth_assignments_from_toml(
    monkeypatch, tmp_path: Path
) -> None:
    settings_dir = tmp_path / "config"
    settings_dir.mkdir()
    (settings_dir / "pr-auto-reviewer" / "settings.toml").parent.mkdir()
    (settings_dir / "pr-auto-reviewer" / "settings.toml").write_text(
        """
[auth.defaults]
manager_profile = "work-manager"
reviewer_profile = "review-bot"

[auth.profiles.work-manager]
provider = "gh"
host = "github.com"
account = "alice"
transport = "cli"

[auth.profiles.review-bot]
provider = "gh"
host = "github.com"
account = "acme-reviewer"
transport = "http"
""".strip()
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(settings_dir))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("PLATFORM_MODE", raising=False)

    from pr_auto_reviewer.infrastructure.config.config import load_config

    configuration = load_config().auth_configuration

    assert configuration.defaults.manager_profile == "work-manager"
    assert configuration.profile("review-bot").account == "acme-reviewer"
