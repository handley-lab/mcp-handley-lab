"""Integration tests for unified list_models function."""

from mcp_handley_lab.llm.tool import list_models


def test_list_models_returns_all_providers():
    """Test list_models returns models for all providers."""
    result = list_models()

    # Should have models for major providers
    assert "claude" in result
    assert "gemini" in result
    assert "openai" in result
    assert "mistral" in result
    assert "grok" in result
    assert "groq" in result


def test_list_models_claude_models():
    """Test Claude models are included in list_models result."""
    result = list_models()

    # Verify Claude models exist
    assert len(result["claude"]) > 0

    # Check that we have expected Claude models
    model_ids = [model["id"] for model in result["claude"]]
    assert any("claude" in name.lower() for name in model_ids)

    # Verify each model has required fields
    for model in result["claude"]:
        assert model["id"] != ""
        assert "capabilities" in model
        assert "context_window" in model


def test_list_models_gemini_models():
    """Test Gemini models are included in list_models result."""
    result = list_models()

    # Verify Gemini models exist
    assert len(result["gemini"]) > 0

    # Check that we have expected Gemini models
    model_ids = [model["id"] for model in result["gemini"]]
    assert any("gemini" in name.lower() for name in model_ids)

    # Verify each model has required fields
    for model in result["gemini"]:
        assert model["id"] != ""
        assert "capabilities" in model
        assert "context_window" in model


def test_list_models_openai_models():
    """Test OpenAI models are included in list_models result."""
    result = list_models()

    # Verify OpenAI models exist
    assert len(result["openai"]) > 0

    # Check that we have expected OpenAI models
    model_ids = [model["id"] for model in result["openai"]]
    assert any("gpt" in name.lower() for name in model_ids)

    # Verify each model has required fields
    for model in result["openai"]:
        assert model["id"] != ""
        assert "capabilities" in model
        assert "context_window" in model


def test_list_models_structure_consistency():
    """Test that all providers have consistent model structure."""
    result = list_models()

    for provider in ["claude", "gemini", "openai", "mistral", "grok", "groq"]:
        if provider not in result or len(result[provider]) == 0:
            continue

        for model in result[provider]:
            # All models should have these keys
            assert "id" in model
            assert "description" in model
            assert "context_window" in model
            assert "tags" in model
            assert "capabilities" in model
            assert "supported_options" in model

            # Capabilities should be a dict with boolean values
            caps = model["capabilities"]
            assert isinstance(caps, dict)
            assert "vision" in caps
            assert isinstance(caps["vision"], bool)


def test_list_models_capabilities():
    """Test that model capabilities are properly populated."""
    result = list_models()

    # Find models with vision capability
    vision_models = []
    for provider, models in result.items():
        for model in models:
            if model["capabilities"].get("vision", False):
                vision_models.append((provider, model))

    # Should have some vision-capable models
    assert len(vision_models) > 0

    # Find models with reasoning capability
    reasoning_models = []
    for provider, models in result.items():
        for model in models:
            if model["capabilities"].get("reasoning", False):
                reasoning_models.append((provider, model))

    # Reasoning models should exist (o-series, gemini with thinking, etc.)
    assert len(reasoning_models) > 0


if __name__ == "__main__":
    # Run basic smoke test
    print("Testing unified list_models...")
    result = list_models()

    total_models = sum(len(models) for models in result.values())
    print(f"✅ Total: {total_models} models available")

    for provider, models in result.items():
        print(f"  {provider}: {len(models)} models")

    print("✅ list_models working correctly!")
