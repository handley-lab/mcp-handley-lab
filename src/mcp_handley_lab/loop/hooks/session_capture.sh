#!/bin/bash
# Session capture hook for MCP Loop.
# Captures Claude Code session_id and stores it keyed by git root hash.
# Install via: mcp-loop-cli install-hook
# Server runs via: mcp-loop

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -n "$SESSION_ID" ] && [ -n "$CWD" ]; then
    mkdir -p ~/.local/state/mcp-loop/sessions
    # Normalize to git repo root (or cwd if not in repo)
    cd "$CWD" 2>/dev/null
    ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$CWD")
    # Safe hashing via stdin (avoids shell interpolation issues)
    ROOT_HASH=$(printf '%s' "$ROOT" | python3 -c "import hashlib,sys; print(hashlib.md5(sys.stdin.read().encode()).hexdigest())")
    # Atomic write
    TMPFILE=$(mktemp)
    echo "$SESSION_ID" > "$TMPFILE"
    mv "$TMPFILE" ~/.local/state/mcp-loop/sessions/"$ROOT_HASH"
fi
