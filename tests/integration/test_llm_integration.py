"""Unified integration tests for all LLM providers (Claude, Gemini, OpenAI)."""
from pathlib import Path

import pytest
from mcp_handley_lab.llm.claude.tool import analyze_image as claude_analyze_image
from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.claude.tool import server_info as claude_server_info
from mcp_handley_lab.llm.gemini.tool import analyze_image as gemini_analyze_image
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.gemini.tool import server_info as gemini_server_info
from mcp_handley_lab.llm.openai.tool import analyze_image as openai_analyze_image
from mcp_handley_lab.llm.openai.tool import ask as openai_ask
from mcp_handley_lab.llm.openai.tool import server_info as openai_server_info
from PIL import Image

# Define provider-specific parameters
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
]

server_info_providers = [
    pytest.param(claude_server_info, "ANTHROPIC_API_KEY", id="claude"),
    pytest.param(gemini_server_info, "GEMINI_API_KEY", id="gemini"),
    pytest.param(openai_server_info, "OPENAI_API_KEY", id="openai"),
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
    skip_if_no_api_key, test_output_file, ask_func, api_key, model, question, answer
):
    """Test basic text generation for all LLM providers."""
    skip_if_no_api_key(api_key)

    result = ask_func(
        prompt=f"What is {question}? Answer with just the number.",
        output_file=test_output_file,
        model=model,
        temperature=0.0,
        agent_name=False,
    )

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

    result = ask_func(
        prompt="What is in this file?",
        output_file=test_output_file,
        files=[str(test_file)],
        model=model,
        agent_name=False,
    )

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

    result = analyze_func(
        prompt="What color is this image?",
        output_file=test_output_file,
        files=[str(image_path)],
        model=model,
        agent_name=False,  # Disable memory for clean test
    )

    assert result.content is not None
    assert len(result.content) > 0
    assert result.usage.input_tokens > 0
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_memory_disabled(
    skip_if_no_api_key, test_output_file, ask_func, api_key, model, question, answer
):
    """Test that memory is properly disabled when agent_name=False."""
    skip_if_no_api_key(api_key)

    result = ask_func(
        prompt=f"Remember this number: {answer}. What is {question}?",
        output_file=test_output_file,
        model=model,
        temperature=0.0,
        agent_name=False,
    )

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

    # Handle both string and ServerInfo object returns
    if hasattr(result, "name"):
        # ServerInfo object
        assert "server" in result.name.lower() or "tool" in result.name.lower()
        assert result.status == "active"
        assert result.dependencies
    else:
        # String return
        assert result.status == "active"
        assert "Tool" in result.name


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func, api_key, model, question, answer", llm_providers)
def test_llm_input_validation(
    skip_if_no_api_key, test_output_file, ask_func, api_key, model, question, answer
):
    """Test input validation for all LLM providers."""
    skip_if_no_api_key(api_key)

    # Test empty prompt should raise ValueError
    with pytest.raises(ValueError, match="prompt.*required|empty"):
        ask_func(
            prompt="",
            output_file=test_output_file,
            model=model,
            agent_name=False,
        )

    # Test missing output_file should raise ValueError
    with pytest.raises(ValueError, match="Output file.*required"):
        ask_func(
            prompt="Test prompt",
            output_file="",
            model=model,
            agent_name=False,
        )


# Error scenario test parameters
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
]


@pytest.mark.vcr
@pytest.mark.parametrize(
    "ask_func, api_key, valid_model, invalid_value, error_param", error_scenarios
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

    # Test invalid model name should raise error (various exception types possible)
    with pytest.raises((ValueError, RuntimeError, Exception)):
        ask_func(
            prompt="Test prompt",
            output_file=test_output_file,
            model=invalid_value if error_param == "model" else valid_model,
            agent_name=False,
        )


@pytest.mark.vcr
@pytest.mark.parametrize("ask_func,api_key,model,prompt,expected", llm_providers)
def test_llm_response_metadata_fields(
    skip_if_no_api_key, test_output_file, ask_func, api_key, model, prompt, expected
):
    """Test that all LLM providers return comprehensive metadata fields."""
    skip_if_no_api_key(api_key)

    # Test OpenAI with logprobs enabled if it's OpenAI
    kwargs = {}
    if "openai" in str(ask_func):
        kwargs.update({"enable_logprobs": True, "top_logprobs": 3})

    result = ask_func(
        prompt=prompt,
        output_file=test_output_file,
        model=model,
        agent_name="test_metadata",
        **kwargs,
    )

    # Check basic response
    assert result.content is not None
    assert expected in result.content
    assert Path(test_output_file).exists()

    # Check common metadata fields
    assert result.finish_reason != ""
    assert result.model_version != ""
    assert isinstance(result.avg_logprobs, float)

    # Check response_id (provider-specific)
    if "openai" in str(ask_func) or "claude" in str(ask_func):
        assert result.response_id != ""

    # Check provider-specific fields
    if "openai" in str(ask_func):
        # OpenAI-specific fields
        assert result.system_fingerprint != ""
        assert result.service_tier != ""
        assert isinstance(result.completion_tokens_details, dict)
        assert isinstance(result.prompt_tokens_details, dict)

        # Check logprobs were captured when enabled
        if kwargs.get("enable_logprobs"):
            assert result.avg_logprobs != 0.0

        # Check token details structure
        if result.completion_tokens_details:
            expected_keys = {
                "reasoning_tokens",
                "accepted_prediction_tokens",
                "rejected_prediction_tokens",
                "audio_tokens",
            }
            assert expected_keys.issubset(result.completion_tokens_details.keys())

    elif "claude" in str(ask_func):
        # Claude-specific fields
        assert result.service_tier != ""
        assert isinstance(result.cache_creation_input_tokens, int)
        assert isinstance(result.cache_read_input_tokens, int)
        # stop_sequence can be empty string for normal completion
        assert isinstance(result.stop_sequence, str)

    elif "gemini" in str(ask_func):
        # Gemini has generation_time_ms
        assert result.generation_time_ms > 0


@pytest.mark.vcr
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
    )

    # Should have basic metadata but no meaningful logprobs
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
    )

    # Should have meaningful logprobs
    assert result2.avg_logprobs != 0.0
    assert result2.finish_reason != ""
    assert result2.response_id != ""
