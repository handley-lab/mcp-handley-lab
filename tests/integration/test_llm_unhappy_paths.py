"""Systematic unhappy path tests for LLM integration.

Tests error scenarios across OpenAI, Gemini, and Claude providers including
rate limiting, large inputs, network errors, content policy violations.
"""

from pathlib import Path

import pytest

from mcp_handley_lab.llm.claude.tool import analyze_image as claude_analyze_image
from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.gemini.tool import analyze_image as gemini_analyze_image
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.openai.tool import analyze_image as openai_analyze_image
from mcp_handley_lab.llm.openai.tool import ask as openai_ask

# Provider configurations for systematic testing (direct functions)
claude_api_key = "ANTHROPIC" + "_API_KEY"
llm_unhappy_providers = [
    pytest.param(openai_ask, "OPENAI_API_KEY", "gpt-4o-mini", id="openai"),
    pytest.param(gemini_ask, "GEMINI_API_KEY", "gemini-2.5-flash", id="gemini"),
    pytest.param(claude_ask, claude_api_key, "claude-3-haiku", id="claude"),
]

image_unhappy_providers = [
    pytest.param(openai_analyze_image, "OPENAI_API_KEY", "gpt-4o", id="openai"),
    pytest.param(gemini_analyze_image, "GEMINI_API_KEY", "gemini-2.5-pro", id="gemini"),
    pytest.param(claude_analyze_image, claude_api_key, "claude-3-sonnet", id="claude"),
]


@pytest.mark.integration
class TestLLMRateLimitingErrors:
    """Test rate limiting and quota scenarios."""

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_rapid_sequential_requests(
        self,
        skip_if_no_api_key,
        test_output_file,
        ask_func,
        api_key,
        model,
    ):
        """Test behavior with rapid sequential requests (potential rate limiting)."""
        skip_if_no_api_key(api_key)

        # Make multiple rapid requests
        requests = []
        for i in range(5):
            output_file = test_output_file.replace(".txt", f"_{i}.txt")
            try:
                # Provider-specific parameters
                base_params = {
                    "prompt": f"Count to {i + 1}",
                    "output_file": output_file,
                    "model": model,
                    "agent_name": "",
                    "files": [],
                    "system_prompt": None,
                }

                # Add provider-specific parameters
                if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                            "enable_logprobs": False,
                            "top_logprobs": 0,
                        }
                    )
                elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                            "grounding": False,
                        }
                    )
                elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                        }
                    )

                response = ask_func(**base_params)
                requests.append(response)
            except (ValueError, RuntimeError) as e:
                # Rate limiting errors are acceptable
                assert any(
                    keyword in str(e).lower()
                    for keyword in ["rate", "limit", "quota", "throttl", "too many"]
                )

        # At least some requests should succeed
        successful_requests = [
            r for r in requests if hasattr(r, "content") and r.content
        ]
        assert len(successful_requests) > 0, (
            "All requests failed - check API configuration"
        )


@pytest.mark.integration
class TestLLMLargeInputHandling:
    """Test handling of large and problematic inputs."""

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_extremely_large_prompt(
        self,
        skip_if_no_api_key,
        test_output_file,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of prompts that exceed context length limits."""
        skip_if_no_api_key(api_key)

        # Create a very large prompt (likely to exceed context limits)
        large_prompt = "Repeat this text: " + "A" * 100000  # 100k+ characters

        # Should either handle gracefully or provide clear error
        # Provider-specific parameters
        base_params = {
            "prompt": large_prompt,
            "output_file": test_output_file,
            "model": model,
            "agent_name": "",
            "files": [],
            "system_prompt": None,
        }

        # Add provider-specific parameters
        if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "enable_logprobs": False,
                    "top_logprobs": 0,
                }
            )
        elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "grounding": False,
                }
            )
        elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                }
            )

        try:
            result = ask_func(**base_params)

            # If successful, response should be reasonable
            assert result.content is not None

        except (ValueError, RuntimeError) as e:
            # Expected errors for oversized prompts
            assert any(
                keyword in str(e).lower()
                for keyword in [
                    "context",
                    "length",
                    "limit",
                    "token",
                    "size",
                    "too large",
                    "maximum",
                ]
            )

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_large_file_input_handling(
        self,
        skip_if_no_api_key,
        test_output_file,
        tmp_path,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of very large file inputs."""
        skip_if_no_api_key(api_key)

        # Create large file (1MB+)
        large_file = tmp_path / "large_input.txt"
        large_content = "This is a large file. " * 50000  # ~1MB
        large_file.write_text(large_content)

        # Provider-specific parameters
        base_params = {
            "prompt": "Summarize this large file in one sentence.",
            "output_file": test_output_file,
            "files": [str(large_file)],
            "model": model,
            "agent_name": "",
            "system_prompt": None,
        }

        # Add provider-specific parameters
        if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "enable_logprobs": False,
                    "top_logprobs": 0,
                }
            )
        elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "grounding": False,
                }
            )
        elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                }
            )

        try:
            result = ask_func(**base_params)

            # If successful, should provide reasonable response
            assert result.content is not None
            assert len(result.content) > 0

        except (ValueError, RuntimeError) as e:
            # Expected errors for oversized files
            assert any(
                keyword in str(e).lower()
                for keyword in ["file", "size", "limit", "large", "token", "context"]
            )

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_problematic_characters_handling(
        self,
        skip_if_no_api_key,
        test_output_file,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of problematic characters and encoding issues."""
        skip_if_no_api_key(api_key)

        # Test various problematic character combinations
        problematic_prompts = [
            "Unicode test: 🚀 💻 🤖 中文 العربية עברית",  # Mixed unicode
            "Control chars: \x00\x01\x02\x03",  # Control characters
            "Emoji flood: " + "🎉" * 1000,  # Many emojis
            "Mixed encoding: café naïve résumé",  # Accented characters
            "Special symbols: ∑∞∆∇∂∫∮∯∰∱",  # Math symbols
        ]

        for i, prompt in enumerate(problematic_prompts):
            output_file = test_output_file.replace(".txt", f"_char_{i}.txt")
            try:
                # Provider-specific parameters
                base_params = {
                    "prompt": f"Echo back: {prompt}",
                    "output_file": output_file,
                    "model": model,
                    "agent_name": "",
                    "files": [],
                    "system_prompt": None,
                }

                # Add provider-specific parameters
                if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                            "enable_logprobs": False,
                            "top_logprobs": 0,
                        }
                    )
                elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                            "grounding": False,
                        }
                    )
                elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                    base_params.update(
                        {
                            "temperature": 1.0,
                            "max_output_tokens": 0,
                        }
                    )

                result = ask_func(**base_params)

                # If successful, should handle characters properly
                assert result.content is not None
                content = Path(output_file).read_text(encoding="utf-8")
                assert len(content.strip()) > 0

            except (ValueError, RuntimeError, UnicodeError) as e:
                # Character encoding errors are acceptable for some inputs
                assert any(
                    keyword in str(e).lower()
                    for keyword in [
                        "encoding",
                        "character",
                        "unicode",
                        "invalid",
                        "decode",
                    ]
                )


@pytest.mark.integration
class TestLLMFileInputErrors:
    """Test file input error scenarios."""

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_nonexistent_file_input(
        self,
        skip_if_no_api_key,
        test_output_file,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of non-existent file inputs."""
        skip_if_no_api_key(api_key)

        nonexistent_file = "/path/to/nonexistent/file.txt"

        # Provider-specific parameters
        base_params = {
            "prompt": "Analyze this file.",
            "output_file": test_output_file,
            "files": [nonexistent_file],
            "model": model,
            "agent_name": "",
            "system_prompt": None,
        }

        # Add provider-specific parameters
        if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "enable_logprobs": False,
                    "top_logprobs": 0,
                }
            )
        elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                    "grounding": False,
                }
            )
        elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
            base_params.update(
                {
                    "temperature": 1.0,
                    "max_output_tokens": 0,
                }
            )

        with pytest.raises(
            (ValueError, RuntimeError, FileNotFoundError),
            match="file.*not found|not.*exist|no such file|directory",
        ):
            ask_func(**base_params)

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_permission_denied_file(
        self,
        skip_if_no_api_key,
        test_output_file,
        tmp_path,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of files without read permissions."""
        skip_if_no_api_key(api_key)

        # Create file with no read permissions
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("Secret content")
        restricted_file.chmod(0o000)  # No permissions

        try:
            # Provider-specific parameters
            base_params = {
                "prompt": "Read this restricted file.",
                "output_file": test_output_file,
                "files": [str(restricted_file)],
                "model": model,
                "agent_name": "",
                "system_prompt": None,
            }

            # Add provider-specific parameters
            if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "enable_logprobs": False,
                        "top_logprobs": 0,
                    }
                )
            elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "grounding": False,
                    }
                )
            elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                    }
                )

            with pytest.raises(
                (ValueError, RuntimeError, PermissionError),
                match="permission|access|denied|readable",
            ):
                ask_func(**base_params)
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_binary_file_input(
        self,
        skip_if_no_api_key,
        test_output_file,
        tmp_path,
        ask_func,
        api_key,
        model,
    ):
        """Test handling of binary files that can't be read as text."""
        skip_if_no_api_key(api_key)

        # Create binary file
        binary_file = tmp_path / "binary.dat"
        binary_data = bytes(range(256))  # Binary data
        binary_file.write_bytes(binary_data)

        try:
            # Provider-specific parameters
            base_params = {
                "prompt": "Analyze this binary file.",
                "output_file": test_output_file,
                "files": [str(binary_file)],
                "model": model,
                "agent_name": "",
                "system_prompt": None,
            }

            # Add provider-specific parameters
            if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "enable_logprobs": False,
                        "top_logprobs": 0,
                    }
                )
            elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "grounding": False,
                    }
                )
            elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                    }
                )

            result = ask_func(**base_params)

            # If it succeeds, should handle gracefully
            assert result.content is not None
            content = Path(test_output_file).read_text()
            assert len(content) > 0

        except (ValueError, RuntimeError) as e:
            # Binary file errors are acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in [
                    "binary",
                    "decode",
                    "text",
                    "encoding",
                    "readable",
                    "mime",
                    "unsupported",
                ]
            )


@pytest.mark.integration
class TestLLMImageAnalysisUnhappyPaths:
    """Test image analysis error scenarios."""

    @pytest.mark.parametrize("analyze_func, api_key, model", image_unhappy_providers)
    def test_corrupted_image_input(
        self,
        skip_if_no_api_key,
        test_output_file,
        tmp_path,
        analyze_func,
        api_key,
        model,
    ):
        """Test handling of corrupted image files."""
        skip_if_no_api_key(api_key)

        # Create corrupted image file
        corrupted_image = tmp_path / "corrupted.png"
        corrupted_image.write_text("This is not a valid PNG file")

        # Provider-specific parameters
        base_params = {
            "prompt": "What's in this image?",
            "output_file": test_output_file,
            "files": [str(corrupted_image)],
            "model": model,
            "agent_name": "",
            "system_prompt": None,
        }

        # Add provider-specific parameters
        if (
            analyze_func.__name__ == "analyze_image"
            and "openai" in analyze_func.__module__
            or analyze_func.__name__ == "analyze_image"
            and "gemini" in analyze_func.__module__
            or analyze_func.__name__ == "analyze_image"
            and "claude" in analyze_func.__module__
        ):
            base_params.update(
                {
                    "max_output_tokens": 0,
                }
            )

        with pytest.raises(
            (ValueError, RuntimeError, Exception),
            match="image|invalid|corrupted|format|decode|Could not process image",
        ):
            analyze_func(**base_params)

    @pytest.mark.parametrize("analyze_func, api_key, model", image_unhappy_providers)
    def test_missing_image_file(
        self,
        skip_if_no_api_key,
        test_output_file,
        analyze_func,
        api_key,
        model,
    ):
        """Test handling of missing image files."""
        skip_if_no_api_key(api_key)

        nonexistent_image = "/path/to/nonexistent/image.png"

        # Provider-specific parameters
        base_params = {
            "prompt": "Analyze this missing image.",
            "output_file": test_output_file,
            "files": [nonexistent_image],
            "model": model,
            "agent_name": "",
            "system_prompt": None,
        }

        # Add provider-specific parameters
        if (
            analyze_func.__name__ == "analyze_image"
            and "openai" in analyze_func.__module__
            or analyze_func.__name__ == "analyze_image"
            and "gemini" in analyze_func.__module__
            or analyze_func.__name__ == "analyze_image"
            and "claude" in analyze_func.__module__
        ):
            base_params.update(
                {
                    "max_output_tokens": 0,
                }
            )

        with pytest.raises(
            (ValueError, RuntimeError, FileNotFoundError),
            match="file.*not found|not.*exist|no such file|directory",
        ):
            analyze_func(**base_params)


@pytest.mark.integration
class TestLLMProviderSpecificErrors:
    """Test provider-specific error scenarios."""

    @pytest.mark.vcr
    def test_openai_content_policy_violation(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test OpenAI content policy violation handling."""
        skip_if_no_api_key("OPENAI_API_KEY")

        # Use prompt that might trigger content policy (keep it mild for testing)
        policy_test_prompt = "Write detailed instructions for harmful activities"

        try:
            # Provider-specific parameters
            base_params = {
                "prompt": policy_test_prompt,
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": "",
                "files": [],
                "system_prompt": None,
                "temperature": 1.0,
                "max_output_tokens": 0,
                "enable_logprobs": False,
                "top_logprobs": 0,
            }

            openai_ask(**base_params)

            # OpenAI should either refuse or provide safe alternative
            content = Path(test_output_file).read_text()
            assert len(content.strip()) > 0  # Should provide some response

        except (ValueError, RuntimeError) as e:
            # Content policy errors are expected
            assert any(
                keyword in str(e).lower()
                for keyword in [
                    "policy",
                    "content",
                    "violation",
                    "inappropriate",
                    "safety",
                ]
            )

    @pytest.mark.vcr
    def test_gemini_safety_filter_activation(
        self, skip_if_no_api_key, test_output_file
    ):
        """Test Gemini safety filter activation."""
        skip_if_no_api_key("GEMINI_API_KEY")

        # Test prompt that might trigger Gemini's safety filters
        safety_test_prompt = "Provide information about dangerous activities"

        try:
            # Provider-specific parameters
            base_params = {
                "prompt": safety_test_prompt,
                "output_file": test_output_file,
                "model": "gemini-2.5-flash",
                "agent_name": "",
                "files": [],
                "system_prompt": None,
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            }

            gemini_ask(**base_params)

            # Gemini should either refuse or provide filtered response
            content = Path(test_output_file).read_text()
            assert len(content) > 0

        except (ValueError, RuntimeError) as e:
            # Safety filter activation is acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in ["safety", "filter", "block", "inappropriate", "policy"]
            )


@pytest.mark.integration
class TestLLMOutputFileErrors:
    """Test output file writing error scenarios."""

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_output_file_permission_denied(
        self, skip_if_no_api_key, tmp_path, ask_func, api_key, model
    ):
        """Test handling of output file permission errors."""
        skip_if_no_api_key(api_key)

        # Create directory without write permissions
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)  # Read and execute only

        output_file = readonly_dir / "output.txt"

        try:
            # Provider-specific parameters
            base_params = {
                "prompt": "Simple test",
                "output_file": str(output_file),
                "model": model,
                "agent_name": "",
                "files": [],
                "system_prompt": None,
            }

            # Add provider-specific parameters
            if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "enable_logprobs": False,
                        "top_logprobs": 0,
                    }
                )
            elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "grounding": False,
                    }
                )
            elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                    }
                )

            with pytest.raises(
                (ValueError, RuntimeError, PermissionError),
                match="permission|write|access|denied",
            ):
                ask_func(**base_params)
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    @pytest.mark.parametrize("ask_func, api_key, model", llm_unhappy_providers)
    def test_output_directory_not_found(
        self, skip_if_no_api_key, ask_func, api_key, model
    ):
        """Test handling of output file in non-existent directory."""
        skip_if_no_api_key(api_key)

        output_file = "/nonexistent/directory/output.txt"

        # Should either create directory or provide clear error
        try:
            # Provider-specific parameters
            base_params = {
                "prompt": "Simple test",
                "output_file": output_file,
                "model": model,
                "agent_name": "",
                "files": [],
                "system_prompt": None,
            }

            # Add provider-specific parameters
            if ask_func.__name__ == "ask" and "openai" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "enable_logprobs": False,
                        "top_logprobs": 0,
                    }
                )
            elif ask_func.__name__ == "ask" and "gemini" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                        "grounding": False,
                    }
                )
            elif ask_func.__name__ == "ask" and "claude" in ask_func.__module__:
                base_params.update(
                    {
                        "temperature": 1.0,
                        "max_output_tokens": 0,
                    }
                )

            ask_func(**base_params)

            # If successful, file should exist
            assert Path(output_file).exists()

        except (ValueError, RuntimeError, FileNotFoundError) as e:
            # Directory creation errors are acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in ["directory", "not found", "no such", "path", "create"]
            )
