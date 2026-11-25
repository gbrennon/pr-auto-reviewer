# Command Processing Lifecycle

Commands placed in PR comments are executed via `process-commands`.

### Invoking Command Processing

To trigger command processing for a pull request:

```bash
# Using the CLI
pr-auto-reviewer process-commands --repo owner/repo --pr 42 [-v]

# Using Make
make issues REPO=owner/repo PR=42
```

### End-to-End Processing Flow

`ProcessIssueCommandsService` handles the command lifecycle in the following sequence:

1. **Load Pull Request**: Fetches the `PullRequest` aggregate from the repository (`pr_repository.find`).
2. **Retrieve Latest Review**: Reads the raw markdown of the latest review comment (`review_reader.get_latest_review`).
3. **Parse Review Items**: Parses review items and their IDs from the review body (`review_item_parser.parse`).
4. **Fetch PR Comments**: Retrieves all comments posted on the PR (`comment_reader.get_comments`).
5. **Deduplication / Idempotency**: Evaluates each comment. If `pr.is_comment_processed(comment.id)` is true, the comment is skipped to prevent duplicate issue creation.
6. **Command Parsing**: Inspects unprocessed comments with `issue_command_parser.parse(comment.id, comment.body)`.
7. **Mark Processed**: Records the comment ID as processed on the PR entity (`pr.mark_comment_processed(comment.id)`).
8. **Item Validation**: Compares requested IDs against current review items:
   - **Unknown IDs**: A validation failure comment lists available items.
   - **Blocking or inactive IDs**: The ID is rejected and remains unchanged.
   - **Mixed commands**: If any requested ID is unknown, blocking, or inactive,
     the whole command is rejected and no eligible ID is acted upon.
   - **Open non-blocking IDs**: The command proceeds with issue creation or dismissal.
9. **Apply Command**: Creates tracker issues or records dismissed IDs in the PR aggregate.
10. **Post Confirmation**: A comment lists created issues, dismissed IDs, or rejected IDs.
11. **Persist State**: Saves the updated pull request entity with processed comments and command state.

---

## Bot Feedback and Responses

When all item IDs are valid open, non-blocking findings, the bot creates the
issues on the target repository and comments back with issue references:

```markdown
Created 2 issue(s):

- #101: [MINOR] STYLE: Simplify this branch
  - review item `a3f2` (minor style, non-blocking) — status: open (still relevant)
- #102: [INFO] DOCS: Clarify configuration
  - review item `b7d1` (info docs, non-blocking) — status: open (still relevant)
```

### Validation Failure Response

If any item ID cannot be found in the latest review, the bot halts issue creation and provides a helpful list of available item IDs:

```markdown
Could not find review items: #xyz9.

Available items:
- #a3f2: Token expiration logic fails on leap year...
- #b7d1: Unsanitized input in header parser...
```

### Atomic Validation Rule

Item validation is atomic per command: if any requested ID is unknown,
blocking, or inactive, no issues are created and no items are dismissed from
that comment. This prevents partial execution and ensures the user can review
the rejection before retrying.

---
