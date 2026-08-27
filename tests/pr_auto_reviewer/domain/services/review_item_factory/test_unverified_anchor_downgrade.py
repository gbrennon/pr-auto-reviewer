from ._helpers import *


class TestUnverifiedAnchorDowngrade:
    """Findings whose snippet never matches the cited file are non-blocking."""

    @staticmethod
    def _repo_with_file(tmp_path, content: str):
        repo = tmp_path / "repo"
        target = repo / "src" / "mod.py"
        target.parent.mkdir(parents=True)
        target.write_text(content)
        return repo

    def test_nonexistent_snippet_is_downgraded_to_info(
        self, tmp_path,
    ) -> None:
        repo = self._repo_with_file(tmp_path, "x = 1\n")
        item = ReviewResponseParser.normalize_item_dict({
            "file": "src/mod.py",
            "issue": "Variable x is reassigned unsafely.",
            "severity": "high",
            "current_code": "this line does not exist anywhere",
            "line": "1",
        })

        items, _skips = ReviewItemFactory().create(
            [item], repo, ["src/mod.py"],
        )

        assert len(items) == 1
        assert items[0].severity == ItemSeverity.INFO
        assert "[anchor_unverified]" in items[0].description

    def test_verbatim_snippet_keeps_original_severity(
        self, tmp_path,
    ) -> None:
        repo = self._repo_with_file(
            tmp_path, "x = 1\ny = unsafe_operation(x)\n",
        )
        item = ReviewResponseParser.normalize_item_dict({
            "file": "src/mod.py",
            "issue": "Unsafe operation on x.",
            "severity": "major",
            "current_code": "y = unsafe_operation(x)",
            "line": "2",
        })

        items, _skips = ReviewItemFactory().create(
            [item], repo, ["src/mod.py"],
        )

        assert len(items) == 1
        assert items[0].severity == ItemSeverity.MAJOR
        assert "[anchor_unverified]" not in items[0].description

    def test_downgrade_decision_is_logged(
        self, tmp_path, caplog,
    ) -> None:
        import logging

        repo = self._repo_with_file(tmp_path, "x = 1\n")
        item = ReviewResponseParser.normalize_item_dict({
            "file": "src/mod.py",
            "issue": "Variable x is reassigned unsafely.",
            "severity": "critical",
            "current_code": "fabricated snippet text",
            "line": "1",
        })

        with caplog.at_level(logging.WARNING):
            ReviewItemFactory().create([item], repo, ["src/mod.py"])

        assert any(
            "unverified code anchor" in record.message
            for record in caplog.records
        )

