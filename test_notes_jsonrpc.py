# \!/usr/bin/env python3
import json
import subprocess
import sys


def test_notes_jsonrpc():
    # Start the notes server
    process = subprocess.Popen(
        ["mcp-notes"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )

    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        print("Initialize:", response.strip())

        # Send initialized notification
        process.stdin.write(
            '{"jsonrpc": "2.0", "method": "notifications/initialized"}\n'
        )
        process.stdin.flush()

        # Test create_note tool call
        create_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "create_note",
                "arguments": {
                    "path": "test",
                    "title": "Test Note",
                    "content": "Test note via JSON-RPC",
                    "scope": "local",
                },
            },
        }
        process.stdin.write(json.dumps(create_request) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        print("Create note:", response.strip())

        # Check for errors
        if '"isError":true' in response:
            print(r"❌ Tool execution failed\!")
            return False
        else:
            print(r"✅ Tool execution successful\!")
            return True

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        process.terminate()
        process.wait()


if __name__ == "__main__":
    success = test_notes_jsonrpc()
    sys.exit(0 if success else 1)
