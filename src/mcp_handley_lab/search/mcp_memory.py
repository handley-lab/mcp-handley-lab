"""MCP Memory conversation search.

This module indexes conversations stored in git branches under
~/.mcp-handley-lab/conversations/<project>/
"""

import json
import subprocess
from pathlib import Path

from mcp_handley_lab.search.common import (
    ensure_idx_column,
    file_lock,
    fts_search,
    get_connection,
    setup_fts_with_triggers,
)

DB_NAME = "mcp"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    session_id TEXT NOT NULL,
    project_path TEXT,
    uuid TEXT,
    type TEXT NOT NULL,
    timestamp TEXT,
    content_text TEXT,
    model TEXT,
    cost_usd REAL,
    raw_json TEXT,
    idx INTEGER
);

CREATE TABLE IF NOT EXISTS sync_meta (
    file_path TEXT PRIMARY KEY,
    tip_sha TEXT,
    entry_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_file_path ON entries(file_path);
CREATE INDEX IF NOT EXISTS idx_session ON entries(session_id);
CREATE INDEX IF NOT EXISTS idx_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON entries(timestamp);
"""


def _init_schema(conn):
    """Initialize database schema and FTS triggers."""
    conn.executescript(SCHEMA)
    setup_fts_with_triggers(conn)
    ensure_idx_column(conn)  # Auto-migrate existing DBs, forces resync if needed


def _get_memory_dir() -> Path:
    """Get the MCP memory conversations directory."""
    import os

    base = os.environ.get(
        "MCP_HANDLEY_LAB_MEMORY_DIR", str(Path.home() / ".mcp-handley-lab")
    )
    return Path(base) / "conversations"


def _list_git_repos() -> list[Path]:
    """Find all git repositories under the conversations directory."""
    memory_dir = _get_memory_dir()
    if not memory_dir.exists():
        return []
    repos = []
    for project_dir in memory_dir.iterdir():
        if project_dir.is_dir() and (project_dir / ".git").exists():
            repos.append(project_dir)
    return repos


def _list_branches(repo_path: Path) -> list[str]:
    """List all branches in a git repository."""
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
    """Get the tip commit SHA for a branch."""
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
    """Get conversation.jsonl content from a branch."""
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


def _extract_text(entry: dict) -> str:
    """Extract searchable text from MCP memory entry."""
    texts = []
    etype = entry.get("type")

    if etype == "message":
        texts.append(entry.get("content", ""))
        # Include usage info if present
        usage = entry.get("usage", {})
        if usage.get("model"):
            texts.append(f"model:{usage['model']}")

    elif etype == "system_prompt":
        texts.append(entry.get("content", ""))

    elif etype == "clear":
        texts.append("conversation cleared")

    return "\n".join(filter(None, texts))


def _classify_type(entry: dict) -> str:
    """Classify entry into user/assistant/system type."""
    etype = entry.get("type")
    role = entry.get("role")

    if etype == "message":
        if role == "user":
            return "user"
        elif role == "assistant":
            return "assistant"
        return "system"
    elif etype == "system_prompt" or etype == "clear":
        return "system"
    return "system"


def _parse_branch(repo_path: Path, branch: str, project_name: str) -> list[tuple]:
    """Parse a branch's conversation.jsonl. Returns entry tuples for batch insert."""
    content = _get_branch_content(repo_path, branch)
    if not content:
        return []

    entries = []
    # Use branch as session_id, repo path as file_path for tracking
    file_path = f"{repo_path}:{branch}"
    idx = 0  # Track position of kept entries only

    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entry_type = _classify_type(entry)
            content_text = _extract_text(entry)

            if not content_text.strip():
                continue

            # Get cost from usage if available
            usage = entry.get("usage", {})
            cost_usd = usage.get("cost")
            model = usage.get("model")

            entries.append(
                (
                    file_path,
                    branch,  # session_id = branch name
                    project_name,
                    None,  # uuid
                    entry_type,
                    entry.get("timestamp"),
                    content_text,
                    model,
                    cost_usd,
                    line.strip(),
                    idx,  # Position in session
                )
            )
            idx += 1
        except json.JSONDecodeError:
            continue

    return entries


def sync(full: bool = False) -> dict:
    """Sync MCP memory conversations to database."""
    with file_lock("mcp"):
        conn = get_connection("mcp")
        _init_schema(conn)
        conn.commit()  # Commit any schema changes before starting sync transaction

        try:
            conn.execute("BEGIN IMMEDIATE")

            if full:
                conn.execute("DELETE FROM entries")
                conn.execute("DELETE FROM sync_meta")

            stats = {"files": 0, "entries": 0, "skipped": 0, "deleted": 0}
            processed_branches = set()

            for repo_path in _list_git_repos():
                project_name = repo_path.name
                branches = _list_branches(repo_path)

                for branch in branches:
                    file_path = f"{repo_path}:{branch}"
                    processed_branches.add(file_path)

                    # Check if branch has changed
                    tip = _get_branch_tip(repo_path, branch)
                    if not tip:
                        continue

                    existing = conn.execute(
                        "SELECT tip_sha FROM sync_meta WHERE file_path = ?",
                        (file_path,),
                    ).fetchone()

                    if not full and existing and existing["tip_sha"] == tip:
                        stats["skipped"] += 1
                        continue

                    # Delete existing entries
                    conn.execute(
                        "DELETE FROM entries WHERE file_path = ?", (file_path,)
                    )

                    entries = _parse_branch(repo_path, branch, project_name)
                    if entries:
                        conn.executemany(
                            """
                            INSERT INTO entries (file_path, session_id, project_path, uuid, type,
                                               timestamp, content_text, model, cost_usd, raw_json, idx)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            entries,
                        )

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sync_meta (file_path, tip_sha, entry_count)
                        VALUES (?, ?, ?)
                        """,
                        (file_path, tip, len(entries)),
                    )
                    stats["files"] += 1
                    stats["entries"] += len(entries)

            # Clean up deleted branches
            existing_rows = conn.execute("SELECT file_path FROM sync_meta").fetchall()
            for row in existing_rows:
                if row["file_path"] not in processed_branches:
                    conn.execute(
                        "DELETE FROM entries WHERE file_path = ?", (row["file_path"],)
                    )
                    conn.execute(
                        "DELETE FROM sync_meta WHERE file_path = ?", (row["file_path"],)
                    )
                    stats["deleted"] += 1

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return stats


def search(
    query: str = "",
    project: str = "",
    type: str = "",
    limit: int = 20,
    since: str = "",
) -> list[dict]:
    """Full-text search across MCP memory conversations."""
    conn = get_connection("mcp")
    _init_schema(conn)

    if not query:
        sql = "SELECT * FROM entries WHERE 1=1"
        params: list = []

        if project:
            sql += " AND project_path LIKE ?"
            params.append(f"%{project}%")
        if type:
            sql += " AND type = ?"
            params.append(type)
        if since:
            sql += " AND timestamp >= ?"
            params.append(since)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(row) for row in conn.execute(sql, params)]

    return fts_search(
        conn,
        query,
        limit=limit,
        filters={
            "project_path": project or None,
            "type": type or None,
            "timestamp": since or None,
        },
    )


def stats() -> dict:
    """Get MCP memory usage statistics."""
    conn = get_connection("mcp")
    _init_schema(conn)

    totals = conn.execute(
        """
        SELECT COUNT(*) as entries,
               COUNT(DISTINCT session_id) as sessions,
               COUNT(DISTINCT project_path) as projects,
               SUM(cost_usd) as total_cost
        FROM entries
        """
    ).fetchone()

    by_type = conn.execute(
        """
        SELECT type, COUNT(*) as count
        FROM entries
        GROUP BY type
        ORDER BY count DESC
        """
    ).fetchall()

    return {
        "entries": totals["entries"],
        "sessions": totals["sessions"],
        "projects": totals["projects"],
        "total_cost": totals["total_cost"] or 0.0,
        "by_type": {row["type"]: row["count"] for row in by_type},
    }
