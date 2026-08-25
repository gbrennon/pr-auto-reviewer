"""IdentifierGroundingFilterService — strip unevidenced identifiers from generated prompts."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class IdentifierGroundingFilterService:
    """Genericize identifier-like tokens that lack transcript evidence.

    Advisor corrections and manager re-plans are LLM-generated text;
    they can invent class or file names and propagate them into the
    next peer's prompt as fact (observed live: an advisor invented
    ``AppInbound`` / ``ShallowInbound level 0`` and the manager re-plan
    repeated them).  Every multi-hump CamelCase name and repository
    path in the text must also appear in the observed evidence — the
    transcript, the findings, the assignment — otherwise it is replaced
    with a neutral placeholder before reaching another agent.
    """

    _CAMEL_TOKEN = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
    _PATH_TOKEN = re.compile(r"\b[\w.-]+(?:/[\w.-]+)+\.\w{1,4}\b")
    _PLACEHOLDER = "[unverified reference]"

    def strip_unobserved(self, text: str, evidence: str) -> str:
        """Return *text* with unevidenced identifiers genericized."""
        if not text:
            return text
        grounded = self._PATH_TOKEN.sub(
            lambda match: self._keep_or_replace(match.group(0), evidence),
            text,
        )
        grounded = self._CAMEL_TOKEN.sub(
            lambda match: self._keep_or_replace(match.group(0), evidence),
            grounded,
        )
        return grounded

    @staticmethod
    def _keep_or_replace(token: str, evidence: str) -> str:
        """Keep *token* when *evidence* cites it; replace it otherwise."""
        if token in evidence:
            return token
        logger.info(
            "Stripping unevidenced identifier from generated prompt: %s",
            token,
        )
        return IdentifierGroundingFilterService._PLACEHOLDER
