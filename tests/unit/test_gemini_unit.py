"""Unit tests for Gemini LLM tool functionality."""
from unittest.mock import Mock, patch

import pytest

from mcp_handley_lab.llm.gemini.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    analyze_image,
    ask,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    def test_model_configs_all_present(self):
        """Test that all expected models are in MODEL_CONFIGS."""
        expected_models = {
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # Gemini 2.5 models
        assert MODEL_CONFIGS["gemini-2.5-pro"]["output_tokens"] == 65536
        assert MODEL_CONFIGS["gemini-2.5-flash"]["output_tokens"] == 65536
        assert MODEL_CONFIGS["gemini-2.5-flash-lite"]["output_tokens"] == 64000

        # Gemini 2.0 models
        assert MODEL_CONFIGS["gemini-2.0-flash"]["output_tokens"] == 8192
        assert MODEL_CONFIGS["gemini-2.0-flash-lite"]["output_tokens"] == 8192

        # Gemini 1.5 models
        assert MODEL_CONFIGS["gemini-1.5-flash"]["output_tokens"] == 8192
        assert MODEL_CONFIGS["gemini-1.5-flash-8b"]["output_tokens"] == 8192
        assert MODEL_CONFIGS["gemini-1.5-pro"]["output_tokens"] == 8192

    def test_model_configs_input_limits(self):
        """Test that model configurations have correct input limits."""
        # Most models have 1M input tokens
        assert MODEL_CONFIGS["gemini-2.5-flash"]["input_tokens"] == 1048576
        assert MODEL_CONFIGS["gemini-2.0-flash"]["input_tokens"] == 1048576
        assert MODEL_CONFIGS["gemini-1.5-flash"]["input_tokens"] == 1048576

        # Gemini 1.5 Pro has 2M input tokens
        assert MODEL_CONFIGS["gemini-1.5-pro"]["input_tokens"] == 2097152

        # Gemini 2.5 Flash Lite has 1M input tokens
        assert MODEL_CONFIGS["gemini-2.5-flash-lite"]["input_tokens"] == 1000000

    def test_get_model_config_known_models(self):
        """Test _get_model_config with known model names."""
        config = _get_model_config("gemini-2.5-flash")
        assert config["output_tokens"] == 65536
        assert config["input_tokens"] == 1048576

        config = _get_model_config("gemini-1.5-pro")
        assert config["output_tokens"] == 8192
        assert config["input_tokens"] == 2097152

    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to gemini-1.5-flash
        assert config["output_tokens"] == 8192
        assert config["input_tokens"] == 1048576


class TestAskTokenLimits:
    """Test ask function with max_output_tokens parameter."""

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_ask_uses_model_default_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses model's default token limit when max_output_tokens not specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"

        # Call ask with gemini-2.5-flash (should use 65536 tokens)
        result = ask(
            prompt="Test prompt",
            output_file="/tmp/test.txt",
            model="gemini-2.5-flash",
            agent_name=False
        )

        # Verify generate_content was called with correct config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 65536

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_ask_uses_custom_tokens(self, mock_handle_output, mock_client):
        """Test that ask uses custom max_output_tokens when specified."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"

        # Call ask with custom token limit
        result = ask(
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

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_ask_different_model_defaults(self, mock_handle_output, mock_client):
        """Test that ask uses correct defaults for different models."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"

        # Test gemini-1.5-pro (should use 8192 tokens)
        ask(
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

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_analyze_image_uses_model_default_tokens(self, mock_handle_output, mock_resolve_images, mock_client):
        """Test that analyze_image uses model's default token limit."""
        # Setup mocks
        mock_resolve_images.return_value = []
        mock_response = Mock()
        mock_response.text = "Image analysis response"
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_handle_output.return_value = "Response saved"

        # Call analyze_image with default model (pro -> gemini-1.5-pro)
        result = analyze_image(
            prompt="Analyze this image",
            output_file="/tmp/analysis.txt",
            image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            agent_name=False
        )

        # Verify generate_content was called with correct config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs['config']
        assert config.max_output_tokens == 8192  # gemini-1.5-pro default

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    @patch('mcp_handley_lab.llm.gemini.tool._resolve_images')
    @patch('mcp_handley_lab.llm.gemini.tool.handle_output')
    def test_analyze_image_uses_custom_tokens(self, mock_handle_output, mock_resolve_images, mock_client):
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
        result = analyze_image(
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

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_ask_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors."""
        mock_client.models.generate_content.side_effect = Exception("Should not be called")

        # This should not raise a validation error
        try:
            ask(
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

    @patch('mcp_handley_lab.llm.gemini.tool.client')
    def test_analyze_image_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors in analyze_image."""
        mock_client.models.generate_content.side_effect = Exception("Should not be called")

        # This should not raise a validation error
        try:
            analyze_image(
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
