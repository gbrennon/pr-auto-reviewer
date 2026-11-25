"""Composite settings presentation port for application wiring."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.presentation.general_settings_port import GeneralSettingsPort
from pr_auto_reviewer.presentation.global_credential_port import GlobalCredentialPort
from pr_auto_reviewer.presentation.repository_credential_port import RepositoryCredentialPort
from pr_auto_reviewer.presentation.repository_management_port import RepositoryManagementPort


class SettingsServicesPort(
    GeneralSettingsPort,
    GlobalCredentialPort,
    RepositoryCredentialPort,
    RepositoryManagementPort,
    Protocol,
):
    """Complete settings service composed from narrow capability ports."""
