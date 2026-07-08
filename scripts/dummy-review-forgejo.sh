#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m' GREEN='\033[0;32m' CYAN='\033[0;36m' YELLOW='\033[0;33m' BOLD='\033[1m' NC='\033[0m'

log_step()  { printf "\n${BOLD}${CYAN}=== %s ===${NC}\n" "$1" >&2; }
log_ok()    { printf "${GREEN}✓${NC}  %s\n" "$1" >&2; }
log_fail()  { printf "${RED}✗${NC}  %s\n" "$1" >&2; }
log_info()  { printf "${CYAN}→${NC}  %s\n" "$1" >&2; }
log_curl()  { printf "${YELLOW}curl${NC} %s\n" "$1" >&2; }

ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
  log_info "Loaded $ENV_FILE"
fi
CURL_TIMEOUT=15

API_BASE="${FORGEJO_API_URL:-${CODEBERG_API_URL:-https://codeberg.org/api/v1}}"

prompt() {
  local var_name="$1" label="$2"
  local val="${!var_name:-}"
  if [[ -n "$val" ]]; then
    log_info "$label: using \$$var_name from .env"
    printf '%s' "$val"
    return
  fi
  printf '%s' "${!var_name:-}" >/dev/null
  read -r -p "Enter $label ($var_name): " val 
  printf '%s' "$val"
}

log_step "Forgejo Dummy Review"

REPO="${REPO:-}"
if [[ -z "$REPO" ]]; then
  printf 'Repository (owner/repo): ' >&2
  read -r REPO 
fi
[[ -z "$REPO" ]] && { log_fail "Repository is required"; exit 1; }

PR="${PR:-}"
if [[ -z "$PR" ]]; then
  printf 'PR number: ' >&2
  read -r PR 
fi
[[ -z "$PR" ]] && { log_fail "PR number is required"; exit 1; }

OWNER_TOKEN=$(prompt "FORGEJO_OWNER_TOKEN" "Owner token")
[[ -z "$OWNER_TOKEN" ]] && OWNER_TOKEN=$(prompt "CODEBERG_OWNER_TOKEN" "Owner token")
[[ -z "$OWNER_TOKEN" ]] && { log_fail "FORGEJO_OWNER_TOKEN or CODEBERG_OWNER_TOKEN is required"; exit 1; }

REVIEWER_TOKEN=$(prompt "FORGEJO_REVIEWER_TOKEN" "Reviewer token")
if [[ -z "$REVIEWER_TOKEN" ]]; then
  REVIEWER_TOKEN=$(prompt "CODEBERG_REVIEWER_TOKEN" "Reviewer token")
fi
if [[ -z "$REVIEWER_TOKEN" ]]; then
  log_info "No reviewer token — using owner token"
  REVIEWER_TOKEN="$OWNER_TOKEN"
fi

REVIEWER_USER="${FORGEJO_REVIEWER_USERNAME:-${CODEBERG_REVIEWER_USERNAME:-}}"
if [[ -z "$REVIEWER_USER" ]]; then
  printf 'Reviewer username: ' >&2
  read -r REVIEWER_USER 
fi
[[ -z "$REVIEWER_USER" ]] && REVIEWER_USER="gbrennon"

printf '\n' >&2
log_info "Configuration:"
log_info "  API:       $API_BASE"
log_info "  Repo:      $REPO"
log_info "  PR:        #$PR"
log_info "  Reviewer:  $REVIEWER_USER"
printf '\n' >&2

log_step "STEP 1 — Fetch PR"
log_curl "GET /repos/$REPO/pulls/$PR  (token: \$FORGEJO_OWNER_TOKEN)"
PR_RESP=$(curl -s --connect-timeout 5 --max-time "$CURL_TIMEOUT" \
  -o /dev/stdout -w "\n%{http_code}" \
  -H "Authorization: token $OWNER_TOKEN" \
  "$API_BASE/repos/$REPO/pulls/$PR" 2>&1) || true
PR_CODE=$(echo "$PR_RESP" | tail -1)
PR_BODY=$(echo "$PR_RESP" | head -n -1)
if [[ "$PR_CODE" == "200" ]]; then
  log_ok "PR found (200)"
  HEAD_SHA=$(echo "$PR_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin)['head']['sha'])" 2>/dev/null || echo "?")
  log_info "Head SHA: $HEAD_SHA"
else
  log_fail "PR fetch failed (HTTP $PR_CODE)"
  echo "$PR_BODY"
  exit 1
fi

log_step "STEP 2 — Request reviewer"
log_curl "POST /repos/$REPO/pulls/$PR/requested_reviewers  (token: \$FORGEJO_OWNER_TOKEN)"
REQ_RESP=$(curl -s --connect-timeout 5 --max-time "$CURL_TIMEOUT" \
  -o /dev/stdout -w "\n%{http_code}" \
  -X POST -H "Authorization: token $OWNER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"reviewers\":[\"$REVIEWER_USER\"]}" \
  "$API_BASE/repos/$REPO/pulls/$PR/requested_reviewers" 2>&1) || true
REQ_CODE=$(echo "$REQ_RESP" | tail -1)
REQ_BODY=$(echo "$REQ_RESP" | head -n -1)
case "$REQ_CODE" in
  201) log_ok "Reviewer requested (201)" ;;
  422) log_info "Already requested or self-review blocked (422 — non-fatal)" ;;
  403) log_fail "403 — FORGEJO_OWNER_TOKEN lacks write:repository scope" ;;
  *)   log_fail "HTTP $REQ_CODE" ; echo "$REQ_BODY" ;;
esac

log_step "STEP 3 — Submit review"
REVIEW_BODY="Dummy review from pr-auto-reviewer — API path verification."
event="COMMENT"
log_curl "POST /repos/$REPO/pulls/$PR/reviews  (token: \$FORGEJO_REVIEWER_TOKEN)"
log_info "Payload: body='...' event=$event commit_id=$HEAD_SHA"

REV_RESP=$(curl -s --connect-timeout 5 --max-time "$CURL_TIMEOUT" \
  -o /dev/stdout -w "\n%{http_code}" \
  -X POST -H "Authorization: token $REVIEWER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"body\":\"$REVIEW_BODY\",\"event\":\"$event\",\"commit_id\":\"$HEAD_SHA\"}" \
  "$API_BASE/repos/$REPO/pulls/$PR/reviews" 2>&1) || true
REV_CODE=$(echo "$REV_RESP" | tail -1)
REV_BODY=$(echo "$REV_RESP" | head -n -1)

case "$REV_CODE" in
  201|200)
    log_ok "Review submitted (HTTP $REV_CODE)"
    echo "$REV_BODY" | python3 -m json.tool 2>/dev/null
    RID=$(echo "$REV_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)
    [[ -n "$RID" ]] && log_info "Review ID: $RID"
    ;;
  401) log_fail "401 — Review token does not exist. Generate at https://codeberg.org/settings/applications" ;;
  403) log_fail "403 — Token lacks write:repository scope. Generate a new token." ;;
  422) log_fail "422" ; echo "$REV_BODY" ;;
  *)   log_fail "HTTP $REV_CODE" ; echo "$REV_BODY" ;;
esac

log_step "RESULT"
printf '\n' >&2
printf "${BOLD}Owner token${NC}  ($( [[ -n "${FORGEJO_OWNER_TOKEN:-}${CODEBERG_OWNER_TOKEN:-}" ]] && echo 'from .env' || echo 'entered'))\n" >&2
printf "  READ PR:          $( [[ "$PR_CODE" == "200" ]] && printf "${GREEN}OK${NC}" || printf "${RED}FAIL ($PR_CODE)${NC}" )\n" >&2
printf "  REQUEST REVIEWER: $( [[ "$REQ_CODE" == 20* || "$REQ_CODE" == 422 ]] && printf "${GREEN}OK${NC}" || printf "${RED}FAIL ($REQ_CODE)${NC}" )\n" >&2
printf "${BOLD}Review token${NC} ($( [[ -n "${FORGEJO_REVIEWER_TOKEN:-}${CODEBERG_REVIEWER_TOKEN:-}" ]] && echo 'from .env' || echo 'entered'))\n" >&2
printf "  SUBMIT REVIEW:    $( [[ "$REV_CODE" == 20* ]] && printf "${GREEN}OK${NC}" || printf "${RED}FAIL ($REV_CODE)${NC}" )\n" >&2
printf '\n' >&2
