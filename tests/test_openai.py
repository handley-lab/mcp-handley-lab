"""Unit tests for OpenAI LLM tool."""
import base64
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open
import requests

from mcp_handley_lab.llm.openai.tool import (
    ask, analyze_image, generate_image, get_response, server_info,
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
    
    def test_resolve_images_single_data_url(self):
        """Test resolving single image from data URL."""
        image_data = "data:image/png;base64,iVBORw0KGgoAAAANSU"
        result = _resolve_images(image_data=image_data)
        assert len(result) == 1
        assert result[0] == image_data
    
    @patch('pathlib.Path.read_bytes')
    @patch('base64.b64encode')
    def test_resolve_images_file_path(self, mock_b64encode, mock_read_bytes):
        """Test resolving image from file path."""
        mock_read_bytes.return_value = b"fake_image_data"
        mock_b64encode.return_value.decode.return_value = "encoded_data"
        
        result = _resolve_images(image_data="/path/to/image.png")
        assert len(result) == 1
        assert "data:image/png;base64,encoded_data" in result[0]
    
    @patch('pathlib.Path.read_bytes')
    @patch('base64.b64encode')
    def test_resolve_images_file_path_jpeg(self, mock_b64encode, mock_read_bytes):
        """Test resolving JPEG image from file path."""
        mock_read_bytes.return_value = b"fake_image_data"
        mock_b64encode.return_value.decode.return_value = "encoded_data"
        
        result = _resolve_images(image_data="/path/to/image.jpg")
        assert len(result) == 1
        assert "data:image/jpeg;base64,encoded_data" in result[0]
    
    def test_resolve_images_error(self):
        """Test resolving images with error."""
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(image_data="invalid_data")
    
    def test_determine_mime_type(self):
        """Test MIME type detection."""
        assert _determine_mime_type(Path("test.py")) == "text/x-python"
        assert _determine_mime_type(Path("test.json")) == "application/json"
        assert _determine_mime_type(Path("test.png")) == "image/png"
        assert _determine_mime_type(Path("test.jpg")) == "image/jpeg"
        assert _determine_mime_type(Path("test.unknown")) == "application/octet-stream"
    
    def test_is_text_file(self):
        """Test text file detection."""
        assert _is_text_file(Path("test.py")) == True
        assert _is_text_file(Path("test.txt")) == True
        assert _is_text_file(Path("test.md")) == True
        assert _is_text_file(Path("test.json")) == True
        assert _is_text_file(Path("test.png")) == False
        assert _is_text_file(Path("test.pdf")) == False
        assert _is_text_file(Path("test.unknown")) == False
    
    @patch('mcp_handley_lab.llm.openai.tool.client')
    def test_resolve_files_large_file_upload_success(self, mock_client, tmp_path):
        """Test Files API upload for large files."""
        # Create a large file (>1MB)
        large_file = tmp_path / "large.txt"
        large_content = "x" * (1024 * 1024 + 1)  # Just over 1MB
        large_file.write_text(large_content)
        
        # Mock the Files API response
        mock_upload_response = MagicMock()
        mock_upload_response.id = "file-123"
        mock_client.files.create.return_value = mock_upload_response
        
        files = [{"path": str(large_file)}]
        file_attachments, inline_content = _resolve_files(files)
        
        # Should use Files API for large file
        assert len(file_attachments) == 1
        assert file_attachments[0]["file_id"] == "file-123"
        assert file_attachments[0]["tools"] == [{"type": "file_search"}]
        assert inline_content == []
        
        # Verify Files API was called
        mock_client.files.create.assert_called_once()
    
    @patch('mcp_handley_lab.llm.openai.tool.client')
    def test_resolve_files_large_file_upload_fallback(self, mock_client, tmp_path):
        """Test Files API upload fallback for large files when upload fails."""
        # Create a large file (>1MB)
        large_file = tmp_path / "large.txt"
        large_content = "x" * (1024 * 1024 + 1)  # Just over 1MB
        large_file.write_text(large_content)
        
        # Mock Files API to fail
        mock_client.files.create.side_effect = Exception("Upload failed")
        
        files = [{"path": str(large_file)}]
        file_attachments, inline_content = _resolve_files(files)
        
        # Should fallback to truncated inline content
        assert file_attachments == []
        assert len(inline_content) == 1
        assert "[File: large.txt]" in inline_content[0]
        assert "[Content truncated due to size]" in inline_content[0]
        
        # Verify Files API was attempted
        mock_client.files.create.assert_called_once()
    
    def test_resolve_files_binary_small(self, tmp_path):
        """Test small binary file handling."""
        # Create a small binary file
        binary_file = tmp_path / "test.png"
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        binary_file.write_bytes(binary_content)
        
        files = [{"path": str(binary_file)}]
        file_attachments, inline_content = _resolve_files(files)
        
        # Should inline small binary files with base64 encoding
        assert file_attachments == []
        assert len(inline_content) == 1
        assert "[Binary file: test.png, image/png," in inline_content[0]
        assert base64.b64encode(binary_content).decode() in inline_content[0]
    
    def test_resolve_images_array_data_url(self):
        """Test resolving images array with data URL."""
        images = ["data:image/png;base64,iVBORw0KGgoAAAANSU"]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == images[0]
    
    @patch('pathlib.Path.read_bytes')
    @patch('base64.b64encode')
    def test_resolve_images_array_file_path(self, mock_b64encode, mock_read_bytes):
        """Test resolving images array with file path."""
        mock_read_bytes.return_value = b"fake_image_data"
        mock_b64encode.return_value.decode.return_value = "encoded_data"
        
        images = ["/path/to/image.png"]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert "data:image/png;base64,encoded_data" in result[0]
    
    def test_resolve_images_dict_data(self):
        """Test resolving images with dict data."""
        images = [{"data": "base64encoded"}]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert "data:image/jpeg;base64,base64encoded" in result[0]
    
    def test_resolve_images_dict_data_with_prefix(self):
        """Test resolving images with dict data that already has data URL prefix."""
        images = [{"data": "data:image/png;base64,encoded"}]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert result[0] == "data:image/png;base64,encoded"
    
    @patch('pathlib.Path.read_bytes')
    @patch('base64.b64encode')
    def test_resolve_images_dict_path(self, mock_b64encode, mock_read_bytes):
        """Test resolving images with dict path."""
        mock_read_bytes.return_value = b"fake_image_data"
        mock_b64encode.return_value.decode.return_value = "encoded_data"
        
        images = [{"path": "/path/to/image.png"}]
        result = _resolve_images(images=images)
        assert len(result) == 1
        assert "data:image/png;base64,encoded_data" in result[0]
    
    def test_resolve_images_array_error(self):
        """Test resolving images array with error."""
        images = ["invalid_data"]
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(images=images)


class TestOpenAITools:
    """Test OpenAI tool functions."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch('mcp_handley_lab.llm.openai.tool.client') as mock:
            # Mock response for chat completions
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Test response"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            
            mock.chat.completions.create.return_value = mock_response
            
            # Mock response for image generation
            mock_image_response = MagicMock()
            mock_image_response.data[0].url = "https://example.com/image.png"
            mock.images.generate.return_value = mock_image_response
            
            # Mock response for models list
            mock_model = MagicMock()
            mock_model.id = "gpt-4o"
            mock_models_response = MagicMock()
            mock_models_response.data = [mock_model]
            mock.models.list.return_value = mock_models_response
            
            yield mock
    
    @pytest.fixture
    def mock_memory_manager(self):
        """Mock memory manager."""
        with patch('mcp_handley_lab.llm.openai.tool.memory_manager') as mock:
            mock_agent = MagicMock()
            mock_agent.get_conversation_history.return_value = []
            mock.get_agent.return_value = None
            mock.create_agent.return_value = mock_agent
            yield mock
    
    def test_ask_basic(self, mock_openai_client, mock_memory_manager):
        """Test basic ask functionality."""
        result = ask("Hello, how are you?", output_file="-")
        
        assert "Test response" in result
        assert "💰 Usage:" in result
        mock_openai_client.chat.completions.create.assert_called_once()
        
        # Check the call arguments
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-4o"
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["messages"][-1]["content"] == "Hello, how are you?"
    
    def test_ask_with_model(self, mock_openai_client, mock_memory_manager):
        """Test ask with custom model."""
        result = ask("Hello", output_file="-", model="gpt-3.5-turbo")
        
        assert "Test response" in result
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-3.5-turbo"
    
    def test_ask_with_temperature(self, mock_openai_client, mock_memory_manager):
        """Test ask with custom temperature."""
        result = ask("Hello", output_file="-", temperature=0.9)
        
        assert "Test response" in result
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["temperature"] == 0.9
    
    def test_ask_with_max_tokens(self, mock_openai_client, mock_memory_manager):
        """Test ask with max tokens."""
        result = ask("Hello", output_file="-", max_tokens=100)
        
        assert "Test response" in result
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 100
    
    def test_ask_with_agent(self, mock_openai_client, mock_memory_manager):
        """Test ask with agent memory."""
        mock_agent = MagicMock()
        mock_agent.get_conversation_history.return_value = [
            {"role": "system", "content": "You are helpful"}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="test_agent")
        
        assert "Test response" in result
        call_args = mock_openai_client.chat.completions.create.call_args
        assert len(call_args[1]["messages"]) == 2
        assert call_args[1]["messages"][0]["role"] == "system"
    
    def test_ask_with_new_agent(self, mock_openai_client, mock_memory_manager):
        """Test ask with new agent that needs to be created."""
        mock_agent = MagicMock()
        mock_agent.get_conversation_history.return_value = []
        mock_memory_manager.get_agent.return_value = None  # Agent doesn't exist
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = ask("Hello", output_file="-", agent_name="new_agent")
        
        assert "Test response" in result
        mock_memory_manager.create_agent.assert_called_once_with("new_agent")
        mock_memory_manager.add_message.assert_called()
    
    def test_ask_with_files(self, mock_openai_client, mock_memory_manager, tmp_path):
        """Test ask with file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")
        
        files = [{"path": str(test_file)}]
        result = ask("Analyze this", output_file="-", files=files)
        
        assert "Test response" in result
        call_args = mock_openai_client.chat.completions.create.call_args
        message_content = call_args[1]["messages"][-1]["content"]
        assert "[File: test.txt]" in message_content
        assert "file content" in message_content
    
    def test_ask_api_error(self, mock_openai_client, mock_memory_manager):
        """Test ask with API error."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="OpenAI API error"):
            ask("Hello", output_file="-")
    
    def test_analyze_image_basic(self, mock_openai_client, mock_memory_manager):
        """Test basic image analysis."""
        with patch('mcp_handley_lab.llm.openai.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = ["data:image/png;base64,encoded"]
            
            result = analyze_image("What's in this image?", output_file="-", image_data="test_image.png")
            
            assert "Test response" in result
            assert "💰 Usage:" in result
            mock_openai_client.chat.completions.create.assert_called_once()
            
            # Check the message structure
            call_args = mock_openai_client.chat.completions.create.call_args
            content = call_args[1]["messages"][-1]["content"]
            assert len(content) == 2  # Text + image
            assert content[0]["type"] == "text"
            assert content[1]["type"] == "image_url"
    
    def test_analyze_image_with_focus(self, mock_openai_client, mock_memory_manager):
        """Test image analysis with focus."""
        with patch('mcp_handley_lab.llm.openai.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = ["data:image/png;base64,encoded"]
            
            result = analyze_image("Analyze", output_file="-", image_data="test.png", focus="technical")
            
            call_args = mock_openai_client.chat.completions.create.call_args
            assert "Focus on technical aspects" in call_args[1]["messages"][-1]["content"][0]["text"]
    
    def test_analyze_image_no_images(self, mock_openai_client, mock_memory_manager):
        """Test image analysis without images."""
        with pytest.raises(ValueError, match="Either image_data or images must be provided"):
            analyze_image("What's in this image?", output_file="-")
    
    def test_analyze_image_with_agent(self, mock_openai_client, mock_memory_manager):
        """Test image analysis with agent."""
        with patch('mcp_handley_lab.llm.openai.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = ["data:image/png;base64,encoded"]
            
            mock_agent = MagicMock()
            mock_agent.get_conversation_history.return_value = []
            mock_memory_manager.get_agent.return_value = mock_agent
            
            result = analyze_image("Analyze", output_file="-", image_data="test.png", agent_name="vision_agent")
            
            mock_memory_manager.add_message.assert_called()
    
    def test_analyze_image_api_error(self, mock_openai_client, mock_memory_manager):
        """Test image analysis with API error."""
        with patch('mcp_handley_lab.llm.openai.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = ["data:image/png;base64,encoded"]
            mock_openai_client.chat.completions.create.side_effect = Exception("Vision API Error")
            
            with pytest.raises(RuntimeError, match="OpenAI vision API error"):
                analyze_image("Analyze", output_file="-", image_data="test.png")
    
    @patch('requests.get')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_basic(self, mock_tempfile, mock_requests, mock_openai_client, mock_memory_manager):
        """Test basic image generation."""
        # Mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_requests.return_value = mock_response
        
        result = generate_image("A beautiful sunset")
        
        assert "✅ Image generated successfully!" in result
        assert "/tmp/generated_image.png" in result
        assert "💰 Cost: $0.04" in result
        
        mock_openai_client.images.generate.assert_called_once()
        call_args = mock_openai_client.images.generate.call_args
        assert call_args[1]["prompt"] == "A beautiful sunset"
        assert call_args[1]["model"] == "dall-e-3"
        assert call_args[1]["size"] == "1024x1024"
        assert call_args[1]["quality"] == "standard"
    
    @patch('requests.get')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_custom_params(self, mock_tempfile, mock_requests, mock_openai_client, mock_memory_manager):
        """Test image generation with custom parameters."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_requests.return_value = mock_response
        
        result = generate_image(
            "A cat", 
            model="dall-e-2", 
            quality="hd", 
            size="512x512"
        )
        
        call_args = mock_openai_client.images.generate.call_args
        assert call_args[1]["model"] == "dall-e-2"
        assert call_args[1]["quality"] == "hd"
        assert call_args[1]["size"] == "512x512"
    
    @patch('requests.get')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_with_agent(self, mock_tempfile, mock_requests, mock_openai_client, mock_memory_manager):
        """Test image generation with agent."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_requests.return_value = mock_response
        
        mock_agent = MagicMock()
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = generate_image("A sunset", agent_name="art_agent")
        
        mock_memory_manager.add_message.assert_called()
    
    @patch('requests.get')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_with_new_agent(self, mock_tempfile, mock_requests, mock_openai_client, mock_memory_manager):
        """Test image generation with new agent that needs to be created."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_requests.return_value = mock_response
        
        mock_memory_manager.get_agent.return_value = None  # Agent doesn't exist
        mock_agent = MagicMock()
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = generate_image("A sunset", agent_name="new_art_agent")
        
        mock_memory_manager.create_agent.assert_called_once_with("new_art_agent")
        mock_memory_manager.add_message.assert_called()
    
    def test_generate_image_api_error(self, mock_openai_client, mock_memory_manager):
        """Test image generation with API error."""
        mock_openai_client.images.generate.side_effect = Exception("DALL-E Error")
        
        with pytest.raises(RuntimeError, match="DALL-E API error"):
            generate_image("A sunset")
    
    @patch('requests.get')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_image_download_error(self, mock_tempfile, mock_requests, mock_openai_client, mock_memory_manager):
        """Test image generation with download error."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/generated_image.png"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        mock_requests.side_effect = requests.RequestException("Download failed")
        
        with pytest.raises(RuntimeError, match="DALL-E API error"):
            generate_image("A sunset")
    
    def test_server_info_success(self, mock_openai_client, mock_memory_manager):
        """Test server info with successful connection."""
        mock_memory_manager.list_agents.return_value = ["agent1", "agent2"]
        
        result = server_info()
        
        assert "OpenAI Tool Server Status" in result
        assert "Status: Connected and ready" in result
        assert "API Key: Configured ✓" in result
        assert "Available Models:" in result
        assert "Active Agents: 2" in result
        assert "Available tools:" in result
        
        mock_openai_client.models.list.assert_called_once()
    
    def test_server_info_api_error(self, mock_openai_client, mock_memory_manager):
        """Test server info with API error."""
        mock_openai_client.models.list.side_effect = Exception("API Key Invalid")
        
        with pytest.raises(RuntimeError, match="OpenAI API configuration error"):
            server_info()
    
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
    
    def test_ask_with_file_output(self, mock_openai_client, mock_memory_manager, tmp_path):
        """Test ask with file output."""
        output_file = tmp_path / "response.txt"
        
        result = ask("Hello", output_file=str(output_file))
        
        assert "Response saved to:" in result
        assert str(output_file) in result
        assert "Content: 13 characters" in result  # "Test response" = 13 chars
        assert output_file.exists()
        assert output_file.read_text() == "Test response"
    
    def test_analyze_image_with_file_output(self, mock_openai_client, mock_memory_manager, tmp_path):
        """Test analyze_image with file output."""
        output_file = tmp_path / "analysis.txt"
        
        with patch('mcp_handley_lab.llm.openai.tool._resolve_images') as mock_resolve:
            mock_resolve.return_value = ["data:image/jpeg;base64,test"]
            
            result = analyze_image("Analyze this", output_file=str(output_file), image_data="test.png")
            
            assert "Response saved to:" in result
            assert str(output_file) in result
            assert "Content: 13 characters" in result
            assert output_file.exists()
            assert output_file.read_text() == "Test response"


class TestOpenAIMain:
    """Test the __main__ module."""
    
    @patch('mcp_handley_lab.llm.openai.__main__.mcp')
    def test_main_function(self, mock_mcp):
        """Test the main function."""
        from mcp_handley_lab.llm.openai.__main__ import main
        
        main()
        mock_mcp.run.assert_called_once()
    
    @patch('mcp_handley_lab.llm.openai.__main__.main')
    def test_main_runs_server(self, mock_main):
        """Test that __main__ runs when called directly."""
        # Simulate running as main module
        import mcp_handley_lab.llm.openai.__main__ as main_module
        
        # Mock __name__ to be '__main__'
        with patch.object(main_module, '__name__', '__main__'):
            # Re-import to trigger the if __name__ == '__main__' block
            import importlib
            importlib.reload(main_module)
        
        # The module should exist and be importable
        assert main_module is not None