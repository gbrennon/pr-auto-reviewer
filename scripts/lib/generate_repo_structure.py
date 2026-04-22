#!/usr/bin/env python3
"""Generate a repo structure tree from a local directory.

Outputs a tree similar to `tree` but filtering out common non-source directories.
Used by validate.sh to provide codebase context to the AI reviewer.

Supports --detect-type to output a project type hint instead of the tree.
"""

import os
import sys

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist",
    "build", ".eggs", ".nox", "coverage", "htmlcov", ".hg", ".svn",
    ".idea", ".vscode", ".vs", "target", "vendor", "vendor-bin",
    "bower_components", ".next", ".nuxt", ".cache",
}

SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".o", ".a",
    ".class", ".jar", ".war", ".ear", ".woff", ".woff2", ".eot",
    ".ttf", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf", ".zip", ".tar", ".gz",
    ".bz2", ".xz", ".7z", ".rar", ".db", ".sqlite", ".lock",
}

MAX_DEPTH = 6
MAX_FILES = 300

LAYER_INDICATORS = {
    "domain", "application", "infrastructure", "adapters", "ports",
    "presentation", "use_cases", "usecases", "services", "repositories",
    "handlers", "controllers", "persistence",
}


def should_skip_dir(name):
    return name in SKIP_DIRS or name.startswith(".")


def should_skip_file(name):
    _, ext = os.path.splitext(name)
    return ext.lower() in SKIP_EXTENSIONS


def generate_tree(root, prefix="", depth=0, file_count=[0]):
    if depth > MAX_DEPTH or file_count[0] > MAX_FILES:
        return

    try:
        entries = sorted(os.listdir(root))
    except PermissionError:
        return

    dirs = []
    files = []
    for entry in entries:
        path = os.path.join(root, entry)
        if os.path.isdir(path):
            if not should_skip_dir(entry):
                dirs.append(entry)
        else:
            if not should_skip_file(entry):
                files.append(entry)

    items = dirs + files
    for i, item in enumerate(items, 1):
        is_last = i == len(items)
        connector = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

        path = os.path.join(root, item)
        if os.path.isdir(path):
            print(f"{prefix}{connector}{item}/")
            generate_tree(path, prefix + child_prefix, depth + 1, file_count)
        else:
            print(f"{prefix}{connector}{item}")
            file_count[0] += 1

        if file_count[0] > MAX_FILES:
            print(f"{prefix}... (truncated, too many files)")
            return


def detect_project_type_local(root):
    """Derive project type hint from a local directory structure."""
    try:
        entries = set(os.listdir(root))
    except (PermissionError, FileNotFoundError):
        return "unknown"

    has_src = "src" in entries and os.path.isdir(os.path.join(root, "src"))

    if has_src:
        src_path = os.path.join(root, "src")
        src_entries = set(os.listdir(src_path))

        layer_matches = src_entries & LAYER_INDICATORS
        if len(layer_matches) >= 2:
            return "layered"

        feature_dirs = [
            d for d in src_entries
            if os.path.isdir(os.path.join(src_path, d))
            and not d.startswith(".")
            and d not in LAYER_INDICATORS
            and d not in SKIP_DIRS
        ]
        if len(feature_dirs) >= 2 and not layer_matches:
            return "vertical-slices"

        return "structured"

    has_scripts = "scripts" in entries and os.path.isdir(os.path.join(root, "scripts"))

    if has_scripts and not has_src:
        return "scripts"

    has_makefile = any(f in entries for f in ("Makefile", "makefile", "GNUmakefile"))

    if has_makefile and not has_src:
        return "scripts"

    simple_indicators = {"app.py", "main.py", "manage.py", "app.ts", "index.ts", "main.go"}
    if entries & simple_indicators:
        return "simple"

    return "unknown"


def detect_project_type_from_tree(tree_text):
    """Derive project type hint from a flat path tree (API response).

    Expected input: one path per line, dirs end with /, e.g.:
        src/
        src/domain/
        src/application/
        scripts/
        Makefile
    """
    lines = [line.strip() for line in tree_text.strip().splitlines() if line.strip()]
    dirs = set()
    files = set()

    for line in lines:
        basename = line.rsplit("/", 1)[-1] if "/" in line else line
        if line.endswith("/"):
            dirs.add(basename.rstrip("/"))
        else:
            files.add(basename)

        parent_parts = []
        for part in line.split("/"):
            if part:
                parent_parts.append(part)
        for i in range(1, len(parent_parts)):
            path_so_far = "/".join(parent_parts[:i])
            if not path_so_far.endswith("/"):
                dirs.add(parent_parts[i - 1])

    has_src = "src" in dirs

    if has_src:
        src_subdirs = set()
        for line in lines:
            parts = line.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "src":
                if parts[1] and not parts[1].startswith("."):
                    src_subdirs.add(parts[1])

        layer_matches = src_subdirs & LAYER_INDICATORS
        if len(layer_matches) >= 2:
            return "layered"

        feature_dirs = src_subdirs - LAYER_INDICATORS - SKIP_DIRS
        if len(feature_dirs) >= 2 and not layer_matches:
            return "vertical-slices"

        return "structured"

    has_scripts = "scripts" in dirs

    if has_scripts and not has_src:
        return "scripts"

    has_makefile = "Makefile" in files or "makefile" in files or "GNUmakefile" in files

    if has_makefile and not has_src:
        return "scripts"

    simple_indicators = {"app.py", "main.py", "manage.py", "app.ts", "index.ts", "main.go"}
    if files & simple_indicators:
        return "simple"

    return "unknown"


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_repo_structure.py <repo_path>", file=sys.stderr)
        print("       generate_repo_structure.py --detect-type <repo_path>", file=sys.stderr)
        print("       generate_repo_structure.py --detect-type-from-tree  (reads tree from stdin)", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--detect-type":
        if len(sys.argv) < 3:
            print("Usage: generate_repo_structure.py --detect-type <repo_path>", file=sys.stderr)
            sys.exit(1)
        repo_path = sys.argv[2]
        if not os.path.isdir(repo_path):
            print(f"Error: {repo_path} is not a directory", file=sys.stderr)
            sys.exit(1)
        print(detect_project_type_local(repo_path))
        return

    if sys.argv[1] == "--detect-type-from-tree":
        tree_text = sys.stdin.read()
        print(detect_project_type_from_tree(tree_text))
        return

    repo_path = sys.argv[1]
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    repo_name = os.path.basename(os.path.abspath(repo_path))
    print(f"{repo_name}/")
    generate_tree(repo_path, prefix="", depth=0)


if __name__ == "__main__":
    main()
