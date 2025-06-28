"""Unit tests for LLM common utilities."""
import pytest
import base64
import os
import time
from pathlib import Path
from unittest.mock import patch, Mock, mock_open
from PIL import Image
import io

from mcp_handley_lab.llm.common import (
    get_session_id, determine_mime_type, is_text_file, resolve_file_content,
    read_file_smart, resolve_image_data, handle_output, handle_agent_memory
)


class TestGetSessionId:
    """Test session ID generation."""
    
    def test_get_session_id_with_valid_context(self):
        """Test session ID with valid MCP context."""
        mock_mcp = Mock()
        mock_context = Mock()
        mock_context.client_id = "test_client_123"
        mock_mcp.get_context.return_value = mock_context
        
        result = get_session_id(mock_mcp)
        assert result == "_session_test_client_123"
    
    def test_get_session_id_no_client_id(self):
        """Test session ID when context has no client_id."""
        mock_mcp = Mock()
        mock_context = Mock()
        mock_context.client_id = None
        mock_mcp.get_context.return_value = mock_context
        
        with patch('os.getpid', return_value=12345), \
             patch('time.time', return_value=1640995200):
            result = get_session_id(mock_mcp)
            assert result == "_session_12345_1640995200"
    
    def test_get_session_id_exception_fallback(self):
        """Test session ID fallback when context access fails."""
        mock_mcp = Mock()
        mock_mcp.get_context.side_effect = Exception("Context error")
        
        with patch('os.getpid', return_value=12345), \
             patch('time.time', return_value=1640995200):
            result = get_session_id(mock_mcp)
            assert result == "_session_12345_1640995200"


class TestDetermineMimeType:
    """Test MIME type detection."""
    
    @pytest.mark.parametrize("file_path,expected_mime", [
        ("test.txt", "text/plain"),
        ("test.md", "text/markdown"),
        ("test.py", "text/x-python"),
        ("test.js", "text/javascript"),
        ("test.html", "text/html"),
        ("test.css", "text/css"),
        ("test.json", "application/json"),
        ("test.xml", "application/xml"),
        ("test.csv", "text/csv"),
        ("test.pdf", "application/pdf"),
        ("test.png", "image/png"),
        ("test.jpg", "image/jpeg"),
        ("test.jpeg", "image/jpeg"),
        ("test.gif", "image/gif"),
        ("test.webp", "image/webp"),
    ])
    def test_determine_mime_type_known_extensions(self, file_path, expected_mime):
        """Test MIME type detection for known extensions."""
        result = determine_mime_type(Path(file_path))
        assert result == expected_mime
    
    def test_determine_mime_type_case_insensitive(self):
        """Test MIME type detection is case insensitive."""
        assert determine_mime_type(Path("test.TXT")) == "text/plain"
        assert determine_mime_type(Path("test.PNG")) == "image/png"
    
    def test_determine_mime_type_unknown_extension(self):
        """Test MIME type detection for unknown extensions."""
        assert determine_mime_type(Path("test.unknown")) == "application/octet-stream"
        assert determine_mime_type(Path("no_extension")) == "application/octet-stream"


class TestIsTextFile:
    """Test text file detection."""
    
    @pytest.mark.parametrize("file_path,expected", [
        ("test.txt", True),
        ("test.md", True),
        ("test.py", True),
        ("test.js", True),
        ("test.html", True),
        ("test.css", True),
        ("test.json", True),
        ("test.xml", True),
        ("test.csv", True),
        ("test.yaml", True),
        ("test.yml", True),
        ("test.toml", True),
        ("test.ini", True),
        ("test.conf", True),
        ("test.log", True),
        ("test.png", False),
        ("test.jpg", False),
        ("test.pdf", False),
        ("test.exe", False),
        ("test.unknown", False),
    ])
    def test_is_text_file(self, file_path, expected):
        """Test text file detection for various extensions."""
        result = is_text_file(Path(file_path))
        assert result == expected
    
    def test_is_text_file_case_insensitive(self):
        """Test text file detection is case insensitive."""
        assert is_text_file(Path("test.TXT")) is True
        assert is_text_file(Path("test.PNG")) is False


class TestResolveFileContent:
    """Test file content resolution."""
    
    def test_resolve_file_content_direct_string(self):
        """Test resolving direct string content."""
        content, path = resolve_file_content("Direct string content")
        assert content == "Direct string content"
        assert path is None
    
    def test_resolve_file_content_dict_with_content(self):
        """Test resolving dict with content key."""
        content, path = resolve_file_content({"content": "Dict content"})
        assert content == "Dict content"
        assert path is None
    
    @patch('pathlib.Path.exists')
    def test_resolve_file_content_dict_with_existing_path(self, mock_exists):
        """Test resolving dict with existing file path."""
        mock_exists.return_value = True
        
        content, path = resolve_file_content({"path": "/tmp/test.txt"})
        assert content is None
        assert path == Path("/tmp/test.txt")
    
    @patch('pathlib.Path.exists')
    def test_resolve_file_content_dict_with_nonexistent_path(self, mock_exists):
        """Test resolving dict with non-existent file path."""
        mock_exists.return_value = False
        
        content, path = resolve_file_content({"path": "/tmp/nonexistent.txt"})
        assert "Error: File not found" in content
        assert path is None
    
    def test_resolve_file_content_invalid_input(self):
        """Test resolving invalid input types."""
        content, path = resolve_file_content({"invalid": "key"})
        assert content is None
        assert path is None
        
        content, path = resolve_file_content(123)  # Invalid type
        assert content is None
        assert path is None


class TestReadFileSmart:
    """Test smart file reading."""
    
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    def test_read_file_smart_text_file(self, mock_read_text, mock_stat):
        """Test reading a text file."""
        mock_stat.return_value.st_size = 100
        mock_read_text.return_value = "Test content"
        
        content, is_text = read_file_smart(Path("test.txt"))
        assert content == "[File: test.txt]\nTest content"
        assert is_text is True
    
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.read_bytes')
    def test_read_file_smart_text_file_unicode_error(self, mock_read_bytes, mock_read_text, mock_stat):
        """Test reading text file that has Unicode decode error."""
        mock_stat.return_value.st_size = 100
        mock_read_text.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        mock_read_bytes.return_value = b'\x00\x01\x02'
        
        content, is_text = read_file_smart(Path("test.txt"))
        assert "[Binary file:" in content
        assert "test.txt" in content
        assert "100 bytes" in content
        assert is_text is False
    
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_bytes')
    def test_read_file_smart_binary_file(self, mock_read_bytes, mock_stat):
        """Test reading a binary file."""
        mock_stat.return_value.st_size = 100
        mock_read_bytes.return_value = b'\x00\x01\x02'
        
        content, is_text = read_file_smart(Path("test.bin"))
        assert "[Binary file:" in content
        assert "test.bin" in content
        assert "application/octet-stream" in content
        assert "100 bytes" in content
        assert is_text is False
    
    @patch('pathlib.Path.stat')
    def test_read_file_smart_large_file(self, mock_stat):
        """Test reading file that exceeds size limit."""
        mock_stat.return_value.st_size = 30 * 1024 * 1024  # 30MB
        
        with pytest.raises(ValueError, match="File too large"):
            read_file_smart(Path("large.txt"))
    
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    def test_read_file_smart_custom_max_size(self, mock_read_text, mock_stat):
        """Test reading with custom max size."""
        mock_stat.return_value.st_size = 1000
        mock_read_text.return_value = "Test content"
        
        # Should work with higher limit
        content, is_text = read_file_smart(Path("test.txt"), max_size=2000)
        assert is_text is True
        
        # Should fail with lower limit
        with pytest.raises(ValueError, match="File too large"):
            read_file_smart(Path("test.txt"), max_size=500)


class TestResolveImageData:
    """Test image data resolution."""
    
    def test_resolve_image_data_data_url(self):
        """Test resolving data URL format."""
        # Simple red pixel PNG
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        data_url = f"data:image/png;base64,{base64_data}"
        
        result = resolve_image_data(data_url)
        expected = base64.b64decode(base64_data)
        assert result == expected
    
    @patch('pathlib.Path.read_bytes')
    def test_resolve_image_data_file_path_string(self, mock_read_bytes):
        """Test resolving file path as string."""
        mock_read_bytes.return_value = b"image_data"
        
        result = resolve_image_data("/path/to/image.png")
        assert result == b"image_data"
    
    def test_resolve_image_data_dict_with_data(self):
        """Test resolving dict with base64 data."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        result = resolve_image_data({"data": base64_data})
        expected = base64.b64decode(base64_data)
        assert result == expected
    
    @patch('pathlib.Path.read_bytes')
    def test_resolve_image_data_dict_with_path(self, mock_read_bytes):
        """Test resolving dict with file path."""
        mock_read_bytes.return_value = b"image_data"
        
        result = resolve_image_data({"path": "/path/to/image.png"})
        assert result == b"image_data"
    
    def test_resolve_image_data_invalid_format(self):
        """Test resolving invalid image format."""
        with pytest.raises(ValueError, match="Invalid image format"):
            resolve_image_data({"invalid": "format"})
        
        with pytest.raises(ValueError, match="Invalid image format"):
            resolve_image_data(123)


class TestHandleOutput:
    """Test output handling."""
    
    @patch('pathlib.Path.write_text')
    def test_handle_output_to_file(self, mock_write_text):
        """Test output to file."""
        with patch('mcp_handley_lab.common.pricing.format_usage', return_value="Usage: $0.001"):
            result = handle_output(
                response_text="Test response",
                output_file="/tmp/test.txt",
                model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                cost=0.001,
                provider="openai"
            )
        
        mock_write_text.assert_called_once_with("Test response")
        assert "Response saved to: /tmp/test.txt" in result
        assert "Content: 13 characters, 1 lines" in result
        assert "Usage: $0.001" in result
    
    def test_handle_output_to_stdout(self):
        """Test output to stdout."""
        with patch('mcp_handley_lab.common.pricing.format_usage', return_value="Usage: $0.001"):
            result = handle_output(
                response_text="Test response",
                output_file="-",
                model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                cost=0.001,
                provider="openai"
            )
        
        assert result == "Test response\n\nUsage: $0.001"


class TestHandleAgentMemory:
    """Test agent memory handling."""
    
    @patch('mcp_handley_lab.llm.common.memory_manager')
    def test_handle_agent_memory_with_named_agent(self, mock_memory_manager):
        """Test memory handling with named agent."""
        mock_agent = Mock()
        mock_memory_manager.get_agent.return_value = mock_agent
        
        result = handle_agent_memory(
            agent_name="test_agent",
            user_prompt="Test prompt",
            response_text="Test response",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            session_id_func=lambda: "session_123"
        )
        
        assert result == "test_agent"
        mock_memory_manager.add_message.assert_any_call("test_agent", "user", "Test prompt", 100, 0.0005)
        mock_memory_manager.add_message.assert_any_call("test_agent", "assistant", "Test response", 50, 0.0005)
    
    @patch('mcp_handley_lab.llm.common.memory_manager')
    def test_handle_agent_memory_create_new_agent(self, mock_memory_manager):
        """Test memory handling when agent needs to be created."""
        mock_memory_manager.get_agent.return_value = None
        mock_agent = Mock()
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = handle_agent_memory(
            agent_name="new_agent",
            user_prompt="Test prompt",
            response_text="Test response",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            session_id_func=lambda: "session_123"
        )
        
        assert result == "new_agent"
        mock_memory_manager.create_agent.assert_called_once_with("new_agent")
    
    @patch('mcp_handley_lab.llm.common.memory_manager')
    def test_handle_agent_memory_session_fallback(self, mock_memory_manager):
        """Test memory handling with session fallback when no agent name."""
        mock_agent = Mock()
        mock_memory_manager.get_agent.return_value = None
        mock_memory_manager.create_agent.return_value = mock_agent
        
        result = handle_agent_memory(
            agent_name=None,
            user_prompt="Test prompt",
            response_text="Test response",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            session_id_func=lambda: "session_123"
        )
        
        assert result == "session_123"
        mock_memory_manager.create_agent.assert_called_once_with("session_123")
    
    def test_handle_agent_memory_disabled(self):
        """Test memory handling when disabled."""
        result = handle_agent_memory(
            agent_name=False,
            user_prompt="Test prompt",
            response_text="Test response",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
            session_id_func=lambda: "session_123"
        )
        
        assert result is None