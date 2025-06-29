"""Unit tests for Gemini LLM tool functionality."""
import pytest
import tempfile
import base64
import io
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
from PIL import Image

from mcp_handley_lab.llm.gemini.tool import (
    _get_model_config, MODEL_CONFIGS, ask, analyze_image, generate_image,
    create_agent, list_agents, agent_stats, clear_agent, delete_agent,
    get_response, server_info, _get_session_id, _resolve_files, _resolve_images,
    _handle_agent_and_usage
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""
    
    @pytest.mark.parametrize("model_name,expected_output_tokens", [
        ("gemini-2.5-pro", 65536),
        ("gemini-2.5-flash", 65536),
        ("gemini-2.5-flash-lite", 64000),
        ("gemini-2.0-flash", 8192),
        ("gemini-2.0-flash-lite", 8192),
        ("gemini-1.5-flash", 8192),
        ("gemini-1.5-flash-8b", 8192),
        ("gemini-1.5-pro", 8192),
    ])
    def test_model_output_token_limits_parameterized(self, model_name, expected_output_tokens):
        """Test model output token limits for all models."""
        assert MODEL_CONFIGS[model_name]["output_tokens"] == expected_output_tokens
    
    def test_model_configs_all_present(self):
        """Test that all expected models are in MODEL_CONFIGS."""
        expected_models = {
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-2.0-flash", "gemini-2.0-flash-lite", 
            "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models
    
    
    
    @pytest.mark.parametrize("model_name,expected_output_tokens", [
        ("gemini-2.5-flash", 65536),
        ("gemini-1.5-pro", 8192),
        ("gemini-2.0-flash", 8192),
    ])
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test _get_model_config with various known models."""
        config = _get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens
    
    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to gemini-2.5-flash
        assert config["output_tokens"] == 65536


class TestAskTokenLimits:
    """Test ask function with max_output_tokens parameter."""
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    async def test_ask_uses_model_default_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses model's default token limit when max_output_tokens not specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call ask with gemini-2.5-flash (should use 65536 tokens)
        result = await ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gemini-2.5-flash",
            agent_name=False
        )
        
        # Verify generate_content was called with correct config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 65536
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    async def test_ask_uses_custom_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses custom max_output_tokens when specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call ask with custom token limit
        result = await ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gemini-2.5-flash",
            max_output_tokens=1000,
            agent_name=False
        )
        
        # Verify generate_content was called with custom config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 1000
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    async def test_ask_different_model_defaults(self, mock_handle_output, mock_client):
        """Test that ask uses correct defaults for different models."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Test gemini-1.5-pro (should use 8192 tokens)
        await ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gemini-1.5-pro",
            agent_name=False
        )
        
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 8192


class TestAnalyzeImageTokenLimits:
    """Test analyze_image function with max_output_tokens parameter."""
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    async def test_analyze_image_uses_model_default_tokens(self, mock_handle_output, mock_resolve_images, mock_client):
        """Test that analyze_image uses model's default token limit."""
        # Setup mocks
        mock_resolve_images.return_value = []
        mock_response = Mock()
        mock_response.text = "Image analysis response"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call analyze_image with default model (gemini-2.5-pro)
        result = await analyze_image(
            prompt="Analyze this image",
            output_file="/tmp/analysis.txt",
            image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            agent_name=False
        )
        
        # Verify generate_content was called with correct config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 65536  # gemini-2.5-pro default
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    async def test_analyze_image_uses_custom_tokens(self, mock_handle_output, mock_resolve_images, mock_client):
        """Test that analyze_image uses custom max_output_tokens when specified."""
        # Setup mocks
        mock_resolve_images.return_value = []
        mock_response = Mock()
        mock_response.text = "Image analysis response"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"
        
        # Call analyze_image with custom token limit
        result = await analyze_image(
            prompt="Analyze this image",
            output_file="/tmp/analysis.txt",
            image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            max_output_tokens=2000,
            agent_name=False
        )
        
        # Verify generate_content was called with custom config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 2000


class TestInputValidation:
    """Test input validation for token limits and boolean handling."""
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    async def test_ask_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors."""
        mock_client.models.generate_content.side_effect = Exception("Should not be called")
        
        # This should not raise a validation error
        try:
            await ask(
                prompt="Test",
                output_file="/tmp/test.txt",
                agent_name=False
            )
        except ValueError as e:
            if "strip" in str(e):
                pytest.fail("agent_name=False should not cause strip() validation error")
        except Exception:
            # Other exceptions are expected (like the mock exception)
            pass
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.client')
    async def test_analyze_image_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors in analyze_image."""
        mock_client.models.generate_content.side_effect = Exception("Should not be called")
        
        # This should not raise a validation error
        try:
            await analyze_image(
                prompt="Test",
                output_file="/tmp/test.txt",
                image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
                agent_name=False
            )
        except ValueError as e:
            if "strip" in str(e):
                pytest.fail("agent_name=False should not cause strip() validation error")
        except Exception:
            # Other exceptions are expected (like the mock exception)
            pass


class TestErrorHandling:
    """Test error handling scenarios for coverage."""
    
    @patch('mcp_handley_lab.llm.gemini.tool.settings')
    @patch('mcp_handley_lab.llm.gemini.tool.google_genai.Client')
    def test_client_initialization_error(self, mock_client_class, mock_settings):
        """Test client initialization error handling (lines 32-34)."""
        # Force the initialization to fail
        mock_settings.gemini_api_key = 'test_key'
        mock_client_class.side_effect = Exception("API key invalid")
        
        # Import the module to trigger initialization
        import importlib
        import mcp_handley_lab.llm.gemini.tool
        importlib.reload(mcp_handley_lab.llm.gemini.tool)
        
        # The module should load but client should be None
        assert mcp_handley_lab.llm.gemini.tool.client is None
        assert mcp_handley_lab.llm.gemini.tool.initialization_error == "API key invalid"
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.llm.gemini.tool.is_text_file')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_text')
    async def test_resolve_files_read_error(self, mock_read_text, mock_stat, mock_exists, mock_is_text):
        """Test file reading error in _resolve_files (lines 127-131)."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_files
        
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 100  # Small file
        mock_is_text.return_value = True
        # Make read_text fail
        mock_read_text.side_effect = Exception("Permission denied")
        
        files = [{"path": "/tmp/test.txt"}]
        parts = await _resolve_files(files)
        
        # Should have error message part
        assert len(parts) == 1
        assert "Error reading file" in parts[0].text
        assert "Permission denied" in parts[0].text
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.exists')
    async def test_resolve_files_processing_error(self, mock_exists):
        """Test file processing error in _resolve_files (lines 130-131)."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_files
        
        # Make the path check itself fail
        mock_exists.side_effect = Exception("Invalid path")
        
        files = [{"path": "/invalid/path"}]
        parts = await _resolve_files(files)
        
        # Should have error message part
        assert len(parts) == 1
        assert "Error processing file /invalid/path: Invalid path" in parts[0].text
    
    @patch('pathlib.Path.read_bytes')
    @patch('PIL.Image.open')
    def test_resolve_images_load_error(self, mock_image_open, mock_read_bytes):
        """Test image loading error in _resolve_images (lines 161-162)."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_images
        
        # Return valid bytes but make PIL.Image.open fail
        mock_read_bytes.return_value = b"some image data"
        mock_image_open.side_effect = Exception("Invalid image format")
        
        with pytest.raises(ValueError, match="Failed to load image"):
            _resolve_images(images=[{"path": "/tmp/invalid.jpg"}])
    
    @pytest.mark.asyncio
    async def test_analyze_image_output_file_validation(self):
        """Test output file validation in analyze_image (line 485)."""
        from mcp_handley_lab.llm.gemini.tool import analyze_image
        
        # Test with whitespace-only output file
        with pytest.raises(ValueError, match="Output file is required"):
            await analyze_image(
                prompt="Test",
                output_file="   ",  # Whitespace only
                image_data="data:image/png;base64,test"
            )