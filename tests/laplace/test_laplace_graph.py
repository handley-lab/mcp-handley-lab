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


# --- the interlock layer: claims, citations, and the figure forms -----------


@pytest.fixture
def rich_manuscript(tmp_path: Path) -> Path:
    """A manuscript exercising every interlock node kind: a claim that leans on
    an equation and a citation, section- and claim-level cites, a figure env, a
    bare TikZ schematic, and a back-reference to the claim."""
    p = tmp_path / "rich.tex"
    p.write_text(
        textwrap.dedent(
            r"""
            \section{Introduction}
            Background, citing \cite{shannon1948,jaynes1957}. See \ref{fig:loop}.
            \section{Main Result}
            \begin{equation}\label{eq:core} F = U - TS. \end{equation}
            \begin{result}[Closure]\label{res:closure}
            The closure identity \eqref{eq:core} holds, following \citet{zwanzig1961}.
            \end{result}
            \begin{figure}
              \includegraphics{loop.pdf}
              \caption{The adaptive loop.}
              \label{fig:loop}
            \end{figure}
            A bare schematic:
            \begin{tikzpicture}\label{fig:bare} \draw (0,0)--(1,1); \end{tikzpicture}
            \section{Discussion}
            We refer back to \ref{res:closure} and cite \cite{shannon1948}.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return p


def test_claim_node_with_optional_name(rich_manuscript: Path):
    g = CanonGraph.from_manuscript(rich_manuscript)
    claims = {n.id: n for n in g.nodes.values() if n.kind == "claim"}
    assert "claim:res_closure" in claims
    assert claims["claim:res_closure"].label == "Closure"
    assert claims["claim:res_closure"].meta["env"] == "result"


def test_claim_contained_and_supported_by_equation(rich_manuscript: Path):
    """A claim belongs to its section and points at the equation it invokes -
    the claim->evidence edge the interlock graph exists to make visible."""
    g = CanonGraph.from_manuscript(rich_manuscript)
    assert _edge(g, "sec:main_result", "claim:res_closure")  # contains
    assert any(
        e.src == "claim:res_closure" and e.dst == "eq:eq_core" and e.rel == "supported_by"
        for e in g.edges
    )


def test_citations_are_nodes_with_section_and_claim_edges(rich_manuscript: Path):
    g = CanonGraph.from_manuscript(rich_manuscript)
    cites = {n.id for n in g.nodes.values() if n.kind == "citation"}
    assert {"cite:shannon1948", "cite:jaynes1957", "cite:zwanzig1961"} <= cites
    # section -> citation (intro cites shannon) and claim -> citation (the \citet
    # inside the result env is attributed to the claim, not just its section).
    assert any(e.src == "sec:introduction" and e.dst == "cite:shannon1948" and e.rel == "cites" for e in g.edges)
    assert any(e.src == "claim:res_closure" and e.dst == "cite:zwanzig1961" and e.rel == "cites" for e in g.edges)


def test_bare_tikz_is_a_figure_but_includegraphics_in_env_is_not_doubled(rich_manuscript: Path):
    g = CanonGraph.from_manuscript(rich_manuscript)
    figs = {n.id: n for n in g.nodes.values() if n.kind == "figure"}
    assert figs["fig:fig_bare"].meta.get("tikz") is True  # bare TikZ became a figure
    assert "fig:fig_loop" in figs  # the figure env
    # the \includegraphics inside that env must not spawn a second figure node
    assert not any(n.endswith("loop_pdf") for n in figs)


def test_backreference_to_claim_resolves(rich_manuscript: Path):
    """A \\ref to a claim's label is a real reference edge, never a dangling one."""
    g = CanonGraph.from_manuscript(rich_manuscript)
    assert _edge(g, "sec:discussion", "claim:res_closure")
    assert not any(d["to"] == "res:closure" for d in g.health()["dangling"])


def test_input_order_beats_sorted_filenames(tmp_path: Path):
    """Pointed at a root file, sections follow \\input order - the case a
    sorted-glob directory merge would get backwards."""
    root = tmp_path / "main.tex"
    (tmp_path / "parts").mkdir()
    (tmp_path / "parts" / "zeta.tex").write_text(r"\section{Zeta Section}" + "\n", encoding="utf-8")
    (tmp_path / "parts" / "alpha.tex").write_text(r"\section{Alpha Section}" + "\n", encoding="utf-8")
    root.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\input{parts/zeta}\n\\input{parts/alpha}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    g = CanonGraph.from_manuscript(root)
    order = {n.label: n.meta["order"] for n in g.nodes.values() if n.kind == "section"}
    assert order["Zeta Section"] == 0 and order["Alpha Section"] == 1
    assert _edge(g, "sec:zeta_section", "sec:alpha_section")  # precedes


_LAW_OF_LAWS = Path(
    r"C:\Users\gerar\VScodeProjects\physics_paper_orchestra"
    r"\law-of-laws\manuscript\tex_v5\main.tex"
)


@pytest.mark.skipif(not _LAW_OF_LAWS.exists(), reason="orchestra manuscript not present on this machine")
def test_real_manuscript_interlock_builds():
    """Smoke test against a live orchestra manuscript - it must build a rich
    interlock graph and honour \\input reading order."""
    g = CanonGraph.from_manuscript(_LAW_OF_LAWS)
    kinds = {n.kind for n in g.nodes.values()}
    assert {"section", "figure", "equation", "citation"} <= kinds
    order = {n.label: n.meta["order"] for n in g.nodes.values() if n.kind == "section"}
    scaling = next(o for lbl, o in order.items() if "scaling" in lbl.lower())
    discussion = next(o for lbl, o in order.items() if lbl.strip().lower() == "discussion")
    assert scaling < discussion  # \input order; a sorted-glob merge would reverse this
    assert g.to_mermaid().startswith("graph ")
    json.loads(json.dumps(g.to_json()))
    assert g.health()["node_count"] > 30
