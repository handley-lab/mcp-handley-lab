"""MCP Loop CLI - session hook installation and utilities."""

import json
import shutil
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).parent / "hooks" / "session_capture.sh"
INSTALL_DIR = Path.home() / ".local" / "share" / "mcp-loop"
INSTALLED_HOOK = INSTALL_DIR / "session_capture.sh"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
HOOK_MATCHER = "mcp__loop__*"


def install_hook() -> None:
    """Install session capture hook and configure Claude Code settings."""
    # Install hook script
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(HOOK_SCRIPT, INSTALLED_HOOK)
    INSTALLED_HOOK.chmod(0o755)
    print(f"Installed hook to: {INSTALLED_HOOK}")

    # Load existing settings
    if CLAUDE_SETTINGS.exists():
        settings = json.loads(CLAUDE_SETTINGS.read_text())
    else:
        CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        settings = {}

    # Build hook entry
    hook_entry = {
        "matcher": HOOK_MATCHER,
        "hooks": [{"type": "command", "command": str(INSTALLED_HOOK)}],
    }

    # Add/update hooks section
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if hook already exists (by matcher)
    pre_tool_use = settings["hooks"]["PreToolUse"]
    existing_idx = next(
        (i for i, h in enumerate(pre_tool_use) if h.get("matcher") == HOOK_MATCHER),
        None,
    )
    if existing_idx is not None:
        pre_tool_use[existing_idx] = hook_entry
        print(f"Updated existing hook in {CLAUDE_SETTINGS}")
    else:
        pre_tool_use.append(hook_entry)
        print(f"Added hook to {CLAUDE_SETTINGS}")

    # Write back
    CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    print("Restart Claude Code to activate the hook.")


def main() -> None:
    """CLI entry point.

    Note: The MCP server runs via `mcp-loop`. This CLI provides utilities.
    """
    if len(sys.argv) < 2:
        print("Usage: mcp-loop-cli <command>")
        print()
        print("Commands:")
        print("  install-hook  Install session capture hook for Claude Code")
        print()
        print("Note: The MCP server runs via `mcp-loop`")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "install-hook":
        install_hook()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
