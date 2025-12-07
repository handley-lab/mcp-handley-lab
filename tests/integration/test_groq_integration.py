"""Integration tests for Groq LLM tools with real API calls."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.llm.groq.tool import mcp


@pytest.fixture
def test_output_file():
    """Create a temporary output file for test results."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_ask_simple(test_output_file):
    """Test basic text generation with Groq."""
    _, response = await mcp.call_tool(
        "ask",
        {
            "prompt": "What is 2+2? Answer with just the number.",
            "output_file": test_output_file,
            "agent_name": "",
            "model": "llama-3.1-8b-instant",
        },
    )

    assert "error" not in str(response).lower()
    assert response["content"]
    assert "usage" in response

    # Check output file was created
    output_content = Path(test_output_file).read_text()
    assert "4" in output_content


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_ask_with_files(test_output_file):
    """Test text generation with file input."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as test_file:
        test_file.write("Test document content: The answer is 42")
        test_file_path = test_file.name

    try:
        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What number is mentioned in the file?",
                "output_file": test_output_file,
                "agent_name": "",
                "model": "llama-3.1-8b-instant",
                "files": [test_file_path],
            },
        )

        assert "error" not in str(response).lower()
        assert response["content"]

        # Check response mentions the number
        output_content = Path(test_output_file).read_text()
        assert "42" in output_content

    finally:
        Path(test_file_path).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_list_models():
    """Test listing available Groq models."""
    _, response = await mcp.call_tool("list_models", {})

    assert "error" not in str(response).lower()
    assert "categories" in response or "models" in str(response)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_server_info():
    """Test server info without API call."""
    _, response = await mcp.call_tool("server_info", {})

    assert "error" not in str(response).lower()
    assert "groq" in str(response).lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_test_connection():
    """Test API connection."""
    _, response = await mcp.call_tool("test_connection", {})

    assert (
        "error" not in str(response).lower()
        or "connection successful" in str(response).lower()
    )


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_ask_with_memory(test_output_file):
    """Test conversation memory with agent_name."""
    # First message
    _, response1 = await mcp.call_tool(
        "ask",
        {
            "prompt": "Remember this number: 777. Just confirm you remember it.",
            "output_file": test_output_file,
            "agent_name": "test_memory_agent",
            "model": "llama-3.1-8b-instant",
        },
    )

    assert "error" not in str(response1).lower()

    # Second message - should remember
    _, response2 = await mcp.call_tool(
        "ask",
        {
            "prompt": "What number did I ask you to remember?",
            "output_file": test_output_file,
            "agent_name": "test_memory_agent",
            "model": "llama-3.1-8b-instant",
        },
    )

    assert "error" not in str(response2).lower()
    output_content = Path(test_output_file).read_text()
    assert "777" in output_content


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_ask_different_models(test_output_file):
    """Test with different Groq models."""
    models_to_test = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    ]

    for model in models_to_test:
        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "Say 'hello' in one word.",
                "output_file": test_output_file,
                "agent_name": "",
                "model": model,
            },
        )

        assert "error" not in str(response).lower(), f"Failed for model: {model}"
        assert response["content"], f"No content for model: {model}"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_kimi_model(test_output_file):
    """Test Kimi K2 model with large context."""
    _, response = await mcp.call_tool(
        "ask",
        {
            "prompt": "What is the capital of France? Answer briefly.",
            "output_file": test_output_file,
            "agent_name": "",
            "model": "moonshotai/kimi-k2-instruct-0905",
        },
    )

    assert "error" not in str(response).lower()
    assert response["content"]
    output_content = Path(test_output_file).read_text()
    assert "paris" in output_content.lower()
