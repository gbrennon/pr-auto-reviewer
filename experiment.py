import os
import re
import sys
import requests
from dataclasses import dataclass
from enum import Enum


# =========================
# FORGE BACKENDS
# =========================

class Forge(Enum):
    GITHUB = "github"
    CODEBERG = "codeberg"


class ReviewMode(Enum):
    FORMAL = "formal"
    COMMENT = "comment"


@dataclass(frozen=True)
class ForgeConfig:
    base_url: str
    auth_header: str
    diff_accept: str
    extra_headers: dict


def build_forge_config(forge: Forge, token: str) -> ForgeConfig:
    if forge == Forge.GITHUB:
        return ForgeConfig(
            base_url="https://api.github.com",
            auth_header=f"Bearer {token}",
            diff_accept="application/vnd.github.v3.diff",
            extra_headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    if forge == Forge.CODEBERG:
        return ForgeConfig(
            base_url="https://codeberg.org/api/v1",
            auth_header=f"token {token}",
            diff_accept="application/vnd.gitea.v1.diff",
            extra_headers={
                "Accept": "application/json",
            },
        )
    raise ValueError(f"Unknown forge: {forge}")


# =========================
# CONFIGURATION
# =========================

OWNER = "gbrennon"
REPO = "dotfiles"
PR_NUMBER = 46

REVIEW_FILE = "audio/scripts/audio_test.sh"


# =========================
# TOKEN RESOLUTION
# =========================

_ENV_TOKENS = {
    Forge.GITHUB: "GITHUB_REVIEWER_TOKEN",
    Forge.CODEBERG: "FORGEJO_REVIEWER_TOKEN",
}


def resolve_token(forge: Forge) -> str:
    env_var = _ENV_TOKENS[forge]
    token = os.environ.get(env_var)
    if not token:
        print(f"ERROR: environment variable {env_var} is not set.")
        sys.exit(1)
    return token


# =========================
# HTTP CLIENT
# =========================

def make_headers(config: ForgeConfig) -> dict:
    return {
        **config.extra_headers,
        "Authorization": config.auth_header,
        "Content-Type": "application/json",
    }


def pulls_url(config: ForgeConfig) -> str:
    return f"{config.base_url}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"


def reviews_url(config: ForgeConfig) -> str:
    return f"{config.base_url}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews"


def issues_comments_url(config: ForgeConfig) -> str:
    return f"{config.base_url}/repos/{OWNER}/{REPO}/issues/{PR_NUMBER}/comments"


def pulls_comments_url(config: ForgeConfig) -> str:
    return f"{config.base_url}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/comments"


# =========================
# HELPERS
# =========================

def get_pr_head_commit(config: ForgeConfig) -> str:
    response = requests.get(pulls_url(config), headers=make_headers(config))
    response.raise_for_status()
    return response.json()["head"]["sha"]


def get_diff_position(config: ForgeConfig, forge: Forge, target_file: str, target_line: int, side: str) -> int | None:
    """
    Resolves the comment anchor value for a given absolute line number.

    GitHub:   requires walking the diff to compute a diff-relative `position`.
    Codeberg: accepts the raw file line number via `old_position` / `new_position`.
    """
    if forge == Forge.CODEBERG:
        return target_line

    diff_headers = {**make_headers(config), "Accept": config.diff_accept}
    response = requests.get(pulls_url(config), headers=diff_headers)
    response.raise_for_status()

    in_target_file = False
    position = 0
    old_line = 0
    new_line = 0

    for raw_line in response.text.splitlines():
        if raw_line.startswith("diff --git"):
            in_target_file = target_file in raw_line
            position = 0
            old_line = 0
            new_line = 0
            continue

        if not in_target_file:
            continue

        if raw_line.startswith(("--- ", "+++ ")):
            continue

        if raw_line.startswith("@@"):
            m = re.search(r"-(\d+)(?:,\d+)? \+(\d+)", raw_line)
            if m:
                old_line = int(m.group(1)) - 1
                new_line = int(m.group(2)) - 1
            position += 1
            continue

        if raw_line.startswith("-"):
            old_line += 1
            position += 1
            if side == "LEFT" and old_line == target_line:
                return position

        elif raw_line.startswith("+"):
            new_line += 1
            position += 1
            if side == "RIGHT" and new_line == target_line:
                return position

        else:
            old_line += 1
            new_line += 1
            position += 1
            if side == "LEFT" and old_line == target_line:
                return position
            if side == "RIGHT" and new_line == target_line:
                return position

    return None


def build_inline_comment(forge: Forge, position: int, side: str, body: str) -> dict:
    """
    Builds the inline comment dict with the correct anchor field per forge.

    GitHub:   {"path": ..., "position": N,        "body": ...}
    Codeberg: {"path": ..., "old_position": N,    "body": ...}  (LEFT)
              {"path": ..., "new_position": N,    "body": ...}  (RIGHT)
    """
    comment = {"path": REVIEW_FILE, "body": body}

    if forge == Forge.GITHUB:
        comment["position"] = position
    elif forge == Forge.CODEBERG:
        comment["old_position" if side == "LEFT" else "new_position"] = position

    return comment


def prompt_request_changes_input() -> tuple[int, str, str]:
    """
    Interactively collects the line number, side, and suggestion from the user.
    Returns (line_number, side, comment_body).
    """
    print("\n-- Inline comment --")

    while True:
        raw_line = input("Line number: ").strip()
        if raw_line.isdigit() and int(raw_line) > 0:
            line_number = int(raw_line)
            break
        print("Please enter a valid positive integer.")

    print("Side:")
    print("  1. LEFT  (removed line, old file)")
    print("  2. RIGHT (added or context line, new file)")
    while True:
        raw_side = input("Side [1/2]: ").strip()
        if raw_side == "1":
            side = "LEFT"
            break
        if raw_side == "2":
            side = "RIGHT"
            break
        print("Please enter 1 or 2.")

    print("\nSuggestion (the replacement code).")
    print("Enter one line at a time. Leave a blank line when done:")
    suggestion_lines: list[str] = []
    while True:
        line = input()
        if line == "":
            break
        suggestion_lines.append(line)

    suggestion_block = "\n".join(suggestion_lines)
    body = f"```suggestion\n{suggestion_block}\n```"

    return line_number, side, body


# =========================
# REVIEW ACTIONS
# =========================

def submit_approval(config: ForgeConfig, mode: ReviewMode):
    if config.base_url == "https://api.github.com" and mode == ReviewMode.COMMENT:
        payload = {"body": "Looks good to me."}
        url = issues_comments_url(config)
    else:
        payload = {
            "body": "Looks good to me.",
            "event": "APPROVED",
        }
        url = reviews_url(config)
    response = requests.post(url, headers=make_headers(config), json=payload)
    print_response(response)


def submit_comment_review(config: ForgeConfig, mode: ReviewMode):
    if config.base_url == "https://api.github.com" and mode == ReviewMode.COMMENT:
        payload = {
            "body": (
                "General review comment.\n\n"
                "No blocking issues were found."
            ),
        }
        url = issues_comments_url(config)
    else:
        payload = {
            "body": (
                "General review comment.\n\n"
                "No blocking issues were found."
            ),
            "event": "COMMENT",
        }
        url = reviews_url(config)
    response = requests.post(url, headers=make_headers(config), json=payload)
    print_response(response)


def submit_request_changes(config: ForgeConfig, forge: Forge, mode: ReviewMode):
    line_number, side, comment_body = prompt_request_changes_input()

    commit_id = get_pr_head_commit(config)

    position = get_diff_position(config, forge, REVIEW_FILE, line_number, side)
    if position is None:
        print(f"ERROR: line {line_number} (side={side}) not found in the diff for '{REVIEW_FILE}'.")
        print("Verify the line is part of the PR diff and that the side matches the line type.")
        return

    print(f"\nResolved line {line_number} ({side}) → anchor value {position}")

    if forge == Forge.GITHUB and mode == ReviewMode.COMMENT:
        # General comment
        general_payload = {"body": "Please address the inline comments before this PR can be merged."}
        general_url = issues_comments_url(config)
        resp = requests.post(general_url, headers=make_headers(config), json=general_payload)
        print_response(resp)
        
        # Inline comment
        inline_comment = build_inline_comment(forge, position, side, comment_body)
        inline_payload = {**inline_comment, "commit_id": commit_id}
        inline_url = pulls_comments_url(config)
        resp = requests.post(inline_url, headers=make_headers(config), json=inline_payload)
        print_response(resp)
    else:
        payload = {
            "commit_id": commit_id,
            "body": "Please address the inline comments before this PR can be merged.",
            "event": "REQUEST_CHANGES",
            "comments": [build_inline_comment(forge, position, side, comment_body)],
        }

        response = requests.post(reviews_url(config), headers=make_headers(config), json=payload)
        print_response(response)


# =========================
# OUTPUT
# =========================

def print_response(response: requests.Response):
    print("\nStatus:", response.status_code)
    try:
        data = response.json()
    except Exception:
        print(response.text)
        return

    if response.ok:
        print("Review submitted successfully.")
        print("Review ID:", data.get("id"))
        print("State:", data.get("state"))
    else:
        print("Forge returned an error:")
        print(data)


# =========================
# ENTRYPOINT
# =========================

def select_forge() -> Forge:
    print("\nSelect forge:")
    print("1. GitHub")
    print("2. Codeberg")

    choice = input("\nForge: ").strip()

    if choice == "1":
        return Forge.GITHUB
    if choice == "2":
        return Forge.CODEBERG

    print("Invalid choice.")
    sys.exit(1)


def main():
    forge = select_forge()
    
    mode = ReviewMode.FORMAL  # Default for Codeberg
    if forge == Forge.GITHUB:
        print("\n-- GitHub Review Mode --")
        print("1. Formal Review (Forces PR state change: Approved/Changes Requested)")
        print("2. Just Comments (No state change, posts as standard PR comments)")
        
        mode_choice = input("\nMode [1/2]: ").strip()
        if mode_choice == "2":
            mode = ReviewMode.COMMENT
        else:
            mode = ReviewMode.FORMAL

    token = resolve_token(forge)
    config = build_forge_config(forge, token)

    print(f"\nPR Review Demo [{forge.value}] | Mode: {mode.value}")
    print("---------------------")
    print("1. Approve")
    print("2. Comment")
    print("3. Request Changes")

    choice = input("\nAction: ").strip()

    if choice == "1":
        submit_approval(config, mode)
    elif choice == "2":
        submit_comment_review(config, mode)
    elif choice == "3":
        submit_request_changes(config, forge, mode)
    else:
        print("Invalid option.")


if __name__ == "__main__":
    main()
