# Git Plan — `fix/llm-hallucination-unbiased-tests`

Branch already contains pre-existing refactoring work (47 files diff,
580 insertions, 1761 deletions). Each commit groups source changes with
their tests, focused on `src/pr_auto_reviewer/` + `Makefile` + `tests/`.

---

## Commit 1 — `refactor(config): unify configuration into infrastructure/config`

Centralises config loading, adds `GitProvider`, `REVIEW_OUTPUT` mode,
`PLATFORM_*` env vars alongside legacy `FORGEJO_*`/`OLLAMA_*` names.
Cleans up `forgejo_api.py` (-208 lines) to delegate to the new config.

**Source:**
```
src/pr_auto_reviewer/config.py                                   (modified)
src/pr_auto_reviewer/forgejo_api.py                              (modified, -208)
src/pr_auto_reviewer/infrastructure/config/config.py             (new)
.env.example                                                      (modified)
Makefile                                                          (modified)
```

**Tests:**
```
tests/pr_auto_reviewer/infrastructure/config/test_config.py      (new)
```

---

## Commit 2 — `refactor(application): restructure services, commands, and ports`

Adds `RegisterIssueService`, `ProcessIssueCommandsService` command
patterns. Updates `__init__.py` exports. Adds `register_issue` command
and port. Minor message/serializer tweaks.

**Source:**
```
src/pr_auto_reviewer/application/commands/__init__.py            (modified)
src/pr_auto_reviewer/application/commands/register_issue_command.py (new)
src/pr_auto_reviewer/application/messages/messages.py            (modified)
src/pr_auto_reviewer/application/ports/inbound/__init__.py       (modified)
src/pr_auto_reviewer/application/ports/inbound/register_issue_port.py (new)
src/pr_auto_reviewer/application/serializers/issue_body_builder.py (modified)
src/pr_auto_reviewer/application/services/__init__.py            (modified)
src/pr_auto_reviewer/application/services/process_issue_commands_service.py (modified, +140)
src/pr_auto_reviewer/application/services/register_issue_service.py (new)
```

**Tests:**
```
tests/pr_auto_reviewer/application/services/test_process_issue_commands_service.py (new)
tests/pr_auto_reviewer/application/services/test_register_issue_service.py        (new)
tests/pr_auto_reviewer/application/services/test_review_pull_request_service.py   (new)
```

---

## Commit 3 — `refactor(domain): add review_item entities and exceptions`

Adds `review_item_not_found_error`, updates `review_item` entity,
updates domain `__init__.py` exports.

**Source:**
```
src/pr_auto_reviewer/domain/__init__.py                          (modified)
src/pr_auto_reviewer/domain/entities/review_item.py              (modified)
src/pr_auto_reviewer/domain/exceptions/__init__.py               (modified)
src/pr_auto_reviewer/domain/exceptions/review_item_not_found_error.py (new)
```

**Tests:**
```
tests/pr_auto_reviewer/domain/entities/test_issue.py             (new)
tests/pr_auto_reviewer/domain/entities/test_pull_request.py      (new)
tests/pr_auto_reviewer/domain/value_objects/test_code_review.py  (new)
tests/pr_auto_reviewer/domain/value_objects/test_comment_id.py   (new)
tests/pr_auto_reviewer/domain/value_objects/test_commit_sha.py   (new)
tests/pr_auto_reviewer/domain/value_objects/test_issue_command.py (new)
tests/pr_auto_reviewer/domain/value_objects/test_item_severity.py (new)
tests/pr_auto_reviewer/domain/value_objects/test_pull_request_diff.py (new)
tests/pr_auto_reviewer/domain/value_objects/test_pull_request_id.py (new)
tests/pr_auto_reviewer/domain/value_objects/test_repository_context_value_object.py (new)
tests/pr_auto_reviewer/domain/value_objects/test_review_item.py  (new)
tests/pr_auto_reviewer/domain/value_objects/test_review_verdict.py (new)
tests/pr_auto_reviewer/domain/services/test_issue_command_parser.py (new)
tests/pr_auto_reviewer/domain/services/test_review_item_parser.py (new)
```

**Deleted (old structure):**
```
tests/pr_auto_reviewer/core/models/entities/test_issue.py        (deleted)
tests/pr_auto_reviewer/core/models/entities/test_pull_request.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_code_review.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_comment_id.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_commit_sha.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_issue_command.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_item_severity.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_pull_request_diff.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_pull_request_id.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_review_context.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_review_item.py (deleted)
tests/pr_auto_reviewer/core/models/value_objects/test_review_verdict.py (deleted)
```

---

## Commit 4 — `refactor(infrastructure): add DI container, response parser, adapters`

Adds `Container` for dependency injection. Splits `OllamaLlmAdapter`
(-201 lines, delegates to `PromptBuilder` + `ReviewResponseParser`).
Adds `TerminalReviewPublisher`, `NullPullRequestRepository`,
`GitProvider`. Updates all platform adapters for new config.

**Source:**
```
src/pr_auto_reviewer/infrastructure/container.py                 (new)
src/pr_auto_reviewer/infrastructure/git_platform/git_provider.py (new)
src/pr_auto_reviewer/infrastructure/git_platform/terminal_review_publisher.py (new)
src/pr_auto_reviewer/infrastructure/llm/ollama_llm_adapter.py    (modified, -201)
src/pr_auto_reviewer/infrastructure/llm/review_response_parser.py (new)
src/pr_auto_reviewer/infrastructure/persistence/null_pr_repository.py (new)
src/pr_auto_reviewer/infrastructure/git_platform/architecture_detector.py (modified)
src/pr_auto_reviewer/infrastructure/git_platform/changeset_fetcher.py (modified)
src/pr_auto_reviewer/infrastructure/git_platform/comment_publisher.py (modified)
src/pr_auto_reviewer/infrastructure/git_platform/repo_lister_adapter.py (modified)
src/pr_auto_reviewer/infrastructure/git_platform/repository_context.py (modified)
src/pr_auto_reviewer/infrastructure/git_platform/review_publisher.py (modified)
```

**Tests:**
```
tests/pr_auto_reviewer/infrastructure/test_container.py          (new)
tests/pr_auto_reviewer/infrastructure/client/test_git_platform_http_client.py (new)
tests/pr_auto_reviewer/infrastructure/command_bus/test_in_memory_command_bus.py (new)
tests/pr_auto_reviewer/infrastructure/config/test_config.py      (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_architecture_detector.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_changeset_fetcher.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_comment_publisher.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_comment_reader.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_fixture_pairs.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_git_provider.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_issue_tracker.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_pr_lister_adapter.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_repo_lister_adapter.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_repository_context.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_review_publisher.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_review_reader.py (new)
tests/pr_auto_reviewer/infrastructure/git_platform/test_terminal_review_publisher.py (new)
tests/pr_auto_reviewer/infrastructure/llm/test_ollama_llm_adapter.py (new)
tests/pr_auto_reviewer/infrastructure/llm/test_review_response_parser.py (new)
tests/pr_auto_reviewer/infrastructure/persistence/test_json_file_pr_repository.py (new)
tests/pr_auto_reviewer/infrastructure/persistence/test_null_pr_repository.py (new)
tests/pr_auto_reviewer/infrastructure/persistence/test_pr_repository.py (new)
```

**Fixtures (supporting):**
```
tests/fixtures/__init__.py                                       (new)
tests/fixtures/auto_fixtures.py                                  (new)
tests/fixtures/changeset_fixtures.py                             (new)
tests/fixtures/git_platform_fixtures.py                          (new)
tests/fixtures/http_fixtures.py                                  (new)
tests/fixtures/integration_fixtures.py                           (new)
tests/fixtures/http_client_fixtures.json                         (new)
tests/fixtures/comment_publisher_fixtures.json                   (new)
tests/fixtures/comment_reader_fixtures.json                      (new)
tests/fixtures/context_fixtures.json                             (new)
tests/fixtures/integration_fixtures.json                         (new)
tests/fixtures/issue_tracker_fixtures.json                       (new)
tests/fixtures/pr_fixtures.json                                  (new)
tests/fixtures/repository_context_fixtures.json                  (new)
tests/fixtures/review_flow_fixtures.json                         (new)
tests/fixtures/review_publisher_fixtures.json                    (new)
tests/fixtures/review_reader_fixtures.json                       (new)
tests/fixtures/capture_responses.py                              (new)
tests/conftest.py                                                 (new)
tests/fixtures/pr18.diff                                         (deleted)
```

---

## Commit 5 — `refactor(presentation): add CLI runner, polling daemon, composition root`

Adds `CliRunner` for subcommand dispatch. Adds `PollingDaemon` +
`PollingDaemonConfig`. Adds `CompositionRoot` for DI wiring.
Deletes old `bootstrap.py`. Updates `cli.py`, `main.py`,
`ollama_client.py`, `comment_parser.py`, `review_item_extractor.py`.
Adds CLI scripts: `clean`, `create-issues`, `list-items`, `validate`,
`validate-pr`, `watch-prs`, `reload`, `start`, `stop`, `status`,
`restart`, `logs`, `help`, `check-token`, `get-pr-diff`,
`issue-creator`, `test-issue-creation`.

**Source:**
```
src/pr_auto_reviewer/cli.py                                      (modified, +66)
src/pr_auto_reviewer/main.py                                     (modified)
src/pr_auto_reviewer/ollama_client.py                            (modified)
src/pr_auto_reviewer/comment_parser.py                           (modified)
src/pr_auto_reviewer/review_item_extractor.py                    (modified)
src/pr_auto_reviewer/test_issue_creation.py                      (modified)
src/pr_auto_reviewer/bootstrap.py                                (deleted)
src/pr_auto_reviewer/__init__.py                                 (modified)
src/pr_auto_reviewer/clean.py                                    (new)
src/pr_auto_reviewer/create_issues_from_pr.py                    (new)
src/pr_auto_reviewer/list_items.py                               (new)
src/pr_auto_reviewer/validate.py                                 (new)
src/pr_auto_reviewer/validate_pr.py                              (new)
src/pr_auto_reviewer/watch_prs.py                                (new)
src/pr_auto_reviewer/reload.py                                   (new)
src/pr_auto_reviewer/start.py                                    (new)
src/pr_auto_reviewer/stop.py                                     (new)
src/pr_auto_reviewer/status.py                                   (new)
src/pr_auto_reviewer/restart.py                                  (new)
src/pr_auto_reviewer/logs.py                                     (new)
src/pr_auto_reviewer/help.py                                     (new)
src/pr_auto_reviewer/check_token.py                              (new)
src/pr_auto_reviewer/get_pr_diff.py                              (new)
src/pr_auto_reviewer/issue_creator.py                            (new)
src/pr_auto_reviewer/presentation/cli/runner.py                  (modified, +85)
src/pr_auto_reviewer/presentation/polling_daemon/polling_daemon.py (modified)
src/pr_auto_reviewer/presentation/polling_daemon/polling_daemon_config.py (modified)
src/pr_auto_reviewer/presentation/composition_root.py            (new)
scripts/watch-prs.sh                                              (modified)
```

**Tests:**
```
tests/pr_auto_reviewer/presentation/cli/test_cli_runner.py       (new)
tests/pr_auto_reviewer/presentation/polling_daemon/test_polling_daemon.py (new)
tests/pr_auto_reviewer/presentation/polling_daemon/test_polling_daemon_config.py (new)
tests/pr_auto_reviewer/presentation/test_composition_root.py     (new)
tests/pr_auto_reviewer/presentation/ports/test_open_pull_request.py (new)
tests/pr_auto_reviewer/test_e2e_review_flow.py                   (new)
```

---

## Commit 6 — `fix(llm): include file_contents in prompt to prevent hallucinations`

The PromptBuilder only sent unified diffs (`+prefix`) to the LLM.
Small models hallucinated "missing shebang" on code that already had one.
Adding clean file contents and explicit anti-hallucination rules fixes
this. Also adds `force=True` to `logging.basicConfig`.

**Source:**
```
src/pr_auto_reviewer/infrastructure/llm/prompt_builder.py        (new, +132)
src/pr_auto_reviewer/presentation/composition_root.py            (modified, force=True)
```

**Tests:**
```
tests/pr_auto_reviewer/infrastructure/llm/test_prompt_builder.py (new, 16 tests)
```

---

## Commit 7 — `feat(scripts): add capture-ollama-fixtures.py`

Batch script that sends diff fixtures to the real Ollama API and
saves raw `{"response": "..."}` JSON. Removes hand-crafted bias.

**Source:**
```
scripts/capture-ollama-fixtures.py                               (new)
```

---

## Commit 8 — `test(fixtures): add multi-language diff and captured Ollama fixtures`

18 diff fixtures across 7 languages + 2 bash scripts. 9 real captured
Ollama responses from `code-review:latest` (qwen2 7.6B). Full API
payload with model, timings, eval counts. Deletes 9 old hand-crafted
fixtures that had biased assertion-to-data coupling.

**Diff fixtures:**
```
tests/fixtures/diffs/python-sql-injection.diff                   (new)
tests/fixtures/diffs/python-sql-injection.full                   (new)
tests/fixtures/diffs/java-god-class.diff                         (new)
tests/fixtures/diffs/java-god-class.full                         (new)
tests/fixtures/diffs/go-no-error-handling.diff                   (new)
tests/fixtures/diffs/go-no-error-handling.full                   (new)
tests/fixtures/diffs/rust-clean-service.diff                     (new)
tests/fixtures/diffs/rust-clean-service.full                     (new)
tests/fixtures/diffs/ruby-hardcoded-secret.diff                  (new)
tests/fixtures/diffs/ruby-hardcoded-secret.full                  (new)
tests/fixtures/diffs/csharp-tight-coupling.diff                  (new)
tests/fixtures/diffs/csharp-tight-coupling.full                  (new)
tests/fixtures/diffs/kotlin-clean-service.diff                   (new)
tests/fixtures/diffs/kotlin-clean-service.full                   (new)
tests/fixtures/diffs/shell-with-shebang.diff                     (new)
tests/fixtures/diffs/shell-with-shebang.full                     (new)
tests/fixtures/diffs/shell-missing-shebang.diff                  (new)
tests/fixtures/diffs/shell-missing-shebang.full                  (new)
```

**Ollama responses:**
```
tests/fixtures/ollama_responses/python-sql-injection.json        (captured)
tests/fixtures/ollama_responses/java-god-class.json              (captured)
tests/fixtures/ollama_responses/go-no-error-handling.json        (captured)
tests/fixtures/ollama_responses/rust-clean-service.json          (captured)
tests/fixtures/ollama_responses/ruby-hardcoded-secret.json       (captured)
tests/fixtures/ollama_responses/csharp-tight-coupling.json       (captured)
tests/fixtures/ollama_responses/kotlin-clean-service.json        (captured)
tests/fixtures/ollama_responses/shell-with-shebang.json          (captured)
tests/fixtures/ollama_responses/shell-missing-shebang.json       (captured)

tests/fixtures/ollama_responses/approved_shell.json              (deleted)
tests/fixtures/ollama_responses/changes_requested_shell.json     (deleted)
tests/fixtures/ollama_responses/python_sql_injection.json        (deleted)
tests/fixtures/ollama_responses/java_god_class.json              (deleted)
tests/fixtures/ollama_responses/go_no_error_handling.json        (deleted)
tests/fixtures/ollama_responses/ruby_hardcoded_secret.json       (deleted)
tests/fixtures/ollama_responses/csharp_tight_coupling.json       (deleted)
tests/fixtures/ollama_responses/rust_clean_service.json          (deleted)
tests/fixtures/ollama_responses/kotlin_clean_service.json        (deleted)
```

---

## Commit 9 — `test(e2e): add real verdict E2E tests with captured fixtures`

26 tests through the full pipeline — real `ReviewPullRequestService`,
`OllamaLlmAdapter`, `ReviewResponseParser`, `PromptBuilder`. Only
`requests.post` is mocked. Covers APPROVED, CHANGES_REQUESTED, prompt
contents, multi-language fixtures, and all LLM-outage scenarios
(connection refused, timeout, HTTP 500, DNS, invalid JSON, empty
response, publisher-not-called safety check).

**Tests:**
```
tests/pr_auto_reviewer/test_e2e_review_verdict.py                (new, 12 tests)
tests/pr_auto_reviewer/test_multilang_review_verdict.py          (new, 14 tests)
```

---

## Commit 10 — `refactor(test): replace MagicMock with injected stubs in app tests`

18 MagicMock instances replaced with 9 real stub classes implementing
port Protocols. Call tracking via plain lists. Uses real domain
services (`ReviewItemParser`, `IssueCommandParser`, `IssueBodyBuilder`).

**Stubs + tests:**
```
tests/pr_auto_reviewer/application/stubs.py                      (new)
tests/pr_auto_reviewer/application/__init__.py                   (new)
tests/pr_auto_reviewer/application/services/test_review_pull_request_service.py  (rewritten, 5 tests)
tests/pr_auto_reviewer/application/services/test_register_issue_service.py       (rewritten, 5 tests)
tests/pr_auto_reviewer/application/services/test_process_issue_commands_service.py (rewritten, 5 tests)
```

---

## Commit 11 — `docs: add fix-llm-hallucination.md and git-plan.md`

**Docs:**
```
docs/fix-llm-hallucination.md                                    (new)
docs/git-plan.md                                                 (new)
```

---

## Layer summary

| Commit | Layer | Scope |
|--------|-------|-------|
| 1 | Infrastructure | Config unification |
| 2 | Application | Services, commands, ports |
| 3 | Domain | Entities, exceptions, value objects |
| 4 | Infrastructure | Container, adapters, parser |
| 5 | Presentation | CLI, daemon, composition root |
| 6 | Infrastructure | Prompt builder fix |
| 7 | Scripts | Capture tool |
| 8 | Fixtures | Diffs + Ollama responses |
| 9 | E2E | Verdict + multilang tests |
| 10 | Application tests | Stubs replacing MagicMock |
| 11 | Docs | Documentation |

## Test count progression

| Commit | Tests |
|--------|-------|
| 1 | config tests |
| 2 | app service tests (MagicMock) |
| 3 | domain entities + value objects |
| 4 | infrastructure adapters |
| 5 | presentation (CLI, daemon, E2E flow) |
| 6 | prompt builder |
| 8 | fixture data |
| 9 | E2E verdict (26 tests) |
| 10 | app service tests (stubs, rewritten) |
| **Total** | **557 tests** |
