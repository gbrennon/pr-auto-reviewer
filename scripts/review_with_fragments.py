#!/usr/bin/env python3
"""Review code using the fragment-based prompt composition system.

Uses the same GitPlatformHttpClient as the legacy system — works with
Codeberg, GitHub, and any Forgejo/Gitea instance configured in .env.

Usage:
    PYTHONPATH=src:. python scripts/review_with_fragments.py \
        --repo gbrennon/pr-auto-reviewer --pr 1 --language python

    PYTHONPATH=src:. python scripts/review_with_fragments.py \
        --diff-file my.diff --language python --prompt-only

    PYTHONPATH=src:. python scripts/review_with_fragments.py \
        --diff-file my.diff --language python
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

def _build_http_client() -> object:
    from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
        GitPlatformHttpClient,
    )
    from pr_auto_reviewer.infrastructure.config.config import load_config

    cfg = load_config()
    return GitPlatformHttpClient(cfg.platform_api_url, cfg.platform_token)

def fetch_pr_diff(repo: str, pr_number: int) -> tuple[str, list[str]]:
    client = _build_http_client()

    diff_path = f"/repos/{repo}/pulls/{pr_number}.diff"
    diff = client.get_raw(diff_path)

    if not diff or len(diff.strip()) < 20:
        sys.exit(f"PR #{pr_number} returned empty or tiny diff ({len(diff)} chars)")

    files_path = f"/repos/{repo}/pulls/{pr_number}/files"
    files_data = client.get(files_path)
    file_paths = [f["filename"] for f in files_data]

    return diff, file_paths

def compose_prompt(language: str, diff: str, file_paths: list[str]) -> str:
    from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
    from pr_auto_reviewer.infrastructure.fragments.repositories import (
        FileSystemFragmentRepository,
    )
    from pr_auto_reviewer.infrastructure.fragments.renderers import Jinja2Renderer
    from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
        ComposeReviewPromptAdapter,
    )

    fragments_dir = Path("fragments")
    if not fragments_dir.is_dir():
        sys.exit("No fragments/ directory — run from project root")

    repo = FileSystemFragmentRepository(base_path=fragments_dir)
    renderer = Jinja2Renderer()
    service = ComposeReviewPromptAdapter(
        repository=repo, renderer=renderer, max_tokens=4000,
    )

    context = ReviewContext(language=language, file_paths=file_paths, diff=diff)

    composed = service.execute(context)
    print(f"\nSelected {len(composed.fragments_used)} fragments: {composed.fragments_used}")
    print(f"\nTokens: {composed.total_tokens}  Fragments: {composed.fragments_used}")
    return composed.content

def call_ollama(prompt: str, model: str) -> tuple[str, dict]:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    print(f"Calling Ollama at {host} with model {model}...")
    print(f"Prompt: {len(prompt)} chars (~{len(prompt)//4} tokens)\n")

    SEP = "\n\n---\n\n"
    system_text = ""
    user_text = prompt
    if SEP in prompt:
        parts = prompt.split(SEP, 1)
        system_text = parts[0]
        user_text = parts[1]

    payload: dict = {"model": model, "prompt": user_text, "stream": False}
    if system_text:
        payload["system"] = system_text

    resp = requests.post(
        f"{host}/api/generate",
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("response", ""), body

def extract_json(text: str):
    import re
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None

def determine_verdict(review: dict) -> str:
    verdict = review.get("verdict", "").lower()
    if verdict in ("approve", "approved"):
        return "approved"
    if verdict in ("request_changes", "changes_requested"):
        return "changes_requested"
    for issue in review.get("issues", []):
        if issue.get("severity", "").lower() in ("critical", "high"):
            return "changes_requested"
    return "approved"

def _code_fence(code: str, lang: str = "") -> str:
    code = code.replace("\\n", "\n").replace("\\t", "    ")
    return f"```{lang}\n{code}\n```"

def _fmt_location(file: str, line: str) -> str:
    if file and line:
        return f"{file}:{line}"
    return file or ""

def build_review_body(review: dict, model: str) -> tuple[str, str]:
    import os as _os
    issues = review.get("issues", [])
    suggestions = review.get("suggestions", [])
    praise = review.get("praise", [])
    summary = review.get("summary", "")
    verdict_reason = review.get("verdict_reason", "")
    model_name = model or _os.environ.get("OLLAMA_MODEL", "code-review")

    verdict = determine_verdict(review)
    verdict_text = "Approved" if verdict == "approved" else "Changes Requested"

    body = "AI Code Review\n\n"
    body += f"Verdict: {verdict_text}\n"
    if verdict_reason:
        body += f"Reason: {verdict_reason}\n"

    if issues:
        body += "Issues\n\n"
        for i in issues:
            sev = i.get("severity", "medium").upper()
            typ = i.get("type", i.get("category", ""))
            loc = _fmt_location(i.get("file", ""), i.get("line", ""))
            desc = i.get("description", "")
            current_code = i.get("current_code", "")
            suggested_fix = i.get("suggested_fix", "")
            type_tag = f" [{typ}]" if typ else ""
            location_part = f" {loc}:" if loc else ""
            body += f"    [{sev}]{type_tag}{location_part} {desc}\n"
            if current_code and suggested_fix:
                body += "\n"
                body += f"    {_code_fence(current_code)}\n"
                body += "\n"
                body += "    Suggested:"
                body += f"\n\n    {_code_fence(suggested_fix)}\n"
                body += "\n"
        body += "\n"

    if suggestions:
        body += "Suggestions\n\n"
        for s in suggestions:
            loc = _fmt_location(s.get("file", ""), s.get("line", ""))
            desc = s.get("description", "")
            current_code_s = s.get("current_code", "")
            suggested_code = s.get("suggested_code", "")
            location_part = f" {loc}:" if loc else ""
            body += f"    {location_part} {desc}\n"
            if current_code_s and suggested_code:
                body += "\n"
                body += f"    {_code_fence(current_code_s)}\n"
                body += "\n"
                body += "    Suggested:"
                body += f"\n\n    {_code_fence(suggested_code)}\n"
                body += "\n"
        body += "\n"

    if praise:
        body += "Praise\n\n"
        for p in praise:
            file = p.get("file", "")
            desc = p.get("description", "")
            body += f"    {file}: {desc}\n" if file else f"    {desc}\n"
        body += "\n"

    if summary:
        body += f"Summary: {summary}\n"

    body += f"\n---\n*Review by {model_name} via local Forgejo*"
    return verdict, body

def post_formal_review(repo: str, pr_number: int, verdict: str, body: str) -> None:
    from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
        GitPlatformHttpClient,
    )
    from pr_auto_reviewer.infrastructure.config.config import load_config

    cfg = load_config()
    api_token = cfg.platform_token
    reviewer_token = cfg.reviewer_token or api_token
    reviewer_username = cfg.reviewer_username

    if not reviewer_token:
        sys.exit("No reviewer token configured — cannot post to platform")
    if not reviewer_username:
        sys.exit("No reviewer username configured")

    event_map = {"approved": "APPROVED", "changes_requested": "REQUEST_CHANGES"}
    event = event_map.get(verdict, "COMMENT")

    client = GitPlatformHttpClient(cfg.platform_api_url, api_token)

    try:
        client.post(
            f"/repos/{repo}/pulls/{pr_number}/requested_reviewers",
            {"reviewers": [reviewer_username]},
        )
    except Exception:
        pass

    review_client = GitPlatformHttpClient(cfg.platform_api_url, reviewer_token)
    try:
        resp = review_client.post(
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            {"event": event, "body": body},
        )
        review_id = resp.get("id", "")
        print(f"\nReview ({verdict}) posted to {repo}#{pr_number}")
        if review_id:
            print(f"  Review ID: {review_id}")
    except Exception as e:
        print(f"\nFailed to post review: {e}")
        print("=" * 60)
        print("REVIEW (not posted — see below)")
        print("=" * 60)
        print(body)
        raise

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review code using fragment-based prompt composition"
    )
    parser.add_argument("--repo", help="Repository (owner/repo)")
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--diff-file", type=Path, help="Local diff file")
    parser.add_argument("--full-file", type=Path, help="Full source file for language auto-detection")
    parser.add_argument("--language", default=None, help="Programming language (auto-detected if omitted)")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "codellama"), help="Ollama model")
    parser.add_argument(
        "--output", choices=["terminal", "platform"], default="terminal",
        help="Where to send the review (default: terminal)",
    )
    parser.add_argument(
        "--prompt-only", action="store_true",
        help="Only compose the prompt, skip Ollama",
    )
    args = parser.parse_args()

    if args.diff_file:
        diff = args.diff_file.read_text()
        file_paths = ["unknown"]
        print(f"Loaded diff from {args.diff_file} ({len(diff)} chars)")
    elif args.repo and args.pr:
        print(f"Fetching PR #{args.pr} from {args.repo}...")
        diff, file_paths = fetch_pr_diff(args.repo, args.pr)
        print(f"Fetched {len(diff)} chars, {len(file_paths)} files: "
              f"{', '.join(file_paths[:10])}")
    else:
        sys.exit("Need --repo/--pr or --diff-file")

    if args.language is None:
        from pr_auto_reviewer.infrastructure.context.language_detector import (
            LanguageDetector,
        )
        detector = LanguageDetector()
        args.language = detector.detect(file_paths)
        if args.language != "unknown":
            print(f"Auto-detected language: {args.language}")
        elif args.full_file:
            full_content = args.full_file.read_text()
            import re
            if re.search(r"^\s*use\s+", full_content, re.MULTILINE):
                args.language = "rust"
            elif re.search(r"^\s*(import|from)\s+", full_content, re.MULTILINE):
                args.language = "python"
            elif re.search(r"^\s*package\s+", full_content, re.MULTILINE):
                args.language = "go"
            print(f"Content-detected language: {args.language}")

    if not args.language or args.language == "unknown":
        sys.exit("Could not detect language. Use --language to specify explicitly.")

    prompt = compose_prompt(args.language, diff, file_paths)

    if args.prompt_only:
        print("\n" + "=" * 60)
        print("COMPOSED PROMPT")
        print("=" * 60)
        print(prompt)
        return

    raw_response, ollama_body = call_ollama(prompt, model=args.model)

    prompt_tokens_est = len(prompt) // 4
    eval_count = ollama_body.get("eval_count", 0)
    eval_duration = ollama_body.get("eval_duration", 0) / 1e9
    total_duration = ollama_body.get("total_duration", 0) / 1e9
    load_duration = ollama_body.get("load_duration", 0) / 1e9
    prompt_eval_count = ollama_body.get("prompt_eval_count", "?")

    print(f"\n{'─' * 60}")
    print(f"  Tokens — prompt: ~{prompt_tokens_est} est (Ollama eval: {prompt_eval_count})")
    print(f"  Tokens — completion: {eval_count}")
    print(f"  Tokens — total: ~{prompt_tokens_est + eval_count}")
    input_cost = os.getenv("MODEL_INPUT_COST_PER_1K")
    output_cost = os.getenv("MODEL_OUTPUT_COST_PER_1K")
    if input_cost and output_cost:
        input_c = float(input_cost)
        output_c = float(output_cost)
        cost = (prompt_tokens_est / 1000) * input_c + (eval_count / 1000) * output_c
        print(f"  Cost estimate: ${cost:.6f}")
    print(f"  Time — eval: {eval_duration:.1f}s, load: {load_duration:.1f}s, total: {total_duration:.1f}s")
    print(f"{'─' * 60}")

    parsed = extract_json(raw_response)
    if parsed is None:
        print("WARNING: Could not parse JSON from Ollama response, using raw text")
        parsed = {"summary": raw_response, "issues": [], "suggestions": [], "praise": []}

    verdict, formatted = build_review_body(parsed, args.model)

    if args.output == "platform":
        post_formal_review(args.repo, args.pr, verdict, formatted)
    else:
        print("\n" + "=" * 60)
        print(f"REVIEW — Verdict: {verdict.upper()}")
        print("=" * 60)
        print(formatted)

if __name__ == "__main__":
    main()
