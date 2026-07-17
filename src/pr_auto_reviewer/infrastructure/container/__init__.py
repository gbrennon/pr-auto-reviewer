"""Container — DI container package.

Re-exports Container (facade) and load_config for callers and
monkeypatch compatibility.
"""

from pr_auto_reviewer.infrastructure.container._container import Container
from pr_auto_reviewer.infrastructure.config import Config, load_config

__all__ = ["Container", "load_config", "Config"]
