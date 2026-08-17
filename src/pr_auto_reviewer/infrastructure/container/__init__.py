"""Container — DI container package.

Re-exports Container (facade) and load_config for callers and
monkeypatch compatibility.
"""

from pr_auto_reviewer.infrastructure.config import Config, load_config
from pr_auto_reviewer.infrastructure.container._container import Container

__all__ = ["Config", "Container", "load_config"]
