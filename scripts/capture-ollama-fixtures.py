#!/usr/bin/env python3
"""Capture real Ollama responses for each multi-language diff fixture.

For each .diff/.full pair in tests/fixtures/diffs/, this script:
1. Builds the prompt via PromptBuilder (with file_contents!)
2. Calls the REAL Ollama via OllamaLlmAdapter
3. Saves the raw Ollama JSON response as an ollama_responses/*.json fixture
4. Also saves the parsed review fields for inspection

Usage: python scripts/capture-ollama-fixtures.py [--dry-run]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv()

from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import OllamaLlmAdapter
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DIFFS_DIR = FIXTURES_DIR / "diffs"
RESPONSES_DIR = FIXTURES_DIR / "ollama_responses"

# ── mapping: diff base name → file_path in the diff ───────────────────
SCENARIOS = [
    ("python-sql-injection",   "app/repository.py"),
    ("java-god-class",         "src/main/java/com/example/OrderService.java"),
    ("go-no-error-handling",   "pkg/handler/user.go"),
    ("rust-clean-service",     "src/services/user_service.rs"),
    ("ruby-hardcoded-secret",  "lib/payment_gateway.rb"),
    ("csharp-tight-coupling",  "Services/ReportGenerator.cs"),
    ("kotlin-clean-service",   "src/main/kotlin/com/example/UserService.kt"),
    ("shell-with-shebang",     "scripts/deploy.sh"),
    ("shell-missing-shebang",  "scripts/deploy.sh"),
]


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    host = os.environ.get("OLLAMA_HOST", os.environ.get("LLM_HOST",
                              "http://localhost:11434"))
    model = os.environ.get("OLLAMA_MODEL", os.environ.get("LLM_MODEL",
                              "code-review"))

    if dry_run:
        print(f"[DRY RUN] Would use Ollama at {host} with model={model}")
    else:
        llm = OllamaLlmAdapter(host=host, model=model)

    context = RepositoryContext(architecture_hint="")

    for base_name, file_path in SCENARIOS:
        diff_file = DIFFS_DIR / f"{base_name}.diff"
        full_file = DIFFS_DIR / f"{base_name}.full"
        out_file = RESPONSES_DIR / f"{base_name}.json"

        if not diff_file.exists():
            print(f"  SKIP {base_name}: missing {diff_file}")
            continue
        if not full_file.exists():
            print(f"  SKIP {base_name}: missing {full_file}")
            continue

        diff_content = diff_file.read_text()
        file_content = full_file.read_text()

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha("abc"),
            diff_content=diff_content,
            file_contents={file_path: file_content},
        )

        prompt = PromptBuilder.build(diff, context)
        print(f"\n{'='*60}")
        print(f"  {base_name}")
        print(f"    diff: {len(diff_content)} chars, prompt: {len(prompt)} chars")

        if dry_run:
            print(f"    [DRY RUN] Would save to {out_file.name}")
            continue

        # Call the REAL Ollama (captures raw response via monkey-patch)
        import requests
        import json as _json

        class RealOllamaCaller:
            def __init__(self, host: str, model: str):
                self._host = host.rstrip("/")
                self._model = model

            def call(self, prompt: str) -> dict:
                resp = requests.post(
                    f"{self._host}/api/generate",
                    json={"model": self._model, "prompt": prompt, "stream": False},
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()

        try:
            caller = RealOllamaCaller(host, model)
            raw_response = caller.call(prompt)
        except Exception as e:
            print(f"    ERROR: {e}")
            raw_response = {"_error": str(e)}

        # Save the raw Ollama JSON (what the API actually returned)
        out_file.write_text(json.dumps(raw_response, indent=2))
        resp_text = raw_response.get("response", "")
        print(f"    response: {len(resp_text)} chars → saved {out_file.name}")

        # Also parse it to show verdict
        if resp_text and "_error" not in raw_response:
            from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
                ReviewResponseParser,
            )
            review = ReviewResponseParser.parse(resp_text, model)
            print(f"    verdict: {review.verdict.value}, items: {len(review.items)}")

    print(f"\nDone! {len(SCENARIOS)} scenarios processed.")


if __name__ == "__main__":
    main()
