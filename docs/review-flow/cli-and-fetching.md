# 4.1. CLI Parsing & Bootstrapping

### 4.1. CLI Parsing & Bootstrapping

```
  Shell: uv run pr-auto-reviewer review -r gbrennon/pr-auto-reviewer -p 71 -v --force
         │
         │  pyproject.toml entry point → pr_auto_reviewer.cli:main()
         ▼
  ┌───────────────────────────────────────────────────────────────┐
  │  cli.py:main()                                                │
  │                                                               │
  │  argparse parses:                                             │
  │    command  = "review"                                        │
  │    repo     = "gbrennon/pr-auto-reviewer"                     │
  │    pr       = 71                                              │
  │    force    = True                                            │
  │    verbose  = True                                            │
  │                                                               │
  │  → bootstrap()                                                │
  │      └─ CompositionRoot()                                     │
  │           ├─ load_config()                                    │
  │           │   ├─ Reads .env / user config                     │
  │           │   └─ Config(platform_token, llm_host, ...)        │
  │           ├─ Container(config)  → wires all adapters          │
  │           └─ _wire_components() → ApplicationComponents       │
  │                                                               │
  │  → Rebuilds argv:                                             │
  │    ["pr-auto-reviewer", "review",                             │
  │     "--repo", "gbrennon/pr-auto-reviewer",                    │
  │     "--pr", "71", "--force", "--verbose"]                     │
  │                                                               │
  │  → components.cli_runner.run(argv)                            │
  └───────────────────────────────────────────────────────────────┘
```

### 4.2. CLI Runner — PR Fetching

```
  ┌───────────────────────────────────────────────────────────────┐
  │  CliRunner._run_review(["--repo","...","--pr","71",           │
  │                         "--force","--verbose"])               │
  │                                                               │
  │  force_mode = True  (args.force is True)                      │
  │                                                               │
  │  Since --force:                                               │
  │    → pr_lister.get_pr("gbrennon/pr-auto-reviewer", 71)        │
  │       └─ ForgejoPrLister / GithubPrLister / CompositePrLister │
  │            GET /repos/gbrennon/pr-auto-reviewer/pulls/71      │
  │            → OpenPullRequest(pr_id, head_sha, title, desc)    │
  │       (state-agnostic — works for closed/merged PRs too)      │
  │                                                               │
  │  → ReviewPullRequestCommand(                                  │
  │       pr_id=PullRequestId("gbrennon/pr-auto-reviewer", 71),   │
  │       head_sha=CommitSha("abc123..."),                        │
  │       title="...",                                            │
  │       description="...",                                      │
  │       force=True,                                             │
  │    )                                                          │
  │                                                               │
  │  → review_service.execute(command)                            │
  └───────────────────────────────────────────────────────────────┘
```
