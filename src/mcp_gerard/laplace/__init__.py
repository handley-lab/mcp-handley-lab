"""The Laplace Engine: a cross-LLM, self-refining drafting canon served over MCP.

The engine exposes the tripartite task loop - orient (understand the goal and load
relevant canon), execute (translate the goal into a local action), and verify
(translate the result back and check consistency) - plus a slow self-refinement
loop (assess + dream) governed by measured skill fitness.
"""

from mcp_gerard.laplace.canon import Canon, canon_root

__all__ = ["Canon", "canon_root"]
