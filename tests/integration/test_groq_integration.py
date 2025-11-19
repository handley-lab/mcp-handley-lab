"""Integration tests for Groq LLM provider."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.llm.groq.tool import (
    ask,
    list_models,
    server_info,
    test_connection,
)


class TestGroqIntegration:
    """Comprehensive integration tests for Groq LLM provider."""

    @pytest.mark.vcr
    def test_groq_ask_basic(self):
        """Test basic text generation with Groq."""
        result = ask(
            prompt="Hello, world!",
            model="llama-3.1-8b-instant",
            output_file="-",
            agent_name="",
            files=[],
            system_prompt=None,
            temperature=1.0,
            max_output_tokens=0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result.content is not None
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0
        assert result.usage.model_used == "llama-3.1-8b-instant"
        assert result.usage.cost > 0

    @pytest.mark.vcr
    def test_groq_list_models(self):
        """Test listing available models."""
        result = list_models()
        assert result.summary.provider == "groq"
        assert result.summary.total_models > 0
        assert len(result.models) > 0
        # Check for specific Groq models
        model_ids = [m.id for m in result.models]
        assert "llama-3.1-8b-instant" in model_ids

    @pytest.mark.vcr
    def test_groq_server_info(self):
        """Test server info functionality."""
        result = server_info()
        assert result.name == "Groq Tool"
        assert result.status == "active"
        assert len(result.capabilities) > 0

    @pytest.mark.vcr
    def test_groq_test_connection(self):
        """Test connection testing."""
        result = test_connection()
        assert isinstance(result, str)

    @pytest.mark.vcr
    def test_groq_ask_with_files(self):
        """Test text generation with file input."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is a test file content for Groq LLM processing.")
            test_file = f.name

        try:
            result = ask(
                prompt="Summarize the content of this file",
                files=[test_file],
                model="llama-3.1-8b-instant",
                output_file="-",
                agent_name="",
                system_prompt=None,
                temperature=1.0,
                max_output_tokens=0,
                prompt_file=None,
                prompt_vars={},
                system_prompt_file=None,
                system_prompt_vars={},
            )
            assert result.content is not None
            assert result.usage.input_tokens > 0
            assert result.usage.model_used == "llama-3.1-8b-instant"
        finally:
            Path(test_file).unlink(missing_ok=True)

    @pytest.mark.vcr
    def test_groq_system_prompt_basic(self):
        """Test system prompt functionality."""
        result = ask(
            prompt="What is quantum computing?",
            system_prompt="You are a helpful science educator specializing in quantum physics.",
            model="llama-3.1-8b-instant",
            output_file="-",
            agent_name="",
            files=[],
            temperature=1.0,
            max_output_tokens=0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result.content is not None
        assert result.usage.input_tokens > 0

    @pytest.mark.vcr
    def test_groq_temperature_scenarios(self):
        """Test temperature parameter scenarios."""
        result = ask(
            prompt="Generate some text",
            temperature=1.5,
            model="llama-3.1-8b-instant",
            output_file="-",
            agent_name="",
            files=[],
            system_prompt=None,
            max_output_tokens=0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result.content is not None

    @pytest.mark.vcr
    def test_groq_error_scenarios(self):
        """Test error handling."""
        # Invalid model
        with pytest.raises(ValueError):
            ask(
                prompt="Test prompt",
                model="invalid-groq-model-xyz",
                output_file="-",
                agent_name="",
                files=[],
                system_prompt=None,
                temperature=1.0,
                max_output_tokens=0,
                prompt_file=None,
                prompt_vars={},
                system_prompt_file=None,
                system_prompt_vars={},
            )

    @pytest.mark.vcr
    def test_groq_memory_with_agent(self):
        """Test persistent memory with named agent."""
        agent_name = "test_groq_agent"

        # First message
        result1 = ask(
            prompt="My favorite color is blue",
            agent_name=agent_name,
            model="llama-3.1-8b-instant",
            output_file="-",
            files=[],
            system_prompt=None,
            temperature=1.0,
            max_output_tokens=0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result1.content is not None

        # Second message - should maintain agent state
        result2 = ask(
            prompt="What's my favorite color?",
            agent_name=agent_name,
            model="llama-3.1-8b-instant",
            output_file="-",
            files=[],
            system_prompt=None,
            temperature=1.0,
            max_output_tokens=0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result2.content is not None

    @pytest.mark.vcr
    def test_groq_prompt_file_basic(self):
        """Test loading prompt from file."""
        prompt_content = "What is 2+2? Answer briefly."

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt_content)
            prompt_file = f.name

        try:
            result = ask(
                prompt=None,
                prompt_file=prompt_file,
                model="llama-3.1-8b-instant",
                output_file="-",
                agent_name="",
                files=[],
                system_prompt=None,
                temperature=1.0,
                max_output_tokens=0,
                prompt_vars={},
                system_prompt_file=None,
                system_prompt_vars={},
            )
            assert result.content is not None
            assert result.usage.output_tokens > 0
        finally:
            Path(prompt_file).unlink(missing_ok=True)

    @pytest.mark.vcr
    def test_groq_large_context_kimi(self):
        """Test Kimi's 256K context window capability."""
        large_context = "Summarize this comprehensive document: " + "x" * 50000

        result = ask(
            prompt=large_context,
            model="moonshotai/kimi-k2-instruct-0905",
            max_output_tokens=8192,
            output_file="-",
            agent_name="",
            files=[],
            system_prompt=None,
            temperature=1.0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result.content is not None
        assert result.usage.model_used == "moonshotai/kimi-k2-instruct-0905"
        assert result.usage.output_tokens > 0

    @pytest.mark.vcr
    def test_groq_max_tokens_validation(self):
        """Test max tokens limitation."""
        result = ask(
            prompt="Tell me a long story about artificial intelligence",
            max_output_tokens=100,
            model="llama-3.1-8b-instant",
            output_file="-",
            agent_name="",
            files=[],
            system_prompt=None,
            temperature=1.0,
            prompt_file=None,
            prompt_vars={},
            system_prompt_file=None,
            system_prompt_vars={},
        )
        assert result.content is not None
        assert result.usage.output_tokens <= 100
