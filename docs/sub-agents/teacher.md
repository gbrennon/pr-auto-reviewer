# Teacher

The teacher is the quality and skills role of the review team. Unlike the
peers, it produces no review findings: it **teaches** each sub-agent its
craft and keeps the whole team's skill curve rising. In practice the
teacher is embodied by the coaching layer — the manager's task planning
and the advisor's live feedback — plus this documentation set, which is
the team's curriculum.

## Why the teacher exists

A sub-agent that merely re-reads its instructions drifts. A sub-agent
that *understands its task, the failure modes, and the reasons behind
the rules* stays on task and self-corrects. The teacher exists to close
that gap: every prompt, every piece of feedback, and every doc page is
written to be **taught** — concept first, then rule, then concrete
example — so the sub-agents internalize *why* rather than just *what*.

## How the teacher works

1. **Assigns a focused task before work.** The [manager](manager.md)
   acts first: it explains the intent, separates the diff into focused
   tasks, and hands each phase one task it must not re-derive. The task
   is the lesson plan for that phase.
2. **Gives feedback while the work happens.** The [advisor](advisor.md)
   reads every turn and grades it on the S/A/B/C/D/F scale. On D it
   interrupts with a corrective note; on F it blocks and the manager
   re-plans the task so the restart teaches the agent what it missed.
   This is the teacher's most important action: it happens during the
   task, not after it.
3. **Keeps a class notebook.** Every exchange — peer turns, advisor
   gradings, manager briefs and re-plans, verifier runs — is persisted
   as a transcript under `~/.local/state/pr-auto-reviewer/conversations/`.
   The notebook is what lets a later review build on the lessons of
   earlier ones.

## Teaching tone (the writing contract)

Every page under `docs/sub-agents/`, and every sub-agent prompt, must
**teach**, in this order:

1. **Why** the role exists and what failure it prevents.
2. **What** the role must produce/decide (its responsibility).
3. **How** — the concrete behaviour, with the failure modes called out
   ("never do X because Y").
4. **How to verify** — a grounded check the agent can run itself
   (e.g. "before concluding, you MUST inspect at least one changed file
   with the tools; a verdict with zero tool calls is rejected").

Rules are stated as taught truths with their consequence, never as bare
prohibitions. Documentation is not a comment recap — it is instruction.

## Relation to other roles

The teacher is expressed through the [manager](manager.md) (who assigns
and re-teaches tasks) and the [advisor](advisor.md) (who grades and
interrupts). The [engineer](engineer.md) and [architect](architect.md)
are its students; the transcripts it leaves are its gradebook.