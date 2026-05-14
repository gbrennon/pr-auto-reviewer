# How to Generate a Patch File Using Git CLI

You can generate a patch file from your local repository using the following methods:

## 1. Patch for Uncommitted Changes

To create a patch for changes you have staged (with `git add`) but not yet committed:

```sh
git diff --cached > my-changes.patch
```

To include unstaged changes as well:

```sh
git diff > my-changes.patch
```

## 2. Patch for Commits (e.g., for a PR or branch)

To generate a patch for one or more commits:

```sh
git format-patch -1 <commit-sha>
# or for a range:
git format-patch <start-commit>..<end-commit>
```

This creates one or more `.patch` files. To combine them into a single file:

```sh
cat *.patch > combined.patch
```

## 3. Patch for a PR from a Remote (e.g., Codeberg)

Fetch the PR branch, then diff against the base branch:

```sh
git fetch origin pull/<pr-number>/head:pr-<pr-number>
git diff main pr-<pr-number> > pr.patch
```

Replace `main` with your base branch name.

---

You can now use the generated `.patch` file with the Python validator:

```sh
python -m src.pr_auto_reviewer.cli validate -d pr.patch
```
