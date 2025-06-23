"""Integration tests for OpenAI LLM tool."""
import tempfile
from pathlib import Path
import pytest
from mcp_handley_lab.llm.openai.tool import ask, server_info
from mcp_handley_lab.common.config import settings


class TestOpenAIIntegration:
    """Integration tests that call the real OpenAI API."""
    
    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip tests if no API key is configured."""
        if settings.openai_api_key == "YOUR_API_KEY_HERE":
            pytest.skip("OpenAI API key not configured")
    
    def test_ask_integration(self):
        """Test basic ask functionality with real API."""
        # Simple test that should work reliably
        result = ask("What is 2+2? Answer with just the number.")
        
        # Should contain the answer and usage info
        assert "4" in result
        assert "💰 Usage:" in result
        assert "tokens" in result
    
    def test_server_info_integration(self):
        """Test server info with real API connection."""
        result = server_info()
        
        assert "OpenAI Tool Server Status" in result
        assert "Status: Connected and ready" in result
        assert "API Key: Configured ✓" in result
        assert "Available Models:" in result
        assert "gpt" in result.lower()  # Should list GPT models
    
    def test_ask_with_file_integration(self):
        """Test ask with file content using real API."""
        # Create a temporary file with test content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("The weather is sunny today.\nTemperature: 75°F")
            temp_file = f.name
        
        try:
            files = [{"path": temp_file}]
            result = ask("What's the temperature mentioned in this file?", files=files)
            
            # Should extract the temperature
            assert "75" in result
            assert "💰 Usage:" in result
        finally:
            Path(temp_file).unlink()
    
    def test_ask_small_model_integration(self):
        """Test ask with a smaller/cheaper model."""
        result = ask(
            "Hello! Respond with exactly: 'Integration test successful'",
            model="gpt-4o-mini"
        )
        
        # Should contain our expected response
        assert "Integration test successful" in result
        assert "💰 Usage:" in result