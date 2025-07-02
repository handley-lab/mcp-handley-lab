import pytest
import tempfile
from pathlib import Path
from mcp_handley_lab.llm.gemini.tool import ask, analyze_image, generate_image, server_info
from mcp_handley_lab.agent.tool import create_agent, list_agents, agent_stats, clear_agent, delete_agent

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_ask_basic(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await ask(
        prompt="What is 3+3? Answer with just the number.",
        output_file=test_output_file,
        model="gemini-2.5-flash",
        temperature=0.0
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "6" in content

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_ask_with_grounding_1_5(skip_if_no_api_key, test_output_file):
    """Test grounding with Gemini 1.5 models (legacy GoogleSearchRetrieval)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await ask(
        prompt="What is the current date today?",
        output_file=test_output_file,
        grounding=True,
        model="gemini-1.5-pro"  # Use 1.5 model with GoogleSearchRetrieval
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "2025" in content

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_ask_with_grounding_2_5(skip_if_no_api_key, test_output_file):
    """Test grounding with Gemini 2.5 models (recommended GoogleSearch)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await ask(
        prompt="What is the current date today?",
        output_file=test_output_file,
        grounding=True,
        model="gemini-2.5-flash"  # Use 2.5 model with GoogleSearch
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "2025" in content

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_ask_with_file(skip_if_no_api_key, test_output_file, test_json_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await ask(
        prompt="What data is in this JSON file?",
        output_file=test_output_file,
        files=[{"path": test_json_file}],
        model="gemini-2.5-flash"
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "test" in content.lower()

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_agent_lifecycle(skip_if_no_api_key, test_output_file, temp_storage_dir):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    agent_name = "test_agent_lifecycle"
    
    # Clean up any existing agent from previous test runs
    try:
        await delete_agent(agent_name=agent_name)
    except (ValueError, RuntimeError):
        pass  # Agent doesn't exist, which is fine
    
    # Create agent
    result = await create_agent(
        agent_name=agent_name,
        personality="You are a helpful assistant"
    )
    assert "created" in result.lower()
    
    # List agents
    result = await list_agents()
    assert agent_name in result
    
    # Ask with agent
    result = await ask(
        prompt="Remember my favorite color is blue",
        output_file=test_output_file,
        agent_name=agent_name
    )
    assert "saved" in result.lower() or "success" in result.lower()
    
    # Get stats
    result = await agent_stats(agent_name=agent_name)
    assert agent_name in result
    assert "messages" in result.lower()
    
    # Clear agent
    result = await clear_agent(agent_name=agent_name)
    assert "cleared" in result.lower()
    
    # Delete agent
    result = await delete_agent(agent_name=agent_name)
    assert "deleted" in result.lower()

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_analyze_image(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Simple red pixel image
    red_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    result = await analyze_image(
        prompt="What color is dominant in this image?",
        output_file=test_output_file,
        image_data=red_pixel,
        focus="colors",
        model="gemini-2.5-pro"  # Use pro model for better analysis
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert any(color in content.lower() for color in ["red", "yellow", "orange", "color"])

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_generate_image(skip_if_no_api_key):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await generate_image(
        prompt="A simple blue square"
    )
    
    assert "saved" in result.lower() or "success" in result.lower() or ".png" in result

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_server_info(skip_if_no_api_key):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await server_info()
    
    assert "gemini" in result.lower()
    assert "status" in result.lower()

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_custom_token_limits(skip_if_no_api_key, test_output_file):
    """Test that custom max_output_tokens parameter works with real API."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test with very low token limit - should still work but be brief
    result = await ask(
        prompt="Say exactly: SUCCESS",
        output_file=test_output_file,
        model="gemini-2.5-flash",
        max_output_tokens=50,
        agent_name=False
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "SUCCESS" in content

@pytest.mark.asyncio
@pytest.mark.vcr  
async def test_gemini_high_token_limits(skip_if_no_api_key, test_output_file):
    """Test that high token limits work with 2.5 models."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test with higher token limit using gemini-2.5-flash
    result = await ask(
        prompt="Write a brief explanation of photosynthesis in plants.",
        output_file=test_output_file,
        model="gemini-2.5-flash",
        max_output_tokens=1000,
        agent_name=False
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert len(content) > 50  # Should be a substantial response
    assert "photosynthesis" in content.lower()

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_analyze_image_token_limits(skip_if_no_api_key, test_output_file):
    """Test that analyze_image respects custom token limits."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Create a simple test image (small red square)
    from PIL import Image
    import io
    import base64
    
    # Create a 10x10 red square
    img = Image.new('RGB', (10, 10), color='red')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_data = base64.b64encode(img_buffer.getvalue()).decode()
    
    result = await analyze_image(
        prompt="What color is this image? Just say the color.",
        output_file=test_output_file,
        image_data=f"data:image/png;base64,{img_data}",
        max_output_tokens=100,  # Reasonable limit for simple color identification
        agent_name=False,
        model="gemini-2.5-flash"  # Explicitly specify model
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()


# NEW VCR-BASED TESTS TO REPLACE MOCKED COMPREHENSIVE TESTS

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_memory_disabled_integration(skip_if_no_api_key, test_output_file):
    """Test ask function with memory explicitly disabled (agent_name=False)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = await ask(
        prompt="What is 7+8? Just answer with the number.",
        output_file=test_output_file,
        agent_name=False,  # Explicitly disable memory
        model="gemini-2.5-flash",
        temperature=0.0
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert "tokens" in result.lower()  # Should show token stats for non-memory mode
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "15" in content


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_conversation_history_integration(skip_if_no_api_key, test_output_file, temp_storage_dir):
    """Test conversation history with real agent memory (VCR replacement for mocked history tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    agent_name = "conv_history_test"
    
    # Clean up any existing agent
    try:
        await delete_agent(agent_name=agent_name)
    except (ValueError, RuntimeError):
        pass
    
    # Create agent with personality
    await create_agent(
        agent_name=agent_name,
        personality="You are a math tutor who always shows your work step by step"
    )
    
    # First interaction - teach something
    result1 = await ask(
        prompt="Remember that I'm learning multiplication tables. What is 6 x 7?",
        output_file=test_output_file,
        agent_name=agent_name,
        model="gemini-2.5-flash"
    )
    assert "saved" in result1.lower()
    
    # Second interaction - test memory and personality persistence
    result2 = await ask(
        prompt="Now test me: what multiplication problem did I just ask about?",
        output_file=test_output_file + "_2",
        agent_name=agent_name,
        model="gemini-2.5-flash"
    )
    assert "saved" in result2.lower()
    
    # Verify the agent remembered the previous interaction
    content2 = Path(test_output_file + "_2").read_text()
    assert "6" in content2 and "7" in content2  # Should remember the 6x7 question
    
    # Clean up
    await delete_agent(agent_name=agent_name)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_multiple_file_types_integration(skip_if_no_api_key, test_output_file, tmp_path):
    """Test file handling with various formats (VCR replacement for mocked file resolution tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Create test files of different types
    text_file = tmp_path / "test.txt"
    text_file.write_text("This is a test text file with important data: PROJECT_X")
    
    json_file = tmp_path / "test.json"
    json_file.write_text('{"project": "PROJECT_X", "status": "active", "count": 42}')
    
    # Test with multiple files
    result = await ask(
        prompt="What project name appears in both files?",
        output_file=test_output_file,
        files=[
            {"path": str(text_file)},
            {"path": str(json_file)},
            {"content": "Additional context: PROJECT_X is the main project"}
        ],
        model="gemini-2.5-flash",
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "PROJECT_X" in content or "project_x" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_temperature_variations_integration(skip_if_no_api_key, test_output_file):
    """Test different temperature settings (VCR replacement for mocked temperature tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test with very low temperature (deterministic)
    result = await ask(
        prompt="Say exactly: DETERMINISTIC_TEST",
        output_file=test_output_file,
        temperature=0.0,
        model="gemini-2.5-flash",
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "DETERMINISTIC_TEST" in content


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_image_analysis_focus_options_integration(skip_if_no_api_key, test_output_file):
    """Test different image analysis focus options (VCR replacement for mocked image tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Create a more complex test image with text
    from PIL import Image, ImageDraw, ImageFont
    import io
    import base64
    
    # Create an image with text and colors
    img = Image.new('RGB', (100, 50), color='blue')
    draw = ImageDraw.Draw(img)
    # Use default font since we can't guarantee font availability
    draw.text((10, 10), "HELLO", fill='white')
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_data = base64.b64encode(img_buffer.getvalue()).decode()
    
    # Test text focus
    result = await analyze_image(
        prompt="What text do you see in this image?",
        output_file=test_output_file,
        image_data=f"data:image/png;base64,{img_data}",
        focus="text",
        model="gemini-2.5-pro",
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert "hello" in content.lower() or "text" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_model_variants_integration(skip_if_no_api_key, test_output_file):
    """Test different model variants work correctly (VCR replacement for mocked model tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test gemini-2.5-pro model
    result = await ask(
        prompt="Write a very brief explanation of what prime numbers are.",
        output_file=test_output_file,
        model="gemini-2.5-pro", 
        agent_name=False
    )
    
    assert "saved" in result.lower()
    content = Path(test_output_file).read_text()
    assert len(content) > 10  # Should have substantial content
    assert "prime" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_session_memory_vs_named_agent_integration(skip_if_no_api_key, test_output_file, temp_storage_dir):
    """Test session memory vs named agent behavior (VCR replacement for memory manager mocking)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test 1: Named agent for consistent memory
    test_agent1 = "session_memory_test"
    try:
        await delete_agent(agent_name=test_agent1)
    except (ValueError, RuntimeError):
        pass
    
    await create_agent(agent_name=test_agent1)
    
    result1 = await ask(
        prompt="Remember that my favorite number is 42",
        output_file=test_output_file + "_session1",
        agent_name=test_agent1,
        model="gemini-2.5-flash"
    )
    assert "saved" in result1.lower()
    
    result2 = await ask(
        prompt="What is my favorite number?",
        output_file=test_output_file + "_session2",
        agent_name=test_agent1,
        model="gemini-2.5-flash"
    )
    assert "saved" in result2.lower()
    content2 = Path(test_output_file + "_session2").read_text()
    assert "42" in content2
    
    # Clean up
    await delete_agent(agent_name=test_agent1)
    
    # Test 2: Named agent (cross-session persistence)
    named_agent = "test_named_memory"
    try:
        await delete_agent(agent_name=named_agent)
    except (ValueError, RuntimeError):
        pass
    
    await create_agent(agent_name=named_agent)
    
    result3 = await ask(
        prompt="My lucky number is 777",
        output_file=test_output_file + "_named1",
        agent_name=named_agent,
        model="gemini-2.5-flash"
    )
    assert "saved" in result3.lower()
    
    result4 = await ask(
        prompt="What is my lucky number?",
        output_file=test_output_file + "_named2",
        agent_name=named_agent,
        model="gemini-2.5-flash"
    )
    assert "saved" in result4.lower()
    content4 = Path(test_output_file + "_named2").read_text()
    assert "777" in content4
    
    # Clean up
    await delete_agent(agent_name=named_agent)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_image_generation_integration(skip_if_no_api_key):
    """Test image generation with different prompts (VCR replacement for mocked generation tests)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test basic image generation
    result = await generate_image(
        prompt="A simple geometric shape: blue circle",
        agent_name=False
    )
    
    assert "image generated" in result.lower() or ".png" in result
    assert "success" in result.lower() or "saved" in result.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_input_validation_integration(skip_if_no_api_key, test_output_file):
    """Test input validation with real API (ensures validation works before API calls)."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test empty prompt validation
    with pytest.raises(ValueError, match="Prompt is required"):
        await ask(
            prompt="",
            output_file=test_output_file
        )
    
    # Test empty output file validation
    with pytest.raises(ValueError, match="Output file is required"):
        await ask(
            prompt="Test",
            output_file=""
        )
    
    # Test empty agent name validation
    with pytest.raises(ValueError, match="Agent name cannot be empty"):
        await ask(
            prompt="Test",
            output_file=test_output_file,
            agent_name="   "  # Whitespace only
        )


# Memory functionality is tested through the async function-based tests above
# which use VCR cassettes efficiently. JSON-RPC subprocess tests removed
# because VCR cannot intercept HTTP calls made by subprocess processes.
