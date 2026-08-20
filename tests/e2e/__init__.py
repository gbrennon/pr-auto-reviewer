"""End-to-end tests: record-and-replay review flows and captured behavior.

These tests run against the full environment; the first run records real
HTTP into VCR cassettes, and later runs replay them offline.
"""