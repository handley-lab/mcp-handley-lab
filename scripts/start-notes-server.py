#!/usr/bin/env python3
"""Startup script for the persistent Notes MCP server."""
import os

from mcp_handley_lab.notes.server import main

if __name__ == "__main__":
    # Set default environment variables if not set
    os.environ.setdefault("NOTES_SERVER_HOST", "localhost")
    os.environ.setdefault("NOTES_SERVER_PORT", "8765")

    print("🚀 Starting Notes MCP Server...")
    print("📡 Using StreamableHTTP transport")
    print("🔌 Server will run on: http://127.0.0.1:8000")
    print("🛑 Press Ctrl+C to stop")
    print()

    main()
