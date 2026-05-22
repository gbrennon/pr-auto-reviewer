#!/usr/bin/env bash
# start.sh - Start the watcher service

set -e

echo "Starting service..."
systemctl --user start pr-auto-reviewer.service
echo "Service started."