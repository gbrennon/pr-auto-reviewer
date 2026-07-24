.PHONY: help install start stop status restart test clean reset issues list-items bootstrap review review-force daemon daemon-once capture-fixture

SHELL := /usr/bin/bash
SCRIPT_DIR := scripts

.DEFAULT_GOAL := help


help:  ## Show this help
	@grep -E '^[a-zA-Z_-][a-zA-Z_ -]*:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── production install ───────────────────────────────────────────────────────

install:  ## Install CLI globally (pr-auto-reviewer)
	@bash $(SCRIPT_DIR)/install-service.sh

# ── dev-mode service management ──────────────────────────────────────────────

PIDFILE := /tmp/pr-auto-reviewer.pid

start:  ## Start the PR reviewer daemon
	@nohup uv run python -m pr_auto_reviewer watch-prs > /tmp/pr-auto-reviewer.log 2>&1 & echo $$! > $(PIDFILE); \
	echo "Daemon started (pid $$(cat $(PIDFILE))); log: /tmp/pr-auto-reviewer.log"

stop:  ## Stop the PR reviewer daemon
	@pid=$$(cat $(PIDFILE) 2>/dev/null); \
	if [ -n "$$pid" ] && kill $$pid 2>/dev/null; then \
		rm -f $(PIDFILE); \
		echo "Daemon stopped (pid $$pid)"; \
	else \
		pid=$$(pgrep -f "python.*pr_auto_reviewer watch-prs" 2>/dev/null | head -1); \
		if [ -n "$$pid" ]; then \
			kill $$pid 2>/dev/null && echo "Daemon stopped (pid $$pid)"; \
		else \
			echo "Daemon not running"; \
		fi; \
	fi

status:  ## Show daemon status
	@pid=$$(cat $(PIDFILE) 2>/dev/null); \
	if [ -n "$$pid" ] && kill -0 $$pid 2>/dev/null; then \
		echo "Daemon running (pid $$pid)"; \
	elif pid=$$(pgrep -f "python.*pr_auto_reviewer watch-prs" 2>/dev/null | head -1) && [ -n "$$pid" ]; then \
		echo "Daemon running (pid $$pid)"; \
	else \
		echo "Daemon not running"; \
	fi

restart: stop start  ## Restart the daemon

# ── development ─────────────────────────────────────────────────────────────

bootstrap:  ## Bootstrap the project environment
	@bash $(SCRIPT_DIR)/bootstrap.sh

test:  ## Run tests
	uv run pytest

# ── operations ──────────────────────────────────────────────────────────────

clean reset:  ## Clean state files
	@uv run python -m pr_auto_reviewer clean

review:  ## Review a PR (REPO=owner/repo PR=N GITHUB_OWNER_TOKEN=... or FORGEJO_OWNER_TOKEN=...)
	@env REVIEW_OUTPUT="$(REVIEW_OUTPUT)" uv run python -m pr_auto_reviewer review --repo $(REPO) --pr $(PR)

review-force:  ## Force to review a PR (REPO=owner/repo PR=N GITHUB_OWNER_TOKEN=... or FORGEJO_OWNER_TOKEN=...)
	@env REVIEW_OUTPUT="$(REVIEW_OUTPUT)" uv run python -m pr_auto_reviewer review --repo $(REPO) --pr $(PR) --force


daemon-once:  ## Run the watcher once
	@uv run python -m pr_auto_reviewer watch-prs --once

daemon:  ## Run the watcher continuously
	@uv run python -m pr_auto_reviewer watch-prs

# ── issue commands ──────────────────────────────────────────────────────────

issues:  ## Create issues from PR comments
	@bash $(SCRIPT_DIR)/create-issues-from-pr.sh

list-items:  ## List review items (REPO=owner/repo PR=N)
	@uv run python -m pr_auto_reviewer list-items --repo $(REPO) --pr $(PR)

# ── fixtures ────────────────────────────────────────────────────────────────

capture-fixture:  ## Capture test fixtures (REPO=owner/repo PR=N)
	@bash $(SCRIPT_DIR)/capture-fixture.sh -r $(REPO) -p $(PR)
