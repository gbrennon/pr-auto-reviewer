"""clean.py - Clean state files."""

import os
from pathlib import Path


def clean() -> None:
    """Clean state files."""
    project_dir = Path(__file__).parent.parent.parent
    state_file = project_dir / "runner-data" / "pr-reviews.json"
    
    print("Cleaning state files...")
    if state_file.exists():
        state_file.unlink()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text('{"reviewed":{}}')
    print("Done. State reset.")


if __name__ == "__main__":
    clean()