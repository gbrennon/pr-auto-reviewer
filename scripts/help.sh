#!/usr/bin/bash
# help.sh — Show help for PR Auto Reviewer

cat <<EOF
PR Auto Reviewer - Makefile

Usage:
  make install         Install and configure the service
  make start           Start the watcher service
  make stop           Stop the watcher service
  make status         Show service status
  make restart        Restart the service
  make logs           Show service logs (follow)
  make watch          Run watcher once (manual mode)
  make test           Run unit tests
  make issues         Create issues from PR commands
  make list-items     List review items from PR
  make clean          Clean state files
  make install-bashunit  Install bashunit testing framework
  make validate DIFF=<file> [OUTPUT=<file>] [REPO=<path>]  Generate local code review (no Codeberg API)
  make validate-pr REPO=<owner/repo> PR=<n> [OUTPUT=<file>] [BRANCH=<branch>]  Generate review from Codeberg PR

Examples:
  make test
  make watch
  make issues REPO=owner/repo PR=8
  make list-items REPO=owner/repo PR=8
  make validate DIFF=changes.patch
  make validate DIFF=changes.patch REPO=/path/to/repo
  make validate-pr REPO=owner/repo PR=42
EOF