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
from ...common.memory import memory_manager
from ...common.pricing import calculate_cost, format_usage

mcp = FastMCP("OpenAI Tool")

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)


def _resolve_files(files: Optional[List[Union[str, Dict[str, str]]]]) -> List[str]:
    """Resolve file inputs to content strings."""
    if not files:
        return []
    
    content_list = []
    for file_item in files:
        if isinstance(file_item, str):
            content_list.append(file_item)
        elif isinstance(file_item, dict):
            if "content" in file_item:
                content_list.append(file_item["content"])
            elif "path" in file_item:
                try:
                    content_list.append(Path(file_item["path"]).read_text())
                except (OSError, UnicodeDecodeError) as e:
                    content_list.append(f"Error reading file {file_item['path']}: {e}")
    
    return content_list


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
    provider: str = "openai"
) -> str:
    """Handle agent memory and return formatted usage info."""
    cost = calculate_cost(model, input_tokens, output_tokens, provider)
    
    if agent_name:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)
        
        memory_manager.add_message(agent_name, "user", user_prompt, input_tokens, cost / 2)
        memory_manager.add_message(agent_name, "assistant", response_text, output_tokens, cost / 2)
    
    return format_usage(model, input_tokens, output_tokens, cost, provider)


@mcp.tool(description="Asks a question to an OpenAI GPT model. Supports file analysis.")
def ask(
    prompt: str,
    agent_name: Optional[str] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    files: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """Ask OpenAI a question with optional persistent memory."""
    try:
        # Build conversation history
        messages = []
        if agent_name:
            agent = memory_manager.get_agent(agent_name)
            if agent:
                messages = agent.get_conversation_history()
        
        # Add file contents to prompt if provided
        file_contents = _resolve_files(files)
        if file_contents:
            prompt += "\n\n" + "\n\n".join(file_contents)
        
        # Add current prompt
        messages.append({"role": "user", "content": prompt})
        
        # Make API call
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        response_text = response.choices[0].message.content
        
        # Extract usage info
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # Handle agent and usage
        usage_info = _handle_agent_and_usage(agent_name, prompt, response_text, model, input_tokens, output_tokens)
        
        return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")


@mcp.tool(description="Analyzes one or more images with a prompt using a GPT vision model.")
def analyze_image(
    prompt: str,
    image_data: Optional[str] = None,
    images: Optional[List[Union[str, Dict[str, str]]]] = None,
    focus: str = "general",
    model: str = "gpt-4o",
    agent_name: Optional[str] = None
) -> str:
    """Analyze images with OpenAI vision model."""
    if not image_data and not images:
        raise ValueError("Either image_data or images must be provided")
    
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
                messages = agent.get_conversation_history()
        
        # Add current message with images
        messages.append({"role": "user", "content": content})
        
        # Make API call
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096
        )
        
        response_text = response.choices[0].message.content
        
        # Extract usage info
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # Handle agent and usage
        image_desc = f"[Image analysis: {len(image_list)} image(s)]"
        usage_info = _handle_agent_and_usage(agent_name, f"{prompt} {image_desc}", response_text, model, input_tokens, output_tokens)
        
        return f"{response_text}\n\n{usage_info}"
        
    except Exception as e:
        raise RuntimeError(f"OpenAI vision API error: {e}")


@mcp.tool(description="Generates an image from a text prompt using a DALL-E model.")
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: Optional[str] = None
) -> str:
    """Generate images with DALL-E."""
    try:
        # Make API call
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )
        
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


@mcp.tool(description="Checks the OpenAI server status and API key configuration.")
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
- ask: Chat with GPT models
- analyze_image: Image analysis with vision models  
- generate_image: Generate images with DALL-E
- server_info: Get server status"""
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API configuration error: {e}")