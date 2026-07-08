---
id: shell-quoting
language: shell
priority: 85
category: correctness
---

# Shell Quoting & Expansion Review

Review the following shell script for proper quoting and variable expansion:

```shell
{{ code }}
```

## Checks

- Unquoted variable expansions (`$var` instead of `"$var"`) causing word splitting
- Unquoted command substitutions (`$(cmd)` instead of `"$(cmd)"`)
- `$@` vs `$*` confusion — `$*` joins all args as single string
- Filenames with spaces, newlines, or special characters not handled
- `read` without `-r` that interprets backslashes
- `[*]` array expansion when `[@]` is needed
- Globbing left enabled when iterating over potentially non-existent patterns
- `echo` with arbitrary data — use `printf` instead

## Good Example

```shell
#!/usr/bin/env bash
set -euo pipefail

process_files() {
    local target_dir="$1"
    shift  # Remove target_dir, keep remaining args as files

    mkdir -p "$target_dir"

    for file in "$@"; do
        if [[ -f "$file" ]]; then
            printf 'Processing: %s\n' "$file"
            cp "$file" "$target_dir/"
        fi
    done
}

files=$(find . -name '*.txt' -print0 | xargs -0)
# -print0 + xargs -0 handle filenames with spaces/newlines
```

## Bad Example

```shell
process_files() {
    local target_dir=$1
    # Unquoted — breaks with spaces in path

    for file in $*; do
    # $* instead of "$@" — all args merged into one string then split again

        if [ -f $file ]; then
        # Unquoted — word splitting, globbing
            echo Processing: $file
            # echo may interpret backslash sequences
            cp $file $target_dir/
        fi
    done
}
```
