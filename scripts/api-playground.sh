#!/usr/bin/env bash
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

JQ_AVAILABLE=true
command -v jq >/dev/null 2>&1 || { JQ_AVAILABLE=false; echo "Warning: jq not found" >&2; }

json_pretty() { if $JQ_AVAILABLE; then echo "$1" | jq . 2>/dev/null || echo "$1"; else echo "$1"; fi; }
json_field()  { if $JQ_AVAILABLE; then echo "$1" | jq -r "$2" 2>/dev/null || echo ""; else echo ""; fi; }
json_escape() { if $JQ_AVAILABLE; then jq -Rs . <<< "$1"; else printf '"%s"' "${1//\"/\\\"}"; fi; }

read_body() {
    local tmpfile
    tmpfile=$(mktemp /tmp/api-playground.XXXXXX 2>/dev/null || mktemp 2>/dev/null) || die "Cannot create temp file"
    if [[ -n "${EDITOR:-}" ]]; then "$EDITOR" "$tmpfile"; else echo "(Enter body, Ctrl+D)"; cat > "$tmpfile"; fi
    local content; content=$(<"$tmpfile"); rm -f "$tmpfile"; echo "$content"
}

_load_dotenv() {
    local dotenv_path="${1:-.env}"
    [[ -f "$dotenv_path" ]] || return 0
    while IFS='=' read -r key value; do
        key="${key##*( )}"; key="${key%%*( )}"
        [[ -z "$key" || "$key" == \#* ]] && continue
        value="${value##*( )}"; value="${value%%*( )}"
        export "$key=$value"
    done < "$dotenv_path"
}

_resolve() {
    local env_var="$1" label="$2"
    local val="${!env_var:-}"

    if [[ -n "$val" ]]; then
        echo "  $label: using \$$env_var from environment" >&2
        printf '%s' "$val"
        return
    fi

    _load_dotenv "$SCRIPT_DIR/.env"
    _load_dotenv "$HOME/.config/pr-auto-reviewer/config"

    val="${!env_var:-}"
    if [[ -n "$val" ]]; then
        echo "  $label: using \$$env_var from config file" >&2
        printf '%s' "$val"
        return
    fi

    read -r -p "  $label (\$$env_var): " val
    printf '%s' "${val:-}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

API_BASE=""
TOKEN=""
OWNER_TOKEN=""
API_RESPONSE_BODY=""
API_RESPONSE_STATUS=""

call_api() {
    local method="$1" path="$2"; shift 2
    local body=""; local extra_headers=()
    [[ $# -gt 0 ]] && { body="$1"; shift; }
    extra_headers=("$@")

    local url="${API_BASE}${path}"
    local masked_token="${TOKEN: -4}"
    local auth_scheme="Bearer"
    local auth_header="Authorization: Bearer $TOKEN"

    if [[ "$PLATFORM_MODE" == "forgejo" ]]; then
        auth_scheme="token"
        auth_header="Authorization: token $TOKEN"
    fi

    echo "=== REQUEST ==="
    echo "URL: $method $url"
    echo "  Authorization: $auth_scheme ***${masked_token}"

    local curl_args=(-s -L -X "$method" -H "$auth_header" -H "User-Agent: api-playground")
    for h in "${extra_headers[@]}"; do
        curl_args+=(-H "$h")
        echo "  ${h%%:*}: ${h#*: }"
    done

    if [[ -n "$body" ]]; then
        curl_args+=(-H "Content-Type: application/json" -d "$body")
        echo "Body:"; json_pretty "$body"
    fi

    echo "--- curl ---"
    set -x
    local resp_file
    resp_file=$(mktemp /tmp/api-playground.XXXXXX 2>/dev/null || mktemp 2>/dev/null)
    API_RESPONSE_STATUS=$(curl "${curl_args[@]}" -w "%{http_code}" -o "$resp_file" "$url" 2>/dev/null)
    API_RESPONSE_BODY=$(<"$resp_file")
    rm -f "$resp_file"
    { set +x; } 2>/dev/null

    echo; echo "=== RESPONSE ==="
    echo "Status: $API_RESPONSE_STATUS"
    json_pretty "$API_RESPONSE_BODY"
    echo
}

echo "=== API Playground ==="
echo

PLATFORM_MODE="${PLATFORM_MODE:-}"
if [[ -z "$PLATFORM_MODE" ]]; then
    echo "Select platform:"
    PS3="Platform (number): "
    select _p in "GitHub  (https://api.github.com)" "Codeberg (https://codeberg.org/api/v1)"; do
        case $_p in
            *GitHub*) PLATFORM_MODE="github"; API_BASE="https://api.github.com"; break;;
            *Codeberg*) PLATFORM_MODE="forgejo"; API_BASE="https://codeberg.org/api/v1"; break;;
        esac
        echo "Invalid selection"
    done
elif [[ "$PLATFORM_MODE" == "github" ]]; then
    API_BASE="https://api.github.com"
    echo "Platform: GitHub (from PLATFORM_MODE env)"
elif [[ "$PLATFORM_MODE" == "forgejo" ]]; then
    API_BASE="https://codeberg.org/api/v1"
    echo "Platform: Codeberg (from PLATFORM_MODE env)"
else
    die "Unknown PLATFORM_MODE='$PLATFORM_MODE' — expected 'github' or 'forgejo'"
fi

echo
echo "Resolving:"

if [[ "$PLATFORM_MODE" == "github" ]]; then
    TOKEN=$(_resolve "GITHUB_OWNER_TOKEN" "Owner token")
    [[ -z "$TOKEN" ]] && die "GITHUB_OWNER_TOKEN is required"
    OWNER_TOKEN=$(_resolve "GITHUB_REVIEWER_TOKEN" "Reviewer token")
    [[ -z "$OWNER_TOKEN" ]] && OWNER_TOKEN="$TOKEN"
    REVIEWER_USERNAME=$(_resolve "GITHUB_REVIEWER_USERNAME" "Reviewer username")
    [[ -z "$REVIEWER_USERNAME" ]] && REVIEWER_USERNAME=$(_resolve "REVIEWER_USERNAME" "Reviewer username")
else
    TOKEN=$(_resolve "FORGEJO_OWNER_TOKEN" "Owner token")
    [[ -z "$TOKEN" ]] && die "FORGEJO_OWNER_TOKEN is required"
    OWNER_TOKEN=$(_resolve "FORGEJO_REVIEWER_TOKEN" "Reviewer token")
    [[ -z "$OWNER_TOKEN" ]] && OWNER_TOKEN="$TOKEN"
    REVIEWER_USERNAME=$(_resolve "FORGEJO_REVIEWER_USERNAME" "Reviewer username")
    [[ -z "$REVIEWER_USERNAME" ]] && REVIEWER_USERNAME=$(_resolve "REVIEWER_USERNAME" "Reviewer username")
fi

REPO=$(_resolve "REPO" "Repository")

echo
echo " Configuration:"
echo "  Platform: $PLATFORM_MODE"
echo "  API URL:  $API_BASE"
echo "  Repo:     ${REPO:-<none set>}"
echo "  Reviewer: ${REVIEWER_USERNAME:-<none set>}"
echo

while true; do
    echo "=== Actions ==="
    PS3="Action (number): "
    select _action in \
        "List repos" "List open PRs" "Get PR" "Get PR diff" \
        "Get file contents" "Get repo tree" "List PR comments" \
        "Post PR comment" "Get PR reviews" "Submit PR review" \
        "Request reviewer" "Create issue" "Get PR commits" "Exit"
    do
        case $_action in
            "Exit") exit 0;;

            "List repos")
                call_api "GET" "/user/repos?per_page=100&type=all&sort=updated"; break;;

            "List open PRs")
                call_api "GET" "/repos/$REPO/pulls?state=open&limit=20"; break;;

            "Get PR")
                read -r -p "PR number: " _pr_num
                call_api "GET" "/repos/$REPO/pulls/$_pr_num"; break;;

            "Get PR diff")
                read -r -p "PR number: " _pr_num
                if [[ "$PLATFORM_MODE" == "github" ]]; then
                    call_api "GET" "/repos/$REPO/pulls/$_pr_num.diff" "" "Accept: application/vnd.github.diff"
                else
                    call_api "GET" "/repos/$REPO/pulls/$_pr_num.diff"
                fi
                break;;

            "Get file contents")
                read -r -p "File path: " _fp
                read -r -p "Commit SHA [main]: " _sha; _sha="${_sha:-main}"
                if [[ "$PLATFORM_MODE" == "github" ]]; then
                    call_api "GET" "/repos/$REPO/contents/$_fp?ref=$_sha" "" "Accept: application/vnd.github.raw+json"
                else
                    call_api "GET" "/repos/$REPO/raw/$_sha/$_fp"
                fi
                break;;

            "Get repo tree")
                call_api "GET" "/repos/$REPO/git/trees/main?recursive=1"; break;;

            "List PR comments")
                read -r -p "PR number: " _pr_num
                call_api "GET" "/repos/$REPO/issues/$_pr_num/comments?limit=50"; break;;

            "Post PR comment")
                read -r -p "PR number: " _pr_num
                echo "Enter comment body:"; _body=$(read_body)
                _payload="{\"body\": $(json_escape "$_body")}"
                json_pretty "$_payload"
                (TOKEN="$OWNER_TOKEN"; call_api "POST" "/repos/$REPO/issues/$_pr_num/comments" "$_payload")
                break;;

            "Get PR reviews")
                read -r -p "PR number: " _pr_num
                call_api "GET" "/repos/$REPO/pulls/$_pr_num/reviews?limit=10"; break;;

            "Submit PR review")
                read -r -p "PR number: " _pr_num
                select _v in "APPROVE" "REQUEST_CHANGES" "COMMENT"; do
                    case $_v in APPROVE|REQUEST_CHANGES|COMMENT) break;; esac
                done
                echo "Enter review body:"; _rb=$(read_body)
                _payload="{\"event\": \"$_v\", \"body\": $(json_escape "$_rb")"
                _pr_resp=$(curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/repos/$REPO/pulls/$_pr_num" 2>/dev/null)
                _cid=$(json_field "$_pr_resp" '.head.sha')
                [[ -n "$_cid" ]] && _payload="${_payload}, \"commit_id\": \"$_cid\""
                [[ "$PLATFORM_MODE" == "forgejo" ]] && _payload="${_payload}, \"official\": true"
                _payload="${_payload}}"
                json_pretty "$_payload"
                call_api "POST" "/repos/$REPO/pulls/$_pr_num/reviews" "$_payload"
                break;;

            "Request reviewer")
                read -r -p "PR number: " _pr_num
                _un="${REVIEWER_USERNAME}"
                read -r -p "Reviewer username [$_un]: " _in; _un="${_in:-$_un}"
                [[ -z "$_un" ]] && { echo "No username, cancelled"; break; }
                _payload="{\"reviewers\": [$(json_escape "$_un")]}"
                json_pretty "$_payload"
                (TOKEN="$OWNER_TOKEN"; call_api "POST" "/repos/$REPO/pulls/$_pr_num/requested_reviewers" "$_payload")
                break;;

            "Create issue")
                read -r -p "Title: " _ti; [[ -z "$_ti" ]] && { echo "No title, cancelled"; break; }
                echo "Enter issue body:"; _ib=$(read_body)
                _payload="{\"title\": $(json_escape "$_ti"), \"body\": $(json_escape "$_ib")}"
                json_pretty "$_payload"
                call_api "POST" "/repos/$REPO/issues" "$_payload"
                break;;

            "Get PR commits")
                read -r -p "PR number: " _pr_num
                call_api "GET" "/repos/$REPO/pulls/$_pr_num/commits?limit=30"; break;;

            *) echo "Invalid selection";;
        esac
    done
done
