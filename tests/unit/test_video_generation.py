"""Unit tests for Gemini Veo video generation adapter."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mcp_handley_lab.llm.providers.gemini import adapter

ADAPTER = "mcp_handley_lab.llm.providers.gemini.adapter"


def _video(video_bytes=b"mp4-bytes", mime_type="video/mp4"):
    return SimpleNamespace(video_bytes=video_bytes, mime_type=mime_type)


def _operation(done=True, error=None, videos=None, rai=None):
    response = SimpleNamespace(generated_videos=videos, rai_media_filtered_reasons=rai)
    return SimpleNamespace(done=done, error=error, response=response)


def _client_returning(initial_op, poll_ops=()):
    """Build a mock client whose generate_videos returns initial_op and whose
    operations.get yields the supplied poll_ops in sequence."""
    client = MagicMock()
    client.models.generate_videos.return_value = initial_op
    client.operations.get.side_effect = list(poll_ops)
    return client


class TestVideoGenerationAdapter:
    def test_basic_success_no_download(self):
        video = _video()
        op = _operation(done=True, videos=[SimpleNamespace(video=video)])
        client = _client_returning(op)
        with patch(f"{ADAPTER}.get_client", return_value=client):
            result = adapter.video_generation_adapter(
                "a cat", "veo-3.1-generate-preview"
            )
        assert result["video_bytes"] == b"mp4-bytes"
        assert result["mime_type"] == "video/mp4"
        assert result["duration_seconds"] == 8  # YAML default
        client.files.download.assert_not_called()

    def test_audio_param_not_forwarded(self):
        # The Developer API rejects generate_audio; Veo 3.1 emits native audio by
        # default, so the adapter must never set it on the config.
        op = _operation(videos=[SimpleNamespace(video=_video())])
        client = _client_returning(op)
        with patch(f"{ADAPTER}.get_client", return_value=client):
            adapter.video_generation_adapter("x", "veo-3.1-generate-preview")
        config = client.models.generate_videos.call_args.kwargs["config"]
        assert config.generate_audio is None

    def test_only_set_kwargs_forwarded(self):
        op = _operation(videos=[SimpleNamespace(video=_video())])
        client = _client_returning(op)
        with patch(f"{ADAPTER}.get_client", return_value=client):
            adapter.video_generation_adapter(
                "x",
                "veo-3.1-generate-preview",
                aspect_ratio="16:9",
                negative_prompt="blurry",
            )
        config = client.models.generate_videos.call_args.kwargs["config"]
        assert config.aspect_ratio == "16:9"
        assert config.negative_prompt == "blurry"
        assert config.resolution is None
        assert config.duration_seconds is None

    def test_requested_duration_used_for_pricing(self):
        op = _operation(videos=[SimpleNamespace(video=_video())])
        client = _client_returning(op)
        with patch(f"{ADAPTER}.get_client", return_value=client):
            result = adapter.video_generation_adapter(
                "x", "veo-3.1-generate-preview", duration_seconds=4
            )
        assert result["duration_seconds"] == 4

    def test_polls_until_done_then_downloads_when_bytes_missing(self):
        video = _video(video_bytes=None)
        pending = _operation(done=False)
        finished = _operation(done=True, videos=[SimpleNamespace(video=video)])
        client = _client_returning(pending, poll_ops=[finished])

        def _download(file):
            file.video_bytes = b"downloaded"

        client.files.download.side_effect = _download
        with patch(f"{ADAPTER}.get_client", return_value=client):
            result = adapter.video_generation_adapter(
                "x", "veo-3.1-generate-preview", poll_interval=0
            )
        client.operations.get.assert_called_once()
        client.files.download.assert_called_once()
        assert result["video_bytes"] == b"downloaded"

    def test_done_on_final_poll_does_not_timeout(self):
        # max_polls=1: initial pending, single poll returns done — must NOT timeout.
        pending = _operation(done=False)
        finished = _operation(done=True, videos=[SimpleNamespace(video=_video())])
        client = _client_returning(pending, poll_ops=[finished])
        with patch(f"{ADAPTER}.get_client", return_value=client):
            result = adapter.video_generation_adapter(
                "x", "veo-3.1-generate-preview", poll_interval=0, max_polls=1
            )
        assert result["video_bytes"] == b"mp4-bytes"

    def test_timeout_when_never_done(self):
        pending = _operation(done=False)
        client = _client_returning(
            pending, poll_ops=[_operation(done=False), _operation(done=False)]
        )
        with (
            patch(f"{ADAPTER}.get_client", return_value=client),
            pytest.raises(TimeoutError),
        ):
            adapter.video_generation_adapter(
                "x", "veo-3.1-generate-preview", poll_interval=0, max_polls=2
            )

    def test_operation_error_raises(self):
        op = _operation(done=True, error="quota exceeded")
        client = _client_returning(op)
        with (
            patch(f"{ADAPTER}.get_client", return_value=client),
            pytest.raises(RuntimeError, match="quota exceeded"),
        ):
            adapter.video_generation_adapter("x", "veo-3.1-generate-preview")

    def test_empty_videos_raises_with_rai_reasons(self):
        op = _operation(done=True, videos=[], rai=["safety"])
        client = _client_returning(op)
        with (
            patch(f"{ADAPTER}.get_client", return_value=client),
            pytest.raises(RuntimeError, match="safety"),
        ):
            adapter.video_generation_adapter("x", "veo-3.1-generate-preview")

    def test_image_to_video_resolves_input_image(self):
        op = _operation(videos=[SimpleNamespace(video=_video())])
        client = _client_returning(op)
        sentinel = object()
        with (
            patch(f"{ADAPTER}.get_client", return_value=client),
            patch(f"{ADAPTER}._resolve_video_image", return_value=sentinel) as rvi,
        ):
            adapter.video_generation_adapter(
                "x", "veo-3.1-generate-preview", input_image="/tmp/a.png"
            )
        rvi.assert_called_once_with("/tmp/a.png")
        assert client.models.generate_videos.call_args.kwargs["image"] is sentinel


class TestDurationThreading:
    def test_default_duration_threaded_from_yaml(self):
        from mcp_handley_lab.llm.model_loader import build_model_configs_dict

        configs = build_model_configs_dict("gemini")
        assert configs["veo-3.1-generate-preview"]["default_duration_seconds"] == 8
        assert configs["veo-2.0-generate-001"]["default_duration_seconds"] == 8


class TestVideoCapabilityFlag:
    def test_get_model_capabilities_marks_veo(self):
        from mcp_handley_lab.llm.registry import get_model_capabilities

        caps = get_model_capabilities("veo-3.1-generate-preview")["capabilities"]
        assert caps["video_generation"] is True
        assert caps["image_generation"] is False

    def test_non_video_model_not_marked(self):
        from mcp_handley_lab.llm.registry import get_model_capabilities

        caps = get_model_capabilities("gemini-3.1-pro-preview")["capabilities"]
        assert caps["video_generation"] is False

    def test_list_all_models_marks_veo(self):
        from mcp_handley_lab.llm.registry import list_all_models

        gemini = {m["id"]: m for m in list_all_models()["gemini"]}
        assert gemini["veo-3.1-generate-preview"]["capabilities"]["video_generation"]
        assert gemini["veo-2.0-generate-001"]["capabilities"]["video_generation"]


class TestResolveVideoImage:
    def test_data_uri(self):
        raw = b"\x89PNG\r\n\x1a\n"
        uri = "data:image/png;base64," + base64.b64encode(raw).decode()
        img = adapter._resolve_video_image(uri)
        assert img.image_bytes == raw
        assert img.mime_type == "image/png"

    def test_local_path_uses_from_file(self):
        with patch(f"{ADAPTER}.GenAIImage.from_file", return_value="IMG") as ff:
            result = adapter._resolve_video_image("/tmp/pic.jpg")
        ff.assert_called_once_with(location="/tmp/pic.jpg")
        assert result == "IMG"
