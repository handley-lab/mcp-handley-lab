"""Comprehensive unit tests for Gemini LLM tool functionality."""
import pytest
import tempfile
import base64
import io
import os
import time
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
from PIL import Image

from mcp_handley_lab.llm.gemini.tool import (
    _get_model_config, MODEL_CONFIGS, ask, analyze_image, generate_image,
    create_agent, list_agents, agent_stats, clear_agent, delete_agent,
    get_response, server_info, _get_session_id, _resolve_files, _resolve_images,
    _handle_agent_and_usage, client, initialization_error
)


class TestHelperFunctions:
    """Test helper functions."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.get_session_id')
    def test_get_session_id(self, mock_get_session_id):
        """Test _get_session_id function."""
        mock_get_session_id.return_value = "test_session_id"
        
        result = _get_session_id()
        assert result == "test_session_id"
        mock_get_session_id.assert_called_once()


class TestResolveFiles:
    """Test file resolution functionality."""
    
    def test_resolve_files_empty_list(self):
        """Test resolving empty file list."""
        result = _resolve_files(None)
        assert result == []
        
        result = _resolve_files([])
        assert result == []
    
    def test_resolve_files_direct_string(self):
        """Test resolving direct string content."""
        files = ["Direct text content"]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert result[0].text == "Direct text content"
    
    def test_resolve_files_dict_with_content(self):
        """Test resolving dict with content key."""
        files = [{"content": "Dict content"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert result[0].text == "Dict content"
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    @patch('mcp_handley_lab.llm.gemini.tool.is_text_file')
    def test_resolve_files_small_text_file(self, mock_is_text, mock_read_text, mock_stat, mock_exists):
        """Test resolving small text file."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 1000  # Small file
        mock_read_text.return_value = "File content"
        mock_is_text.return_value = True
        
        files = [{"path": "/tmp/test.txt"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert "[File: test.txt]" in result[0].text
        assert "File content" in result[0].text
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_bytes')
    @patch('mcp_handley_lab.llm.gemini.tool.is_text_file')
    @patch('mcp_handley_lab.llm.gemini.tool.determine_mime_type')
    def test_resolve_files_small_binary_file(self, mock_mime_type, mock_is_text, mock_read_bytes, mock_stat, mock_exists):
        """Test resolving small binary file."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 1000  # Small file
        mock_read_bytes.return_value = b'\x00\x01\x02'
        mock_is_text.return_value = False
        mock_mime_type.return_value = "application/octet-stream"
        
        files = [{"path": "/tmp/test.bin"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert hasattr(result[0], 'inline_data')
        assert result[0].inline_data.mime_type == "application/octet-stream"
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.determine_mime_type')
    def test_resolve_files_large_file_upload(self, mock_mime_type, mock_client, mock_stat, mock_exists):
        """Test resolving large file with Files API."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 25 * 1024 * 1024  # 25MB file
        mock_mime_type.return_value = "text/plain"
        
        # Mock file upload
        mock_uploaded_file = Mock()
        mock_uploaded_file.uri = "gs://test-bucket/file.txt"
        mock_client.files.upload.return_value = mock_uploaded_file
        
        files = [{"path": "/tmp/large.txt"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert hasattr(result[0], 'file_data')
        assert result[0].file_data.file_uri == "gs://test-bucket/file.txt"
    
    @patch('pathlib.Path.exists')
    def test_resolve_files_nonexistent_file(self, mock_exists):
        """Test resolving non-existent file."""
        mock_exists.return_value = False
        
        files = [{"path": "/tmp/nonexistent.txt"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert "Error: File not found" in result[0].text


class TestResolveImages:
    """Test image resolution functionality."""
    
    def test_resolve_images_empty(self):
        """Test resolving empty image inputs."""
        result = _resolve_images()
        assert result == []
        
        result = _resolve_images(None, None)
        assert result == []
    
    @patch('mcp_handley_lab.llm.gemini.tool.resolve_image_data')
    @patch('PIL.Image.open')
    def test_resolve_images_single_image(self, mock_image_open, mock_resolve_image_data):
        """Test resolving single image data."""
        mock_resolve_image_data.return_value = b"image_data"
        mock_image = Mock()
        mock_image_open.return_value = mock_image
        
        result = _resolve_images(image_data="test_image")
        
        assert len(result) == 1
        assert result[0] == mock_image
        mock_resolve_image_data.assert_called_once_with("test_image")
    
    @patch('mcp_handley_lab.llm.gemini.tool.resolve_image_data')
    @patch('PIL.Image.open')
    def test_resolve_images_multiple_images(self, mock_image_open, mock_resolve_image_data):
        """Test resolving multiple images."""
        mock_resolve_image_data.side_effect = [b"image1", b"image2"]
        mock_image1, mock_image2 = Mock(), Mock()
        mock_image_open.side_effect = [mock_image1, mock_image2]
        
        result = _resolve_images(images=["image1", "image2"])
        
        assert len(result) == 2
        assert result[0] == mock_image1
        assert result[1] == mock_image2
    
    @patch('mcp_handley_lab.llm.gemini.tool.resolve_image_data')
    def test_resolve_images_error_handling(self, mock_resolve_image_data):
        """Test error handling in image resolution."""
        mock_resolve_image_data.side_effect = Exception("Image load error")
        
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(image_data="bad_image")


class TestHandleAgentAndUsage:
    """Test agent memory and usage handling."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_agent_memory')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_handle_agent_and_usage(self, mock_handle_output, mock_handle_agent_memory, mock_calculate_cost):
        """Test agent memory and usage handling."""
        mock_calculate_cost.return_value = 0.001
        mock_handle_output.return_value = "Output result"
        
        result = _handle_agent_and_usage(
            agent_name="test_agent",
            user_prompt="Test prompt",
            response_text="Test response",
            model="gemini-1.5-flash",
            input_tokens=100,
            output_tokens=50,
            output_file="/tmp/test.txt"
        )
        
        assert result == "Output result"
        mock_calculate_cost.assert_called_once_with("gemini-1.5-flash", 100, 50, "gemini")
        mock_handle_agent_memory.assert_called_once()
        mock_handle_output.assert_called_once()


class TestAgentManagement:
    """Test agent management functions."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_create_agent_success(self, mock_memory_manager):
        """Test successful agent creation."""
        mock_agent = Mock()
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = create_agent("test_agent", "Test personality")
        
        assert "test_agent" in result
        assert "created successfully" in result
        assert "Test personality" in result
        mock_memory_manager.create_agent.assert_called_once_with("test_agent", "Test personality")
    
    def test_create_agent_empty_name(self):
        """Test creating agent with empty name."""
        with pytest.raises(ValueError, match="Agent name is required"):
            create_agent("")
        
        with pytest.raises(ValueError, match="Agent name is required"):
            create_agent("   ")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_create_agent_error(self, mock_memory_manager):
        """Test agent creation error handling."""
        mock_memory_manager.create_agent.side_effect = ValueError("Agent already exists")
        
        with pytest.raises(ValueError, match="Agent already exists"):
            create_agent("existing_agent")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_list_agents_empty(self, mock_memory_manager):
        """Test listing agents when none exist."""
        mock_memory_manager.list_agents.return_value = []
        
        result = list_agents()
        assert "No agents found" in result
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_list_agents_with_data(self, mock_memory_manager):
        """Test listing agents with data."""
        mock_agent = Mock()
        mock_agent.get_stats.return_value = {
            'name': 'test_agent',
            'created_at': '2024-01-01T00:00:00',
            'message_count': 10,
            'total_tokens': 1000,
            'total_cost': 0.01,
            'personality': 'Test personality'
        }
        mock_memory_manager.list_agents.return_value = [mock_agent]
        
        result = list_agents()
        assert "test_agent" in result
        assert "2024-01-01" in result
        assert "10" in result
        assert "1,000" in result
        assert "$0.0100" in result
        assert "Test personality" in result
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_agent_stats_success(self, mock_memory_manager):
        """Test getting agent statistics."""
        mock_agent = Mock()
        mock_agent.get_stats.return_value = {
            'created_at': '2024-01-01T00:00:00',
            'message_count': 5,
            'total_tokens': 500,
            'total_cost': 0.005,
            'personality': 'Test personality'
        }
        mock_agent.messages = []
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = agent_stats("test_agent")
        assert "test_agent" in result
        assert "2024-01-01T00:00:00" in result
        assert "500" in result
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_agent_stats_not_found(self, mock_memory_manager):
        """Test getting stats for non-existent agent."""
        mock_memory_manager.get_agent.return_value = None
        
        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            agent_stats("nonexistent")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_clear_agent_success(self, mock_memory_manager):
        """Test clearing agent history."""
        mock_memory_manager.clear_agent_history.return_value = True
        
        result = clear_agent("test_agent")
        assert "test_agent" in result
        assert "cleared successfully" in result
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_clear_agent_not_found(self, mock_memory_manager):
        """Test clearing non-existent agent."""
        mock_memory_manager.clear_agent_history.return_value = False
        
        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            clear_agent("nonexistent")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_delete_agent_success(self, mock_memory_manager):
        """Test deleting agent."""
        mock_memory_manager.delete_agent.return_value = True
        
        result = delete_agent("test_agent")
        assert "test_agent" in result
        assert "deleted permanently" in result
    
    def test_delete_agent_empty_name(self):
        """Test deleting agent with empty name."""
        with pytest.raises(ValueError, match="Agent name is required"):
            delete_agent("")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_delete_agent_not_found(self, mock_memory_manager):
        """Test deleting non-existent agent."""
        mock_memory_manager.delete_agent.return_value = False
        
        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            delete_agent("nonexistent")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_get_response_success(self, mock_memory_manager):
        """Test getting response from agent."""
        mock_memory_manager.get_response.return_value = "Test response"
        
        result = get_response("test_agent", 0)
        assert result == "Test response"
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_get_response_agent_not_found(self, mock_memory_manager):
        """Test getting response when agent doesn't exist."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = None
        
        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            get_response("nonexistent")
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_get_response_no_message(self, mock_memory_manager):
        """Test getting response when message doesn't exist."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = Mock()  # Agent exists
        
        with pytest.raises(ValueError, match="No message found at index 5"):
            get_response("test_agent", 5)


class TestImageGeneration:
    """Test image generation functionality."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('uuid.uuid4')
    @patch('tempfile.gettempdir')
    @patch('pathlib.Path.write_bytes')
    def test_generate_image_success(self, mock_write_bytes, mock_tempdir, mock_uuid, 
                                  mock_format_usage, mock_calculate_cost, mock_memory_manager, mock_client):
        """Test successful image generation."""
        # Setup mocks
        mock_tempdir.return_value = "/tmp"
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = lambda self: "12345678-1234-1234-1234-123456789012"
        mock_calculate_cost.return_value = 0.01
        mock_format_usage.return_value = "Usage: $0.01"
        
        # Mock response
        mock_image = Mock()
        mock_image.image.image_bytes = b"image_data"
        mock_response = Mock()
        mock_response.generated_images = [mock_image]
        mock_client.models.generate_images.return_value = mock_response
        
        # Mock memory
        mock_agent = Mock()
        mock_memory_manager.get_agent.return_value = None
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = generate_image("A beautiful landscape", agent_name="test_agent")
        
        assert "Image Generated Successfully" in result
        assert "gemini_generated_12345678.png" in result
        mock_client.models.generate_images.assert_called_once()
    
    def test_generate_image_empty_prompt(self):
        """Test image generation with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required"):
            generate_image("")
    
    def test_generate_image_empty_agent_name(self):
        """Test image generation with empty agent name."""
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            generate_image("Test prompt", agent_name="   ")
    
    @patch('mcp_handley_lab.llm.gemini.tool.client', None)
    def test_generate_image_no_client(self):
        """Test image generation when client not initialized."""
        with pytest.raises(RuntimeError, match="Gemini client not initialized"):
            generate_image("Test prompt")
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_generate_image_no_images_generated(self, mock_client):
        """Test when no images are generated."""
        mock_response = Mock()
        mock_response.generated_images = []
        mock_client.models.generate_images.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="No images were generated"):
            generate_image("Test prompt", agent_name=False)
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_generate_image_no_image_data(self, mock_client):
        """Test when generated image has no data."""
        mock_image = Mock()
        mock_image.image = None
        mock_response = Mock()
        mock_response.generated_images = [mock_image]
        mock_client.models.generate_images.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Generated image has no data"):
            generate_image("Test prompt", agent_name=False)


class TestServerInfo:
    """Test server info functionality."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_server_info_success(self, mock_memory_manager, mock_client):
        """Test successful server info retrieval."""
        # Mock models response
        mock_model1 = Mock()
        mock_model1.name = "models/gemini-1.5-flash"
        mock_model2 = Mock()
        mock_model2.name = "models/gemini-1.5-pro"
        mock_client.models.list.return_value = [mock_model1, mock_model2]
        
        # Mock memory manager
        mock_memory_manager.list_agents.return_value = [Mock(), Mock()]
        mock_memory_manager.storage_dir = "/tmp/memory"
        
        result = server_info()
        
        assert "Connected and ready" in result
        assert "2 models" in result
        assert "gemini-1.5-flash" in result
        assert "Active Agents: 2" in result
        assert "/tmp/memory" in result
    
    @patch('mcp_handley_lab.llm.gemini.tool.client', None)
    def test_server_info_no_client(self):
        """Test server info when client not initialized."""
        with pytest.raises(RuntimeError, match="Gemini client not initialized"):
            server_info()
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_server_info_api_error(self, mock_client):
        """Test server info with API error."""
        mock_client.models.list.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="Gemini API configuration error"):
            server_info()


class TestInputValidationComprehensive:
    """Test comprehensive input validation across all functions."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_ask_input_validation(self, mock_client):
        """Test ask function input validation."""
        # Empty prompt
        with pytest.raises(ValueError, match="Prompt is required"):
            ask("", "/tmp/test.txt")
        
        # Empty output file
        with pytest.raises(ValueError, match="Output file is required"):
            ask("Test", "")
        
        # Empty agent name when provided
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            ask("Test", "/tmp/test.txt", agent_name="   ")
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_analyze_image_input_validation(self, mock_client):
        """Test analyze_image function input validation."""
        # Empty prompt
        with pytest.raises(ValueError, match="Prompt is required"):
            analyze_image("", "/tmp/test.txt", image_data="test")
        
        # No images provided
        with pytest.raises(ValueError, match="Either image_data or images must be provided"):
            analyze_image("Test", "/tmp/test.txt")
        
        # Empty agent name when provided
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            analyze_image("Test", "/tmp/test.txt", image_data="test", agent_name="   ")


class TestMemoryDisabling:
    """Test memory disabling functionality."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_ask_memory_disabled(self, mock_write_text, mock_format_usage, mock_calculate_cost, mock_client):
        """Test ask function with memory disabled."""
        # Setup mocks
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        result = ask("Test prompt", "/tmp/test.txt", agent_name=False)
        
        assert "Response saved to" in result
        assert "Usage: $0.001" in result
        mock_write_text.assert_called_once_with("Test response")
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_analyze_image_memory_disabled(self, mock_write_text, mock_format_usage, mock_calculate_cost, 
                                         mock_resolve_images, mock_client):
        """Test analyze_image function with memory disabled."""
        # Setup mocks
        mock_resolve_images.return_value = [Mock()]
        mock_response = Mock()
        mock_response.text = "Image analysis"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.002
        mock_format_usage.return_value = "Usage: $0.002"
        
        result = analyze_image("Analyze this", "/tmp/test.txt", image_data="test", agent_name=False)
        
        assert "Response saved to" in result
        assert "Usage: $0.002" in result
        mock_write_text.assert_called_once_with("Image analysis")


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_ask_api_error(self, mock_client):
        """Test ask function with API error."""
        mock_client.models.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="Gemini API error"):
            ask("Test prompt", "/tmp/test.txt", agent_name=False)
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_ask_no_response_text(self, mock_client):
        """Test ask function when no response text generated."""
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="No response text generated"):
            ask("Test prompt", "/tmp/test.txt", agent_name=False)
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_api_error(self, mock_resolve_images, mock_client):
        """Test analyze_image function with API error."""
        mock_resolve_images.return_value = [Mock()]
        mock_client.models.generate_content.side_effect = Exception("Vision API Error")
        
        with pytest.raises(RuntimeError, match="Gemini vision API error"):
            analyze_image("Test prompt", "/tmp/test.txt", image_data="test", agent_name=False)
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    def test_analyze_image_no_response_text(self, mock_resolve_images, mock_client):
        """Test analyze_image function when no response text generated."""
        mock_resolve_images.return_value = [Mock()]
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="No response text generated"):
            analyze_image("Test prompt", "/tmp/test.txt", image_data="test", agent_name=False)


class TestConversationHistory:
    """Test conversation history handling."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    @patch('mcp_handley_lab.llm.gemini.tool._get_session_id')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_files')
    @patch('mcp_handley_lab.llm.gemini.tool._handle_agent_and_usage')
    def test_ask_with_history(self, mock_handle_agent, mock_resolve_files, mock_get_session_id, 
                             mock_memory_manager, mock_client):
        """Test ask function with conversation history."""
        # Setup mocks
        mock_get_session_id.return_value = "session_123"
        mock_resolve_files.return_value = []
        mock_handle_agent.return_value = "Result"
        
        mock_agent = Mock()
        mock_agent.personality = "Test personality"
        mock_agent.get_conversation_history.return_value = [
            {"role": "user", "parts": [{"text": "Previous question"}]},
            {"role": "assistant", "parts": [{"text": "Previous answer"}]}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        mock_response = Mock()
        mock_response.text = "New response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("New question", "/tmp/test.txt", agent_name="test_agent")
        
        assert result == "Result"
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert "contents" in call_args.kwargs
        assert call_args.kwargs["config"].system_instruction == "Test personality"
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_files')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage') 
    @patch('pathlib.Path.write_text')
    def test_ask_with_files_no_history(self, mock_write_text, mock_format_usage, mock_calculate_cost, mock_resolve_files, mock_client):
        """Test ask function with files but no history."""
        # Setup mocks
        mock_resolve_files.return_value = [Mock()]
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        mock_response = Mock()
        mock_response.text = "Response with files"
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Question with files", "/tmp/test.txt", files=[{"path": "/tmp/file.txt"}], agent_name=False)
        
        assert "Response saved to" in result
        assert "Usage: $0.001" in result
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert "contents" in call_args.kwargs
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_ask_simple_text_only(self, mock_write_text, mock_format_usage, mock_calculate_cost, mock_client):
        """Test ask function with simple text-only prompt."""
        # Setup mocks
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        mock_response = Mock()
        mock_response.text = "Simple response"
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 3
        mock_client.models.generate_content.return_value = mock_response
        
        result = ask("Simple question", "/tmp/test.txt", agent_name=False)
        
        assert "Response saved to" in result
        assert "Usage: $0.001" in result
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert call_args.kwargs["contents"] == "Simple question"


class TestStdoutOutput:
    """Test stdout output functionality."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    def test_ask_stdout_output(self, mock_format_usage, mock_calculate_cost, mock_client):
        """Test ask function with stdout output."""
        # Setup mocks
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        result = ask("Test prompt", "-", agent_name=False)
        
        assert result == "Test response\n\nUsage: $0.001"
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    def test_analyze_image_stdout_output(self, mock_format_usage, mock_calculate_cost, 
                                       mock_resolve_images, mock_client):
        """Test analyze_image function with stdout output."""
        # Setup mocks
        mock_resolve_images.return_value = [Mock()]
        mock_response = Mock()
        mock_response.text = "Image analysis"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.002
        mock_format_usage.return_value = "Usage: $0.002"
        
        result = analyze_image("Analyze this", "-", image_data="test", agent_name=False)
        
        assert result == "Image analysis\n\nUsage: $0.002"


class TestImageGenerationMemoryDisabled:
    """Test image generation with memory disabled."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('uuid.uuid4')
    @patch('tempfile.gettempdir')
    @patch('pathlib.Path.write_bytes')
    def test_generate_image_memory_disabled(self, mock_write_bytes, mock_tempdir, mock_uuid, 
                                          mock_format_usage, mock_calculate_cost, mock_client):
        """Test image generation with memory disabled."""
        # Setup mocks
        mock_tempdir.return_value = "/tmp"
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = lambda self: "12345678-1234-1234-1234-123456789012"
        mock_calculate_cost.return_value = 0.01
        mock_format_usage.return_value = "Usage: $0.01"
        
        # Mock response
        mock_image = Mock()
        mock_image.image.image_bytes = b"image_data"
        mock_response = Mock()
        mock_response.generated_images = [mock_image]
        mock_client.models.generate_images.return_value = mock_response
        
        result = generate_image("A beautiful landscape", agent_name=False)
        
        assert "Image Generated Successfully" in result
        assert "gemini_generated_12345678.png" in result
        mock_client.models.generate_images.assert_called_once()


class TestFileUploadFallback:
    """Test file upload fallback scenarios."""
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.determine_mime_type')
    def test_resolve_files_upload_failure_fallback(self, mock_mime_type, mock_client, mock_read_text, mock_stat, mock_exists):
        """Test fallback when file upload fails."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 25 * 1024 * 1024  # 25MB file
        mock_mime_type.return_value = "text/plain"
        mock_read_text.return_value = "File content"
        
        # Mock upload failure
        mock_client.files.upload.side_effect = Exception("Upload failed")
        
        files = [{"path": "/tmp/large.txt"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert "[File: large.txt]" in result[0].text
        assert "File content" in result[0].text
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.determine_mime_type')
    def test_resolve_files_upload_failure_unicode_error(self, mock_mime_type, mock_client, mock_read_text, mock_stat, mock_exists):
        """Test fallback when upload fails and text read has unicode error."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 25 * 1024 * 1024  # 25MB file
        mock_mime_type.return_value = "text/plain"
        mock_read_text.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        
        # Mock upload failure
        mock_client.files.upload.side_effect = Exception("Upload failed")
        
        files = [{"path": "/tmp/large.txt"}]
        result = _resolve_files(files)
        
        assert len(result) == 1
        assert "Error: Could not upload or read file" in result[0].text


class TestClientInitialization:
    """Test client initialization scenarios."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client', None)
    @patch('mcp_handley_lab.llm.gemini.tool.initialization_error', "API key not configured")
    def test_ask_no_client_initialization(self):
        """Test ask function when client not initialized."""
        with pytest.raises(RuntimeError, match="Gemini client not initialized: API key not configured"):
            ask("Test prompt", "/tmp/test.txt")
    
    @patch('mcp_handley_lab.llm.gemini.tool.client', None)
    @patch('mcp_handley_lab.llm.gemini.tool.initialization_error', "API key not configured")
    def test_analyze_image_no_client_initialization(self):
        """Test analyze_image function when client not initialized."""
        with pytest.raises(RuntimeError, match="Gemini client not initialized: API key not configured"):
            analyze_image("Test prompt", "/tmp/test.txt", image_data="test")


class TestAgentStatsWithMessages:
    """Test agent stats with message history."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.memory_manager')
    def test_agent_stats_with_messages(self, mock_memory_manager):
        """Test getting agent statistics with message history."""
        # Mock message with timestamp
        mock_message = Mock()
        mock_message.timestamp.strftime.return_value = "2024-01-01 12:00"
        mock_message.role = "user"
        mock_message.content = "This is a test message with enough content to be truncated"
        
        mock_agent = Mock()
        mock_agent.get_stats.return_value = {
            'created_at': '2024-01-01T00:00:00',
            'message_count': 1,
            'total_tokens': 100,
            'total_cost': 0.001,
            'personality': None
        }
        mock_agent.messages = [mock_message]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = agent_stats("test_agent")
        assert "test_agent" in result
        assert "2024-01-01 12:00" in result
        assert "user:" in result
        assert "This is a test message" in result


class TestNonStandardModelNames:
    """Test non-standard model name handling."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_ask_with_full_model_name(self, mock_write_text, mock_format_usage, mock_calculate_cost, mock_client):
        """Test ask function with full model name."""
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        result = ask("Test prompt", "/tmp/test.txt", model="gemini-1.5-flash-002", agent_name=False)
        
        assert "Response saved to" in result
        call_args = mock_client.models.generate_content.call_args
        assert call_args.kwargs["model"] == "gemini-1.5-flash-002"
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_analyze_image_with_full_model_name(self, mock_write_text, mock_format_usage, mock_calculate_cost, 
                                              mock_resolve_images, mock_client):
        """Test analyze_image function with full model name."""
        mock_resolve_images.return_value = [Mock()]
        mock_response = Mock()
        mock_response.text = "Image analysis"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.002
        mock_format_usage.return_value = "Usage: $0.002"
        
        result = analyze_image("Test prompt", "/tmp/test.txt", image_data="test", 
                             model="gemini-1.5-pro-002", agent_name=False)
        
        assert "Response saved to" in result
        call_args = mock_client.models.generate_content.call_args
        assert call_args.kwargs["model"] == "gemini-1.5-pro-002"


class TestGroundingAndTools:
    """Test grounding (Google Search) functionality."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_ask_with_grounding(self, mock_write_text, mock_format_usage, mock_calculate_cost, mock_client):
        """Test ask function with grounding enabled."""
        mock_response = Mock()
        mock_response.text = "Test response with grounding"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.001
        mock_format_usage.return_value = "Usage: $0.001"
        
        result = ask("What's the weather today?", "/tmp/test.txt", grounding=True, agent_name=False)
        
        assert "Response saved to" in result
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert hasattr(config, 'tools')
        assert len(config.tools) == 1


class TestAnalyzeImageFocus:
    """Test image analysis focus enhancement."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.calculate_cost')
    @patch('mcp_handley_lab.llm.gemini.tool.format_usage')
    @patch('pathlib.Path.write_text')
    def test_analyze_image_with_focus(self, mock_write_text, mock_format_usage, mock_calculate_cost, 
                                    mock_resolve_images, mock_client):
        """Test analyze_image function with focus enhancement."""
        mock_resolve_images.return_value = [Mock()]
        mock_response = Mock()
        mock_response.text = "Technical analysis"
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 15
        mock_client.models.generate_content.return_value = mock_response
        mock_calculate_cost.return_value = 0.003
        mock_format_usage.return_value = "Usage: $0.003"
        
        result = analyze_image("Analyze the diagram", "/tmp/test.txt", image_data="test", 
                             focus="technical", agent_name=False)
        
        assert "Response saved to" in result
        call_args = mock_client.models.generate_content.call_args
        # The prompt should be enhanced with focus
        contents = call_args.kwargs["contents"]
        assert "Focus on technical aspects" in contents[0]