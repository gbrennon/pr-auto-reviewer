#!/bin/bash
# Temporary script to validate the review flow with real world
# Usage: ./scripts/validate-review-flow.sh <repo> <pr_number>
# Example: ./scripts/validate-review-flow.sh owner/repo 123

set -e

REPO="${1:-}"
PR_NUMBER="${2:-}"

if [[ -z "$REPO" || -z "$PR_NUMBER" ]]; then
    echo "Usage: $0 <repo> <pr_number>"
    echo "Example: $0 owner/repo 123"
    exit 1
fi

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

echo "=== Validating review flow for $REPO PR #$PR_NUMBER ==="
echo ""

cd "$PROJECT_DIR"
export PYTHONPATH=src:$PYTHONPATH

python3 << PYTHON_SCRIPT
import sys
import os

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.review_context import ReviewContext

REPO = "$REPO"
PR_NUMBER = $PR_NUMBER

FORGEJO_TOKEN = os.environ.get('FORGEJO_TOKEN', '')
FORGEJO_HOST = os.environ.get('FORGEJO_HOST', 'https://codeberg.org')
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'codellama')

if not FORGEJO_TOKEN:
    print('Error: FORGEJO_TOKEN not set')
    sys.exit(1)

# Step 1: Get PR data
print('=== Step 1: Fetch PR data from API ===')
import requests as req

pr_url = f'{FORGEJO_HOST}/api/v1/repos/{REPO}/pulls/{PR_NUMBER}'
response = req.get(pr_url, headers={'Authorization': f'token {FORGEJO_TOKEN}'}, timeout=30)

if response.status_code != 200:
    print(f'Error: Failed to get PR (status {response.status_code})')
    print(response.text)
    sys.exit(1)

pr_data = response.json()
print(f'  Title: {pr_data["title"]}')
print(f'  State: {pr_data["state"]}')
print(f'  Draft: {pr_data.get("draft", False)}')
print(f'  SHA: {pr_data["head"]["sha"]}')

if pr_data.get('draft', False):
    print('')
    print('Error: Cannot review draft PR')
    sys.exit(1)

# Step 2: Get diff
print('')
print('=== Step 2: Fetch PR diff ===')
diff_url = f'{FORGEJO_HOST}/api/v1/repos/{REPO}/pulls/{PR_NUMBER}.diff'
diff_response = req.get(diff_url, headers={'Authorization': f'token {FORGEJO_TOKEN}'}, timeout=30)
diff_content = diff_response.text
print(f'  Diff size: {len(diff_content)} bytes')

if not diff_content.strip():
    print('Error: Empty diff')
    sys.exit(1)

# Step 3: Get repository context
print('')
print('=== Step 3: Fetch repository context ===')
tree_url = f'{FORGEJO_HOST}/api/v1/repos/{REPO}/git/trees/{pr_data["base"]["ref"]}?recursive=1'
tree_response = req.get(tree_url, headers={'Authorization': f'token {FORGEJO_TOKEN}'}, timeout=30)

if tree_response.status_code != 200:
    print(f'Warning: Could not get file tree (status {tree_response.status_code})')
    tree_paths = []
else:
    tree_data = tree_response.json()
    tree_paths = [item['path'] for item in tree_data.get('tree', [])]

print(f'  Found {len(tree_paths)} files')

# Step 4: Build diff and context
print('')
print('=== Step 4: Build diff and context ===')

diff = PullRequestDiff(
    pr_id=PullRequestId(repository=REPO, number=PR_NUMBER),
    head_sha=CommitSha(pr_data['head']['sha']),
    diff_content=diff_content,
    repository_structure='\n'.join(tree_paths[:100]) if tree_paths else None,
)

from pr_auto_reviewer.infrastructure.git_platform.architecture_detector import ArchitectureDetector
detector = ArchitectureDetector()
arch_hint = detector.detect(tree_paths) if tree_paths else "unknown"

context = ReviewContext(
    architecture_hint=arch_hint,
    conventions=None,
    repository_structure='\n'.join(tree_paths[:100]) if tree_paths else None
)

print(f'  Architecture detected: {arch_hint}')

# Step 5: Call LLM
print('')
print('=== Step 5: Call LLM ===')
print(f'  Ollama: {OLLAMA_HOST}')
print(f'  Model: {OLLAMA_MODEL}')

from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import _PromptBuilder, _ReviewResponseParser

prompt = _PromptBuilder.build(diff, context)

print('')
print('=== Prompt (first 1500 chars) ===')
print(prompt[:1500])
print('...')
print('')

# Call LLM directly
raw_response = req.post(
    f"{OLLAMA_HOST}/api/generate",
    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
    timeout=120,
)
raw_response.raise_for_status()
raw_text = raw_response.json().get("response", "")

print('=== Raw LLM Response ===')
print(raw_text[:2500])
print('...')
print('')

# Parse response
review = _ReviewResponseParser.parse(raw_text, OLLAMA_MODEL)

print(f'  Parsed verdict: {review.verdict.value}')
print(f'  Parsed items: {len(review.items)}')

# Print items
print('')
print('=== Review Items ===')
if review.items:
    for item in review.items:
        print(f'{item.number}. **{item.severity.value.upper()}** [{item.category}] \`{item.file_path or "general"}\` - {item.description}')
else:
    print('  (No items found in response)')

print('')
print('=== Validation complete ===')
PYTHON_SCRIPT