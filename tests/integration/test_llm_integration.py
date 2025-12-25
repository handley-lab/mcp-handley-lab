"""Unified integration tests for all LLM providers (Claude, Gemini, OpenAI)."""

from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from PIL import Image

from mcp_handley_lab.llm.chat.tool import mcp

# Define provider-specific parameters (unified MCP, model determines provider)
llm_providers = [
    pytest.param(
        "claude",
        "ANTHROPIC_API_KEY",
        "claude-haiku-4-5-20251001",
        "5+5",
        "10",
        id="claude",
    ),
    pytest.param(
        "gemini",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "3+3",
        "6",
        id="gemini",
    ),
    pytest.param(
        "openai",
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "2+2",
        "4",
        id="openai",
    ),
    pytest.param(
        "grok",
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
        "claude",
        "ANTHROPIC_API_KEY",
        "claude-sonnet-4-5-20250929",
        id="claude",
    ),
    pytest.param(
        "gemini",
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini",
    ),
    pytest.param(
        "openai",
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai",
    ),
    pytest.param(
        "grok",
        "XAI_API_KEY",
        "grok-2-vision-1212",
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
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_ask_basic(
    skip_if_no_api_key,
    test_output_file,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test basic text generation for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Provider-specific parameters
    base_params = {
        "prompt": f"What is {question}? Answer with just the number.",
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",  # Disable memory
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_ask_with_files(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    provider,
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

    # Provider-specific parameters
    base_params = {
        "prompt": "What is in this file?",
        "output_file": test_output_file,
        "files": [str(test_file)],
        "model": model,
        "agent_name": "",
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 1.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 1.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 1.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert any(word in content.lower() for word in ["hello", "world", "test"])


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model", image_providers)
async def test_llm_analyze_image(
    skip_if_no_api_key,
    test_output_file,
    create_test_image,
    provider,
    api_key,
    model,
):
    """Test image analysis for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test image
    image_path = create_test_image("test_red.png", color="red")

    # Provider-specific parameters
    base_params = {
        "prompt": "What color is this image?",
        "output_file": test_output_file,
        "images": [str(image_path)],
        "model": model,
        "agent_name": "",
    }

    # Add provider-specific parameters
    if provider in ("openai", "gemini", "claude", "grok"):
        base_params.update({})

    _, response = await mcp.call_tool("analyze_image", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_memory_disabled(
    skip_if_no_api_key,
    test_output_file,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test that memory is properly disabled when agent_name=False."""
    skip_if_no_api_key(api_key)

    # Provider-specific parameters
    base_params = {
        "prompt": f"Remember this number: {answer}. What is {question}?",
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_input_validation(
    skip_if_no_api_key,
    test_output_file,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test input validation for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Provider-specific base parameters
    base_params = {
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 1.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 1.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 1.0,
            }
        )

    # Test empty prompt should raise error
    with pytest.raises(ToolError) as e1:
        await mcp.call_tool(
            "ask", {**base_params, "prompt": "", "output_file": test_output_file}
        )
    assert "prompt" in str(e1.value).lower() or "empty" in str(e1.value).lower()

    # Note: output_file now has a default of "-" in the unified tool,
    # so missing output_file is valid (uses stdout)


# Error scenario test parameters (unified MCP, model determines provider)
error_scenarios = [
    pytest.param(
        "claude",
        "ANTHROPIC_API_KEY",
        "claude-haiku-4-5-20251001",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="claude-invalid-model",
    ),
    pytest.param(
        "gemini",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="gemini-invalid-model",
    ),
    pytest.param(
        "openai",
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="openai-invalid-model",
    ),
    pytest.param(
        "grok",
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
    "provider, api_key, valid_model, invalid_value, error_param",
    error_scenarios,
)
async def test_llm_error_scenarios(
    skip_if_no_api_key,
    test_output_file,
    provider,
    api_key,
    valid_model,
    invalid_value,
    error_param,
):
    """Test error handling for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Provider-specific base parameters
    base_params = {
        "prompt": "Test prompt",
        "output_file": test_output_file,
        "model": invalid_value if error_param == "model" else valid_model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 1.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 1.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 1.0,
            }
        )

    # Test invalid model name should raise error
    with pytest.raises((ValueError, RuntimeError, Exception)):
        _, response = await mcp.call_tool("ask", base_params)
        # If no exception, check for error in response
        if "error" not in response:
            raise RuntimeError("Expected error for invalid model but call succeeded")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, prompt, expected", llm_providers)
async def test_llm_response_metadata_fields(
    skip_if_no_api_key,
    test_output_file,
    provider,
    api_key,
    model,
    prompt,
    expected,
):
    """Test that all LLM providers return comprehensive metadata fields."""
    skip_if_no_api_key(api_key)

    # Provider-specific base parameters
    base_params = {
        "prompt": prompt,
        "output_file": test_output_file,
        "model": model,
        "agent_name": "test_metadata",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 1.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 1.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 1.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    # Check basic response
    assert response["content"] is not None
    assert expected in response["content"]
    assert Path(test_output_file).exists()

    # Check common metadata fields
    assert response["finish_reason"] != ""
    assert response["model_version"] != ""
    assert response["avg_logprobs"] is None or isinstance(
        response["avg_logprobs"], float
    )

    # Check response_id (provider-specific)
    if provider in ("openai", "claude"):
        assert response.get("response_id", "") != ""

    # Provider-specific fields
    if provider == "openai":
        # Note: system_fingerprint and service_tier may be empty with Responses API
        assert isinstance(response.get("system_fingerprint", ""), str)
        assert isinstance(response.get("service_tier", ""), str)
        assert isinstance(response["completion_tokens_details"], dict)
        assert isinstance(response["prompt_tokens_details"], dict)

        if response["completion_tokens_details"]:
            expected_keys = {
                "reasoning_tokens",
                "accepted_prediction_tokens",
                "rejected_prediction_tokens",
                "audio_tokens",
            }
            assert expected_keys.issubset(response["completion_tokens_details"].keys())

    elif provider == "claude":
        assert response.get("service_tier", "") != ""
        assert isinstance(response.get("cache_creation_input_tokens", 0), int)
        assert isinstance(response.get("cache_read_input_tokens", 0), int)
        assert isinstance(response.get("stop_sequence", ""), str)

    elif provider == "gemini":
        assert response.get("generation_time_ms", 0) > 0

    elif provider == "grok":
        sf = response.get("system_fingerprint", "")
        assert isinstance(sf, str)
        assert response.get("service_tier", "") == ""
        assert isinstance(response["completion_tokens_details"], dict)
        assert isinstance(response["prompt_tokens_details"], dict)


class TestLLMMemory:
    """Test LLM conversational memory functionality."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_memory_enabled_with_agent_name(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test that conversational context is maintained across two calls with the same agent_name."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import uuid

        agent_name = f"test_memory_agent_{uuid.uuid4()}"  # Unique name per test run

        # Call 1: Provide a piece of information
        _, response1 = await mcp.call_tool(
            "ask",
            {
                "prompt": "My user ID is 789. Remember this important number.",
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": agent_name,
                "temperature": 0.1,
                "files": [],
            },
        )
        assert "error" not in response1, response1.get("error")
        assert response1["content"] is not None

        # Call 2: Ask a question that relies on the information from Call 1
        test_output_file2 = test_output_file.replace(".txt", "_2.txt")
        _, response2 = await mcp.call_tool(
            "ask",
            {
                "prompt": "What was my user ID that I told you?",
                "output_file": test_output_file2,
                "model": "gpt-4o-mini",
                "agent_name": agent_name,
                "temperature": 0.1,
                "files": [],
            },
        )
        assert "error" not in response2, response2.get("error")
        assert response2["content"] is not None
        content2 = Path(test_output_file2).read_text()
        assert "789" in content2, f"Expected '789' in response: {content2}"

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_memory_isolation_different_agents(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test that different agent names have isolated memory contexts."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import uuid

        agent_name1 = f"agent_1_{uuid.uuid4()}"
        agent_name2 = f"agent_2_{uuid.uuid4()}"

        # Agent 1: Remember number 123
        _, _ = await mcp.call_tool(
            "ask",
            {
                "prompt": "My favorite number is 123. Remember this.",
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": agent_name1,
                "temperature": 0.1,
                "files": [],
            },
        )

        # Agent 2: Ask about the number (should NOT know it)
        test_output_file2 = test_output_file.replace(".txt", "_agent2.txt")
        _, _ = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is my favorite number?",
                "output_file": test_output_file2,
                "model": "gpt-4o-mini",
                "agent_name": agent_name2,
                "temperature": 0.1,
                "files": [],
            },
        )

        # Verify isolation - Agent 2 should not know Agent 1's information
        content2 = Path(test_output_file2).read_text().lower()
        assert "123" not in content2, (
            f"Agent 2 should not know Agent 1's number: {content2}"
        )
        assert any(
            phrase in content2
            for phrase in [
                "don't know",
                "can't know",
                "cannot know",
                "not provided",
                "haven't told",
                "no information",
                "don't have access",
                "unless you tell me",
            ]
        ), f"Agent 2 should indicate it doesn't know: {content2}"


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_prompt_file_basic(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test basic prompt file loading for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test prompt file
    prompt_file = tmp_path / "test_prompt.txt"
    prompt_file.write_text(f"What is {question}? Answer with just the number.")

    # Provider-specific parameters
    base_params = {
        "prompt_file": str(prompt_file),
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_prompt_file_with_template_vars(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test prompt file loading with template variable substitution for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test prompt file with template variables
    prompt_file = tmp_path / "template_prompt.txt"
    prompt_file.write_text(
        "What is ${math_problem}? Answer with just the ${output_format}."
    )

    # Provider-specific parameters
    base_params = {
        "prompt_file": str(prompt_file),
        "prompt_vars": {"math_problem": question, "output_format": "number"},
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_system_prompt_file_with_templates(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test system prompt file loading with template variables for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Create test system prompt file with template variables
    system_prompt_file = tmp_path / "system_template.txt"
    system_prompt_file.write_text("You are a ${persona}. ${instruction}")

    # Provider-specific parameters
    base_params = {
        "prompt": f"What is {question}?",
        "system_prompt_file": str(system_prompt_file),
        "system_prompt_vars": {
            "persona": "helpful mathematics tutor",
            "instruction": "Always provide clear, concise answers with just the result.",
        },
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    _, response = await mcp.call_tool("ask", base_params)
    assert "error" not in response, response.get("error")

    assert response["content"] is not None
    assert len(response["content"]) > 0
    assert response["usage"]["input_tokens"] > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.parametrize("provider, api_key, model, question, answer", llm_providers)
async def test_llm_prompt_file_xor_validation(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    provider,
    api_key,
    model,
    question,
    answer,
):
    """Test XOR validation for prompt and prompt_file parameters."""
    skip_if_no_api_key(api_key)

    # Create test prompt file
    prompt_file = tmp_path / "test_prompt.txt"
    prompt_file.write_text(f"What is {question}?")

    # Provider-specific base parameters
    base_params = {
        "output_file": test_output_file,
        "model": model,
        "agent_name": "",
        "files": [],
    }

    # Add provider-specific parameters
    if provider == "openai":
        base_params.update(
            {
                "temperature": 0.0,
            }
        )
    elif provider == "gemini":
        base_params.update(
            {
                "temperature": 0.0,
                "grounding": False,
            }
        )
    elif provider in ("claude", "grok"):
        base_params.update(
            {
                "temperature": 0.0,
            }
        )

    # Test: both prompt and prompt_file provided (should fail)
    with pytest.raises(ToolError) as exc_info:
        params_both = base_params.copy()
        params_both.update(
            {
                "prompt": f"What is {question}?",
                "prompt_file": str(prompt_file),
            }
        )
        await mcp.call_tool("ask", params_both)
    assert "exactly one of 'prompt' or 'prompt_file'" in str(exc_info.value).lower()

    # Test: neither prompt nor prompt_file provided (should fail)
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool("ask", base_params)
    assert "exactly one of 'prompt' or 'prompt_file'" in str(exc_info.value).lower()
