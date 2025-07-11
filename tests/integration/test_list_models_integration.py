"""Integration tests for list_models function across all LLM providers."""
import pytest
from mcp_handley_lab.llm.claude.tool import list_models as claude_list_models
from mcp_handley_lab.llm.gemini.tool import list_models as gemini_list_models
from mcp_handley_lab.llm.openai.tool import list_models as openai_list_models
from mcp_handley_lab.shared.models import ModelListing


@pytest.mark.vcr
def test_claude_list_models():
    """Test Claude list_models function returns valid model listing."""
    result = claude_list_models()

    # Verify response structure
    assert isinstance(result, ModelListing)
    assert result.summary.provider == "claude"
    assert len(result.models) > 0

    # Check that we have expected Claude models
    model_names = [model.name for model in result.models]
    assert any("claude" in name.lower() for name in model_names)

    # Verify each model has required fields
    for model in result.models:
        assert model.name != ""
        assert model.pricing.input_cost_per_1m >= 0
        assert model.pricing.output_cost_per_1m >= 0
        assert model.context_window != ""


@pytest.mark.vcr
def test_gemini_list_models():
    """Test Gemini list_models function returns valid model listing."""
    result = gemini_list_models()

    # Verify response structure
    assert isinstance(result, ModelListing)
    assert result.summary.provider == "gemini"
    assert len(result.models) > 0

    # Check that we have expected Gemini models
    model_names = [model.name for model in result.models]
    assert any("gemini" in name.lower() for name in model_names)

    # Verify each model has required fields
    for model in result.models:
        assert model.name != ""
        assert model.pricing.input_cost_per_1m >= 0
        assert model.pricing.output_cost_per_1m >= 0
        assert model.context_window != ""


@pytest.mark.vcr
def test_openai_list_models():
    """Test OpenAI list_models function returns valid model listing."""
    result = openai_list_models()

    # Verify response structure
    assert isinstance(result, ModelListing)
    assert result.summary.provider == "openai"
    assert len(result.models) > 0

    # Check that we have expected OpenAI models
    model_names = [model.name for model in result.models]
    assert any("gpt" in name.lower() for name in model_names)

    # Verify each model has required fields
    for model in result.models:
        assert model.name != ""
        assert model.pricing.input_cost_per_1m >= 0
        assert model.pricing.output_cost_per_1m >= 0
        assert model.context_window != ""


@pytest.mark.vcr
def test_model_listings_consistency():
    """Test that all providers return consistent model listing structure."""
    claude_result = claude_list_models()
    gemini_result = gemini_list_models()
    openai_result = openai_list_models()

    # All should be ModelListing instances
    for result in [claude_result, gemini_result, openai_result]:
        assert isinstance(result, ModelListing)
        assert len(result.models) > 0
        assert result.summary.provider != ""
        assert len(result.categories) > 0

    # Each provider should have different provider names
    providers = {
        claude_result.summary.provider,
        gemini_result.summary.provider,
        openai_result.summary.provider,
    }
    assert len(providers) == 3
    assert "claude" in providers
    assert "gemini" in providers
    assert "openai" in providers


@pytest.mark.vcr
def test_model_capabilities_fields():
    """Test that model capabilities are properly populated."""
    # Test Claude models for specific capabilities
    claude_result = claude_list_models()

    # Find a Claude vision model
    vision_models = [
        m
        for m in claude_result.models
        if "vision" in m.capabilities or "sonnet" in m.name.lower()
    ]
    if vision_models:
        model = vision_models[0]
        assert isinstance(model.capabilities, list)

    # Test Gemini models
    gemini_result = gemini_list_models()

    # Gemini should have both text and vision models
    model_caps = [model.capabilities for model in gemini_result.models]
    assert len(model_caps) > 0

    # Test OpenAI models
    openai_result = openai_list_models()

    # OpenAI should have GPT models
    gpt_models = [m for m in openai_result.models if "gpt" in m.name.lower()]
    assert len(gpt_models) > 0

    for model in gpt_models[:3]:  # Check first 3 GPT models
        assert isinstance(model.capabilities, list)


@pytest.mark.vcr
def test_model_pricing_consistency():
    """Test that model pricing information is reasonable and consistent."""
    for provider_func in [claude_list_models, gemini_list_models, openai_list_models]:
        result = provider_func()

        for model in result.models:
            # Skip image/video models which have different pricing structure
            if model.pricing.type in ["per_image", "per_second"]:
                continue

            # Input cost should be reasonable (less than $10,000 per 1M tokens)
            assert 0 <= model.pricing.input_cost_per_1m <= 10000

            # Output cost should be reasonable
            assert 0 <= model.pricing.output_cost_per_1m <= 50000

            # Context window should be meaningful
            assert model.context_window != ""


if __name__ == "__main__":
    # Run basic smoke tests
    print("Testing Claude list_models...")
    claude_result = claude_list_models()
    print(f"✅ Claude: {len(claude_result.models)} models available")

    print("Testing Gemini list_models...")
    gemini_result = gemini_list_models()
    print(f"✅ Gemini: {len(gemini_result.models)} models available")

    print("Testing OpenAI list_models...")
    openai_result = openai_list_models()
    print(f"✅ OpenAI: {len(openai_result.models)} models available")

    print("✅ All list_models functions working correctly!")
