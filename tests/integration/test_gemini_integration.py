import pytest
import tempfile
from pathlib import Path
from mcp_handley_lab.llm.gemini.tool import ask, analyze_image, generate_image, create_agent, list_agents, agent_stats, clear_agent, delete_agent, server_info

@pytest.mark.vcr
def test_gemini_ask_basic(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = ask(
        prompt="What is 3+3? Answer with just the number.",
        output_file=test_output_file,
        model="flash",
        temperature=0.0
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "6" in content

@pytest.mark.vcr
def test_gemini_ask_with_grounding(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = ask(
        prompt="What is the current date today?",
        output_file=test_output_file,
        grounding=True,
        model="flash"
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "2025" in content

@pytest.mark.vcr
def test_gemini_ask_with_file(skip_if_no_api_key, test_output_file, test_json_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = ask(
        prompt="What data is in this JSON file?",
        output_file=test_output_file,
        files=[{"path": test_json_file}],
        model="flash"
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert "test" in content.lower()

@pytest.mark.vcr
def test_gemini_agent_lifecycle(skip_if_no_api_key, test_output_file, temp_storage_dir):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    agent_name = "test_agent_lifecycle"
    
    # Create agent
    result = create_agent(
        agent_name=agent_name,
        personality="You are a helpful assistant"
    )
    assert "created" in result.lower()
    
    # List agents
    result = list_agents()
    assert agent_name in result
    
    # Ask with agent
    result = ask(
        prompt="Remember my favorite color is blue",
        output_file=test_output_file,
        agent_name=agent_name
    )
    assert "saved" in result.lower() or "success" in result.lower()
    
    # Get stats
    result = agent_stats(agent_name=agent_name)
    assert agent_name in result
    assert "messages" in result.lower()
    
    # Clear agent
    result = clear_agent(agent_name=agent_name)
    assert "cleared" in result.lower()
    
    # Delete agent
    result = delete_agent(agent_name=agent_name)
    assert "deleted" in result.lower()

@pytest.mark.vcr
def test_gemini_analyze_image(skip_if_no_api_key, test_output_file):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Simple red pixel image
    red_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    result = analyze_image(
        prompt="What color is dominant in this image?",
        output_file=test_output_file,
        image_data=red_pixel,
        focus="colors"
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    content = Path(test_output_file).read_text()
    assert any(color in content.lower() for color in ["red", "yellow", "orange", "color"])

@pytest.mark.vcr
def test_gemini_generate_image(skip_if_no_api_key):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = generate_image(
        prompt="A simple blue square"
    )
    
    assert "saved" in result.lower() or "success" in result.lower() or ".png" in result

@pytest.mark.vcr
def test_gemini_server_info(skip_if_no_api_key):
    skip_if_no_api_key("GEMINI_API_KEY")
    
    result = server_info()
    
    assert "gemini" in result.lower()
    assert "status" in result.lower()

@pytest.mark.vcr
def test_gemini_custom_token_limits(skip_if_no_api_key, test_output_file):
    """Test that custom max_output_tokens parameter works with real API."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test with very low token limit - should still work but be brief
    result = ask(
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

@pytest.mark.vcr  
def test_gemini_high_token_limits(skip_if_no_api_key, test_output_file):
    """Test that high token limits work with 2.5 models."""
    skip_if_no_api_key("GEMINI_API_KEY")
    
    # Test with higher token limit using gemini-2.5-flash
    # Gemini 2.5 uses many tokens for internal reasoning, so we need a much higher limit
    result = ask(
        prompt="What is photosynthesis?",
        output_file=test_output_file,
        model="gemini-2.5-flash",
        max_output_tokens=2000,
        agent_name=False
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert len(content) > 50  # Should be a substantial response
    assert "photosynthesis" in content.lower()

@pytest.mark.vcr
def test_gemini_analyze_image_token_limits(skip_if_no_api_key, test_output_file):
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
    
    result = analyze_image(
        prompt="What color is this image? Just say the color.",
        output_file=test_output_file,
        image_data=f"data:image/png;base64,{img_data}",
        max_output_tokens=25,
        agent_name=False
    )
    
    assert "saved" in result.lower() or "success" in result.lower()
    assert Path(test_output_file).exists()
    content = Path(test_output_file).read_text()
    assert "red" in content.lower()
