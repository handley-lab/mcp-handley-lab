"""Entry point for Google Calendar MCP server."""
from .tool import mcp


def main():
    """Run the Google Calendar MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()