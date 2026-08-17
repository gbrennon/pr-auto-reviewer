"""Capture real API responses as fixture data for git_platform integration tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv

load_dotenv()

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_publisher import (
    ForgejoCommentPublisher,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_reader import ForgejoCommentReader
from pr_auto_reviewer.infrastructure.forgejo.issue_tracker import ForgejoIssueTracker
from pr_auto_reviewer.infrastructure.forgejo.review_reader import ForgejoReviewReader
from pr_auto_reviewer.infrastructure.github.github_review_publisher import (
    GithubReviewPublisher as GitReviewPublisherAdapter,
)

TOKEN = os.getenv("FORGEJO_OWNER_TOKEN")
if not TOKEN:
    print("FORGEJO_OWNER_TOKEN not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://codeberg.org/api/v1"
OUT_DIR = Path(__file__).resolve().parent

with open(OUT_DIR / "pr_fixtures.json") as f:
    pr_data = json.load(f)

PR = pr_data["private_pr"]
PU = pr_data["public_pr"]

scenarios = [
    {"label": "private", "repo": PR["repo"], "pr_number": PR["pr_number"], "head_sha": PR["head_sha"]},
    {"label": "public",  "repo": PU["repo"],  "pr_number": PU["pr_number"],  "head_sha": PU["head_sha"]},
]

client = GitPlatformHttpClient(BASE_URL, TOKEN)

def save_json(name, data):
    with open(OUT_DIR / name, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  -> saved {name}")

print("1. HTTP client ...")
http_fix = {}
for s in scenarios:
    L, repo, n = s["label"], s["repo"], s["pr_number"]
    try:
        r = client.get(f"/repos/{repo}/pulls/{n}")
        http_fix[f"{L}_get_pull"] = {"path": f"/repos/{repo}/pulls/{n}", "number": r.get("number"), "title": r.get("title")}
        print(f"  {L}: GET pull OK")
    except requests.RequestException as e:
        print(f"  {L}: GET pull ERR {e}")
    try:
        txt = client.get_raw(f"/repos/{repo}/pulls/{n}.diff")
        http_fix[f"{L}_get_raw"] = {"path": f"/repos/{repo}/pulls/{n}.diff", "len": len(txt)}
        print(f"  {L}: GET_RAW diff OK ({len(txt)} chars)")
    except requests.RequestException as e:
        print(f"  {L}: GET_RAW diff ERR {e}")
    try:
        r = client.get("/users/search", q="gbrennon", limit=1)
        http_fix[f"{L}_get_params"] = {"path": "/users/search", "has_data": bool(r.get("data"))}
        print(f"  {L}: GET /users/search OK")
    except requests.RequestException as e:
        print(f"  {L}: GET /users/search ERR {e}")
save_json("http_client_fixtures.json", http_fix)

print("2. Comment reader ...")
cr = ForgejoCommentReader(client)
cmt_fix = {}
for s in scenarios:
    L = s["label"]
    pid = PullRequestId(repository=s["repo"], number=s["pr_number"])
    try:
        comments = cr.get_comments(pid)
        cmt_fix[L] = {"repo": s["repo"], "pr_number": s["pr_number"], "count": len(comments),
                       "comments": [{"id": str(c.id), "body": c.body, "created_at": c.created_at.isoformat()} for c in comments]}
        print(f"  {L}: {len(comments)} comments OK")
    except requests.RequestException as e:
        cmt_fix[L] = {"repo": s["repo"], "pr_number": s["pr_number"], "error": str(e)}
        print(f"  {L}: ERR {e}")
save_json("comment_reader_fixtures.json", cmt_fix)

print("3. Review reader ...")
rr = ForgejoReviewReader(client)
rr_fix = {}
for s in scenarios:
    L = s["label"]
    pid = PullRequestId(repository=s["repo"], number=s["pr_number"])
    try:
        body = rr.get_latest_review(pid)
        rr_fix[L] = {"repo": s["repo"], "pr_number": s["pr_number"], "has_review": body is not None}
        print(f"  {L}: review={'present' if body else 'none'} OK")
    except requests.RequestException as e:
        rr_fix[L] = {"repo": s["repo"], "pr_number": s["pr_number"], "error": str(e)}
        print(f"  {L}: ERR {e}")
save_json("review_reader_fixtures.json", rr_fix)

print("5. Comment publisher ...")
cp = ForgejoCommentPublisher(client)
cp_fix = {}
s = scenarios[0]
pid = PullRequestId(repository=s["repo"], number=s["pr_number"])
try:
    cp.post(pid, "Test from capture script")
    cp_fix["private"] = {"repo": s["repo"], "pr_number": s["pr_number"], "success": True}
    print("  private: posted OK")
except requests.RequestException as e:
    cp_fix["private"] = {"repo": s["repo"], "pr_number": s["pr_number"], "success": False, "error": str(e)}
    print(f"  private: ERR {e}")
save_json("comment_publisher_fixtures.json", cp_fix)

print("6. Issue tracker ...")
it = ForgejoIssueTracker(client)
it_fix = {}
s = scenarios[0]
repo = s["repo"]
try:
    issue = it.create(repository=repo, title="Test issue from capture script", body="Please ignore.")
    it_fix["private"] = {"repo": repo, "issue_number": issue.id, "title": issue.title}
    print(f"  private: created #{issue.id} OK")
except requests.RequestException as e:
    it_fix["private"] = {"repo": repo, "error": str(e)}
    print(f"  private: ERR {e}")
save_json("issue_tracker_fixtures.json", it_fix)

print("7. Review publisher ...")
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

rp = GitReviewPublisherAdapter(client, reviewer_username="gbrennon")
rp_fix = {}
s = scenarios[0]
pid = PullRequestId(repository=s["repo"], number=s["pr_number"])
review = CodeReview(
    id=CommentId("test-1"), verdict=ReviewVerdict.APPROVED,
    summary="Test review from capture script",
    items=[ReviewItem(id="test-001", category="test", severity=ItemSeverity.LOW, description="Test item.", file_path="README.md")],
    pr_id=pid, model_used="test-capture")
try:
    rp.publish(pid, review)
    rp_fix["private"] = {"repo": s["repo"], "pr_number": s["pr_number"], "success": True}
    print("  private: published OK")
except requests.RequestException as e:
    rp_fix["private"] = {"repo": s["repo"], "pr_number": s["pr_number"], "success": False, "error": str(e)}
    print(f"  private: ERR {e}")
save_json("review_publisher_fixtures.json", rp_fix)

print("\nDone!")
