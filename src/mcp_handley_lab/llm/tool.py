"""Unified LLM Tool for AI interactions via MCP.

Provides a single entry point for multiple LLM providers (Gemini, OpenAI, Claude,
Mistral, Grok, Groq) with model-based provider inference and Git-backed memory.
Consolidates chat, image generation, audio transcription, OCR, and model listing.
"""

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import TextContent
from pydantic import Field

from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.llm.common import load_prompt_text
from mcp_handley_lab.llm.registry import (
    get_adapter,
    list_all_models,
    resolve_model,
    validate_options,
)
from mcp_handley_lab.llm.shared import conversation as _conversation
from mcp_handley_lab.llm.shared import process_llm_request, resolve_generation_adapter
from mcp_handley_lab.shared.models import LLMResult  # noqa: F401 - used in type hints

mcp = FastMCP("LLM Tool")


@mcp.resource("model://list")
def model_list() -> dict[str, list[dict[str, Any]]]:
    """All available LLM models grouped by provider with capabilities and pricing."""
    return list_all_models()


def _resolve_session_branch(branch: str) -> str:
    """Resolve 'session' branch to client-scoped ID for MCP context."""
    if branch != "session":
        return branch
    context = mcp.get_context()
    client_id = getattr(context, "client_id", None) or os.getpid()
    return f"_session_{client_id}"


def _detect_image_format(data: bytes) -> str:
    """Detect image format from magic bytes."""
    if len(data) < 12:
        return "png"  # Too short to detect, default
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "png"  # Default fallback


@mcp.tool(
    description="Send a message to an LLM. Provider is auto-detected from model name. "
    "Supports Gemini, OpenAI, Claude, Mistral, Grok, and Groq. "
    "Use conversation tool to manage branches and retrieve past responses. "
    "For vision/image analysis, provide images parameter with local paths or data URIs. "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, branch, commit_sha}."
)
def chat(
    prompt: str = Field(
        default="",
        description="The message to send to the LLM.",
    ),
    prompt_file: str = Field(
        default="",
        description="Path to a file containing the prompt. Cannot be used with 'prompt'.",
    ),
    prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for template substitution using ${var} syntax.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save the response. Empty string means no file output. "
        "Responses are always stored in memory (~/.mcp-handley-lab/) and can be "
        "retrieved via conversation(action='response').",
    ),
    branch: str = Field(
        default="session",
        description="Conversation branch name. 'session' auto-scopes to client. "
        "Use unique names for isolated conversations, 'false' to disable memory.",
    ),
    model: str = Field(
        default="gemini",
        description="Model or provider name. Provider is inferred automatically. "
        "Use provider names (gemini, openai, claude) for latest defaults, "
        "or specific model IDs. Aliases: 'deep-research' (autonomous web research). "
        "Use model://list resource or list_models() to see available options.",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness (0.0-2.0). Higher is more creative.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="Files to include as extra context (recommended for large content like code summaries). "
        "Accepts local paths. Text is inlined, binary is base64-encoded. "
        "Per-call only — not retained in branch history; re-pass on follow-up calls if needed.",
    ),
    images: list[str] = Field(
        default_factory=list,
        description="Images for vision analysis. Accepts: local paths or "
        "data URIs (data:image/png;base64,...). When non-empty, routes to "
        "vision model. Both files and images can be used simultaneously.",
    ),
    focus: str = Field(
        default="general",
        description="Analysis focus when images provided (e.g., 'ocr', 'objects', 'general'). "
        "Prepended to prompt when not 'general'.",
    ),
    system_prompt: str = Field(
        default="",
        description="System instructions for the conversation.",
    ),
    system_prompt_file: str = Field(
        default="",
        description="Path to a file containing system instructions.",
    ),
    system_prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for system prompt template substitution.",
    ),
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific options. Use model://list resource to discover. "
        "Examples: grounding (Gemini), reasoning_effort (OpenAI), enable_thinking (Claude).",
    ),
    from_ref: str = Field(
        default="",
        description="Fork from this ref when creating a new conversation branch. "
        "Use commit_sha from a previous response to fork from that point.",
    ),
) -> LLMResult:
    """Send a message to an LLM with automatic provider detection."""
    provider, canonical_model, config = resolve_model(model)
    validate_options(provider, model, config, options)
    resolved_branch = _resolve_session_branch(branch)
    generation_func = resolve_generation_adapter(provider, config, images)

    kwargs: dict[str, Any] = {
        "prompt_file": prompt_file or None,
        "prompt_vars": prompt_vars or None,
        "temperature": temperature,
        "files": files,
        "system_prompt": system_prompt or None,
        "system_prompt_file": system_prompt_file or None,
        "system_prompt_vars": system_prompt_vars or None,
        "options": options,
    }
    if images:
        kwargs["images"] = images
        kwargs["focus"] = focus

    return process_llm_request(
        prompt=prompt or None,
        output_file=output_file,
        branch=resolved_branch,
        model=canonical_model,
        provider=provider,
        generation_func=generation_func,
        from_ref=from_ref or None,
        **kwargs,
    )


@mcp.tool(
    description="Retrieve past LLM responses and manage conversation history. "
    "Use 'response' to get a previous assistant message from a branch (the primary way to retrieve results from chat). "
    "Actions: 'list' (all branches), 'log' (history with hashes), 'show' (content at ref), "
    "'response' (get assistant message by index), "
    "'edit' (start editing session with worktree), 'done' (end editing session)."
)
def conversation(
    action: str = Field(
        ...,
        description="Action to perform: 'list', 'log', 'show', 'response', 'edit', 'done'.",
    ),
    branch: str = Field(
        default="",
        description="Target branch for log/show/response actions.",
    ),
    ref: str = Field(
        default="",
        description="Specific commit ref for show action. If provided, takes precedence over branch.",
    ),
    index: int = Field(
        default=-1,
        description="For response action: assistant message index (-1=last, -2=second-to-last, 0=first).",
    ),
    limit: int = Field(
        default=20,
        description="For log action: maximum number of entries to return.",
    ),
    force: bool = Field(
        default=False,
        description="For done action: force removal even if lock not held by this process.",
    ),
    output_file: str = Field(
        default="",
        description="For response action: save content to this file path instead of returning inline.",
    ),
) -> dict[str, Any]:
    """Git interface for conversation management."""
    resolved_branch = _resolve_session_branch(branch) if branch else branch
    return _conversation(
        action=action,
        branch=resolved_branch,
        ref=ref,
        index=index,
        limit=limit,
        force=force,
        output_file=output_file,
    )


REVIEW_SYSTEM_PROMPT = (
    "You are a code reviewer. Review the provided code against any plan/specification. "
    "Be specific: reference file paths and line numbers. "
    "Assess: plan adherence, code quality, completeness, and readiness. "
    "If you cannot make a decision because relevant code is missing from the summary, "
    "state NEEDS MORE CODE and list the specific files or modules you need to see. "
    "If no blocking issues remain, state APPROVED. "
    "Otherwise, list required fixes with specific locations."
)

DEFAULT_REVIEW_PROMPT = (
    "Review this implementation. "
    "Check code quality, completeness, and readiness to proceed."
)


@mcp.tool(
    description="Review code with an external LLM. Runs code2prompt internally "
    "(with --line-numbers) from the current directory, then sends the summary + "
    "plan + any extra files to the LLM for review. "
    "Returns: {content, usage, branch, commit_sha}."
)
def review(
    plan: str = Field(
        default="",
        description="Path to plan/specification file to review against. "
        "Strongly recommended so the reviewer has a spec to assess compliance.",
    ),
    prompt: str = Field(
        default="",
        description="Additional instructions for the reviewer. "
        "If empty, uses a default review prompt.",
    ),
    model: str = Field(
        default="openai",
        description="Model or provider name for the reviewer.",
    ),
    branch: str = Field(
        default="session",
        description="Conversation branch for multi-round reviews. "
        "'session' auto-scopes to client.",
    ),
    include: list[str] = Field(
        default_factory=list,
        description="Glob patterns for code2prompt include (e.g., '*.py').",
    ),
    exclude: list[str] = Field(
        default_factory=list,
        description="Glob patterns for code2prompt exclude (e.g., '*_test.py').",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="Additional context files (e.g., CLAUDE.md).",
    ),
    output_file: str = Field(
        default="",
        description="File path to save the review response.",
    ),
    diff: bool = Field(
        default=False,
        description="Use git diff mode instead of full codebase scan.",
    ),
) -> LLMResult:
    """Review code by running code2prompt and sending to an LLM."""
    import tempfile

    if plan:
        plan = str(Path(plan).expanduser())
    files = [str(Path(f).expanduser()) for f in files if f]
    if output_file:
        output_file = str(Path(output_file).expanduser())

    fd, c2p_output = tempfile.mkstemp(suffix=".md", prefix="review_")
    os.close(fd)

    try:
        args = [".", "--output-file", c2p_output, "--line-numbers"]
        for pat in include:
            args.extend(["--include", pat])
        for pat in exclude:
            args.extend(["--exclude", pat])
        if diff:
            args.append("--diff")

        run_command(["code2prompt"] + args, timeout=120)

        all_files = [c2p_output] + ([plan] if plan else []) + files
        final_prompt = DEFAULT_REVIEW_PROMPT
        if prompt:
            final_prompt = f"{DEFAULT_REVIEW_PROMPT}\n\n{prompt}"

        provider, canonical_model, config = resolve_model(model)
        resolved_branch = _resolve_session_branch(branch)
        generation_func = resolve_generation_adapter(provider, config)

        return process_llm_request(
            prompt=final_prompt,
            output_file=output_file,
            branch=resolved_branch,
            model=canonical_model,
            provider=provider,
            generation_func=generation_func,
            files=all_files,
            system_prompt=REVIEW_SYSTEM_PROMPT,
        )
    finally:
        Path(c2p_output).unlink(missing_ok=True)


@mcp.tool(
    description="Generate an image from a text prompt. "
    "Use model://list resource to discover available image models. "
    "Supports Gemini (imagen-*, gemini-*-image), OpenAI (dall-e-*), and Grok (grok-*-image) models. "
    "Nano Banana models (gemini-*-image) support input_images for editing/reference. "
    "Returns: [TextContent(JSON metadata), Image(preview)]. "
    "Metadata includes: file_path, file_size_bytes, model, provider, cost, detected_format, enhanced_prompt, original_prompt."
)
def generate_image(
    prompt: str = Field(
        default="",
        description="Text description of the image to generate.",
    ),
    prompt_file: str = Field(
        default="",
        description="Path to a file containing the prompt. Cannot be used with 'prompt'.",
    ),
    prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for template substitution using ${var} syntax.",
    ),
    output_file: str = Field(
        ...,
        description="File path to save the generated image. Nano Banana outputs JPEG, Imagen outputs PNG.",
    ),
    model: str = Field(
        default="gemini-3-pro-image-preview",
        description="Image model. Provider auto-detected from name.",
    ),
    input_images: list[str] = Field(
        default_factory=list,
        description="Input images for editing (Nano Banana models only). "
        "Provide images to edit/transform based on the prompt. "
        "Accepts: local paths, URLs, or data URIs.",
    ),
    size: str = Field(
        default="",
        description="Image size. For Nano Banana: '1K', '2K', '4K'. For others: '1024x1024'.",
    ),
    quality: str = Field(
        default="",
        description="Image quality (e.g., 'hd'). Provider-specific.",
    ),
    aspect_ratio: str = Field(
        default="",
        description="Aspect ratio. Nano Banana supports: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.",
    ),
):  # No return type - allows mixed TextContent + Image content
    """Generate an image from a text prompt."""
    final_prompt = load_prompt_text(
        prompt or None, prompt_file or None, prompt_vars or None
    )
    if not final_prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    provider, canonical_model, _ = resolve_model(model)

    try:
        generation_func = get_adapter(provider, "image_generation")
    except ValueError as e:
        raise ValueError(
            f"Image generation not supported for {provider} models. "
            f"Supported: Gemini (imagen-*), OpenAI (dall-e-*), Grok (grok-*-image)"
        ) from e

    kwargs = {}
    if size:
        kwargs["size"] = size
    if quality:
        kwargs["quality"] = quality
    if aspect_ratio:
        kwargs["aspect_ratio"] = aspect_ratio
    if input_images:
        kwargs["input_images"] = input_images

    response_data = generation_func(
        prompt=final_prompt, model=canonical_model, **kwargs
    )

    # Defensive check for missing image_bytes
    if "image_bytes" not in response_data:
        raise ValueError(
            f"Provider {provider} did not return image_bytes. "
            f"Response keys: {list(response_data.keys())}"
        )

    # Ensure image_bytes is bytes (not base64 string)
    image_bytes = response_data["image_bytes"]
    if isinstance(image_bytes, str):
        import base64

        try:
            image_bytes = base64.b64decode(image_bytes, validate=True)
        except Exception as e:
            raise ValueError(f"Provider {provider} returned invalid base64: {e}") from e

    # Validate image_bytes is valid
    if not isinstance(image_bytes, bytes | bytearray) or len(image_bytes) == 0:
        raise ValueError(
            f"Provider {provider} returned invalid image_bytes: "
            f"type={type(image_bytes).__name__}, len={len(image_bytes) if image_bytes else 0}"
        )

    input_tokens = response_data.get("input_tokens", 0)
    output_tokens = response_data.get("output_tokens", 1)

    filepath = Path(output_file)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(image_bytes)

    cost = calculate_cost(
        canonical_model, input_tokens, output_tokens, provider, images_generated=1
    )

    # Detect actual format from bytes
    detected_format = _detect_image_format(image_bytes)

    # Build metadata dict
    metadata = {
        "file_path": str(filepath),
        "file_size_bytes": len(image_bytes),
        "model": canonical_model,
        "provider": provider,
        "cost": cost,
        "detected_format": detected_format,
        "enhanced_prompt": response_data.get("enhanced_prompt", ""),
        "original_prompt": final_prompt,
    }

    # Return both metadata and image preview (matches word/render pattern)
    return [
        TextContent(type="text", text=json.dumps(metadata, indent=2)),
        Image(data=image_bytes, format=detected_format),
    ]


@mcp.tool(
    description="Transcribe audio to text using Groq Whisper. "
    "Supports MP3, WAV, FLAC, OGG, M4A. Use model://list resource to discover audio models. "
    "Returns: {text, segments?: [{start, end, text}]}. Segments included if include_timestamps=true."
)
def transcribe(
    audio_path: str = Field(
        ...,
        description="Path to audio file.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save transcription as JSON. Empty means no file output.",
    ),
    language: str = Field(
        default="",
        description="Language code (e.g., 'en', 'fr'). Empty for auto-detection.",
    ),
    include_timestamps: bool = Field(
        default=False,
        description="Include segment-level timestamps in output.",
    ),
) -> dict[str, Any]:
    """Transcribe audio using Groq Whisper."""
    adapter = get_adapter("groq", "audio_transcription")
    result = adapter(
        audio_path=audio_path,
        language=language,
        include_timestamps=include_timestamps,
    )

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))

    return result


@mcp.tool(
    description="Extract text from documents using Mistral OCR. "
    "Supports PDFs, images (PNG, JPG), PPTX, and DOCX. Use model://list resource to discover OCR models. "
    "Returns: {status, pages, output_file?, message}. Full OCR JSON saved to output_file if provided."
)
def ocr(
    document_path: str = Field(
        ...,
        description="Path to document file or URL. Supports PDF, images, PPTX, DOCX.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save full OCR results as JSON. Empty means no file output.",
    ),
    include_images: bool = Field(
        default=False,
        description="Include base64-encoded images with bounding boxes in output.",
    ),
) -> dict[str, Any]:
    """Process document with Mistral OCR for text extraction."""
    adapter = get_adapter("mistral", "ocr")
    result = adapter(document_path, include_images)

    pages = result.get("pages", [])
    response: dict[str, Any] = {
        "status": "success",
        "pages": len(pages),
        "message": f"OCR complete. {len(pages)} page(s) extracted.",
    }

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))
        response["output_file"] = output_file
        response["message"] += f" Full results saved to {output_file}"
    else:
        response["text"] = "\n\n".join(
            page.get("markdown", page.get("text", "")) for page in pages
        )

    return response


@mcp.tool(
    description="List all available models from all providers with full details including "
    "capabilities, supported options, pricing, and constraints. Use this to discover "
    "which models to use with chat, generate_image, transcribe, ocr, and mcp-llm-embeddings tools."
)
def list_models() -> dict[str, list[dict[str, Any]]]:
    """List all available models grouped by provider with capabilities."""
    return list_all_models()
