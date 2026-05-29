# [Domain Name]: Project Scaffold

When initiating a new project in a novel domain, clone this scaffold.

## 1. Domain Epistemology
- Create a `domains/[domain_name]/axioms.md` file. Define the strict theoretical rules, governing equations, or fundamental laws that apply to this domain. Subagents will load this to prevent hallucinating physics or logic outside of your specific constraints.

## 2. Active Projects
- Create `domains/[domain_name]/projects/[project_name].md`. Document the current state, active hypotheses, and subagent directives specific to this manuscript.

## 3. Router Registration
- Update the root `wiki/index.md` to list your new domain and link to its conceptual maps.
