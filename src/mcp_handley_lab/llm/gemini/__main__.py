"""Entry point for Gemini LLM MCP server."""
from .tool import mcp


def main():
    """Run the Gemini MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()