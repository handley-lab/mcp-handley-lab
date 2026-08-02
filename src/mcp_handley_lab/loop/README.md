# Persistent loop actors

Correct, minimal documentation is best. Omission is preferable to an
unsupported or obsolete claim. Incorrect documentation is worst.

This package contains the transitional `mcp-loop` daemon and its native Python
interface. New composition uses `mcp_handley_lab.loop.manage` and `run`; the
FastMCP adapter and console entry point remain only for unported consumers.

```python
from mcp_handley_lab.loop import manage, run

actor = manage("spawn", backend="python", label="worker")
result = run(actor.loop_id, "sum(range(10))", sync_timeout=-1)
history = manage("read", loop_id=actor.loop_id)
```

`manage()` owns lifecycle operations: `spawn`, `list`, `read`, `read_raw`,
`status`, `terminate`, `kill`, and `prune`. `run()` submits one input and returns
a typed `RunResult`. Both communicate with the same Unix-socket daemon and
autostart it when necessary.

The daemon state under `~/.local/state/mcp-loop` and its socket under
`~/.local/run` are implementation details, not a second API. Alan and Agent
Fleet are the current estate boundary for persistent agent sessions; do not add
new consumers to this legacy daemon while those remaining consumers are being
ported.
