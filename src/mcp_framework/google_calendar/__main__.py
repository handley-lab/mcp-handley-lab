"""Main entry point for Google Calendar MCP server."""
import asyncio
from .tool import mcp

def main():
    """Run the Google Calendar MCP server."""
    return asyncio.run(mcp.run())

if __name__ == "__main__":
    main()