# The Laplace Engine

A cross-LLM, self-refining canon for manuscript drafting, served over MCP. One
source of truth, mounted by every LLM you use, exposing a tripartite task loop
and a slow self-refinement loop governed by measured skill fitness.

## The loop

```
FAST (within a session)
  orient  -> laplace_orient(goal)      load goal + relevant canon
  execute -> laplace_skill / laplace_run   run the local action
  verify  -> laplace_verify(target)    check consistency; mismatch re-orients

SLOW (between sessions)
  assess  -> laplace_assess            measure skill fitness from telemetry
  dream   -> laplace_dream             silently refine canon (evidence-gated)
  rollback-> laplace_rollback(ref)     undo any dreamer mutation
```

## Layout

```
laplace/
  canon/                 the single source of truth (version-controlled)
    index.yaml           hand-authored manifest: relevance + initial status
    lifecycle.yaml       machine-owned overlay the dreamer writes (status/fitness)
    wiki/                aesthetics, operations, structure, workflow, domains
    skills/<name>/       SKILL.md protocol + optional backing script
    agents/              neutral persona definitions (dreamer, empiricist)
  canon.py               loader, canon:// resolver, relevance + orient bundle
  verify.py              structured consistency ledgers + backing-script runner
  telemetry.py           append-only event log (the fitness substrate)
  assess.py              fitness + evidence-gated lifecycle recommendations
  dreamer.py             the R&R cycle (curation + optional generative forging)
  render.py              per-client bootstrap adapters
  tool.py                the FastMCP server (mcp-laplace)
```

## Tools

| Tool | Phase | Purpose |
|------|-------|---------|
| `laplace_orient(goal, domain?)` | orient | concise, ranked canon bundle for a goal |
| `laplace_search` / `laplace_index` / `laplace_resolve` | orient | search / list / fetch canon |
| `laplace_skill(name)` | execute | protocol spec + how to run a skill |
| `laplace_run(skill, target, args?)` | execute | run a skill's backing script |
| `laplace_verify(target, checks?)` | verify | epistemic / voice / crossref / empirical report |
| `laplace_assess()` | dream | per-skill fitness + recommended lifecycle moves |
| `laplace_log(skill, signal)` | dream | record explicit feedback |
| `laplace_dream(apply, forge?, friction?)` | dream | refine canon; revertible commits |
| `laplace_rollback(ref)` | dream | undo a dreamer commit |
| `laplace_sync(client, write?)` | adapter | render/install a client's bootstrap |

## Make it the default everywhere

The engine is a stdio MCP server (`mcp-laplace`, registered in `pyproject.toml`).
Register it once per client, then drop in the generated bootstrap:

```jsonc
// any MCP client's server config (Claude .mcp.json, Codex, etc.)
{ "mcpServers": { "laplace": { "type": "stdio", "command": "mcp-laplace" } } }
```

```python
# generate + install bootstraps from the canon
laplace_sync("claude",      write=True)   # ~/.claude/skills/laplace/SKILL.md
laplace_sync("gemini",      write=True)   # ~/.gemini/GEMINI.md
laplace_sync("codex",       write=True)   # ~/.codex/AGENTS.md
laplace_sync("antigravity", write=True)   # ~/.antigravity/laplace_bootstrap.md
```

`laplace_sync` also returns the MCP registration snippet, so wiring a new client
is copy-paste.

## Configuration

- `LAPLACE_CANON` - point all clients at a shared canon working copy (the dreamer
  commits there). Defaults to the canon packaged with mcp-gerard.
- `LAPLACE_STATE` - telemetry/state dir. Defaults to `~/.mcp-gerard/laplace`.
- `LAPLACE_SESSION` - group telemetry events from one drive of the loop.

## How the dreamer stays safe while autonomous

It never promotes by fiat. `assess` derives fitness (usage x verify-pass-rate x
retention x feedback); only skills that earn it over real uses become `core`, and
only the unused or degraded are deprecated. Every mutation is a scoped git commit
in the canon, so `laplace_rollback` undoes anything. New forged skills are born
`experimental` under the Probationary Protocol.
