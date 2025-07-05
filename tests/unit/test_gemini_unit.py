"""Unit tests for Gemini LLM tool functionality."""
from unittest.mock import patch

import pytest
from mcp_handley_lab.llm.gemini.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    analyze_image,
    ask,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-2.5-pro", 65536),
            ("gemini-2.5-flash", 65536),
            ("gemini-2.5-flash-lite", 64000),
            ("gemini-1.5-flash", 8192),
            ("gemini-1.5-flash-8b", 8192),
            ("gemini-1.5-pro", 8192),
        ],
    )
    def test_model_output_token_limits_parameterized(
        self, model_name, expected_output_tokens
    ):
        """Test model output token limits for all models."""
        assert MODEL_CONFIGS[model_name]["output_tokens"] == expected_output_tokens

    def test_model_configs_all_present(self):
        """Test that all expected models are in MODEL_CONFIGS."""
        expected_models = {
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
            "imagen-4",
            "imagen-4-ultra",
            "imagen-3",
            "veo-2",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-2.5-flash", 65536),
            ("gemini-1.5-pro", 8192),
        ],
    )
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test _get_model_config with various known models."""
        config = _get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens

    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to gemini-2.5-flash
        assert config["output_tokens"] == 65536


class TestInputValidation:
    """Test input validation for token limits and boolean handling."""

    @patch("mcp_handley_lab.llm.gemini.tool.client")
    def test_ask_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors."""
        mock_client.models.generate_content.side_effect = Exception(
            "Should not be called"
        )

        # This should not raise a validation error
        try:
            ask(prompt="Test", output_file="/tmp/test.txt", agent_name=False)
        except ValueError as e:
            if "strip" in str(e):
                pytest.fail(
                    "agent_name=False should not cause strip() validation error"
                )
        except Exception:
            # Other exceptions are expected (like the mock exception)
            pass

    @patch("mcp_handley_lab.llm.gemini.tool.client")
    def test_analyze_image_agent_name_false_validation(self, mock_client):
        """Test that agent_name=False doesn't cause validation errors in analyze_image."""
        mock_client.models.generate_content.side_effect = Exception(
            "Should not be called"
        )

        # This should not raise a validation error
        try:
            analyze_image(
                prompt="Test",
                output_file="/tmp/test.txt",
                image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
                agent_name=False,
            )
        except ValueError as e:
            if "strip" in str(e):
                pytest.fail(
                    "agent_name=False should not cause strip() validation error"
                )
        except Exception:
            # Other exceptions are expected (like the mock exception)
            pass


class TestErrorHandling:
    """Test error handling scenarios for coverage."""

    @patch("mcp_handley_lab.llm.gemini.tool.settings")
    @patch("mcp_handley_lab.llm.gemini.tool.google_genai.Client")
    def test_client_initialization_error(self, mock_client_class, mock_settings):
        """Test client initialization error handling - should raise exception."""
        # Force the initialization to fail
        mock_settings.gemini_api_key = "test_key"
        mock_client_class.side_effect = Exception("API key invalid")

        # Import the module to trigger initialization
        import importlib

        import mcp_handley_lab.llm.gemini.tool

        with pytest.raises(Exception, match="API key invalid"):
            importlib.reload(mcp_handley_lab.llm.gemini.tool)

    @patch("mcp_handley_lab.llm.gemini.tool.is_text_file")
    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.read_text")
    def test_resolve_files_read_error(self, mock_read_text, mock_stat, mock_is_text):
        """Test file reading error in _resolve_files - should fail fast."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_files

        mock_stat.return_value.st_size = 100  # Small file
        mock_is_text.return_value = True
        # Make read_text fail
        mock_read_text.side_effect = Exception("Permission denied")

        files = [{"path": "/tmp/test.txt"}]

        # Should raise exception instead of adding error text
        with pytest.raises(Exception, match="Permission denied"):
            _resolve_files(files)

    def test_resolve_files_processing_error(self):
        """Test file processing error in _resolve_files - should fail fast."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_files

        # Use invalid path that will cause stat() to fail
        files = [{"path": "/invalid/nonexistent/path"}]

        # Should raise FileNotFoundError instead of adding error text
        with pytest.raises(FileNotFoundError):
            _resolve_files(files)

    @patch("pathlib.Path.read_bytes")
    @patch("PIL.Image.open")
    def test_resolve_images_load_error(self, mock_image_open, mock_read_bytes):
        """Test image loading error in _resolve_images (lines 161-162)."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_images

        # Return valid bytes but make PIL.Image.open fail
        mock_read_bytes.return_value = b"some image data"
        mock_image_open.side_effect = Exception("Invalid image format")

        with pytest.raises(Exception, match="Invalid image format"):
            _resolve_images(images=[{"path": "/tmp/invalid.jpg"}])

    @patch("mcp_handley_lab.llm.gemini.tool.client")
    def test_analyze_image_output_file_validation(self, mock_client):
        """Test output file validation in analyze_image (line 485)."""
        from mcp_handley_lab.llm.gemini.tool import analyze_image

        # Test with whitespace-only output file
        with pytest.raises(ValueError, match="Output file is required"):
            analyze_image(
                prompt="Test",
                output_file="   ",  # Whitespace only
                image_data="data:image/png;base64,test",
            )
