"""Unit tests for the Laplace canon graph projector (graph.py)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mcp_gerard.laplace.canon import Canon
from mcp_gerard.laplace.graph import CanonGraph, render

pytestmark = pytest.mark.unit


@pytest.fixture
def linked_canon(tmp_path: Path) -> Canon:
    """A small canon with a known link topology.

    Pages and links exercise every edge kind: a structural domain->axioms edge,
    a wiki->wiki ``[[tail]]`` link, a wiki->skill ``canon://`` link, a
    skill->skill link, a wiki->agent ``canon://agents`` link, and one broken
    link.
    """
    root = tmp_path / "canon"
    (root / "wiki" / "aesthetics").mkdir(parents=True)
    (root / "wiki" / "author").mkdir(parents=True)
    (root / "wiki" / "domains" / "synthetics").mkdir(parents=True)
    (root / "agents").mkdir(parents=True)
    for sk in ("epistemic_ledger", "result_foundry", "lonely_skill"):
        (root / "skills" / sk).mkdir(parents=True)

    (root / "index.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            wiki:
              aesthetics/voice_and_style: {title: The Laplace Voice, scope: global, tags: [voice]}
              author/the_author: {title: The Author, scope: global, tags: [author]}
            domains:
              synthetics:
                axioms: domains/synthetics/axioms
                tags: [synthetics]
            skills:
              epistemic_ledger: {description: ledger, activity: evaluating, status: core, tags: [latex]}
              result_foundry: {description: foundry, activity: staging, status: experimental, tags: [core]}
              lonely_skill: {description: nobody links here, activity: staging, status: deprecated, tags: []}
            """
        ),
        encoding="utf-8",
    )
    (root / "lifecycle.yaml").write_text("skills: {}\n", encoding="utf-8")
    (root / "agents" / "the_dreamer.yaml").write_text(
        "name: the_dreamer\nrole: Metacognitive R&R node\n", encoding="utf-8"
    )

    # voice -> author via [[tail]]; voice -> epistemic_ledger and -> agent via canon://.
    (root / "wiki" / "aesthetics" / "voice_and_style.md").write_text(
        "# The Laplace Voice\n\nShared with [[the_author]], proofed by "
        "canon://skills/epistemic_ledger, refined by canon://agents/the_dreamer.yaml.\n",
        encoding="utf-8",
    )
    (root / "wiki" / "author" / "the_author.md").write_text(
        "# The Author\n\nThe method counterpart to the voice.\n", encoding="utf-8"
    )
    (root / "wiki" / "domains" / "synthetics" / "axioms.md").write_text(
        "# Axioms\n\nGenerality first.\n", encoding="utf-8"
    )
    # skill -> skill link, plus a broken link to a page that does not exist.
    (root / "skills" / "epistemic_ledger" / "SKILL.md").write_text(
        "---\ndescription: ledger\n---\n\nPairs with [[result_foundry]] and "
        "[[a_page_that_does_not_exist]].\n",
        encoding="utf-8",
    )
    (root / "skills" / "result_foundry" / "SKILL.md").write_text(
        "---\ndescription: foundry\n---\n\nThe innermost ring.\n", encoding="utf-8"
    )
    (root / "skills" / "lonely_skill" / "SKILL.md").write_text(
        "---\ndescription: nobody links here\n---\n\nIsolated.\n", encoding="utf-8"
    )
    return Canon.load(root)


def _edge(g: CanonGraph, src: str, dst: str) -> bool:
    return any(e.src == src and e.dst == dst and e.rel != "dangling" for e in g.edges)


def test_nodes_cover_wiki_skills_domains_agents(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert "wiki:aesthetics/voice_and_style" in g.nodes
    assert "skill:epistemic_ledger" in g.nodes
    assert "domain:synthetics" in g.nodes
    assert "agent:the_dreamer" in g.nodes


def test_tail_wikilink_resolves(linked_canon: Canon):
    """A ``[[the_author]]`` link resolves to the full ref by its path tail - the
    exact case the harness display kept garbling, asserted as a hard bit."""
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert _edge(g, "wiki:aesthetics/voice_and_style", "wiki:author/the_author")
    assert "missing:the_author" not in g.nodes


def test_canon_uri_link_resolves_to_skill(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert _edge(g, "wiki:aesthetics/voice_and_style", "skill:epistemic_ledger")


def test_canon_uri_link_resolves_to_agent(linked_canon: Canon):
    """canon://agents/the_dreamer.yaml is a real edge, not a dangling target."""
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert _edge(g, "wiki:aesthetics/voice_and_style", "agent:the_dreamer")
    assert not any(d["to"] == "agents/the_dreamer.yaml" for d in g.health()["dangling"])


def test_structural_domain_edges(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert _edge(g, "domain:synthetics", "wiki:domains/synthetics/axioms")


def test_broken_link_becomes_dangling_with_provenance(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    h = g.health()
    assert "missing:a_page_that_does_not_exist" in g.nodes
    bad = next(d for d in h["dangling"] if d["to"] == "a_page_that_does_not_exist")
    assert "[[a_page_that_does_not_exist]]" in bad["evidence"]


def test_template_placeholder_is_not_dangling(linked_canon: Canon, tmp_path: Path):
    """A prose placeholder like canon://domains/.../projects/<project> is a
    template, not a broken link - it must not pollute the health report."""
    sk = linked_canon.skills["result_foundry"]
    sk.skill_md.write_text(
        "---\ndescription: foundry\n---\n\nWrites to "
        "`canon://domains/.../projects/<project>` on close.\n",
        encoding="utf-8",
    )
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert not any("..." in d["to"] or "<" in d["to"] for d in g.health()["dangling"])


def test_orphan_detection(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    h = g.health()
    assert "skill:lonely_skill" in h["orphans"]
    assert "wiki:author/the_author" not in h["orphans"]


def test_dead_wood_not_flagged_unless_linked(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    assert g.health()["dead_wood_linked"] == []


def test_focus_subgraph_is_bounded(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    sub = g.focus("wiki:aesthetics/voice_and_style", depth=1)
    assert "wiki:author/the_author" in sub.nodes
    assert "skill:lonely_skill" not in sub.nodes


def test_mermaid_render_is_wellformed(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    m = g.to_mermaid()
    assert m.startswith("graph ")
    assert "classDef" in m
    assert "skill_dead" in m  # the deprecated skill gets the dead-wood class


def test_canvas_render_is_valid_jsoncanvas(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    canvas = g.to_canvas()
    assert isinstance(canvas["nodes"], list) and canvas["nodes"]
    for n in canvas["nodes"]:
        assert {"id", "type", "x", "y", "width", "height"} <= set(n)
    json.loads(json.dumps(canvas))  # round-trips, it is written verbatim


def test_json_render_round_trips(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=False)
    s = json.dumps(g.to_json())
    assert json.loads(s)["health"]["node_count"] >= 6


def test_render_focus_unknown_node_reports_closest(linked_canon: Canon, monkeypatch):
    import mcp_gerard.laplace.graph as gmod

    monkeypatch.setattr(gmod, "get_canon", lambda *a, **k: linked_canon)
    res = render("mermaid", focus="no_such_node")
    assert "error" in res and "closest" in res


def test_fitness_weighting_is_defensive(linked_canon: Canon):
    g = CanonGraph.from_canon(linked_canon, with_fitness=True)
    for n in g.nodes.values():
        assert 0.0 <= n.weight <= 1.0


# --- manuscript projection: the same graph object, a different source --------


@pytest.fixture
def manuscript(tmp_path: Path) -> Path:
    p = tmp_path / "main.tex"
    p.write_text(
        textwrap.dedent(
            r"""
            \section{Introduction}
            We motivate the work and point ahead to \ref{fig:overview}.
            \section{Main Result}
            The core identity is
            \begin{equation}\label{eq:core} E = mc^2. \end{equation}
            \begin{figure}
              \includegraphics{overview.png}
              \caption{An overview of the construction.}
              \label{fig:overview}
            \end{figure}
            \section{Discussion}
            Equation \eqref{eq:core} closes the argument, see also \ref{eq:ghost}.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return p


def test_manuscript_builds_section_figure_equation_nodes(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    kinds = {n.kind for n in g.nodes.values()}
    assert {"section", "figure", "equation"} <= kinds


def test_manuscript_section_sequence_and_containment(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    rels = {(e.src.split(":")[0], e.rel, e.dst.split(":")[0]) for e in g.edges}
    assert ("sec", "precedes", "sec") in rels
    assert ("sec", "contains", "eq") in rels
    assert ("sec", "contains", "fig") in rels


def test_manuscript_cross_reference_edges(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    assert any(e.rel == "references" and e.dst == "eq:eq_core" for e in g.edges)


def test_manuscript_broken_ref_is_dangling(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    assert any(d["to"] == "eq:ghost" for d in g.health()["dangling"])


def test_manuscript_renders_through_same_projections(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    assert g.to_mermaid().startswith("graph ")
    assert g.to_canvas()["nodes"]
    json.loads(json.dumps(g.to_json()))


def test_core_outward_ring_classification(manuscript: Path):
    g = CanonGraph.from_manuscript(manuscript)
    groups = {n.label: n.group for n in g.nodes.values() if n.kind == "section"}
    assert groups["Main Result"] == "ring_core"
    assert groups["Introduction"] == "ring_outer"


def test_real_canon_renders_and_reports_health():
    """Smoke test against the live packaged canon - it must build and self-report."""
    g = CanonGraph.from_canon(with_fitness=False)
    h = g.health()
    assert h["node_count"] > 30
    assert g.to_mermaid().startswith("graph ")
    assert isinstance(h["components"], int)
