# mcp-handley-lab

A transitional collection of research and productivity integrations. The
package still contains MCP servers and console entry points for consumers that
have not yet moved, but new composition uses the Python interfaces directly.

Correct, minimal documentation is best. Omission is preferable to an
unsupported or obsolete claim. Incorrect documentation is worst.

## Python interfaces

The package exports ordinary functions and typed values from domain modules:

| Capability | Import |
| --- | --- |
| LLM calls and conversations | `mcp_handley_lab.llm` |
| Embeddings | `mcp_handley_lab.llm.embeddings` |
| Persistent language and REPL actors | `mcp_handley_lab.loop` |
| Claude transcript/state inspection | `mcp_handley_lab.claude` |
| Transcript search | `mcp_handley_lab.search` |
| Google Maps and Photos | `mcp_handley_lab.google_maps`, `mcp_handley_lab.google_photos` |
| Otter transcripts | `mcp_handley_lab.otter` |
| X11 screenshots | `mcp_handley_lab.screenshot` |
| Word, Excel, PowerPoint, and Visio | `mcp_handley_lab.microsoft.*` |

For example:

```python
from mcp_handley_lab.llm import chat
from mcp_handley_lab.loop import manage, run

answer = chat("Review this design", model="gemini", branch="review")

actor = manage("spawn", backend="python", label="worker")
result = run(actor.loop_id, "sum(range(10))", sync_timeout=-1)
```

`manage()` is the lifecycle primitive for persistent actors; `run()` submits
one input and returns a `RunResult`. The daemon socket and session state are
implementation details of that Python interface.

Some domains now have separate authoritative substrates. Use `mdcal` for the
current calendar system, native notmuch plus `mddraft` for email, `mddb` for
Markdown databases, and Alan/Agent Fleet for persistent agent sessions. Do not
add new consumers to this package's Google Calendar, email, or MCP wrappers.

## Legacy boundary

The scripts declared in `pyproject.toml` are compatibility processes, not the
composition API. They remain until their actual consumers are ported and
tested. Remove an adapter and its dependencies when the last consumer moves;
do not add a second wrapper, migration layer, or CLI compatibility surface.

The package is installed through its Arch `PKGBUILD` where legacy services
still require it. Every repository change must use `scripts/bump_version.py`,
which updates both `pyproject.toml` and `PKGBUILD`; CI rejects an unchanged or
mismatched version.

## Development

```sh
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

External credentials remain outside the repository. Tests use explicit
fixtures or temporary paths and must not mutate live mail, calendar, document,
or session state.

## License

MIT
