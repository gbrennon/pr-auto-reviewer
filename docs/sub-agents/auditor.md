# Auditor

The Auditor protects the review's memory. It runs before the normal review
phases and audits the complete historical record, not only the latest review.
That record includes every actionable finding and suggestion from every
persisted `CodeReview` snapshot, including records whose current status is
terminal.

## Lifecycle records

The Auditor preserves each record's immutable evidence and existing ID. It
changes only the lifecycle projection:

- `created` marks a record's first appearance before publication;
- `open` means the record is still active after an audit;
- `resolved` means the current code positively proves that the defect or
  suggestion has been addressed;
- `dismissed` means the record was explicitly dismissed.

`resolved` and `dismissed` are terminal. Auditing a terminal record is
required for complete history, but a terminal record must not be reopened.
If the same defect or suggestion recurs after a terminal outcome, it is a
new record with a new ID. The Auditor audits the supplied historical records;
it never matches a new finding to an old terminal ID.

The next audit of a `created` record yields `open` when it remains present or
`resolved` only with positive proof. A missing mention, an unread file, or a
vague model assertion is not proof of remediation. The latest transition
explanation is retained with the lifecycle and is rendered with the record
when the output model exposes it.

## How it decides

For each historical finding or suggestion, the Auditor revisits the recorded
file, description, detection method, reproduction, acceptance criteria, and
relevant code. It uses the repository exploration tools to inspect the
current implementation and checks both sides of the claim:

1. reproduce the original defect or trace the behavior that caused it;
2. verify that the proposed change satisfies the finding's acceptance
   criteria, or that the suggestion is now addressed;
3. return an explicit result for the record's supplied index;
4. preserve the record's source section (`items` or `suggestions`) and ID.

The conversation is fail-closed. An aborted or unparseable audit leaves an
active historical record open, preserving blocking behavior until a later run
supplies evidence. It does not discard records, synthesize replacements, or
turn suggestions into findings.

## Relationship to verification

The verifier handles newly reported findings and rejects hallucinations by
checking them against source. It does not decide whether a prior finding or
suggestion was remediated. The Auditor owns that decision for all historical
records, while the normal phases independently produce genuinely new records.
