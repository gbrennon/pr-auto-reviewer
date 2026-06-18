import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =========================
# CONFIGURATION
# =========================
OWNER = "gbrennon"
REPO = "dotfiles"
PR_NUMBER = 46
TOKEN = os.environ.get("FORGEJO_REVIEWER_TOKEN")

BASE_URL = "https://codeberg.org/api/v1"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def select_verdict() -> str:
    """Prompt the user to select a verdict for the review."""
    print("\nSelect the verdict to force:")
    print("1. Approve (APPROVED)")
    print("2. Request Changes (REQUEST_CHANGES)")
    print("3. Comment (COMMENT)")
    
    while True:
        choice = input("\nChoice [1/2/3]: ").strip()
        if choice == "1":
            return "APPROVED"
        if choice == "2":
            return "REQUEST_CHANGES"
        if choice == "3":
            return "COMMENT"
        print("Invalid choice. Please enter 1, 2, or 3.")

def verify_formal_review():
    if not TOKEN:
        print("ERROR: FORGEJO_REVIEWER_TOKEN environment variable is not set.")
        print("Please ensure it is defined in your .env file.")
        sys.exit(1)

    print(f"--- Verifying Formal Review for Codeberg PR #{PR_NUMBER} ---")

    # 1. Get the current head commit SHA
    pull_url = f"{BASE_URL}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
    print(f"Fetching PR info from {pull_url}...")
    pr_resp = requests.get(pull_url, headers=HEADERS)
    pr_resp.raise_for_status()
    head_sha = pr_resp.json()["head"]["sha"]
    print(f"Head SHA: {head_sha}")

    # 2. User selects the verdict
    verdict = select_verdict()
    print(f"Selected Verdict: {verdict}")

    # 3. Submit the Review
    review_url = f"{BASE_URL}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews"
    payload = {
        "event": verdict,
        "body": f"Verification: Force-sending a {verdict} review to verify the fix.",
        "official": True,
        "commit_id": head_sha
    }
    
    print(f"Sending review to {review_url}...")
    print(f"Payload: {payload}")
    
    review_resp = requests.post(review_url, headers=HEADERS, json=payload)
    
    if review_resp.ok:
        data = review_resp.json()
        print("\nSUCCESS: Review submitted.")
        print(f"Review ID: {data.get('id')}")
        print(f"State: {data.get('state')}")
        print(f"Official: {data.get('official')}")
        print(f"URL: {data.get('html_url')}")
        print("\nCheck the PR page to verify the status change.")
    else:
        print("\nFAILED to submit review:")
        print(f"Status: {review_resp.status_code}")
        print(f"Response: {review_resp.text}")

if __name__ == "__main__":
    verify_formal_review()
