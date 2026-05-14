# Phase 5: Presentation Layer - CLI & End-to-End Tests

**Prerequisites**: Phase 4 complete and all AC-4.x passing

**Goal**: Implement CLI interface with complete user workflow tests (NO MOCKS in E2E tests).

**Duration Estimate**: 3-4 hours

---

## Overview

This phase builds the **user-facing layer**:
- Command-line interface
- Configuration management
- Complete workflow orchestration
- End-to-end tests validating user stories

**CRITICAL E2E TESTING RULES:**
- ❌ **NO MOCKING** infrastructure or domain
- ✅ **TEST REAL WORKFLOWS** from CLI input to output
- ✅ **USE REAL FILES** and real fragments
- ✅ **VALIDATE USER EXPERIENCE** not implementation

---

## Part 1: CLI Command Structure

### Design: Subcommand Architecture

```bash
# Compose a review prompt
pr-review compose --language python --diff-file changes.diff

# List available fragments
pr-review fragments list --language python

# Validate fragment files
pr-review fragments validate

# Show version
pr-review --version
```

---

## Part 2: TDD Implementation - CLI

### TDD Iteration 5.1: Version Command

#### Step 1: Write Failing E2E Test (RED)

Create `tests/e2e/test_cli_workflows.py`:

```python
import subprocess
import sys
from pathlib import Path
import pytest


class TestCLIBasics:
    @pytest.fixture
    def cli_path(self) -> str:
        """Path to CLI entry point."""
        # Assumes CLI can be invoked via: python -m src.presentation.cli
        return f"{sys.executable} -m src.presentation.cli"
    
    def test_shows_version(self, cli_path):
        """CLI should display version when --version flag is used."""
        result = subprocess.run(
            f"{cli_path} --version",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "pr-review" in result.stdout.lower()
        assert result.stdout.strip() != ""
    
    def test_shows_help(self, cli_path):
        """CLI should display help when --help flag is used."""
        result = subprocess.run(
            f"{cli_path} --help",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "commands:" in result.stdout.lower()
        assert "compose" in result.stdout.lower()
```

**Run test (should FAIL):** No CLI module exists

---

#### Step 2: Write Minimal Code (GREEN)

Create `src/presentation/__init__.py` (empty)

Create `src/presentation/cli.py`:

```python
import argparse
import sys
from typing import Optional


__version__ = "0.1.0"


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="pr-review",
        description="AI-powered PR review using composable prompt fragments"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # compose subcommand
    compose_parser = subparsers.add_parser(
        "compose",
        help="Compose a review prompt from fragments"
    )
    compose_parser.add_argument(
        "--language",
        required=True,
        help="Programming language (e.g., python, go)"
    )
    compose_parser.add_argument(
        "--diff-file",
        required=True,
        type=str,
        help="Path to diff file"
    )
    compose_parser.add_argument(
        "--output",
        type=str,
        help="Output file (default: stdout)"
    )
    
    # fragments subcommand
    fragments_parser = subparsers.add_parser(
        "fragments",
        help="Manage fragments"
    )
    fragments_subparsers = fragments_parser.add_subparsers(
        dest="fragments_command",
        help="Fragment commands"
    )
    
    # fragments list
    list_parser = fragments_subparsers.add_parser(
        "list",
        help="List available fragments"
    )
    list_parser.add_argument(
        "--language",
        help="Filter by language"
    )
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv)
        
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == "compose":
            return compose_command(args)
        elif args.command == "fragments":
            return fragments_command(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def compose_command(args) -> int:
    """Handle compose command."""
    # TODO: Implement in next iteration
    print("Compose command not yet implemented", file=sys.stderr)
    return 1


def fragments_command(args) -> int:
    """Handle fragments command."""
    # TODO: Implement in next iteration
    print("Fragments command not yet implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Create `src/presentation/__main__.py`:

```python
from src.presentation.cli import main
import sys

sys.exit(main())
```

**Run test (should PASS)**

---

### TDD Iteration 5.2: Compose Command E2E

#### Step 1: Create Test Fixtures

```bash
mkdir -p tests/e2e/fixtures
```

Create `tests/e2e/fixtures/test.diff`:

```diff
diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,10 @@
 def process_data(data):
+    # TODO: Add validation
     try:
-        result = transform(data)
+        if not data:
+            raise ValueError("Data is empty")
+        result = transform(data)
         return result
     except:
         pass
```

---

#### Step 2: Write Failing E2E Test (RED)

```python
import tempfile
from pathlib import Path


class TestComposeWorkflow:
    @pytest.fixture
    def fragments_dir(self) -> Path:
        """Use real test fixtures from Phase 2."""
        return Path(__file__).parent.parent / "fixtures" / "fragments"
    
    @pytest.fixture
    def diff_file(self) -> Path:
        """Path to test diff file."""
        return Path(__file__).parent / "fixtures" / "test.diff"
    
    @pytest.fixture
    def cli_path(self) -> str:
        return f"{sys.executable} -m src.presentation.cli"
    
    def test_composes_prompt_from_diff(
        self,
        cli_path,
        diff_file,
        fragments_dir,
        tmp_path
    ):
        """E2E: User runs compose command and gets a prompt."""
        output_file = tmp_path / "prompt.txt"
        
        # Execute CLI command
        result = subprocess.run(
            f"{cli_path} compose "
            f"--language python "
            f"--diff-file {diff_file} "
            f"--output {output_file} "
            f"--fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        # Verify success
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        
        # Verify output file exists
        assert output_file.exists(), "Output file not created"
        
        # Verify prompt content
        prompt_content = output_file.read_text()
        
        # Should contain fragment content
        assert "Python Error Handling" in prompt_content
        assert "SOLID Principles" in prompt_content
        
        # Should contain diff
        assert "def process_data" in prompt_content
        assert "except:" in prompt_content
        
        # Should be structured markdown
        assert "# " in prompt_content  # Has headers
        assert "```" in prompt_content  # Has code blocks
    
    def test_outputs_to_stdout_by_default(
        self,
        cli_path,
        diff_file,
        fragments_dir
    ):
        """E2E: User can output to stdout instead of file."""
        result = subprocess.run(
            f"{cli_path} compose "
            f"--language python "
            f"--diff-file {diff_file} "
            f"--fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Python Error Handling" in result.stdout
        assert len(result.stdout) > 100  # Substantial output
    
    def test_fails_with_missing_diff_file(self, cli_path, fragments_dir):
        """E2E: Clear error when diff file doesn't exist."""
        result = subprocess.run(
            f"{cli_path} compose "
            f"--language python "
            f"--diff-file /nonexistent/file.diff "
            f"--fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()
    
    def test_fails_with_invalid_language(self, cli_path, diff_file, fragments_dir):
        """E2E: Clear error when no fragments for language."""
        result = subprocess.run(
            f"{cli_path} compose "
            f"--language brainfuck "
            f"--diff-file {diff_file} "
            f"--fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode != 0
        assert "no fragments" in result.stderr.lower() or "not found" in result.stderr.lower()
```

**Run tests (should FAIL)**

---

#### Step 3: Write Implementation (GREEN)

Update `cli.py`:

```python
from pathlib import Path
from src.infrastructure.repositories import FileSystemFragmentRepository
from src.infrastructure.renderers import Jinja2Renderer
from src.application.services import FragmentSelector, PromptComposer
from src.application.use_cases import ComposeReviewPromptUseCase
from src.domain.entities import ReviewContext


def compose_command(args) -> int:
    """Handle compose command.
    
    Workflow:
    1. Read diff file
    2. Create review context
    3. Load fragments
    4. Compose prompt
    5. Output result
    """
    try:
        # Read diff file
        diff_path = Path(args.diff_file)
        if not diff_path.exists():
            print(f"Error: Diff file not found: {diff_path}", file=sys.stderr)
            return 1
        
        diff_content = diff_path.read_text()
        
        # Determine fragments directory
        if hasattr(args, 'fragments_dir') and args.fragments_dir:
            fragments_dir = Path(args.fragments_dir)
        else:
            # Default: fragments/ in current directory
            fragments_dir = Path.cwd() / "fragments"
        
        if not fragments_dir.exists():
            print(f"Error: Fragments directory not found: {fragments_dir}", file=sys.stderr)
            return 1
        
        # Build dependency tree (hexagonal architecture)
        repository = FileSystemFragmentRepository(base_path=fragments_dir)
        renderer = Jinja2Renderer()
        selector = FragmentSelector(repository=repository)
        composer = PromptComposer(renderer=renderer)
        use_case = ComposeReviewPromptUseCase(
            selector=selector,
            composer=composer
        )
        
        # Create review context
        context = ReviewContext(
            language=args.language,
            file_paths=[str(diff_path)],  # Could parse from diff
            diff=diff_content
        )
        
        # Execute use case
        prompt = use_case.execute(context)
        
        # Output result
        if hasattr(args, 'output') and args.output:
            output_path = Path(args.output)
            output_path.write_text(prompt.content)
            print(f"Prompt written to: {output_path}")
        else:
            print(prompt.content)
        
        return 0
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# Update main to add fragments_dir argument
def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="pr-review",
        description="AI-powered PR review using composable prompt fragments"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # compose subcommand
    compose_parser = subparsers.add_parser(
        "compose",
        help="Compose a review prompt from fragments"
    )
    compose_parser.add_argument(
        "--language",
        required=True,
        help="Programming language (e.g., python, go)"
    )
    compose_parser.add_argument(
        "--diff-file",
        required=True,
        type=str,
        help="Path to diff file"
    )
    compose_parser.add_argument(
        "--output",
        type=str,
        help="Output file (default: stdout)"
    )
    compose_parser.add_argument(
        "--fragments-dir",
        type=str,
        help="Fragments directory (default: ./fragments)"
    )
    
    # ... rest of parser definition ...
    
    return parser
```

**Run tests (should PASS)**

---

### TDD Iteration 5.3: Fragments List Command

#### Step 1: Write Failing Test (RED)

```python
class TestFragmentsWorkflow:
    @pytest.fixture
    def cli_path(self) -> str:
        return f"{sys.executable} -m src.presentation.cli"
    
    @pytest.fixture
    def fragments_dir(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "fragments"
    
    def test_lists_all_fragments(self, cli_path, fragments_dir):
        """E2E: User lists all available fragments."""
        result = subprocess.run(
            f"{cli_path} fragments list --fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # Should show fragment IDs
        assert "python-error-handling" in result.stdout
        assert "go-concurrency" in result.stdout
        assert "solid-principles" in result.stdout
        
        # Should show metadata
        assert "python" in result.stdout
        assert "priority" in result.stdout.lower() or "80" in result.stdout
    
    def test_lists_fragments_for_specific_language(self, cli_path, fragments_dir):
        """E2E: User filters fragments by language."""
        result = subprocess.run(
            f"{cli_path} fragments list --language python --fragments-dir {fragments_dir}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "python-error-handling" in result.stdout
        assert "go-concurrency" not in result.stdout  # Filtered out
```

**Run tests (should FAIL)**

---

#### Step 2: Write Implementation (GREEN)

Update `cli.py`:

```python
def fragments_command(args) -> int:
    """Handle fragments command."""
    if not hasattr(args, 'fragments_command') or not args.fragments_command:
        print("Error: No fragments subcommand specified", file=sys.stderr)
        return 1
    
    try:
        # Determine fragments directory
        if hasattr(args, 'fragments_dir') and args.fragments_dir:
            fragments_dir = Path(args.fragments_dir)
        else:
            fragments_dir = Path.cwd() / "fragments"
        
        if not fragments_dir.exists():
            print(f"Error: Fragments directory not found: {fragments_dir}", file=sys.stderr)
            return 1
        
        repository = FileSystemFragmentRepository(base_path=fragments_dir)
        
        if args.fragments_command == "list":
            return list_fragments(repository, args)
        else:
            print(f"Unknown fragments command: {args.fragments_command}", file=sys.stderr)
            return 1
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def list_fragments(repository: FileSystemFragmentRepository, args) -> int:
    """List available fragments.
    
    Args:
        repository: Fragment repository
        args: CLI arguments
        
    Returns:
        Exit code
    """
    try:
        # Get fragments
        if hasattr(args, 'language') and args.language:
            fragments = repository.find_by_language(args.language)
            print(f"\nFragments for {args.language}:")
        else:
            # List all languages
            all_fragments = []
            for lang_dir in repository.base_path.iterdir():
                if lang_dir.is_dir():
                    lang = lang_dir.name
                    if lang == "universal":
                        all_fragments.extend(repository.find_universal())
                    else:
                        all_fragments.extend(repository.find_by_language(lang))
            fragments = all_fragments
            print("\nAll fragments:")
        
        if not fragments:
            print("No fragments found.")
            return 0
        
        # Display fragments
        print()
        for fragment in sorted(fragments, key=lambda f: (f.language or "universal", f.priority), reverse=True):
            lang_display = fragment.language or "universal"
            print(f"  {fragment.id}")
            print(f"    Language:  {lang_display}")
            print(f"    Priority:  {fragment.priority}")
            print(f"    Category:  {fragment.category}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"Error listing fragments: {e}", file=sys.stderr)
        return 1


# Update parser to add fragments-dir to list command
def create_parser() -> argparse.ArgumentParser:
    # ... previous code ...
    
    # fragments list
    list_parser = fragments_subparsers.add_parser(
        "list",
        help="List available fragments"
    )
    list_parser.add_argument(
        "--language",
        help="Filter by language"
    )
    list_parser.add_argument(
        "--fragments-dir",
        type=str,
        help="Fragments directory (default: ./fragments)"
    )
    
    return parser
```

**Run tests (should PASS)**

---

## Part 3: Configuration File Support

### TDD Iteration 5.4: Config File

#### Step 1: Write Failing Test (RED)

Create `tests/e2e/fixtures/pr-review.yaml`:

```yaml
fragments_dir: tests/fixtures/fragments
max_tokens: 4000
language: python
```

Add test:

```python
def test_loads_config_from_file(self, cli_path, diff_file, tmp_path):
    """E2E: User can configure via YAML file."""
    config_file = tmp_path / "pr-review.yaml"
    config_file.write_text(f"""
fragments_dir: {Path(__file__).parent.parent / 'fixtures' / 'fragments'}
max_tokens: 4000
""")
    
    result = subprocess.run(
        f"{cli_path} --config {config_file} compose "
        f"--language python "
        f"--diff-file {diff_file}",
        shell=True,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Python Error Handling" in result.stdout
```

**Run test (should FAIL)**

---

#### Step 2: Write Implementation (GREEN)

Update `cli.py`:

```python
import yaml


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from file.
    
    Args:
        config_path: Path to config file (if None, looks for default locations)
        
    Returns:
        Configuration dictionary
    """
    if config_path and config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    
    # Look for default locations
    default_paths = [
        Path.cwd() / "pr-review.yaml",
        Path.cwd() / ".pr-review.yaml",
        Path.home() / ".config" / "pr-review" / "config.yaml"
    ]
    
    for path in default_paths:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
    
    return {}


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="pr-review",
        description="AI-powered PR review using composable prompt fragments"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file (YAML)"
    )
    
    # ... rest of parser ...
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Load config
    config_path = Path(args.config) if hasattr(args, 'config') and args.config else None
    config = load_config(config_path)
    
    # Merge config with args (args take precedence)
    if config:
        for key, value in config.items():
            if not hasattr(args, key) or getattr(args, key) is None:
                setattr(args, key, value)
    
    # ... rest of main ...
```

**Run test (should PASS)**

---

## Part 4: Run Full E2E Test Suite

```bash
# Run E2E tests (these are slow, use real I/O)
poetry run pytest tests/e2e/ -v -s

# Run all tests
poetry run pytest -v

# Generate coverage report
poetry run pytest --cov=src --cov-report=html --cov-report=term
```

---

## Acceptance Criteria (Phase 5)

### ✅ AC-5.1: CLI Commands Work
- [ ] `pr-review --version` shows version
- [ ] `pr-review --help` shows usage
- [ ] `pr-review compose` generates prompts
- [ ] `pr-review fragments list` lists fragments

### ✅ AC-5.2: E2E Tests Validate User Workflows
- [ ] Tests use REAL CLI invocation (subprocess)
- [ ] Tests use REAL fragments from fixtures
- [ ] Tests validate COMPLETE workflows (input → output)
- [ ] NO MOCKS in E2E tests
- [ ] All E2E tests pass: `pytest tests/e2e/ -v`

### ✅ AC-5.3: Error Handling
- [ ] Clear error message for missing diff file
- [ ] Clear error message for invalid language
- [ ] Clear error message for missing fragments directory
- [ ] Non-zero exit code on errors

### ✅ AC-5.4: Configuration
- [ ] Can load config from YAML file
- [ ] CLI args override config file
- [ ] Fragments directory configurable
- [ ] Default config locations work

---

## Phase 5 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 6 IF:**

1. ✅ All AC-5.x criteria are met
2. ✅ E2E tests pass and use real I/O
3. ✅ CLI is usable from command line
4. ✅ Error messages are helpful
5. ✅ Configuration system works

**Verification Commands:**
```bash
# Install package in dev mode
poetry install

# Test CLI directly
poetry run python -m src.presentation.cli --version
poetry run python -m src.presentation.cli --help

# Run E2E tests
poetry run pytest tests/e2e/ -v

# Manual smoke test
echo "+def foo(): pass" > /tmp/test.diff
poetry run python -m src.presentation.cli compose \
  --language python \
  --diff-file /tmp/test.diff \
  --fragments-dir tests/fixtures/fragments
```

---

## Next Phase Preview

**Phase 6** will implement:
- LLM integration (Ollama adapter)
- GitHub/Forgejo PR fetching
- Complete review workflow
- Production-ready features

**DO NOT START PHASE 6 UNTIL ALL PHASE 5 CRITERIA ARE MET.**
