"""Shared utilities for LLM tools."""
import base64
import io
import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from PIL import Image

from ..common.memory import memory_manager


def get_session_id(mcp_instance) -> str:
    """Get persistent session ID for this MCP server process."""
    try:
        context = mcp_instance.get_context()
        client_id = getattr(context, 'client_id', None)
        return f"_session_{client_id}" if client_id else f"_session_{os.getpid()}_{int(time.time())}"
    except:
        return f"_session_{os.getpid()}_{int(time.time())}"


def determine_mime_type(file_path: Path) -> str:
    """Determine MIME type based on file extension."""
    suffix = file_path.suffix.lower()
    mime_types = {
        '.txt': 'text/plain', '.md': 'text/markdown', '.py': 'text/x-python',
        '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css',
        '.json': 'application/json', '.xml': 'application/xml', '.csv': 'text/csv',
        '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
    }
    return mime_types.get(suffix, 'application/octet-stream')


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file."""
    text_extensions = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', 
                      '.xml', '.csv', '.yaml', '.yml', '.toml', '.ini', '.conf', '.log'}
    return file_path.suffix.lower() in text_extensions


def resolve_file_content(file_item: Union[str, Dict[str, str]]) -> tuple[Optional[str], Optional[Path]]:
    """Resolve file input to content string and optional path."""
    if isinstance(file_item, str):
        return file_item, None
    elif isinstance(file_item, dict):
        if "content" in file_item:
            return file_item["content"], None
        elif "path" in file_item:
            file_path = Path(file_item["path"])
            if not file_path.exists():
                return f"Error: File not found: {file_path}", None
            return None, file_path
    return None, None


def read_file_smart(file_path: Path, max_size: int = 20 * 1024 * 1024) -> tuple[str, bool]:
    """Read file with size-aware strategy. Returns (content, is_text)."""
    file_size = file_path.stat().st_size
    
    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes > {max_size}")
    
    if is_text_file(file_path):
        try:
            content = file_path.read_text(encoding='utf-8')
            return f"[File: {file_path.name}]\n{content}", True
        except UnicodeDecodeError:
            pass
    
    # Binary file - base64 encode
    file_content = file_path.read_bytes()
    encoded_content = base64.b64encode(file_content).decode()
    mime_type = determine_mime_type(file_path)
    return f"[Binary file: {file_path.name}, {mime_type}, {file_size} bytes]\n{encoded_content}", False


def resolve_image_data(image_item: Union[str, Dict[str, str]]) -> bytes:
    """Resolve image input to raw bytes."""
    if isinstance(image_item, str):
        if image_item.startswith("data:image"):
            header, encoded = image_item.split(",", 1)
            return base64.b64decode(encoded)
        else:
            return Path(image_item).read_bytes()
    elif isinstance(image_item, dict):
        if "data" in image_item:
            return base64.b64decode(image_item["data"])
        elif "path" in image_item:
            return Path(image_item["path"]).read_bytes()
    
    raise ValueError(f"Invalid image format: {image_item}")


def handle_output(
    response_text: str,
    output_file: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    provider: str
) -> str:
    """Handle file output and return formatted response."""
    from ..common.pricing import format_usage
    
    usage_info = format_usage(model, input_tokens, output_tokens, cost, provider)
    
    if output_file != '-':
        output_path = Path(output_file)
        output_path.write_text(response_text)
        char_count = len(response_text)
        line_count = response_text.count('\n') + 1
        return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n{usage_info}"
    else:
        return f"{response_text}\n\n{usage_info}"


def handle_agent_memory(
    agent_name: Optional[Union[str, bool]],
    user_prompt: str,
    response_text: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    session_id_func
) -> Optional[str]:
    """Handle agent memory storage. Returns actual agent name used."""
    # Use session-specific agent if no agent_name provided (and memory not disabled)
    if not agent_name and agent_name is not False:
        agent_name = session_id_func()
    
    # Store in agent memory (only if memory not disabled)
    if agent_name is not False:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)
        
        memory_manager.add_message(agent_name, "user", user_prompt, input_tokens, cost / 2)
        memory_manager.add_message(agent_name, "assistant", response_text, output_tokens, cost / 2)
        return agent_name
    
    return None
