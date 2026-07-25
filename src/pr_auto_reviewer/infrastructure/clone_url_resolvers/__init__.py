"""HTTPS and SSH clone URL resolver implementations."""

from .https_clone_url_resolver import HttpsCloneUrlResolver
from .ssh_clone_url_resolver import SshCloneUrlResolver

__all__ = ["HttpsCloneUrlResolver", "SshCloneUrlResolver"]
