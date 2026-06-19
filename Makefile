.PHONY: help install start stop status restart logs test clean reset issues list-items bootstrap review review-force daemon daemon-once capture-fixture

SHELL := /usr/bin/bash
SCRIPT_DIR := scripts

.DEFAULT_GOAL := help

# ── help ────────────────────────────────────────────────────────────────────

help:
	@echo "$$(tput bold)PR Auto Reviewer — Makefile targets$$(tput sgr0)"
	@echo ""
	@echo "  make install          Install and configure the systemd service"
	@echo "  make start            Start the daemon"
	@echo "  make stop             Stop the daemon"
	@echo "  make status           Show daemon status"
	@echo "  make restart          Restart the daemon"
	@echo "  make logs             Show daemon logs (follow)"
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

# ── service management ──────────────────────────────────────────────────────

install:
	@bash $(SCRIPT_DIR)/install-service.sh

start:
	@bash $(SCRIPT_DIR)/start.sh

stop:
	@bash $(SCRIPT_DIR)/stop.sh

status:
	@bash $(SCRIPT_DIR)/status.sh

restart:
	@bash $(SCRIPT_DIR)/restart.sh

logs:
	@bash $(SCRIPT_DIR)/logs.sh

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
