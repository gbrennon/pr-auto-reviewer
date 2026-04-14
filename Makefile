.PHONY: help install start stop status restart logs watch test clean issues list-items install-bashunit

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
	@echo "  make test           Run unit tests"
	@echo "  make issues         Create issues from PR commands"
	@echo "  make list-items     List review items from PR"
	@echo "  make clean          Clean state files"
	@echo "  make install-bashunit  Install bashunit testing framework"
	@echo ""
	@echo "Examples:"
	@echo "  make test"
	@echo "  make watch"
	@echo "  make issues REPO=owner/repo PR=8"
	@echo "  make list-items REPO=owner/repo PR=8"

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
	@bash $(SCRIPT_DIR)/test-unit.sh

issues:
	@bash $(SCRIPT_DIR)/create-issues-from-pr.sh

list-items:
	@bash $(SCRIPT_DIR)/list-items.sh

clean:
	@bash $(SCRIPT_DIR)/clean.sh

install-bashunit:
	@bash $(SCRIPT_DIR)/install-bashunit.sh