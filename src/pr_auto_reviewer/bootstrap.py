"""Bootstrap the PR Auto Reviewer."""

import os
from pathlib import Path

from .config import Config

class Bootstrap:
    """Bootstrap the PR Auto Reviewer."""

    def __init__(self, config: Config) -> None:
        """Initialize the bootstrapper.

        Args:
            config: Configuration object
        """
        self.config = config

    def run(self) -> None:
        """Run the bootstrap."""
        print("Bootstrapping PR Auto Reviewer...")

        # Create state directory
        state_dir = Path.home() / ".pr-auto-reviewer" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created state directory: {state_dir}")

        # Create config file if it doesn't exist
        config_path = Path.home() / ".pr-auto-reviewer" / "config.toml"
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                f.write("""# PR Auto Reviewer Configuration

# Ollama settings
ollama_host = "http://localhost:11434"
ollama_model = "llama3"

# Forgejo settings
forgejo_host = "https://codeberg.org"
forgejo_token = ""  # Personal access token
forgejo_reviewer_token = ""  # Token for the reviewer user
forgejo_reviewer_username = ""  # Username of the reviewer

# Review settings
review_template = ""
""")
            print(f"Created config file: {config_path}")
        else:
            print(f"Config file already exists: {config_path}")

        # Create example .env file
        env_path = Path.home() / ".pr-auto-reviewer" / ".env.example"
        if not env_path.exists():
            with open(env_path, "w") as f:
                f.write("""# PR Auto Reviewer Environment Variables

# Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# Forgejo settings
FORGEJO_HOST=https://codeberg.org
FORGEJO_TOKEN=your-personal-access-token
FORGEJO_REVIEWER_TOKEN=reviewer-user-token
FORGEJO_REVIEWER_USERNAME=reviewer-username

# Review settings
REVIEW_TEMPLATE=
""")
            print(f"Created example .env file: {env_path}")
        else:
            print(f"Example .env file already exists: {env_path}")

        print("Bootstrap complete!")


def bootstrap() -> None:
    """CLI entry point for bootstrap command."""
    from .config import load_config
    config = load_config()
    boot = Bootstrap(config=config)
    boot.run()