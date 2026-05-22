from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.fragments.repositories import (
    FileSystemFragmentRepository,
)


_VALID_FRAGMENT = """---
id: test-fragment
language: python
priority: 80
category: testing
---
Review for correctness and edge cases.
"""

_NO_CLOSING_DELIMITER = """---
id: broken
Some content without closing delimiter.
"""

_YAML_NON_DICT = """---
42
---
Some content.
"""

_UNIVERSAL_FRAGMENT = """---
id: uni-frag
priority: 90
category: universal
---
Review all code for general best practices.
"""


class TestFileSystemFragmentRepository:

    def test_find_by_language_when_malformed_yaml_then_skips(self, tmp_path):
        lang_dir = tmp_path / "python"
        lang_dir.mkdir()
        (lang_dir / "bad.md").write_text(_YAML_NON_DICT)
        repo = FileSystemFragmentRepository(tmp_path)
        assert repo.find_by_language("python") == []

    def test_find_by_language_when_no_closing_delimiter_then_skips(self, tmp_path):
        lang_dir = tmp_path / "python"
        lang_dir.mkdir()
        (lang_dir / "broken.md").write_text(_NO_CLOSING_DELIMITER)
        repo = FileSystemFragmentRepository(tmp_path)
        assert repo.find_by_language("python") == []

    def test_find_by_id_when_non_directory_in_base_path_then_skips(self, tmp_path):
        (tmp_path / "README.txt").write_text("not a fragment")
        lang_dir = tmp_path / "python"
        lang_dir.mkdir()
        (lang_dir / "valid.md").write_text(_VALID_FRAGMENT)
        repo = FileSystemFragmentRepository(tmp_path)
        assert repo.find_by_id("test-fragment") is not None

    def test_find_by_language_when_valid_fragment_then_finds_it(self, tmp_path):
        lang_dir = tmp_path / "python"
        lang_dir.mkdir()
        (lang_dir / "valid.md").write_text(_VALID_FRAGMENT)
        repo = FileSystemFragmentRepository(tmp_path)
        fragments = repo.find_by_language("python")
        assert len(fragments) == 1
        assert fragments[0].id == "test-fragment"

    def test_find_universal_when_valid_fragment_then_finds_it(self, tmp_path):
        uni_dir = tmp_path / "universal"
        uni_dir.mkdir()
        (uni_dir / "uni.md").write_text(_UNIVERSAL_FRAGMENT)
        repo = FileSystemFragmentRepository(tmp_path)
        fragments = repo.find_universal()
        assert len(fragments) == 1

    def test_find_by_language_when_directory_missing_then_returns_empty(self, tmp_path):
        repo = FileSystemFragmentRepository(tmp_path)
        assert repo.find_by_language("rust") == []

    def test_find_universal_when_directory_missing_then_returns_empty(self, tmp_path):
        repo = FileSystemFragmentRepository(tmp_path)
        assert repo.find_universal() == []
