# Phase 6: LLM Integration & Production Features

**Prerequisites**: Phase 5 complete and all AC-5.x passing

**Goal**: Integrate with Ollama LLM and add production-ready features for complete PR review workflow.

**Duration Estimate**: 3-4 hours

---

## Overview

This final phase completes the system with:
- LLM integration (Ollama adapter)
- PR fetching (GitHub/Forgejo/Codeberg)
- Complete review workflow (fetch PR → compose prompt → send to LLM → output review)
- Production features (logging, retries, streaming)

---

## Part 1: LLM Port & Ollama Adapter

### TDD Iteration 6.1: LLM Port Definition

#### Step 1: Write Test (RED)

Create `tests/unit/domain/test_llm_port.py`:

```python
import pytest
from typing import Protocol
from src.domain.ports import LLMProvider


class TestLLMProviderProtocol:
    def test_is_protocol(self):
        """LLMProvider should be a Protocol (interface)."""
        assert issubclass(LLMProvider, Protocol)
    
    def test_has_generate_method(self):
        """LLMProvider must define generate method."""
        import inspect
        sig = inspect.signature(LLMProvider.generate)
        params = list(sig.parameters.keys())
        
        assert 'prompt' in params
        assert sig.return_annotation == str
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Add to `src/domain/ports.py`:

```python
class LLMProvider(Protocol):
    """Port for LLM inference.
    
    Implementations might use Ollama, OpenAI, Anthropic, or local models.
    """
    
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate a review from the prompt.
        
        Args:
            prompt: Complete review prompt
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated review text
            
        Raises:
            ConnectionError: If LLM service is unavailable
            ValueError: If generation fails
        """
        ...
```

**Run test (should PASS)**

---

### TDD Iteration 6.2: Ollama Adapter

#### Step 1: Write Failing Integration Test (RED)

Create `tests/integration/infrastructure/test_ollama_adapter.py`:

```python
import pytest
import requests
from src.infrastructure.llm import OllamaAdapter


class TestOllamaAdapter:
    @pytest.fixture
    def ollama_available(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    @pytest.fixture
    def adapter(self) -> OllamaAdapter:
        """Create Ollama adapter."""
        return OllamaAdapter(
            base_url="http://localhost:11434",
            model="llama3.2:3b"  # Small model for testing
        )
    
    def test_creates_adapter_with_config(self):
        """Adapter should initialize with configuration."""
        adapter = OllamaAdapter(
            base_url="http://localhost:11434",
            model="codellama"
        )
        
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.model == "codellama"
    
    @pytest.mark.skipif(
        not pytest.ollama_available,
        reason="Ollama not running locally"
    )
    def test_generates_review_from_prompt(self, adapter, ollama_available):
        """Adapter should generate review using Ollama.
        
        NOTE: This is a REAL integration test - it calls actual Ollama API.
        Skip if Ollama is not running.
        """
        if not ollama_available:
            pytest.skip("Ollama not available")
        
        prompt = """
# Code Review

Review this Python code for error handling issues:

```python
def process_data(data):
    try:
        result = transform(data)
        return result
    except:
        pass
```

Identify the problems and suggest fixes.
"""
        
        # Execute
        review = adapter.generate(prompt, max_tokens=500)
        
        # Verify
        assert isinstance(review, str)
        assert len(review) > 50  # Should be substantial
        assert "except" in review.lower()  # Should mention the issue
    
    def test_handles_connection_error(self):
        """Adapter should raise clear error when Ollama is unavailable."""
        adapter = OllamaAdapter(
            base_url="http://localhost:99999",  # Invalid port
            model="codellama"
        )
        
        with pytest.raises(ConnectionError, match="Ollama.*unavailable"):
            adapter.generate("test prompt")
```

**Run test (should FAIL)**

---

#### Step 2: Write Implementation (GREEN)

Add dependency:
```bash
poetry add requests
```

Create `src/infrastructure/llm.py`:

```python
import requests
from typing import Optional


class OllamaAdapter:
    """Adapter for Ollama LLM API.
    
    Connects to local or remote Ollama instance for code review generation.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "codellama",
        timeout: int = 120
    ):
        """Initialize Ollama adapter.
        
        Args:
            base_url: Ollama API base URL
            model: Model name (e.g., "codellama", "llama3.2")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
    
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate a review from the prompt.
        
        Args:
            prompt: Complete review prompt
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated review text
            
        Raises:
            ConnectionError: If Ollama service is unavailable
            ValueError: If generation fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    }
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
            
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Ollama service unavailable at {self.base_url}. "
                f"Is Ollama running? Error: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise ConnectionError(
                f"Ollama request timed out after {self.timeout}s"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Ollama generation failed: {e}") from e
    
    def check_health(self) -> bool:
        """Check if Ollama service is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
```

**Run test (should PASS if Ollama is running, SKIP otherwise)**

---

## Part 2: PR Fetching Adapters

### TDD Iteration 6.3: GitHub PR Adapter

#### Step 1: Define Port

Add to `src/domain/ports.py`:

```python
@dataclass(frozen=True)
class PullRequest:
    """Value object representing a pull request."""
    number: int
    title: str
    diff: str
    file_paths: list[str]
    repository: str
    author: str


class PRProvider(Protocol):
    """Port for fetching pull request data.
    
    Implementations might fetch from GitHub, GitLab, Forgejo, etc.
    """
    
    def fetch_pr(self, repo: str, pr_number: int) -> PullRequest:
        """Fetch pull request data.
        
        Args:
            repo: Repository identifier (e.g., "owner/repo")
            pr_number: Pull request number
            
        Returns:
            PullRequest with diff and metadata
            
        Raises:
            ValueError: If PR not found or invalid
            ConnectionError: If API is unavailable
        """
        ...
```

---

#### Step 2: Write Failing Integration Test (RED)

Create `tests/integration/infrastructure/test_github_adapter.py`:

```python
import pytest
import os
from src.infrastructure.git_providers import GitHubAdapter


class TestGitHubAdapter:
    @pytest.fixture
    def github_token(self) -> str:
        """Get GitHub token from environment."""
        return os.getenv("GITHUB_TOKEN", "")
    
    @pytest.fixture
    def adapter(self, github_token) -> GitHubAdapter:
        """Create GitHub adapter."""
        return GitHubAdapter(token=github_token)
    
    @pytest.mark.skipif(
        not os.getenv("GITHUB_TOKEN"),
        reason="GITHUB_TOKEN not set"
    )
    def test_fetches_public_pr(self, adapter):
        """Adapter should fetch PR from public repository.
        
        Uses a known stable PR for testing.
        """
        # Use a closed PR from a stable project
        pr = adapter.fetch_pr("python/cpython", 1)  # Very old PR, stable
        
        assert pr.number == 1
        assert pr.title != ""
        assert pr.diff != ""
        assert len(pr.file_paths) > 0
        assert pr.repository == "python/cpython"
    
    def test_handles_invalid_pr_number(self, adapter):
        """Adapter should raise error for non-existent PR."""
        with pytest.raises(ValueError, match="PR.*not found"):
            adapter.fetch_pr("python/cpython", 9999999)
```

**Run test (should FAIL)**

---

#### Step 3: Write Implementation (GREEN)

Create `src/infrastructure/git_providers.py`:

```python
import requests
from typing import Optional
from src.domain.ports import PullRequest


class GitHubAdapter:
    """Adapter for GitHub API to fetch pull requests."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize GitHub adapter.
        
        Args:
            token: Optional GitHub personal access token
        """
        self.token = token
        self.base_url = "https://api.github.com"
    
    def fetch_pr(self, repo: str, pr_number: int) -> PullRequest:
        """Fetch pull request data from GitHub.
        
        Args:
            repo: Repository in "owner/repo" format
            pr_number: Pull request number
            
        Returns:
            PullRequest with diff and metadata
        """
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        
        try:
            # Fetch PR metadata
            pr_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
            pr_response = requests.get(pr_url, headers=headers)
            pr_response.raise_for_status()
            pr_data = pr_response.json()
            
            # Fetch PR diff
            diff_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
            diff_headers = headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            diff_response = requests.get(diff_url, headers=diff_headers)
            diff_response.raise_for_status()
            
            # Fetch changed files
            files_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
            files_response = requests.get(files_url, headers=headers)
            files_response.raise_for_status()
            files_data = files_response.json()
            
            return PullRequest(
                number=pr_number,
                title=pr_data["title"],
                diff=diff_response.text,
                file_paths=[f["filename"] for f in files_data],
                repository=repo,
                author=pr_data["user"]["login"]
            )
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"PR #{pr_number} not found in {repo}")
            raise
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"GitHub API error: {e}") from e


class ForgejoAdapter:
    """Adapter for Forgejo/Gitea API to fetch pull requests."""
    
    def __init__(self, base_url: str, token: Optional[str] = None):
        """Initialize Forgejo adapter.
        
        Args:
            base_url: Forgejo instance URL (e.g., "https://codeberg.org")
            token: Optional API token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
    
    def fetch_pr(self, repo: str, pr_number: int) -> PullRequest:
        """Fetch pull request from Forgejo/Gitea instance."""
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        
        try:
            # Forgejo API is compatible with Gitea
            api_base = f"{self.base_url}/api/v1"
            pr_url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
            
            pr_response = requests.get(pr_url, headers=headers)
            pr_response.raise_for_status()
            pr_data = pr_response.json()
            
            # Fetch diff
            diff_url = f"{pr_url}.diff"
            diff_response = requests.get(diff_url, headers=headers)
            diff_response.raise_for_status()
            
            # Fetch files
            files_url = f"{pr_url}/files"
            files_response = requests.get(files_url, headers=headers)
            files_response.raise_for_status()
            files_data = files_response.json()
            
            return PullRequest(
                number=pr_number,
                title=pr_data["title"],
                diff=diff_response.text,
                file_paths=[f["filename"] for f in files_data],
                repository=repo,
                author=pr_data["user"]["login"]
            )
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"PR #{pr_number} not found")
            raise
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Forgejo API error: {e}") from e
```

**Run test (should PASS with GITHUB_TOKEN, SKIP otherwise)**

---

## Part 3: Complete Review Workflow Use Case

### TDD Iteration 6.4: Review PR Use Case

#### Step 1: Write Failing Test (RED)

Create `tests/unit/application/test_review_use_case.py`:

```python
import pytest
from unittest.mock import Mock
from src.application.use_cases import ReviewPRUseCase
from src.domain.ports import PRProvider, LLMProvider, FragmentRepository
from src.domain.entities import PullRequest


class TestReviewPRUseCase:
    @pytest.fixture
    def mock_pr_provider(self) -> Mock:
        return Mock(spec=PRProvider)
    
    @pytest.fixture
    def mock_llm(self) -> Mock:
        return Mock(spec=LLMProvider)
    
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(spec=FragmentRepository)
    
    @pytest.fixture
    def use_case(
        self,
        mock_pr_provider,
        mock_llm,
        mock_repository
    ) -> ReviewPRUseCase:
        from src.application.services import FragmentSelector, PromptComposer
        
        selector = FragmentSelector(repository=mock_repository)
        composer = PromptComposer()
        
        return ReviewPRUseCase(
            pr_provider=mock_pr_provider,
            llm=mock_llm,
            selector=selector,
            composer=composer
        )
    
    def test_reviews_pull_request_end_to_end(
        self,
        use_case,
        mock_pr_provider,
        mock_llm,
        mock_repository
    ):
        """Use case should orchestrate: fetch PR → compose prompt → generate review."""
        # Setup mocks
        pr = PullRequest(
            number=123,
            title="Fix error handling",
            diff="+def foo():\n+    try:\n+        pass\n+    except:\n+        pass",
            file_paths=["main.py"],
            repository="user/repo",
            author="developer"
        )
        mock_pr_provider.fetch_pr.return_value = pr
        
        mock_repository.find_by_language.return_value = [
            PromptFragment(
                id="python-errors",
                content="Check errors: {{code}}",
                language="python",
                priority=80,
                category="errors"
            )
        ]
        mock_repository.find_universal.return_value = []
        
        mock_llm.generate.return_value = "Review: The bare except clause is problematic..."
        
        # Execute
        review = use_case.execute(repo="user/repo", pr_number=123, language="python")
        
        # Verify workflow
        mock_pr_provider.fetch_pr.assert_called_once_with("user/repo", 123)
        mock_repository.find_by_language.assert_called_once_with("python")
        mock_llm.generate.assert_called_once()
        
        # Verify output
        assert "bare except" in review.lower()
        assert len(review) > 20
```

**Run test (should FAIL)**

---

#### Step 2: Write Implementation (GREEN)

Add to `src/application/use_cases.py`:

```python
from src.domain.ports import PRProvider, LLMProvider


class ReviewPRUseCase:
    """Use case for reviewing a pull request end-to-end.
    
    Orchestrates:
    1. Fetch PR from provider (GitHub/Forgejo)
    2. Detect language from file paths
    3. Select fragments
    4. Compose prompt
    5. Generate review with LLM
    6. Return review text
    """
    
    def __init__(
        self,
        pr_provider: PRProvider,
        llm: LLMProvider,
        selector: FragmentSelector,
        composer: PromptComposer
    ):
        """Initialize use case.
        
        Args:
            pr_provider: PR fetching port
            llm: LLM generation port
            selector: Fragment selection service
            composer: Prompt composition service
        """
        self._pr_provider = pr_provider
        self._llm = llm
        self._selector = selector
        self._composer = composer
    
    def execute(
        self,
        repo: str,
        pr_number: int,
        language: str
    ) -> str:
        """Execute complete PR review workflow.
        
        Args:
            repo: Repository identifier (e.g., "owner/repo")
            pr_number: Pull request number
            language: Programming language for fragment selection
            
        Returns:
            Generated review text
            
        Raises:
            ValueError: If PR not found or review generation fails
            ConnectionError: If PR provider or LLM unavailable
        """
        # Step 1: Fetch PR
        pr = self._pr_provider.fetch_pr(repo, pr_number)
        
        # Step 2: Create review context
        context = ReviewContext(
            language=language,
            file_paths=pr.file_paths,
            diff=pr.diff
        )
        
        # Step 3: Compose prompt
        prompt = self._selector.select_for(context)
        composed = self._composer.compose(prompt, context)
        
        # Step 4: Generate review
        review = self._llm.generate(composed.content)
        
        return review
```

**Run test (should PASS)**

---

## Part 4: CLI Integration

### Add Review Command to CLI

Update `src/presentation/cli.py`:

```python
def create_parser() -> argparse.ArgumentParser:
    # ... existing code ...
    
    # review subcommand (new)
    review_parser = subparsers.add_parser(
        "review",
        help="Review a pull request"
    )
    review_parser.add_argument(
        "--repo",
        required=True,
        help="Repository (e.g., owner/repo)"
    )
    review_parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="Pull request number"
    )
    review_parser.add_argument(
        "--language",
        required=True,
        help="Programming language"
    )
    review_parser.add_argument(
        "--provider",
        choices=["github", "forgejo"],
        default="github",
        help="Git provider"
    )
    review_parser.add_argument(
        "--ollama-model",
        default="codellama",
        help="Ollama model name"
    )
    
    return parser


def review_command(args) -> int:
    """Handle review command."""
    try:
        # Build adapters
        if args.provider == "github":
            import os
            pr_provider = GitHubAdapter(token=os.getenv("GITHUB_TOKEN"))
        else:  # forgejo
            forgejo_url = os.getenv("FORGEJO_URL", "https://codeberg.org")
            pr_provider = ForgejoAdapter(
                base_url=forgejo_url,
                token=os.getenv("FORGEJO_TOKEN")
            )
        
        llm = OllamaAdapter(model=args.ollama_model)
        
        fragments_dir = Path(args.fragments_dir) if hasattr(args, 'fragments_dir') else Path.cwd() / "fragments"
        repository = FileSystemFragmentRepository(base_path=fragments_dir)
        renderer = Jinja2Renderer()
        
        selector = FragmentSelector(repository=repository)
        composer = PromptComposer(renderer=renderer)
        
        use_case = ReviewPRUseCase(
            pr_provider=pr_provider,
            llm=llm,
            selector=selector,
            composer=composer
        )
        
        # Execute review
        print(f"Fetching PR #{args.pr} from {args.repo}...")
        review = use_case.execute(
            repo=args.repo,
            pr_number=args.pr,
            language=args.language
        )
        
        print("\n" + "="*60)
        print("REVIEW")
        print("="*60 + "\n")
        print(review)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
```

---

## Part 5: E2E Test for Complete Workflow

Create `tests/e2e/test_complete_workflow.py`:

```python
import pytest
import subprocess
import sys
import os
from pathlib import Path


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN") or not Path("/usr/bin/ollama").exists(),
    reason="Requires GITHUB_TOKEN and Ollama installed"
)
class TestCompleteReviewWorkflow:
    """End-to-end tests for complete PR review workflow.
    
    These tests require:
    - GITHUB_TOKEN environment variable
    - Ollama running locally
    - Internet connection
    """
    
    def test_reviews_real_github_pr(self):
        """Complete workflow: GitHub PR → fragments → Ollama → review output."""
        cli_path = f"{sys.executable} -m src.presentation.cli"
        fragments_dir = Path(__file__).parent.parent / "fixtures" / "fragments"
        
        # Use a known stable closed PR
        result = subprocess.run(
            f"{cli_path} review "
            f"--repo python/cpython "
            f"--pr 1 "
            f"--language python "
            f"--provider github "
            f"--fragments-dir {fragments_dir} "
            f"--ollama-model llama3.2:3b",
            shell=True,
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes
        )
        
        # Should succeed
        assert result.returncode == 0, f"Failed: {result.stderr}"
        
        # Should contain review content
        assert "REVIEW" in result.stdout
        assert len(result.stdout) > 200  # Substantial output
```

---

## Part 6: Production Features

### Logging Configuration

Create `src/infrastructure/logging.py`:

```python
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
```

### Add to CLI:

```python
def create_parser():
    # ... existing code ...
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Setup logging
    from src.infrastructure.logging import setup_logging
    setup_logging(args.log_level)
    
    # ... rest of main ...
```

---

## Acceptance Criteria (Phase 6)

### ✅ AC-6.1: LLM Integration
- [ ] `OllamaAdapter` implements `LLMProvider` port
- [ ] Generates reviews from prompts
- [ ] Handles connection errors gracefully
- [ ] Integration tests pass (if Ollama available)

### ✅ AC-6.2: PR Fetching
- [ ] `GitHubAdapter` fetches PRs from GitHub
- [ ] `ForgejoAdapter` fetches PRs from Forgejo/Codeberg
- [ ] Handles API errors gracefully
- [ ] Integration tests pass (if tokens available)

### ✅ AC-6.3: Complete Workflow
- [ ] `ReviewPRUseCase` orchestrates full workflow
- [ ] CLI `review` command works
- [ ] E2E test validates complete flow
- [ ] Logging configured

### ✅ AC-6.4: Production Ready
- [ ] Error messages are helpful
- [ ] Timeouts configured
- [ ] Retries on transient failures (optional)
- [ ] Documentation updated

---

## Phase 6 Exit Criteria

**SYSTEM IS COMPLETE WHEN:**

1. ✅ All AC-6.x criteria are met
2. ✅ All tests pass (unit + integration + E2E)
3. ✅ CLI works for all commands
4. ✅ Complete workflow tested end-to-end
5. ✅ Production features implemented

**Verification Commands:**
```bash
# Full test suite
poetry run pytest -v

# Test with real Ollama (if available)
poetry run pytest tests/integration/infrastructure/test_ollama_adapter.py -v -s

# Manual end-to-end test
export GITHUB_TOKEN=your_token
poetry run python -m src.presentation.cli review \
  --repo python/cpython \
  --pr 1 \
  --language python \
  --provider github
```

---

## Final Deliverables Checklist

### Code Quality
- [ ] All layers follow hexagonal architecture
- [ ] Zero SOLID violations
- [ ] 90%+ test coverage
- [ ] All tests pass

### Testing
- [ ] Unit tests (domain + application) - fast, mocked
- [ ] Integration tests (infrastructure) - real I/O, no mocks
- [ ] E2E tests (presentation) - complete workflows

### Documentation
- [ ] README with usage examples
- [ ] Architecture diagram
- [ ] Fragment authoring guide
- [ ] Configuration reference

### Production
- [ ] CLI is usable
- [ ] Error handling is robust
- [ ] Logging configured
- [ ] Configuration flexible

---

## Congratulations! 🎉

You have successfully implemented a **production-ready PR review agent** using:
- ✅ **Hexagonal Architecture** (ports & adapters)
- ✅ **SOLID Principles** throughout
- ✅ **Religious TDD** (test-first always)
- ✅ **Proper test layers** (unit, integration, E2E)
- ✅ **Composable prompt fragments** (extensible)
- ✅ **Real integrations** (GitHub, Forgejo, Ollama)

**The system is decoupled, testable, and maintainable.**

---

## Next Steps (Optional Enhancements)

Consider these future improvements:
- Token counting with tiktoken for accuracy
- Streaming LLM responses
- Parallel fragment selection
- Fragment analytics (which are most useful)
- GitHub Actions integration
- Web UI for fragment management
- Multi-language detection from diffs
- Review quality metrics
