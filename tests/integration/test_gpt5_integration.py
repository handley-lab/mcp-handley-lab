"""Integration tests for GPT-5 models."""

import os

import pytest
from mcp_handley_lab.llm.openai.tool import mcp


def skip_if_no_openai_key():
    """Skip test if OPENAI_API_KEY is not available."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not available")


@pytest.mark.vcr
@pytest.mark.live
class TestGPT5Integration:
    """Test GPT-5 model functionality."""

    @pytest.mark.asyncio
    async def test_gpt5_basic_query(self):
        """Test basic GPT-5 query functionality."""
        skip_if_no_openai_key()

        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is 3+3? Answer with just the number.",
                "model": "gpt-5",
                "agent_name": "false",  # Disable memory for clean test
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        # Check that the response contains the expected answer
        content = response.get("content", "")
        assert "6" in content

    @pytest.mark.asyncio
    async def test_gpt5_mini_basic_query(self):
        """Test basic GPT-5-mini query functionality."""
        skip_if_no_openai_key()

        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is 2+2? Answer with just the number.",
                "model": "gpt-5-mini",
                "agent_name": "false",
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        content = response.get("content", "")
        assert "4" in content

    @pytest.mark.asyncio
    async def test_gpt5_nano_basic_query(self):
        """Test basic GPT-5-nano query functionality."""
        skip_if_no_openai_key()

        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is 1+1? Answer with just the number.",
                "model": "gpt-5-nano",
                "agent_name": "false",
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        content = response.get("content", "")
        assert "2" in content

    @pytest.mark.asyncio
    async def test_gpt5_default_model(self):
        """Test that the default model is now gpt-5-mini."""
        skip_if_no_openai_key()

        # Test without specifying model (should use default)
        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is 5+5? Answer with just the number.",
                "agent_name": "false",
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        content = response.get("content", "")
        assert "10" in content

        # Check that gpt-5-mini was actually used
        usage_info = response.get("usage", {})
        model_used = usage_info.get("model_used", "")
        assert "gpt-5" in model_used.lower()

    @pytest.mark.asyncio
    async def test_gpt5_context_window(self):
        """Test that GPT-5 models handle large context."""
        skip_if_no_openai_key()

        # Create a moderately long prompt to test context handling
        long_text = "The quick brown fox jumps over the lazy dog. " * 100

        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": f"Count how many words are in this text: {long_text}",
                "model": "gpt-5-nano",
                "agent_name": "false",
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        content = response.get("content", "")
        # Should be able to handle this context without errors
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_gpt5_vision_capability(self):
        """Test that GPT-5 models are marked as vision-capable."""
        skip_if_no_openai_key()

        # Test the list_models functionality to check vision tag
        _, response = await mcp.call_tool("list_models", {})

        assert "error" not in str(response)
        models = response.get("models", [])

        # Find GPT-5 models and check they have vision tag
        gpt5_models = [m for m in models if m.get("id", "").startswith("gpt-5")]
        assert len(gpt5_models) >= 3  # gpt-5, gpt-5-mini, gpt-5-nano, gpt-5-chat-latest

        for model in gpt5_models:
            tags = model.get("tags", [])
            assert "vision" in tags, f"Model {model.get('id')} should have vision tag"

    @pytest.mark.asyncio
    async def test_gpt5_temperature_not_supported(self):
        """Test that GPT-5 models properly reject temperature parameter."""
        skip_if_no_openai_key()

        # GPT-5 models should reject custom temperature values
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(
            ToolError, match="does not support the 'temperature' parameter"
        ):
            await mcp.call_tool(
                "ask",
                {
                    "prompt": "Say hello",
                    "model": "gpt-5-nano",
                    "temperature": 0.1,  # Should fail
                    "agent_name": "false",
                    "output_file": "-",
                },
            )

    @pytest.mark.asyncio
    async def test_gpt5_nano_no_temperature(self):
        """Test that GPT-5-nano works without temperature parameter."""
        skip_if_no_openai_key()

        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "Say hello",
                "model": "gpt-5-nano",
                # No temperature parameter - should use default
                "agent_name": "false",
                "output_file": "-",
            },
        )

        assert "error" not in str(response)
        content = response.get("content", "")
        assert len(content) > 0
