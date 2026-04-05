#!/usr/bin/env bash
# ollama-client.sh — Ollama API wrapper for code review.

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"

# Resolve Ollama host - always try localhost first for local development
resolve_ollama_host() {
  # First try localhost (works with docker and podman when Ollama runs locally)
  if curl -sf "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "http://localhost:11434"
    return
  fi
  
  # Then try host.containers.internal (podman on macOS)
  if curl -sf "http://host.containers.internal:11434/api/tags" >/dev/null 2>&1; then
    echo "http://host.containers.internal:11434"
    return
  fi
  
  # Use env value if set and working
  if [[ -n "$OLLAMA_HOST" ]]; then
    if curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
      echo "$OLLAMA_HOST"
      return
    fi
  fi
  
  echo ""
}

# Check if Ollama is available
ollama_available() {
  local host
  host=$(resolve_ollama_host)
  [[ -n "$host" ]] && curl -sf "${host}/api/tags" >/dev/null 2>&1
}

# Generate completion
ollama_generate() {
  local prompt="$1"
  local model="${2:-$OLLAMA_MODEL}"
  
  local host
  host=$(resolve_ollama_host)
  
  if [[ -z "$host" ]]; then
    echo '{"error": "Ollama not available"}'
    return 1
  fi
  
  curl -sf -X POST "${host}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${model}\",
      \"prompt\": \"${prompt}\",
      \"stream\": false
    }"
}

# Generate review for a diff
ollama_review() {
  local diff="$1"
  
  local review_prompt="You are a code reviewer. Review the following git diff and provide constructive feedback. Focus on bugs, security issues, code quality, and potential improvements. Output in JSON format:

{
  \"issues\": [
    {\"line\": \"10\", \"severity\": \"high\", \"description\": \"issue description\"}
  ],
  \"suggestions\": [
    {\"line\": \"15\", \"description\": \"suggestion\"}
  ],
  \"summary\": \"one sentence overall assessment\"
}

DIFF:
${diff}"

  local response
  response=$(ollama_generate "$review_prompt")
  
  # Extract response field
  echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null || true
}