---
name: orient_recovery
description: "[EXPERIMENTAL] The recovery branch for an underdetermined orient. When laplace_orient returns domain=null or an otherwise incomplete route, stay inside the engine: enumerate the canon with laplace_index, resolve the candidate domain and project, then re-orient with an explicit domain. An empty engine answer is a branch, never an exit to the raw filesystem."
---
# orient_recovery

**Status: [EXPERIMENTAL]**

## Purpose
The engine is closed under its own gaps. Every response from `laplace_orient` is a move
inside the loop - including an empty one. The observed failure is the opposite reflex: orient
returns `domain=null`, the model reads that as "the engine has nothing for me", and falls out
to native behaviour - brute-forcing the filesystem with `grep` / `Get-ChildItem` / `ls` to find
a handoff or a project root, or reverting to generic file editing and subagent delegation. The
loop breaks at exactly the moment it should self-route. This skill makes an underdetermined
orient a defined branch with an in-engine recipe, so there is never a reason to leave the MCP.

## The trigger
Any orient whose route is underdetermined. The canonical case is `domain: null` in the bundle,
but the same branch applies whenever the offered skills and loaded context do not match the work
in hand. `domain=null` means "name the domain yourself", not "no domain exists".

## The pass (in fixed order)
1. **Do not leave the engine.** The first move after an underdetermined orient is another engine
   call, never a filesystem search or a native edit. Hold this before anything else.
2. **Enumerate.** Call `laplace_index()` to survey the whole canon - every domain, its projects,
   and the skills on offer. This is the map orient routes against.
3. **Match.** Read the goal against the enumerated domains and their projects. The active project
   is the one whose state the work advances. Pick the single best candidate.
4. **Resolve.** Call `laplace_resolve(ref)` on the candidate domain's project node to pull its
   state in full - the standing context and the pointer to its live handoff. The canon owns this
   pointer, so the handoff is reached through the engine, not hunted on disk.
5. **Re-orient explicitly.** Call `laplace_orient(goal=..., domain=...)` with the domain named.
   The bundle now carries the right axioms, project state, and candidate skills. The loop is
   recovered - resume orient -> execute -> verify from here.

## Invariants
- **An empty answer is a branch, not an exit.** A null or thin orient routes back into the engine.
  The raw filesystem is never the recovery path for a routing question.
- **Name the domain rather than guess the rules.** When orient cannot infer the domain, the
  recovery is to enumerate and re-orient with it stated - not to reconstruct the project from
  static memory or a directory walk.
- **The canon owns the handoff pointer.** Reach a project's live state by resolving its node, so
  the next context starts from the canon's record rather than a path that may have moved.
- **One re-orient, then resume.** Recovery is a short detour back onto the rail, not a new loop.

## Backing
No deterministic script yet. A natural future backing is an orient-guard: when a bundle returns
domain=null, emit the index summary and the candidate domains inline with the bundle, so the
recovery recipe is handed to the model in the same response that triggered it - structural
enforcement rather than remembered discipline.
