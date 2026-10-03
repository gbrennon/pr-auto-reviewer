# Auditor

The Auditor protects the review's memory. A new review can see findings from an earlier run, but it must not silently assume that the updated code fixed them. The Auditor compares each prior finding with the current source and decides whether the original defect is still open or has been resolved.

## What the Auditor produces

For every prior finding, the Auditor returns the original finding with an explicit `status`:

- `open` when the defect remains, the evidence is incomplete, or the audit cannot finish;
- `resolved` only when the current code proves that the defect no longer exists.

The default is `open`. Resolution by absence is forbidden: a missing mention, an unread file, or a vague model assertion is not proof of remediation.

## How it decides

The Auditor revisits the finding's file, description, detection method, reproduction, acceptance criteria, and relevant code. It uses the repository exploration tools to inspect the current implementation and checks both sides of the claim:

1. reproduce the original defect or trace the behavior that caused it;
2. verify that the proposed change satisfies the finding's acceptance criteria;
3. return an explicit result for the finding's index.

The conversation is fail-closed. An aborted or unparseable audit leaves every prior finding `open`, preserving the blocking behavior until a later run supplies evidence.

## Relationship to verification

The verifier handles newly reported findings and rejects hallucinations by checking them against source. It does not decide whether a prior finding was remediated. The Auditor owns that decision, and the orchestrator runs it only when prior findings are present for the review.
