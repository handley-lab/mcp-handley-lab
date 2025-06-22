"""Entry point for JQ MCP server."""
from .tool import mcp


def main():
    """Run the JQ MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()