"""Audio Tool for speech-to-text transcription via MCP.

Provides audio transcription using Mistral's Voxtral model.
Supports MP3, WAV, FLAC, OGG, M4A formats.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Audio Tool")


@mcp.tool(
    description="Transcribe audio to text using Mistral Voxtral. "
    "Supports MP3, WAV, FLAC, OGG, M4A. "
    "Returns: {text, segments?: [{start, end, text}]}. Segments included if include_timestamps=true."
)
def transcribe(
    audio_path: str = Field(
        ...,
        description="Path to audio file or URL.",
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
    """Transcribe audio using Mistral Voxtral model."""
    from mcp_handley_lab.llm.registry import get_adapter

    adapter = get_adapter("mistral", "audio_transcription")
    result = adapter(
        audio_path=audio_path,
        language=language,
        include_timestamps=include_timestamps,
    )

    if output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))

    return result
