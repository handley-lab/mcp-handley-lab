# Git Mechanics

* **Git Mechanic & Worktree Frictions**: Windows path limits (`MAX_PATH`) and broken git reverts frequently corrupt the repository state. You must consult the `git_mechanic` skill to bypass path limits (`core.longpaths true`) and execute safe reverts (`safe_revert.py`). Never commit unresolved conflict markers.
