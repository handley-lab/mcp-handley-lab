"""Simple integration test for Gemini memory behavior."""
import pytest
import subprocess
import json
import tempfile
import vcr


@pytest.mark.integration 
class TestGeminiMemorySimple:
    """Simple tests demonstrating Gemini memory functionality."""
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_simple_math.yaml", record_mode="once")
    def test_memory_math_sequence(self):
        """Test the 2+2, double that sequence that demonstrates memory."""
        # Use a temporary directory for any file outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            process = subprocess.Popen(
                ['/home/will/code/mcp.3/venv/bin/mcp-gemini'], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                bufsize=0
            )
            
            try:
                # Initialize server
                init_msg = {
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05", 
                        "capabilities": {"tools": {}}, 
                        "clientInfo": {"name": "memory-demo", "version": "1.0.0"}
                    }
                }
                
                process.stdin.write(json.dumps(init_msg) + '\n')
                process.stdin.flush()
                init_response = process.stdout.readline()
                
                assert "Gemini Tool" in init_response
                
                # Send initialized notification
                process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
                process.stdin.flush()
                
                # Call 1: What's 2+2?
                call1 = {
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {
                        "name": "ask", 
                        "arguments": {
                            "prompt": "What is 2+2? Please answer with just the number.",
                            "output_file": f"{temp_dir}/response1.txt"
                        }
                    }
                }
                
                process.stdin.write(json.dumps(call1) + '\n')
                process.stdin.flush()
                response1_line = process.stdout.readline()
                response1 = json.loads(response1_line)
                
                assert not response1["result"]["isError"], f"First call failed: {response1}"
                
                # Call 2: Double that result
                call2 = {
                    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {
                        "name": "ask", 
                        "arguments": {
                            "prompt": "Double that result",
                            "output_file": f"{temp_dir}/response2.txt"
                        }
                    }
                }
                
                process.stdin.write(json.dumps(call2) + '\n')
                process.stdin.flush()
                response2_line = process.stdout.readline()
                response2 = json.loads(response2_line)
                
                assert not response2["result"]["isError"], f"Second call failed: {response2}"
                
                # Read the actual responses
                with open(f"{temp_dir}/response1.txt", 'r') as f:
                    first_content = f.read().strip()
                    
                with open(f"{temp_dir}/response2.txt", 'r') as f:
                    second_content = f.read().strip()
                
                # Verify the math sequence worked
                assert "4" in first_content, f"Expected '4' in first response: {first_content}"
                assert "8" in second_content, f"Expected '8' in second response: {second_content}"
                
                print(f"✅ Memory test passed!")
                print(f"   First response: {first_content}")
                print(f"   Second response: {second_content}")
                
            finally:
                process.terminate()
                process.wait()
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_no_memory.yaml", record_mode="once")
    def test_no_memory_mode(self):
        """Test that agent_name=False disables memory properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            process = subprocess.Popen(
                ['/home/will/code/mcp.3/venv/bin/mcp-gemini'], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                bufsize=0
            )
            
            try:
                # Initialize
                init_msg = {
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05", 
                        "capabilities": {"tools": {}}, 
                        "clientInfo": {"name": "no-memory-test", "version": "1.0.0"}
                    }
                }
                
                process.stdin.write(json.dumps(init_msg) + '\n')
                process.stdin.flush()
                process.stdout.readline()  # consume init response
                
                process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
                process.stdin.flush()
                
                # Call 1: Store something (with memory disabled)
                call1 = {
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {
                        "name": "ask", 
                        "arguments": {
                            "prompt": "My favorite number is 42. Remember this.",
                            "output_file": f"{temp_dir}/no_mem_1.txt",
                            "agent_name": False  # Disable memory
                        }
                    }
                }
                
                process.stdin.write(json.dumps(call1) + '\n')
                process.stdin.flush()
                process.stdout.readline()  # consume response
                
                # Call 2: Try to recall (with memory disabled)
                call2 = {
                    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {
                        "name": "ask", 
                        "arguments": {
                            "prompt": "What was my favorite number that I just told you?",
                            "output_file": f"{temp_dir}/no_mem_2.txt",
                            "agent_name": False  # Disable memory
                        }
                    }
                }
                
                process.stdin.write(json.dumps(call2) + '\n')
                process.stdin.flush()
                process.stdout.readline()  # consume response
                
                # Check that memory was disabled
                with open(f"{temp_dir}/no_mem_2.txt", 'r') as f:
                    recall_response = f.read().lower()
                    
                # Should not remember the number 42
                memory_disabled_phrases = [
                    "don't remember", "don't have", "no memory", 
                    "can't remember", "don't recall", "not told"
                ]
                
                memory_disabled = any(phrase in recall_response for phrase in memory_disabled_phrases)
                assert memory_disabled, f"Expected memory to be disabled, but got: {recall_response}"
                
                print(f"✅ No memory test passed!")
                print(f"   Response: {recall_response}")
                
            finally:
                process.terminate()
                process.wait()