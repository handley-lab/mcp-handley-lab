"""Shared MCP instance for unified email tool."""
from mcp.server.fastmcp import FastMCP

# Single, shared MCP instance for the entire email tool.
# All provider modules will import and use this instance.
mcp = FastMCP("Email")
