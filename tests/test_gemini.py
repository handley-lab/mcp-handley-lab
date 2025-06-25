"""Unit tests for Gemini LLM tool with google-genai SDK."""
import base64
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open, Mock
from PIL import Image
import io

from mcp_handley_lab.llm.gemini.tool import (
    ask, analyze_image, generate_image, create_agent, list_agents, 
    agent_stats, get_response, clear_agent, delete_agent, server_info,
    _resolve_files, _resolve_images, _handle_agent_and_usage,
    _determine_mime_type, _is_text_file
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_resolve_files_empty(self):
        """Test resolving empty files list."""
        result = _resolve_files(None)
        assert result == []
        
        result = _resolve_files([])
        assert result == []
    
    def test_resolve_files_string_content(self):
        """Test resolving files with string content."""
        files = ["content1", "content2"]
        result = _resolve_files(files)
        assert len(result) == 2
        assert result[0].text == "content1"
        assert result[1].text == "content2"
    
    def test_resolve_files_dict_content(self):
        """Test resolving files with dict content."""
        files = [
            {"content": "dict content"},
            {"content": "another content"}
        ]
        result = _resolve_files(files)
        assert len(result) == 2
        assert result[0].text == "dict content"
        assert result[1].text == "another content"
    
    def test_resolve_files_dict_path(self, tmp_path):
        """Test resolving files with dict path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")
        
        files = [{"path": str(test_file)}]
        result = _resolve_files(files)
        assert len(result) == 1
        assert result[0].text == "[File: test.txt]\nfile content"
    
    def test_resolve_files_dict_path_error(self):
        """Test resolving files with invalid path."""
        files = [{"path": "/nonexistent/file.txt"}]
        result = _resolve_files(files)
        assert len(result) == 1
        assert "Error: File not found" in result[0].text
    
    def test_resolve_files_mixed(self, tmp_path):
        """Test resolving mixed file types."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")
        
        files = [
            "string content",
            {"content": "dict content"},
            {"path": str(test_file)}
        ]
        result = _resolve_files(files)
        assert len(result) == 3
        assert result[0].text == "string content"
        assert result[1].text == "dict content"
        assert result[2].text == "[File: test.txt]\nfile content"
    
    @patch('PIL.Image.open')
    def test_resolve_images_single_data_url(self, mock_image_open):
        """Test resolving single image from data URL."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        
        # Create a simple data URL
        image_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        result = _resolve_images(image_data=image_data)
        assert len(result) == 1
        assert result[0] == mock_image
        mock_image_open.assert_called_once()
    
    @patch('PIL.Image.open')
    @patch('pathlib.Path.read_bytes')
    def test_resolve_images_file_path(self, mock_read_bytes, mock_image_open):
        """Test resolving image from file path."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        mock_read_bytes.return_value = b"fake_image_data"
        
        result = _resolve_images(image_data="/path/to/image.png")
        assert len(result) == 1
        assert result[0] == mock_image
    
    def test_resolve_images_error(self):
        """Test resolving images with error."""
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(image_data="invalid_data")
    
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_resolve_images_array_data_url(self, mock_b64decode, mock_image_open):
        """Test resolving images array with data URL."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        mock_b64decode.return_value = b"fake_image_data"
        
        images = ["data:image/png;base64,iVBORw0KGgoAAAANSU"]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == mock_image
    
    @patch('PIL.Image.open')
    @patch('pathlib.Path.read_bytes')
    def test_resolve_images_array_file_path(self, mock_read_bytes, mock_image_open):
        """Test resolving images array with file path."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        mock_read_bytes.return_value = b"fake_image_data"
        
        images = ["/path/to/image.png"]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == mock_image
    
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_resolve_images_dict_data(self, mock_b64decode, mock_image_open):
        """Test resolving images with dict data."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        mock_b64decode.return_value = b"fake_image_data"
        
        images = [{"data": "base64encoded"}]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == mock_image
    
    @patch('PIL.Image.open')
    @patch('pathlib.Path.read_bytes')
    def test_resolve_images_dict_path(self, mock_read_bytes, mock_image_open):
        """Test resolving images with dict path."""
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        mock_read_bytes.return_value = b"fake_image_data"
        
        images = [{"path": "/path/to/image.png"}]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == mock_image
    
    def test_resolve_images_array_error(self):
        """Test resolving images array with error."""
        images = ["invalid_data"]
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(images=images)
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    def test_handle_agent_and_usage_file_output(self, mock_format_usage, mock_calculate_cost, mock_memory_manager, tmp_path):
        """Test handle_agent_and_usage with file output."""
        mock_calculate_cost.return_value = 0.01
        mock_format_usage.return_value = "💰 Usage: 100 tokens"
        
        output_file = tmp_path / "output.txt"
        result = _handle_agent_and_usage(
            None, "prompt", "response", "flash", 50, 50, str(output_file)
        )
        
        assert f"Response saved to: {output_file}" in result
        assert "Content: 8 characters, 1 lines" in result
        assert "💰 Usage: 100 tokens" in result
        assert output_file.read_text() == "response"
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    def test_handle_agent_and_usage_stdout(self, mock_format_usage, mock_calculate_cost, mock_memory_manager):
        """Test handle_agent_and_usage with stdout output."""
        mock_calculate_cost.return_value = 0.01
        mock_format_usage.return_value = "💰 Usage: 100 tokens"
        
        result = _handle_agent_and_usage(
            None, "prompt", "response", "flash", 50, 50, "-"
        )
        
        assert "response\n\n💰 Usage: 100 tokens" == result
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    def test_handle_agent_and_usage_with_agent(self, mock_format_usage, mock_calculate_cost, mock_memory_manager):
        """Test handle_agent_and_usage with agent memory."""
        mock_calculate_cost.return_value = 0.01
        mock_format_usage.return_value = "💰 Usage: 100 tokens"
        mock_agent = MagicMock()
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = _handle_agent_and_usage(
            "test_agent", "prompt", "response", "flash", 50, 50, "-"
        )
        
        mock_memory_manager.get_agent.assert_called_with("test_agent")
        mock_memory_manager.add_message.assert_called()
        assert "response\n\n💰 Usage: 100 tokens" == result
    
    def test_determine_mime_type(self):
        """Test MIME type determination."""
        from pathlib import Path
        
        assert _determine_mime_type(Path("test.txt")) == "text/plain"
        assert _determine_mime_type(Path("test.py")) == "text/x-python"
        assert _determine_mime_type(Path("test.js")) == "text/javascript"
        assert _determine_mime_type(Path("test.json")) == "application/json"
        assert _determine_mime_type(Path("test.png")) == "image/png"
        assert _determine_mime_type(Path("test.jpg")) == "image/jpeg"
        assert _determine_mime_type(Path("test.pdf")) == "application/pdf"
        assert _determine_mime_type(Path("test.unknown")) == "application/octet-stream"
        assert _determine_mime_type(Path("test")) == "application/octet-stream"
    
    def test_is_text_file(self):
        """Test text file detection."""
        from pathlib import Path
        
        # Text files
        assert _is_text_file(Path("test.txt")) == True
        assert _is_text_file(Path("test.md")) == True
        assert _is_text_file(Path("test.py")) == True
        assert _is_text_file(Path("test.js")) == True
        assert _is_text_file(Path("test.json")) == True
        assert _is_text_file(Path("test.yaml")) == True
        assert _is_text_file(Path("test.yml")) == True
        assert _is_text_file(Path("test.toml")) == True
        assert _is_text_file(Path("config.conf")) == True
        assert _is_text_file(Path("app.log")) == True
        
        # Binary files
        assert _is_text_file(Path("test.png")) == False
        assert _is_text_file(Path("test.jpg")) == False
        assert _is_text_file(Path("test.pdf")) == False
        assert _is_text_file(Path("test.exe")) == False
        assert _is_text_file(Path("test.bin")) == False
        assert _is_text_file(Path("test")) == False


class TestGeminiTools:
    """Test Gemini tool functions."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock google-genai client."""
        with patch('mcp_handley_lab.llm.gemini.tool.client') as mock:
            yield mock
    
    @pytest.fixture
    def mock_memory_manager(self):
        """Mock memory manager."""
        with patch('mcp_handley_lab.llm.gemini.tool.memory_manager') as mock:
            mock_agent = MagicMock()
            mock_agent.get_conversation_history.return_value = []
            mock.get_agent.return_value = None
            mock.create_agent.return_value = mock_agent
            yield mock
    
    def test_ask_basic(self, mock_client, mock_memory_manager):
        """Test basic ask functionality."""
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Hello, how are you?", output_file="-")
        
        assert "Test response" in result
        assert "💰 Usage:" in result
        mock_client.models.generate_content.assert_called_once()
    
    def test_ask_client_not_initialized(self, mock_memory_manager):
        """Test ask when client is not initialized."""
        # Temporarily set client to None to simulate initialization failure
        import mcp_handley_lab.llm.gemini.tool as gemini_tool
        original_client = gemini_tool.client
        gemini_tool.client = None
        
        try:
            with pytest.raises(RuntimeError, match="Gemini client not initialized"):
                ask("Hello", output_file="-")
        finally:
            # Restore original client
            gemini_tool.client = original_client
    
    def test_ask_with_agent(self, mock_client, mock_memory_manager):
        """Test ask with agent memory."""
        # Setup agent
        mock_agent = MagicMock()
        mock_agent.personality = "Helpful assistant"
        mock_agent.get_conversation_history.return_value = [
            {"role": "user", "content": "Previous message"}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Hello", output_file="-", agent_name="test_agent")
        
        assert "Test response" in result
        mock_memory_manager.get_agent.assert_called_with("test_agent")
        mock_memory_manager.add_message.assert_called()
    
    def test_ask_with_files(self, mock_client, mock_memory_manager, tmp_path):
        """Test ask with file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("File content")
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        files = [{"path": str(test_file)}, {"content": "Direct content"}]
        result = ask("Question about files", output_file="-", files=files)
        
        assert "Test response" in result
        # Check that content was structured properly with separate parts
        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]['contents']
        # Contents should now be a list of Part objects, not a string with concatenated content
        assert isinstance(contents, list)
        assert len(contents) > 1  # Should have multiple parts (prompt + files)
    
    @patch('mcp_handley_lab.llm.gemini.tool.Tool')
    @patch('mcp_handley_lab.llm.gemini.tool.GoogleSearchRetrieval')
    def test_ask_with_grounding(self, mock_google_search_retrieval, mock_tool, mock_client, mock_memory_manager):
        """Test ask with grounding enabled."""
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Current weather", output_file="-", grounding=True)
        
        assert "Test response" in result
        # Check that tools were configured
        mock_tool.assert_called_once()
        mock_google_search_retrieval.assert_called_once()
    
    def test_ask_with_temperature(self, mock_client, mock_memory_manager):
        """Test ask with custom temperature."""
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Creative question", output_file="-", temperature=0.9)
        
        assert "Test response" in result
        # Check generation config
        config = mock_client.models.generate_content.call_args[1]['config']
        assert config.temperature == 0.9
    
    def test_ask_api_error(self, mock_client, mock_memory_manager):
        """Test ask with API error."""
        mock_client.models.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="Gemini API error"):
            ask("Hello", output_file="-")
    
    def test_ask_no_response_text(self, mock_client, mock_memory_manager):
        """Test ask when no response text is generated."""
        # Mock response without text
        mock_response = MagicMock()
        mock_response.text = None
        
        mock_client.models.generate_content.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="No response text generated"):
            ask("Hello", output_file="-")
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_basic(self, mock_resolve_images, mock_client, mock_memory_manager):
        """Test basic image analysis."""
        mock_image = MagicMock()
        mock_resolve_images.return_value = [mock_image]
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = analyze_image("What's in this image?", output_file="-", image_data="fake_image_data")
        
        assert "Test response" in result
        assert "💰 Usage:" in result
        mock_resolve_images.assert_called_once()
    
    def test_analyze_image_client_not_initialized(self, mock_memory_manager):
        """Test analyze_image when client is not initialized."""
        # Temporarily set client to None to simulate initialization failure
        import mcp_handley_lab.llm.gemini.tool as gemini_tool
        original_client = gemini_tool.client
        gemini_tool.client = None
        
        try:
            with pytest.raises(RuntimeError, match="Gemini client not initialized"):
                analyze_image("Analyze", output_file="-", image_data="fake")
        finally:
            # Restore original client
            gemini_tool.client = original_client
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_with_focus(self, mock_resolve_images, mock_client, mock_memory_manager):
        """Test image analysis with focus."""
        mock_image = MagicMock()
        mock_resolve_images.return_value = [mock_image]
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = analyze_image("Analyze this", output_file="-", image_data="fake", focus="technical")
        
        assert "Test response" in result
        # Check that focus was added to prompt
        call_args = mock_client.models.generate_content.call_args[1]['contents']
        assert "Focus on technical aspects" in call_args[0]
    
    def test_analyze_image_no_images(self, mock_client, mock_memory_manager):
        """Test image analysis without images."""
        with pytest.raises(ValueError, match="Either image_data or images must be provided"):
            analyze_image("What's in this image?", output_file="-")
    
    def test_analyze_image_api_error(self, mock_client, mock_memory_manager):
        """Test image analysis with API error."""
        with patch('mcp_handley_lab.llm.gemini.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = [MagicMock()]
            mock_client.models.generate_content.side_effect = Exception("Vision API Error")
            
            with pytest.raises(RuntimeError, match="Gemini vision API error"):
                analyze_image("Analyze this", output_file="-", image_data="fake")
    
    def test_generate_image_success(self, mock_client, mock_memory_manager):
        """Test successful image generation."""
        # Mock the generated image response
        mock_image = MagicMock()
        mock_image.image.image_bytes = b"fake_image_data"
        
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        
        mock_client.models.generate_images.return_value = mock_response
        
        result = generate_image("A beautiful sunset")
        
        assert "✅ **Image Generated Successfully**" in result
        assert "📁 **File:**" in result
        assert "gemini_generated_" in result
        assert ".png" in result
        assert "📏 **Size:** 15 bytes" in result  # len(b"fake_image_data") = 15
        assert "💰 Usage:" in result
        
        # Verify the client was called correctly
        mock_client.models.generate_images.assert_called_once()
    
    def test_generate_image_client_not_initialized(self, mock_memory_manager):
        """Test generate_image when client is not initialized."""
        # Temporarily set client to None to simulate initialization failure
        import mcp_handley_lab.llm.gemini.tool as gemini_tool
        original_client = gemini_tool.client
        gemini_tool.client = None
        
        try:
            with pytest.raises(RuntimeError, match="Gemini client not initialized"):
                generate_image("A test image")
        finally:
            # Restore original client
            gemini_tool.client = original_client
    
    def test_generate_image_with_agent(self, mock_client, mock_memory_manager):
        """Test image generation with agent memory."""
        # Mock the generated image response
        mock_image = MagicMock()
        mock_image.image.image_bytes = b"fake_image_data"
        
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        
        mock_client.models.generate_images.return_value = mock_response
        
        # Mock agent exists
        mock_agent = MagicMock()
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = generate_image("A test image", agent_name="test_agent")
        
        assert "✅ **Image Generated Successfully**" in result
        mock_memory_manager.get_agent.assert_called_with("test_agent")
        mock_memory_manager.add_message.assert_called()
    
    def test_generate_image_no_images_generated(self, mock_client, mock_memory_manager):
        """Test when no images are generated."""
        mock_response = MagicMock()
        mock_response.generated_images = []
        
        mock_client.models.generate_images.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="No images were generated"):
            generate_image("A test image")
    
    def test_generate_image_no_image_data(self, mock_client, mock_memory_manager):
        """Test when generated image has no data."""
        mock_image = MagicMock()
        mock_image.image = None
        
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        
        mock_client.models.generate_images.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Generated image has no data"):
            generate_image("A test image")
    
    def test_create_agent_success(self, mock_memory_manager):
        """Test creating an agent."""
        mock_memory_manager.create_agent.return_value = MagicMock()
        
        result = create_agent("test_agent", "Helpful assistant")
        
        assert "Agent 'test_agent' created successfully" in result
        assert "with personality: Helpful assistant" in result
        mock_memory_manager.create_agent.assert_called_with("test_agent", "Helpful assistant")
    
    def test_create_agent_no_personality(self, mock_memory_manager):
        """Test creating an agent without personality."""
        mock_memory_manager.create_agent.return_value = MagicMock()
        
        result = create_agent("test_agent")
        
        assert "Agent 'test_agent' created successfully!" in result
        assert "with personality:" not in result
        mock_memory_manager.create_agent.assert_called_with("test_agent", None)
    
    def test_create_agent_duplicate(self, mock_memory_manager):
        """Test creating duplicate agent."""
        mock_memory_manager.create_agent.side_effect = ValueError("Agent already exists")
        
        with pytest.raises(ValueError, match="Agent already exists"):
            create_agent("test_agent")
    
    def test_list_agents_empty(self, mock_memory_manager):
        """Test listing agents when none exist."""
        mock_memory_manager.list_agents.return_value = []
        
        result = list_agents()
        
        assert "No agents found" in result
    
    def test_list_agents_with_data(self, mock_memory_manager):
        """Test listing agents with data."""
        mock_agent = MagicMock()
        mock_agent.get_stats.return_value = {
            "name": "test_agent",
            "created_at": "2025-01-01T12:00:00",
            "message_count": 5,
            "total_tokens": 100,
            "total_cost": 0.01,
            "personality": "Helpful"
        }
        mock_memory_manager.list_agents.return_value = [mock_agent]
        
        result = list_agents()
        
        assert "test_agent" in result
        assert "Messages: 5" in result
        assert "Tokens: 100" in result
        assert "Cost: $0.0100" in result
        assert "Personality: Helpful" in result
    
    def test_agent_stats_success(self, mock_memory_manager):
        """Test getting agent statistics."""
        mock_agent = MagicMock()
        mock_agent.get_stats.return_value = {
            "name": "test_agent",
            "created_at": "2025-01-01T12:00:00",
            "message_count": 5,
            "total_tokens": 100,
            "total_cost": 0.01,
            "personality": "Helpful"
        }
        mock_agent.messages = []
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = agent_stats("test_agent")
        
        assert "Agent Statistics: test_agent" in result
        assert "Total Messages: 5" in result
        assert "Total Tokens: 100" in result
    
    def test_agent_stats_with_messages(self, mock_memory_manager):
        """Test getting agent statistics with recent messages."""
        mock_message = MagicMock()
        mock_message.timestamp.strftime.return_value = "2025-01-01 12:00"
        mock_message.role = "user"
        mock_message.content = "Hello there, this is a test message that is longer than 100 characters so it should be truncated in the output"
        
        mock_agent = MagicMock()
        mock_agent.get_stats.return_value = {
            "name": "test_agent",
            "created_at": "2025-01-01T12:00:00",
            "message_count": 1,
            "total_tokens": 50,
            "total_cost": 0.005,
            "personality": None
        }
        mock_agent.messages = [mock_message]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = agent_stats("test_agent")
        
        assert "Agent Statistics: test_agent" in result
        assert "Recent Messages:" in result
        assert "2025-01-01 12:00 👤 user:" in result
        assert "Hello there, this is a test message that is longer than 100 characters so it should be truncated in ..." in result
    
    def test_agent_stats_not_found(self, mock_memory_manager):
        """Test getting stats for non-existent agent."""
        mock_memory_manager.get_agent.return_value = None
        
        with pytest.raises(ValueError, match="Agent 'test_agent' not found"):
            agent_stats("test_agent")
    
    def test_clear_agent_success(self, mock_memory_manager):
        """Test clearing agent history."""
        mock_memory_manager.clear_agent_history.return_value = True
        
        result = clear_agent("test_agent")
        
        assert "Agent 'test_agent' history cleared successfully" in result
        mock_memory_manager.clear_agent_history.assert_called_with("test_agent")
    
    def test_clear_agent_not_found(self, mock_memory_manager):
        """Test clearing non-existent agent."""
        mock_memory_manager.clear_agent_history.return_value = False
        
        with pytest.raises(ValueError, match="Agent 'test_agent' not found"):
            clear_agent("test_agent")
    
    def test_delete_agent_success(self, mock_memory_manager):
        """Test deleting agent."""
        mock_memory_manager.delete_agent.return_value = True
        
        result = delete_agent("test_agent")
        
        assert "Agent 'test_agent' deleted permanently" in result
        mock_memory_manager.delete_agent.assert_called_with("test_agent")
    
    def test_delete_agent_not_found(self, mock_memory_manager):
        """Test deleting non-existent agent."""
        mock_memory_manager.delete_agent.return_value = False
        
        with pytest.raises(ValueError, match="Agent 'test_agent' not found"):
            delete_agent("test_agent")
    
    def test_get_response_success(self, mock_memory_manager):
        """Test getting response from agent."""
        mock_memory_manager.get_response.return_value = "Test response content"
        
        result = get_response("test_agent")
        
        assert result == "Test response content"
        mock_memory_manager.get_response.assert_called_with("test_agent", -1)
    
    def test_get_response_with_index(self, mock_memory_manager):
        """Test getting response with specific index."""
        mock_memory_manager.get_response.return_value = "Specific response"
        
        result = get_response("test_agent", 2)
        
        assert result == "Specific response"
        mock_memory_manager.get_response.assert_called_with("test_agent", 2)
    
    def test_get_response_agent_not_found(self, mock_memory_manager):
        """Test getting response from non-existent agent."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = None
        
        with pytest.raises(ValueError, match="Agent 'test_agent' not found"):
            get_response("test_agent")
    
    def test_get_response_message_not_found(self, mock_memory_manager):
        """Test getting response when message index doesn't exist."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = MagicMock()  # Agent exists
        
        with pytest.raises(ValueError, match="No message found at index 5"):
            get_response("test_agent", 5)
    
    def test_server_info_success(self, mock_client, mock_memory_manager):
        """Test server info when API is working."""
        # Mock model list response
        mock_model1 = MagicMock()
        mock_model1.name = "models/gemini-1.5-pro"
        mock_model2 = MagicMock()
        mock_model2.name = "models/gemini-1.5-flash"
        
        mock_models_response = [mock_model1, mock_model2]
        mock_client.models.list.return_value = mock_models_response
        
        mock_memory_manager.list_agents.return_value = [MagicMock(), MagicMock()]
        
        result = server_info()
        
        assert "Gemini Tool Server Status" in result
        assert "Connected and ready" in result
        assert "Available Models: 2 models" in result
        assert "Active Agents: 2" in result
        assert "Available tools:" in result
    
    def test_server_info_client_not_initialized(self):
        """Test server info when client is not initialized."""
        # Temporarily set client to None to simulate initialization failure
        import mcp_handley_lab.llm.gemini.tool as gemini_tool
        original_client = gemini_tool.client
        gemini_tool.client = None
        
        try:
            with pytest.raises(RuntimeError, match="Gemini client not initialized"):
                server_info()
        finally:
            # Restore original client
            gemini_tool.client = original_client
    
    def test_server_info_api_error(self, mock_client, mock_memory_manager):
        """Test server info with API error."""
        mock_client.models.list.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="Gemini API configuration error"):
            server_info()
    
    def test_ask_with_file_output(self, mock_client, mock_memory_manager, tmp_path):
        """Test ask with file output."""
        output_file = tmp_path / "response.txt"
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Hello", output_file=str(output_file))
        
        assert "Response saved to:" in result
        assert str(output_file) in result
        assert "Content: 13 characters" in result  # "Test response" = 13 chars
        assert output_file.exists()
        assert output_file.read_text() == "Test response"
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_with_file_output(self, mock_resolve_images, mock_client, mock_memory_manager, tmp_path):
        """Test analyze_image with file output."""
        output_file = tmp_path / "analysis.txt"
        mock_resolve_images.return_value = [MagicMock()]
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        mock_client.models.generate_content.return_value = mock_response
        
        result = analyze_image("Analyze this", output_file=str(output_file), image_data="fake")
        
        assert "Response saved to:" in result
        assert str(output_file) in result
        assert "Content: 13 characters" in result
        assert output_file.exists()
        assert output_file.read_text() == "Test response"