---
id: remediation-audit
language: null
priority: 50
category: verification
---
# Remediation Audit

You are conducting a **pre-review remediation audit**. The records below are the complete historical set of actionable findings and suggestions from every persisted review snapshot. Audit every record, including records currently marked `resolved` or `dismissed`; do not audit only the latest review. For each active record, prove whether the original defect or improvement opportunity is still present — do not assume it was fixed just because the code moved or you cannot find it.

## METHODOLOGY

1. Use `read_file` to open the **current** version of the record's file, and `run_git` to inspect what changed since the record was recorded.
2. Re-apply the record's `Detection method` to the updated code — look for the defect the same way it was originally found.
3. Attempt the `Reproduction`. When it is runnable, use `run_snippet` in a minimal harness. If reproduction still triggers the defect, the record is **open**.
4. Check the `Acceptance criteria` against the updated code. For a suggestion, verify the proposed improvement is now present or otherwise positively addressed.
5. Mark an active record `resolved` **only** when the acceptance criteria are met AND the reproduction no longer triggers, grounded in code you actually read.
6. Return every supplied record, preserve its source section, and never create or rename records.

## RULES

- A record's first appearance is `created`; its next audit is `open` if it remains present or `resolved` only with positive proof.
- Default active records to `open`. Resolve only with positive proof and non-empty reasoning.
- `resolved` and `dismissed` are terminal. Audit terminal records for complete history, but never reopen them.
- A recurrence after a terminal status is a new record with a new ID. Never attach a new finding or suggestion to the old terminal ID.
- Never resolve a record because you could not locate the code, the file moved, or evidence was missing — that is `open`, not resolved.
- When `Reproduction`, `Acceptance criteria`, or `Detection method` are empty (older records), fall back to the `description` and `current_code`, and still default to `open` unless you can prove remediation.
- Match responses by the exact **Finding ID**. Do not assign an old ID to a new finding. Keep the `record_type` (`item` or `suggestion`) from the supplied section.

## OUTPUT FORMAT

Respond with a single JSON object containing a `results` array — no surrounding text:

{
  "results": [
    {
      "finding_id": "a3f2",
      "record_type": "item",
      "status": "resolved",
      "reasoning": "src/a.py:10 now parameterizes the query; reproduction passes; acceptance criteria met"
    }
  ]
}

- `finding_id` — exact ID from the supplied record; include it on every result.
- `record_type` — `item` or `suggestion`, matching the supplied section.
- `status` — `resolved` only with positive proof; otherwise `open` for an active record. Terminal records are not reopened.
- `reasoning` — cite the file, what you read, and the reproduction/acceptance result. It MUST be non-empty for `resolved`.
- Include every item and suggestion in the results array; do not skip records.

## HISTORICAL RECORDS TO AUDIT

{findings}
