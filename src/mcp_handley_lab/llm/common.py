"""Shared utilities for LLM tools."""

import base64
import mimetypes
import os
from pathlib import Path

from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.shared.models import ServerInfo

# Enhance mimetypes with common text file types that might not be in the default database
# This runs once when the module is imported

# Programming languages and source code
mimetypes.add_type("text/x-c", ".c")
mimetypes.add_type("text/x-c++src", ".cpp")
mimetypes.add_type("text/x-java-source", ".java")
mimetypes.add_type("application/x-php", ".php")
mimetypes.add_type("application/sql", ".sql")
mimetypes.add_type("text/x-rustsrc", ".rs")
mimetypes.add_type("text/x-go", ".go")
mimetypes.add_type("text/x-ruby", ".rb")
mimetypes.add_type("text/x-perl", ".pl")
mimetypes.add_type("text/x-shellscript", ".sh")

# Documentation and markup
mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/markdown", ".markdown")
mimetypes.add_type("application/x-tex", ".tex")
mimetypes.add_type("text/x-diff", ".diff")
mimetypes.add_type("text/x-patch", ".patch")
mimetypes.add_type(
    "text/xml", ".xml"
)  # Ensure consistent XML MIME type across environments

# Configuration and structured data
mimetypes.add_type("text/x-yaml", ".yaml")
mimetypes.add_type("text/x-yaml", ".yml")
mimetypes.add_type("application/toml", ".toml")
mimetypes.add_type("text/plain", ".ini")
mimetypes.add_type("text/plain", ".conf")
mimetypes.add_type("text/plain", ".log")

# A set of application/* MIME types that are known to be text-based.
# This is used by is_text_file() to correctly identify text files that
# don't start with the 'text/' prefix (e.g., 'application/json').
# Note: text/* types are handled by the startswith('text/') check in is_text_file()
TEXT_BASED_APPLICATION_TYPES = {
    # Standard text-based application types
    "application/json",
    "application/javascript",
    "application/xhtml+xml",
    "application/rss+xml",
    "application/atom+xml",
    # Custom registered text-based application types (matching our add_type calls)
    "application/sql",
    "application/x-php",
    "application/x-tex",
    "application/toml",
}


def get_session_id(mcp_instance, provider: str = "default") -> str:
    """Get persistent session ID for this MCP server process with provider isolation."""
    context = mcp_instance.get_context()
    client_id = getattr(context, "client_id", None)
    base_id = client_id if client_id else os.getpid()
    return f"_session_{provider}_{base_id}"


def determine_mime_type(file_path: Path) -> str:
    """Determine MIME type based on file extension using enhanced mimetypes module."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type if mime_type else "application/octet-stream"


def is_gemini_supported_mime_type(mime_type: str) -> bool:
    """Check if MIME type is supported by Gemini API."""
    supported_mime_types = {
        # Documents
        "application/pdf",
        "text/plain",
        # Images
        "image/png",
        "image/jpeg",
        "image/webp",
        # Audio
        "audio/x-aac",
        "audio/flac",
        "audio/mp3",
        "audio/mpeg",
        "audio/m4a",
        "audio/opus",
        "audio/pcm",
        "audio/wav",
        "audio/webm",
        # Video
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/mov",
        "video/avi",
        "video/x-flv",
        "video/mpg",
        "video/webm",
        "video/wmv",
        "video/3gpp",
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
        return "text/plain"

    # For binary files, keep the original (let Gemini reject if unsupported)
    return original_mime


def is_gemini_mime_error(error_message: str) -> bool:
    """Check if an error message indicates an unsupported MIME type."""
    return "Unsupported MIME type" in str(error_message)


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file based on its MIME type."""
    mime_type = determine_mime_type(file_path)

    # Common text MIME types
    if mime_type.startswith("text/"):
        return True

    # Other common text-based formats categorized as 'application/*'
    return mime_type in TEXT_BASED_APPLICATION_TYPES


def resolve_file_content(
    file_item: str | dict[str, str],
) -> tuple[str | None, Path | None]:
    """Resolve file input to content string and optional path."""
    if isinstance(file_item, str):
        return file_item, None
    elif isinstance(file_item, dict):
        if "content" in file_item:
            return file_item["content"], None
        elif "path" in file_item:
            file_path = Path(file_item["path"])
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            return None, file_path
    return None, None


def read_file_smart(
    file_path: Path, max_size: int = 20 * 1024 * 1024
) -> tuple[str, bool]:
    """Read file with size-aware strategy. Returns (content, is_text)."""
    file_size = file_path.stat().st_size

    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes > {max_size}")

    if is_text_file(file_path):
        content = file_path.read_text(encoding="utf-8")
        return f"[File: {file_path.name}]\n{content}", True

    # Binary file - base64 encode
    file_content = file_path.read_bytes()
    encoded_content = base64.b64encode(file_content).decode()
    mime_type = determine_mime_type(file_path)
    return (
        f"[Binary file: {file_path.name}, {mime_type}, {file_size} bytes]\n{encoded_content}",
        False,
    )


def resolve_image_data(image_item: str | dict[str, str]) -> bytes:
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
    provider: str,
) -> str:
    """Handle file output and return formatted response."""
    from mcp_handley_lab.common.pricing import format_usage

    usage_info = format_usage(input_tokens, output_tokens, cost)

    if output_file != "-":
        output_path = Path(output_file)
        output_path.write_text(response_text)
        char_count = len(response_text)
        line_count = response_text.count("\n") + 1
        return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n{usage_info}"
    else:
        return f"{response_text}\n\n{usage_info}"


def handle_agent_memory(
    agent_name: str | bool | None,
    user_prompt: str,
    response_text: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    session_id_func,
) -> str | None:
    """Handle agent memory storage. Returns actual agent name used."""
    # Handle memory disable patterns
    if isinstance(agent_name, str) and (
        agent_name.lower() == "false" or agent_name == ""
    ):
        agent_name = False

    # Use session-specific agent for "session" or if no agent_name provided (and memory not disabled)
    if agent_name == "session" or agent_name is None:
        agent_name = session_id_func()

    # Store in agent memory (only if memory not disabled)
    if agent_name is not False:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)

        memory_manager.add_message(
            agent_name, "user", user_prompt, input_tokens, cost / 2
        )
        memory_manager.add_message(
            agent_name, "assistant", response_text, output_tokens, cost / 2
        )
        return agent_name

    return None


def resolve_multimodal_content(
    files: list[str] | None = None, images: list[str] | None = None
) -> list[dict]:
    """
    Resolves file paths and image data into a standardized list of content blocks.
    Each block is a dict with 'type', 'mime_type', and 'data' (or 'text').
    """
    if files is None:
        files = []
    if images is None:
        images = []
    content_blocks = []

    # Process text/binary files
    for file_path_str in files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type = determine_mime_type(file_path)
        if is_text_file(file_path):
            text_content = file_path.read_text(encoding="utf-8")
            content_blocks.append(
                {
                    "type": "text_file",
                    "filename": file_path.name,
                    "text": text_content,
                }
            )
        else:
            # For binary files, pass as base64 data
            binary_data = file_path.read_bytes()
            content_blocks.append(
                {
                    "type": "binary_file",
                    "filename": file_path.name,
                    "mime_type": mime_type,
                    "data": base64.b64encode(binary_data),
                }
            )

    # Process images
    for image_item in images:
        image_bytes = resolve_image_data(image_item)

        # Determine mime type for the image
        if isinstance(image_item, str) and image_item.startswith("data:image"):
            mime_type = image_item.split(";")[0].split(":")[1]
        else:
            mime_type = determine_mime_type(Path(image_item))
            if not mime_type.startswith("image/"):
                mime_type = "image/jpeg"  # Default for safety

        content_blocks.append(
            {
                "type": "image",
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

    return content_blocks


def resolve_images_for_multimodal_prompt(
    prompt: str, images: list[str]
) -> tuple[str, list[dict]]:
    """
    Standardized image processing for multimodal prompts.

    Returns:
        tuple: (prompt_text, list of image content blocks)
        Each image block has: {"type": "image", "mime_type": str, "data": str}
    """
    if not images:
        return prompt, []

    image_blocks = []
    for image_path in images:
        image_bytes = resolve_image_data(image_path)

        # Determine mime type
        if isinstance(image_path, str) and image_path.startswith("data:image"):
            mime_type = image_path.split(";")[0].split(":")[1]
        else:
            mime_type = determine_mime_type(Path(image_path))
            if not mime_type.startswith("image/"):
                mime_type = "image/jpeg"

        image_blocks.append(
            {
                "type": "image",
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

    return prompt, image_blocks


def resolve_files_for_llm(
    files: list[str], max_file_size: int = 1024 * 1024
) -> list[str]:
    """Resolve list of file paths to inline content strings for LLM providers.

    Args:
        files: List of file paths
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        List of formatted content strings with file headers
    """
    if not files:
        return []

    inline_content = []
    for file_path_str in files:
        file_path = Path(file_path_str)
        try:
            content, is_text = read_file_smart(file_path, max_file_size)
            inline_content.append(content)
        except ValueError as e:
            if "too large" in str(e):
                # File too large - read truncated version
                if is_text_file(file_path):
                    content = file_path.read_text(encoding="utf-8")[
                        :100000
                    ]  # 100KB limit
                    inline_content.append(
                        f"[File: {file_path.name} (truncated)]\n{content}..."
                    )
                else:
                    inline_content.append(
                        f"[File: {file_path.name} - too large to include]"
                    )
            else:
                raise

    return inline_content


def build_server_info(
    provider_name: str,
    available_models: list[str],
    memory_manager,
    vision_support: bool = False,
    image_generation: bool = False,
) -> ServerInfo:
    """Build standardized ServerInfo object for LLM providers."""

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    # Build capabilities list
    capabilities = [
        f"ask - Chat with {provider_name} models (persistent memory enabled by default)",
        "list_models - List available models with detailed information",
        "server_info - Get server status",
    ]

    if vision_support:
        capabilities.insert(
            1,
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
        )

    if image_generation:
        if vision_support:
            capabilities.insert(
                2, f"generate_image - Generate images with {provider_name}"
            )
        else:
            capabilities.insert(
                1, f"generate_image - Generate images with {provider_name}"
            )

    # Build dependencies dict
    dependencies = {
        "api_key": "configured",
        "available_models": f"{len(available_models)} models",
        "active_agents": str(agent_count),
        "memory_storage": str(memory_manager.storage_dir),
    }

    if vision_support:
        dependencies["vision_support"] = "true"

    if image_generation:
        dependencies["image_generation"] = "true"

    return ServerInfo(
        name=f"{provider_name} Tool",
        version="1.0.0",
        status="active",
        capabilities=capabilities,
        dependencies=dependencies,
    )


def load_provider_models(provider: str) -> tuple[dict, str, callable]:
    """Load model configurations and return configs, default model, and config getter.

    Returns:
        tuple: (MODEL_CONFIGS dict, DEFAULT_MODEL str, _get_model_config function)
    """
    from mcp_handley_lab.llm.model_loader import (
        build_model_configs_dict,
        load_model_config,
    )

    # Load model configurations from YAML
    model_configs = build_model_configs_dict(provider)

    # Load default model from YAML
    config = load_model_config(provider)
    default_model = config["default_model"]

    # Return a closure for getting model config with fallback
    def get_model_config(model: str) -> dict:
        """Get model configuration with fallback to default."""
        return model_configs.get(model, model_configs[default_model])

    return model_configs, default_model, get_model_config
