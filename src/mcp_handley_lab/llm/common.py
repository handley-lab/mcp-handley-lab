"""Shared utilities for LLM tools."""
import base64
import io
import mimetypes
import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from PIL import Image

from ..common.memory import memory_manager

# Enhance mimetypes with common text file types that might not be in the default database
# This runs once when the module is imported

# Programming languages and source code
mimetypes.add_type('text/x-c', '.c')
mimetypes.add_type('text/x-c++src', '.cpp')
mimetypes.add_type('text/x-java-source', '.java')
mimetypes.add_type('application/x-php', '.php')
mimetypes.add_type('application/sql', '.sql')
mimetypes.add_type('text/x-rustsrc', '.rs')
mimetypes.add_type('text/x-go', '.go')
mimetypes.add_type('text/x-ruby', '.rb')
mimetypes.add_type('text/x-perl', '.pl')
mimetypes.add_type('text/x-shellscript', '.sh')

# Documentation and markup
mimetypes.add_type('application/x-tex', '.tex')
mimetypes.add_type('text/x-diff', '.diff')
mimetypes.add_type('text/x-patch', '.patch')
mimetypes.add_type('text/xml', '.xml')  # Ensure consistent XML MIME type across environments

# Configuration and structured data
mimetypes.add_type('text/x-yaml', '.yaml')
mimetypes.add_type('text/x-yaml', '.yml')
mimetypes.add_type('application/toml', '.toml')
mimetypes.add_type('text/plain', '.ini')
mimetypes.add_type('text/plain', '.conf')
mimetypes.add_type('text/plain', '.log')

# Define text-based application types that match our add_type calls above
# This set should only contain application/* types that are known to be text-based.
# Note: text/* types are handled by the startswith('text/') check in is_text_file()
TEXT_BASED_APPLICATION_TYPES = {
    # Standard text-based application types
    'application/json',
    'application/javascript',
    'application/xhtml+xml',
    'application/rss+xml',
    'application/atom+xml',
    
    # Custom registered text-based application types (matching our add_type calls)
    'application/sql',
    'application/x-php',
    'application/x-tex',
    'application/toml',
}


def get_session_id(mcp_instance) -> str:
    """Get persistent session ID for this MCP server process."""
    try:
        context = mcp_instance.get_context()
        client_id = getattr(context, 'client_id', None)
        return f"_session_{client_id}" if client_id else f"_session_{os.getpid()}"
    except Exception:
        # When no MCP context (direct Python usage), use just process ID for persistence
        return f"_session_{os.getpid()}"


def determine_mime_type(file_path: Path) -> str:
    """Determine MIME type based on file extension using enhanced mimetypes module."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type if mime_type else 'application/octet-stream'


def is_gemini_supported_mime_type(mime_type: str) -> bool:
    """Check if MIME type is supported by Gemini API."""
    supported_mime_types = {
        # Documents
        'application/pdf', 'text/plain',
        # Images  
        'image/png', 'image/jpeg', 'image/webp',
        # Audio
        'audio/x-aac', 'audio/flac', 'audio/mp3', 'audio/mpeg', 'audio/m4a',
        'audio/opus', 'audio/pcm', 'audio/wav', 'audio/webm',
        # Video
        'video/mp4', 'video/mpeg', 'video/quicktime', 'video/mov', 'video/avi',
        'video/x-flv', 'video/mpg', 'video/webm', 'video/wmv', 'video/3gpp',
    }
    return mime_type in supported_mime_types


def get_gemini_safe_mime_type(file_path: Path) -> str:
    """Get a Gemini-safe MIME type, falling back to text/plain for text files.
    
    This proactive approach prevents unnecessary API calls by converting known
    unsupported text MIME types to text/plain before upload. For unknown MIME
    types, the original is preserved to let Gemini handle the validation.
    """
    original_mime = determine_mime_type(file_path)
    
    # If it's already supported, use it
    if is_gemini_supported_mime_type(original_mime):
        return original_mime
    
    # If it's a text file, fall back to text/plain (which is supported)
    if is_text_file(file_path):
        return 'text/plain'
    
    # For binary files, keep the original (let Gemini reject if unsupported)
    return original_mime


def is_gemini_mime_error(error_message: str) -> bool:
    """Check if an error message indicates an unsupported MIME type."""
    return "Unsupported MIME type" in str(error_message)


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file based on its MIME type."""
    mime_type = determine_mime_type(file_path)
    
    # Common text MIME types
    if mime_type.startswith('text/'):
        return True
    
    # Other common text-based formats categorized as 'application/*'
    return mime_type in TEXT_BASED_APPLICATION_TYPES


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
    
    usage_info = format_usage(input_tokens, output_tokens, cost)
    
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
