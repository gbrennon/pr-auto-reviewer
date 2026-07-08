import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import OllamaLlmAdapter
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder

def _parse_argv(argv: list[str]) -> dict:
    opts: dict = {
        "diff_file": None,
        "output_file": None,
        "repo": "unknown",
        "owner": None,
        "repo_name": None,
        "pr_number": None,
        "head_sha": None,
    }
    positional: list[str] = []
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--repo":
            i += 1; opts["repo"] = argv[i]
        elif arg == "--owner":
            i += 1; opts["owner"] = argv[i]
        elif arg == "--repo-name":
            i += 1; opts["repo_name"] = argv[i]
        elif arg == "--pr":
            i += 1; opts["pr_number"] = int(argv[i])
        elif arg == "--sha":
            i += 1; opts["head_sha"] = argv[i]
        else:
            positional.append(arg)
        i += 1

    if len(positional) >= 1:
        opts["diff_file"] = Path(positional[0])
    if len(positional) >= 2:
        opts["output_file"] = Path(positional[1])
    return opts

def main():
    opts = _parse_argv(sys.argv)

    if opts["diff_file"] is None or opts["output_file"] is None:
        print(
            "Usage: _generate_review.py <diff_file> <output_json>"
            " [--repo <repo>] [--owner <owner>] [--repo-name <name>]"
            " [--pr <number>] [--sha <head_sha>]",
            file=sys.stderr,
        )
        sys.exit(1)

    diff_content = opts["diff_file"].read_text()
    max_diff = int(os.environ.get("OLLAMA_MAX_DIFF_CHARS", 20000))
    if len(diff_content) > max_diff:
        chunks = diff_content.split("diff --git ")
        truncated = []
        for chunk in chunks:
            candidate = ("diff --git " + chunk) if truncated else chunk
            if sum(len(c) for c in truncated) + len(candidate) > max_diff:
                break
            truncated.append(candidate)
        diff_content = "".join(truncated).rstrip() + "\n"
        print(f"Diff truncated: {len(opts['diff_file'].read_text())} -> {len(diff_content)} chars ({len(truncated)}/{len(chunks)} chunks kept)")
    diff = PullRequestDiff(pr_id=None, head_sha=None, diff_content=diff_content)
    context = RepositoryContext(
        architecture_hint="unknown",
        repository_structure=opts["repo"],
        conventions=None,
    )

    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build(diff, context)
    print(f"Diff: {len(diff_content)} chars, Prompt: {len(prompt)} chars")

    try:
        host = os.environ.get("OLLAMA_HOST", os.environ.get("LLM_HOST", "http://localhost:11434"))
        model = os.environ.get("OLLAMA_MODEL", os.environ.get("LLM_MODEL", "code-review"))
        llm = OllamaLlmAdapter(host=host, model=model)
        review = llm.review(diff, context)

        result: dict = {
            "verdict": review.verdict.value,
            "summary": review.summary or "(no summary provided by model)",
            "model_used": review.model_used,
            "items": [
                {
                    "number": item.number,
                    "severity": item.severity.value,
                    "category": item.category,
                    "file_path": item.file_path,
                    "description": item.description,
                }
                for item in review.items
            ],
        }

        if opts["owner"]:
            result["owner"] = opts["owner"]
        if opts["repo_name"]:
            result["repo"] = opts["repo_name"]
            if opts["owner"]:
                result["full_repo"] = f"{opts['owner']}/{opts['repo_name']}"
        if opts["pr_number"] is not None:
            result["pr_number"] = opts["pr_number"]
        if opts["head_sha"]:
            result["head_sha"] = opts["head_sha"]

        opts["output_file"].write_text(json.dumps(result, indent=2))
        print(f"Review saved: {opts['output_file']}")
        print(f"  Verdict: {review.verdict.value}")
        print(f"  Items: {len(review.items)}")
        print(f"  Summary: {review.summary[:100]}..." if review.summary else "  Summary: (none)")

    except Exception as e:
        print(f"LLM review failed: {e}", file=sys.stderr)
        print("Saving placeholder...", file=sys.stderr)
        opts["output_file"].write_text(json.dumps({"_error": str(e)}, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
