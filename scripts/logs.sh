#!/usr/bin/env bash
# logs.sh - Show service logs (follow mode)

journalctl --user -u pr-auto-reviewer.service --no-pager -f