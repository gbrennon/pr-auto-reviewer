# PR Auto Reviewer

AI-powered code review for Forgejo/Codeberg using local Ollama models.

## Getting Started

```bash
git clone https://codeberg.org/gbrennon/pr-auto-reviewer.git
cd pr-auto-reviewer
```

### 1. Environment Variables

Create `.env` in the project root:

```bash
cp .env.example .env
```

Edit `.env` with required variables. See [Configuration](docs/configuration.md) for all options.

### 2. Install & Run

```bash
make install
```

## Quick Commands

| Command | What it does |
|---------|--------------|
| `make test` | Run unit tests |
| `make watch` | Run watcher once (manual mode) |
| `make start` | Start the service |
| `make stop` | Stop the service |
| `make status` | Show service status |
| `make restart` | Restart the service |
| `make logs` | View service logs |
| `make clean` | Reset state files |

See [Scripts Reference](docs/scripts.md) for full command list.

## Requirements

- **Ollama** - Local AI inference. [Install](https://ollama.ai)
- **Forgejo or Codeberg** - Self-hosted or cloud
- **Two API tokens** - Owner and reviewer accounts
- **systemd** - For service management

See [Requirements](docs/requirements.md) for full details.

## Learn More

- [Configuration](docs/configuration.md) - All env vars explained
- [Scripts Reference](docs/scripts.md) - Available commands
- [Features](docs/features.md) - What's implemented
- [Structure](docs/structure.md) - How it works
- [Troubleshooting](docs/troubleshooting.md) - Common issues
- [Testing](docs/HOWTO-test.md) - How to test changes