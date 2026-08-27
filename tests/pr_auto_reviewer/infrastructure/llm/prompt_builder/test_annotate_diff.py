from ._helpers import *


class TestAnnotateDiff:
    def test_annotates_added_file(self):
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "index 0000000..abc\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1 @@\n"
            "+print('hello')\n"
        )
        result = _annotate_diff(diff)
        assert "[ADDED] new.py" in result
        assert "Review its content" in result

    def test_annotates_deleted_file(self):
        diff = (
            "diff --git a/old.py b/old.py\n"
            "deleted file mode 100644\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-print('bye')\n"
        )
        result = _annotate_diff(diff)
        assert "[DELETED] old.py" in result
        assert "being removed" in result

    def test_annotates_modified_file(self):
        diff = (
            "diff --git a/file.py b/file.py\n"
            "index abc..def 100644\n"
            "--- a/file.py\n"
            "+++ b/file.py\n"
            "@@ -1 +1,2 @@\n"
            " unchanged\n"
            "+new line\n"
        )
        result = _annotate_diff(diff)
        assert "[MODIFIED] file.py" in result

