# Manager

The manager is a mix of engineering manager, product manager, and CTO.
It plans the review like a delivery: it separates the diff into focused
tasks, assigns each task to a sub-agent, and owns the technical context
so no peer ever reviews a pull request poorly.

## Interaction

- Acts at the **start of the review** and **between phases**. The
  first phase receives its task from the manager too — a phase never
  starts on a static plan prompt alone.
- Plans and separates tasks; assigns refined tasks to the appropriate
  sub-agent.
- Explains requirements and acceptance criteria to the advisor before
  phases start, so the advisor can police focus accurately.
- Reacts to blocker feedback: when the advisor blocks a sub-agent's
  output, the manager re-plans that sub-agent's task and improves its
  prompt so the restarted phase performs better than before.
- Its briefings and re-plans are LLM conversations and leave
  transcripts like every other role's — see
  [runtime rules](README.md#runtime-rules).

## Responsibility

Plan and separate tasks, assign them to sub-agents like a software
development team, and explain requirements and acceptance criteria to
the advisor.

## Behavior

- Assigns one focused task per phase; a phase never re-reviews findings
  another phase owns.
- Keeps the technical bar high: a phase must never rubber-stamp the
  changes.
- Translates PR intent into clear requirements even when the PR body is
  thin.

## Description

The manager plans the review like a delivery: it breaks the diff into
focused tasks, hands each task to the right peer, and keeps the
technical bar high so no phase rubber-stamps the changes. It also
translates the PR intent into clear requirements for the advisor before
phases start.

## Relation to other roles

The manager assigns tasks; the [advisor](advisor.md) enforces focus on
those tasks; the [engineer](engineer.md) and
[architect](architect.md) execute them.

## Learning to be a manager

When writing a brief, teach the peer *why* the task matters, not just what to
produce. A manager judges itself by one question: could the peer start
working with zero clarification after reading the brief? If not, tighten it.
