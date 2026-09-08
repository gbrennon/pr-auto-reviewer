# Documentation Index

Navigation hub for all project documentation.

---

## 📁 By Category

### Architecture & Design
| Document | Purpose |
|---|---|
| [architecture/structure.md](architecture/structure.md) | Project structure, layers, source tree |
| [architecture/diagrams/deep-architecture.md](architecture/diagrams/deep-architecture.md) | **Deep architecture diagrams** - hexagonal layers, domain model, orchestration flow, adapter sequences |

### Configuration
| Document | Purpose |
|---|---|
| [configuration/configuration.md](configuration/configuration.md) | All environment variables, precedence, token setup |

### Review Flow
| Document | Purpose |
|---|---|
| [review-flow/review-flow-architecture.md](review-flow/review-flow-architecture.md) | Detailed command flow, port/adapter maps, DI wiring, advanced flows |

### Features
| Document | Purpose |
|---|---|
| [features/features.md](features/features.md) | Implemented features, planned work, platform support |

### Operations (Running the App)
| Document | Purpose |
|---|---|
| [operations/HOWTO-single-review.md](operations/HOWTO-single-review.md) | Single PR review walkthrough |
| [operations/troubleshooting.md](operations/troubleshooting.md) | Common issues and fixes |

### Contributing (Development)
| Document | Purpose |
|---|---|
| [contributing/requirements.md](contributing/requirements.md) | Prerequisites, hardware, platform support, model setup |
| [contributing/HOWTO-test.md](contributing/HOWTO-test.md) | Test philosophy, running tests, test patterns, CI/CD |

### Reference (Detailed Specs)
| Document | Purpose |
|---|---|
| [reference/command-guide.md](reference/command-guide.md) | PR comment commands syntax, lifecycle, examples |
| [reference/verdict-event-mapping.md](reference/verdict-event-mapping.md) | Verdict ↔ GitHub/Forgejo event mapping, danger zones |
| [reference/use-strict-fragment-selection.md](reference/use-strict-fragment-selection.md) | Fragment selection behavior and tuning |
| [reference/report-gaps-resolution.md](reference/report-gaps-resolution.md) | Multi-phase review gaps resolution report |

### Sub-Agents (Review Team)
| Document | Purpose |
|---|---|
| [sub-agents/README.md](sub-agents/README.md) | Sub-agent roles overview and runtime rules |
| [sub-agents/manager.md](sub-agents/manager.md) | Manager - plans, assigns, owns context |
| [sub-agents/advisor.md](sub-agents/advisor.md) | Advisor - grades every turn, interrupts drift |
| [sub-agents/engineer.md](sub-agents/engineer.md) | Engineer - bugs, security, quality |
| [sub-agents/architect.md](sub-agents/architect.md) | Architect - structure, coupling, patterns |
| [sub-agents/teacher.md](sub-agents/teacher.md) | Teacher - coaching layer, curriculum |

### Tokens
| Document | Purpose |
|---|---|
| [tokens/README.md](tokens/README.md) | Token types, env vars, auth headers |
| [tokens/github.md](tokens/github.md) | GitHub PAT creation, scopes, org overrides, verification |
| [tokens/codeberg.md](tokens/codeberg.md) | Codeberg/Forgejo token creation, scopes, verification |

---

## 🎯 Quick Start Paths

| Goal | Start Here |
|---|---|
| Run a review | [operations/HOWTO-single-review.md](operations/HOWTO-single-review.md) |
| Configure the app | [configuration/configuration.md](configuration/configuration.md) |
| Understand architecture | [architecture/structure.md](architecture/structure.md) → [architecture/diagrams/deep-architecture.md](architecture/diagrams/deep-architecture.md) |
| Set up tokens | [tokens/README.md](tokens/README.md) |
| Run tests | [contributing/HOWTO-test.md](contributing/HOWTO-test.md) |
| Debug a problem | [operations/troubleshooting.md](operations/troubleshooting.md) |

---

## 🔗 Cross-References

- **README.md** → [Project README](../README.md) (entry point, quick start)
- **AGENTS.md** → [Agent Rules](../AGENTS.md) (coding conventions, test rules)
- **CLAUDE.md** → [Claude Context](../CLAUDE.md) (project context for AI)
- **Makefile** → [Makefile](../Makefile) (available commands: `make help`)