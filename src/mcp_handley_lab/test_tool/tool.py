"""Test tool for verifying MCP cancellation behavior."""

import anyio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Test Tool")


def log_debug(message: str):
    """Log debug messages to a file for visibility during testing."""
    with open("/tmp/test_tool_debug.log", "a") as f:
        f.write(f"[TEST_TOOL DEBUG] {message}\n")
        f.flush()


@mcp.tool(description="Echo hello world and pause for 10 seconds to test cancellation")
async def hello_with_pause() -> str:
    """Echo hello world, then pause for 10 seconds."""
    log_debug("hello_with_pause() started")
    result = "Hello, World!"

    log_debug("Starting 10-second pause loop")
    for i in range(10):
        log_debug(f"Sleep iteration {i+1}/10")
        await anyio.sleep(1)

    log_debug("Completed all sleep iterations successfully")
    return f"{result} - Completed after 10 second pause"


@mcp.tool(description="Simple echo without delay")
def hello_simple() -> str:
    """Simple echo without delay."""
    return "Hello, World! (instant)"


@mcp.tool(description="Check server status")
def server_info() -> str:
    """Get server status information."""
    return """Test Tool Server Status
==========================
Status: Connected and ready

Available tools:
- hello_with_pause: Echo hello world and pause for 10 seconds
- hello_simple: Simple echo without delay
- server_info: Get server status"""
