"""OpenAI LLM tool for AI interactions via MCP."""
import base64
import io
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from openai import OpenAI
from PIL import Image
from mcp.server.fastmcp import FastMCP

from ...common.config import settings
from ...common.pricing import calculate_cost
from ...common.memory import memory_manager
from ..common import (
    determine_mime_type, is_text_file, resolve_image_data, 
    handle_output, handle_agent_memory
)

mcp = FastMCP("OpenAI Tool")

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Model configurations with token limits from OpenAI documentation
MODEL_CONFIGS = {
    # O3 Series (2025)
    "o3-mini": {"output_tokens": 100000, "param": "max_completion_tokens"},
    
    # O1 Series (Reasoning Models)
    "o1-preview": {"output_tokens": 32768, "param": "max_completion_tokens"},
    "o1-mini": {"output_tokens": 65536, "param": "max_completion_tokens"},
    
    # GPT-4o Series
    "gpt-4o": {"output_tokens": 16384, "param": "max_tokens"},
    "gpt-4o-mini": {"output_tokens": 16384, "param": "max_tokens"},
    "gpt-4o-2024-11-20": {"output_tokens": 16384, "param": "max_tokens"},
    "gpt-4o-2024-08-06": {"output_tokens": 16384, "param": "max_tokens"},
    "gpt-4o-mini-2024-07-18": {"output_tokens": 16384, "param": "max_tokens"},
    
    # GPT-4.1 Series (if released)
    "gpt-4.1": {"output_tokens": 32768, "param": "max_tokens"},
    "gpt-4.1-mini": {"output_tokens": 16384, "param": "max_tokens"},
}


def _get_model_config(model: str) -> Dict[str, Any]:
    """Get token limits and parameter name for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS["gpt-4o"])  # default to gpt-4o


def _resolve_files(files: Optional[List[Union[str, Dict[str, str]]]]) -> tuple[List[Dict], List[str]]:
    """Resolve file inputs to OpenAI chat content format.
    
    Returns tuple of (file_attachments, inline_content):
    - file_attachments: List of dicts for Files API (large files)
    - inline_content: List of strings for direct inclusion (small files)
    
    Uses intelligent size-based strategy:
    - Small files (<1MB): Include content directly in messages
    - Large files (1MB-20MB): Upload via Files API for Assistants
    - Text files: Direct content inclusion with filename header
    - Binary files: Base64 encoding for small files, Files API for large
    """
    if not files:
        return [], []
    
    file_attachments = []
    inline_content = []
    
    for file_item in files:
        if isinstance(file_item, str):
            # Direct content string
            inline_content.append(file_item)
        elif isinstance(file_item, dict):
            if "content" in file_item:
                # Direct content from dict
                inline_content.append(file_item["content"])
            elif "path" in file_item:
                # File path - determine optimal handling strategy
                file_path = Path(file_item["path"])
                try:
                    if not file_path.exists():
                        inline_content.append(f"Error: File not found: {file_path}")
                        continue
                    
                    file_size = file_path.stat().st_size
                    
                    if file_size > 1024 * 1024:  # 1MB threshold for Files API
                        # Large file - use Files API for assistant-compatible upload
                        try:
                            uploaded_file = client.files.create(
                                file=open(file_path, "rb"),
                                purpose="assistants"
                            )
                            file_attachments.append({
                                "file_id": uploaded_file.id,
                                "tools": [{"type": "file_search"}]
                            })
                        except Exception as e:
                            # Fallback to chunked text inclusion for large files
                            try:
                                if is_text_file(file_path):
                                    content = file_path.read_text(encoding='utf-8')
                                    # Truncate very large text files to prevent token overflow
                                    if len(content) > 50000:  # ~12.5k tokens rough estimate
                                        content = content[:50000] + "\n\n[Content truncated due to size]"
                                    inline_content.append(f"[File: {file_path.name}]\n{content}")
                                else:
                                    inline_content.append(f"Error: Could not upload large binary file {file_path}: {e}")
                            except UnicodeDecodeError:
                                inline_content.append(f"Error: Could not process large file {file_path}: {e}")
                    else:
                        # Small file - include directly
                        try:
                            if is_text_file(file_path):
                                # Text file - read as string with header
                                content = file_path.read_text(encoding='utf-8')
                                inline_content.append(f"[File: {file_path.name}]\n{content}")
                            else:
                                # Small binary file - base64 encode with metadata
                                file_content = file_path.read_bytes()
                                encoded_content = base64.b64encode(file_content).decode()
                                mime_type = determine_mime_type(file_path)
                                inline_content.append(
                                    f"[Binary file: {file_path.name}, {mime_type}, {file_size} bytes]\n{encoded_content}"
                                )
                        except Exception as e:
                            inline_content.append(f"Error reading file {file_path}: {e}")
                            
                except Exception as e:
                    inline_content.append(f"Error processing file {file_path}: {e}")
    
    return file_attachments, inline_content






def _resolve_images(
    image_data: Optional[str] = None, 
    images: Optional[List[Union[str, Dict[str, str]]]] = None
) -> List[str]:
    """Resolve image inputs to base64 encoded strings for OpenAI."""
    image_list = []
    
    if image_data:
        try:
            if image_data.startswith("data:image"):
                image_list.append(image_data)
            else:
                # File path - convert to base64
                image_bytes = Path(image_data).read_bytes()
                # Detect format from file extension
                ext = Path(image_data).suffix.lower()
                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext[1:]}"
                encoded = base64.b64encode(image_bytes).decode()
                image_list.append(f"data:{mime_type};base64,{encoded}")
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}")
    
    if images:
        for image_item in images:
            try:
                if isinstance(image_item, str):
                    if image_item.startswith("data:image"):
                        image_list.append(image_item)
                    else:
                        # File path
                        image_bytes = Path(image_item).read_bytes()
                        ext = Path(image_item).suffix.lower()
                        mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext[1:]}"
                        encoded = base64.b64encode(image_bytes).decode()
                        image_list.append(f"data:{mime_type};base64,{encoded}")
                elif isinstance(image_item, dict):
                    if "data" in image_item:
                        # Already base64 encoded
                        encoded_data = image_item["data"]
                        if not encoded_data.startswith("data:image"):
                            encoded_data = f"data:image/jpeg;base64,{encoded_data}"
                        image_list.append(encoded_data)
                    elif "path" in image_item:
                        image_bytes = Path(image_item["path"]).read_bytes()
                        ext = Path(image_item["path"]).suffix.lower()
                        mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext[1:]}"
                        encoded = base64.b64encode(image_bytes).decode()
                        image_list.append(f"data:{mime_type};base64,{encoded}")
            except Exception as e:
                raise ValueError(f"Failed to load image: {e}")
    
    return image_list


def _handle_agent_and_usage(
    agent_name: Optional[str], 
    user_prompt: str, 
    response_text: str, 
    model: str,
    input_tokens: int, 
    output_tokens: int,
    output_file: str,
    provider: str = "openai"
) -> str:
    """Handle agent memory, file output, and return formatted usage info."""
    cost = calculate_cost(model, input_tokens, output_tokens, provider)
    
    # Handle agent memory (OpenAI doesn't use session-based memory like Gemini)
    if agent_name:
        handle_agent_memory(
            agent_name, user_prompt, response_text, 
            input_tokens, output_tokens, cost, lambda: agent_name
        )
    
    # Handle output
    return handle_output(
        response_text, output_file, model, 
        input_tokens, output_tokens, cost, provider
    )


@mcp.tool(description="""Asks a question to an OpenAI GPT model with optional file context and persistent memory.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

File Input Formats:
- {"path": "/path/to/file"} - Reads file from filesystem
- {"content": "text content"} - Uses provided text directly
- "direct string" - Treats string as literal content

Key Parameters:
- `model`: "gpt-4o" (default, multimodal), "gpt-4o-mini" (fast), "o1-preview" (reasoning), "o1-mini" (fast reasoning)
- `temperature`: Creativity level 0.0 (deterministic) to 2.0 (very creative, default: 0.7)
- `max_output_tokens`: Override model's default output token limit
- `agent_name`: Store conversation in persistent memory for ongoing interactions

Token Limits by Model:
- o3-mini: 100,000 tokens (default)
- o1-mini: 65,536 tokens (default)
- o1-preview: 32,768 tokens (default)
- gpt-4o/gpt-4o-mini: 16,384 tokens (default)
- Use max_output_tokens parameter to override defaults

Model Selection Guide:
- gpt-4o: Best for complex analysis, coding, and multimodal tasks (128k context)
- gpt-4o-mini: Fast and cost-effective for simple tasks (128k context)
- o1-preview: Advanced reasoning for complex problems (128k context, no system messages)
- o1-mini: Fast reasoning for mathematical and coding tasks (128k context, no system messages)

Error Handling:
- Raises RuntimeError for OpenAI API errors (authentication, quota, rate limits)
- Raises ValueError for invalid file paths or unsupported content
- Agent memory automatically handles conversation context limits
- Large responses automatically saved to avoid MCP message size limits

Examples:
```python
# Basic question with file context
ask(
    prompt="Explain this code and suggest improvements",
    output_file="/tmp/analysis.md",
    files=[{"path": "/path/to/code.py"}],
    model="gpt-4o"
)

# Persistent agent conversation
ask(
    prompt="Continue reviewing the codebase",
    output_file="/tmp/review.md",
    agent_name="code_reviewer",
    model="gpt-4o",
    temperature=0.3
)

# Complex reasoning task
ask(
    prompt="Solve this algorithmic problem step by step",
    output_file="/tmp/solution.md",
    model="o1-preview",
    files=[{"content": "Problem description here"}]
)

# Multiple file analysis
ask(
    prompt="Compare these implementations",
    output_file="/tmp/comparison.md",
    files=[
        {"path": "/path/to/impl1.py"},
        {"path": "/path/to/impl2.py"},
        {"content": "Additional context"}
    ],
    max_output_tokens=2000
)
```""")
def ask(
    prompt: str,
    output_file: str,
    agent_name: Optional[str] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    files: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """Ask OpenAI a question with optional persistent memory."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file or not output_file.strip():
        raise ValueError("Output file is required")
    if agent_name is not None and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    try:
        # Build conversation history
        messages = []
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if agent:
                messages = agent.get_openai_conversation_history()
        
        # Resolve files using improved strategy
        file_attachments, inline_content = _resolve_files(files)
        if inline_content:
            prompt += "\n\n" + "\n\n".join(inline_content)
        
        # Add current prompt with file attachments if any
        message_content = {"role": "user", "content": prompt}
        if file_attachments:
            message_content["attachments"] = file_attachments
        messages.append(message_content)
        
        # Get model-specific configuration
        model_config = _get_model_config(model)
        
        # Use provided max_output_tokens or fall back to model default
        output_tokens = max_output_tokens if max_output_tokens is not None else model_config["output_tokens"]
        
        # Prepare API call parameters based on model type
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        # Use correct parameter name based on model
        if model_config["param"] == "max_completion_tokens":
            api_params["max_completion_tokens"] = output_tokens
        else:
            api_params["max_tokens"] = output_tokens
        
        # Make API call
        response = client.chat.completions.create(**api_params)
        
        response_text = response.choices[0].message.content
        
        # Extract usage info
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # Handle agent and usage
        return _handle_agent_and_usage(agent_name, prompt, response_text, model, input_tokens, output_tokens, output_file)
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")


@mcp.tool(description="""Analyzes images using OpenAI's GPT-4 Vision model with advanced multimodal capabilities.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the analysis for future processing (recommended)
- '-' to output directly to stdout (use sparingly for large analyses)

Image Input Formats:
- {"path": "/path/to/image.jpg"} - Read from filesystem (preferred)
- {"data": "base64_encoded_data"} - Base64 encoded image data
- "data:image/jpeg;base64,/9j/4AAQ..." - Data URL format
- "/path/to/image.jpg" - Direct path string (legacy, use dict format instead)

Analysis Focus Options:
- "general" (default) - Overall image description
- "objects" - Focus on object detection and identification
- "colors" - Analyze color palette and composition
- "composition" - Focus on artistic composition and layout
- "text" - Extract and analyze text within images (OCR)
- "technical" - Focus on technical aspects, quality, metadata
- "medical" - Medical image analysis (disclaimer: not for diagnosis)
- "code" - Analyze screenshots of code or diagrams

Model Options:
- "gpt-4o" (default) - Best vision capabilities, handles complex visual reasoning
- "gpt-4o-mini" - Faster, cost-effective vision analysis for simple tasks

Error Handling:
- Raises ValueError for missing images or unsupported formats
- Raises RuntimeError for OpenAI API errors (quota, rate limits, content policy)
- Supports: JPEG, PNG, GIF, WebP (max 20MB per image)
- Multiple images increase token usage significantly

Examples:
```python
# Analyze single image
analyze_image(
    prompt="Describe what you see in this screenshot",
    output_file="/tmp/analysis.md",
    image_data="/path/to/screenshot.png",
    focus="general"
)

# Multiple images comparison
analyze_image(
    prompt="Compare these two UI designs and suggest improvements",
    output_file="/tmp/comparison.md",
    images=[
        {"path": "/path/to/design1.png"},
        {"path": "/path/to/design2.png"}
    ],
    focus="composition"
)

# Extract text from image
analyze_image(
    prompt="Extract and transcribe all text from this document",
    output_file="/tmp/extracted_text.md",
    image_data={"path": "/path/to/document.jpg"},
    focus="text",
    model="gpt-4o"
)

# Code analysis from screenshot
analyze_image(
    prompt="Review this code for potential bugs and improvements",
    output_file="/tmp/code_review.md",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    focus="code",
    agent_name="code_reviewer"
)
```""")
def analyze_image(
    prompt: str,
    output_file: str,
    image_data: Optional[str] = None,
    images: Optional[List[Union[str, Dict[str, str]]]] = None,
    focus: str = "general",
    model: str = "gpt-4o",
    agent_name: Optional[str] = None,
    max_output_tokens: Optional[int] = None
) -> str:
    """Analyze images with OpenAI vision model."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file or not output_file.strip():
        raise ValueError("Output file is required")
    if not image_data and not images:
        raise ValueError("Either image_data or images must be provided")
    if agent_name is not None and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    try:
        # Load images
        image_list = _resolve_images(image_data, images)
        
        # Enhance prompt based on focus
        if focus != "general":
            prompt = f"Focus on {focus} aspects. {prompt}"
        
        # Build message content with images
        content = [{"type": "text", "text": prompt}]
        for image_url in image_list:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        
        # Build conversation history
        messages = []
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if agent:
                messages = agent.get_openai_conversation_history()
        
        # Add current message with images
        messages.append({"role": "user", "content": content})
        
        # Get model-specific configuration
        model_config = _get_model_config(model)
        
        # Use provided max_output_tokens or fall back to model default
        output_tokens = max_output_tokens if max_output_tokens is not None else model_config["output_tokens"]
        
        # Prepare API call parameters based on model type
        api_params = {
            "model": model,
            "messages": messages,
        }
        
        # Use correct parameter name based on model
        if model_config["param"] == "max_completion_tokens":
            api_params["max_completion_tokens"] = output_tokens
        else:
            api_params["max_tokens"] = output_tokens
        
        # Make API call
        response = client.chat.completions.create(**api_params)
        
        response_text = response.choices[0].message.content
        
        # Extract usage info
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # Handle agent and usage
        image_desc = f"[Image analysis: {len(image_list)} image(s)]"
        return _handle_agent_and_usage(agent_name, f"{prompt} {image_desc}", response_text, model, input_tokens, output_tokens, output_file)
        
    except Exception as e:
        raise RuntimeError(f"OpenAI vision API error: {e}")


@mcp.tool(description="""Generates high-quality images using OpenAI's DALL-E models.

Model Options:
- "dall-e-3" (default) - Latest model with best quality and prompt adherence
- "dall-e-2" - Previous generation, faster and more cost-effective

Quality Settings:
- "standard" (default) - Good quality, faster generation
- "hd" - Higher resolution and detail (DALL-E 3 only)

Size Options:
- DALL-E 3: "1024x1024" (default), "1024x1792" (portrait), "1792x1024" (landscape)
- DALL-E 2: "256x256", "512x512", "1024x1024" (default)

Prompt Guidelines:
- Be descriptive and specific for best results
- Include style, mood, lighting, and composition details
- DALL-E 3 follows prompts more precisely than DALL-E 2
- Avoid requesting copyrighted characters or inappropriate content

Examples:
```python
# High-quality artistic image
generate_image(
    prompt="A serene mountain landscape at sunset with golden light reflecting on a crystal-clear lake, painted in impressionist style with visible brushstrokes",
    model="dall-e-3",
    quality="hd",
    size="1792x1024"
)

# Technical diagram
generate_image(
    prompt="Clean, minimalist flowchart showing a software deployment pipeline with rounded rectangles and arrow connections, professional blue and white colors",
    model="dall-e-3",
    size="1024x1792"
)

# Portrait with specific style
generate_image(
    prompt="Professional headshot of a confident software engineer in modern office setting, natural lighting, shallow depth of field, photorealistic style",
    model="dall-e-3",
    quality="hd",
    agent_name="design_assistant"
)

# Cost-effective generation
generate_image(
    prompt="Simple icon design for a mobile app, minimalist style, single color",
    model="dall-e-2",
    size="512x512"
)
```

Note: Generated images are automatically downloaded and saved to temporary files. Use the returned file path for further processing.

Error Handling:
- Raises RuntimeError for DALL-E API errors (quota exceeded, content policy violations)
- Raises ValueError for prompts violating OpenAI's usage policies
- Image download may fail due to network issues; temporary URLs expire quickly
- DALL-E 3 may revise prompts for safety compliance""")
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: Optional[str] = None
) -> str:
    """Generate images with DALL-E."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if agent_name is not None and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    try:
        # Make API call (quality only supported for DALL-E 3)
        params = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1
        }
        if model == "dall-e-3":
            params["quality"] = quality
            
        response = client.images.generate(**params)
        
        # Get the image URL
        image_url = response.data[0].url
        
        # Download and save the image
        import requests
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_response.content)
            saved_path = f.name
        
        # Calculate cost (DALL-E pricing is per image)
        cost = calculate_cost(model, 1, 0, "openai")  # 1 image
        
        # Handle agent memory
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if not agent:
                agent = memory_manager.create_agent(agent_name)
            
            memory_manager.add_message(agent_name, "user", f"Generate image: {prompt}", 0, cost / 2)
            memory_manager.add_message(agent_name, "assistant", f"Image generated and saved to {saved_path}", 0, cost / 2)
        
        cost_str = f"${cost:.4f}" if cost < 0.01 else f"${cost:.2f}"
        
        return f"✅ Image generated successfully!\n📁 Saved to: {saved_path}\n💰 Cost: {cost_str}"
        
    except Exception as e:
        raise RuntimeError(f"DALL-E API error: {e}")


@mcp.tool(description="""Retrieves a specific message from an agent's conversation history by index.

Index Usage:
- -1 (default): Last/most recent message
- 0: First message in history  
- Positive integers: Specific message position

Example:
```python
# Get the last response
get_response("code_mentor")

# Get the first message
get_response("code_mentor", index=0)

# Get third message
get_response("code_mentor", index=2)
```""")
def get_response(agent_name: str, index: int = -1) -> str:
    """Get a message from an agent's conversation history by index."""
    response = memory_manager.get_response(agent_name, index)
    if response is None:
        if memory_manager.get_agent(agent_name) is None:
            raise ValueError(f"Agent '{agent_name}' not found")
        else:
            raise ValueError(f"No message found at index {index}")
    
    return response


@mcp.tool(description="Checks OpenAI server status, API connectivity, available models, and agent statistics. Returns configuration status and available commands. Use this to verify the tool is properly configured before making requests.")
def server_info() -> str:
    """Get server status and OpenAI configuration."""
    try:
        # Test API key by listing models
        models = client.models.list()
        available_models = [m.id for m in models.data if m.id.startswith(("gpt", "dall-e", "text-", "o1"))]
        
        # Get agent count
        agent_count = len(memory_manager.list_agents())
        
        return f"""OpenAI Tool Server Status
==========================
Status: Connected and ready
API Key: Configured ✓
Available Models: {len(available_models)} models
- {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}

Agent Management:
- Active Agents: {agent_count}
- Memory Storage: {memory_manager.storage_dir}

Available tools:
- ask: Chat with GPT models (requires output_file parameter)
- analyze_image: Image analysis with vision models (requires output_file parameter)
- generate_image: Generate images with DALL-E
- get_response: Retrieve messages from agent conversation history
- server_info: Get server status"""
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API configuration error: {e}")