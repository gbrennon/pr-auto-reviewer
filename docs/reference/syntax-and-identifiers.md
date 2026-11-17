# Overview and Purpose

PR Auto Reviewer supports automation commands posted as PR discussion comments. The primary use case is converting findings from an automated code review into tracked repository issues without navigating away from the PR conversation.

When developers or maintainers review findings posted by the bot, they can comment with a command targeting one or more finding IDs. When processed, the tool extracts the finding details, creates dedicated repository issues, and comments back on the PR with references to the created issues.

---

## Supported Command Syntax

Commands are parsed by `IssueCommandParser` using a flexible regular expression that accommodates common prefix and separator conventions.

### Syntax Variations

The following formats are recognized interchangeably:

- `/create-issue <item_ids>`
- `/create issue <item_ids>`
- `/createissue <item_ids>`
- `create-issue <item_ids>`
- `create issue <item_ids>`
- `createissue <item_ids>`
- `/create-issue for <item_ids>`
- `/create issue for <item_ids>`
- `create-issue for <item_ids>`
- `create issue for <item_ids>`

Dismissal uses the following syntax:

- `dismiss <item_ids>`
- `/dismiss <item_ids>`

### Casing and Whitespace Rules

- **Case-Insensitive**: Commands match regardless of casing. For example, `/CREATE ISSUE a1, b2` and `/create-issue a1, b2` behave identically.
- **Leading Slash Optional**: Commands work both with a leading slash (`/create-issue`) and without (`create-issue`).
- **Whitespace Tolerance**: Spaces or hyphens between `create` and `issue` are accepted. Optional `for` preposition is accepted.
- **Delimiter Tolerance**: Item IDs are separated by commas. Spaces surrounding commas are automatically stripped (for example, `a3f2 , b7d1` is parsed as `["a3f2", "b7d1"]`).

### Examples

```markdown
/create-issue a3f2
/create-issue a3f2, b7d1
create issue for c9e4, d1f0
/createissue 1a2b
```

### Dismissal

Use `dismiss` to mark open, non-blocking review items as no longer relevant
without creating or closing a tracker issue:

```markdown
dismiss e03401 , b99602
```

Dismissal accepts IDs from both findings and suggestions. Spaces around commas
are optional. Repeating the same command is safe and idempotent.

### Blocking-item restriction

`create issue` and `dismiss` automation is limited to open, non-blocking items.
CRITICAL and MAJOR severities and every SECURITY-category item are rejected and
remain open for code changes and formal review. A command containing both an
eligible ID and a blocking ID is rejected atomically; no ID is acted upon.
Dismissal does not close external tracker issues.

```markdown
Cannot dismiss review items for: `b7d1` (major bug, blocking; status: open).
Only open non-blocking review items are eligible; blocking findings must be
handled through code changes and formal review.
```

---

## Finding Review Item IDs

Each actionable issue reported in the bot's review comment is assigned a unique identifier.

### Anatomy of a Review Item Header

Review items in the posted review body begin with a structured header formatted as:

```markdown
<id>. [<category>] [<severity>] <file_path>:<line>
```

Example review item header:

```markdown
a3f2. [BUG] [CRITICAL] src/server/auth.py:42
```

In this example, the item ID is `a3f2`.

### Listing Items via CLI

You can inspect the parsed items and their IDs for any reviewed PR from the terminal:

```bash
# Using pr-auto-reviewer CLI
pr-auto-reviewer list-items --repo owner/repo --pr 42

# Using Make
make list-items REPO=owner/repo PR=42
```

The output displays an ASCII table:

```text
#    | Severity   | Category     | File                           | Description
----------------------------------------------------------------------------------------------------
a3f2 | CRITICAL   | BUG          | src/server/auth.py:42          | Token expiration logic fails on leap year...
b7d1 | MAJOR      | SECURITY     | src/server/headers.py:15       | Unsanitized input in header parser...
```

The values in the `#` column correspond directly to the item IDs passed to issue creation commands.

---
