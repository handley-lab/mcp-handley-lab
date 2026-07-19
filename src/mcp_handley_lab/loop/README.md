# MCP Loop

Persistent REPL loop daemon with parent-child orchestration.

## Background

This implementation draws on two key concepts:

**Recursive Language Models (RLM)** ([arXiv:2512.24601](https://arxiv.org/abs/2512.24601)) - Zhang, Kraska, Khattab (Dec 2025) introduce a paradigm where LLMs recursively call themselves to process arbitrarily long inputs. MCP Loop extends this: any REPL (LLM or code-based) can spawn and orchestrate other REPLs, enabling recursive computation across heterogeneous backends.

**OpenClaw** - A reference implementation for LLM session management (listing, history, spawn, send, memory). MCP Loop adopts the Unix process model (loop_id like PID, parent_id like PPID) rather than OpenClaw's WebSocket gateway, using a Unix socket daemon pattern like ssh-agent.

## Features

- **Persistent loops**: Python, Bash, Julia, R, and other REPLs that survive across tool calls
- **Claude backend**: Spawn Claude Code instances as child loops
- **Parent-child tracking**: Unix-style hierarchy (loop_id like PID, parent_id like PPID)
- **Orchestration**: Python code inside loops can spawn and manage child loops

## Usage

```python
# Spawn a Python loop
mcp__loop__manage(action="spawn", backend="python", label="worker")
# Returns: {"loop_id": "python-123456", "parent_id": "session-...", "ok": true}

# Run input through the loop
mcp__loop__run(loop_id="python-123456", input="2 + 2")
# Returns: {"output": "4", "cell_index": 0, "elapsed_seconds": 0.4}

# List all loops
mcp__loop__manage(action="list")

# Kill a loop
mcp__loop__manage(action="kill", loop_id="python-123456")
```

## Session Hook Setup (Optional)

To automatically track which Claude Code session spawned each loop, install the session capture hook:

1. Copy the hook script:
```bash
mkdir -p ~/.local/share/mcp-loop
cp src/mcp_handley_lab/loop/hooks/session_capture.sh ~/.local/share/mcp-loop/
chmod +x ~/.local/share/mcp-loop/session_capture.sh
```

2. Add to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__loop__*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/YOUR_USER/.local/share/mcp-loop/session_capture.sh"
          }
        ]
      }
    ]
  }
}
```

3. Restart Claude Code.

## Client Library (for orchestration)

Python code running inside a loop can spawn child loops:

```python
# Inside a Python loop:
import sys
sys.path.insert(0, '/path/to/mcp-handley-lab/src')
from mcp_handley_lab.loop.client import spawn, run, list_loops

# Spawn a child
child_id = spawn('bash', label='worker')

# Run input in child
result = run(child_id, 'echo hello')
print(result)  # "hello"

# List loops
for loop in list_loops():
    print(f"{loop['loop_id']} (parent: {loop['parent_id']})")
```

## Available Backends

- `python` - Python 3 interpreter
- `bash` - Bash shell
- `ipython` - IPython (with matplotlib)
- `julia` - Julia
- `R` - R
- `claude` - Claude Code (stream-json mode)
- `mathematica` - Wolfram Mathematica
- `clojure`, `apl`, `maple`, `ollama` - Other REPLs
