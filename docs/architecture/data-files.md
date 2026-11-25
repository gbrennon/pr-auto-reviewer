# Data Files

```
~/.config/pr-auto-reviewer/
└── config                  # Configuration file (env-file format)

~/.local/state/pr-auto-reviewer/
├── state.json              # State file - tracks reviewed PRs by SHA
└── conversations/          # Per-review LLM conversation transcripts

~/.cache/pr-auto-reviewer/
├── verified-tokens.json    # Token verification cache
└── repos/                  # Local git clones for diffing
```

The state file prevents duplicate reviews. A PR is only re-reviewed if the SHA changes.
