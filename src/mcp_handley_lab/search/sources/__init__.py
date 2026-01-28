"""Source adapters for transcript search.

Each source module implements:
    discover_items() -> list[SyncItem]
    load_entries(item: SyncItem) -> list[RawEntry]
"""

from mcp_handley_lab.search.sources import claude, codex, gemini, mcp_memory

SOURCES = {
    "claude": claude,
    "codex": codex,
    "gemini": gemini,
    "mcp": mcp_memory,
}
