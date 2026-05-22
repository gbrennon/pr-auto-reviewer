#!/usr/bin/env bash
# status.sh - Show service status

systemctl --user status pr-auto-reviewer.service || true