#!/usr/bin/env python3
"""Test script to understand FastMCP cancellation handling."""

import asyncio
import json
import sys
from typing import Any

import fastmcp


# Create a simple test server
app = fastmcp.FastMCP("test-cancellation")


@app.tool
async def slow_task(duration: int = 10) -> str:
    """A tool that simulates a long-running task."""
    try:
        print(f"Starting slow task for {duration} seconds", file=sys.stderr)
        await asyncio.sleep(duration)
        return f"Task completed after {duration} seconds"
    except asyncio.CancelledError:
        print("Task was cancelled!", file=sys.stderr)
        # Convert to RuntimeError as requested
        raise RuntimeError("Task cancelled by user")


@app.tool  
async def fast_task() -> str:
    """A tool that completes quickly."""
    return "Fast task completed"


if __name__ == "__main__":
    app.run()