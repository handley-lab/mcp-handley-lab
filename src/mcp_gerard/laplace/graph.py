"""The canon as one typed graph, projected into many renders.

The Laplace canon is already a graph: wiki nodes, skills, and domains, wired by
``[[name]]`` wikilinks and ``canon://`` references in the prose, plus the
structural belongs-to relations between a domain and its axioms, projects, and
skills. This module makes that latent graph explicit as a single ``CanonGraph``
object, then projects it into whatever surface the moment needs - Mermaid for a
note or a PDF, an Obsidian Canvas for the vault, a graph-config for Obsidian's
native view, or a plain JSON edge list for any interactive viewer.

The design follows the canon's own discipline: synthesise, do not partition.
AutoSci (the repo this was scouted from) keeps three separate graphs - a wiki
graph, a manuscript DAG, and a claim-dependency graph. Here there is one node
and edge model. A manuscript-structure graph is the same object built from a
different source, so every renderer below serves it for free once it lands.

Two things this does that a static export does not:

* **Provenance on every edge.** Each link carries the line of prose it was
  found in (``evidence``) and the file it came from (``source``). A link is
  never asserted without the text that justifies it.
* **Fitness-weighted nodes.** A skill node's weight is its measured fitness
  from the telemetry ledger, not a hand-set importance. The rendered graph is a
  self-portrait of the engine: load-bearing skills render large and bright, dead
  wood renders faint. Health is a property of the topology - orphans, dangling
  links, and deprecated-but-still-linked skills are first-class findings.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable

from mcp_gerard.laplace.canon import Canon, _split_frontmatter, get_canon

# ---------------------------------------------------------------------------
# Extraction patterns
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_CANON_RE = re.compile(r"canon://([A-Za-z0-9_./-]+)")

# Group palettes. Hex for Mermaid/JSON; Obsidian's graph + canvas use a built-in
# palette indexed "1".."6", so each group also carries a canvas colour id.
_WIKI_SECTION_HEX = {
    "aesthetics": "#EC4899",
    "operations": "#4A90D9",
    "structure": "#84CC16",
    "workflow": "#F39C12",
    "templates": "#95A5A6",
    "author": "#2ECC71",
    "voice_corpus": "#1ABC9C",
    "domains": "#E67E22",
}
_ACTIVITY_HEX = {
    "generating": "#F39C12",
    "staging": "#4A90D9",
    "evaluating": "#9B5DE5",
}
_DOMAIN_HEX = "#E74C3C"
_AGENT_HEX = "#F1C40F"
_MISSING_HEX = "#C0392B"

# Manuscript-projection groups (the same graph, a different source). A section
# is coloured by its core-outward ring when the title exposes one, else a
# neutral section hue. Claims and citations are the interlock layer above the
# structure - what the prose asserts, and what it leans on.
_MANUSCRIPT_HEX = {
    "section": "#4A90D9",
    "figure": "#16A085",
    "equation": "#9B5DE5",
    "claim": "#D35400",
    "citation": "#7F8C8D",
    "ring_core": "#E74C3C",
    "ring_inner": "#F39C12",
    "ring_outer": "#4A90D9",
}

# Obsidian/Canvas palette ids (built-in: 1 red, 2 orange, 3 yellow, 4 green,
# 5 cyan, 6 purple). One per group, chosen for mutual contrast.
_GROUP_CANVAS_COLOR = {
    "aesthetics": "6",
    "operations": "5",
    "structure": "4",
    "workflow": "3",
    "templates": "2",
    "author": "4",
    "voice_corpus": "5",
    "domains": "2",
    "generating": "3",
    "staging": "5",
    "evaluating": "6",
    "domain": "1",
    "missing": "1",
    "section": "5",
    "figure": "4",
    "equation": "6",
    "claim": "2",
    "citation": "5",
    "ring_core": "1",
    "ring_inner": "3",
    "ring_outer": "5",
    "agent": "3",
}

# Section-title heuristics for the core-outward ring (canon://workflow/core_outward_trunk).
_RING_CORE = re.compile(r"\b(result|theorem|main|core|derivation)\b", re.I)
_RING_OUTER = re.compile(
    r"\b(intro|introduction|related|background|discussion|conclusion|appendix)\b", re.I
)

# Manuscript-structure extraction. The interlock layer above sections/equations:
# claims (theorem-like environments), the citations the prose leans on, and the
# figure forms a section can hold - a full figure env, a bare TikZ picture, or a
# loose \includegraphics. \input/\include drive the true reading order.
_CLAIM_ENVS = (
    "theorem", "lemma", "proposition", "corollary", "claim",
    "conjecture", "definition", "assumption", "result", "remark",
)
_CLAIM_RE = re.compile(
    r"\\begin\{(" + "|".join(_CLAIM_ENVS) + r")\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}",
    re.DOTALL,
)
_CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|autocite|textcite|parencite)"
    r"\*?(?:\[[^\]]*\])*\{([^}]+)\}"
)
_TIKZ_RE = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.DOTALL)
_INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")
_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
_REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|pageref)\{([^}]+)\}")


def _group_hex(group: str) -> str:
    if group in _WIKI_SECTION_HEX:
        return _WIKI_SECTION_HEX[group]
    if group in _ACTIVITY_HEX:
        return _ACTIVITY_HEX[group]
    if group in _MANUSCRIPT_HEX:
        return _MANUSCRIPT_HEX[group]
    if group == "domain":
        return _DOMAIN_HEX
    if group == "agent":
        return _AGENT_HEX
    if group == "missing":
        return _MISSING_HEX
    return "#7F8C8D"


# ---------------------------------------------------------------------------
# Data model - one node, one edge, for every projection
# ---------------------------------------------------------------------------


@dataclass
class Node:
    id: str  # stable: "wiki:<ref>" | "skill:<name>" | "domain:<name>" | "missing:<token>"
    kind: str  # wiki | skill | domain | missing
    label: str
    group: str  # colour bucket: wiki section | skill activity | "domain" | "missing"
    status: str | None = None  # skill lifecycle: core | experimental | deprecated
    weight: float = 0.5  # 0..1; skill fitness, else a neutral prior
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    rel: str  # links_to | belongs_to_domain | has_axioms | has_project | dangling
    evidence: str = ""  # the line of prose the link was found in
    source: str = ""  # the file the edge was extracted from
    count: int = 1  # collapsed parallel links


@dataclass
class CanonGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    # -- construction -------------------------------------------------------
    @classmethod
    def from_canon(
        cls, canon: Canon | None = None, with_fitness: bool = True
    ) -> CanonGraph:
        """Extract the typed graph latent in the canon.

        Nodes are every wiki page, skill, and domain. Edges are the structural
        belongs-to relations plus every ``[[name]]`` and ``canon://`` link found
        in the prose, each carrying the line it came from. Unresolved links
        become ``dangling`` edges into a synthetic ``missing:`` node, so a broken
        cross-reference is visible rather than silently dropped.
        """
        canon = canon or get_canon()
        g = cls()

        # Nodes: domains, wiki pages, skills.
        for dname in canon.domains():
            g.nodes[f"domain:{dname}"] = Node(
                id=f"domain:{dname}",
                kind="domain",
                label=dname,
                group="domain",
                meta={"tags": (canon.domains()[dname] or {}).get("tags", [])},
            )
        for ref, n in canon.wiki.items():
            g.nodes[f"wiki:{ref}"] = Node(
                id=f"wiki:{ref}",
                kind="wiki",
                label=n.title,
                group=_wiki_group(ref),
                meta={"ref": f"canon://{ref}", "scope": n.scope, "domain": n.domain, "tags": n.tags},
            )

        fitness = _fitness_map(canon) if with_fitness else {}
        for name, sk in canon.skills.items():
            g.nodes[f"skill:{name}"] = Node(
                id=f"skill:{name}",
                kind="skill",
                label=name,
                group=sk.activity if sk.activity in _ACTIVITY_HEX else "staging",
                status=sk.status,
                weight=float(fitness.get(name, 0.5)),
                meta={
                    "domain": sk.domain,
                    "backing": sk.backing,
                    "tags": sk.tags,
                    "fitness": fitness.get(name),
                },
            )

        # Agent personas (canon/agents/*.yaml). The canon prose links to these
        # via canon://agents/<name>.yaml, so they are real nodes, not dangling
        # targets. They are the dream-loop's actors - the dreamer and the
        # empiricist - so the graph shows who acts on the canon, not just what.
        agents_dir = canon.root / "agents"
        if agents_dir.is_dir():
            for ay in sorted(agents_dir.glob("*.yaml")):
                aname = ay.stem
                role = _agent_role(ay)
                g.nodes[f"agent:{aname}"] = Node(
                    id=f"agent:{aname}", kind="agent", label=aname, group="agent",
                    meta={"role": role, "ref": f"canon://agents/{aname}.yaml"},
                )

        # Resolution index for [[name]] and canon:// targets.
        resolver = g._build_resolver(canon)

        # Structural edges: domain -> axioms / projects, skill -> its domain.
        for dname, dmeta in canon.domains().items():
            dmeta = dmeta or {}
            ax = dmeta.get("axioms")
            if ax and f"wiki:{ax}" in g.nodes:
                g.edges.append(Edge(f"domain:{dname}", f"wiki:{ax}", "has_axioms", source="index.yaml"))
            for pref in (dmeta.get("projects") or {}).values():
                if f"wiki:{pref}" in g.nodes:
                    g.edges.append(Edge(f"domain:{dname}", f"wiki:{pref}", "has_project", source="index.yaml"))
        for name, sk in canon.skills.items():
            if sk.domain and sk.domain != "global" and f"domain:{sk.domain}" in g.nodes:
                g.edges.append(Edge(f"skill:{name}", f"domain:{sk.domain}", "belongs_to_domain", source="index.yaml"))

        # Prose edges: every [[name]] and canon:// link, with provenance.
        for ref, n in canon.wiki.items():
            g._extract_prose_edges(f"wiki:{ref}", n.path, resolver, canon)
        for name, sk in canon.skills.items():
            if sk.skill_md.exists():
                g._extract_prose_edges(f"skill:{name}", sk.skill_md, resolver, canon)

        g._collapse_parallel_edges()
        return g

    @classmethod
    def from_manuscript(cls, target) -> CanonGraph:
        """Build the SAME graph object from a LaTeX manuscript's structure.

        This is the synthesis the canon asks for: a manuscript is not a separate
        kind of graph, it is the same node/edge model sourced from ``.tex``
        instead of canon prose. Five node kinds make the interlock visible
        before the prose is read in order:

        * **sections** - in true reading order. A single root file is flattened
          along its ``\\input``/``\\include`` tree, so the section->section
          ``precedes`` chain follows how the paper is read, not how its files
          sort. A directory of loose section files falls back to sorted-glob
          merge (the crossref ledger's order).
        * **figures** - a full ``figure`` env, a bare ``tikzpicture``, or a
          loose ``\\includegraphics``. A section ``contains`` the figures in its
          span.
        * **equations** - every ``eq:`` label, contained by its section.
        * **claims** - theorem-like environments (result, proposition, lemma,
          ...). A claim is ``contains``ed by its section and ``supported_by`` the
          equations it states or invokes - the 'derive, do not assert' backbone
          the epistemic_ledger checks, here made navigable.
        * **citations** - every ``\\cite`` key. The section, and the claim if the
          cite sits inside one, ``cites`` it.

        A reference (``\\ref``/``\\eqref``) becomes an edge to the thing
        referenced, and a reference to a label never defined becomes a dangling
        edge, exactly as a broken wikilink does. Every renderer then serves this
        graph unchanged.

        ``target`` is a root ``.tex`` file (preferred - its ``\\input`` order is
        authoritative) or a directory of ``.tex`` files.
        """
        full = _gather_manuscript_text(target)

        g = cls()
        label_owner: dict[str, str] = {}

        # Sections -> nodes, with character spans so children can be attributed.
        spans: list[tuple[int, int, str]] = []
        sec_marks = [
            (m.start(), m.group(2))
            for m in re.finditer(r"\\(sub)?section\*?\{([^}]+)\}", full)
        ]
        for i, (start, name) in enumerate(sec_marks):
            end = sec_marks[i + 1][0] if i + 1 < len(sec_marks) else len(full)
            sid = f"sec:{_slug(name)}"
            if sid in g.nodes:
                sid = f"{sid}_{i}"  # disambiguate repeated titles
            g.nodes[sid] = Node(
                id=sid, kind="section", label=name, group=_ring_group(name),
                meta={"order": i, "ring": _ring_group(name)},
            )
            spans.append((start, end, sid))
            if i > 0:
                g.edges.append(Edge(spans[i - 1][2], sid, "precedes", source="structure"))
            # A section's own \label(s) sit before its first environment - a
            # section may carry several as aliases. Register each so a
            # \ref{sec:...} elsewhere resolves to this section (the
            # section->section interlock) rather than dangling.
            seg = full[start:end]
            cutoff = seg.find(r"\begin{")
            for lab_m in _LABEL_RE.finditer(seg):
                if cutoff != -1 and lab_m.start() >= cutoff:
                    break
                label_owner.setdefault(lab_m.group(1), sid)

        def _owner(pos: int) -> str | None:
            for s, e, sid in spans:
                if s <= pos < e:
                    return sid
            return None

        fig_spans: list[tuple[int, int]] = []

        def _add_figure(fid: str, label: str, owner_pos: int, meta: dict[str, Any]) -> None:
            g.nodes.setdefault(fid, Node(id=fid, kind="figure", label=label, group="figure", meta=meta))
            owner = _owner(owner_pos)
            if owner:
                g.edges.append(Edge(owner, fid, "contains", source="structure"))

        # Float envs (figure, table) -> figure nodes; a float belongs to the
        # section it sits in. A table is a labelled, captioned float that the
        # prose \refs exactly as a figure, so it interlocks the same way.
        for m in re.finditer(r"\\begin\{(figure|table)\*?\}(.*?)\\end\{\1\*?\}", full, re.DOTALL):
            env, body = m.group(1), m.group(2)
            fig_spans.append((m.start(), m.end()))
            lab = _LABEL_RE.search(body)
            cap = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.DOTALL)
            key = lab.group(1) if lab else f"{env}_{m.start()}"
            fid = f"fig:{_slug(key)}"
            _add_figure(fid, cap.group(1).strip()[:48] if cap else key, m.start(), {"label": key, "float": env})
            if lab:
                label_owner[lab.group(1)] = fid

        def _in_figure(pos: int) -> bool:
            return any(s <= pos < e for s, e in fig_spans)

        # A bare TikZ picture or a loose \includegraphics outside any figure env
        # is a figure in its own right - a schematic dropped straight into the
        # prose still interlocks with the section that holds it.
        for m in _TIKZ_RE.finditer(full):
            if _in_figure(m.start()):
                continue
            lab = _LABEL_RE.search(m.group(0))
            key = lab.group(1) if lab else f"tikz_{m.start()}"
            fid = f"fig:{_slug(key)}"
            _add_figure(fid, key, m.start(), {"label": key, "tikz": True})
            if lab:
                label_owner[lab.group(1)] = fid
        for m in _INCLUDEGRAPHICS_RE.finditer(full):
            if _in_figure(m.start()):
                continue
            fname = m.group(1).strip()
            _add_figure(f"fig:{_slug(fname)}", fname, m.start(), {"file": fname})

        # Equation labels -> nodes; an equation belongs to its section.
        for m in re.finditer(r"\\label\{(eq:[^}]+)\}", full):
            lab = m.group(1)
            eid = f"eq:{_slug(lab)}"
            g.nodes.setdefault(
                eid, Node(id=eid, kind="equation", label=lab, group="equation", meta={"label": lab})
            )
            label_owner[lab] = eid
            owner = _owner(m.start())
            if owner:
                g.edges.append(Edge(owner, eid, "contains", source="structure"))

        # Claims (theorem-like envs) -> nodes, contained by their section and
        # supported_by the equations they state or invoke. Cites inside a claim
        # are attributed to it in the citation pass below.
        claim_spans: list[tuple[int, int, str]] = []
        for i, m in enumerate(_CLAIM_RE.finditer(full)):
            env, body = m.group(1), m.group(2)
            lab = _LABEL_RE.search(body)
            name = re.match(r"\\begin\{" + re.escape(env) + r"\}\[([^\]]*)\]", m.group(0))
            key = lab.group(1) if lab else (name.group(1) if name else f"{env}_{i}")
            cid = f"claim:{_slug(key)}"
            if cid in g.nodes:
                cid = f"{cid}_{i}"
            g.nodes[cid] = Node(
                id=cid, kind="claim", label=(name.group(1) if name else key),
                group="claim", meta={"env": env, "label": lab.group(1) if lab else None},
            )
            claim_spans.append((m.start(), m.end(), cid))
            if lab:
                label_owner[lab.group(1)] = cid
            owner = _owner(m.start())
            if owner:
                g.edges.append(Edge(owner, cid, "contains", source="structure"))
            # claim -> evidence: every equation the claim states or references.
            ev = _line_at(full, m.start())
            eq_labels = set(re.findall(r"\\label\{(eq:[^}]+)\}", body)) | {
                r for r in _REF_RE.findall(body) if r.startswith("eq:")
            }
            for el in eq_labels:
                dst = label_owner.get(el, f"eq:{_slug(el)}")
                if dst in g.nodes:
                    g.edges.append(Edge(cid, dst, "supported_by", ev, "structure"))

        def _claim_owner(pos: int) -> str | None:
            for s, e, cid in claim_spans:
                if s <= pos < e:
                    return cid
            return None

        # Citations -> nodes; the section (and the claim, if any) that invokes a
        # reference cites it. Multiple keys in one \cite are separate citations.
        for m in _CITE_RE.finditer(full):
            ev = _line_at(full, m.start())
            owner = _owner(m.start())
            claim = _claim_owner(m.start())
            for key in (k.strip() for k in m.group(1).split(",")):
                if not key:
                    continue
                cnode = f"cite:{key}"
                g.nodes.setdefault(
                    cnode, Node(id=cnode, kind="citation", label=key, group="citation", meta={"key": key})
                )
                if owner:
                    g.edges.append(Edge(owner, cnode, "cites", ev, "structure"))
                if claim:
                    g.edges.append(Edge(claim, cnode, "cites", ev, "structure"))

        # References -> edges from the citing section to the referenced object.
        for m in _REF_RE.finditer(full):
            lab = m.group(1)
            owner = _owner(m.start())
            if owner is None:
                continue
            dst = label_owner.get(lab)
            ev = _line_at(full, m.start())
            if dst is None:
                miss = f"missing:{lab}"
                g.nodes.setdefault(miss, Node(id=miss, kind="missing", label=lab, group="missing"))
                g.edges.append(Edge(owner, miss, "dangling", ev, "structure"))
            elif dst != owner:
                g.edges.append(Edge(owner, dst, "references", ev, "structure"))

        g._collapse_parallel_edges()
        return g

    # -- internals ----------------------------------------------------------
    def _build_resolver(self, canon: Canon) -> dict[str, str]:
        """Map every token a link might use to a node id.

        Resolution order matters: an exact skill name or full wiki ref wins over
        a bare path tail, which is the ambiguous case (two pages can share a
        leaf name). On a tail collision the first by sorted ref wins, which is
        deterministic and good enough - the dangling check still catches a link
        that resolves to the wrong twin only if it points nowhere.
        """
        idx: dict[str, str] = {}
        for dname in canon.domains():
            idx.setdefault(dname, f"domain:{dname}")
        # Agents are addressed as agents/<name>.yaml or agents/<name> in prose.
        for nid in self.nodes:
            if nid.startswith("agent:"):
                aname = nid.split(":", 1)[1]
                idx[f"agents/{aname}.yaml"] = nid
                idx[f"agents/{aname}"] = nid
                idx.setdefault(aname, nid)
        # Tails first (lowest priority), so exact refs/names below overwrite them.
        for ref in sorted(canon.wiki):
            tail = ref.rsplit("/", 1)[-1]
            idx.setdefault(tail, f"wiki:{ref}")
        for ref in canon.wiki:
            idx[ref] = f"wiki:{ref}"
        for name in canon.skills:
            idx[name] = f"skill:{name}"
        return idx

    def _extract_prose_edges(
        self, src_id: str, path, resolver: dict[str, str], canon: Canon
    ) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return
        _, body = _split_frontmatter(text)
        source = path.name

        for m in _WIKILINK_RE.finditer(body):
            token = m.group(1).split("|", 1)[0].strip()
            token = token.rsplit("/", 1)[-1].removesuffix(".md")
            self._add_link(src_id, token, resolver, body, m.start(), source)

        for m in _CANON_RE.finditer(body):
            # The char class admits '.', so a link ending a sentence captures the
            # trailing full stop (canon://x.yaml.) - strip trailing punctuation
            # before resolving, then drop a bare .md page suffix.
            raw = m.group(1).strip().rstrip(".").removesuffix(".md")
            if raw.startswith("skills/"):
                token = raw.split("/", 1)[1]
            else:
                token = raw  # full wiki ref, or agents/<name>.yaml
            self._add_link(src_id, token, resolver, body, m.start(), source)

    def _add_link(
        self, src_id: str, token: str, resolver: dict[str, str],
        body: str, pos: int, source: str,
    ) -> None:
        if not token or "..." in token or any(c in token for c in "<>*"):
            return  # a prose template placeholder, not a real link
        dst = resolver.get(token)
        evidence = _line_at(body, pos)
        if dst is None:
            miss_id = f"missing:{token}"
            self.nodes.setdefault(
                miss_id,
                Node(id=miss_id, kind="missing", label=token, group="missing"),
            )
            self.edges.append(Edge(src_id, miss_id, "dangling", evidence, source))
            return
        if dst == src_id:
            return  # a page that names itself is not an edge
        self.edges.append(Edge(src_id, dst, "links_to", evidence, source))

    def _collapse_parallel_edges(self) -> None:
        seen: dict[tuple[str, str, str], Edge] = {}
        for e in self.edges:
            key = (e.src, e.dst, e.rel)
            if key in seen:
                seen[key].count += 1
            else:
                seen[key] = e
        self.edges = list(seen.values())

    # -- analytics ----------------------------------------------------------
    def neighbours(self, undirected: bool = True) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = defaultdict(set)
        for e in self.edges:
            adj[e.src].add(e.dst)
            if undirected:
                adj[e.dst].add(e.src)
        return adj

    def health(self) -> dict[str, Any]:
        """Topology as a health report.

        * orphans - real nodes (not ``missing``) with no edge at all
        * dangling - links into a non-existent target
        * dead_wood_linked - deprecated skills still pointed at by live prose
        * components - count of connected components over real nodes
        """
        adj = self.neighbours(undirected=True)
        real = {nid for nid, n in self.nodes.items() if n.kind != "missing"}
        orphans = sorted(nid for nid in real if not adj.get(nid))

        dangling = [
            {"from": e.src, "to": self.nodes[e.dst].label, "evidence": e.evidence, "source": e.source}
            for e in self.edges
            if e.rel == "dangling"
        ]

        deprecated = {
            nid for nid, n in self.nodes.items() if n.kind == "skill" and n.status == "deprecated"
        }
        dead_wood_linked = sorted(
            {e.dst for e in self.edges if e.rel == "links_to" and e.dst in deprecated}
        )

        return {
            "orphans": orphans,
            "dangling": dangling,
            "dead_wood_linked": dead_wood_linked,
            "components": self._component_count(real, adj),
            "node_count": len(real),
            "edge_count": sum(1 for e in self.edges if e.rel != "dangling"),
            "pass": not orphans and not dangling and not dead_wood_linked,
        }

    @staticmethod
    def _component_count(real: set[str], adj: dict[str, set[str]]) -> int:
        seen: set[str] = set()
        comps = 0
        for start in real:
            if start in seen:
                continue
            comps += 1
            stack = [start]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(n for n in adj.get(cur, ()) if n in real and n not in seen)
        return comps

    def focus(self, node_id: str, depth: int = 2) -> CanonGraph:
        """Return the BFS neighbourhood subgraph within ``depth`` hops of a node."""
        if node_id not in self.nodes:
            raise KeyError(f"node {node_id!r} not in graph")
        adj = self.neighbours(undirected=True)
        keep: dict[str, int] = {node_id: 0}
        q: deque[str] = deque([node_id])
        while q:
            cur = q.popleft()
            if keep[cur] >= depth:
                continue
            for nxt in adj.get(cur, ()):
                if nxt not in keep:
                    keep[nxt] = keep[cur] + 1
                    q.append(nxt)
        sub = CanonGraph(
            nodes={nid: self.nodes[nid] for nid in keep},
            edges=[e for e in self.edges if e.src in keep and e.dst in keep],
        )
        # Stash BFS depth for radial layout in the canvas renderer.
        for nid, d in keep.items():
            sub.nodes[nid].meta = {**sub.nodes[nid].meta, "_ring": d}
        return sub

    def filter_kinds(self, kinds: Iterable[str]) -> CanonGraph:
        keep = {nid for nid, n in self.nodes.items() if n.kind in set(kinds)}
        return CanonGraph(
            nodes={nid: self.nodes[nid] for nid in keep},
            edges=[e for e in self.edges if e.src in keep and e.dst in keep],
        )

    # -- projections --------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        """The interchange format. Any viewer - and any future graph source,
        like a manuscript-structure graph - speaks this."""
        return {
            "nodes": [
                {
                    "id": n.id, "kind": n.kind, "label": n.label, "group": n.group,
                    "status": n.status, "weight": round(n.weight, 3), "meta": n.meta,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "src": e.src, "dst": e.dst, "rel": e.rel,
                    "evidence": e.evidence, "source": e.source, "count": e.count,
                }
                for e in self.edges
            ],
            "health": self.health(),
        }

    def to_mermaid(self, direction: str = "LR") -> str:
        """A Mermaid ``graph`` - the universal projection, embeds in any
        markdown note or, via a filter, a manuscript appendix.

        Node shape and class carry meaning: a deprecated skill or an orphan
        renders in a warning class, a dangling link renders dashed into a ghost
        node. Skill node size tracks fitness through the class buckets.
        """
        lines = [f"graph {direction}"]
        groups: dict[str, list[str]] = defaultdict(list)
        classes: dict[str, str] = {}

        for n in self.nodes.values():
            nid = _mid(n.id)
            label = _esc(n.label)
            if n.kind == "missing":
                node = f'{nid}["{label}"]'
                classes[nid] = "dangling"
            elif n.kind == "domain":
                node = f'{nid}{{{{"{label}"}}}}'
                classes[nid] = "g_domain"
            elif n.kind == "skill":
                node = f'{nid}(["{label}"])'
                classes[nid] = _skill_class(n)
            else:
                node = f'{nid}["{label}"]'
                classes[nid] = f"g_{n.group}"
            groups[n.group].append(node)

        # Emit nodes grouped into subgraphs by colour bucket for readability.
        for group, decls in groups.items():
            lines.append(f"  subgraph {_mid('grp_'+group)}[{_esc(group)}]")
            for d in decls:
                lines.append(f"    {d}")
            lines.append("  end")

        for e in self.edges:
            arrow = "-.->|dangling|" if e.rel == "dangling" else (
                f"-->|{_esc(e.rel)}|" if e.rel != "links_to" else "-->"
            )
            lines.append(f"  {_mid(e.src)} {arrow} {_mid(e.dst)}")

        for nid, cls in classes.items():
            lines.append(f"  class {nid} {cls};")

        # classDefs: group colours, plus skill-fitness and warning buckets.
        for group in groups:
            if group in ("domain", "missing"):
                continue
            lines.append(f"  classDef g_{group} fill:{_group_hex(group)},color:#fff,stroke:#333;")
        lines.append(f"  classDef g_domain fill:{_DOMAIN_HEX},color:#fff,stroke:#000,stroke-width:2px;")
        lines.append("  classDef dangling fill:#fff,color:#900,stroke:#900,stroke-dasharray:4 3;")
        lines.append("  classDef skill_hot fill:#9B5DE5,color:#fff,stroke:#333,stroke-width:3px;")
        lines.append("  classDef skill_warm fill:#B388E0,color:#fff,stroke:#333;")
        lines.append("  classDef skill_cold fill:#E8DAF5,color:#333,stroke:#999;")
        lines.append("  classDef skill_dead fill:#eee,color:#999,stroke:#bbb,stroke-dasharray:3 3;")
        return "\n".join(lines)

    def to_obsidian_graph(self) -> dict[str, Any]:
        """An Obsidian ``graph.json`` colour-group config, one group per bucket.

        Obsidian colours by note path. Canon pages do not live in the vault by
        default, so the colour groups key off the label text - drop this beside a
        vault export of the canon and the groups light up."""
        groups = []
        seen: set[str] = set()
        for n in self.nodes.values():
            if n.group in seen or n.kind == "missing":
                continue
            seen.add(n.group)
            groups.append({"query": f"tag:#{n.group} OR path:{n.group}", "color": _rgb(_group_hex(n.group))})
        return {
            "colorGroups": groups,
            "showTags": True,
            "showAttachments": False,
            "collapse-filter": False,
            "scale": 1,
        }

    def to_canvas(self, radial: bool = False) -> dict[str, Any]:
        """An Obsidian ``.canvas`` (JSONCanvas). Force-clustered by group for the
        full map, or concentric rings by BFS depth when built from ``focus``.

        Layout is deterministic - positions come from group/ring indices and
        node order, never randomness, so the same graph always lays out the same
        way and a diff of two canvases is meaningful."""
        cnodes, cedges = [], []
        positions = self._radial_positions() if radial else self._clustered_positions()
        for n in self.nodes.values():
            x, y = positions[n.id]
            size = _canvas_size(n)
            cnodes.append({
                "id": _cid(n.id),
                "type": "text",
                "text": f"**{n.label}**" + (f"\n_{n.status}_" if n.status else ""),
                "x": int(x), "y": int(y),
                "width": size, "height": max(60, size // 3),
                "color": _GROUP_CANVAS_COLOR.get(n.group, "1"),
            })
        for i, e in enumerate(self.edges):
            cedges.append({
                "id": f"e{i}",
                "fromNode": _cid(e.src),
                "toNode": _cid(e.dst),
                "label": "" if e.rel == "links_to" else e.rel,
                "toEnd": "arrow",
                **({"color": "1"} if e.rel == "dangling" else {}),
            })
        return {"nodes": cnodes, "edges": cedges}

    # -- layouts (deterministic) -------------------------------------------
    def _clustered_positions(self) -> dict[str, tuple[float, float]]:
        by_group: dict[str, list[Node]] = defaultdict(list)
        for n in self.nodes.values():
            by_group[n.group].append(n)
        pos: dict[str, tuple[float, float]] = {}
        groups = sorted(by_group)
        ring_r = 1600
        for gi, group in enumerate(groups):
            ga = 2 * math.pi * gi / max(1, len(groups))
            cx, cy = ring_r * math.cos(ga), ring_r * math.sin(ga)
            members = sorted(by_group[group], key=lambda n: n.id)
            cols = max(1, int(math.ceil(math.sqrt(len(members)))))
            for mi, n in enumerate(members):
                row, col = divmod(mi, cols)
                pos[n.id] = (cx + col * 420 - cols * 210, cy + row * 200)
        return pos

    def _radial_positions(self) -> dict[str, tuple[float, float]]:
        rings: dict[int, list[Node]] = defaultdict(list)
        for n in self.nodes.values():
            rings[int(n.meta.get("_ring", 1))].append(n)
        pos: dict[str, tuple[float, float]] = {}
        for d, members in rings.items():
            members = sorted(members, key=lambda n: n.id)
            if d == 0:
                pos[members[0].id] = (0.0, 0.0)
                continue
            r = 700 * d
            for mi, n in enumerate(members):
                a = 2 * math.pi * mi / max(1, len(members))
                pos[n.id] = (r * math.cos(a), r * math.sin(a))
        return pos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wiki_group(ref: str) -> str:
    top = ref.split("/", 1)[0]
    return top if top in _WIKI_SECTION_HEX else "structure"


def _agent_role(path) -> str:
    """Pull the ``role:`` line from an agent yaml without a full parse."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("role:"):
                return line.split(":", 1)[1].strip()
    except (OSError, UnicodeError):
        pass
    return ""


def _read_tex(fp) -> str:
    try:
        return fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return fp.read_text(encoding="utf-16")


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*?$", "", text, flags=re.MULTILINE)


def _flatten_inputs(root, seen: set | None = None, depth: int = 0) -> str:
    """Inline every ``\\input``/``\\include`` from a root ``.tex``, in place.

    Section ordering in a multi-file manuscript lives in the root file's input
    sequence, not in sorted filenames - the discussion follows the results,
    appendices run a..k. Splicing each child where it is invoked recovers that
    true reading order, so the section ``precedes`` chain matches the paper. The
    ``seen`` set and depth cap guard against an include cycle.
    """
    from pathlib import Path

    root = Path(root)
    seen = set() if seen is None else seen
    rp = root.resolve()
    if rp in seen or depth > 32:
        return ""
    seen.add(rp)
    try:
        text = _strip_comments(_read_tex(root))
    except (OSError, UnicodeError):
        return ""

    def _repl(m: "re.Match[str]") -> str:
        cpath = root.parent / m.group(1).strip()
        if cpath.suffix != ".tex":
            cpath = cpath.with_suffix(".tex")
        return _flatten_inputs(cpath, seen, depth + 1)

    return _INPUT_RE.sub(_repl, text)


def _gather_manuscript_text(target) -> str:
    """Merge a manuscript's sources into one comment-stripped string.

    A single file is flattened along its ``\\input`` tree (true reading order).
    A directory is the sorted-glob fallback for a loose set of section files
    with no root, mirroring the crossref ledger's merge order.
    """
    from pathlib import Path

    target = Path(target)
    if target.is_dir():
        parts = []
        for fp in sorted(target.glob("**/*.tex")):
            try:
                parts.append(_strip_comments(_read_tex(fp)))
            except (OSError, UnicodeError):
                continue
        return "\n".join(parts)
    return _flatten_inputs(target)


def _ring_group(name: str) -> str:
    """Classify a section into a core-outward ring by its title."""
    if _RING_CORE.search(name):
        return "ring_core"
    if _RING_OUTER.search(name):
        return "ring_outer"
    return "section"


def _slug(s: str) -> str:
    s = re.sub(r"[:/\s\-]+", "_", s.strip())
    s = re.sub(r"[^A-Za-z0-9_]", "", s)
    return (s[:60] or "x").lower()


def _fitness_map(canon: Canon) -> dict[str, float]:
    """Per-skill fitness from telemetry, defensively. No ledger -> empty map and
    every skill keeps the neutral prior."""
    try:
        from mcp_gerard.laplace import assess as _assess

        return {name: float(d.get("fitness", 0.5)) for name, d in _assess.assess(canon).items()}
    except Exception:  # noqa: BLE001 - fitness is an enrichment, never a hard dep
        return {}


def _skill_class(n: Node) -> str:
    if n.status == "deprecated":
        return "skill_dead"
    if n.weight >= 0.66:
        return "skill_hot"
    if n.weight >= 0.45:
        return "skill_warm"
    return "skill_cold"


def _canvas_size(n: Node) -> int:
    if n.kind == "domain":
        return 360
    if n.kind == "skill":
        return int(220 + 360 * max(0.0, min(1.0, n.weight)))  # fitness -> size
    if n.kind == "missing":
        return 200
    return 320


def _line_at(body: str, pos: int) -> str:
    start = body.rfind("\n", 0, pos) + 1
    end = body.find("\n", pos)
    if end == -1:
        end = len(body)
    return body[start:end].strip()[:200]


_MID_RE = re.compile(r"[^A-Za-z0-9]")


def _mid(node_id: str) -> str:
    """A Mermaid-safe identifier."""
    return "n_" + _MID_RE.sub("_", node_id)


def _cid(node_id: str) -> str:
    return _MID_RE.sub("_", node_id)


def _esc(s: str) -> str:
    return s.replace('"', "'").replace("\n", " ").replace("|", "/")


def _rgb(hex_colour: str) -> int:
    """Obsidian graph colours are packed 0xRRGGBB integers."""
    return int(hex_colour.lstrip("#"), 16)


# ---------------------------------------------------------------------------
# Top-level API + CLI
# ---------------------------------------------------------------------------

_RENDERERS = ("mermaid", "json", "canvas", "obsidian")


def render(
    fmt: str = "mermaid",
    focus: str | None = None,
    depth: int = 2,
    kinds: list[str] | None = None,
    canon: Canon | None = None,
    manuscript: str | None = None,
) -> dict[str, Any]:
    """Build a graph and project it. Source is the canon by default, or a
    manuscript ``.tex``/directory when ``manuscript`` is given - the same
    renderers serve both. Returns the artifact plus a health summary, so a
    caller sees the topology's defects alongside the picture."""
    if manuscript:
        from pathlib import Path

        if not Path(manuscript).exists():
            return {"error": f"manuscript path not found: {manuscript}"}
        g = CanonGraph.from_manuscript(manuscript)
    else:
        g = CanonGraph.from_canon(canon)
    scoped = g
    if kinds:
        scoped = scoped.filter_kinds(kinds)
    radial = False
    if focus:
        fid = focus if focus in scoped.nodes else _match_node(scoped, focus)
        if fid is None:
            return {"error": f"focus node {focus!r} not found", "closest": _closest(scoped, focus)}
        scoped = scoped.focus(fid, depth)
        radial = True

    if fmt == "mermaid":
        artifact: Any = scoped.to_mermaid()
    elif fmt == "json":
        artifact = scoped.to_json()
    elif fmt == "canvas":
        artifact = scoped.to_canvas(radial=radial)
    elif fmt == "obsidian":
        artifact = scoped.to_obsidian_graph()
    else:
        return {"error": f"unknown format {fmt!r}", "formats": list(_RENDERERS)}

    return {
        "format": fmt,
        "focus": focus,
        "artifact": artifact,
        "health": g.health(),
        "stats": {"nodes": len(scoped.nodes), "edges": len(scoped.edges)},
    }


def _match_node(g: CanonGraph, token: str) -> str | None:
    if token in g.nodes:
        return token
    for prefix in ("skill:", "wiki:", "domain:"):
        if f"{prefix}{token}" in g.nodes:
            return f"{prefix}{token}"
    for nid, n in g.nodes.items():
        if n.label == token:
            return nid
    return None


def _closest(g: CanonGraph, token: str, k: int = 5) -> list[str]:
    t = token.lower()
    scored = sorted(
        ((sum(1 for c in t if c in nid.lower()), nid) for nid in g.nodes),
        reverse=True,
    )
    return [nid for _, nid in scored[:k]]


def _main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Project the Laplace canon graph.")
    p.add_argument("--format", default="mermaid", choices=_RENDERERS)
    p.add_argument("--focus", default=None, help="centre on a node (id, skill name, or label)")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--kinds", default=None, help="comma-separated: wiki,skill,domain (canon) or section,figure,equation,claim,citation (manuscript)")
    p.add_argument("--manuscript", default=None, help="build from a .tex file or directory instead of the canon")
    p.add_argument("--out", default=None, help="write artifact to a file")
    p.add_argument("--health", action="store_true", help="print only the health report")
    args = p.parse_args(argv)

    if args.health:
        g = CanonGraph.from_manuscript(args.manuscript) if args.manuscript else CanonGraph.from_canon()
        print(json.dumps(g.health(), indent=2))
        return 0

    kinds = args.kinds.split(",") if args.kinds else None
    res = render(args.format, args.focus, args.depth, kinds, manuscript=args.manuscript)
    if "error" in res:
        print(json.dumps(res, indent=2))
        return 1
    artifact = res["artifact"]
    text = artifact if isinstance(artifact, str) else json.dumps(artifact, indent=2)
    if args.out:
        from pathlib import Path

        Path(args.out).write_text(text, encoding="utf-8")
        h = res["health"]
        print(f"wrote {args.format} to {args.out}  ({res['stats']['nodes']} nodes, "
              f"{res['stats']['edges']} edges, {len(h['dangling'])} dangling, "
              f"{len(h['orphans'])} orphans)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
