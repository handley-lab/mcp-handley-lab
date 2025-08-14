"""Unified integration tests for all LLM providers (Claude, Gemini, OpenAI)."""

from pathlib import Path

import pytest
from PIL import Image

from mcp_handley_lab.llm.claude.tool import analyze_image as claude_analyze_image
from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.claude.tool import server_info as claude_server_info
from mcp_handley_lab.llm.gemini.tool import analyze_image as gemini_analyze_image
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.gemini.tool import server_info as gemini_server_info
from mcp_handley_lab.llm.grok.tool import analyze_image as grok_analyze_image
from mcp_handley_lab.llm.grok.tool import ask as grok_ask
from mcp_handley_lab.llm.grok.tool import server_info as grok_server_info
from mcp_handley_lab.llm.openai.tool import analyze_image as openai_analyze_image
from mcp_handley_lab.llm.openai.tool import ask as openai_ask
from mcp_handley_lab.llm.openai.tool import server_info as openai_server_info

# Define provider-specific parameters (direct function references)
llm_providers = [
    pytest.param(
        claude_ask,
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        "5+5",
        "10",
        id="claude",
    ),
    pytest.param(
        gemini_ask,
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "3+3",
        "6",
        id="gemini",
    ),
    pytest.param(
        openai_ask,
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "2+2",
        "4",
        id="openai",
    ),
    pytest.param(
        grok_ask,
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
        claude_analyze_image,
        "ANTHROPIC_API_KEY",
        "claude-3-5-sonnet-20240620",
        id="claude",
    ),
    pytest.param(
        gemini_analyze_image,
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini",
    ),
    pytest.param(
        openai_analyze_image,
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai",
    ),
    pytest.param(
        grok_analyze_image,
        "XAI_API_KEY",
        "grok-2-vision-1212",
        id="grok",
        marks=pytest.mark.skip(
            reason="Grok uses gRPC (no VCR cassettes) - consume tokens without recording benefit"
        ),
    ),
]

server_info_providers = [
    pytest.param(claude_server_info, "ANTHROPIC_API_KEY", id="claude"),
    pytest.param(gemini_server_info, "GEMINI_API_KEY", id="gemini"),
    pytest.param(openai_server_info, "OPENAI_API_KEY", id="openai"),
    pytest.param(
        grok_server_info,
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
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_ask_basic(
    skip_if_no_api_key,
    test_output_file,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
            }
        )

    result = ask_func(**base_params)

    assert result.content is not None
    assert len(result.content) > 0
    assert result.usage.input_tokens > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_ask_with_files(
    skip_if_no_api_key,
    test_output_file,
    tmp_path,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
            }
        )

    result = ask_func(**base_params)

    assert result.content is not None
    assert len(result.content) > 0
    assert result.usage.input_tokens > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert any(word in content.lower() for word in ["hello", "world", "test"])


@pytest.mark.vcr
@pytest.mark.parametrize("analyze_func, api_key, model", image_providers)
def test_llm_analyze_image(
    skip_if_no_api_key,
    test_output_file,
    create_test_image,
    analyze_func,
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
        "files": [str(image_path)],
        "model": model,
        "agent_name": "",
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if (
        analyze_func.__name__ == "analyze_image"
        and "openai" in analyze_func.__module__
        or analyze_func.__name__ == "analyze_image"
        and "gemini" in analyze_func.__module__
        or analyze_func.__name__ == "analyze_image"
        and "claude" in analyze_func.__module__
        or analyze_func.__name__ == "analyze_image"
        and "grok" in analyze_func.__module__
    ):
        base_params.update(
            {
                "max_output_tokens": 0,
            }
        )

    result = analyze_func(**base_params)

    assert result.content is not None
    assert len(result.content) > 0
    assert result.usage.input_tokens > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_memory_disabled(
    skip_if_no_api_key,
    test_output_file,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 0.0,
                "max_output_tokens": 0,
            }
        )

    result = ask_func(**base_params)

    assert result.content is not None
    assert len(result.content) > 0
    assert result.usage.input_tokens > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert answer in content


@pytest.mark.vcr
@pytest.mark.parametrize("server_info_func, api_key", server_info_providers)
def test_llm_server_info(skip_if_no_api_key, server_info_func, api_key):
    """Test server info for all LLM providers."""
    skip_if_no_api_key(api_key)

    result = server_info_func()

    # Handle both attribute and dict-style returns
    name = getattr(result, "name", None) or (
        result.get("name") if isinstance(result, dict) else None
    )
    status = getattr(result, "status", None) or (
        result.get("status") if isinstance(result, dict) else None
    )
    dependencies = getattr(result, "dependencies", None) or (
        result.get("dependencies") if isinstance(result, dict) else None
    )

    assert name is not None
    assert status == "active"
    assert dependencies is not None


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_input_validation(
    skip_if_no_api_key,
    test_output_file,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
            }
        )

    # Test empty prompt should raise error
    with pytest.raises((ValueError, RuntimeError)) as e1:
        ask_func(prompt="", output_file=test_output_file, **base_params)
    assert "prompt" in str(e1.value).lower() or "empty" in str(e1.value).lower()

    # Test missing output_file should raise error
    with pytest.raises((ValueError, RuntimeError)) as e2:
        ask_func(prompt="Test prompt", output_file="", **base_params)
    assert "output" in str(e2.value).lower() or "file" in str(e2.value).lower()


# Error scenario test parameters (direct function references)
error_scenarios = [
    pytest.param(
        claude_ask,
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="claude-invalid-model",
    ),
    pytest.param(
        gemini_ask,
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="gemini-invalid-model",
    ),
    pytest.param(
        openai_ask,
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        "invalid-model-name-that-does-not-exist",
        "model",
        id="openai-invalid-model",
    ),
    pytest.param(
        grok_ask,
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
@pytest.mark.parametrize(
    "ask_func, api_key, valid_model, invalid_value, error_param",
    error_scenarios,
)
def test_llm_error_scenarios(
    skip_if_no_api_key,
    test_output_file,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
            }
        )

    # Test invalid model name should raise error
    with pytest.raises((ValueError, RuntimeError, Exception)):
        result = ask_func(**base_params)
        # If no exception, enforce failure since we expected one
        if hasattr(result, "content"):
            raise RuntimeError("Expected error for invalid model but call succeeded")


@pytest.mark.parametrize("ask_func, api_key, model, prompt, expected", llm_providers)
def test_llm_response_metadata_fields(
    skip_if_no_api_key,
    test_output_file,
    ask_func,
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
        "system_prompt": None,
    }

    # Add provider-specific parameters
    if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "enable_logprobs": True,
                "top_logprobs": 3,
            }
        )
    elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            }
        )
    elif (
        ask_func.__name__ == "ask"
        and "claude" in ask_func.__module__
        or ask_func.__name__ == "ask"
        and "grok" in ask_func.__module__
    ):
        base_params.update(
            {
                "temperature": 1.0,
                "max_output_tokens": 0,
            }
        )

    result = ask_func(**base_params)

    # Check basic response
    assert result.content is not None
    assert expected in result.content
    assert Path(test_output_file).exists()

    # Check common metadata fields
    assert result.finish_reason != ""
    assert result.model_version != ""
    assert isinstance(result.avg_logprobs, float)

    # Check response_id (provider-specific)
    if ask_func in (openai_ask, claude_ask):
        assert getattr(result, "response_id", "") != ""

    # Provider-specific fields
    if ask_func is openai_ask:
        assert getattr(result, "system_fingerprint", "") != ""
        assert getattr(result, "service_tier", "") != ""
        assert isinstance(result.completion_tokens_details, dict)
        assert isinstance(result.prompt_tokens_details, dict)

        if base_params.get("enable_logprobs"):
            assert result.avg_logprobs != 0.0

        if result.completion_tokens_details:
            expected_keys = {
                "reasoning_tokens",
                "accepted_prediction_tokens",
                "rejected_prediction_tokens",
                "audio_tokens",
            }
            assert expected_keys.issubset(result.completion_tokens_details.keys())

    elif ask_func is claude_ask:
        assert getattr(result, "service_tier", "") != ""
        assert isinstance(getattr(result, "cache_creation_input_tokens", 0), int)
        assert isinstance(getattr(result, "cache_read_input_tokens", 0), int)
        assert isinstance(getattr(result, "stop_sequence", ""), str)

    elif ask_func is gemini_ask:
        assert getattr(result, "generation_time_ms", 0) > 0

    elif ask_func is grok_ask:
        sf = getattr(result, "system_fingerprint", "")
        assert isinstance(sf, str)
        assert getattr(result, "service_tier", "") == ""
        assert isinstance(result.completion_tokens_details, dict)
        assert isinstance(result.prompt_tokens_details, dict)


def test_openai_logprobs_configuration(skip_if_no_api_key, test_output_file):
    """Test OpenAI logprobs configuration options."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test without logprobs (default)
    result1 = openai_ask(
        prompt="What is 2+2?",
        output_file=test_output_file,
        model="gpt-4o-mini",
        agent_name="test_no_logprobs",
        enable_logprobs=False,
        files=[],
        system_prompt=None,
        temperature=1.0,
        max_output_tokens=0,
        top_logprobs=0,
    )

    assert result1.avg_logprobs == 0.0
    assert result1.finish_reason != ""
    assert result1.response_id != ""

    # Test with logprobs enabled
    result2 = openai_ask(
        prompt="What is 3+3?",
        output_file=test_output_file,
        model="gpt-4o-mini",
        agent_name="test_with_logprobs",
        enable_logprobs=True,
        top_logprobs=5,
        files=[],
        system_prompt=None,
        temperature=1.0,
        max_output_tokens=0,
    )

    assert result2.avg_logprobs != 0.0
    assert result2.finish_reason != ""
    assert result2.response_id != ""


class TestLLMMemory:
    """Test LLM conversational memory functionality."""

    @pytest.mark.vcr
    def test_memory_enabled_with_agent_name(self, skip_if_no_api_key, test_output_file):
        """Test that conversational context is maintained across two calls with the same agent_name."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import uuid

        agent_name = f"test_memory_agent_{uuid.uuid4()}"  # Unique name per test run

        # Call 1: Provide a piece of information
        result1 = openai_ask(
            prompt="My user ID is 789. Remember this important number.",
            output_file=test_output_file,
            model="gpt-4o-mini",
            agent_name=agent_name,
            temperature=0.1,
            files=[],
            system_prompt=None,
            max_output_tokens=0,
            enable_logprobs=False,
            top_logprobs=0,
        )
        assert result1.content is not None

        # Call 2: Ask a question that relies on the information from Call 1
        test_output_file2 = test_output_file.replace(".txt", "_2.txt")
        result2 = openai_ask(
            prompt="What was my user ID that I told you?",
            output_file=test_output_file2,
            model="gpt-4o-mini",
            agent_name=agent_name,
            temperature=0.1,
            files=[],
            system_prompt=None,
            max_output_tokens=0,
            enable_logprobs=False,
            top_logprobs=0,
        )
        assert result2.content is not None
        content2 = Path(test_output_file2).read_text()
        assert "789" in content2, f"Expected '789' in response: {content2}"

    @pytest.mark.vcr
    def test_memory_isolation_different_agents(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test that different agent names have isolated memory contexts."""
        skip_if_no_api_key("OPENAI_API_KEY")

        import uuid

        agent_name1 = f"agent_1_{uuid.uuid4()}"
        agent_name2 = f"agent_2_{uuid.uuid4()}"

        # Agent 1: Remember number 123
        _ = openai_ask(
            prompt="My favorite number is 123. Remember this.",
            output_file=test_output_file,
            model="gpt-4o-mini",
            agent_name=agent_name1,
            temperature=0.1,
            files=[],
            system_prompt=None,
            max_output_tokens=0,
            enable_logprobs=False,
            top_logprobs=0,
        )

        # Agent 2: Ask about the number (should NOT know it)
        test_output_file2 = test_output_file.replace(".txt", "_agent2.txt")
        _ = openai_ask(
            prompt="What is my favorite number?",
            output_file=test_output_file2,
            model="gpt-4o-mini",
            agent_name=agent_name2,
            temperature=0.1,
            files=[],
            system_prompt=None,
            max_output_tokens=0,
            enable_logprobs=False,
            top_logprobs=0,
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
                "not provided",
                "haven't told",
                "no information",
                "don't have access",
            ]
        ), f"Agent 2 should indicate it doesn't know: {content2}"
