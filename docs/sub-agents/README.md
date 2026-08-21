# Sub-Agent Roles

The staged review is executed by a team of sub-agents. Each role has a
responsibility, a behavior, and an interaction contract with its peers.
Roles are pure metadata in the domain model; the workflow composes them
into phase prompts at runtime. See the individual pages for details:

| Role | Interaction | Responsibility | Behavior |
|---|---|---|---|
| [manager](manager.md) | plans and assigns tasks; briefs the advisor | own the technical context so no phase reviews poorly | act at review start and between phases |
| [advisor](advisor.md) | watches peers; grades and interrupts drift | keep every sub-agent on its assigned task | grade with S/B/D/F and re-prompt on F |
| [engineer](engineer.md) | reviews its assigned phase like a principal | find bugs, quality gaps, principle breaks; suggest fitting practices | prefer clean, decoupled code; never suggest something brand new |
| [architect](architect.md) | reviews structure, not behavior | enforce architecture rules and conventions | read source for violations, coupling, poor design |

The current production plan runs three phases: Bug Hunt — Diff and Bug
Hunt — Branch execute as an *engineer*; Architecture Review executes as
an *architect*. The manager opens the review and the advisor watches
every phase — both shape the composed prompts even though they do not
run their own phases.