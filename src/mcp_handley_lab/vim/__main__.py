"""Entry point for Vim MCP server."""
from .tool import mcp


def main():
    """Run the Vim MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()