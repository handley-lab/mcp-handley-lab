import pytest
import tempfile
from pathlib import Path
from mcp_handley_lab.llm.openai.tool import ask, analyze_image, generate_image, server_info

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_ask_basic(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("OPENAI_API_KEY")
    
    result = await ask(
        prompt="What is 2+2? Answer with just the number.",
        output_file=test_output_file,
        model="gpt-4o-mini",
        temperature=0.0
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "4" in content

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_ask_with_file(skip_if_no_api_key, test_output_file, test_json_file):
    skip_if_no_api_key("OPENAI_API_KEY")
    
    result = await ask(
        prompt="What is in this JSON file?",
        output_file=test_output_file,
        files=[{"path": test_json_file}],
        model="gpt-4o-mini"
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
        model="gpt-4o-mini"
    )
    assert "saved" in result1.lower()
    
    # Second message referencing first
    result2 = await ask(
        prompt="What is my name?",
        output_file=test_output_file,
        agent_name="memory_test",
        model="gpt-4o-mini"
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
        model="gpt-4o"  # Use gpt-4o for vision tasks since o3-mini doesn't support vision
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert any(color in content.lower() for color in ["red", "yellow", "orange", "color"])

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_openai_generate_image(skip_if_no_api_key):
    skip_if_no_api_key("OPENAI_API_KEY")
    
    result = await generate_image(
        prompt="A simple red circle on white background",
        model="dall-e-2",
        size="256x256"
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