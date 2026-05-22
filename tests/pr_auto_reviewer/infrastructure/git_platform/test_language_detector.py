from pr_auto_reviewer.infrastructure.git_platform.language_detector import (
    LanguageDetector,
)


class TestLanguageDetector:

    def test_detect_when_single_extension_then_returns_language(self):
        assert LanguageDetector().detect(["main.py"]) == "python"
        assert LanguageDetector().detect(["Main.java"]) == "java"
        assert LanguageDetector().detect(["main.go"]) == "go"
        assert LanguageDetector().detect(["lib.rs"]) == "rust"
        assert LanguageDetector().detect(["App.kt"]) == "kotlin"
        assert LanguageDetector().detect(["index.ts"]) == "typescript"
        assert LanguageDetector().detect(["app.js"]) == "javascript"
        assert LanguageDetector().detect(["main.rb"]) == "ruby"
        assert LanguageDetector().detect(["Program.cs"]) == "csharp"
        assert LanguageDetector().detect(["main.swift"]) == "swift"

    def test_detect_when_majority_extension_then_returns_dominant_language(self):
        paths = ["a.py", "b.py", "c.rs", "d.py"]
        assert LanguageDetector().detect(paths) == "python"

    def test_detect_when_no_known_extension_then_returns_unknown(self):
        assert LanguageDetector().detect(["README.md", "Dockerfile"]) == "unknown"

    def test_detect_when_empty_paths_then_returns_unknown(self):
        assert LanguageDetector().detect([]) == "unknown"
