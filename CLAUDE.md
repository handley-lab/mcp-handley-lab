# Agent instructions

Correct, minimal documentation is best. Omission is preferable to an
unsupported or obsolete claim. Incorrect documentation is worst.

## Architecture

This repository is transitional. Direct Python functions and typed return
values are the composition boundary. Existing FastMCP tools and console entry
points serve unported consumers only; do not create new CLI or MCP surfaces.
When the last real consumer of an adapter moves, delete the adapter and its
dependencies rather than preserving compatibility.

Keep domain operations in `shared.py` or another transport-independent module.
An MCP `tool.py` may adapt that operation to FastMCP but must not contain the
only implementation. Export supported Python functions from the domain
package's `__init__.py` and test them directly. Protocol tests are justified
only for behavior introduced by the protocol adapter.

Prefer a few orthogonal functions over action-specific wrappers. Return typed
Python values rather than serialized envelopes when the caller is Python.
Validate independently changing external input once at its boundary and let
unexpected internal states fail visibly.

## Current boundaries

- `mcp_handley_lab.llm` and `mcp_handley_lab.loop` are direct Python surfaces.
- `mcp_handley_lab.claude` and `mcp_handley_lab.search` expose transcript and
  session evidence.
- Office modules expose direct OOXML read/edit operations.
- Calendar and email integrations remain for legacy consumers; current estate
  work belongs in `mdcal`, native notmuch, and `mddraft`.
- ArXiv and code2prompt modules are deprecated in their package initializers in
  favor of skills.

Do not infer that a console script in `pyproject.toml` is the preferred API. It
is evidence that a compatibility process still exists and needs a verified
consumer audit before deletion.

## Safety and verification

Credentials and live user data stay outside the repository. Use controlled
fixtures and temporary directories. A unit mock proves only local behavior;
integration claims require the real API, document format, process, or protocol
boundary named by the claim.

Run the relevant direct-function tests and lint for changed modules. Do not
disable tests or swallow failures to keep a legacy adapter alive.

Every commit requires a version bump through:

```sh
python scripts/bump_version.py
```

The script updates `pyproject.toml` and `PKGBUILD`. Never bypass the version or
pre-commit checks.
