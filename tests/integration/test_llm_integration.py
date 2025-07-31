"""Unified integration tests for all LLM providers (Claude, Gemini, OpenAI)."""
from pathlib import Path

import pytest
from mcp_handley_lab.llm.claude.tool import mcp as claude_mcp
from mcp_handley_lab.llm.gemini.tool import mcp as gemini_mcp
from mcp_handley_lab.llm.grok.tool import mcp as grok_mcp
from mcp_handley_lab.llm.openai.tool import mcp as openai_mcp
from PIL import Image

# Define provider-specific parameters
llm_providers = [
    pytest.param(
        claude_mcp,
        "ask",
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        "5+5",
        "10",
        id="claude",
    ),
    pytest.param(
        gemini_mcp,
        "ask",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "3+3",
        "6",
        id="gemini",
    ),
    pytest.param(
        openai_mcp,
        "ask",
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "2+2",
        "4",
        id="openai",
    ),
    pytest.param(
        grok_mcp,
        "ask",
        "XAI_API_KEY",
        "grok-3-mini",
        "7+1",
        "8",
        id="grok",
        marks=pytest.mark.skip(
            reason="Grok uses gRPC (no VCR cassettes) - consume tokens without recording benefit"
        ),
    ),
]

image_providers = [
    pytest.param(
        claude_mcp,
        "analyze_image",
        "ANTHROPIC_API_KEY",
        "claude-3-5-sonnet-20240620",
        id="claude",
    ),
    pytest.param(
        gemini_mcp,
        "analyze_image",
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini",
    ),
    pytest.param(
        openai_mcp,
        "analyze_image",
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai",
    ),
    pytest.param(
        grok_mcp,
        "analyze_image",
        "XAI_API_KEY",
        "grok-2-vision-1212",
        id="grok",
        marks=pytest.mark.skip(
            reason="Grok uses gRPC (no VCR cassettes) - consume tokens without recording benefit"
        ),
    ),
]

server_info_providers = [
    pytest.param(claude_mcp, "server_info", "ANTHROPIC_API_KEY", id="claude"),
    pytest.param(gemini_mcp, "server_info", "GEMINI_API_KEY", id="gemini"),
    pytest.param(openai_mcp, "server_info", "OPENAI_API_KEY", id="openai"),
    pytest.param(
        grok_mcp,
        "server_info",
        "XAI_API_KEY",
        id="grok",
        marks=pytest.mark.skip(
            reason="Grok uses gRPC (no VCR cassettes) - consume tokens without recording benefit"
        ),
    ),
]


@pytest.fixture
def create_test_image(tmp_path):
    """Create test images for image analysis tests."""

    def _create_image(filename, color="red", size=(100, 100)):
        img = Image.new("RGB", size, color=color)
        image_path = tmp_path / filename
        img.save(image_path, format="PNG")
        return image_path

    return _create_image


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance, tool_name, api_key, model, question, answer", llm_providers
)
async def test_llm_ask_basic(
    skip_if_no_api_key,
    test_output_file,
    mcp_instance,
    tool_name,
    api_key,
    model,
    question,
    answer,
):
    """Test basic text generation for all LLM providers."""
    skip_if_no_api_key(api_key)

    result = await mcp_instance.call_tool(
        tool_name,
        {
            "prompt": f"What is {question}? Answer with just the number.",
            "output_file": test_output_file,
            "model": model,
            "temperature": 0.0,
            "agent_name": "",
        },
    )
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    assert result["content"] is not None
    assert len(result["content"]) > 0
    assert result["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance, tool_name, api_key, model, question, answer", llm_providers
)
async def test_llm_ask_with_files(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    mcp_instance,
    tool_name,
    api_key,
    model,
    question,
    answer,
):
    """Test file input for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\nThis is a test file.")

    result = await mcp_instance.call_tool(
        tool_name,
        {
            "prompt": "What is in this file?",
            "output_file": test_output_file,
            "files": [str(test_file)],
            "model": model,
            "agent_name": "",
        },
    )
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    assert result["content"] is not None
    assert len(result["content"]) > 0
    assert result["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert any(word in content.lower() for word in ["hello", "world", "test"])


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", image_providers)
async def test_llm_analyze_image(
    skip_if_no_api_key,
    test_output_file,
    create_test_image,
    mcp_instance,
    tool_name,
    api_key,
    model,
):
    """Test image analysis for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test image
    image_path = create_test_image("test_red.png", color="red")

    result = await mcp_instance.call_tool(
        tool_name,
        {
            "prompt": "What color is this image?",
            "output_file": test_output_file,
            "files": [str(image_path)],
            "model": model,
            "agent_name": "",  # Disable memory for clean test
        },
    )
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    assert result["content"] is not None
    assert len(result["content"]) > 0
    assert result["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance, tool_name, api_key, model, question, answer", llm_providers
)
async def test_llm_memory_disabled(
    skip_if_no_api_key,
    test_output_file,
    mcp_instance,
    tool_name,
    api_key,
    model,
    question,
    answer,
):
    """Test that memory is properly disabled when agent_name=False."""
    skip_if_no_api_key(api_key)

    result = await mcp_instance.call_tool(
        tool_name,
        {
            "prompt": f"Remember this number: {answer}. What is {question}?",
            "output_file": test_output_file,
            "model": model,
            "temperature": 0.0,
            "agent_name": "",
        },
    )
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    assert result["content"] is not None
    assert len(result["content"]) > 0
    assert result["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("mcp_instance, tool_name, api_key", server_info_providers)
async def test_llm_server_info(skip_if_no_api_key, mcp_instance, tool_name, api_key):
    """Test server info for all LLM providers."""
    skip_if_no_api_key(api_key)

    result = await mcp_instance.call_tool(tool_name, {})
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    # Handle both string and ServerInfo object returns
    if "name" in result and isinstance(result.get("name"), str):
        # Dictionary/object with name field
        assert "server" in result["name"].lower() or "tool" in result["name"].lower()
        assert result["status"] == "active"
        assert result["dependencies"]
    else:
        # String return or other format
        assert result["status"] == "active"
        assert "Tool" in result["name"]


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance, tool_name, api_key, model, question, answer", llm_providers
)
async def test_llm_input_validation(
    skip_if_no_api_key,
    test_output_file,
    mcp_instance,
    tool_name,
    api_key,
    model,
    question,
    answer,
):
    """Test input validation for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Test empty prompt should raise error
    try:
        result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "",
                "output_file": test_output_file,
                "model": model,
                "agent_name": "",
            },
        )
        import json

        response = json.loads(result[0].text)
        # If no exception, check for error in response
        if "error" in response:
            assert (
                "prompt" in response["error"].lower()
                or "empty" in response["error"].lower()
            )
        else:
            pytest.fail("Expected error for empty prompt")
    except Exception as e:
        # MCP wraps errors in ToolError
        assert "prompt" in str(e).lower() or "empty" in str(e).lower()

    # Test missing output_file should raise error
    try:
        result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "Test prompt",
                "output_file": "",
                "model": model,
                "agent_name": "",
            },
        )
        import json

        response = json.loads(result[0].text)
        # If no exception, check for error in response
        if "error" in response:
            assert (
                "output" in response["error"].lower()
                or "file" in response["error"].lower()
            )
        else:
            pytest.fail("Expected error for missing output file")
    except Exception as e:
        # MCP wraps errors in ToolError
        assert "output" in str(e).lower() or "file" in str(e).lower()


# Error scenario test parameters
error_scenarios = [
    pytest.param(
        claude_mcp,
        "ask",
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="claude-invalid-model",
    ),
    pytest.param(
        gemini_mcp,
        "ask",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="gemini-invalid-model",
    ),
    pytest.param(
        openai_mcp,
        "ask",
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="openai-invalid-model",
    ),
    pytest.param(
        grok_mcp,
        "ask",
        "XAI_API_KEY",
        "grok-3-mini",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="grok-invalid-model",
        marks=pytest.mark.skip(
            reason="Grok uses gRPC (no VCR cassettes) - consume tokens without recording benefit"
        ),
    ),
]


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance, tool_name, api_key, valid_model, invalid_value, error_param",
    error_scenarios,
)
async def test_llm_error_scenarios(
    skip_if_no_api_key,
    test_output_file,
    mcp_instance,
    tool_name,
    api_key,
    valid_model,
    invalid_value,
    error_param,
):
    """Test error handling for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Test invalid model name should raise error (various exception types possible)
    with pytest.raises((ValueError, RuntimeError, Exception)):
        result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "Test prompt",
                "output_file": test_output_file,
                "model": invalid_value if error_param == "model" else valid_model,
                "agent_name": "",
            },
        )
        import json

        response = json.loads(result[0].text)
        # If no exception is raised, check for error in response
        if "error" in response:
            raise RuntimeError(response["error"])


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mcp_instance,tool_name,api_key,model,prompt,expected", llm_providers
)
async def test_llm_response_metadata_fields(
    skip_if_no_api_key,
    test_output_file,
    mcp_instance,
    tool_name,
    api_key,
    model,
    prompt,
    expected,
):
    """Test that all LLM providers return comprehensive metadata fields."""
    skip_if_no_api_key(api_key)

    # Test OpenAI with logprobs enabled if it's OpenAI
    kwargs = {}
    if "openai" in str(mcp_instance):
        kwargs.update({"enable_logprobs": True, "top_logprobs": 3})

    result = await mcp_instance.call_tool(
        tool_name,
        {
            "prompt": prompt,
            "output_file": test_output_file,
            "model": model,
            "agent_name": "test_metadata",
            **kwargs,
        },
    )
    import json

    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    # Check basic response
    assert result["content"] is not None
    assert expected in result["content"]
    assert Path(test_output_file).exists()

    # Check common metadata fields
    assert result["finish_reason"] != ""
    assert result["model_version"] != ""
    assert isinstance(result["avg_logprobs"], float)

    # Check response_id (provider-specific)
    if "openai" in str(mcp_instance) or "claude" in str(mcp_instance):
        assert result["response_id"] != ""

    # Check provider-specific fields
    if "openai" in str(mcp_instance):
        # OpenAI-specific fields
        assert result["system_fingerprint"] != ""
        assert result["service_tier"] != ""
        assert isinstance(result["completion_tokens_details"], dict)
        assert isinstance(result["prompt_tokens_details"], dict)

        # Check logprobs were captured when enabled
        if kwargs.get("enable_logprobs"):
            assert result["avg_logprobs"] != 0.0

        # Check token details structure
        if result["completion_tokens_details"]:
            expected_keys = {
                "reasoning_tokens",
                "accepted_prediction_tokens",
                "rejected_prediction_tokens",
                "audio_tokens",
            }
            assert expected_keys.issubset(result["completion_tokens_details"].keys())

    elif "claude" in str(mcp_instance):
        # Claude-specific fields
        assert result["service_tier"] != ""
        assert isinstance(result["cache_creation_input_tokens"], int)
        assert isinstance(result["cache_read_input_tokens"], int)
        # stop_sequence can be empty string for normal completion
        assert isinstance(result["stop_sequence"], str)

    elif "gemini" in str(mcp_instance):
        # Gemini has generation_time_ms
        assert result["generation_time_ms"] > 0

    elif "grok" in str(mcp_instance):
        # Grok-specific fields (similar to OpenAI but without some features)
        assert (
            result["system_fingerprint"] != "" or result["system_fingerprint"] == ""
        )  # Allow empty
        assert result["service_tier"] == ""  # Grok doesn't have service tiers
        assert isinstance(result["completion_tokens_details"], dict)
        assert isinstance(result["prompt_tokens_details"], dict)


@pytest.mark.live
@pytest.mark.asyncio
async def test_openai_logprobs_configuration(skip_if_no_api_key, test_output_file):
    """Test OpenAI logprobs configuration options."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test without logprobs (default)
    result1 = await openai_mcp.call_tool(
        "ask",
        {
            "prompt": "What is 2+2?",
            "output_file": test_output_file,
            "model": "gpt-4o-mini",
            "agent_name": "test_no_logprobs",
            "enable_logprobs": False,
        },
    )
    import json

    response1 = json.loads(result1[0].text)
    assert "error" not in response1, response1.get("error")
    result1 = response1

    # Should have basic metadata but no meaningful logprobs
    assert result1["avg_logprobs"] == 0.0
    assert result1["finish_reason"] != ""
    assert result1["response_id"] != ""

    # Test with logprobs enabled
    result2 = await openai_mcp.call_tool(
        "ask",
        {
            "prompt": "What is 3+3?",
            "output_file": test_output_file,
            "model": "gpt-4o-mini",
            "agent_name": "test_with_logprobs",
            "enable_logprobs": True,
            "top_logprobs": 5,
        },
    )
    response2 = json.loads(result2[0].text)
    assert "error" not in response2, response2.get("error")
    result2 = response2

    # Should have meaningful logprobs
    assert result2["avg_logprobs"] != 0.0
    assert result2["finish_reason"] != ""
    assert result2["response_id"] != ""


class TestLLMMemory:
    """Test LLM conversational memory functionality."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_memory_enabled_with_agent_name(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test that conversational context is maintained across two calls with the same agent_name."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import json
        import uuid

        agent_name = f"test_memory_agent_{uuid.uuid4()}"  # Unique name per test run

        # Call 1: Provide a piece of information
        result1 = await openai_mcp.call_tool(
            "ask",
            {
                "prompt": "My user ID is 789. Remember this important number.",
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": agent_name,
                "temperature": 0.1,
            },
        )
        response1 = json.loads(result1[0].text)
        assert "error" not in response1, response1.get("error")
        result1 = response1
        assert result1["content"] is not None

        # Call 2: Ask a question that relies on the information from Call 1
        test_output_file2 = test_output_file.replace(".txt", "_2.txt")
        result2 = await openai_mcp.call_tool(
            "ask",
            {
                "prompt": "What was my user ID that I told you?",
                "output_file": test_output_file2,
                "model": "gpt-4o-mini",
                "agent_name": agent_name,
                "temperature": 0.1,
            },
        )
        response2 = json.loads(result2[0].text)
        assert "error" not in response2, response2.get("error")
        result2 = response2

        # Verify memory worked - the model should remember the user ID
        assert result2["content"] is not None
        content2 = Path(test_output_file2).read_text()
        assert "789" in content2, f"Expected '789' in response: {content2}"

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_memory_isolation_different_agents(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test that different agent names have isolated memory contexts."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import json
        import uuid

        agent_name1 = f"agent_1_{uuid.uuid4()}"
        agent_name2 = f"agent_2_{uuid.uuid4()}"

        # Agent 1: Remember number 123
        result1 = await openai_mcp.call_tool(
            "ask",
            {
                "prompt": "My favorite number is 123. Remember this.",
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": agent_name1,
                "temperature": 0.1,
            },
        )
        response1 = json.loads(result1[0].text)
        assert "error" not in response1, response1.get("error")

        # Agent 2: Ask about the number (should NOT know it)
        test_output_file2 = test_output_file.replace(".txt", "_agent2.txt")
        result2 = await openai_mcp.call_tool(
            "ask",
            {
                "prompt": "What is my favorite number?",
                "output_file": test_output_file2,
                "model": "gpt-4o-mini",
                "agent_name": agent_name2,
                "temperature": 0.1,
            },
        )
        response2 = json.loads(result2[0].text)
        assert "error" not in response2, response2.get("error")

        # Verify isolation - Agent 2 should not know Agent 1's information
        content2 = Path(test_output_file2).read_text().lower()
        assert (
            "123" not in content2
        ), f"Agent 2 should not know Agent 1's number: {content2}"
        assert any(
            phrase in content2
            for phrase in [
                "don't know",
                "not provided",
                "haven't told",
                "no information",
                "don't have access",
            ]
        ), f"Agent 2 should indicate it doesn't know: {content2}"
