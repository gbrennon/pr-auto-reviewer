#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

OWNER="" REPO="" PR=""
OWNER_TOKEN=""  OWNER_TOKEN_VAR=""
REVIEWER_TOKEN=""  REVIEWER_TOKEN_VAR=""
REVIEWER_USERNAME=""
VERDICT="COMMENT"
BODY="Automated review from pr-auto-reviewer verification script."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner) OWNER="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    --owner-token)
      if [[ "$2" == '$'* ]]; then
        OWNER_TOKEN_VAR="${2:1}"
        OWNER_TOKEN="${!OWNER_TOKEN_VAR:-}"
      else
        OWNER_TOKEN="$2"
        OWNER_TOKEN_VAR="--owner-token"
      fi
      shift 2 ;;
    --reviewer-token)
      if [[ "$2" == '$'* ]]; then
        REVIEWER_TOKEN_VAR="${2:1}"
        REVIEWER_TOKEN="${!REVIEWER_TOKEN_VAR:-}"
      else
        REVIEWER_TOKEN="$2"
        REVIEWER_TOKEN_VAR="--reviewer-token"
      fi
      shift 2 ;;
    --reviewer-username) REVIEWER_USERNAME="$2"; shift 2 ;;
    --verdict) VERDICT="$2"; shift 2 ;;
    --body) BODY="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

missing=()
[[ -z "$OWNER" ]] && missing+=("--owner")
[[ -z "$REPO" ]] && missing+=("--repo")
[[ -z "$PR" ]] && missing+=("--pr")
[[ -z "$OWNER_TOKEN" ]] && missing+=("--owner-token \$GITHUB_OWNER_TOKEN")
[[ -z "$REVIEWER_TOKEN" ]] && missing+=("--reviewer-token \$GITHUB_REVIEWER_TOKEN")
[[ -z "$REVIEWER_USERNAME" ]] && missing+=("--reviewer-username")
if [[ ${#missing[@]} -gt 0 ]]; then
  echo -e "${RED}ERROR: missing required args: ${missing[*]}${NC}" >&2
  echo "Usage: $0 --owner O --repo R --pr N --owner-token \$GITHUB_OWNER_TOKEN --reviewer-token \$GITHUB_REVIEWER_TOKEN --reviewer-username U" >&2
  exit 1
fi

API_BASE="https://api.github.com"
REVIEWERS_URL="${API_BASE}/repos/${OWNER}/${REPO}/pulls/${PR}/requested_reviewers"
REVIEWS_URL="${API_BASE}/repos/${OWNER}/${REPO}/pulls/${PR}/reviews"

log_section() { printf "\n${BOLD}${CYAN}%s${NC}\n" "══════════ $1 ══════════" >&2; }
log_info()    { printf "${GREEN}[INFO]${NC}  %s\n" "$1" >&2; }
log_warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$1" >&2; }
log_error()   { printf "${RED}[ERROR]${NC} %s\n" "$1" >&2; }

log_body() {
  printf "${CYAN}[BODY:%s]${NC}\n" "$1" >&2
  printf '%s\n' "$2" | python3 -m json.tool 2>/dev/null || printf '%s\n' "$2"
  printf '\n' >&2
}

log_response() {
  printf "${CYAN}[RESP]${NC} HTTP %s\n" "$1" >&2
  if [[ -n "${2:-}" ]]; then
    printf '%s\n' "$2" | python3 -m json.tool 2>/dev/null || printf '%s\n' "$2"
  fi
  printf '\n' >&2
}

_do_curl() {
  local method="$1" url="$2" token="$3" data="$4" token_label="$5"
  local tmp_body http_code body
  tmp_body="$(mktemp)"

  printf "${CYAN}[CURL]${NC}  curl -X %s\n" "$method" >&2
  printf "        -H 'Accept: application/vnd.github+json'\n" >&2
  printf "        -H 'Authorization: Bearer %s'\n" "\$${token_label}" >&2
  printf "        -H 'X-GitHub-Api-Version: 2022-11-28'\n" >&2
  printf "        '%s'\n" "$url" >&2
  printf "        -d '%s'\n" "$data" >&2
  printf "\n" >&2

  http_code=$(curl -s -o "$tmp_body" -w "%{http_code}" \
    -X "$method" \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${token}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -H "Content-Type: application/json" \
    -d "$data" \
    "$url" 2>&1)

  body="$(cat "$tmp_body")"
  log_response "$http_code" "$body"
  rm -f "$tmp_body"
  printf "%s\n%s\n" "$http_code" "$body"
}

log_section "STEP 1 — Request reviewer (owner token: \$$OWNER_TOKEN_VAR)"
log_info "Uses GITHUB_OWNER_TOKEN (requires write/push access)"
log_info "POST ${REVIEWERS_URL}"

REQ_BODY="{\"reviewers\":[\"${REVIEWER_USERNAME}\"]}"
log_body "request" "$REQ_BODY"

REQ_RESP="$(_do_curl POST "$REVIEWERS_URL" "$OWNER_TOKEN" "$REQ_BODY" "${OWNER_TOKEN_VAR}")"
REQ_CODE="$(echo "$REQ_RESP" | head -1)"

case "$REQ_CODE" in
  201) log_info "✓ Reviewer request succeeded (HTTP 201)" ;;
  422) log_warn "✗ 422 — reviewer already requested or no write access" ;;
  *)   log_warn "✗ HTTP ${REQ_CODE}" ;;
esac

log_section "STEP 2 — Submit formal review (reviewer token: \$$REVIEWER_TOKEN_VAR)"
log_info "Uses GITHUB_REVIEWER_TOKEN (reviewer authors the review)"
log_info "Verdict: ${VERDICT}"
log_info "POST ${REVIEWS_URL}"

REV_BODY="{\"event\":\"${VERDICT}\",\"body\":\"${BODY}\"}"
log_body "review" "$REV_BODY"

REV_RESP="$(_do_curl POST "$REVIEWS_URL" "$REVIEWER_TOKEN" "$REV_BODY" "${REVIEWER_TOKEN_VAR}")"
REV_CODE="$(echo "$REV_RESP" | head -1)"
REV_JSON="$(echo "$REV_RESP" | tail -n +2)"

case "$REV_CODE" in
  200|201)
    log_info "✓ Review submitted (HTTP ${REV_CODE})"
    RID="$(echo "$REV_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || true)"
    RURL="$(echo "$REV_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('html_url',''))" 2>/dev/null || true)"
    [[ -n "$RID" ]]  && log_info "Review ID:  ${RID}"
    [[ -n "$RURL" ]] && log_info "Review URL: ${RURL}"
    ;;
  403)
    log_error "✗ 403 Forbidden — check GITHUB_REVIEWER_TOKEN has 'repo' scope and write access"
    ;;
  422)
    log_error "✗ 422 Unprocessable — check event field (APPROVE|REQUEST_CHANGES|COMMENT)"
    ;;
  *) log_warn "✗ HTTP ${REV_CODE}" ;;
esac

log_section "STEP 3 — Review with commit_id (reviewer token: \$$REVIEWER_TOKEN_VAR)"
log_info "Fetching PR head SHA..."

PR_URL="${API_BASE}/repos/${OWNER}/${REPO}/pulls/${PR}"
PR_RESP="$(_do_curl GET "$PR_URL" "$OWNER_TOKEN" '{}' "${OWNER_TOKEN_VAR}")"
PR_CODE="$(echo "$PR_RESP" | head -1)"
PR_JSON="$(echo "$PR_RESP" | tail -n +2)"

if [[ "$PR_CODE" == "200" ]]; then
  SHA="$(echo "$PR_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['head']['sha'])" 2>/dev/null || true)"
  log_info "PR head SHA: ${SHA}"
  SHA_BODY="{\"event\":\"${VERDICT}\",\"body\":\"${BODY}\",\"commit_id\":\"${SHA}\"}"
  log_body "review+commit" "$SHA_BODY"
  SHA_RESP="$(_do_curl POST "$REVIEWS_URL" "$REVIEWER_TOKEN" "$SHA_BODY" "${REVIEWER_TOKEN_VAR}")"
  SHA_CODE="$(echo "$SHA_RESP" | head -1)"
  case "$SHA_CODE" in
    200|201) log_info "✓ Review with commit_id submitted (HTTP ${SHA_CODE})" ;;
    *)       log_warn "HTTP ${SHA_CODE}" ;;
  esac
else
  log_warn "Could not fetch PR info (HTTP ${PR_CODE}) — skipping"
fi

log_section "DONE"
echo -e "${GREEN}Verification complete. All curl calls and responses logged above.${NC}" >&2
