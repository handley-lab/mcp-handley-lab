"""Integration tests for Gemini memory behavior via JSON-RPC."""
import pytest
import subprocess
import json
import time
import vcr
from pathlib import Path


class TestGeminiMemoryIntegration:
    """Test Gemini memory behavior through actual JSON-RPC MCP protocol."""
    
    def setup_method(self):
        """Start Gemini MCP server for each test."""
        self.process = subprocess.Popen(
            ['/home/will/code/mcp.3/venv/bin/mcp-gemini'], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True, 
            bufsize=0
        )
        
        # Initialize server
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", 
                "capabilities": {"tools": {}}, 
                "clientInfo": {"name": "memory-test", "version": "1.0.0"}
            }
        }
        
        self.process.stdin.write(json.dumps(init_msg) + '\n')
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        assert "Gemini Tool" in response
        
        # Send initialized notification
        self.process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        self.process.stdin.flush()
    
    def teardown_method(self):
        """Clean up server process."""
        if self.process:
            self.process.terminate()
            self.process.wait()
    
    def send_ask_request(self, prompt: str, request_id: int, **kwargs) -> tuple[dict, str]:
        """Send an ask request and return the parsed response and content."""
        ask_request = {
            "jsonrpc": "2.0", 
            "id": request_id, 
            "method": "tools/call",
            "params": {
                "name": "ask", 
                "arguments": {
                    "prompt": prompt,
                    "output_file": "-",  # Use stdout to avoid file dependencies
                    **kwargs
                }
            }
        }
        
        self.process.stdin.write(json.dumps(ask_request) + '\n')
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        parsed_response = json.loads(response)
        
        # Extract the actual Gemini response content from the MCP result
        if not parsed_response["result"]["isError"]:
            # The content is in the first part before usage info
            full_text = parsed_response["result"]["content"][0]["text"]
            # Split on the usage info line to get just the response
            response_content = full_text.split('\n\n')[0] if '\n\n' in full_text else full_text
        else:
            response_content = ""
            
        return parsed_response, response_content
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_math.yaml", record_mode="once")
    def test_session_memory_with_math(self):
        """Test session memory with math problem: 2+2, then double that."""
        # First call: What's 2+2?
        response1, content1 = self.send_ask_request(
            "What is 2+2? Answer with just the number.",
            2
        )
        assert not response1["result"]["isError"]
        assert "4" in content1
        
        # Second call: Double that result
        response2, content2 = self.send_ask_request(
            "Double that result",
            3
        )
        assert not response2["result"]["isError"]
        # Should reference the previous result and give 8
        assert "8" in content2
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_agents.yaml", record_mode="once")
    def test_named_agent_memory_isolation(self):
        """Test that named agents have isolated memory."""
        # Tell agent1 about a number
        response1, content1 = self.send_ask_request(
            "Remember this number: 42",
            4,
            agent_name="math_agent1"
        )
        assert not response1["result"]["isError"]
        
        # Tell agent2 about a different number  
        response2, content2 = self.send_ask_request(
            "Remember this number: 99",
            5,
            agent_name="math_agent2"
        )
        assert not response2["result"]["isError"]
        
        # Ask agent1 what number it remembers
        response3, content3 = self.send_ask_request(
            "What number did I tell you to remember?",
            6,
            agent_name="math_agent1"
        )
        assert not response3["result"]["isError"]
        assert "42" in content3
        assert "99" not in content3
        
        # Ask agent2 what number it remembers
        response4, content4 = self.send_ask_request(
            "What number did I tell you to remember?",
            7,
            agent_name="math_agent2"
        )
        assert not response4["result"]["isError"]
        assert "99" in content4
        assert "42" not in content4
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_none.yaml", record_mode="once")
    def test_no_memory_mode(self):
        """Test that agent_name=False disables memory."""
        # First call with memory disabled
        response1, content1 = self.send_ask_request(
            "My lucky number is 7. Remember this.",
            8,
            agent_name=False
        )
        assert not response1["result"]["isError"]
        
        # Second call with memory disabled - should not remember
        response2, content2 = self.send_ask_request(
            "What was my lucky number?",
            9,
            agent_name=False
        )
        assert not response2["result"]["isError"]
        
        # Should not remember the number
        response_lower = content2.lower()
        # Should indicate no memory/can't remember
        assert any(phrase in response_lower for phrase in [
            "don't remember", "don't have", "no memory", 
            "can't remember", "not remember", "don't recall"
        ])
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_conversation.yaml", record_mode="once")
    def test_cross_call_conversation_flow(self):
        """Test realistic conversation flow across multiple calls."""
        # Start conversation
        response1, content1 = self.send_ask_request(
            "I'm working on a Python project. Can you help?",
            10
        )
        assert not response1["result"]["isError"]
        
        # Follow up - should remember context
        response2, content2 = self.send_ask_request(
            "What programming language did I mention?",
            11
        )
        assert not response2["result"]["isError"]
        assert "python" in content2.lower()
        
        # Continue conversation
        response3, content3 = self.send_ask_request(
            "What are some good testing frameworks for that language?",
            12
        )
        assert not response3["result"]["isError"]
        # Should mention Python testing frameworks
        assert any(framework in content3.lower() for framework in [
            "pytest", "unittest", "testing", "python"
        ])


@pytest.mark.integration
class TestGeminiMemoryIntegrationQuick:
    """Quick memory tests that can run in CI."""
    
    @vcr.use_cassette("tests/integration/cassettes/gemini_memory_quick.yaml", record_mode="once")
    def test_basic_memory_persistence(self):
        """Quick test of basic memory functionality."""
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
                    "clientInfo": {"name": "quick-test", "version": "1.0.0"}
                }
            }
            
            process.stdin.write(json.dumps(init_msg) + '\n')
            process.stdin.flush()
            process.stdout.readline()  # consume init response
            
            process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
            process.stdin.flush()
            
            # Math test: 3+3, then double it
            call1 = {
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {
                    "name": "ask", 
                    "arguments": {
                        "prompt": "What is 3+3? Answer with just the number.",
                        "output_file": "-"  # Use stdout instead of files
                    }
                }
            }
            
            process.stdin.write(json.dumps(call1) + '\n')
            process.stdin.flush()
            response1 = json.loads(process.stdout.readline())
            first_content = response1["result"]["content"][0]["text"].split('\n\n')[0]
            
            call2 = {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {
                    "name": "ask", 
                    "arguments": {
                        "prompt": "Double that result",
                        "output_file": "-"  # Use stdout instead of files
                    }
                }
            }
            
            process.stdin.write(json.dumps(call2) + '\n')
            process.stdin.flush()
            response2 = json.loads(process.stdout.readline())
            second_content = response2["result"]["content"][0]["text"].split('\n\n')[0]
            
            # Verify results
            assert "6" in first_content
            assert "12" in second_content
                
        finally:
            process.terminate()
            process.wait()