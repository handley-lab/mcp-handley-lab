"""Integration tests for Gemini Deep Research via MCP protocol."""

import os

import pytest

from mcp_handley_lab.llm.tool import mcp


def skip_if_no_gemini_key():
    """Skip test if GEMINI_API_KEY is not available."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not available")


@pytest.mark.vcr
@pytest.mark.slow
@pytest.mark.live  # Skip in CI - VCR replays HTTP instantly but time.sleep() still executes
class TestGeminiDeepResearch:
    """Test Gemini Deep Research functionality via MCP protocol."""

    @pytest.mark.asyncio
    async def test_deep_research_basic_query(self):
        """Test deep research with a simple factual query."""
        skip_if_no_gemini_key()

        _, result = await mcp.call_tool(
            "chat",
            {
                "prompt": "What is the capital of France?",
                "model": "gemini-deep-research",
                "branch": "test-deep-research",
            },
        )

        assert "content" in result
        assert "Paris" in result["content"]
        assert "usage" in result
        assert result["branch"] == "test-deep-research"

    @pytest.mark.asyncio
    async def test_deep_research_with_grounding(self):
        """Test that deep research returns grounding metadata."""
        skip_if_no_gemini_key()

        _, result = await mcp.call_tool(
            "chat",
            {
                "prompt": "What are the latest developments in fusion energy research in 2025?",
                "model": "gemini-deep-research",
                "branch": "test-deep-research-grounding",
            },
        )

        assert "content" in result
        assert len(result["content"]) > 100  # Expect substantive response
        # Deep research should provide grounded responses about current events
        assert "fusion" in result["content"].lower()
