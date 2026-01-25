"""Shared utilities for LLM tools."""

import base64
import mimetypes
import os
from pathlib import Path
from string import Template

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


def load_prompt_text(
    prompt: str | None,
    prompt_file: str | None,
    prompt_vars: dict[str, str] | None,
) -> str:
    """Resolve and render prompt from either string or file with optional templating.

    Args:
        prompt: Direct prompt text (mutually exclusive with prompt_file)
        prompt_file: Path to file containing prompt (mutually exclusive with prompt)
        prompt_vars: Variables for ${var} substitution in the prompt text

    Returns:
        Final resolved prompt text

    Raises:
        ValueError: If both or neither prompt sources provided, or template substitution fails
        FileNotFoundError: If prompt_file doesn't exist
    """
    if not (bool(prompt) ^ bool(prompt_file)):
        raise ValueError("Provide exactly one of 'prompt' or 'prompt_file'.")

    # Load prompt text
    if prompt_file:
        final_prompt = Path(prompt_file).read_text(encoding="utf-8")
    else:
        final_prompt = prompt  # type: ignore[assignment]  # XOR ensures non-None

    # Apply template substitution if variables provided
    if prompt_vars:
        final_prompt = Template(final_prompt).substitute(prompt_vars)

    return final_prompt


def get_session_id(provider: str = "default") -> str:
    """Get session ID for this process with provider isolation."""
    return f"_session_{provider}_{os.getpid()}"


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


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file based on its MIME type."""
    mime_type = determine_mime_type(file_path)

    # Common text MIME types
    if mime_type.startswith("text/"):
        return True

    # Other common text-based formats categorized as 'application/*'
    return mime_type in TEXT_BASED_APPLICATION_TYPES


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

    Raises:
        ValueError: If any file exceeds max_file_size (fail-fast, no silent truncation)
    """
    if not files:
        return []

    inline_content = []
    for file_path_str in files:
        file_path = Path(file_path_str)
        # Fail-fast: let ValueError propagate for files too large
        content, is_text = read_file_smart(file_path, max_file_size)
        inline_content.append(content)

    return inline_content


def load_provider_models(provider: str) -> tuple[dict, str]:
    """Load model configurations and return configs and default model.

    Returns:
        tuple: (MODEL_CONFIGS dict, DEFAULT_MODEL str)
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

    return model_configs, default_model
