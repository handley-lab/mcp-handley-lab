"""MCP Memory conversation source adapter.

Discovers git branches under ~/.mcp-handley-lab/conversations/<project>/.
Each branch contains a conversation.jsonl file.
"""

import json
import os
import subprocess
from pathlib import Path

from mcp_handley_lab.search.models import RawEntry, SyncItem


def _get_memory_dir() -> Path:
    base = os.environ.get(
        "MCP_HANDLEY_LAB_MEMORY_DIR", str(Path.home() / ".mcp-handley-lab")
    )
    return Path(base) / "conversations"


def _list_git_repos() -> list[Path]:
    memory_dir = _get_memory_dir()
    if not memory_dir.exists():
        return []
    return [d for d in memory_dir.iterdir() if d.is_dir() and (d / ".git").exists()]


def _list_branches(repo_path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return [b.strip() for b in result.stdout.splitlines() if b.strip()]
    except subprocess.CalledProcessError:
        return []


def _get_branch_tip(repo_path: Path, branch: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _get_branch_content(repo_path: Path, branch: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{branch}:conversation.jsonl"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def discover_items() -> list[SyncItem]:
    """Find all MCP memory branches across all project repos."""
    items = []
    for repo_path in _list_git_repos():
        project_name = repo_path.name
        for branch in _list_branches(repo_path):
            tip = _get_branch_tip(repo_path, branch)
            if not tip:
                continue
            items.append(
                SyncItem(
                    session_key=f"{repo_path}:{branch}",
                    display_name=branch,
                    project=project_name,
                    fingerprint=tip,
                    tip_sha=tip,
                )
            )
    return items


def load_entries(item: SyncItem) -> list[RawEntry]:
    """Load and parse entries from a branch's conversation.jsonl."""
    # Parse repo_path and branch from session_key
    # Format: "/path/to/repo:branch_name"
    colon_idx = item.session_key.rfind(":")
    repo_path = Path(item.session_key[:colon_idx])
    branch = item.session_key[colon_idx + 1 :]

    content = _get_branch_content(repo_path, branch)
    if not content:
        return []

    entries = []
    idx = 0

    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entry_type = _classify_type(entry)
            content_text = _extract_text(entry)

            if not content_text.strip():
                continue

            usage = entry.get("usage", {})
            entries.append(
                RawEntry(
                    idx=idx,
                    role=entry_type,
                    timestamp=entry.get("timestamp"),
                    content=content_text,
                    model=usage.get("model"),
                    cost_usd=usage.get("cost"),
                    raw_json=line.strip(),
                )
            )
            idx += 1
        except json.JSONDecodeError:
            continue

    return entries


def _classify_type(entry: dict) -> str:
    etype = entry.get("type")
    role = entry.get("role")
    if etype == "message":
        if role == "user":
            return "user"
        elif role == "assistant":
            return "assistant"
        return "system"
    elif etype in ("system_prompt", "clear"):
        return "system"
    return "system"


def _extract_text(entry: dict) -> str:
    texts = []
    etype = entry.get("type")
    if etype == "message":
        texts.append(entry.get("content", ""))
        usage = entry.get("usage", {})
        if usage.get("model"):
            texts.append(f"model:{usage['model']}")
    elif etype == "system_prompt":
        texts.append(entry.get("content", ""))
    elif etype == "clear":
        texts.append("conversation cleared")
    return "\n".join(filter(None, texts))
