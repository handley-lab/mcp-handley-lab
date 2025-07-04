#!/usr/bin/env python3
"""Test MCP tool cancellation behavior."""

import asyncio
import json
import subprocess
import sys


async def test_tool_cancellation():
    """Test that MCP tools handle cancellation correctly."""

    # Start the test tool MCP server
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_handley_lab.test_tool"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )

    try:
        # Initialize the server
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        # Read init response
        response = process.stdout.readline()
        print(f"✅ Init response: {response.strip()}")

        # Send initialized notification
        init_notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        process.stdin.write(json.dumps(init_notification) + "\n")
        process.stdin.flush()

        # FIRST: Test server responsiveness with a quick operation
        quick_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "hello_simple", "arguments": {}},
        }
        process.stdin.write(json.dumps(quick_request) + "\n")
        process.stdin.flush()
        print("🔄 Testing server responsiveness with hello_simple...")

        quick_response = await asyncio.wait_for(
            asyncio.create_task(asyncio.to_thread(process.stdout.readline)), timeout=2.0
        )
        print(f"✅ Quick response received: {quick_response.strip()}")

        # SECOND: Start the long-running tool
        tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "hello_with_pause", "arguments": {}},
        }
        process.stdin.write(json.dumps(tool_request) + "\n")
        process.stdin.flush()
        print("🚀 Started hello_with_pause tool (10 second pause)")

        # Wait a short time, then send a cancellation
        await asyncio.sleep(1)
        print("⏰ Sending cancellation after 1 second...")

        cancel_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 3, "reason": "User cancelled"},
        }
        process.stdin.write(json.dumps(cancel_notification) + "\n")
        process.stdin.flush()

        # Give a moment for any immediate response
        await asyncio.sleep(0.1)

        # Check if there's any immediate output on stdout or stderr
        print("🔍 Checking for immediate output after cancellation...")

        # Try to read any available output without blocking
        import os
        import select

        # Check if data is available on stdout
        if os.name == "posix":  # Unix-like systems
            ready, _, _ = select.select([process.stdout], [], [], 0)
            if ready:
                immediate_stdout = process.stdout.readline()
                print(f"📤 Immediate stdout: {repr(immediate_stdout)}")
            else:
                print("📤 No immediate stdout available")

            # Check stderr too
            ready, _, _ = select.select([process.stderr], [], [], 0)
            if ready:
                immediate_stderr = process.stderr.readline()
                print(f"📤 Immediate stderr: {repr(immediate_stderr)}")
            else:
                print("📤 No immediate stderr available")

        # Wait for response or timeout
        try:
            response = await asyncio.wait_for(
                asyncio.create_task(asyncio.to_thread(process.stdout.readline)),
                timeout=3.0,
            )
            print("📨 Tool response after cancellation:")
            print(f"    RAW: {repr(response)}")
            print(f"    JSON: {response.strip()}")

            # Parse and show the content
            try:
                response_data = json.loads(response.strip())
                if "result" in response_data:
                    print(f"    RESULT: {response_data['result']}")
                elif "error" in response_data:
                    print(f"    ERROR: {response_data['error']}")
            except json.JSONDecodeError as e:
                print(f"    JSON_ERROR: {e}")

            # Test if server is still responsive with a simple tool
            ping_request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "hello_simple", "arguments": {}},
            }
            process.stdin.write(json.dumps(ping_request) + "\n")
            process.stdin.flush()
            print("🔄 Testing server responsiveness with hello_simple...")

            ping_response = await asyncio.wait_for(
                asyncio.create_task(asyncio.to_thread(process.stdout.readline)),
                timeout=2.0,
            )
            print("📨 Simple tool response:")
            print(f"    RAW: {repr(ping_response)}")
            print(f"    JSON: {ping_response.strip()}")
            print("✅ Server remained responsive after cancellation!")
            return True

        except asyncio.TimeoutError:
            print("❌ Server became unresponsive after cancellation")
            return False

    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    print("Testing MCP tool cancellation behavior...\n")
    result = asyncio.run(test_tool_cancellation())

    if result:
        print("\n🎉 Cancellation test PASSED!")
    else:
        print("\n💥 Cancellation test FAILED!")
        sys.exit(1)
