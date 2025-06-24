"""Gemini LLM tool for AI interactions via MCP."""
import base64
import io
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import google.generativeai as genai
from PIL import Image
from mcp.server.fastmcp import FastMCP

from ...common.config import settings
from ...common.memory import memory_manager
from ...common.pricing import calculate_cost, format_usage

mcp = FastMCP("Gemini Tool")

# Configure Gemini
genai.configure(api_key=settings.gemini_api_key)


def _resolve_files(files: Optional[List[Union[str, Dict[str, str]]]]) -> List[str]:
    """Resolve file inputs to content strings."""
    if not files:
        return []
    
    content_list = []
    for file_item in files:
        if isinstance(file_item, str):
            # Direct content string
            content_list.append(file_item)
        elif isinstance(file_item, dict):
            if "content" in file_item:
                content_list.append(file_item["content"])
            elif "path" in file_item:
                # Read file from path
                try:
                    content_list.append(Path(file_item["path"]).read_text())
                except (OSError, UnicodeDecodeError) as e:
                    content_list.append(f"Error reading file {file_item['path']}: {e}")
    
    return content_list


def _resolve_images(
    image_data: Optional[str] = None, 
    images: Optional[List[Union[str, Dict[str, str]]]] = None
) -> List[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    image_list = []
    
    # Handle single image_data parameter
    if image_data:
        try:
            if image_data.startswith("data:image"):
                # Data URL format
                header, encoded = image_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
            else:
                # Assume it's a file path
                image_bytes = Path(image_data).read_bytes()
            
            image_list.append(Image.open(io.BytesIO(image_bytes)))
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}")
    
    # Handle images array
    if images:
        for image_item in images:
            try:
                if isinstance(image_item, str):
                    if image_item.startswith("data:image"):
                        header, encoded = image_item.split(",", 1)
                        image_bytes = base64.b64decode(encoded)
                    else:
                        image_bytes = Path(image_item).read_bytes()
                    image_list.append(Image.open(io.BytesIO(image_bytes)))
                elif isinstance(image_item, dict):
                    if "data" in image_item:
                        image_bytes = base64.b64decode(image_item["data"])
                        image_list.append(Image.open(io.BytesIO(image_bytes)))
                    elif "path" in image_item:
                        image_bytes = Path(image_item["path"]).read_bytes()
                        image_list.append(Image.open(io.BytesIO(image_bytes)))
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
    provider: str = "gemini"
) -> str:
    """Handle agent memory, file output, and return formatted usage info."""
    cost = calculate_cost(model, input_tokens, output_tokens, provider)
    
    # Store in agent memory if specified
    if agent_name:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)
        
        memory_manager.add_message(agent_name, "user", user_prompt, input_tokens, cost / 2)
        memory_manager.add_message(agent_name, "assistant", response_text, output_tokens, cost / 2)
    
    # Handle file output
    if output_file != '-':
        # Save to file
        output_path = Path(output_file)
        output_path.write_text(response_text)
        
        # Return summary with file path and usage
        usage_info = format_usage(model, input_tokens, output_tokens, cost, provider)
        char_count = len(response_text)
        line_count = response_text.count('\n') + 1
        return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n\n{usage_info}"
    else:
        # Return full response with usage for stdout
        usage_info = format_usage(model, input_tokens, output_tokens, cost, provider)
        return f"{response_text}\n\n{usage_info}"


@mcp.tool(description="""Asks a question to a Gemini model with optional file context and persistent memory.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

File Input Formats:
- {"path": "/path/to/file"} - Reads file from filesystem
- {"content": "text content"} - Uses provided text directly  
- "direct string" - Treats string as literal content

Key Parameters:
- `model`: "flash" (fast, default), "pro" (advanced reasoning), or full model name (e.g., "gemini-1.5-pro-002")
- `grounding`: Enable Google Search integration for factual accuracy (default: False, may increase response time)
- `agent_name`: Store conversation in persistent memory for ongoing interactions
- `temperature`: Creativity level 0.0 (deterministic) to 1.0 (creative, default: 0.7)

Error Handling:
- Raises RuntimeError for Gemini API errors (authentication, quota, network)
- Raises ValueError for invalid file paths or malformed requests
- Large responses automatically saved to avoid MCP message size limits

Examples:
```python
# Basic question with file output
ask(
    prompt="Explain this code",
    output_file="/tmp/explanation.md",
    files=[{"path": "/path/to/code.py"}]
)

# Grounded research query
ask(
    prompt="What are the latest developments in quantum computing?",
    output_file="/tmp/research.md",
    grounding=True,
    model="pro"
)

# Persistent agent conversation
ask(
    prompt="Continue our discussion about the algorithm",
    output_file="/tmp/response.md",
    agent_name="code_reviewer",
    model="pro"
)

# Multiple file context
ask(
    prompt="Compare these implementations",
    output_file="/tmp/comparison.md",
    files=[
        {"path": "/path/to/impl1.py"},
        {"path": "/path/to/impl2.py"},
        {"content": "Additional context here"}
    ]
)
```""")
def ask(
    prompt: str,
    output_file: str,
    agent_name: Optional[str] = None,
    model: str = "flash",
    temperature: float = 0.7,
    grounding: bool = False,
    files: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """Ask Gemini a question with optional persistent memory."""
    # Resolve model name
    model_name = f"gemini-1.5-{model}" if model in ["flash", "pro"] else model
    
    try:
        # Get the model
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=8192,
        )
        
        # Configure tools for grounding if requested
        tools = None
        if grounding:
            tools = ["google_search_retrieval"]
        
        # Handle agent setup and system instruction (personality)
        agent = None
        system_instruction = None
        history = []
        
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if agent:
                if agent.personality:
                    system_instruction = agent.personality
                history = agent.get_conversation_history()
        
        gemini_model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            tools=tools,
            system_instruction=system_instruction
        )
        
        # Add file contents to prompt if provided
        file_contents = _resolve_files(files)
        if file_contents:
            prompt += "\n\n" + "\n\n".join(file_contents)
        
        # Start or continue conversation
        if history:
            # Continue existing conversation
            chat = gemini_model.start_chat(messages=history)
            response = chat.send_message(prompt)
        else:
            # New conversation
            response = gemini_model.generate_content(prompt)
        
        # Extract response text
        response_text = response.text
        
        # Calculate usage and cost
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        
        # Handle agent and usage
        return _handle_agent_and_usage(agent_name, prompt, response_text, model, input_tokens, output_tokens, output_file)
        
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


@mcp.tool(description="""Analyzes images using Gemini's advanced vision capabilities.

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

Error Handling:
- Raises ValueError for missing or invalid image inputs
- Raises RuntimeError for Gemini API errors (quota, authentication, unsupported formats)
- Supports common formats: JPEG, PNG, GIF, WebP
- Large images may be automatically resized by the API

Examples:
```python
# Analyze single image from file
analyze_image(
    prompt="Describe what you see in this image",
    output_file="/tmp/analysis.md",
    image_data="/path/to/photo.jpg",
    focus="general"
)

# Multiple images comparison
analyze_image(
    prompt="Compare these two diagrams and explain the differences",
    output_file="/tmp/comparison.md",
    images=[
        {"path": "/path/to/diagram1.png"},
        {"path": "/path/to/diagram2.png"}
    ],
    focus="technical"
)

# Extract text from image
analyze_image(
    prompt="Extract and transcribe all text from this document",
    output_file="/tmp/extracted_text.md",
    image_data={"path": "/path/to/document.jpg"},
    focus="text",
    model="pro"
)

# Base64 image analysis
analyze_image(
    prompt="Identify all objects in this scene",
    output_file="/tmp/objects.md",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    focus="objects"
)
```""")
def analyze_image(
    prompt: str,
    output_file: str,
    image_data: Optional[str] = None,
    images: Optional[List[Union[str, Dict[str, str]]]] = None,
    focus: str = "general",
    model: str = "pro",
    agent_name: Optional[str] = None
) -> str:
    """Analyze images with Gemini vision model."""
    if not image_data and not images:
        raise ValueError("Either image_data or images must be provided")
    
    # Resolve model name
    model_name = f"gemini-1.5-{model}" if model in ["flash", "pro"] else model
    
    try:
        # Load images
        image_list = _resolve_images(image_data, images)
        
        # Enhance prompt based on focus
        if focus != "general":
            prompt = f"Focus on {focus} aspects. {prompt}"
        
        # Get the model
        gemini_model = genai.GenerativeModel(model_name)
        
        # Prepare content with images
        content = [prompt] + image_list
        
        # Generate response
        response = gemini_model.generate_content(content)
        response_text = response.text
        
        # Calculate usage and cost
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        
        # Handle agent and usage
        image_desc = f"[Image analysis: {len(image_list)} image(s)]"
        return _handle_agent_and_usage(agent_name, f"{prompt} {image_desc}", response_text, model, input_tokens, output_tokens, output_file)
        
    except Exception as e:
        raise RuntimeError(f"Gemini vision API error: {e}")


@mcp.tool(description="""Generates high-quality images using Gemini's Imagen 3 model.

Creates images from text descriptions with advanced artistic capabilities. Generated images are saved as PNG files to a temporary location.

Prompt Guidelines:
- Be descriptive and specific for best results
- Include style, mood, lighting, and composition details
- Mention aspect ratio preferences if needed
- Avoid requesting copyrighted characters or inappropriate content

Examples:
```python
# Artistic image
generate_image(
    prompt="A serene mountain landscape at sunset, with golden light reflecting on a crystal-clear lake, painted in impressionist style",
    agent_name="artist_bot"
)

# Technical diagram
generate_image(
    prompt="Clean, minimalist flowchart showing a software deployment pipeline, with rounded rectangles and arrow connections, in professional blue and white colors"
)

# Portrait style
generate_image(
    prompt="Professional headshot of a confident software engineer in modern office setting, natural lighting, shallow depth of field"
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
    agent_name: Optional[str] = None
) -> str:
    """Generate images with Gemini using Imagen 3."""
    import tempfile
    from google import genai as google_genai
    from google.genai import types
    from PIL import Image
    from io import BytesIO
    
    # Use Imagen 3 for image generation
    api_model_name = "imagen-3.0-generate-002"
    pricing_model_name = "imagen-3"  # For pricing calculation
    
    # Create Gemini client for image generation
    client = google_genai.Client(api_key=settings.gemini_api_key)
    
    # Generate image using Gemini's generate_images
    response = client.models.generate_images(
        model=api_model_name,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
        )
    )
    
    # Extract image data from response
    generated_image = response.generated_images[0]
    image_bytes = generated_image.image.image_bytes
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_bytes)
        saved_path = f.name
    
    # Handle agent memory and format usage
    response_text = f"✅ Image generated successfully!\n📁 Saved to: {saved_path}"
    return _handle_agent_and_usage(
        agent_name, 
        f"Generate image: {prompt}", 
        response_text,
        pricing_model_name,
        1, 0,  # 1 image, 0 output tokens
        "-",  # Always output to stdout for image generation
        "gemini"
    )


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
        # Test API key by listing models
        models = list(genai.list_models())
        available_models = [m.name.split('/')[-1] for m in models if 'gemini' in m.name]
        
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
- ask: Chat with Gemini models (requires output_file parameter)
- analyze_image: Image analysis with vision models (requires output_file parameter)
- generate_image: Generate images with Imagen 3
- create_agent: Create persistent conversation agents
- list_agents: List all agents and stats
- agent_stats: Get detailed agent statistics
- get_response: Retrieve messages from agent conversation history
- clear_agent: Clear agent conversation history
- delete_agent: Permanently delete agents
- server_info: Get server status"""
        
    except Exception as e:
        raise RuntimeError(f"Gemini API configuration error: {e}")


