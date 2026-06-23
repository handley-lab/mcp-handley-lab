"""Unit tests for Gemini LLM provider adapter."""

import pytest

from mcp_handley_lab.llm.providers.gemini import adapter as gemini_adapter
from mcp_handley_lab.llm.providers.gemini.adapter import (
    MODEL_CONFIGS,
    deep_research_adapter,
    get_model_config,
    resolve_files,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-3.1-pro-preview", 65536),
            ("gemini-2.5-pro", 65536),
            ("gemini-2.5-flash", 65536),
            ("gemini-2.5-flash-lite", 64000),
        ],
    )
    def test_model_output_token_limits_parameterized(
        self, model_name, expected_output_tokens
    ):
        """Test model output token limits for all models."""
        assert MODEL_CONFIGS[model_name]["output_tokens"] == expected_output_tokens

    def test_model_configs_all_present(self):
        """Test that all expected models are in MODEL_CONFIGS."""
        expected_models = {
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3.1-pro-preview-customtools",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-live-preview",
            "gemini-3.1-flash-image",
            "gemini-3-flash-preview",
            "gemini-3-pro-image",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash-image",
            "gemini-deep-research",
            "imagen-4.0-generate-001",
            "imagen-4.0-fast-generate-001",
            "imagen-4.0-ultra-generate-001",
            "imagen-4.0-generate-preview-06-06",
            "veo-2.0-generate-001",
            "veo-3.1-generate-preview",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-3.1-pro-preview", 65536),
            ("gemini-2.5-flash", 65536),
        ],
    )
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test get_model_config with various known models."""
        config = get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens

    def test_get_model_config_unknown_model(self):
        """Test get_model_config falls back to default for unknown models."""
        config = get_model_config("unknown-model")
        # Should default to gemini-3.1-pro-preview
        assert config["output_tokens"] == 65536


class TestGeminiHelpers:
    """Test Gemini internal helper functions."""

    def test_resolve_files_processing_error(self):
        """Test file processing error in resolve_files - should fail fast."""
        # Use invalid path that will cause stat() to fail
        files = ["/invalid/nonexistent/path"]

        # Should raise FileNotFoundError instead of adding error text
        with pytest.raises(FileNotFoundError):
            resolve_files(files)


class _FakeHTTPResponse:
    """Minimal stand-in for an httpx.Response."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHTTPClient:
    """Fake httpx.Client that returns scripted POST/GET payloads."""

    def __init__(self, post_payload, get_payloads, **_kwargs):
        self._post_payload = post_payload
        self._get_payloads = list(get_payloads)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def post(self, *_args, **_kwargs):
        return _FakeHTTPResponse(self._post_payload)

    def get(self, *_args, **_kwargs):
        return _FakeHTTPResponse(self._get_payloads.pop(0))


# Representative completed Interactions API payload (real response schema)
COMPLETED_PAYLOAD = {
    "id": "v1_abc123",
    "status": "completed",
    "steps": [
        {"type": "user_input", "content": [{"text": "What is the capital of France?"}]},
        {
            "type": "model_output",
            "content": [
                {
                    "text": "The capital of France is Paris.",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://en.wikipedia.org/wiki/Paris",
                            "start_index": 0,
                            "end_index": 10,
                        }
                    ],
                }
            ],
        },
    ],
    "usage": {
        "total_input_tokens": 1234,
        "total_output_tokens": 5678,
        "total_tokens": 6912,
    },
}


class TestDeepResearchAdapter:
    """Test parsing of the Interactions API completed payload."""

    def _patch(self, monkeypatch, get_payloads):
        def _factory(*args, **kwargs):
            return _FakeHTTPClient(
                {"id": "v1_abc123"}, get_payloads, *args, **kwargs
            )

        import httpx

        monkeypatch.setattr(httpx, "Client", _factory)
        monkeypatch.setattr(gemini_adapter.time, "sleep", lambda *_: None)

    def test_parses_completed_payload(self, monkeypatch):
        """Text, tokens, and citations are extracted from the real schema."""
        self._patch(monkeypatch, [COMPLETED_PAYLOAD])

        result = deep_research_adapter(
            prompt="What is the capital of France?",
            model="gemini-deep-research",
            history=[],
            system_instruction="",
            options={"poll_interval": 0},
        )

        assert result["text"] == "The capital of France is Paris."
        assert result["input_tokens"] == 1234
        assert result["output_tokens"] == 5678
        assert result["total_tokens"] == 6912
        assert result["finish_reason"] == "stop"
        assert result["response_id"] == "v1_abc123"
        chunks = result["grounding_metadata"]["grounding_chunks"]
        assert chunks == [
            {"uri": "https://en.wikipedia.org/wiki/Paris", "title": ""}
        ]

    def test_completed_but_empty_text_raises(self, monkeypatch):
        """A completed task with no report text fails loudly."""
        empty_payload = {
            "id": "v1_abc123",
            "status": "completed",
            "steps": [
                {"type": "user_input", "content": [{"text": "q"}]},
                {"type": "model_output", "content": [{"text": ""}]},
            ],
            "usage": {},
        }
        self._patch(monkeypatch, [empty_payload])

        with pytest.raises(RuntimeError, match="no report text"):
            deep_research_adapter(
                prompt="q",
                model="gemini-deep-research",
                history=[],
                system_instruction="",
                options={"poll_interval": 0},
            )
