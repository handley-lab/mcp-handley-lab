"""Access Claude Code session transcripts and history."""

import json
import os
from pathlib import Path


def _get_claude_dir() -> Path:
    """Get ~/.claude directory."""
    return Path.home() / ".claude"


def _get_project_dir(project_path: str | None = None) -> Path:
    """Get Claude Code project directory for given or current cwd."""
    cwd = project_path or os.getcwd()
    encoded = cwd.replace("/", "-").replace(".", "-")
    return _get_claude_dir() / "projects" / encoded


def sessions(project_path: str | None = None) -> list[dict]:
    """List all Claude Code sessions for a project (default: current cwd)."""
    project_dir = _get_project_dir(project_path)
    index_file = project_dir / "sessions-index.json"
    if not index_file.exists():
        return []
    return json.loads(index_file.read_text()).get("entries", [])


def transcript(
    session_id: str | None = None,
    project_path: str | None = None,
    raw: bool = False,
) -> list[dict]:
    """Read Claude Code session transcript.

    Args:
        session_id: Specific session to read (default: most recent)
        project_path: Project path (default: current cwd)
        raw: Return all event types, not just user/assistant messages
    """
    project_dir = _get_project_dir(project_path)

    # Find transcript file
    if session_id:
        transcript_file = project_dir / f"{session_id}.jsonl"
    else:
        # Most recently modified .jsonl (excluding agents)
        candidates = [
            f for f in project_dir.glob("*.jsonl") if not f.name.startswith("agent-")
        ]
        if not candidates:
            return []
        transcript_file = max(candidates, key=lambda f: f.stat().st_mtime)

    if not transcript_file.exists():
        return []

    # Parse JSONL
    messages = []
    for line in transcript_file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if raw:
                messages.append(entry)
            elif entry.get("type") in ("user", "assistant"):
                messages.append(_extract_message(entry))
        except json.JSONDecodeError:
            continue
    return messages


def history(include_pasted: bool = False) -> list[dict]:
    """Read user prompt history across all projects.

    Args:
        include_pasted: Include full pasted content (default: False)
    """
    history_file = _get_claude_dir() / "history.jsonl"
    if not history_file.exists():
        return []

    prompts = []
    for line in history_file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            prompt = {
                "display": entry.get("display", ""),
                "timestamp": entry.get("timestamp"),
                "project": entry.get("project"),
                "sessionId": entry.get("sessionId"),
            }
            if include_pasted and entry.get("pastedContents"):
                prompt["pastedContents"] = entry["pastedContents"]
            prompts.append(prompt)
        except json.JSONDecodeError:
            continue
    return prompts


def _extract_message(entry: dict) -> dict:
    """Extract simplified message from transcript entry."""
    msg = {"type": entry["type"], "timestamp": entry.get("timestamp")}
    content = entry.get("message", entry.get("content", {}))

    if isinstance(content, dict) and "content" in content:
        c = content["content"]
        if isinstance(c, str):
            msg["content"] = c
            msg["role"] = content.get("role", entry["type"])
        elif isinstance(c, list):
            texts = [
                item.get("text", "")
                for item in c
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            msg["content"] = "\n".join(texts) if texts else ""
            msg["role"] = content.get("role", entry["type"])
    elif isinstance(content, str):
        msg["content"] = content
        msg["role"] = entry["type"]

    return msg
