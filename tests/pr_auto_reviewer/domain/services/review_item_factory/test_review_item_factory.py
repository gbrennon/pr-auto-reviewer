from ._helpers import *


class TestReviewItemFactory:
    """Tests for ReviewItemFactory domain service."""

    def test_extract_backticked_symbols(self) -> None:
        """Test extracting backticked symbol names."""
        result = ReviewItemFactory._extract_symbols(
            "Refer to `get_user` function"
        )
        assert "get_user" in result

    def test_extract_candidate_symbols(self) -> None:
        """Test extracting candidate symbols from description."""
        result = ReviewItemFactory._extract_symbols(
            "function process_data() failed"
        )
        assert len(result) > 0

    def test_filter_symbols_min_length(self) -> None:
        """Test that symbols shorter than 2 chars are filtered out."""
        result = ReviewItemFactory._extract_symbols("a b c")
        assert all(len(s) > 1 for s in result)

    def test_generate_id_format(self) -> None:
        """Test generated ID format."""
        result = ReviewItemFactory.generate_id()
        assert len(result) == 6
        int(result, 16)

        # Method no longer accepts repo/pr params - always returns short format
        result_without_params = ReviewItemFactory.generate_id()
        assert len(result_without_params) == 6
        int(result_without_params, 16)

    @staticmethod
    def _fake_uuid7(ints: list[int]):
        import itertools

        class _FakeUuid:
            def __init__(self, value: int) -> None:
                self.int = value

        values = itertools.cycle(ints)
        return lambda: _FakeUuid(next(values))

    def test_generate_id_derives_randomness_from_low_bits(
        self, monkeypatch,
    ) -> None:
        """High uuid7 bits are a timestamp; only low bits are random."""
        import pr_auto_reviewer.domain.services.review_item_factory as mod

        high_timestamp_low_random = 0x1A0300000000000000000000000000AB
        monkeypatch.setattr(
            mod._uuid, "uuid7",
            self._fake_uuid7([high_timestamp_low_random]),
        )
        ReviewItemFactory._id_counter = 0

        generated = ReviewItemFactory.generate_id()

        assert generated.endswith("ab01")
        assert not generated.startswith("1a03")

    def test_fresh_process_state_produces_disjoint_ids(
        self, monkeypatch,
    ) -> None:
        """Two runs must never emit the same ID sequence."""
        import pr_auto_reviewer.domain.services.review_item_factory as mod

        def _fake_uuid7_for(values):
            iterator = iter(values)

            class _FakeItem:
                def __init__(self, value: int) -> None:
                    self.int = value

            return lambda: _FakeItem(next(iterator))

        batches = []
        for lows in ([0x1000 + i for i in range(5)],
                     [0x2000 + i for i in range(5)]):
            monkeypatch.setattr(
                mod._uuid, "uuid7",
                _fake_uuid7_for(lows),
            )
            ReviewItemFactory._id_counter = 0
            batches.append(
                [ReviewItemFactory.generate_id() for _ in range(5)]
            )

        first_run_ids = set(batches[0])
        second_run_ids = set(batches[1])

        assert len(first_run_ids) == 5
        assert len(second_run_ids) == 5
        assert first_run_ids.isdisjoint(second_run_ids)

    def test_resolve_exact_path(self) -> None:
        """Test resolving an exact repo-relative path."""
        with Path("/tmp/test_resolve.py").open("w") as f:
            f.write("x = 1\n")

        try:
            result_path, _result_str = ReviewItemFactory._resolve_file_path(
                "test_resolve.py", Path("/tmp"), ["test_resolve.py"]
            )
            assert result_path is not None
            assert _result_str == "test_resolve.py"
        finally:
            Path("/tmp/test_resolve.py").unlink(missing_ok=True)

    def test_resolve_partial_path(self) -> None:
        """Test resolving a partial path against changed files."""
        os.makedirs("/tmp/pkg", exist_ok=True)
        with Path("/tmp/pkg/module.py").open("w") as f:
            f.write("y = 2\n")

        with Path("/tmp/main.py").open("w") as f:
            f.write("z = 3\n")

        try:
            _result_path, _result_str = ReviewItemFactory._resolve_file_path(
                "module.py", Path("/tmp"), ["module.py"]
            )
            assert _result_str == "module.py"
        finally:
            Path("/tmp/pkg/module.py").unlink(missing_ok=True)
            Path("/tmp/main.py").unlink(missing_ok=True)
            os.rmdir("/tmp/pkg")

    def test_unresolvable_path(self) -> None:
        """Test that unresolvable paths return None."""
        result_path, _result_str = ReviewItemFactory._resolve_file_path(
            "nonexistent.py", Path("/tmp"), ["other.py"]
        )
        assert result_path is None

    def test_create_with_valid_items(self) -> None:
        """Test creating ReviewItems from valid dicts."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "Test finding",
                "severity": "minor",
                "category": "bug",
                "current_code": "x = 1",
                "suggested_fix": "x = 2",
            }
        ]

        repo_path = "/tmp/test_repo"
        changed_files = ["src/main.py"]

        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, changed_files
            )
            assert len(items) == 1
            assert len(skip_reasons) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_skips_non_dict(self) -> None:
        """Test that non-dict items are skipped with warning."""
        item_dicts = ["not a dict", 123, None]

        with patch("pr_auto_reviewer.domain.services.review_item_factory.logger.warning") as mock_warn:
            items, _skip_reasons = ReviewItemFactory.create(
                item_dicts, "/tmp", None
            )
            assert len(items) == 0
            assert mock_warn.call_count >= 1

    def test_create_skips_empty_description(self) -> None:
        """Test that items without description are skipped when file_path exists."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo2"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_fabricated_narrative(self) -> None:
        """Test that fabricated error patterns are detected."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "file not found: cannot access the module",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo3"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_with_missing_file(self) -> None:
        """Test that items with missing files are skipped."""
        item_dicts = [
            {
                "file": "src/nonexistent.py",
                "description": "Test finding",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo4"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_generates_ids(self) -> None:
        """Test that each item gets a unique ID."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "Finding 1",
                "severity": "minor",
                "category": "bug",
            },
            {
                "file": "src/main.py",
                "description": "Finding 2",
                "severity": "major",
                "category": "quality",
            },
        ]

        repo_path = "/tmp/test_repo5"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, _skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(items) == 2
            item_ids = [item.id for item in items]
            assert len(set(item_ids)) == 2, f"Expected 2 unique IDs, got {item_ids}"
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_preserves_fields(self) -> None:
        """Test that file_path, description, severity, category are preserved."""
        item_dicts = [
            {
                "file": "src/client.py",
                "description": "Logger at info level",
                "severity": "minor",
                "category": "maintainability",
                "current_code": "logger.info('test')",
                "suggested_fix": "logger.debug('test')",
            }
        ]

        repo_path = "/tmp/test_repo6"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/client.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/client.py").write_text("logger.info('test')\n")

        try:
            items, _skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/client.py"]
            )
            assert len(items) == 1
            item = items[0]
            assert item.file_path == "src/client.py"
            assert item.description == "Logger at info level"
            assert item.severity == ItemSeverity.MINOR
            assert item.category == IssueCategory.MAINTAINABILITY
            assert item.line == "1-1"
            assert item.current_code == "logger.info('test')"
            assert item.suggested_fix == "logger.debug('test')"
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_normalizes_cache_prefixed_absolute_path(
        self, tmp_path,
    ) -> None:
        repo = tmp_path / "repo"
        source_file = repo / "src/main.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("x = 1\n")

        items, skip_reasons = ReviewItemFactory.create(
            [
                {
                    "file": "/cache/clones/repo/src/main.py",
                    "description": "Use the named value",
                    "severity": "minor",
                    "category": "bug",
                    "line": "1",
                    "current_code": "x = 1",
                },
            ],
            repo,
            ["src/main.py"],
        )

        assert len(items) == 1
        assert skip_reasons == []
        assert items[0].file_path == "src/main.py"
        assert not items[0].file_path.startswith("/")
        assert "/cache/clones" not in items[0].file_path

    def test_create_skips_unmappable_absolute_path(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        source_file = repo / "src/main.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("x = 1\n")

        items, skip_reasons = ReviewItemFactory.create(
            [
                {
                    "file": "/cache/clones/repo/tests/test_main.py",
                    "description": "Use the named value",
                    "severity": "minor",
                    "category": "bug",
                    "line": "1",
                    "current_code": "x = 1",
                },
            ],
            repo,
            ["src/main.py"],
        )

        assert items == []
        assert len(skip_reasons) == 1

