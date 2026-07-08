#!/usr/bin/env python3
"""Capture fragment-based review fixtures from real PRs on Codeberg.

For each PR, this script:
1. Fetches the PR diff from the platform
2. Builds the fragment-based prompt (auto-detects language)
3. Calls Ollama for the review
4. Saves: diff, full file, Ollama response, and parsed review

Fixture naming: {username}-{repo}-pr{number}.json

Usage:
  python scripts/capture-fragment-fixtures.py gbrennon/dotfiles 22
  python scripts/capture-fragment-fixtures.py --all
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import requests

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.config.config import load_config
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.fragments.repositories import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.fragments.renderers import Jinja2Renderer

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DIFFS_DIR = FIXTURES_DIR / "diffs"
RESPONSES_DIR = FIXTURES_DIR / "ollama_responses"
REVIEWS_DIR = FIXTURES_DIR / "reviews"

SCENARIOS = [
    ("gbrennon/dotfiles", 22, "47b99e8"),
]

def capture_pr(repo: str, pr_num: int, sha: str) -> None:
    cfg = load_config()
    client = GitPlatformHttpClient(cfg.platform_api_url, cfg.platform_token)

    parts = repo.split("/")
    base = f"{parts[0]}-{parts[1]}-pr{pr_num}"

    raw_diff = client.get_raw(f"/repos/{repo}/pulls/{pr_num}.diff")
    (DIFFS_DIR / f"{base}.diff").write_text(raw_diff)
    print(f"  Diff: {len(raw_diff)} chars")

    paths = re.findall(r"^diff --git a/(.+?) b/(.+?)$", raw_diff, re.MULTILINE)
    file_contents = {}
    full_content = ""
    for a, b in paths:
        if b and b != "/dev/null":
            try:
                content = client.get_raw(f"/repos/{repo}/raw/{sha}/{b}")
                file_contents[b] = content
                full_content += f"\n=== {b} ===\n{content}"
                print(f"  File: {b} ({len(content)} chars)")
            except Exception:
                print(f"  File: {b} (skipped — 404)")

    if full_content:
        (DIFFS_DIR / f"{base}.full").write_text(full_content)

    fragments_dir = PROJECT_ROOT / "fragments"
    repo = FileSystemFragmentRepository(base_path=fragments_dir)
    renderer = Jinja2Renderer()
    from pr_auto_reviewer.infrastructure.context.language_detector import (
        LanguageDetector,
    )
    file_paths = list(file_contents.keys())
    detector = LanguageDetector()
    language = detector.detect(file_paths)
    context = ReviewContext(language=language, file_paths=file_paths, diff=raw_diff)
    service = ComposeReviewPromptAdapter(repository=repo, renderer=renderer)
    composed = service.execute(context)
    prompt = composed.content
    print(f"  Prompt: {len(prompt)} chars (language={language})")

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "code-review")

    resp = requests.post(
        f"{host}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    raw_response = resp.json()

    RESPONSES_DIR.mkdir(exist_ok=True)
    (RESPONSES_DIR / f"{base}.json").write_text(json.dumps(raw_response, indent=2))

    REVIEWS_DIR.mkdir(exist_ok=True)
    review_text = raw_response.get("response", "")
    (REVIEWS_DIR / f"{base}.json").write_text(review_text)

    print(f"  Done: {base}")

def main():
    DIFFS_DIR.mkdir(exist_ok=True)

    if len(sys.argv) >= 3:
        repo = sys.argv[1]
        pr_num = int(sys.argv[2])
        cfg = load_config()
        client = GitPlatformHttpClient(cfg.platform_api_url, cfg.platform_token)
        pr_data = client.get(f"/repos/{repo}/pulls/{pr_num}")
        sha = pr_data.get("head", {}).get("sha", "")
        print(f"Capturing {repo}#{pr_num} (sha: {sha[:7]})")
        capture_pr(repo, pr_num, sha)
        return

    for repo, pr_num, sha in SCENARIOS:
        print(f"Capturing {repo}#{pr_num}")
        capture_pr(repo, pr_num, sha)

if __name__ == "__main__":
    main()
