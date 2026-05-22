#!/usr/bin/env bash
# check-token.sh - diagnostic for FORGEJO_TOKEN and repo discovery
set -euo pipefail

CONFIG_FILE="${HOME}/.config/pr-auto-reviewer/config"
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: Config not found at $CONFIG_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

FORGEJO_HOST="${FORGEJO_HOST:-https://codeberg.org}"
FORGEJO_TOKEN="${FORGEJO_TOKEN:-}"
API_BASE="${FORGEJO_HOST}/api/v1"

if [[ -z "$FORGEJO_TOKEN" ]]; then
  echo "ERROR: FORGEJO_TOKEN is empty in $CONFIG_FILE"
  exit 1
fi

echo "Checking FORGEJO_HOST: $FORGEJO_HOST"

echo "Calling ${API_BASE}/user ..."
user_file=$(mktemp)
user_code=$(curl -sS -H "Authorization: token ${FORGEJO_TOKEN}" "${API_BASE}/user" -o "$user_file" -w "%{http_code}" 2>/dev/null || true)
user_body=$(cat "$user_file" 2>/dev/null || true)
rm -f "$user_file"

echo "HTTP /user: ${user_code}"
if [[ "$user_code" -ne 200 ]]; then
  echo "Body: ${user_body}"
  echo "\nDiagnosis: Authentication failed for FORGEJO_TOKEN (HTTP ${user_code})."
  echo "Actions:"
  echo "  - Verify FORGEJO_TOKEN in $CONFIG_FILE is correct and not expired."
  echo "  - Ensure token has required scopes: \`repo\` and \`read:user\` (Codeberg/Forgejo)."
  echo "  - If self-hosted Forgejo, confirm FORGEJO_HOST is the correct URL and reachable from this host."
  exit 2
fi

# Parse username
username=$(printf '%s' "$user_body" | python3 - <<'PY'
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('login') or data.get('username') or '')
except Exception:
    print('')
PY
)

if [[ -z "$username" ]]; then
  echo "WARNING: /user returned 200 but no username found. Body:\n${user_body}" 
else
  echo "Authenticated username: ${username}"
fi

echo "\nCalling ${API_BASE}/user/repos?limit=50 ..."
repos_file=$(mktemp)
repos_code=$(curl -sS -H "Authorization: token ${FORGEJO_TOKEN}" "${API_BASE}/user/repos?limit=50" -o "$repos_file" -w "%{http_code}" 2>/dev/null || true)
repos_body=$(cat "$repos_file" 2>/dev/null || true)
rm -f "$repos_file"

echo "HTTP /user/repos: ${repos_code}"
if [[ "$repos_code" -ne 200 ]]; then
  echo "Body: ${repos_body}"
  echo "\nDiagnosis: Failed to list repos (HTTP ${repos_code}). If 401, token/auth issue."
  exit 3
fi

# Count repos and show up to 20
count=$(printf '%s' "$repos_body" | python3 - <<'PY'
import sys, json
try:
    data = json.load(sys.stdin)
    repos = data if isinstance(data, list) else data.get('data', [])
    print(len(repos))
except Exception:
    print(0)
PY
)

echo "Total repos returned: ${count}"

printf '%s' "$repos_body" | python3 - <<'PY'
import sys, json
try:
    data = json.load(sys.stdin)
    repos = data if isinstance(data, list) else data.get('data', [])
    for r in repos[:20]:
        full = r.get('full_name') or r.get('path') or ''
        owner = r.get('owner',{})
        owner_login = owner.get('login') or owner.get('username') or ''
        print(f"- {full} (owner: {owner_login})")
except Exception as e:
    print('Could not parse repo list')
PY

echo "\nDone. If token returned 401, regenerate token with required scopes and update $CONFIG_FILE, then reload service: systemctl --user restart pr-auto-reviewer.service"
