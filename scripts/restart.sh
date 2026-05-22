#!/usr/bin/env bash
# restart.sh - Restart the watcher service

set -e

systemctl --user restart pr-auto-reviewer.service || true
echo "Service restarted."