#!/usr/bin/env python3
"""Generate a repo structure tree from a local directory.

Outputs a tree similar to `tree` but filtering out common non-source directories.
Used by validate.sh to provide codebase context to the AI reviewer.
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


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_repo_structure.py <repo_path>", file=sys.stderr)
        sys.exit(1)

    repo_path = sys.argv[1]
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    repo_name = os.path.basename(os.path.abspath(repo_path))
    print(f"{repo_name}/")
    generate_tree(repo_path, prefix="", depth=0)


if __name__ == "__main__":
    main()