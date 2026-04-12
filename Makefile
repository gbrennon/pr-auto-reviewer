.PHONY: help install start stop status restart logs watch test clean issues list-items

SHELL := /usr/bin/env bash
SCRIPT_DIR := scripts
REPO_ROOT := .

help:
	@echo "PR Auto Reviewer - Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install         Install and configure the service"
	@echo "  make start          Start the watcher service"
	@echo "  make stop           Stop the watcher service"
	@echo "  make status         Show service status"
	@echo "  make restart       Restart the service"
	@echo "  make logs          Show service logs (follow)"
	@echo "  make watch        Run watcher once (manual mode)"
	@echo "  make test         Run test on a repo"
	@echo "  make issues       Create issues from PR commands"
	@echo "  make list-items   List review items from PR"
	@echo "  make clean         Clean state files"
	@echo ""
	@echo "Examples:"
	@echo "  make test REPO=gbrennon/pr-auto-reviewer"
	@echo "  make issues REPO=owner/repo PR=8"
	@echo "  make list-items REPO=owner/repo PR=8"

install:
	@echo "Running install script..."
	@bash $(SCRIPT_DIR)/install-service.sh

start:
	@echo "Starting service..."
	@systemctl --user start pr-ai-auto-reviewer.service

stop:
	@echo "Stopping service..."
	@systemctl --user stop pr-ai-auto-reviewer.service

status:
	@systemctl --user status pr-ai-auto-reviewer.service || true

restart:
	@systemctl --user restart pr-ai-auto-reviewer.service || true

logs:
	@journalctl --user -u pr-ai-auto-reviewer.service --no-pager -f

watch:
	@bash $(SCRIPT_DIR)/watch-prs.sh --once

test:
ifndef REPO
	@echo "Usage: make test REPO=owner/repo"
	@exit 1
endif
	@bash $(SCRIPT_DIR)/watch-prs.sh -r $(REPO) --once

issues:
ifndef REPO
	@echo "Usage: make issues REPO=owner/repo PR=number"
	@exit 1
endif
ifndef PR
	@echo "Usage: make issues REPO=owner/repo PR=number"
	@exit 1
endif
	@bash $(SCRIPT_DIR)/create-issues-from-pr.sh $(REPO) $(PR)

list-items:
ifndef REPO
	@echo "Usage: make list-items REPO=owner/repo PR=number"
	@exit 1
endif
ifndef PR
	@echo "Usage: make list-items REPO=owner/repo PR=number"
	@exit 1
endif
	@bash $(SCRIPT_DIR)/watch-prs.sh -r $(REPO) -p $(PR) --list-items

clean:
	@echo "Cleaning state files..."
	@rm -f $(REPO_ROOT)/runner-data/pr-reviews.json
	@echo '{"reviewed":{}}' > $(REPO_ROOT)/runner-data/pr-reviews.json
	@echo "Done. State reset."