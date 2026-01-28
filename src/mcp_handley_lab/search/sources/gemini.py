"""Gemini CLI transcript source adapter.

Discovers JSON chat files under ~/.gemini/tmp/*/chats/.
"""

import json
from pathlib import Path

from mcp_handley_lab.search.models import RawEntry, SyncItem


def _get_gemini_dir() -> Path:
    return Path.home() / ".gemini" / "tmp"


def discover_items() -> list[SyncItem]:
    """Find all Gemini chat JSON files."""
    gemini_dir = _get_gemini_dir()
    if not gemini_dir.exists():
        return []
    items = []
    for f in gemini_dir.glob("*/chats/*.json"):
        stat = f.stat()
        project_hash = f.parent.parent.name
        items.append(
            SyncItem(
                session_key=str(f),
                display_name=f"{project_hash}/{f.stem}",
                project=project_hash,
                fingerprint=f"{stat.st_mtime}:{stat.st_size}",
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
        )
    return items


def load_entries(item: SyncItem) -> list[RawEntry]:
    """Load and parse entries from a Gemini chat JSON file."""
    file_path = Path(item.session_key)
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    entries = []
    idx = 0

    for msg in data.get("messages", []):
        msg_type = _classify_type(msg)
        content_text = _extract_text(msg)

        if not content_text.strip():
            continue

        model = msg.get("model")
        cost_usd = _estimate_cost(msg)

        entries.append(
            RawEntry(
                idx=idx,
                role=msg_type,
                timestamp=msg.get("timestamp"),
                content=content_text,
                model=model,
                cost_usd=cost_usd,
                raw_json=json.dumps(msg),
            )
        )
        idx += 1

    return entries


def _classify_type(msg: dict) -> str:
    msg_type = msg.get("type", "")
    if msg_type == "user":
        return "user"
    elif msg_type == "gemini":
        return "assistant"
    return "system"


def _extract_text(msg: dict) -> str:
    texts = [msg.get("content", "")]
    for thought in msg.get("thoughts", []):
        if isinstance(thought, dict):
            texts.append(thought.get("subject", ""))
            texts.append(thought.get("description", ""))
    for tool in msg.get("toolCalls", []):
        if isinstance(tool, dict):
            texts.append(f"tool:{tool.get('name', '')}")
            args = tool.get("args", {})
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str):
                        texts.append(v)
            texts.append(tool.get("resultDisplay", ""))
    return "\n".join(filter(None, texts))


def _estimate_cost(msg: dict) -> float | None:
    tokens = msg.get("tokens", {})
    if not tokens:
        return None
    input_tokens = tokens.get("input", 0) + tokens.get("cached", 0)
    output_tokens = tokens.get("output", 0) + tokens.get("thoughts", 0)
    return (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000
