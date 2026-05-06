#!/usr/bin/env bash
# stop.sh - Stop the watcher service

set -e

echo "Stopping service..."
systemctl --user stop pr-ai-auto-reviewer.service
echo "Service stopped."