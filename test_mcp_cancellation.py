#!/usr/bin/env python3
"""Test MCP cancellation by sending JSON-RPC messages."""

import asyncio
import json
import subprocess
import sys
import signal
import time


async def test_cancellation():
    """Test MCP server cancellation behavior."""
    
    # Start the test server
    print("Starting MCP test server...")
    process = subprocess.Popen(
        [sys.executable, "test_cancellation.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0
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
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read initialization response
        response = process.stdout.readline()
        print(f"Init response: {response.strip()}")
        
        # Send initialized notification
        process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        process.stdin.flush()
        
        # Start a slow task
        print("Starting slow task...")
        slow_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "slow_task",
                "arguments": {"duration": 30}
            }
        }
        
        process.stdin.write(json.dumps(slow_request) + "\n")
        process.stdin.flush()
        
        # Wait a moment then send a cancellation notification
        await asyncio.sleep(2)
        print("Sending cancellation notification...")
        
        cancel_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {
                "requestId": 2,
                "reason": "User pressed ESC"
            }
        }
        
        process.stdin.write(json.dumps(cancel_notification) + "\n")
        process.stdin.flush()
        
        # Read the response
        print("Waiting for response...")
        response = process.stdout.readline()
        print(f"Tool response: {response.strip()}")
        
        # Check if there are any error messages
        stderr_line = process.stderr.readline()
        if stderr_line:
            print(f"Stderr: {stderr_line.strip()}")
            
    finally:
        # Clean up
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    asyncio.run(test_cancellation())