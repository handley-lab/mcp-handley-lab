"""Unit tests for Grok LLM module."""
from unittest.mock import patch

from mcp_handley_lab.llm.grok.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    analyze_image,
    ask,
    generate_image,
)


class TestGrokModelConfiguration:
    """Test Grok model configuration and functionality."""

    def test_model_configs_all_present(self):
        """Test that all expected Grok models are in MODEL_CONFIGS."""
        expected_models = {
            "grok-4",
            "grok-3",
            "grok-3-mini",
            "grok-2-vision-1212",
            "grok-2-image-1212",
            "grok-2-1212",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # Grok 4 series
        assert MODEL_CONFIGS["grok-4"]["output_tokens"] == 100000

        # Grok 3 series
        assert MODEL_CONFIGS["grok-3"]["output_tokens"] == 65536
        assert MODEL_CONFIGS["grok-3-mini"]["output_tokens"] == 65536

        # Grok 2 series (text models)
        assert MODEL_CONFIGS["grok-2-vision-1212"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["grok-2-1212"]["output_tokens"] == 16384

        # Grok 2 image generation model has None (doesn't use token limits)
        assert MODEL_CONFIGS["grok-2-image-1212"]["output_tokens"] is None

    def test_model_configs_structure(self):
        """Test that model configurations have required structure."""
        # All Grok models should have output_tokens field
        # Note: Image generation models may have None values
        for model_config in MODEL_CONFIGS.values():
            assert "output_tokens" in model_config
            # Allow None for image generation models, require int for others
            output_tokens = model_config["output_tokens"]
            assert output_tokens is None or isinstance(output_tokens, int)

    def test_get_model_config_valid_model(self):
        """Test _get_model_config with valid model names."""
        config = _get_model_config("grok-4")
        assert config["output_tokens"] == 100000

    def test_get_model_config_fallback_to_default(self):
        """Test _get_model_config falls back to default for unknown models."""
        from mcp_handley_lab.llm.grok.tool import DEFAULT_MODEL

        config = _get_model_config("nonexistent-model")
        default_config = MODEL_CONFIGS[DEFAULT_MODEL]
        assert config == default_config


class TestGrokTextGeneration:
    """Test Grok text generation functionality."""

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_ask_basic(self, mock_process):
        """Test basic text generation functionality."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        ask(prompt="What is 2+2?", output_file="-")

        # Verify process_llm_request was called with correct parameters
        mock_process.assert_called_once()
        call_args = mock_process.call_args

        assert call_args[1]["prompt"] == "What is 2+2?"
        assert call_args[1]["provider"] == "grok"
        assert call_args[1]["generation_func"].__name__ == "_grok_generation_adapter"

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_ask_with_files(self, mock_process):
        """Test text generation with file inputs."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        ask(prompt="Analyze this file", files=["test.txt"], output_file="-")

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["files"] == ["test.txt"]

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_ask_with_temperature(self, mock_process):
        """Test text generation with custom temperature."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        ask(prompt="Be creative", temperature=1.5, output_file="-")

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["temperature"] == 1.5

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_ask_with_max_output_tokens(self, mock_process):
        """Test text generation with max output tokens limit."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        ask(prompt="Write a long response", max_output_tokens=1000, output_file="-")

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["max_output_tokens"] == 1000

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_ask_with_custom_model(self, mock_process):
        """Test text generation with custom model."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        ask(prompt="Test question", model="grok-3-mini", output_file="-")

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model"] == "grok-3-mini"


class TestGrokImageAnalysis:
    """Test Grok image analysis functionality."""

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_analyze_image_basic(self, mock_process):
        """Test basic image analysis functionality."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        analyze_image(
            prompt="What's in this image?", files=["test.jpg"], output_file="-"
        )

        # Verify process_llm_request was called with correct parameters
        mock_process.assert_called_once()
        call_args = mock_process.call_args

        assert call_args[1]["prompt"] == "What's in this image?"
        assert call_args[1]["images"] == ["test.jpg"]
        assert call_args[1]["provider"] == "grok"
        assert (
            call_args[1]["generation_func"].__name__ == "_grok_image_analysis_adapter"
        )

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_analyze_image_with_focus(self, mock_process):
        """Test image analysis with focus parameter."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        analyze_image(
            prompt="Analyze this image",
            files=["test.jpg"],
            focus="text",
            output_file="-",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["focus"] == "text"

    @patch("mcp_handley_lab.llm.grok.tool.process_llm_request")
    def test_analyze_image_with_vision_model(self, mock_process):
        """Test image analysis with vision-specific model."""
        mock_process.return_value = {
            "content": "Test response",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        analyze_image(
            prompt="Analyze this image",
            files=["test.jpg"],
            model="grok-2-vision-1212",
            output_file="-",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model"] == "grok-2-vision-1212"


class TestGrokImageGeneration:
    """Test Grok image generation functionality."""

    @patch("mcp_handley_lab.llm.grok.tool.process_image_generation")
    def test_generate_image_basic(self, mock_process):
        """Test basic image generation functionality."""
        mock_process.return_value = {
            "file_path": "/tmp/generated_image.png",
            "metadata": {"model_used": "grok-2-image-1212"},
        }

        generate_image(
            prompt="A beautiful sunset",
        )

        # Verify process_image_generation was called with correct parameters
        mock_process.assert_called_once()
        call_args = mock_process.call_args

        assert call_args[1]["prompt"] == "A beautiful sunset"
        assert call_args[1]["provider"] == "grok"
        assert (
            call_args[1]["generation_func"].__name__ == "_grok_image_generation_adapter"
        )

    @patch("mcp_handley_lab.llm.grok.tool.process_image_generation")
    def test_generate_image_with_model(self, mock_process):
        """Test image generation with specific model."""
        mock_process.return_value = {
            "file_path": "/tmp/generated_image.png",
            "metadata": {"model_used": "grok-2-image-1212"},
        }

        generate_image(
            prompt="A beautiful sunset",
            model="grok-2-image-1212",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model"] == "grok-2-image-1212"

    @patch("mcp_handley_lab.llm.grok.tool.process_image_generation")
    def test_generate_image_with_agent(self, mock_process):
        """Test image generation with agent name."""
        mock_process.return_value = {
            "file_path": "/tmp/generated_image.png",
            "metadata": {"model_used": "grok-2-image-1212"},
        }

        generate_image(
            prompt="A beautiful sunset",
            agent_name="test_agent",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["agent_name"] == "test_agent"


class TestGrokErrorHandling:
    """Test Grok error handling and edge cases."""

    def test_model_config_retrieval_robust(self):
        """Test model configuration retrieval is robust."""
        # Should not raise exceptions for any model name
        config = _get_model_config("completely-invalid-model")
        assert isinstance(config, dict)
        assert "output_tokens" in config

    def test_model_configs_basic_structure(self):
        """Test that all model configs have basic required fields."""
        for model_name, config in MODEL_CONFIGS.items():
            assert "output_tokens" in config, f"Missing output_tokens in {model_name}"
            # Allow None for image generation models (like grok-2-image-1212)
            output_tokens = config["output_tokens"]
            assert output_tokens is None or isinstance(
                output_tokens, int
            ), f"Invalid output_tokens type in {model_name}: {type(output_tokens)}"

    def test_model_count_matches_expected(self):
        """Test that we have the expected number of models."""
        # Ensure we have all 6 expected Grok models
        assert len(MODEL_CONFIGS) == 6
