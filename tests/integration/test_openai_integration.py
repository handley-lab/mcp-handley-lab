from pathlib import Path

import pytest
from mcp_handley_lab.llm.openai.tool import (
    analyze_image,
    ask,
    generate_image,
    server_info,
)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_ask_basic(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("OPENAI_API_KEY")

    result = await ask(
        prompt="What is 2+2? Answer with just the number.",
        output_file=test_output_file,
        model="gpt-4o-mini",
        temperature=0.0,
        agent_name=False,
    )

    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "4" in content


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_ask_with_file(
    skip_if_no_api_key, test_output_file, test_json_file
):
    skip_if_no_api_key("OPENAI_API_KEY")

    result = await ask(
        prompt="What is in this JSON file?",
        output_file=test_output_file,
        files=[{"path": test_json_file}],
        model="gpt-4o-mini",
        agent_name=False,
    )

    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "test" in content.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_ask_with_agent(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("OPENAI_API_KEY")

    # First message
    result1 = await ask(
        prompt="My name is Alice. Remember this.",
        output_file=test_output_file,
        agent_name="memory_test",
        model="gpt-4o-mini",
    )
    assert "saved" in result1.lower()

    # Second message referencing first
    result2 = await ask(
        prompt="What is my name?",
        output_file=test_output_file,
        agent_name="memory_test",
        model="gpt-4o-mini",
    )
    assert "saved" in result2.lower()
    content = Path(test_output_file).read_text()
    assert "alice" in content.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_analyze_image_simple(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("OPENAI_API_KEY")

    # Use a simple base64 red pixel image
    red_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    result = await analyze_image(
        prompt="What color is this image?",
        output_file=test_output_file,
        image_data=red_pixel,
        focus="colors",
        model="gpt-4o",  # Use gpt-4o for vision tasks since o3-mini doesn't support vision
        agent_name=False,
    )

    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert any(
        color in content.lower() for color in ["red", "yellow", "orange", "color"]
    )


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_generate_image(skip_if_no_api_key):
    skip_if_no_api_key("OPENAI_API_KEY")

    result = await generate_image(
        prompt="A simple red circle on white background",
        model="dall-e-2",
        size="256x256",
    )

    assert "saved" in result.lower() or "success" in result.lower()
    assert "image saved" in result.lower() or ".png" in result


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_server_info(skip_if_no_api_key):
    skip_if_no_api_key("OPENAI_API_KEY")

    result = await server_info()

    assert "openai" in result.lower()
    assert "status" in result.lower()


# NEW VCR-BASED TESTS TO REPLACE MOCKED COMPREHENSIVE TESTS


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_memory_disabled_integration(skip_if_no_api_key, test_output_file):
    """Test ask function with memory explicitly disabled (agent_name=False)."""
    skip_if_no_api_key("OPENAI_API_KEY")

    result = await ask(
        prompt="What is 9+6? Just answer with the number.",
        output_file=test_output_file,
        agent_name=False,  # Explicitly disable memory
        model="gpt-4o-mini",
        temperature=0.0,
    )

    assert "saved" in result.lower() or "success" in result.lower()
    assert "tokens" in result.lower()  # Should show token stats for non-memory mode
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "15" in content


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_conversation_memory_integration(
    skip_if_no_api_key, test_output_file
):
    """Test conversation memory persistence with OpenAI."""
    skip_if_no_api_key("OPENAI_API_KEY")

    agent_name = "openai_memory_test"

    # First interaction - establish context
    result1 = await ask(
        prompt="My favorite programming language is Python. Remember this fact.",
        output_file=test_output_file,
        agent_name=agent_name,
        model="gpt-4o-mini",
    )
    assert "saved" in result1.lower()

    # Second interaction - test memory recall
    result2 = await ask(
        prompt="What programming language did I say was my favorite?",
        output_file=test_output_file + "_2",
        agent_name=agent_name,
        model="gpt-4o-mini",
    )
    assert "saved" in result2.lower()

    # Verify memory worked
    content2 = Path(test_output_file + "_2").read_text()
    assert "python" in content2.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_multiple_file_types_integration(
    skip_if_no_api_key, test_output_file, tmp_path
):
    """Test file handling with various formats (VCR replacement for mocked file resolution tests)."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Create test files of different types
    text_file = tmp_path / "instructions.txt"
    text_file.write_text("Build a calculator app using FRAMEWORK_X")

    json_file = tmp_path / "config.json"
    json_file.write_text(
        '{"framework": "FRAMEWORK_X", "version": "2.1", "features": ["math", "gui"]}'
    )

    # Test with multiple files and content types
    result = await ask(
        prompt="What framework should I use for the calculator based on these files?",
        output_file=test_output_file,
        files=[
            {"path": str(text_file)},
            {"path": str(json_file)},
            {"content": "Note: FRAMEWORK_X is the recommended choice for this project"},
        ],
        model="gpt-4o-mini",
        agent_name=False,
    )

    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "framework_x" in content.lower() or "framework x" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_model_variants_integration(skip_if_no_api_key, test_output_file):
    """Test different OpenAI model variants work correctly."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test gpt-4o-mini model (supports temperature)
    result = await ask(
        prompt="Explain photosynthesis in one sentence.",
        output_file=test_output_file,
        model="gpt-4o-mini",
        max_output_tokens=50,
        agent_name=False,
    )

    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert len(content) > 20  # Should have substantial content
    assert "photosynth" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_temperature_variations_integration(
    skip_if_no_api_key, test_output_file
):
    """Test different temperature settings (VCR replacement for mocked temperature tests)."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test with very low temperature (deterministic)
    result = await ask(
        prompt="Say exactly: DETERMINISTIC_RESPONSE",
        output_file=test_output_file,
        temperature=0.0,
        model="gpt-4o-mini",
        agent_name=False,
    )

    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "DETERMINISTIC_RESPONSE" in content


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_image_analysis_focus_options_integration(
    skip_if_no_api_key, test_output_file
):
    """Test different image analysis focus options (VCR replacement for mocked image tests)."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Create a more complex test image with text
    import base64
    import io

    from PIL import Image, ImageDraw

    # Create an image with text and colors
    img = Image.new("RGB", (100, 50), color="green")
    draw = ImageDraw.Draw(img)
    # Use default font since we can't guarantee font availability
    draw.text((10, 10), "WORLD", fill="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_data = base64.b64encode(img_buffer.getvalue()).decode()

    # Test text focus
    result = await analyze_image(
        prompt="What text do you see in this image?",
        output_file=test_output_file,
        image_data=f"data:image/png;base64,{img_data}",
        focus="text",
        model="gpt-4o",  # Use vision-capable model
        agent_name=False,
    )

    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "world" in content.lower() or "text" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_custom_token_limits_integration(
    skip_if_no_api_key, test_output_file
):
    """Test that custom max_output_tokens parameter works with real API."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test with low token limit
    result = await ask(
        prompt="Write a brief definition of recursion in programming.",
        output_file=test_output_file,
        model="gpt-4o-mini",
        max_output_tokens=50,
        agent_name=False,
    )

    assert "saved" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "recurs" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_image_generation_variants_integration(skip_if_no_api_key):
    """Test different image generation models and settings."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test DALL-E 3 with high quality
    result = await generate_image(
        prompt="A minimalist logo: blue triangle on white background",
        model="dall-e-3",
        quality="hd",
        size="1024x1024",
        agent_name=False,
    )

    assert "image saved" in result.lower() or ".png" in result
    assert "success" in result.lower() or "saved" in result.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_analyze_image_token_limits_integration(
    skip_if_no_api_key, test_output_file
):
    """Test that analyze_image respects custom token limits."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Create a simple test image
    import base64
    import io

    from PIL import Image

    # Create a 10x10 yellow square
    img = Image.new("RGB", (10, 10), color="yellow")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_data = base64.b64encode(img_buffer.getvalue()).decode()

    result = await analyze_image(
        prompt="What color is this image? Just say the color.",
        output_file=test_output_file,
        image_data=f"data:image/png;base64,{img_data}",
        max_output_tokens=30,
        agent_name=False,
        model="gpt-4o",  # Vision-capable model
    )

    assert "saved" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "yellow" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_openai_input_validation_integration(
    skip_if_no_api_key, test_output_file
):
    """Test input validation with real API (ensures validation works before API calls)."""
    skip_if_no_api_key("OPENAI_API_KEY")

    # Test empty prompt validation
    with pytest.raises(ValueError, match="Prompt is required"):
        await ask(prompt="", output_file=test_output_file)

    # Test empty output file validation
    with pytest.raises(ValueError, match="Output file is required"):
        await ask(prompt="Test", output_file="")

    # Test empty agent name validation
    with pytest.raises(ValueError, match="Agent name cannot be empty"):
        await ask(
            prompt="Test",
            output_file=test_output_file,
            agent_name="   ",  # Whitespace only
        )
