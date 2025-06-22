"""Entry point for Code2Prompt MCP server."""
from .tool import mcp


def main():
    """Run the Code2Prompt MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()