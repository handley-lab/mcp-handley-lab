"""Canon loader, ``canon://`` resolver, and relevance selection.

The canon is the single source of truth: a wiki (knowledge graph of aesthetics,
operations, structure, workflow, and domain axioms) plus skills (protocol specs
with optional backing scripts) plus agent personas, indexed by ``index.yaml``.

The loader DISCOVERS files on disk and OVERLAYS the manifest metadata. Anything
missing from the manifest falls back to a sensible default, so the canon still
works if the manifest drifts. The manifest is the mutable record the assessment
and dreamer layers write back to (skill ``status`` and ``fitness``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Locating the canon
# ---------------------------------------------------------------------------

# Packaged default: the canon shipped inside this package.
_PACKAGED_CANON = Path(__file__).resolve().parent / "canon"


def canon_root() -> Path:
    """Return the active canon directory.

    Override with ``LAPLACE_CANON`` to point every LLM at a shared working copy
    (the dreamer commits there). Defaults to the canon packaged with mcp-gerard.
    """
    env = os.environ.get("LAPLACE_CANON")
    if env:
        return Path(env).expanduser()
    return _PACKAGED_CANON


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_EXPERIMENTAL_RE = re.compile(r"\[EXPERIMENTAL\]", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter dict, body) for a markdown file with YAML frontmatter."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, text[m.end() :]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Skill:
    name: str
    description: str
    phase: str  # orient | execute | verify
    domain: str
    status: str  # experimental | core | deprecated
    backing: str | None
    tags: list[str]
    path: Path  # the skill directory

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def backing_path(self) -> Path | None:
        return self.path / self.backing if self.backing else None

    def search_blob(self) -> set[str]:
        return _tokenize(" ".join([self.name, self.description, *self.tags]))

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "phase": self.phase,
            "domain": self.domain,
            "status": self.status,
            "description": self.description,
            "backing": self.backing,
            "tags": self.tags,
        }


@dataclass
class WikiNode:
    ref: str  # e.g. "aesthetics/voice_and_style"
    title: str
    scope: str  # global | domain
    domain: str | None
    tags: list[str]
    path: Path

    def search_blob(self) -> set[str]:
        return _tokenize(" ".join([self.ref, self.title, *self.tags]))


@dataclass
class Canon:
    root: Path
    manifest: dict[str, Any]
    lifecycle: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    wiki: dict[str, WikiNode] = field(default_factory=dict)

    # -- construction -------------------------------------------------------
    @classmethod
    def load(cls, root: Path | None = None) -> Canon:
        root = root or canon_root()
        manifest = cls._load_manifest(root)
        lifecycle = cls._load_lifecycle(root)
        canon = cls(root=root, manifest=manifest, lifecycle=lifecycle)
        canon._discover_skills()
        canon._discover_wiki()
        return canon

    @staticmethod
    def _load_lifecycle(root: Path) -> dict[str, Any]:
        """Machine-owned status/fitness overlay the dreamer writes back to.

        Kept separate from index.yaml so the hand-authored, commented manifest is
        never rewritten by automation.
        """
        path = root / "lifecycle.yaml"
        if not path.exists():
            return {"skills": {}}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("skills", {})
        return data

    @staticmethod
    def _load_manifest(root: Path) -> dict[str, Any]:
        path = root / "index.yaml"
        if not path.exists():
            return {"version": 1, "wiki": {}, "domains": {}, "skills": {}}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key in ("wiki", "domains", "skills"):
            data.setdefault(key, {})
        return data

    def _discover_skills(self) -> None:
        skills_dir = self.root / "skills"
        overlay = self.manifest.get("skills", {})
        if not skills_dir.is_dir():
            return
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            sk_dir = skill_md.parent
            name = sk_dir.name
            fm, _ = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
            o = overlay.get(name, {}) or {}
            description = str(o.get("description") or fm.get("description") or "")
            # status precedence: lifecycle overlay (machine) > manifest > inference.
            life = (self.lifecycle.get("skills", {}) or {}).get(name, {}) or {}
            status = life.get("status") or o.get("status")
            if not status:
                head = skill_md.read_text(encoding="utf-8")[:600]
                status = "experimental" if _EXPERIMENTAL_RE.search(head) else "core"
            self.skills[name] = Skill(
                name=name,
                description=description,
                phase=o.get("phase", "execute"),
                domain=o.get("domain", "global"),
                status=status,
                backing=o.get("backing"),
                tags=list(o.get("tags", [])),
                path=sk_dir,
            )

    def _discover_wiki(self) -> None:
        wiki_dir = self.root / "wiki"
        overlay = self.manifest.get("wiki", {})
        domains = self.manifest.get("domains", {})
        if not wiki_dir.is_dir():
            return
        # Map domain-owned refs so discovery can scope them correctly.
        domain_of: dict[str, str] = {}
        for dname, dmeta in domains.items():
            if isinstance(dmeta, dict):
                if dmeta.get("axioms"):
                    domain_of[dmeta["axioms"]] = dname
                for pref in (dmeta.get("projects") or {}).values():
                    domain_of[pref] = dname
        for md in sorted(wiki_dir.rglob("*.md")):
            ref = md.relative_to(wiki_dir).as_posix()[: -len(".md")]
            if ref == "index":
                continue  # superseded by index.yaml as the machine router
            o = overlay.get(ref, {}) or {}
            dom = domain_of.get(ref)
            fm, body = _split_frontmatter(md.read_text(encoding="utf-8"))
            title = o.get("title") or _first_heading(body) or ref
            self.wiki[ref] = WikiNode(
                ref=ref,
                title=title,
                scope=o.get("scope", "domain" if dom else "global"),
                domain=dom,
                tags=list(o.get("tags", [])),
                path=md,
            )

    # -- resolution ---------------------------------------------------------
    def resolve(self, ref: str) -> tuple[Path, str]:
        """Resolve a ``canon://`` / bare ref to (path, content). Raises KeyError."""
        r = ref.strip()
        if r.startswith("canon://"):
            r = r[len("canon://") :]
        r = r.strip("/")
        candidates = [
            self.root / r,
            self.root / f"{r}.md",
            self.root / "wiki" / f"{r}.md",
            self.root / "skills" / r / "SKILL.md",
        ]
        for c in candidates:
            if c.is_file():
                return c, c.read_text(encoding="utf-8")
        raise KeyError(f"Cannot resolve canon ref: {ref!r}")

    # -- relevance ----------------------------------------------------------
    def domains(self) -> dict[str, Any]:
        return self.manifest.get("domains", {})

    def infer_domain(self, goal: str) -> str | None:
        """Guess the active domain from goal text via domain tags / names."""
        tokens = _tokenize(goal)
        best, best_score = None, 0
        for dname, dmeta in self.domains().items():
            blob = _tokenize(dname + " " + " ".join((dmeta or {}).get("tags", [])))
            score = len(tokens & blob)
            if score > best_score:
                best, best_score = dname, score
        return best

    def rank_skills(
        self, goal: str, domain: str | None = None, limit: int = 6
    ) -> list[Skill]:
        tokens = _tokenize(goal)
        scored: list[tuple[float, Skill]] = []
        for sk in self.skills.values():
            if sk.status == "deprecated":
                continue
            score = float(len(tokens & sk.search_blob()))
            if domain and sk.domain == domain:
                score += 2.0
            if sk.domain not in ("global", domain) and sk.domain != "web":
                score -= 1.0  # off-domain skills are less relevant
            if sk.status == "core":
                score += 0.5  # mild prior toward proven tools
            if score > 0:
                scored.append((score, sk))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [sk for _, sk in scored[:limit]]

    def rank_wiki(self, goal: str, domain: str | None, limit: int = 4) -> list[WikiNode]:
        tokens = _tokenize(goal)
        scored: list[tuple[int, WikiNode]] = []
        for node in self.wiki.values():
            if node.scope == "domain" and node.domain != domain:
                continue
            score = len(tokens & node.search_blob())
            if score > 0:
                scored.append((score, node))
        scored.sort(key=lambda x: (-x[0], x[1].ref))
        return [n for _, n in scored[:limit]]

    def domain_nodes(self, domain: str) -> list[WikiNode]:
        """Axioms + active project nodes for a domain, in load order."""
        return [n for n in self.wiki.values() if n.domain == domain]

    def global_foundation(self) -> list[WikiNode]:
        return [n for n in self.wiki.values() if n.scope == "global"]

    # -- the orient bundle --------------------------------------------------
    def orient(self, goal: str, domain: str | None = None) -> dict[str, Any]:
        """Assemble a concise, relevance-ranked context bundle for a goal.

        This is the "understand the goal" third of the loop. It returns full
        content only for the items most relevant to the goal (matched global
        nodes + the active domain's axioms/project), and lists everything else
        as refs the caller can pull on demand - keeping context flow concise.
        """
        domain = domain or self.infer_domain(goal)
        matched = {n.ref for n in self.rank_wiki(goal, domain)}

        foundation = []
        for n in self.global_foundation():
            item = {"ref": f"canon://{n.ref}", "title": n.title, "tags": n.tags}
            if n.ref in matched:
                item["content"] = self.resolve(n.ref)[1]
            foundation.append(item)

        domain_context = []
        if domain:
            for n in self.domain_nodes(domain):
                domain_context.append(
                    {
                        "ref": f"canon://{n.ref}",
                        "title": n.title,
                        "content": self.resolve(n.ref)[1],
                    }
                )

        skills = []
        for sk in self.rank_skills(goal, domain):
            s = sk.summary()
            s["ref"] = f"canon://skills/{sk.name}"
            if sk.backing:
                s["run"] = f"laplace_run(skill={sk.name!r}, target=...)"
            skills.append(s)

        return {
            "goal": goal,
            "domain": domain,
            "loop": (
                "orient (you are here) -> execute via laplace_skill / laplace_run "
                "-> verify via laplace_verify; mismatch re-enters orient"
            ),
            "foundation": foundation,
            "domain_context": domain_context,
            "skills": skills,
            "available_refs": sorted(
                [f"canon://{r}" for r in self.wiki]
                + [f"canon://skills/{n}" for n in self.skills]
            ),
        }


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


@lru_cache(maxsize=1)
def _cached_canon(root_str: str) -> Canon:
    return Canon.load(Path(root_str))


def get_canon(fresh: bool = False) -> Canon:
    """Return the active canon. ``fresh=True`` reloads from disk (after edits)."""
    root = str(canon_root())
    if fresh:
        _cached_canon.cache_clear()
    return _cached_canon(root)
