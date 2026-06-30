.PHONY: help install start stop status restart test clean reset issues list-items bootstrap review review-force daemon daemon-once capture-fixture

SHELL := /usr/bin/bash
SCRIPT_DIR := scripts

.DEFAULT_GOAL := help

# ── help ────────────────────────────────────────────────────────────────────

help:
	@echo "$$(tput bold)PR Auto Reviewer — Makefile targets$$(tput sgr0)"
	@echo ""
	@echo "  make install          Install and configure the systemd service"
	@echo "  make start            Start the daemon in background"
	@echo "  make stop             Stop the daemon"
	@echo "  make status           Check if daemon is running"
	@echo "  make restart          Restart the daemon"
	@echo ""
	@echo "Service management (systemd):"
	@echo "  systemctl --user start   pr-auto-reviewer.service"
	@echo "  systemctl --user stop    pr-auto-reviewer.service"
	@echo "  systemctl --user status  pr-auto-reviewer.service"
	@echo "  systemctl --user restart pr-auto-reviewer.service"
	@echo "  journalctl --user -u pr-auto-reviewer.service -f"
	@echo ""
	@echo "  make bootstrap        Bootstrap the application (install deps, check env)"
	@echo "  make test             Run all tests (uv run pytest)"
	@echo ""
	@echo "  make clean [reset]    Reset reviewed-PR tracking state"
	@echo "  make review [force]   Force-review a specific PR"
	@echo "                        \$$ make review REPO=owner/repo PR=42"
	@echo "  make daemon-once      Poll all repos once, reviewing any open PRs"
	@echo "  make daemon           Poll continuously (daemon mode)"
	@echo ""
	@echo "  make list-items       List review items from a PR"
	@echo "                        \$$ make list-items REPO=owner/repo PR=8"
	@echo "  make issues           Create issues from PR commands"
	@echo "                        \$$ make issues REPO=owner/repo PR=8"
	@echo ""
	@echo "  make capture-fixture  Capture Ollama response fixtures"
	@echo "                        \$$ make capture-fixture REPO=owner/repo PR=8"

# ── production install ───────────────────────────────────────────────────────

install:
	@bash $(SCRIPT_DIR)/install-service.sh

# ── dev-mode service management ──────────────────────────────────────────────

PIDFILE := /tmp/pr-auto-reviewer.pid

start:
	@nohup python -m pr_auto_reviewer watch-prs > /tmp/pr-auto-reviewer.log 2>&1 & echo $$! > $(PIDFILE); \
	echo "Daemon started (pid $$(cat $(PIDFILE))); log: /tmp/pr-auto-reviewer.log"

stop:
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

status:
	@pid=$$(cat $(PIDFILE) 2>/dev/null); \
	if [ -n "$$pid" ] && kill -0 $$pid 2>/dev/null; then \
		echo "Daemon running (pid $$pid)"; \
	elif pid=$$(pgrep -f "python.*pr_auto_reviewer watch-prs" 2>/dev/null | head -1) && [ -n "$$pid" ]; then \
		echo "Daemon running (pid $$pid)"; \
	else \
		echo "Daemon not running"; \
	fi

restart: stop start

# ── development ─────────────────────────────────────────────────────────────

bootstrap:
	@bash $(SCRIPT_DIR)/bootstrap.sh

test:
	uv run pytest

# ── operations ──────────────────────────────────────────────────────────────

clean reset:
	@python -m pr_auto_reviewer clean

review review-force:
	@python -m pr_auto_reviewer review --repo $(REPO) --pr $(PR) --force

daemon-once:
	@python -m pr_auto_reviewer watch-prs --once

daemon:
	@python -m pr_auto_reviewer watch-prs

# ── issue commands ──────────────────────────────────────────────────────────

issues:
	@bash $(SCRIPT_DIR)/create-issues-from-pr.sh

list-items:
	@python -m pr_auto_reviewer list-items --repo $(REPO) --pr $(PR)

# ── fixtures ────────────────────────────────────────────────────────────────

capture-fixture:
	@bash $(SCRIPT_DIR)/capture-fixture.sh -r $(REPO) -p $(PR)
