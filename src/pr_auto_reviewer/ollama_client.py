"""Ollama client module for PR Auto Reviewer."""

import json
import requests
from typing import Optional, Dict, Any
from .config import Config

class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(self, config: Config) -> None:
        """Initialize the Ollama client.

        Args:
            config: Configuration object.
        """
        self.config = config

    def is_available(self) -> bool:
        """Check if Ollama is available.

        Returns:
            True if Ollama is available, False otherwise.
        """
        try:
            response = requests.get(
                f"{self.config.ollama_host}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate_review(self, diff_content: str, repo_structure: str = "") -> Optional[str]:
        """Generate a review using Ollama.

        Args:
            diff_content: The diff content to review.
            repo_structure: Optional repo file tree for context.

        Returns:
            Generated review or None if failed.
        """
        if not self.is_available():
            return None

        prompt = self._build_prompt(diff_content, repo_structure)

        try:
            response = requests.post(
                f"{self.config.ollama_host}/api/generate",
                json={
                    "model": self.config.ollama_model or "code-review:v1",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            return data.get("response")
        except (requests.RequestException, json.JSONDecodeError):
            return None

    def _build_prompt(self, diff_content: str, repo_structure: str = "") -> str:
        """Build the prompt for Ollama.

        Args:
            diff_content: The diff content.
            repo_structure: Optional repo file tree for context.

        Returns:
            Formatted prompt string.
        """
        structure_section = ""
        if repo_structure:
            structure_section = f"""

## REPOSITORY STRUCTURE

The following is the file tree of the repository. Use this to understand the codebase architecture and how files relate to each other.

{repo_structure}

"""

        return f"""You are a Senior Principal Software Engineer and Code Reviewer with deep expertise in software architecture, design patterns, SOLID principles, and engineering excellence. Your role is to provide constructive, actionable code reviews for pull requests.
{structure_section}## Code Changes:
{diff_content}

Please provide your review in the following format:

## Summary
Brief summary of the changes

## Issues
1. [severity] [type] [location]: description
2. [severity] [type] [location]: description

## Suggestions
1. [severity] [type] [location]: description
2. [severity] [type] [location]: description

## Verdict
approved | changes_requested | comment

Provide detailed feedback for each issue and suggestion.
"""
