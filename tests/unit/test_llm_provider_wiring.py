"""Unit tests for LLM provider parameter forwarding and wiring."""

import inspect

import pytest

from mcp_handley_lab.llm.common import load_prompt_text
from mcp_handley_lab.llm.registry import PROVIDERS, get_default_model, resolve_model
from mcp_handley_lab.llm.tool import chat


class TestXORValidation:
    """Test XOR validation functions directly via load_prompt_text."""

    def test_prompt_xor_validation_both_raises(self, tmp_path):
        """Test that providing both prompt and prompt_file raises ValueError."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Test prompt")

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            load_prompt_text(
                prompt="Direct prompt",
                prompt_file=str(prompt_file),
                prompt_vars={},
            )

    def test_prompt_xor_validation_neither_raises(self):
        """Test that providing neither prompt nor prompt_file raises ValueError."""
        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            load_prompt_text(
                prompt="",
                prompt_file="",
                prompt_vars={},
            )

    def test_prompt_xor_validation_prompt_only_succeeds(self):
        """Test that providing only prompt succeeds."""
        result = load_prompt_text(
            prompt="Direct prompt",
            prompt_file="",
            prompt_vars={},
        )
        assert result == "Direct prompt"

    def test_prompt_xor_validation_file_only_succeeds(self, tmp_path):
        """Test that providing only prompt_file succeeds."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("File prompt content")

        result = load_prompt_text(
            prompt="",
            prompt_file=str(prompt_file),
            prompt_vars={},
        )
        assert result == "File prompt content"

    def test_system_prompt_xor_validation_both_raises(self, tmp_path):
        """Test that providing both system_prompt and system_prompt_file raises ValueError."""
        system_file = tmp_path / "system.txt"
        system_file.write_text("Test system")

        # Uses the same load_prompt_text function for system prompt
        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            load_prompt_text(
                prompt="Direct system",
                prompt_file=str(system_file),
                prompt_vars={},
            )


class TestProviderAliasResolution:
    """Test that provider aliases resolve to correct default models."""

    def test_gemini_alias_resolves_to_default(self):
        """Test that 'gemini' resolves to the default Gemini model."""
        provider, model, config = resolve_model("gemini")
        assert provider == "gemini"
        assert model == get_default_model("gemini")
        assert config  # Should have configuration

    def test_openai_alias_resolves_to_default(self):
        """Test that 'openai' resolves to the default OpenAI model."""
        provider, model, config = resolve_model("openai")
        assert provider == "openai"
        assert model == get_default_model("openai")
        assert config

    def test_claude_alias_resolves_to_default(self):
        """Test that 'claude' resolves to the default Claude model."""
        provider, model, config = resolve_model("claude")
        assert provider == "claude"
        assert model == get_default_model("claude")
        assert config

    def test_all_providers_have_defaults(self):
        """Test that all providers have default models defined."""
        for provider in PROVIDERS:
            default = get_default_model(provider)
            assert default, f"Provider {provider} has no default model"

    def test_claude_shorthand_aliases(self):
        """Test Claude shorthand aliases (sonnet, opus, haiku)."""
        for alias in ["sonnet", "opus", "haiku"]:
            provider, model, config = resolve_model(alias)
            assert provider == "claude"
            assert model.startswith("claude-")
            assert config


class TestUnifiedChatParameterConsistency:
    """Test that the unified chat tool has consistent parameters."""

    def test_chat_has_required_parameters(self):
        """Test that chat() has all required parameters."""
        sig = inspect.signature(chat)
        required_params = {
            "prompt",
            "prompt_file",
            "prompt_vars",
            "output_file",
            "branch",
            "model",
            "temperature",
            "files",
            "system_prompt",
            "system_prompt_file",
            "system_prompt_vars",
            "options",
        }

        actual_params = set(sig.parameters.keys())
        for param in required_params:
            assert param in actual_params, f"Missing parameter: {param}"

    def test_chat_has_image_analysis_parameters(self):
        """Test that chat() has image analysis parameters (merged from analyze_image)."""
        sig = inspect.signature(chat)
        image_params = {"images", "focus"}

        actual_params = set(sig.parameters.keys())
        for param in image_params:
            assert param in actual_params, f"Missing parameter: {param}"


class TestModelResolution:
    """Test model name resolution and prefix matching (fail-fast behavior)."""

    def test_prefix_matching_gemini_raises(self):
        """Test that unknown Gemini models fail-fast with helpful error."""
        with pytest.raises(
            ValueError, match="Unknown model.*gemini.*not in the registry"
        ):
            resolve_model("gemini-unknown-model")

    def test_prefix_matching_openai_raises(self):
        """Test that unknown OpenAI models fail-fast with helpful error."""
        with pytest.raises(
            ValueError, match="Unknown model.*openai.*not in the registry"
        ):
            resolve_model("gpt-future-model")

    def test_prefix_matching_claude_raises(self):
        """Test that unknown Claude models fail-fast with helpful error."""
        with pytest.raises(
            ValueError, match="Unknown model.*claude.*not in the registry"
        ):
            resolve_model("claude-future-version")

    def test_unknown_model_raises(self):
        """Test that completely unknown models raise ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("completely-unknown-provider-model")
