.PHONY: help install start stop status restart logs watch test clean issues list-items install-bashunit test-unit

SHELL := /usr/bin/env bash
SCRIPT_DIR := scripts
REPO_ROOT := .

BASHUNIT := ./lib/bashunit

help:
	@echo "PR Auto Reviewer - Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install         Install and configure the service"
	@echo "  make start           Start the watcher service"
	@echo "  make stop           Stop the watcher service"
	@echo "  make status         Show service status"
	@echo "  make restart        Restart the service"
	@echo "  make logs           Show service logs (follow)"
	@echo "  make watch          Run watcher once (manual mode)"
	@echo "  make test           Run test on a repo"
	@echo "  make issues         Create issues from PR commands"
	@echo "  make list-items     List review items from PR"
	@echo "  make clean          Clean state files"
	@echo "  make install-bashunit  Install bashunit testing framework"
	@echo "  make test-unit      Run unit tests with bashunit"
	@echo ""
	@echo "Examples:"
	@echo "  make test REPO=gbrennon/pr-auto-reviewer"
	@echo "  make issues REPO=owner/repo PR=8"
	@echo "  make list-items REPO=owner/repo PR=8"
	@echo "  make test-unit"

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

watch:
	@bash $(SCRIPT_DIR)/watch.sh

test:
ifndef REPO
	@echo "Usage: make test REPO=owner/repo"
	@exit 1
endif
	@bash $(SCRIPT_DIR)/test-pr.sh $(REPO)

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
	@bash $(SCRIPT_DIR)/list-items.sh $(REPO) $(PR)

clean:
	@bash $(SCRIPT_DIR)/clean.sh

install-bashunit:
	@bash $(SCRIPT_DIR)/install-bashunit.sh

test-unit:
	@bash $(SCRIPT_DIR)/test-unit.sh