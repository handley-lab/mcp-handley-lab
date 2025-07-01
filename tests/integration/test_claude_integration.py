"""Integration tests for Claude LLM tool."""
import pytest
import tempfile
from pathlib import Path
from mcp_handley_lab.llm.claude.tool import ask, analyze_image, server_info


@pytest.mark.asyncio
@pytest.mark.vcr  
async def test_claude_ask_basic(skip_if_no_api_key, test_output_file):
    """Test basic Claude text generation."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    result = await ask(
        prompt="What is 5+5? Answer with just the number.",
        output_file=test_output_file,
        model="claude-3-5-haiku-20241022",  # Use fastest model for tests
        temperature=0.0,
        agent_name=False  # Disable memory for clean test
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "10" in content


@pytest.mark.asyncio 
@pytest.mark.vcr
async def test_claude_ask_with_files(skip_if_no_api_key, test_output_file, tmp_path):
    """Test Claude with file input."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\nThis is a test file.")
    
    result = await ask(
        prompt="What is the content of this file?",
        output_file=test_output_file,
        files=[{"path": str(test_file)}],
        model="claude-3-5-haiku-20241022",
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "Hello World" in content or "test file" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_analyze_image_simple(skip_if_no_api_key, test_output_file, create_test_image):
    """Test Claude image analysis with a simple test image."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    # Create simple red square image
    image_path = create_test_image("red_square.png", color="red", size=(100, 100))
    
    result = await analyze_image(
        prompt="What color is this image?",
        output_file=test_output_file,
        image_data=str(image_path),
        model="claude-3-5-sonnet-20240620",  # Use vision-capable model
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_analyze_image_multiple(skip_if_no_api_key, test_output_file, create_test_image):
    """Test Claude image analysis with multiple images."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    # Create test images
    red_image = create_test_image("red.png", color="red", size=(50, 50))
    blue_image = create_test_image("blue.png", color="blue", size=(50, 50))
    
    result = await analyze_image(
        prompt="Compare these two images and tell me what colors they are.",
        output_file=test_output_file,
        images=[{"path": str(red_image)}, {"path": str(blue_image)}],
        model="claude-3-5-sonnet-20240620",
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    # Should mention both colors
    assert "red" in content.lower() and "blue" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_memory_disabled(skip_if_no_api_key, test_output_file):
    """Test Claude with memory explicitly disabled."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    result = await ask(
        prompt="Remember this: my favorite color is purple.",
        output_file=test_output_file,
        model="claude-3-5-haiku-20241022",
        agent_name=False  # Explicitly disable memory
    )
    
    assert "saved" in result.lower()
    
    # Second request should not remember the first
    result2 = await ask(
        prompt="What is my favorite color?",
        output_file=test_output_file + "2",
        model="claude-3-5-haiku-20241022", 
        agent_name=False
    )
    
    content2 = Path(test_output_file + "2").read_text()
    # Should not know the favorite color since memory is disabled
    assert "purple" not in content2.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_server_info(skip_if_no_api_key):
    """Test Claude server info endpoint."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    result = await server_info()
    
    assert "Claude Tool Server Status" in result
    assert "Connected and ready" in result
    assert "API Key: Configured" in result
    assert "Available Models:" in result
    assert "claude-3" in result.lower()
    assert "ask:" in result
    assert "analyze_image:" in result
    assert "Image Generation: ✗" in result  # Claude doesn't support image generation


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_model_aliases(skip_if_no_api_key, test_output_file):
    """Test Claude model aliases work correctly."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    # Test using alias instead of full model name
    result = await ask(
        prompt="What is 2+2? Answer with just the number.",
        output_file=test_output_file,
        model="haiku",  # Using alias instead of full name
        temperature=0.0,
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "4" in content


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_claude_max_tokens_override(skip_if_no_api_key, test_output_file):
    """Test Claude with custom max tokens."""
    skip_if_no_api_key("ANTHROPIC_API_KEY")
    
    result = await ask(
        prompt="Write a very short sentence about cats.",
        output_file=test_output_file,
        model="claude-3-5-haiku-20241022",
        max_output_tokens=20,  # Very small limit
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    # Should be a short response due to token limit
    assert len(content.split()) < 50  # Should be quite short
    assert "cat" in content.lower()