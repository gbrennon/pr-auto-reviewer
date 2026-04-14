#!/usr/bin/env bash
# status.sh - Show service status

systemctl --user status pr-ai-auto-reviewer.service || true