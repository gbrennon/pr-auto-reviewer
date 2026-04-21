#!/usr/bin/env python3
"""Build the Ollama user prompt for code review.

Sends ONLY per-PR context (diff, repo structure, project type hint,
conventions). The model's SYSTEM prompt (from the Modelfile) contains
all review behavior, persona, and output format instructions.
"""

import os

diff = os.environ.get("DIFF_CONTENT", "")
repo_structure = os.environ.get("REPO_STRUCTURE", "")
architecture_hint = os.environ.get("ARCHITECTURE_HINT", "")
conventions = os.environ.get("CONVENTIONS", "")

sections = []

if architecture_hint:
    sections.append(f"PROJECT TYPE: {architecture_hint}\n")

if repo_structure:
    sections.append(f"""REPOSITORY STRUCTURE

The following is the file tree of the repository. Use this to understand
the codebase architecture and how files relate to each other.

{repo_structure}
""")

if conventions:
    sections.append(f"""PROJECT CONVENTIONS

{conventions}
""")

sections.append(f"DIFF:\n\n{diff}")

print("\n".join(sections))
