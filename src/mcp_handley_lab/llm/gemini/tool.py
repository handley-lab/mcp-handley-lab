"""Gemini LLM tool for AI interactions via MCP."""
import base64
import io
import tempfile
import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from PIL import Image
from mcp.server.fastmcp import FastMCP

from google import genai as google_genai
from google.genai.types import GenerateContentConfig, GenerateImagesConfig, Tool, GoogleSearch, GoogleSearchRetrieval, Part, Blob, FileData, Content
from google.genai.errors import ClientError

from ...common.config import settings
from ...common.pricing import calculate_cost, format_usage
from ...common.memory import memory_manager
from ..common import (
    get_session_id, determine_mime_type, is_text_file, 
    resolve_image_data, handle_output, handle_agent_memory
)

mcp = FastMCP("Gemini Tool")

# Configure Gemini client
client = None
initialization_error = None

try:
    client = google_genai.Client(api_key=settings.gemini_api_key)
except Exception as e:
    client = None
    initialization_error = str(e)

# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"

# Model configurations with token limits from https://ai.google.dev/gemini-api/docs/models
MODEL_CONFIGS = {
    # Gemini 2.5 Models
    "gemini-2.5-pro": {"input_tokens": 1048576, "output_tokens": 65536},
    "gemini-2.5-flash": {"input_tokens": 1048576, "output_tokens": 65536},
    "gemini-2.5-flash-lite": {"input_tokens": 1000000, "output_tokens": 64000},
    
    # Gemini 2.0 Models  
    "gemini-2.0-flash": {"input_tokens": 1048576, "output_tokens": 8192},
    "gemini-2.0-flash-lite": {"input_tokens": 1048576, "output_tokens": 8192},
    
    # Gemini 1.5 Models
    "gemini-1.5-flash": {"input_tokens": 1048576, "output_tokens": 8192},
    "gemini-1.5-flash-8b": {"input_tokens": 1048576, "output_tokens": 8192},
    "gemini-1.5-pro": {"input_tokens": 2097152, "output_tokens": 8192},
}


def _get_session_id() -> str:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> Dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS["gemini-1.5-flash"])  # default to 1.5-flash


def _resolve_files(files: Optional[List[Union[str, Dict[str, str]]]]) -> List[Part]:
    """Resolve file inputs to structured content parts for google-genai API.
    
    Uses inlineData for files <20MB and Files API for larger files.
    Returns list of Part objects that can be included in contents.
    """
    if not files:
        return []
    
    parts = []
    for file_item in files:
        if isinstance(file_item, str):
            # Direct content string - create text part
            parts.append(Part(text=file_item))
        elif isinstance(file_item, dict):
            if "content" in file_item:
                # Direct content - create text part
                parts.append(Part(text=file_item["content"]))
            elif "path" in file_item:
                # File path - determine optimal handling based on size
                file_path = Path(file_item["path"])
                try:
                    if not file_path.exists():
                        parts.append(Part(text=f"Error: File not found: {file_path}"))
                        continue
                    
                    file_size = file_path.stat().st_size
                    
                    if file_size > 20 * 1024 * 1024:  # 20MB threshold
                        # Large file - use Files API
                        try:
                            uploaded_file = client.files.upload(
                                file=str(file_path),
                                mime_type=determine_mime_type(file_path)
                            )
                            parts.append(Part(fileData=FileData(fileUri=uploaded_file.uri)))
                        except Exception as e:
                            # Fallback to reading as text if upload fails
                            try:
                                content = file_path.read_text(encoding='utf-8')
                                parts.append(Part(text=f"[File: {file_path.name}]\n{content}"))
                            except UnicodeDecodeError:
                                parts.append(Part(text=f"Error: Could not upload or read file {file_path}: {e}"))
                    else:
                        # Small file - use inlineData with base64 encoding
                        try:
                            if is_text_file(file_path):
                                # For text files, read directly as text
                                content = file_path.read_text(encoding='utf-8')
                                parts.append(Part(text=f"[File: {file_path.name}]\n{content}"))
                            else:
                                # For binary files, use inlineData
                                file_content = file_path.read_bytes()
                                encoded_content = base64.b64encode(file_content).decode()
                                parts.append(Part(
                                    inlineData=Blob(
                                        mimeType=determine_mime_type(file_path),
                                        data=encoded_content
                                    )
                                ))
                        except Exception as e:
                            parts.append(Part(text=f"Error reading file {file_path}: {e}"))
                            
                except Exception as e:
                    parts.append(Part(text=f"Error processing file {file_path}: {e}"))
    
    return parts






def _resolve_images(
    image_data: Optional[str] = None, 
    images: Optional[List[Union[str, Dict[str, str]]]] = None
) -> List[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    image_list = []
    
    # Handle single image_data parameter
    if image_data:
        try:
            image_bytes = resolve_image_data(image_data)
            image_list.append(Image.open(io.BytesIO(image_bytes)))
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}")
    
    # Handle images array
    if images:
        for image_item in images:
            try:
                image_bytes = resolve_image_data(image_item)
                image_list.append(Image.open(io.BytesIO(image_bytes)))
            except Exception as e:
                raise ValueError(f"Failed to load image: {e}")
    
    return image_list


def _handle_agent_and_usage(
    agent_name: Optional[Union[str, bool]], 
    user_prompt: str, 
    response_text: str, 
    model: str,
    input_tokens: int, 
    output_tokens: int,
    output_file: str,
    provider: str = "gemini"
) -> str:
    """Handle agent memory, file output, and return formatted usage info."""
    cost = calculate_cost(model, input_tokens, output_tokens, provider)
    
    # Handle agent memory
    handle_agent_memory(
        agent_name, user_prompt, response_text, 
        input_tokens, output_tokens, cost, _get_session_id
    )
    
    # Handle output
    return handle_output(
        response_text, output_file, model, 
        input_tokens, output_tokens, cost, provider
    )


@mcp.tool(description="""Asks a question to a Gemini model with optional file context and persistent memory.

**Memory Behavior**: Conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

File Input Formats:
- {"path": "/path/to/file"} - Reads file from filesystem
- {"content": "text content"} - Uses provided text directly  
- "direct string" - Treats string as literal content

Key Parameters:
- `model`: "flash" (fast, default), "pro" (advanced reasoning), or full model name (e.g., "gemini-1.5-pro-002")
- `grounding`: Enable Google Search integration for current/recent information and factual accuracy (default: False, may increase response time). **Recommended for**: current date/time, recent events, real-time data, breaking news, or any information that may have changed recently
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)
- `temperature`: Creativity level 0.0 (deterministic) to 1.0 (creative, default: 0.7)

Error Handling:
- Raises RuntimeError for Gemini API errors (authentication, quota, network)
- Raises ValueError for invalid file paths or malformed requests
- Large responses automatically saved to avoid MCP message size limits

Examples:
```python
# Basic question with session memory (default)
ask(
    prompt="Explain this code",
    output_file="/tmp/explanation.md",
    files=[{"path": "/path/to/code.py"}]
)

# Continue conversation in same session
ask(
    prompt="Now show me how to optimize it",
    output_file="/tmp/optimization.md"
)

# Named agent for cross-session persistence
ask(
    prompt="Review this codebase",
    output_file="/tmp/review.md",
    agent_name="code_reviewer",
    model="pro"
)

# Disable memory for one-off queries
ask(
    prompt="What is the weather like?",
    output_file="/tmp/weather.md",
    agent_name=False,
    grounding=True
)
```""")
def ask(
    prompt: str,
    output_file: str,
    agent_name: Optional[Union[str, bool]] = None,
    model: str = "flash",
    temperature: float = 0.7,
    grounding: bool = False,
    files: Optional[List[Union[str, Dict[str, str]]]] = None,
    max_output_tokens: Optional[int] = None
) -> str:
    """Ask Gemini a question with optional persistent memory.
    
    Args:
        prompt: The question or instruction to send to Gemini
        output_file: File path to save the response (use '-' for stdout)
        agent_name: Named agent for persistent memory (None=session, False=disabled)
        model: Gemini model name (flash, pro, or full model name like gemini-2.5-flash)
        temperature: Creativity level 0.0-1.0 (default: 0.7)
        grounding: Enable Google Search integration for current information
        files: List of files to include as context
        max_output_tokens: Override model's default output token limit
    
    Token Limits by Model:
        - gemini-2.5-flash/pro: 65,536 tokens (default)
        - gemini-1.5-flash/pro: 8,192 tokens (default)
        - Use max_output_tokens parameter to override defaults
    
    Example with custom token limit:
        ask(prompt="Write a long essay", model="gemini-2.5-flash", max_output_tokens=32000)
    """
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file or not output_file.strip():
        raise ValueError("Output file is required")
    if agent_name is not None and agent_name is not False and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    if not client:
        raise RuntimeError(f"Gemini client not initialized: {initialization_error}")
    
    # Resolve model name
    model_name = f"gemini-1.5-{model}" if model in ["flash", "pro"] else model
    
    try:
        # Configure tools for grounding if requested
        tools = []
        if grounding:
            tools.append(Tool(googleSearchRetrieval=GoogleSearchRetrieval()))
        
        # Handle agent setup and system instruction (personality)
        system_instruction = None
        history = []
        use_memory = agent_name is not False
        
        # Only use memory if not explicitly disabled
        if use_memory:
            # Use session-specific agent if no agent_name provided (same logic as _handle_agent_and_usage)
            if not agent_name:
                agent_name = _get_session_id()
            
            agent = memory_manager.get_agent(agent_name)
            if agent:
                if agent.personality:
                    system_instruction = agent.personality
                history = agent.get_conversation_history()
        else:
            # No memory - set agent_name to None to skip memory operations
            agent_name = None
        
        # Resolve file contents to structured parts
        file_parts = _resolve_files(files)
        
        # Get model-specific configuration
        model_config = _get_model_config(model)
        
        # Use provided max_output_tokens or fall back to model default
        output_tokens = max_output_tokens if max_output_tokens is not None else model_config["output_tokens"]
        
        # Prepare the config
        config_params = {
            "temperature": temperature,
            "max_output_tokens": output_tokens,
        }
        
        if system_instruction:
            config_params["system_instruction"] = system_instruction
            
        if tools:
            config_params["tools"] = tools
        
        config = GenerateContentConfig(**config_params)
        
        # Generate content
        if history:
            # Continue existing conversation by adding history
            # Create user message with prompt and any file parts
            user_parts = [Part(text=prompt)] + file_parts
            contents = history + [{"role": "user", "parts": [part.to_json_dict() for part in user_parts]}]
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        else:
            # New conversation - create content with prompt and files
            if file_parts:
                # Include files as separate parts
                content_parts = [Part(text=prompt)] + file_parts
                response = client.models.generate_content(
                    model=model_name,
                    contents=content_parts,
                    config=config
                )
            else:
                # Simple text-only prompt
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
        
        # Extract response text
        if response.text:
            response_text = response.text
        else:
            raise RuntimeError("No response text generated")
        
        # Calculate usage
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        
        # Handle agent and usage (only if memory is enabled)
        if use_memory:
            return _handle_agent_and_usage(agent_name, prompt, response_text, model, input_tokens, output_tokens, output_file)
        else:
            # No memory - just handle file output and usage
            cost = calculate_cost(model, input_tokens, output_tokens, "gemini")
            if output_file != '-':
                output_path = Path(output_file)
                output_path.write_text(response_text)
                usage_info = format_usage(model, input_tokens, output_tokens, cost, "gemini")
                char_count = len(response_text)
                line_count = response_text.count('\n') + 1
                return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n\n{usage_info}"
            else:
                usage_info = format_usage(model, input_tokens, output_tokens, cost, "gemini")
                return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


@mcp.tool(description="""Analyzes images using Gemini's advanced vision capabilities.

**Memory Behavior**: Image analysis conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

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
- "text" - Extract and analyze text within images
- "technical" - Focus on technical aspects, quality, metadata

Model Options:
- "pro" (default) - Best for detailed analysis and complex reasoning
- "flash" - Faster response, good for simple image descriptions

Key Parameters:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Error Handling:
- Raises ValueError for missing or invalid image inputs
- Raises RuntimeError for Gemini API errors (quota, authentication, unsupported formats)
- Supports common formats: JPEG, PNG, GIF, WebP
- Large images may be automatically resized by the API

Examples:
```python
# Analyze image with session memory (default)
analyze_image(
    prompt="Describe what you see in this image",
    output_file="/tmp/analysis.md",
    image_data="/path/to/photo.jpg",
    focus="general"
)

# Continue analysis in same session
analyze_image(
    prompt="Now focus on the text in the image",
    output_file="/tmp/text_analysis.md",
    focus="text"
)

# Named agent for cross-session persistence
analyze_image(
    prompt="Analyze this architectural diagram",
    output_file="/tmp/architecture.md",
    image_data={"path": "/path/to/diagram.png"},
    agent_name="architect_reviewer",
    focus="technical"
)

# One-off analysis without memory
analyze_image(
    prompt="What's in this random image?",
    output_file="/tmp/random.md",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    agent_name=False
)
```""")
def analyze_image(
    prompt: str,
    output_file: str,
    image_data: Optional[str] = None,
    images: Optional[List[Union[str, Dict[str, str]]]] = None,
    focus: str = "general",
    model: str = "pro",
    agent_name: Optional[Union[str, bool]] = None,
    max_output_tokens: Optional[int] = None
) -> str:
    """Analyze images with Gemini vision model."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file or not output_file.strip():
        raise ValueError("Output file is required")
    if not image_data and not images:
        raise ValueError("Either image_data or images must be provided")
    if agent_name is not None and agent_name is not False and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    if not client:
        raise RuntimeError(f"Gemini client not initialized: {initialization_error}")
    
    # Resolve model name
    model_name = f"gemini-1.5-{model}" if model in ["flash", "pro"] else model
    
    try:
        # Load images
        image_list = _resolve_images(image_data, images)
        
        # Enhance prompt based on focus
        if focus != "general":
            prompt = f"Focus on {focus} aspects. {prompt}"
        
        # Get model-specific configuration
        model_config = _get_model_config(model)
        
        # Use provided max_output_tokens or fall back to model default
        output_tokens = max_output_tokens if max_output_tokens is not None else model_config["output_tokens"]
        
        # Prepare content with images - google-genai expects PIL Image objects directly
        content = [prompt] + image_list
        
        # Prepare the config
        config = GenerateContentConfig(
            max_output_tokens=output_tokens,
            temperature=0.7
        )
        
        # Generate response
        response = client.models.generate_content(
            model=model_name,
            contents=content,
            config=config
        )
        
        # Extract response text
        if response.text:
            response_text = response.text
        else:
            raise RuntimeError("No response text generated")
        
        # Calculate usage
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        
        # Handle agent and usage (only if memory is enabled)
        image_desc = f"[Image analysis: {len(image_list)} image(s)]"
        use_memory = agent_name is not False
        
        if use_memory:
            return _handle_agent_and_usage(agent_name, f"{prompt} {image_desc}", response_text, model, input_tokens, output_tokens, output_file)
        else:
            # No memory - just handle file output and usage
            cost = calculate_cost(model, input_tokens, output_tokens, "gemini")
            if output_file != '-':
                output_path = Path(output_file)
                output_path.write_text(response_text)
                usage_info = format_usage(model, input_tokens, output_tokens, cost, "gemini")
                char_count = len(response_text)
                line_count = response_text.count('\n') + 1
                return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n\n{usage_info}"
            else:
                usage_info = format_usage(model, input_tokens, output_tokens, cost, "gemini")
                return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"Gemini vision API error: {e}")


@mcp.tool(description="""Generates high-quality images using Gemini's Imagen 3 model.

**Memory Behavior**: Image generation requests are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

Creates images from text descriptions with advanced artistic capabilities. Generated images are saved as PNG files to a temporary location.

Prompt Guidelines:
- Be descriptive and specific for best results
- Include style, mood, lighting, and composition details
- Mention aspect ratio preferences if needed
- Avoid requesting copyrighted characters or inappropriate content

Key Parameters:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Examples:
```python
# Generate with session memory (default)
generate_image(
    prompt="A serene mountain landscape at sunset, with golden light reflecting on a crystal-clear lake, painted in impressionist style"
)

# Continue with variations in same session
generate_image(
    prompt="Now make it more abstract and colorful"
)

# Named agent for cross-session persistence
generate_image(
    prompt="Professional headshot of a confident software engineer",
    agent_name="portrait_artist"
)

# One-off generation without memory
generate_image(
    prompt="Random abstract art",
    agent_name=False
)
```

Note: Generated images are automatically saved to temporary files. Use the returned file path for further processing.

Error Handling:
- Raises RuntimeError for Imagen API errors (quota exceeded, content policy violations)
- Raises ValueError for prompts that violate content policies
- Generated images are PNG format, saved to system temp directory""")
def generate_image(
    prompt: str,
    model: str = "imagen-3",
    agent_name: Optional[Union[str, bool]] = None
) -> str:
    """Generate images with Google's Imagen 3 model."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if agent_name is not None and agent_name is not False and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")
    
    if not client:
        raise RuntimeError(f"Gemini client not initialized: {initialization_error}")
    
    # Map model names to actual model IDs
    model_mapping = {
        "imagen-3": "imagen-3.0-generate-002",
        "image": "imagen-3.0-generate-002",
        "image-flash": "imagen-3.0-generate-002"
    }
    
    actual_model = model_mapping.get(model, "imagen-3.0-generate-002")
    
    try:
        # Generate image
        response = client.models.generate_images(
            model=actual_model,
            prompt=prompt,
            config=GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1"
            )
        )
        
        if not response.generated_images:
            raise RuntimeError("No images were generated")
        
        # Save the generated image
        generated_image = response.generated_images[0]
        if not generated_image.image or not generated_image.image.image_bytes:
            raise RuntimeError("Generated image has no data")
        
        # Save to temporary file
        import uuid
        file_id = str(uuid.uuid4())[:8]
        filename = f"gemini_generated_{file_id}.png"
        filepath = Path(tempfile.gettempdir()) / filename
        
        filepath.write_bytes(generated_image.image.image_bytes)
        
        # Calculate usage and cost (estimate)
        input_tokens = len(prompt.split()) * 2  # Rough estimate
        output_tokens = 1  # Image generation
        cost = calculate_cost(actual_model, input_tokens, output_tokens, "gemini")
        
        # Handle agent memory (only if enabled)
        use_memory = agent_name is not False
        
        if use_memory:
            # Use session-specific agent if no agent_name provided
            if not agent_name:
                agent_name = _get_session_id()
            
            agent = memory_manager.get_agent(agent_name)
            if not agent:
                agent = memory_manager.create_agent(agent_name)
            
            memory_manager.add_message(agent_name, "user", f"Generate image: {prompt}", input_tokens, cost / 2)
            memory_manager.add_message(agent_name, "assistant", f"Generated image saved to {filepath}", output_tokens, cost / 2)
        
        # Format response
        file_size = len(generated_image.image.image_bytes)
        usage_info = format_usage(actual_model, input_tokens, output_tokens, cost, "gemini")
        
        return f"✅ **Image Generated Successfully**\n\n📁 **File:** `{filepath}`\n📏 **Size:** {file_size:,} bytes\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"Error generating image with Imagen: {e}")


@mcp.tool(description="""Creates a new persistent conversation agent with optional personality.

Agents maintain conversation history across multiple interactions, enabling context-aware responses and long-term memory.

Personality Examples:
- "Expert Python developer focused on clean code and best practices"
- "Helpful data scientist specializing in machine learning"
- "Creative writing assistant with expertise in technical documentation"
- "Security-focused code reviewer"

Example:
```python
create_agent(
    agent_name="code_mentor",
    personality="Senior software engineer who provides constructive code reviews with focus on maintainability and performance"
)
```""")
def create_agent(agent_name: str, personality: Optional[str] = None) -> str:
    """Create a new agent with optional personality."""
    # Input validation
    if not agent_name or not agent_name.strip():
        raise ValueError("Agent name is required and cannot be empty")
    
    try:
        agent = memory_manager.create_agent(agent_name, personality)
        personality_info = f" with personality: {personality}" if personality else ""
        return f"✅ Agent '{agent_name}' created successfully{personality_info}!"
    except ValueError as e:
        raise ValueError(str(e))


@mcp.tool(description="Lists all persistent agents with summary statistics including creation date, message count, token usage, and total cost. Use this to manage and monitor agent usage across your projects.")
def list_agents() -> str:
    """List all agents with their statistics."""
    agents = memory_manager.list_agents()
    
    if not agents:
        return "No agents found. Create an agent with create_agent()."
    
    result = "📋 **Agent List**\n\n"
    for agent in agents:
        stats = agent.get_stats()
        result += f"**{stats['name']}**\n"
        result += f"- Created: {stats['created_at'][:10]}\n"
        result += f"- Messages: {stats['message_count']}\n"
        result += f"- Tokens: {stats['total_tokens']:,}\n"
        result += f"- Cost: ${stats['total_cost']:.4f}\n"
        if stats['personality']:
            result += f"- Personality: {stats['personality']}\n"
        result += "\n"
    
    return result


@mcp.tool(description="""Retrieves comprehensive statistics and recent conversation history for a specific agent.

Provides detailed insights into agent usage including total tokens, costs, and the last 5 messages for context review.

Example:
```python
agent_stats("code_mentor")
# Returns creation date, message count, token usage, cost, personality, and recent messages
```""")
def agent_stats(agent_name: str) -> str:
    """Get detailed statistics for a specific agent."""
    agent = memory_manager.get_agent(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found")
    
    stats = agent.get_stats()
    
    result = f"📊 **Agent Statistics: {agent_name}**\n\n"
    result += f"**Overview:**\n"
    result += f"- Created: {stats['created_at']}\n"
    result += f"- Total Messages: {stats['message_count']}\n"
    result += f"- Total Tokens: {stats['total_tokens']:,}\n"
    result += f"- Total Cost: ${stats['total_cost']:.4f}\n"
    
    if stats['personality']:
        result += f"- Personality: {stats['personality']}\n"
    
    # Recent message history (last 5)
    if agent.messages:
        result += f"\n**Recent Messages:**\n"
        recent_messages = agent.messages[-5:]
        for msg in recent_messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            role_icon = "👤" if msg.role == "user" else "🤖"
            result += f"- {timestamp} {role_icon} {msg.role}: {msg.content[:100]}...\n"
    
    return result


@mcp.tool(description="Clears all conversation history for an agent while preserving the agent itself and its personality. Use this to start fresh conversations while maintaining the agent's configuration.")
def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history."""
    success = memory_manager.clear_agent_history(agent_name)
    if success:
        return f"✅ Agent '{agent_name}' history cleared successfully!"
    else:
        raise ValueError(f"Agent '{agent_name}' not found")


@mcp.tool(description="Permanently deletes an agent and all associated conversation data. WARNING: This action cannot be undone. Use clear_agent() instead if you only want to reset the conversation history.")
def delete_agent(agent_name: str) -> str:
    """Delete an agent permanently."""
    # Input validation
    if not agent_name or not agent_name.strip():
        raise ValueError("Agent name is required and cannot be empty")
    
    success = memory_manager.delete_agent(agent_name)
    if success:
        return f"✅ Agent '{agent_name}' deleted permanently!"
    else:
        raise ValueError(f"Agent '{agent_name}' not found")


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


@mcp.tool(description="Checks Gemini server status, API connectivity, available models, and agent statistics. Returns configuration status and available commands. Use this to verify the tool is properly configured before making requests.")
def server_info() -> str:
    """Get server status and Gemini configuration."""
    try:
        if not client:
            raise RuntimeError(f"Gemini client not initialized: {initialization_error}")
        
        # Test API by listing models
        models_response = client.models.list()
        available_models = []
        for model in models_response:
            if 'gemini' in model.name:
                available_models.append(model.name.split('/')[-1])
        
        # Get agent count
        agent_count = len(memory_manager.list_agents())
        
        return f"""Gemini Tool Server Status
==========================
Status: Connected and ready
API Key: Configured ✓
Available Models: {len(available_models)} models
- {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}

Agent Management:
- Active Agents: {agent_count}
- Memory Storage: {memory_manager.storage_dir}

Available tools:
- ask: Chat with Gemini models (persistent memory by default, agent_name=False to disable)
- analyze_image: Image analysis with vision models (persistent memory by default, agent_name=False to disable)
- generate_image: Generate images with Imagen 3 (persistent memory by default, agent_name=False to disable)
- create_agent: Create persistent conversation agents
- list_agents: List all agents and stats
- agent_stats: Get detailed agent statistics
- get_response: Retrieve messages from agent conversation history
- clear_agent: Clear agent conversation history
- delete_agent: Permanently delete agents
- server_info: Get server status"""
        
    except Exception as e:
        raise RuntimeError(f"Gemini API configuration error: {e}")