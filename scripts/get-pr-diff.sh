#!/usr/bin/env bash
# Script to fetch PR diff from Codeberg

source .env

repo="${1:-gbrennon/gb-ollama-container}"
pr="${2:-18}"

diff=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
  "https://codeberg.org/api/v1/repos/${repo}/pulls/${pr}.diff" 2>/dev/null)

if [ -z "$diff" ]; then
  echo "Failed to fetch diff" >&2
  exit 1
fi

echo "$diff"