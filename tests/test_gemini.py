"""Unit tests for Gemini LLM tool."""
import base64
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open
from PIL import Image
import io

from mcp_handley_lab.llm.gemini.tool import (
    ask, analyze_image, generate_image, create_agent, list_agents, 
    agent_stats, get_response, clear_agent, delete_agent, server_info,
    _resolve_files, _resolve_images
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
        assert result == ["content1", "content2"]
    
    def test_resolve_files_dict_content(self):
        """Test resolving files with dict content."""
        files = [
            {"content": "dict content"},
            {"content": "another content"}
        ]
        result = _resolve_files(files)
        assert result == ["dict content", "another content"]
    
    def test_resolve_files_dict_path(self, tmp_path):
        """Test resolving files with dict path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")
        
        files = [{"path": str(test_file)}]
        result = _resolve_files(files)
        assert result == ["file content"]
    
    def test_resolve_files_dict_path_error(self):
        """Test resolving files with invalid path."""
        files = [{"path": "/nonexistent/file.txt"}]
        result = _resolve_files(files)
        assert len(result) == 1
        assert "Error reading file" in result[0]
    
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
        assert result == ["string content", "dict content", "file content"]
    
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


class TestGeminiTools:
    """Test Gemini tool functions."""
    
    @pytest.fixture
    def mock_genai(self):
        """Mock google.generativeai module."""
        with patch('mcp_handley_lab.llm.gemini.tool.genai') as mock:
            # Mock model and response
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_response.usage_metadata.prompt_token_count = 10
            mock_response.usage_metadata.candidates_token_count = 20
            
            mock_model.generate_content.return_value = mock_response
            mock_model.start_chat.return_value.send_message.return_value = mock_response
            mock.GenerativeModel.return_value = mock_model
            
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
    
    def test_ask_basic(self, mock_genai, mock_memory_manager):
        """Test basic ask functionality."""
        result = ask("Hello, how are you?", output_file="-")
        
        assert "Test response" in result
        assert "💰 Usage:" in result
        mock_genai.GenerativeModel.assert_called_once()
        mock_genai.GenerativeModel.return_value.generate_content.assert_called_once()
    
    def test_ask_with_agent(self, mock_genai, mock_memory_manager):
        """Test ask with agent memory."""
        # Setup agent
        mock_agent = MagicMock()
        mock_agent.get_conversation_history.return_value = [
            {"role": "user", "content": "Previous message"}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="test_agent")
        
        assert "Test response" in result
        mock_memory_manager.get_agent.assert_called_with("test_agent")
        mock_memory_manager.add_message.assert_called()
    
    def test_ask_with_files(self, mock_genai, mock_memory_manager, tmp_path):
        """Test ask with file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("File content")
        
        files = [{"path": str(test_file)}, {"content": "Direct content"}]
        result = ask("Question about files", output_file="-", files=files)
        
        assert "Test response" in result
        # Check that file content was added to prompt
        call_args = mock_genai.GenerativeModel.return_value.generate_content.call_args[0][0]
        assert "File content" in call_args
        assert "Direct content" in call_args
    
    def test_ask_with_grounding(self, mock_genai, mock_memory_manager):
        """Test ask with grounding enabled."""
        result = ask("Current weather", output_file="-", grounding=True)
        
        assert "Test response" in result
        # Check that tools were configured
        model_call = mock_genai.GenerativeModel.call_args
        assert "tools" in model_call[1] or len(model_call[0]) > 1
    
    def test_ask_with_temperature(self, mock_genai, mock_memory_manager):
        """Test ask with custom temperature."""
        result = ask("Creative question", output_file="-", temperature=0.9)
        
        assert "Test response" in result
        # Check generation config
        gen_config = mock_genai.GenerationConfig.call_args[1]
        assert gen_config["temperature"] == 0.9
    
    def test_ask_with_agent_creation(self, mock_genai, mock_memory_manager):
        """Test ask with agent creation when agent doesn't exist."""
        # Setup no existing agent
        mock_memory_manager.get_agent.return_value = None
        mock_agent = MagicMock()
        mock_agent.get_conversation_history.return_value = []
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="new_agent")
        
        assert "Test response" in result
        mock_memory_manager.get_agent.assert_called_with("new_agent")
        mock_memory_manager.create_agent.assert_called_with("new_agent")

    def test_ask_api_error(self, mock_memory_manager):
        """Test ask with API error."""
        with patch('mcp_handley_lab.llm.gemini.tool.genai.GenerativeModel') as mock_model:
            mock_model.side_effect = Exception("API Error")
            
            with pytest.raises(RuntimeError, match="Gemini API error"):
                ask("Hello", output_file="-")
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_basic(self, mock_resolve_images, mock_genai, mock_memory_manager):
        """Test basic image analysis."""
        mock_image = MagicMock()
        mock_resolve_images.return_value = [mock_image]
        
        result = analyze_image("What's in this image?", output_file="-", image_data="fake_image_data")
        
        assert "Test response" in result
        assert "💰 Usage:" in result
        mock_resolve_images.assert_called_once()
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_with_focus(self, mock_resolve_images, mock_genai, mock_memory_manager):
        """Test image analysis with focus."""
        mock_image = MagicMock()
        mock_resolve_images.return_value = [mock_image]
        
        result = analyze_image("Analyze this", output_file="-", image_data="fake", focus="technical")
        
        assert "Test response" in result
        # Check that focus was added to prompt
        call_args = mock_genai.GenerativeModel.return_value.generate_content.call_args[0][0]
        assert "Focus on technical aspects" in call_args[0]
    
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_with_agent_creation(self, mock_resolve_images, mock_genai, mock_memory_manager):
        """Test image analysis with agent creation when agent doesn't exist."""
        mock_image = MagicMock()
        mock_resolve_images.return_value = [mock_image]
        
        # Setup no existing agent
        mock_memory_manager.get_agent.return_value = None
        mock_agent = MagicMock()
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = analyze_image("Analyze this", output_file="-", image_data="fake", agent_name="new_agent")
        
        assert "Test response" in result
        mock_memory_manager.get_agent.assert_called_with("new_agent")
        mock_memory_manager.create_agent.assert_called_with("new_agent")

    def test_analyze_image_api_error(self, mock_memory_manager):
        """Test image analysis with API error."""
        with patch('mcp_handley_lab.llm.gemini.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = [MagicMock()]
            
            with patch('mcp_handley_lab.llm.gemini.tool.genai.GenerativeModel') as mock_model:
                mock_model.side_effect = Exception("Vision API Error")
                
                with pytest.raises(RuntimeError, match="Gemini vision API error"):
                    analyze_image("Analyze this", output_file="-", image_data="fake")

    def test_analyze_image_no_images(self, mock_memory_manager):
        """Test image analysis without images."""
        with pytest.raises(ValueError, match="Either image_data or images must be provided"):
            analyze_image("What's in this image?", output_file="-")
    
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_success(self, mock_tempfile, mock_genai, mock_memory_manager):
        """Test successful image generation."""
        # Mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Mock Gemini response with image data
        mock_part = MagicMock()
        mock_part.inline_data.data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAFtqWAJgQAAAABJRU5ErkJggg=="  # 1x1 PNG
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        # Get the mock client from the fixture
        mock_client = mock_genai.GenerativeModel.return_value
        mock_client.generate_content.return_value = mock_response
        
        result = generate_image("A beautiful sunset")
        
        assert "✅ Image generated successfully!" in result
        assert "/tmp/generated_image.png" in result
        assert "💰 Usage: 1 token" in result
        assert "$0.03" in result
        
        # Check that GenerativeModel was created with correct model
        mock_genai.GenerativeModel.assert_called_once_with("imagen-3.0-generate-002")
        
        # Check generate_content was called correctly
        mock_client.generate_content.assert_called_once()
        call_args = mock_client.generate_content.call_args
        assert call_args[1]["contents"] == ["A beautiful sunset"]
        assert call_args[1]["generation_config"]["response_mime_type"] == "image/png"
    
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_with_agent(self, mock_tempfile, mock_genai, mock_memory_manager):
        """Test image generation with agent memory."""
        # Mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Mock Gemini response with image data
        mock_part = MagicMock()
        mock_part.inline_data.data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAFtqWAJgQAAAABJRU5ErkJggg=="
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        mock_client = mock_genai.GenerativeModel.return_value
        mock_client.generate_content.return_value = mock_response
        
        # Mock agent exists
        mock_agent = MagicMock()
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = generate_image("A test image", agent_name="test_agent")
        
        assert "✅ Image generated successfully!" in result
        mock_memory_manager.get_agent.assert_called_with("test_agent")
        mock_memory_manager.add_message.assert_called()
    
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
    
    def test_server_info_success(self):
        """Test server info when API is working."""
        with patch('mcp_handley_lab.llm.gemini.tool.genai.list_models') as mock_list:
            mock_model = MagicMock()
            mock_model.name = "models/gemini-1.5-pro"
            mock_list.return_value = [mock_model]
            
            with patch('mcp_handley_lab.llm.gemini.tool.memory_manager') as mock_memory:
                mock_memory.list_agents.return_value = [MagicMock(), MagicMock()]
                
                result = server_info()
                
                assert "Gemini Tool Server Status" in result
                assert "Connected and ready" in result
                assert "Available Models: 1 models" in result
                assert "Active Agents: 2" in result
                assert "Available tools:" in result
    
    def test_server_info_api_error(self):
        """Test server info with API error."""
        with patch('mcp_handley_lab.llm.gemini.tool.genai.list_models') as mock_list:
            mock_list.side_effect = Exception("API Error")
            
            with pytest.raises(RuntimeError, match="Gemini API configuration error"):
                server_info()
    
    def test_ask_with_personality_system_instruction(self, mock_genai, mock_memory_manager):
        """Test ask function with agent personality sets system instruction."""
        # Setup agent with personality
        mock_agent = MagicMock()
        mock_agent.personality = "You are a helpful coding assistant"
        mock_agent.get_conversation_history.return_value = [
            {"role": "user", "content": [{"text": "Previous message"}]}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="test_agent")
        
        # Check that GenerativeModel was called with system_instruction
        mock_genai.GenerativeModel.assert_called_once()
        call_args = mock_genai.GenerativeModel.call_args
        assert call_args[1]["system_instruction"] == "You are a helpful coding assistant"
        
        assert "Test response" in result
    
    def test_ask_without_personality_no_system_instruction(self, mock_genai, mock_memory_manager):
        """Test ask function without agent personality doesn't set system instruction."""
        # Setup agent without personality
        mock_agent = MagicMock()
        mock_agent.personality = None
        mock_agent.get_conversation_history.return_value = []
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="test_agent")
        
        # Check that GenerativeModel was called without system_instruction
        mock_genai.GenerativeModel.assert_called_once()
        call_args = mock_genai.GenerativeModel.call_args
        assert call_args[1]["system_instruction"] is None
        
        assert "Test response" in result
    
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
    
    def test_ask_with_file_output(self, mock_genai, mock_memory_manager, tmp_path):
        """Test ask with file output."""
        output_file = tmp_path / "response.txt"
        
        result = ask("Hello", output_file=str(output_file))
        
        assert "Response saved to:" in result
        assert str(output_file) in result
        assert "Content: 13 characters" in result  # "Test response" = 13 chars
        assert output_file.exists()
        assert output_file.read_text() == "Test response"
    
    def test_analyze_image_with_file_output(self, mock_genai, mock_memory_manager, tmp_path):
        """Test analyze_image with file output."""
        output_file = tmp_path / "analysis.txt"
        
        with patch('mcp_handley_lab.llm.gemini.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = [MagicMock()]
            
            result = analyze_image("Analyze this", output_file=str(output_file), image_data="fake")
            
            assert "Response saved to:" in result
            assert str(output_file) in result
            assert "Content: 13 characters" in result
            assert output_file.exists()
            assert output_file.read_text() == "Test response"


