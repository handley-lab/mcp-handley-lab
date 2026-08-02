"""Git-backed conversation memory for persistent LLM conversations.

Uses Git branches as conversations with checkout-free operations for reading/writing.
Each project gets its own Git repository under ~/.mcp-handley-lab/conversations/.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

# Valid branch name checking is done via git check-ref-format
# This pattern is used for quick pre-filtering only
VALID_BRANCH_CHARS = re.compile(r"^[A-Za-z0-9_.\-]+$")

EVENT_TYPES = {"message", "system_prompt", "clear"}


def encode_project_path(path: Path) -> str:
    """Encode a project path to a directory-safe name.

    Follows Claude Code's convention: /home/will/project -> -home-will-project
    Uses Path.resolve() for canonicalization (handles symlinks, ., ..).
    Uses as_posix() for cross-platform consistency.
    """
    resolved = path.resolve()
    # Use as_posix() for consistent separators, then replace / with -
    # Also handle Windows drive letters (C: -> C)
    posix_path = resolved.as_posix()
    return posix_path.replace(":", "").replace("/", "-")


def get_global_storage_dir() -> Path:
    """Get the global storage directory for LLM memory."""
    base = Path(os.environ.get("MCP_HANDLEY_LAB_MEMORY_DIR", "~/.mcp-handley-lab"))
    return base.expanduser()


def get_conversations_dir() -> Path:
    """Get the conversations directory (contains per-project Git repos)."""
    return get_global_storage_dir() / "conversations"


def get_edit_dir() -> Path:
    """Get the edit directory (contains worktrees for editing sessions)."""
    return get_global_storage_dir() / "edit"


def _git(
    project_dir: Path, *args: str, input_data: str | None = None
) -> subprocess.CompletedProcess:
    """Run a git command in the project directory.

    Args:
        project_dir: Path to the Git repository
        *args: Git command and arguments
        input_data: Optional data to pass to stdin

    Returns:
        CompletedProcess with stdout/stderr

    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    cmd = ["git", "-C", str(project_dir), *args]
    env = os.environ.copy()
    env["LC_ALL"] = "C"  # Consistent output for parsing

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        env=env,
        check=True,
    )


def _git_unchecked(
    project_dir: Path, *args: str, input_data: str | None = None
) -> subprocess.CompletedProcess:
    """Run a git command without raising on non-zero exit.

    Same as _git but doesn't raise CalledProcessError.
    Used for commands where we need to check the return code ourselves.
    """
    cmd = ["git", "-C", str(project_dir), *args]
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        env=env,
        check=False,
    )


def _ensure_git_repo(project_dir: Path) -> None:
    """Initialize a Git repository if it doesn't exist.

    Sets up:
    - Non-bare repo (required for worktrees)
    - Local identity (user.name, user.email)
    """
    project_dir.mkdir(parents=True, exist_ok=True)

    git_dir = project_dir / ".git"
    if git_dir.exists():
        return

    subprocess.run(
        ["git", "init", str(project_dir)],
        capture_output=True,
        check=True,
    )

    _git(project_dir, "config", "user.name", "mcp-handley-lab")
    _git(project_dir, "config", "user.email", "mcp-handley-lab@local")


def get_project_dir(cwd: Path | None = None) -> Path:
    """Get or create the project-specific Git repository directory.

    Args:
        cwd: Working directory to encode. Defaults to current directory.

    Returns:
        Path to the project's Git repository directory
    """
    if cwd is None:
        cwd = Path.cwd()

    encoded = encode_project_path(cwd)
    project_dir = get_conversations_dir() / encoded

    _ensure_git_repo(project_dir)
    return project_dir


def validate_branch_name(name: str) -> None:
    """Validate a branch name using git check-ref-format.

    Raises:
        ValueError: If the branch name is invalid
    """
    if not name:
        raise ValueError("Branch name cannot be empty")

    if not VALID_BRANCH_CHARS.match(name):
        raise ValueError(
            f"Invalid branch name '{name}'. "
            "Branch names must contain only letters, numbers, underscores, hyphens, and dots."
        )

    result = subprocess.run(
        ["git", "check-ref-format", "--branch", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Invalid branch name '{name}': {result.stderr.strip()}")


def normalize_branch_input(branch: str) -> str | None:
    """Normalize and validate branch input.

    Processing order:
    1. Check for special values (empty string, "false") on raw input
    2. Normalize (strip whitespace)
    3. Validate normalized result

    Returns:
        Normalized branch name, or None if memory should be disabled

    Raises:
        ValueError: If branch name is whitespace-only or invalid
    """
    if branch == "" or branch.lower() == "false":
        return None

    normalized = branch.strip()

    if not normalized:
        raise ValueError("Branch name cannot be whitespace-only")

    validate_branch_name(normalized)
    return normalized


def branch_exists(project_dir: Path, branch: str) -> bool:
    """Check if a branch exists.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to check

    Returns:
        True if branch exists, False otherwise
    """
    result = _git_unchecked(
        project_dir, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}"
    )
    return result.returncode == 0


def read_branch(project_dir: Path, branch: str) -> str:
    """Read conversation content from a branch.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to read

    Returns:
        JSONL content (empty string if branch doesn't exist)

    Raises:
        ValueError: If branch exists but conversation.jsonl is missing (corrupted)
    """
    if not branch_exists(project_dir, branch):
        return ""

    result = _git_unchecked(
        project_dir, "show", f"refs/heads/{branch}:conversation.jsonl"
    )
    if result.returncode != 0:
        # Branch exists but file doesn't - corrupted state
        raise ValueError("Corrupted conversation: missing file")

    return result.stdout


def resolve_ref(project_dir: Path, ref: str) -> str:
    """Resolve a git ref to a commit SHA.

    Args:
        project_dir: Path to the Git repository
        ref: Any valid git ref (SHA, tag, branch name, etc.)

    Returns:
        Resolved commit SHA

    Raises:
        ValueError: If ref doesn't exist
    """
    result = _git_unchecked(project_dir, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise ValueError(f"Ref not found: {ref}")
    return result.stdout.strip()


def read_ref(project_dir: Path, ref: str) -> tuple[str, str]:
    """Read conversation content at a specific ref.

    Args:
        project_dir: Path to the Git repository
        ref: Any valid git ref (SHA, tag, branch name, etc.)

    Returns:
        Tuple of (JSONL content, resolved SHA)

    Raises:
        ValueError: If ref doesn't exist or file is missing
    """
    resolved_sha = resolve_ref(project_dir, ref)

    result = _git_unchecked(project_dir, "show", f"{resolved_sha}:conversation.jsonl")
    if result.returncode != 0:
        raise ValueError("Corrupted conversation: missing file")

    return result.stdout, resolved_sha


def get_branch_sha(project_dir: Path, branch: str) -> str | None:
    """Get the current tip SHA of a branch.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name

    Returns:
        Commit SHA or None if branch doesn't exist
    """
    result = _git_unchecked(
        project_dir, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}"
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def create_commit(
    project_dir: Path,
    content: str,
    parent: str | None,
    message: str,
) -> str:
    """Create a commit with the given content.

    Uses Git plumbing commands to create a commit without checkout:
    1. git hash-object -w --stdin → blob SHA
    2. git mktree → tree SHA
    3. git commit-tree [-p parent] → commit SHA

    Args:
        project_dir: Path to the Git repository
        content: JSONL content for conversation.jsonl
        parent: Parent commit SHA (None for orphan commits)
        message: Commit message

    Returns:
        New commit SHA
    """
    result = _git(project_dir, "hash-object", "-w", "--stdin", input_data=content)
    blob_sha = result.stdout.strip()

    tree_entry = f"100644 blob {blob_sha}\tconversation.jsonl"
    result = _git(project_dir, "mktree", input_data=tree_entry)
    tree_sha = result.stdout.strip()

    if parent:
        result = _git(project_dir, "commit-tree", tree_sha, "-p", parent, "-m", message)
    else:
        result = _git(project_dir, "commit-tree", tree_sha, "-m", message)

    return result.stdout.strip()


def try_fast_forward(
    project_dir: Path, branch: str, old_sha: str, new_sha: str
) -> bool:
    """Attempt to fast-forward a branch from old_sha to new_sha.

    Uses git update-ref with compare-and-swap semantics.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to update
        old_sha: Expected current SHA (for CAS)
        new_sha: New SHA to set

    Returns:
        True if fast-forward succeeded, False if branch moved (conflict)
    """
    result = _git_unchecked(
        project_dir, "update-ref", f"refs/heads/{branch}", new_sha, old_sha
    )
    return result.returncode == 0


def create_branch(project_dir: Path, branch: str, commit_sha: str) -> bool:
    """Create a new branch pointing to the given commit.

    Uses git update-ref with zero-SHA expected old (fails if exists).

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to create
        commit_sha: Commit SHA to point to

    Returns:
        True if branch was created, False if it already exists
    """
    zero_sha = "0" * 40
    result = _git_unchecked(
        project_dir, "update-ref", f"refs/heads/{branch}", commit_sha, zero_sha
    )
    return result.returncode == 0


def create_orphan_branch(
    project_dir: Path, branch: str, content: str, message: str
) -> str:
    """Create a new orphan branch with initial content.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to create
        content: JSONL content for the initial commit
        message: Commit message

    Returns:
        Commit SHA of the initial commit

    Raises:
        ValueError: If branch already exists
    """
    if branch_exists(project_dir, branch):
        raise ValueError(f"Branch '{branch}' already exists")

    commit_sha = create_commit(project_dir, content, None, message)

    if not create_branch(project_dir, branch, commit_sha):
        raise ValueError(f"Failed to create branch '{branch}'")

    return commit_sha


def fork_branch(project_dir: Path, branch: str, from_ref: str) -> str:
    """Create a new branch by forking from a specific ref.

    This is a non-destructive operation that creates a new branch pointing
    to the same commit as from_ref. Useful for exploring alternative
    conversation paths without the overhead of a full worktree.

    Args:
        project_dir: Path to the Git repository
        branch: New branch name to create
        from_ref: Any valid git ref (SHA, tag, branch name) to fork from

    Returns:
        Commit SHA that the new branch points to

    Raises:
        ValueError: If branch already exists or from_ref doesn't exist
    """
    if branch_exists(project_dir, branch):
        raise ValueError(f"Branch '{branch}' already exists")

    result = _git_unchecked(
        project_dir, "rev-parse", "--verify", f"{from_ref}^{{commit}}"
    )
    if result.returncode != 0:
        raise ValueError(f"Ref not found: {from_ref}")

    commit_sha = result.stdout.strip()

    if not create_branch(project_dir, branch, commit_sha):
        raise ValueError(f"Failed to create branch '{branch}'")

    return commit_sha


def parse_messages(jsonl_content: str) -> list[dict[str, Any]]:
    """Parse JSONL content to list of event dicts.

    Args:
        jsonl_content: JSONL string (one JSON object per line)

    Returns:
        List of event dictionaries
    """
    if not jsonl_content.strip():
        return []

    events = []
    for line in jsonl_content.strip().split("\n"):
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def format_messages(events: list[dict[str, Any]]) -> str:
    """Format list of events to JSONL string.

    Args:
        events: List of event dictionaries

    Returns:
        JSONL string
    """
    if not events:
        return ""
    return "\n".join(json.dumps(event) for event in events) + "\n"


def validate_jsonl(content: str) -> None:
    """Validate JSONL content structure.

    Checks:
    1. Each line is valid JSON
    2. Each object has required 'v' and 'type' fields
    3. 'type' is one of: message, system_prompt, clear

    Args:
        content: JSONL content to validate

    Raises:
        ValueError: If content is invalid
    """
    if not content.strip():
        return

    for i, line in enumerate(content.strip().split("\n"), 1):
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on line {i}: {e}") from e

        if "v" not in obj:
            raise ValueError(f"Missing 'v' field on line {i}")

        if "type" not in obj:
            raise ValueError(f"Missing 'type' field on line {i}")

        if obj["type"] not in EVENT_TYPES:
            raise ValueError(
                f"Invalid type '{obj['type']}' on line {i}. "
                f"Must be one of: {', '.join(sorted(EVENT_TYPES))}"
            )


def append_message(
    content: str,
    role: str,
    text: str,
    **meta: Any,
) -> str:
    """Append a message event to JSONL content.

    Args:
        content: Existing JSONL content
        role: Message role (user/assistant)
        text: Message content
        **meta: Additional metadata (usage, cwd, etc.)

    Returns:
        Updated JSONL content
    """
    event = {
        "v": 1,
        "type": "message",
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": text,
    }

    if "usage" in meta:
        event["usage"] = meta["usage"]
    if "cwd" in meta:
        event["cwd"] = meta["cwd"]

    new_line = json.dumps(event) + "\n"

    if content and not content.endswith("\n"):
        content += "\n"

    return content + new_line


def append_system_prompt(content: str, system_prompt: str) -> str:
    """Append a system_prompt event to JSONL content.

    Args:
        content: Existing JSONL content
        system_prompt: System prompt text

    Returns:
        Updated JSONL content
    """
    event = {
        "v": 1,
        "type": "system_prompt",
        "timestamp": datetime.now().isoformat(),
        "content": system_prompt,
    }

    new_line = json.dumps(event) + "\n"

    if content and not content.endswith("\n"):
        content += "\n"

    return content + new_line


def append_clear(content: str) -> str:
    """Append a clear event to JSONL content.

    Args:
        content: Existing JSONL content

    Returns:
        Updated JSONL content
    """
    event = {
        "v": 1,
        "type": "clear",
        "timestamp": datetime.now().isoformat(),
    }

    new_line = json.dumps(event) + "\n"

    if content and not content.endswith("\n"):
        content += "\n"

    return content + new_line


def write_conversation(
    project_dir: Path,
    branch: str,
    content: str,
    message: str,
) -> dict[str, Any]:
    """Write conversation content to a branch with fork-on-conflict.

    Validates JSONL before writing. If the branch has moved since we read it,
    creates a fork branch instead.

    Args:
        project_dir: Path to the Git repository
        branch: Target branch name
        content: JSONL content to write
        message: Commit message

    Returns:
        {
            "branch": str,      # Branch name (may be fork if conflict)
            "commit_sha": str,  # Commit SHA
            "forked": bool,     # True if forked due to conflict
            "forked_from": str | None,  # Original branch if forked
        }
    """
    validate_jsonl(content)

    old_sha = get_branch_sha(project_dir, branch)

    if old_sha is None:
        commit_sha = create_orphan_branch(project_dir, branch, content, message)
        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "forked": False,
            "forked_from": None,
        }

    new_sha = create_commit(project_dir, content, old_sha, message)

    if try_fast_forward(project_dir, branch, old_sha, new_sha):
        return {
            "branch": branch,
            "commit_sha": new_sha,
            "forked": False,
            "forked_from": None,
        }

    fork_branch = f"{branch}-fork-{new_sha}"

    if not create_branch(project_dir, fork_branch, new_sha):
        raise ValueError(f"Failed to create fork branch '{fork_branch}'")

    return {
        "branch": fork_branch,
        "commit_sha": new_sha,
        "forked": True,
        "forked_from": branch,
    }


def get_llm_context(
    project_dir: Path,
    branch: str,
) -> tuple[list[dict[str, str]], str | None]:
    """Get conversation context for LLM API call.

    Implements "since last clear" rule:
    - Only includes messages after the most recent `clear` event
    - Returns most recent `system_prompt` since last clear (or None)

    Args:
        project_dir: Path to the Git repository
        branch: Branch name to read

    Returns:
        (history, system_prompt) where:
        - history: List of {"role": str, "content": str} dicts
        - system_prompt: Most recent system prompt or None
    """
    content = read_branch(project_dir, branch)
    events = parse_messages(content)

    if not events:
        return [], None

    last_clear_idx = -1
    for i, event in enumerate(events):
        if event.get("type") == "clear":
            last_clear_idx = i

    history = []
    system_prompt = None

    for i, event in enumerate(events):
        if i <= last_clear_idx:
            continue

        event_type = event.get("type")
        if event_type == "message":
            history.append(
                {
                    "role": event["role"],
                    "content": event["content"],
                }
            )
        elif event_type == "system_prompt":
            system_prompt = event["content"]

    return history, system_prompt


def list_branches(project_dir: Path) -> list[dict[str, Any]]:
    """List all conversation branches with basic stats.

    Args:
        project_dir: Path to the Git repository

    Returns:
        List of branch info dicts with name, message_count, latest_timestamp
    """
    result = _git_unchecked(
        project_dir, "branch", "--list", "--format=%(refname:short)"
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    branches = []
    for name in result.stdout.strip().split("\n"):
        name = name.strip()
        if not name:
            continue

        content = read_branch(project_dir, name)
        events = parse_messages(content)

        message_count = sum(1 for e in events if e.get("type") == "message")
        latest_timestamp = None
        for event in reversed(events):
            if "timestamp" in event:
                latest_timestamp = event["timestamp"]
                break

        branches.append(
            {
                "name": name,
                "message_count": message_count,
                "latest_timestamp": latest_timestamp,
            }
        )

    return branches


def get_log(
    project_dir: Path,
    branch: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get commit history for a branch.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name
        limit: Maximum commits to return

    Returns:
        List of {sha, timestamp, message_preview} dicts
    """
    result = _git_unchecked(
        project_dir,
        "log",
        f"refs/heads/{branch}",
        f"--max-count={limit}",
        "--format=%H|%aI|%s",
    )
    if result.returncode != 0:
        return []

    entries = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            entries.append(
                {
                    "sha": parts[0],
                    "timestamp": parts[1],
                    "message_preview": parts[2][:100],
                }
            )

    return entries


def _get_lock_path(project_dir: Path) -> Path:
    """Get the lock file path for a project."""
    return project_dir / ".mcp-edit-lock"


def _get_worktree_path(project_dir: Path) -> Path:
    """Get the worktree path for editing a project."""
    encoded = project_dir.name
    return get_edit_dir() / encoded


def is_locked(project_dir: Path) -> dict[str, Any] | None:
    """Check if the project is locked for editing.

    Returns:
        Lock info dict if locked, None otherwise
    """
    lock_path = _get_lock_path(project_dir)
    if not lock_path.exists():
        return None

    try:
        return json.loads(lock_path.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupted lock file - treat as locked with unknown info
        return {"timestamp": None, "pid": None, "worktree_path": None}


def start_edit(project_dir: Path) -> dict[str, Any]:
    """Start an editing session with a worktree.

    Creates:
    - Lock file in project directory
    - Worktree with detached HEAD in edit directory

    Args:
        project_dir: Path to the Git repository

    Returns:
        {"path": str} with worktree path

    Raises:
        ValueError: If already locked or worktree creation fails
    """
    lock_info = is_locked(project_dir)
    if lock_info is not None:
        raise ValueError(
            f"Editing already in progress (pid={lock_info.get('pid')}). "
            "Use conversation(action='done', force=True) to force cleanup."
        )

    worktree_path = _get_worktree_path(project_dir)

    if worktree_path.exists():
        _git_unchecked(project_dir, "worktree", "remove", "--force", str(worktree_path))
        if worktree_path.exists():
            import shutil

            shutil.rmtree(worktree_path, ignore_errors=True)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    branches = list_branches(project_dir)
    if branches:
        branch_name = branches[0]["name"]
        ref = f"refs/heads/{branch_name}"
    else:
        ref = create_commit(project_dir, "", None, "Empty worktree anchor")

    result = _git_unchecked(
        project_dir, "worktree", "add", "--detach", str(worktree_path), ref
    )
    if result.returncode != 0:
        raise ValueError(f"Failed to create worktree: {result.stderr}")

    lock_path = _get_lock_path(project_dir)
    lock_data = {
        "timestamp": datetime.now().isoformat(),
        "pid": os.getpid(),
        "worktree_path": str(worktree_path),
    }
    lock_path.write_text(json.dumps(lock_data))

    return {"path": str(worktree_path)}


def end_edit(project_dir: Path, force: bool = False) -> dict[str, Any]:
    """End an editing session.

    Removes worktree and lock file.

    Args:
        project_dir: Path to the Git repository
        force: If True, remove even if lock wasn't created by this process

    Returns:
        {"success": True}

    Raises:
        ValueError: If not locked (and not forcing)
    """
    lock_path = _get_lock_path(project_dir)
    lock_info = is_locked(project_dir)

    if lock_info is None and not force:
        raise ValueError("No editing session in progress")

    if lock_info and not force and lock_info.get("pid") != os.getpid():
        raise ValueError(
            f"Lock held by different process (pid={lock_info.get('pid')}). "
            "Use force=True to override."
        )

    worktree_path = _get_worktree_path(project_dir)
    if worktree_path.exists():
        _git_unchecked(project_dir, "worktree", "remove", "--force", str(worktree_path))
        if worktree_path.exists():
            import shutil

            shutil.rmtree(worktree_path, ignore_errors=True)

    _git_unchecked(project_dir, "worktree", "prune")

    if lock_path.exists():
        lock_path.unlink()

    return {"success": True}


def get_response(
    project_dir: Path,
    branch: str,
    index: int = -1,
) -> dict[str, Any]:
    """Get an assistant response by index.

    Args:
        project_dir: Path to the Git repository
        branch: Branch name
        index: Response index (0 = first, -1 = last, -2 = second-to-last)

    Returns:
        Response dict with content, usage, timestamp, etc.

    Raises:
        ValueError: If branch not found
        IndexError: If no assistant responses or index out of range
    """
    content = read_branch(project_dir, branch)
    if not content and not branch_exists(project_dir, branch):
        raise ValueError(f"Branch '{branch}' not found")

    events = parse_messages(content)

    last_clear_idx = -1
    for i, event in enumerate(events):
        if event.get("type") == "clear":
            last_clear_idx = i

    responses = []
    for i, event in enumerate(events):
        if i <= last_clear_idx:
            continue
        if event.get("type") == "message" and event.get("role") == "assistant":
            responses.append(event)

    if not responses:
        raise IndexError("Cannot get response: branch has no assistant responses")

    msg = responses[index]
    stored_usage = msg.get("usage") or {}

    result: dict[str, Any] = {"content": msg["content"]}

    usage = {
        "input_tokens": stored_usage.get("input_tokens", 0),
        "output_tokens": stored_usage.get("output_tokens", 0),
        "cost": stored_usage.get("cost", 0.0),
        "model_used": stored_usage.get("model", ""),
    }
    result["usage"] = usage

    llm_result_fields = [
        "finish_reason",
        "avg_logprobs",
        "model_version",
        "generation_time_ms",
        "response_id",
        "system_fingerprint",
        "service_tier",
        "completion_tokens_details",
        "prompt_tokens_details",
        "stop_sequence",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "grounding_metadata",
    ]
    for field in llm_result_fields:
        if field in stored_usage:
            result[field] = stored_usage[field]

    result["branch"] = branch

    return result
