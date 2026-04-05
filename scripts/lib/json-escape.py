#!/usr/bin/env python3
"""Escape a string for JSON."""

import sys
import json

print(json.dumps(sys.stdin.read()))
