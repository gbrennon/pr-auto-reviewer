.PHONY: help install start stop status restart logs watch test clean issues list-items install-bashunit validate validate-pr bootstrap review capture-fixture

SHELL := /usr/bin/bash
SCRIPT_DIR := scripts

help:
	@bash $(SCRIPT_DIR)/help.sh

install:
	@bash $(SCRIPT_DIR)/install-service.sh

start:
	@bash $(SCRIPT_DIR)/start.sh
	@echo "Starting PR Auto Reviewer..."
	@python -m pr_auto_reviewer.cli watch-prs

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

clean:
	@bash $(SCRIPT_DIR)/clean.sh

issues:
	@bash $(SCRIPT_DIR)/create-issues-from-pr.sh

list-items:
	@bash $(SCRIPT_DIR)/list-items.sh

install-bashunit:
	@bash $(SCRIPT_DIR)/install-bashunit.sh

validate:
	@bash $(SCRIPT_DIR)/validate.sh -d $(DIFF) $(if $(OUTPUT),-o $(OUTPUT)) $(if $(REPO),-r $(REPO))

validate-pr:
	@bash $(SCRIPT_DIR)/validate-pr.sh -r $(REPO) -p $(PR) $(if $(OUTPUT),-o $(OUTPUT)) $(if $(BRANCH),-b $(BRANCH))

bootstrap:
	@bash $(SCRIPT_DIR)/bootstrap.sh

review:
	@bash $(SCRIPT_DIR)/watch-prs.sh -r $(REPO) -p $(PR) --once

capture-fixture:
	@bash $(SCRIPT_DIR)/capture-fixture.sh -r $(REPO) -p $(PR) 
