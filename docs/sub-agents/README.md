# Sub-Agent Roles

The staged review is executed by a team of sub-agents. Each role has a
responsibility, a behavior, and an interaction contract with its peers.
Roles are pure metadata in the domain model; the workflow composes them
into phase prompts at runtime. See the individual pages for details:

| Role | Interaction | Responsibility | Behavior |
|---|---|---|---|
| [manager](manager.md) | plans and assigns tasks; briefs the advisor | own the technical context so no phase reviews poorly | act at review start and between phases |
| [advisor](advisor.md) | watches peers turn-by-turn; grades S/A/B/C/D/F and interrupts drift | keep every sub-agent on its assigned task | grade every turn; block on F and hand to manager |
| [engineer](engineer.md) | exercises the diff and its indirect blast radius like a principal | find bugs, security issues, biased tests; suggest fitting practices | probe from many angles; verify tests test real behavior |
| [architect](architect.md) | reviews structure, not behavior | enforce architecture rules and conventions | read source for violations, coupling, anti-patterns |
| [teacher](teacher.md) | teaches each role its task and craft | keep the sub-agent skill curve rising | coach via task planning, live feedback, and transcripts |

The current production plan runs three phases: Bug Hunt — Diff and Bug
Hunt — Branch execute as an *engineer*; Architecture Review executes as
an *architect*. The manager opens the review and the advisor watches
every phase — both shape the composed prompts even though they do not
run their own phases.

## Runtime rules

These rules are enforced by the workflow code, not by convention:

1. **The manager opens the review.** Every phase — including the
   first — receives its task from the manager sub-agent before it
   starts. A phase never runs on a static prompt alone; if the manager
   is unavailable the review fails fast rather than drifting.
2. **The advisor interacts with peers, not just post-mortem.** The
   advisor observes every peer turn, grades it on the S/B/D/F scale,
   and interrupts drift with feedback immediately. A phase output is
   only blocked and restarted after repeated F grades.
3. **Blocker feedback goes back through the manager.** When the
   advisor blocks a sub-agent's output, the manager re-plans that
   sub-agent's task and improves its prompt before the phase restarts —
   a restart never replays the same prompt that already failed.
4. **Max turns is injected, never hardcoded.** The per-conversation
   turn limit comes from configuration (`LLM_MAX_TURNS`, default 10)
   through the composition root. Application services must not carry
   their own turn-count constants.
5. **Every LLM exchange leaves a transcript.** Peer conversations,
   advisor gradings, manager briefings, and verification runs are all
   persisted as markdown under `~/.config/pr-auto-reviewer/
   conversations/<repo>_<pr>/`. A crashed conversation is logged too —
   partial output is audit evidence.
6. **The docs teach.** Sub-agent pages and prompts are written in a
   teaching tone: why the role exists, what it must produce, how, and
   how the agent self-verifies — never a bare list of prohibitions.
   See [teacher.md](teacher.md).
7. **The container wires everything.**
   `src/pr_auto_reviewer/infrastructure/container/` is the only place
   where sub-agents, the turn limit, the conversation logger, and the
   event bus are constructed and connected. Application services
   receive collaborators; they never build them.