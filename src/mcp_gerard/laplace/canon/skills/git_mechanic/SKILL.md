---
name: git_mechanic
description: Automates safe Git operations for Laplace, handling broken reverts, filename length limits on Windows worktrees, and preventing repository state corruption.
---

# Git Mechanic: The Repository Surgeon [EXPERIMENTAL]

This skill provides Laplace with robust, failure-resistant protocols for managing Git state, particularly for complex operations like reverting and branching via worktrees. It eliminates operational friction caused by broken git states and Windows path limits.

## 1. The Worktree Filename Limit (Windows MAX_PATH)

Windows natively enforces a 260-character limit on file paths. When spawning `git worktree` instances, deep directory structures or long branch names frequently exceed this limit, causing git failures and corrupted worktrees.

**The Fix:**
Whenever you create a new workspace on Windows, or if you encounter filename length errors in a Git repository, immediately run the configuration script to bypass the limit:

```
laplace_run(skill="git_mechanic")
```
This executes the backing `scripts/configure_git.py`, which forces `git config --global core.longpaths true`.

Additionally, when creating worktrees, avoid extremely long branch names.

## 2. Safe Reversions and Broken States

A raw `git revert <commit>` often fails gracefully but leaves the repository in a **"Reverting" state** with unresolved conflict markers. If Laplace does not immediately notice this state, subsequent commits will include conflict markers (e.g. `<<<<<<< HEAD`), destroying the manuscript.

**The Fix:**
Do not use raw `git revert` unless you are prepared to manually handle conflicts. Instead, use the Safe Revert script. It will attempt a clean revert, and if conflicts arise, it will **automatically abort the revert** and leave the working tree clean, preventing repository corruption.

```powershell
# auxiliary script; resolve its directory via laplace_skill("git_mechanic").backing_path
python scripts/safe_revert.py <commit_hash>
```

If the safe revert aborts due to conflicts, you must manually inspect the history and either:
1. Use `git restore --source=<commit> <file>` to pull the specific good version of a file.
2. Manually patch the file.

## 3. General Rules of Git Engagement
- **Never commit conflict markers.** Always run `git diff` before committing if a merge or revert has occurred.
- If a repository is stuck in a rebasing, merging, or reverting state, use `git merge --abort`, `git rebase --abort`, or `git revert --abort` to return to a clean state.
