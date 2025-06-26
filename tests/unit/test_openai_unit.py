"""Unit tests for OpenAI LLM module."""
import pytest
import tempfile
import json
import base64
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from PIL import Image
import io

from mcp_handley_lab.llm.openai.tool import (
    ask, analyze_image, generate_image, get_response, server_info,
    _resolve_files, _resolve_images, _handle_agent_and_usage,
    _get_model_config, MODEL_CONFIGS
)
from mcp_handley_lab.llm.common import determine_mime_type, is_text_file


class TestOpenAIModelConfiguration:
    """Test OpenAI model configuration and token limit functionality."""
    
    def test_model_configs_all_present(self):
        """Test that all expected OpenAI models are in MODEL_CONFIGS."""
        expected_models = {
            "o3-mini", "o1-preview", "o1-mini",
            "gpt-4o", "gpt-4o-mini", "gpt-4o-2024-11-20", "gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18",
            "gpt-4.1", "gpt-4.1-mini"
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models
    
    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # O3 series
        assert MODEL_CONFIGS["o3-mini"]["output_tokens"] == 100000
        
        # O1 series 
        assert MODEL_CONFIGS["o1-preview"]["output_tokens"] == 32768
        assert MODEL_CONFIGS["o1-mini"]["output_tokens"] == 65536
        
        # GPT-4o series
        assert MODEL_CONFIGS["gpt-4o"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["gpt-4o-mini"]["output_tokens"] == 16384
        
        # GPT-4.1 series
        assert MODEL_CONFIGS["gpt-4.1"]["output_tokens"] == 32768
        assert MODEL_CONFIGS["gpt-4.1-mini"]["output_tokens"] == 16384
    
    def test_model_configs_param_names(self):
        """Test that model configurations use correct parameter names."""
        # O1/O3 series use max_completion_tokens
        assert MODEL_CONFIGS["o3-mini"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-preview"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-mini"]["param"] == "max_completion_tokens"
        
        # GPT-4o series use max_tokens
        assert MODEL_CONFIGS["gpt-4o"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4o-mini"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4.1"]["param"] == "max_tokens"
    
    def test_get_model_config_known_models(self):
        """Test _get_model_config with known model names."""
        config = _get_model_config("o3-mini")
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_completion_tokens"
        
        config = _get_model_config("gpt-4o")
        assert config["output_tokens"] == 16384
        assert config["param"] == "max_tokens"
    
    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to gpt-4o
        assert config["output_tokens"] == 16384
        assert config["param"] == "max_tokens"


class TestOpenAIHelperFunctions:
    """Test helper functions that don't require API calls."""
    
    def testdetermine_mime_type_text(self):
        """Test MIME type detection for text files."""
        # Test common text file extensions
        assert determine_mime_type(Path("test.txt")) == "text/plain"
        assert determine_mime_type(Path("test.py")) == "text/x-python"
        assert determine_mime_type(Path("test.js")) == "text/javascript"
        assert determine_mime_type(Path("test.json")) == "application/json"
        
    def testdetermine_mime_type_images(self):
        """Test MIME type detection for image files."""
        assert determine_mime_type(Path("test.jpg")) == "image/jpeg"
        assert determine_mime_type(Path("test.png")) == "image/png"
        assert determine_mime_type(Path("test.gif")) == "image/gif"
        assert determine_mime_type(Path("test.webp")) == "image/webp"
        
    def testdetermine_mime_type_unknown(self):
        """Test MIME type detection for unknown extensions."""
        assert determine_mime_type(Path("test.unknown")) == "application/octet-stream"
        assert determine_mime_type(Path("no_extension")) == "application/octet-stream"
    
    def testis_text_file_true(self):
        """Test text file detection for text files."""
        assert is_text_file(Path("test.txt")) is True
        assert is_text_file(Path("test.py")) is True
        assert is_text_file(Path("test.md")) is True
        assert is_text_file(Path("test.json")) is True
        
    def testis_text_file_false(self):
        """Test text file detection for binary files."""
        assert is_text_file(Path("test.jpg")) is False
        assert is_text_file(Path("test.png")) is False
        assert is_text_file(Path("test.pdf")) is False
        assert is_text_file(Path("test.exe")) is False


class TestResolveFiles:
    """Test file resolution logic."""
    
    def test_resolve_files_none(self):
        """Test resolve_files with None input."""
        file_attachments, inline_content = _resolve_files(None)
        assert file_attachments == []
        assert inline_content == []
        
    def test_resolve_files_empty_list(self):
        """Test resolve_files with empty list."""
        file_attachments, inline_content = _resolve_files([])
        assert file_attachments == []
        assert inline_content == []
        
    def test_resolve_files_direct_string(self):
        """Test resolve_files with direct string content."""
        files = ["This is direct content", "More content"]
        file_attachments, inline_content = _resolve_files(files)
        assert file_attachments == []
        assert inline_content == ["This is direct content", "More content"]
        
    def test_resolve_files_dict_content(self):
        """Test resolve_files with dict content."""
        files = [{"content": "Dict content"}, {"content": "More dict content"}]
        file_attachments, inline_content = _resolve_files(files)
        assert file_attachments == []
        assert inline_content == ["Dict content", "More dict content"]
        
    def test_resolve_files_small_text_file(self):
        """Test resolve_files with small text file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Small text file content")
            temp_path = f.name
            
        try:
            files = [{"path": temp_path}]
            file_attachments, inline_content = _resolve_files(files)
            
            assert file_attachments == []
            assert len(inline_content) == 1
            assert "Small text file content" in inline_content[0]
            assert Path(temp_path).name in inline_content[0]  # Should include filename header
        finally:
            Path(temp_path).unlink()


class TestResolveImages:
    """Test image resolution for vision models."""
    
    def test_resolve_images_none(self):
        """Test resolve_images with None input."""
        images = _resolve_images()
        assert images == []
        
    def test_resolve_images_direct_data_url(self):
        """Test resolve_images with data URL."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        resolved_images = _resolve_images(image_data=data_url)
        
        assert len(resolved_images) == 1
        assert resolved_images[0] == data_url
        
    def test_resolve_images_dict_data(self):
        """Test resolve_images with dict containing base64 data."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        images = [{"data": base64_data}]
        resolved_images = _resolve_images(images=images)
        
        assert len(resolved_images) == 1
        assert "data:image/jpeg;base64," in resolved_images[0]  # Function defaults to JPEG for dict data


class TestInputValidation:
    """Test input validation for main functions."""
    
    def test_ask_empty_prompt(self):
        """Test ask with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            ask("", "/tmp/output.txt")
            
    def test_ask_empty_output_file(self):
        """Test ask with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            ask("Test prompt", "")
            
    def test_ask_empty_agent_name(self):
        """Test ask with empty agent name."""
        with pytest.raises(ValueError, match="Agent name cannot be empty when provided"):
            ask("Test prompt", "/tmp/output.txt", agent_name="")
            
    def test_analyze_image_empty_prompt(self):
        """Test analyze_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            analyze_image("", "/tmp/output.txt")
            
    def test_analyze_image_empty_output_file(self):
        """Test analyze_image with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            analyze_image("Test prompt", "")
            
    def test_generate_image_empty_prompt(self):
        """Test generate_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            generate_image("")
            
    def test_get_response_nonexistent_agent(self, mock_memory_manager):
        """Test get_response with nonexistent agent."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = None
        
        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            get_response("nonexistent")


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('mcp_handley_lab.llm.openai.tool.client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_memory_manager():
    """Mock memory manager for testing."""
    with patch('mcp_handley_lab.llm.openai.tool.memory_manager') as mock_manager:
        yield mock_manager


class TestOpenAIApiCalls:
    """Test main functions with mocked API calls."""
    
    def test_ask_basic_success(self, mock_openai_client, mock_memory_manager, temp_storage_dir):
        """Test basic ask function with successful API call."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 100
        mock_response.model = "gpt-4o"
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Mock memory manager
        mock_memory_manager.get_agent.return_value = None
        
        # Mock calculate_cost and handle_agent_and_usage functions
        with patch('mcp_handley_lab.llm.openai.tool.calculate_cost', return_value=0.001), \
             patch('mcp_handley_lab.llm.openai.tool._handle_agent_and_usage', return_value="Response saved successfully"):
            
            output_file = Path(temp_storage_dir) / "output.txt"
            result = ask("Test prompt", str(output_file))
            
            # Verify API was called
            mock_openai_client.chat.completions.create.assert_called_once()
            
            # Verify result message
            assert "Response saved successfully" in result
        
    def test_ask_with_agent(self, mock_openai_client, mock_memory_manager, temp_storage_dir):
        """Test ask function with agent memory."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Agent response"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 75
        mock_response.usage.completion_tokens = 75
        mock_response.usage.total_tokens = 150
        mock_response.model = "gpt-4o"
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Mock agent with conversation history
        mock_agent = Mock()
        mock_agent.get_openai_conversation_history.return_value = [
            {"role": "user", "content": "Previous message"}
        ]
        mock_memory_manager.get_agent.return_value = mock_agent
        
        # Mock calculate_cost and handle_agent_and_usage
        with patch('mcp_handley_lab.llm.openai.tool.calculate_cost', return_value=0.002), \
             patch('mcp_handley_lab.llm.openai.tool._handle_agent_and_usage', return_value="Response saved successfully"):
            
            output_file = Path(temp_storage_dir) / "output.txt"
            result = ask("New prompt", str(output_file), agent_name="test_agent")
            
            # Verify agent history was used
            mock_agent.get_openai_conversation_history.assert_called_once()
            
            # Verify result contains success message
            assert "Response saved successfully" in result
        
    def test_generate_image_success(self, mock_openai_client, temp_storage_dir):
        """Test generate_image with successful API call."""
        # Mock DALL-E response
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].url = "https://example.com/generated_image.png"
        mock_openai_client.images.generate.return_value = mock_response
        
        # Mock image download
        mock_image_data = b"fake_image_data"
        with patch('requests.get') as mock_get:
            mock_get.return_value.content = mock_image_data
            
            result = generate_image("A beautiful sunset")
            
            # Verify API was called
            mock_openai_client.images.generate.assert_called_once()
            call_args = mock_openai_client.images.generate.call_args[1]
            assert call_args['prompt'] == "A beautiful sunset"
            assert call_args['model'] == "dall-e-3"  # default
            
            # Verify result contains file path
            assert "Image generated successfully!" in result
            assert "Saved to:" in result
            
    def test_analyze_image_success(self, mock_openai_client, mock_memory_manager, temp_storage_dir):
        """Test analyze_image with successful API call."""
        # Mock GPT-4 Vision response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Image analysis result"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 200
        mock_response.model = "gpt-4o"
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Mock memory manager
        mock_memory_manager.get_agent.return_value = None
        
        # Create a small test image
        img = Image.new('RGB', (10, 10), color='red')
        img_path = Path(temp_storage_dir) / "test.png"
        img.save(img_path)
        
        with patch('mcp_handley_lab.llm.openai.tool.calculate_cost', return_value=0.003), \
             patch('mcp_handley_lab.llm.openai.tool._handle_agent_and_usage', return_value="Analysis saved successfully"):
            
            output_file = Path(temp_storage_dir) / "analysis.txt"
            result = analyze_image("Describe this image", str(output_file), image_data=str(img_path))
            
            # Verify API was called with image
            mock_openai_client.chat.completions.create.assert_called_once()
            call_args = mock_openai_client.chat.completions.create.call_args[1]
            assert call_args['model'] == "gpt-4o"
            assert any(msg['role'] == 'user' for msg in call_args['messages'])
            
            # Verify result contains success message
            assert "Analysis saved successfully" in result


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_ask_api_error(self, mock_openai_client, temp_storage_dir):
        """Test ask function with API error."""
        # Mock API error
        from openai import OpenAIError
        mock_openai_client.chat.completions.create.side_effect = OpenAIError("API Error")
        
        output_file = Path(temp_storage_dir) / "output.txt"
        
        with pytest.raises(RuntimeError, match="OpenAI API error"):
            ask("Test prompt", str(output_file))

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_ask_uses_model_default_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses model's default token limit when max_output_tokens not specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call ask with o3-mini (should use 100,000 tokens)
        ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="o3-mini",
            agent_name=None
        )
        
        # Verify API was called with max_completion_tokens (not max_tokens)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_completion_tokens"] == 100000
        assert "max_tokens" not in call_kwargs

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_ask_uses_custom_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses custom max_output_tokens when specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call ask with custom token limit
        ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gpt-4o",
            max_output_tokens=1000,
            agent_name=None
        )
        
        # Verify API was called with custom max_tokens
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1000

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_ask_different_param_names(self, mock_handle_output, mock_client):
        """Test that ask uses correct parameter names for different model types."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Test gpt-4o (uses max_tokens)
        ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gpt-4o",
            agent_name=None
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "max_tokens" in call_kwargs
        assert call_kwargs["max_tokens"] == 16384
        
        # Test o1-preview (uses max_completion_tokens)
        ask(
            prompt="Test prompt", 
            output_file="/tmp/test.txt",
            model="o1-preview",
            agent_name=None
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "max_completion_tokens" in call_kwargs
        assert call_kwargs["max_completion_tokens"] == 32768
        assert "max_tokens" not in call_kwargs

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_analyze_image_uses_model_default_tokens(self, mock_handle_output, mock_client):
        """Test that analyze_image uses model's default token limit when max_output_tokens not specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Image analysis"
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Analysis saved"
        
        # Call analyze_image with gpt-4o (should use 16384 tokens)
        analyze_image(
            prompt="Describe this image",
            output_file="/tmp/test.txt",
            image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            model="gpt-4o",
            agent_name=None
        )
        
        # Verify API was called with max_tokens (not max_completion_tokens)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 16384
        assert "max_completion_tokens" not in call_kwargs

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_analyze_image_uses_custom_tokens(self, mock_handle_output, mock_client):
        """Test that analyze_image uses custom max_output_tokens when specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Custom analysis"
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Analysis saved"
        
        # Call analyze_image with custom token limit
        analyze_image(
            prompt="Describe this image",
            output_file="/tmp/test.txt",
            image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            model="gpt-4o",
            max_output_tokens=500,
            agent_name=None
        )
        
        # Verify API was called with custom max_tokens
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 500

    @patch('mcp_handley_lab.llm.openai.tool.client')
    @patch('mcp_handley_lab.llm.openai.tool.handle_output')
    def test_analyze_image_different_param_names(self, mock_handle_output, mock_client):
        """Test that analyze_image uses correct parameter names for different model types."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test analysis"
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response
        mock_handle_output.return_value = "Analysis saved"
        
        base64_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        # Test gpt-4o (uses max_tokens)
        analyze_image(
            prompt="Describe image",
            output_file="/tmp/test.txt",
            image_data=base64_image,
            model="gpt-4o",
            agent_name=None
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "max_tokens" in call_kwargs
        assert call_kwargs["max_tokens"] == 16384
        
        # Test o1-preview (uses max_completion_tokens) - though o1 models don't support vision
        # This tests the parameter selection logic
        analyze_image(
            prompt="Describe image", 
            output_file="/tmp/test.txt",
            image_data=base64_image,
            model="o1-preview",
            agent_name=None
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "max_completion_tokens" in call_kwargs
        assert call_kwargs["max_completion_tokens"] == 32768
        assert "max_tokens" not in call_kwargs
            
    def test_generate_image_invalid_model(self, mock_openai_client):
        """Test generate_image with invalid model parameters."""
        # DALL-E 2 doesn't support quality parameter
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].url = "https://example.com/image.png"
        mock_openai_client.images.generate.return_value = mock_response
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.content = b"fake_image"
            
            result = generate_image("Test prompt", model="dall-e-2", quality="hd")
            
            # Should call API without quality parameter for DALL-E 2
            call_args = mock_openai_client.images.generate.call_args[1]
            assert "quality" not in call_args
            assert call_args['model'] == "dall-e-2"


class TestServerInfo:
    """Test server_info function."""
    
    def test_server_info_basic(self, mock_openai_client, mock_memory_manager):
        """Test server_info returns basic information."""
        # Mock API response with proper structure
        mock_models_response = Mock()
        mock_models_response.data = [
            Mock(id="gpt-4o"),
            Mock(id="gpt-4o-mini"),
            Mock(id="dall-e-3")
        ]
        mock_openai_client.models.list.return_value = mock_models_response
        
        # Mock agent list
        mock_memory_manager.list_agents.return_value = []
        mock_memory_manager.storage_dir = "/tmp/test"
        
        result = server_info()
        
        assert "OpenAI Tool Server Status" in result
        assert "Status: Connected and ready" in result
        assert "Available Models:" in result
        assert "Active Agents: 0" in result
        
    def test_server_info_with_agents(self, mock_openai_client, mock_memory_manager):
        """Test server_info with existing agents."""
        # Mock API response with proper structure
        mock_models_response = Mock()
        mock_models_response.data = [Mock(id="gpt-4o")]
        mock_openai_client.models.list.return_value = mock_models_response
        
        # Mock agents
        mock_agent = Mock()
        mock_memory_manager.list_agents.return_value = [mock_agent]
        mock_memory_manager.storage_dir = "/tmp/test"
        
        result = server_info()
        
        assert "Active Agents: 1" in result