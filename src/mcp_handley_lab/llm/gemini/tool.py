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
    provider: str = "gemini"
) -> str:
    """Handle agent memory and return formatted usage info."""
    cost = calculate_cost(model, input_tokens, output_tokens, provider)
    
    # Store in agent memory if specified
    if agent_name:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)
        
        memory_manager.add_message(agent_name, "user", user_prompt, input_tokens, cost / 2)
        memory_manager.add_message(agent_name, "assistant", response_text, output_tokens, cost / 2)
    
    return format_usage(model, input_tokens, output_tokens, cost, provider)


@mcp.tool(description="Asks a question to a Gemini model with optional file analysis and agent memory.")
def ask(
    prompt: str,
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
        
        gemini_model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            tools=tools
        )
        
        # Build conversation history
        history = []
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if agent:
                history = agent.get_conversation_history()
        
        # Add file contents to prompt if provided
        file_contents = _resolve_files(files)
        if file_contents:
            prompt += "\n\n" + "\n\n".join(file_contents)
        
        # Start or continue conversation
        if history:
            # Continue existing conversation
            chat = gemini_model.start_chat(history=history[:-1] if history else [])
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
        usage_info = _handle_agent_and_usage(agent_name, prompt, response_text, model, input_tokens, output_tokens)
        
        return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


@mcp.tool(description="Analyzes images using Gemini's vision capabilities.")
def analyze_image(
    prompt: str,
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
        usage_info = _handle_agent_and_usage(agent_name, f"{prompt} {image_desc}", response_text, model, input_tokens, output_tokens)
        
        return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"Gemini vision API error: {e}")


@mcp.tool(description="Generates images using Gemini's image generation model.")
def generate_image(
    prompt: str,
    model: str = "imagen-3",
    agent_name: Optional[str] = None
) -> str:
    """Generate images with Gemini using Imagen 3."""
    import tempfile
    import base64
    from mcp_handley_lab.common.pricing import calculate_cost, format_usage
    from mcp_handley_lab.common.memory import memory_manager
    
    # Use Imagen 3 for image generation
    model_name = "imagen-3"
    
    # Create Gemini model for image generation
    gemini_model = genai.GenerativeModel(model_name)
    
    # Generate image using Gemini's generateContent with Imagen
    response = gemini_model.generate_content(
        contents=[prompt],
        generation_config={
            "response_mime_type": "image/png"
        }
    )
    
    # Extract base64 image data
    image_part = response.candidates[0].content.parts[0]
    image_data = base64.b64decode(image_part.inline_data.data)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_data)
        saved_path = f.name
    
    # Handle agent memory and format usage
    usage_info = _handle_agent_and_usage(
        agent_name, 
        f"Generate image: {prompt}", 
        f"Generated image saved to {saved_path}",
        model_name,
        1, 0,  # 1 image, 0 output tokens
        "gemini"
    )
    
    return f"✅ Image generated successfully!\n📁 Saved to: {saved_path}\n{usage_info}"


@mcp.tool(description="Creates a new named agent for persistent conversation memory.")
def create_agent(agent_name: str, personality: Optional[str] = None) -> str:
    """Create a new agent with optional personality."""
    try:
        agent = memory_manager.create_agent(agent_name, personality)
        personality_info = f" with personality: {personality}" if personality else ""
        return f"✅ Agent '{agent_name}' created successfully{personality_info}!"
    except ValueError as e:
        raise ValueError(str(e))


@mcp.tool(description="Lists all existing named agents and their summary statistics.")
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


@mcp.tool(description="Retrieves detailed statistics and history for a specific named agent.")
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


@mcp.tool(description="Clears the conversation history of a named agent.")
def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history."""
    success = memory_manager.clear_agent_history(agent_name)
    if success:
        return f"✅ Agent '{agent_name}' history cleared successfully!"
    else:
        raise ValueError(f"Agent '{agent_name}' not found")


@mcp.tool(description="Permanently deletes a named agent and all its data.")
def delete_agent(agent_name: str) -> str:
    """Delete an agent permanently."""
    success = memory_manager.delete_agent(agent_name)
    if success:
        return f"✅ Agent '{agent_name}' deleted permanently!"
    else:
        raise ValueError(f"Agent '{agent_name}' not found")


@mcp.tool(description="Checks the Gemini server status and API key configuration.")
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
- ask: Chat with Gemini models
- analyze_image: Image analysis with vision models
- generate_image: Generate images (not yet available)
- create_agent: Create persistent conversation agents
- list_agents: List all agents and stats
- agent_stats: Get detailed agent statistics
- clear_agent: Clear agent conversation history
- delete_agent: Permanently delete agents
- server_info: Get server status"""
        
    except Exception as e:
        raise RuntimeError(f"Gemini API configuration error: {e}")


