"""Unit tests for LLM provider parameter forwarding and wiring."""

import inspect

import pytest

from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.grok.tool import ask as grok_ask
from mcp_handley_lab.llm.openai.tool import ask as openai_ask


class TestProviderXORValidation:
    """Test XOR validation at the provider level."""

    def test_openai_ask_xor_validation_prompt_raises(self, tmp_path):
        """Test that OpenAI ask() raises ValueError for conflicting prompt parameters."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Test prompt")

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            openai_ask(
                prompt="Direct prompt",
                prompt_file=str(prompt_file),
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
                output_file="-",
                agent_name="",
                model="gpt-4o-mini",
                files=[],
                temperature=1.0,
                max_output_tokens=0,
                enable_logprobs=False,
                top_logprobs=0,
            )

    def test_claude_ask_xor_validation_prompt_raises(self, tmp_path):
        """Test that Claude ask() raises ValueError for conflicting prompt parameters."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Test prompt")

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            claude_ask(
                prompt="Direct prompt",
                prompt_file=str(prompt_file),
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
                output_file="-",
                agent_name="",
                model="claude-3-5-haiku-20241022",
                files=[],
                temperature=1.0,
                max_output_tokens=0,
            )

    def test_gemini_ask_xor_validation_prompt_raises(self):
        """Test that Gemini ask() raises ValueError for conflicting prompt parameters."""
        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            gemini_ask(
                prompt="",
                prompt_file="",
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
                output_file="-",
                agent_name="",
                model="gemini-2.5-flash",
                files=[],
                temperature=1.0,
                max_output_tokens=0,
                grounding=False,
            )

    def test_grok_ask_xor_validation_prompt_raises(self):
        """Test that Grok ask() raises ValueError for conflicting prompt parameters."""
        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            grok_ask(
                prompt="",
                prompt_file="",
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
                output_file="-",
                agent_name="",
                model="grok-3-mini",
                files=[],
                temperature=1.0,
                max_output_tokens=0,
            )


class TestProviderParameterConsistency:
    """Test that all providers have consistent parameter signatures."""

    def test_all_providers_have_prompt_file_parameters(self):
        """Test that all ask() functions have the required new parameters."""
        providers = [openai_ask, claude_ask, gemini_ask, grok_ask]
        required_params = {
            "prompt_file",
            "prompt_vars",
            "system_prompt_file",
            "system_prompt_vars",
        }

        for provider_ask in providers:
            sig = inspect.signature(provider_ask)
            provider_params = set(sig.parameters.keys())

            for param in required_params:
                assert param in provider_params, (
                    f"Provider {provider_ask.__module__} missing parameter: {param}"
                )

    def test_parameter_types_are_consistent(self):
        """Test that all providers have consistent parameter types for new parameters."""
        providers = [openai_ask, claude_ask, gemini_ask, grok_ask]
        expected_types = {
            "prompt_file": str,
            "prompt_vars": dict,
            "system_prompt_file": str,
            "system_prompt_vars": dict,
        }

        for provider_ask in providers:
            sig = inspect.signature(provider_ask)

            for param_name, expected_type in expected_types.items():
                param = sig.parameters[param_name]
                # For Field() parameters, the annotation might be wrapped
                actual_type = param.annotation

                # Handle dict[str, str] type annotations first
                if (
                    hasattr(actual_type, "__origin__")
                    and actual_type.__origin__ is dict
                ):
                    actual_type = dict
                # Handle Union types (e.g., str | None)
                elif hasattr(actual_type, "__origin__"):
                    args = getattr(actual_type, "__args__", ())
                    # Get the first non-None type
                    actual_type = next(
                        (arg for arg in args if arg is not type(None)), actual_type
                    )

                assert actual_type == expected_type, (
                    f"Provider {provider_ask.__module__} parameter {param_name} "
                    f"has type {actual_type}, expected {expected_type}"
                )


class TestPromptFileValidationBehavior:
    """Test the actual behavior of prompt file validation across providers."""

    def test_providers_validate_prompt_xor_consistently(self):
        """Test that all providers validate prompt XOR consistently."""
        providers = [openai_ask, claude_ask, gemini_ask, grok_ask]

        for provider_ask in providers:
            # Test both prompt and prompt_file provided
            with pytest.raises(
                ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
            ):
                provider_ask(
                    prompt="test",
                    prompt_file="/some/file",
                    prompt_vars={},
                    system_prompt="",
                    system_prompt_file="",
                    system_prompt_vars={},
                    output_file="-",
                    agent_name="",
                    model="test-model",  # Will fail later but validation comes first
                    files=[],
                )

            # Test neither prompt nor prompt_file provided
            with pytest.raises(
                ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
            ):
                provider_ask(
                    prompt="",
                    prompt_file="",
                    prompt_vars={},
                    system_prompt="",
                    system_prompt_file="",
                    system_prompt_vars={},
                    output_file="-",
                    agent_name="",
                    model="test-model",  # Will fail later but validation comes first
                    files=[],
                )
