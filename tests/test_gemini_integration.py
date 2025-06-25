"""Integration tests for Gemini LLM tool using real API calls."""
import pytest
import tempfile
from pathlib import Path
import os

from mcp_handley_lab.llm.gemini.tool import (
    ask, analyze_image, generate_image, create_agent, list_agents, 
    agent_stats, get_response, clear_agent, delete_agent, server_info
)


@pytest.mark.integration
class TestGeminiIntegration:
    """Integration tests for Gemini tools with real API calls."""
    
    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Check if Gemini API key is available."""
        if not os.getenv('GEMINI_API_KEY'):
            pytest.skip("GEMINI_API_KEY not set - skipping Gemini integration tests")
    
    def test_server_info_integration(self):
        """Test server info with real API."""
        result = server_info()
        
        assert "Gemini Tool Server Status" in result
        assert "Connected and ready" in result
        assert "API Key: Configured ✓" in result
        assert "Available Models:" in result
        assert "Available tools:" in result
    
    def test_ask_basic_integration(self):
        """Test basic ask functionality with real API."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_file = f.name
        
        try:
            result = ask(
                prompt="What is 2+2? Answer with just the number.",
                output_file=output_file,
                model="flash",
                temperature=0.1
            )
            
            # Check result format
            assert f"Response saved to: {output_file}" in result
            assert "Content:" in result
            assert "💰 Usage:" in result
            
            # Check file was created and contains response
            assert Path(output_file).exists()
            content = Path(output_file).read_text()
            assert "4" in content
        finally:
            # Cleanup
            if Path(output_file).exists():
                Path(output_file).unlink()
    
    def test_ask_with_grounding_integration(self):
        """Test ask with Google Search grounding (grounding may be limited in google-genai)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_file = f.name
        
        try:
            result = ask(
                prompt="What is the current date?",
                output_file=output_file,
                grounding=True,
                model="flash"
            )
            
            # Check result format
            assert f"Response saved to: {output_file}" in result
            assert "💰 Usage:" in result
            
            # Check file was created
            assert Path(output_file).exists()
            content = Path(output_file).read_text()
            assert len(content) > 0
        finally:
            # Cleanup
            if Path(output_file).exists():
                Path(output_file).unlink()
    
    def test_ask_with_files_integration(self):
        """Test ask with file content."""
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as test_file:
            test_file.write('def hello_world():\n    print("Hello, World!")\n')
            test_file_path = test_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_file = f.name
        
        try:
            result = ask(
                prompt="Explain what this Python function does in one sentence.",
                output_file=output_file,
                files=[{"path": test_file_path}],
                model="flash"
            )
            
            # Check result
            assert f"Response saved to: {output_file}" in result
            
            # Check file content
            assert Path(output_file).exists()
            content = Path(output_file).read_text().lower()
            assert any(word in content for word in ["hello", "print", "function"])
        finally:
            # Cleanup
            for path in [test_file_path, output_file]:
                if Path(path).exists():
                    Path(path).unlink()
    
    def test_analyze_image_integration(self):
        """Test image analysis with a simple test image."""
        # Create a simple colored image
        from PIL import Image
        import io
        import base64
        
        # Create a 100x100 red square
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        data_url = f"data:image/png;base64,{img_data}"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_file = f.name
        
        try:
            result = analyze_image(
                prompt="What color is this image? Answer in one word.",
                output_file=output_file,
                image_data=data_url,
                model="flash"
            )
            
            # Check result
            assert f"Response saved to: {output_file}" in result
            assert "💰 Usage:" in result
            
            # Check file content
            assert Path(output_file).exists()
            content = Path(output_file).read_text().lower()
            assert "red" in content
        finally:
            # Cleanup
            if Path(output_file).exists():
                Path(output_file).unlink()
    
    def test_generate_image_integration(self):
        """Test image generation."""
        result = generate_image(
            prompt="A simple red circle on a white background",
            model="imagen-3"
        )
        
        # Check result format  
        assert ("✅ **Image Generated Successfully**" in result or "✅ Image generated successfully!" in result)
        assert ("📁 **File:**" in result or "📁 Saved to:" in result)
        assert ("📏 **Size:**" in result or "bytes" in result)
        assert "💰 Usage:" in result
        
        # Extract file path and check it exists
        lines = result.split('\n')
        if "📁 **File:**" in result:
            file_line = [line for line in lines if "📁 **File:**" in line][0]
            file_path = file_line.split('`')[1]
        else:
            file_line = [line for line in lines if "📁 Saved to:" in line][0]
            file_path = file_line.split(': ')[1]
        
        assert Path(file_path).exists()
        assert Path(file_path).stat().st_size > 0
        
        # Cleanup
        Path(file_path).unlink()
    
    def test_agent_lifecycle_integration(self):
        """Test complete agent lifecycle."""
        agent_name = "test_integration_agent"
        
        try:
            # Create agent
            result = create_agent(
                agent_name=agent_name,
                personality="A helpful assistant that answers in one sentence."
            )
            assert f"Agent '{agent_name}' created successfully" in result
            
            # List agents
            result = list_agents()
            assert agent_name in result
            
            # Get agent stats
            result = agent_stats(agent_name)
            assert f"Agent Statistics: {agent_name}" in result
            assert "Total Messages: 0" in result
            
            # Use agent in conversation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                output_file = f.name
            
            try:
                result = ask(
                    prompt="What is 5+3?",
                    output_file=output_file,
                    agent_name=agent_name,
                    model="flash"
                )
                
                assert f"Response saved to: {output_file}" in result
                
                # Check agent stats updated
                result = agent_stats(agent_name)
                assert "Total Messages: 2" in result  # User + assistant message
                
                # Get specific response
                response = get_response(agent_name, -1)
                assert "8" in response
                
                # Clear agent history
                result = clear_agent(agent_name)
                assert f"Agent '{agent_name}' history cleared successfully" in result
                
                # Verify history cleared
                result = agent_stats(agent_name)
                assert "Total Messages: 0" in result
                
            finally:
                if Path(output_file).exists():
                    Path(output_file).unlink()
            
        finally:
            # Cleanup agent
            try:
                delete_agent(agent_name)
            except:
                pass  # Agent might already be deleted
    
    def test_ask_stdout_integration(self):
        """Test ask with stdout output."""
        result = ask(
            prompt="Say 'Hello Integration Test'",
            output_file="-",
            model="flash",
            temperature=0.1
        )
        
        # Should contain response and usage info
        assert "Hello Integration Test" in result or "hello integration test" in result.lower()
        assert "💰 Usage:" in result
    
    def test_ask_with_agent_memory_integration(self):
        """Test ask with agent memory persistence."""
        agent_name = "memory_test_agent"
        
        try:
            # First conversation
            result1 = ask(
                prompt="Remember this number: 42",
                output_file="-",
                agent_name=agent_name,
                model="flash"
            )
            
            # Second conversation referencing first
            result2 = ask(
                prompt="What number did I ask you to remember?",
                output_file="-", 
                agent_name=agent_name,
                model="flash"
            )
            
            assert "42" in result2
            
        finally:
            # Cleanup
            try:
                delete_agent(agent_name)
            except:
                pass