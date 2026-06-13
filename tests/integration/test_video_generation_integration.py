"""Integration tests for video generation via the MCP protocol.

The Veo SDK client is mocked at its boundary (`get_client`) rather than via a VCR
cassette: a real recording would require credentials and commit a multi-megabyte video
binary. Mocking the client still exercises the full tool path through `mcp.call_tool` —
capability gating, kwarg forwarding, file write, cost calculation, and metadata shape.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.llm.tool import mcp

ADAPTER = "mcp_handley_lab.llm.providers.gemini.adapter"


def _done_client(video_bytes=b"fake-mp4-bytes", mime_type="video/mp4"):
    video = SimpleNamespace(video_bytes=video_bytes, mime_type=mime_type)
    response = SimpleNamespace(
        generated_videos=[SimpleNamespace(video=video)],
        rai_media_filtered_reasons=None,
    )
    operation = SimpleNamespace(done=True, error=None, response=response)
    client = MagicMock()
    client.models.generate_videos.return_value = operation
    return client


@pytest.fixture
def video_path(tmp_path):
    return str(tmp_path / "out.mp4")


@pytest.mark.asyncio
async def test_generate_video_writes_file_and_metadata(video_path):
    client = _done_client()
    with patch(f"{ADAPTER}.get_client", return_value=client):
        _, response = await mcp.call_tool(
            "generate_video",
            {
                "prompt": "a bee landing on a cork",
                "output_file": video_path,
                "model": "veo-3.1-generate-preview",
            },
        )

    assert Path(response["file_path"]).exists()
    assert Path(video_path).read_bytes() == b"fake-mp4-bytes"
    assert response["file_size_bytes"] == len(b"fake-mp4-bytes")
    assert response["model"] == "veo-3.1-generate-preview"
    assert response["provider"] == "gemini"
    assert response["mime_type"] == "video/mp4"
    assert response["duration_seconds"] == 8
    assert response["cost"] == pytest.approx(8 * 0.75)  # per_second pricing
    assert response["original_prompt"] == "a bee landing on a cork"


@pytest.mark.asyncio
async def test_generate_video_forwards_config(video_path):
    client = _done_client()
    with patch(f"{ADAPTER}.get_client", return_value=client):
        await mcp.call_tool(
            "generate_video",
            {
                "prompt": "x",
                "output_file": video_path,
                "model": "veo-3.1-generate-preview",
                "aspect_ratio": "9:16",
                "duration_seconds": 6,
            },
        )
    config = client.models.generate_videos.call_args.kwargs["config"]
    assert config.aspect_ratio == "9:16"
    assert config.duration_seconds == 6
    assert config.generate_audio is None  # Developer API rejects this param


@pytest.mark.asyncio
async def test_generate_video_veo2_pricing(video_path):
    client = _done_client()
    with patch(f"{ADAPTER}.get_client", return_value=client):
        _, response = await mcp.call_tool(
            "generate_video",
            {
                "prompt": "x",
                "output_file": video_path,
                "model": "veo-2.0-generate-001",
            },
        )
    assert response["cost"] == pytest.approx(8 * 0.35)


@pytest.mark.asyncio
async def test_generate_video_rejects_non_video_model(video_path):
    with pytest.raises(ToolError, match="not a video generation model"):
        await mcp.call_tool(
            "generate_video",
            {
                "prompt": "x",
                "output_file": video_path,
                "model": "gemini-3.1-pro-preview",
            },
        )


@pytest.mark.asyncio
async def test_generate_video_rejects_blank_prompt(video_path):
    with pytest.raises(ToolError, match="Prompt is required"):
        await mcp.call_tool(
            "generate_video",
            {
                "prompt": "   ",
                "output_file": video_path,
                "model": "veo-3.1-generate-preview",
            },
        )
