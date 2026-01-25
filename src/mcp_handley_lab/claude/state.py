"""Access ~/.claude.json global state."""

import json
import os
from pathlib import Path


def _get_claude_json() -> dict:
    """Load ~/.claude.json."""
    path = Path.home() / ".claude.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def projects() -> dict[str, dict]:
    """Get all projects with their stats.

    Returns: {"/path/to/project": {"lastCost": 4.75, "lastSessionId": "...", ...}, ...}
    """
    return _get_claude_json().get("projects", {})


def project_stats(project_path: str | None = None) -> dict:
    """Get stats for a specific project (default: current cwd).

    Returns: {"lastCost": 4.75, "lastLinesAdded": 26, "lastSessionId": "...", ...}
    """
    path = project_path or os.getcwd()
    return projects().get(path, {})


def github_repos() -> dict[str, list[str]]:
    """Get GitHub repo to local path mappings.

    Returns: {"owner/repo": ["/local/path1", "/local/path2"], ...}
    """
    return _get_claude_json().get("githubRepoPaths", {})


def mcp_servers() -> dict[str, dict]:
    """Get MCP server configurations.

    Returns: {"email": {"type": "stdio", "command": "mcp-email"}, ...}
    """
    return _get_claude_json().get("mcpServers", {})


def skill_usage() -> dict[str, dict]:
    """Get skill usage statistics.

    Returns: {"skill-name": {"usageCount": 22, "lastUsedAt": 1769...}, ...}
    """
    return _get_claude_json().get("skillUsage", {})
