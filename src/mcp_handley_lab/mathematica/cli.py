#!/usr/bin/env python3
"""
Mathematica MCP Tool CLI Entry Point

Command-line interface for the Mathematica MCP server.
"""

import sys
import logging
from .tool import mcp

def main():
    """Main entry point for the Mathematica MCP tool."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        print("\n👋 Mathematica MCP server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error running Mathematica MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()