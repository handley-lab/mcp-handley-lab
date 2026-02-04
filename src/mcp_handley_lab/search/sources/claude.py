"""Claude Code transcript source adapter.

Discovers JSONL transcript files and history.jsonl under ~/.claude/.
"""

import json
from pathlib import Path

from mcp_handley_lab.claude.transcript import _get_claude_dir
from mcp_handley_lab.search.models import RawEntry, SyncItem


def discover_items() -> list[SyncItem]:
    """Find all Claude transcript files and history.jsonl."""
    items = []

    # Project transcript files
    claude_dir = _get_claude_dir()
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for f in projects_dir.glob("*/*.jsonl"):
            if f.name.startswith("agent-"):
                continue
            stat = f.stat()
            items.append(
                SyncItem(
                    session_key=f"{f.parent.name}/{f.stem}",  # Short: "abc123/session"
                    display_name=f.stem,
                    project=f.parent.name,
                    fingerprint=f"{stat.st_mtime}:{stat.st_size}",
                    file_path=str(f),
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )
            )

    # History file
    history_file = claude_dir / "history.jsonl"
    if history_file.exists():
        stat = history_file.stat()
        items.append(
            SyncItem(
                session_key="history",  # Short: just "history"
                display_name="history",
                project=None,
                fingerprint=f"{stat.st_mtime}:{stat.st_size}",
                file_path=str(history_file),
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
        )

    return items


def load_entries(item: SyncItem) -> list[RawEntry]:
    """Load and parse entries from a Claude transcript file."""
    path = Path(item.file_path)
    if item.display_name == "history":
        return _parse_history(path)
    return _parse_transcript(path)


def _parse_transcript(file_path: Path) -> list[RawEntry]:
    """Parse a Claude Code JSONL transcript file."""
    entries = []
    idx = 0

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                content_text = _extract_text(entry)
                entries.append(
                    RawEntry(
                        idx=idx,
                        role=entry.get("type", "system"),
                        timestamp=entry.get("timestamp"),
                        content=content_text,
                        model=entry.get("model"),
                        cost_usd=entry.get("costUSD"),
                        raw_json=line.strip(),
                    )
                )
                idx += 1
            except json.JSONDecodeError:
                continue
    return entries


def _parse_history(history_file: Path) -> list[RawEntry]:
    """Parse history.jsonl for user prompts."""
    entries = []
    idx = 0

    for line in history_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            display = entry.get("display", "")
            if not display.strip():
                continue
            entries.append(
                RawEntry(
                    idx=idx,
                    role="prompt",
                    timestamp=entry.get("timestamp"),
                    content=display,
                    raw_json=line.strip(),
                )
            )
            idx += 1
        except json.JSONDecodeError:
            continue
    return entries


def _extract_text(entry: dict) -> str:
    """Extract ALL searchable text from Claude entry."""
    texts = []
    etype = entry.get("type")

    if etype in ("user", "assistant"):
        msg = entry.get("message", {})
        content = msg.get("content", "")

        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        texts.append(block.get("text", ""))
                    elif btype == "thinking":
                        texts.append(block.get("thinking", ""))
                    elif btype == "tool_use":
                        texts.append(f"tool:{block.get('name', '')}")
                        inp = block.get("input", {})
                        if isinstance(inp, dict):
                            for v in inp.values():
                                if isinstance(v, str):
                                    texts.append(v)

        tool_result = entry.get("toolUseResult")
        if tool_result:
            if isinstance(tool_result, str):
                texts.append(tool_result)
            elif isinstance(tool_result, list):
                for item in tool_result:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))

    elif etype == "system":
        texts.append(entry.get("content", ""))
    elif etype == "summary":
        texts.append(entry.get("summary", ""))

    return "\n".join(filter(None, texts))
