"""Integration tests for GPT-5 models."""

import os

import pytest

from mcp_handley_lab.llm.tool import mcp


def skip_if_no_openai_key():
    """Skip test if OPENAI_API_KEY is not available."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not available")


@pytest.mark.vcr
class TestGPT5Integration:
    """Test GPT-5 model functionality."""

    @pytest.mark.asyncio
    async def test_gpt5_basic_query(self):
        """Test basic GPT-5 query functionality."""
        skip_if_no_openai_key()

        # GPT-5 doesn't support temperature parameter
        _, response = await mcp.call_tool(
            "chat",
            {
                "prompt": "What is 3+3? Answer with just the number.",
                "output_file": "-",
                "branch": "false",
                "model": "gpt-5",
                "files": [],
                "system_prompt": "",
                # Don't include temperature for GPT-5 models
            },
        )

        assert "error" not in response
        # Check that the response contains the expected answer
        content = response.get("content", "")
        assert "6" in content

    @pytest.mark.asyncio
    async def test_gpt5_mini_basic_query(self):
        """Test basic GPT-5-mini query functionality."""
        skip_if_no_openai_key()

        # GPT-5-mini doesn't support temperature parameter
        _, response = await mcp.call_tool(
            "chat",
            {
                "prompt": "What is 2+2? Answer with just the number.",
                "output_file": "-",
                "branch": "false",
                "model": "gpt-5-mini",
                "files": [],
                "system_prompt": "",
                # Don't include temperature for GPT-5 models
            },
        )

        assert "error" not in response
        content = response.get("content", "")
        assert "4" in content

    @pytest.mark.asyncio
    async def test_gpt5_nano_basic_query(self):
        """Test basic GPT-5-nano query functionality."""
        skip_if_no_openai_key()

        # GPT-5-nano doesn't support temperature parameter
        _, response = await mcp.call_tool(
            "chat",
            {
                "prompt": "What is 1+1? Answer with just the number.",
                "output_file": "-",
                "branch": "false",
                "model": "gpt-5-nano",
                "files": [],
                "system_prompt": "",
                # Don't include temperature for GPT-5 models
            },
        )

        assert "error" not in response
        content = response.get("content", "")
        assert "2" in content

    @pytest.mark.asyncio
    async def test_gpt5_context_window(self):
        """Test that GPT-5 models handle large context."""
        skip_if_no_openai_key()

        # Create a moderately long prompt to test context handling
        long_text = "The quick brown fox jumps over the lazy dog. " * 100

        # GPT-5-nano doesn't support temperature parameter
        _, response = await mcp.call_tool(
            "chat",
            {
                "prompt": f"Count how many words are in this text: {long_text}",
                "output_file": "-",
                "branch": "false",
                "model": "gpt-5-nano",
                "files": [],
                "system_prompt": "",
                # Don't include temperature for GPT-5 models
            },
        )

        assert "error" not in response
        content = response.get("content", "")
        # Should be able to handle this context without errors
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_gpt5_temperature_not_supported(self):
        """Test that GPT-5 models properly reject temperature parameter."""
        skip_if_no_openai_key()

        # GPT-5 models should reject custom temperature values
        # MCP wraps exceptions in ToolError, so we need to catch that
        try:
            _, response = await mcp.call_tool(
                "chat",
                {
                    "prompt": "Say hello",
                    "output_file": "-",
                    "branch": "false",
                    "model": "gpt-5-nano",
                    "temperature": 0.1,  # Should fail
                    "files": [],
                    "system_prompt": "",
                },
            )
            # If we get here, the test should fail
            raise AssertionError("Expected ToolError to be raised")
        except Exception as e:
            # Verify the error message contains the expected text
            assert "does not support the 'temperature' parameter" in str(e)

    @pytest.mark.asyncio
    async def test_gpt5_nano_no_temperature(self):
        """Test that GPT-5-nano works without temperature parameter."""
        skip_if_no_openai_key()

        # GPT-5-nano works without temperature parameter
        _, response = await mcp.call_tool(
            "chat",
            {
                "prompt": "Say hello",
                "output_file": "-",
                "branch": "false",
                "model": "gpt-5-nano",
                "files": [],
                "system_prompt": "",
                # No temperature parameter - should use default
            },
        )

        assert "error" not in response
        content = response.get("content", "")
        assert len(content) > 0
