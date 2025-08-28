"""Integration tests for system_prompt functionality across all LLM providers."""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from mcp_handley_lab.llm.claude.tool import analyze_image as claude_analyze_image
from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.gemini.tool import analyze_image as gemini_analyze_image
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.grok.tool import analyze_image as grok_analyze_image
from mcp_handley_lab.llm.grok.tool import ask as grok_ask
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.openai.tool import analyze_image as openai_analyze_image
from mcp_handley_lab.llm.openai.tool import ask as openai_ask

# Skip all API-requiring tests if API keys not available
gemini_available = bool(os.getenv("GEMINI_API_KEY"))
openai_available = bool(os.getenv("OPENAI_API_KEY"))
claude_available = bool(os.getenv("ANTHROPIC_API_KEY"))
grok_available = bool(os.getenv("XAI_API_KEY"))

# Provider configurations for testing
system_prompt_providers = [
    pytest.param(
        gemini_ask,
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        id="gemini",
        marks=pytest.mark.skipif(
            not gemini_available, reason="GEMINI_API_KEY not available"
        ),
    ),
    pytest.param(
        openai_ask,
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        id="openai",
        marks=pytest.mark.skipif(
            not openai_available, reason="OPENAI_API_KEY not available"
        ),
    ),
    pytest.param(
        claude_ask,
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        id="claude",
        marks=pytest.mark.skipif(
            not claude_available, reason="ANTHROPIC_API_KEY not available"
        ),
    ),
    pytest.param(
        grok_ask,
        "XAI_API_KEY",
        "grok-3-mini",
        id="grok",
        marks=pytest.mark.skip(reason="Grok uses gRPC (no VCR cassettes)"),
    ),
]

image_analysis_providers = [
    pytest.param(
        gemini_analyze_image,
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini",
        marks=pytest.mark.skipif(
            not gemini_available, reason="GEMINI_API_KEY not available"
        ),
    ),
    pytest.param(
        openai_analyze_image,
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai",
        marks=pytest.mark.skipif(
            not openai_available, reason="OPENAI_API_KEY not available"
        ),
    ),
    pytest.param(
        claude_analyze_image,
        "ANTHROPIC_API_KEY",
        "claude-3-5-sonnet-20240620",
        id="claude",
        marks=pytest.mark.skipif(
            not claude_available, reason="ANTHROPIC_API_KEY not available"
        ),
    ),
    pytest.param(
        grok_analyze_image,
        "XAI_API_KEY",
        "grok-2-vision-1212",
        id="grok",
        marks=pytest.mark.skip(reason="Grok uses gRPC (no VCR cassettes)"),
    ),
]


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a sample test image for image analysis tests."""
    img = Image.new("RGB", (100, 100), color="blue")
    image_path = tmp_path / "test_image.png"
    img.save(image_path, format="PNG")
    return image_path


class TestSystemPromptBasic:
    """Test basic system prompt functionality."""

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_system_prompt_parameter_exists(self, ask_func, api_key, model):
        """Test that system_prompt parameter is accepted by all providers."""
        # Test with a simple math question and specific system prompt

        # Provider-specific parameters
        base_params = {
            "prompt": "What is 2+2?",
            "output_file": "/tmp/test_system_prompt.txt",
            "agent_name": "test_system_prompt_param",
            "model": model,
            "system_prompt": "You are a helpful math tutor. Always explain your reasoning.",
            "files": [],
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

        assert result.content is not None
        assert len(result.content) > 0

        # Verify response reflects the system prompt (should be explanatory)
        assert len(result.content) > 10  # Should be more than just "4"

    @pytest.mark.vcr
    @pytest.mark.parametrize("analyze_func,api_key,model", image_analysis_providers)
    def test_system_prompt_image_analysis(
        self, analyze_func, api_key, model, sample_image_path
    ):
        """Test system_prompt works with image analysis tools."""

        # Provider-specific parameters
        base_params = {
            "prompt": "What do you see in this image?",
            "output_file": "/tmp/test_image_system_prompt.txt",
            "agent_name": "test_image_system_prompt",
            "model": model,
            "files": [str(sample_image_path)],
            "system_prompt": "You are a professional art critic. Provide detailed, sophisticated analysis.",
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

        result = analyze_func(**base_params)

        assert result.content is not None
        assert len(result.content) > 0


class TestSystemPromptPersistence:
    """Test that system prompts are remembered across calls."""

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_system_prompt_persistence(self, ask_func, api_key, model):
        """Test that system prompt is remembered across multiple calls."""
        agent_name = f"test_persistence_{model.replace('-', '_')}"

        # Provider-specific parameters
        def get_base_params(prompt, output_file, system_prompt=None):
            base_params = {
                "prompt": prompt,
                "output_file": output_file,
                "agent_name": agent_name,
                "model": model,
                "files": [],
            }
            if system_prompt:
                base_params["system_prompt"] = system_prompt
            else:
                base_params["system_prompt"] = None

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
            return base_params

        # First call: Set system prompt
        params1 = get_base_params(
            "What is 3+3?",
            "/tmp/test_persistence1.txt",
            "You are a concise math expert. Give only the answer and one short explanation.",
        )
        result1 = ask_func(**params1)

        assert result1.content is not None
        content1 = result1.content

        # Second call: No system prompt provided - should use remembered one
        params2 = get_base_params(
            "What is 4+4?",
            "/tmp/test_persistence2.txt",
            None,  # No system prompt - should use remembered one
        )
        result2 = ask_func(**params2)

        assert result2.content is not None
        content2 = result2.content

        # Both responses should be concise (reflecting the system prompt)
        # This is a heuristic test - responses should be relatively short
        assert len(content1) < 200  # Concise response
        assert len(content2) < 200  # Also concise (using remembered system prompt)

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_system_prompt_update(self, ask_func, api_key, model):
        """Test that system prompt can be updated and new one is remembered."""
        agent_name = f"test_update_{model.replace('-', '_')}"

        # Provider-specific parameters
        def get_base_params(prompt, output_file, system_prompt=None):
            base_params = {
                "prompt": prompt,
                "output_file": output_file,
                "agent_name": agent_name,
                "model": model,
                "files": [],
            }
            if system_prompt:
                base_params["system_prompt"] = system_prompt
            else:
                base_params["system_prompt"] = None

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
            return base_params

        # First call: Detailed system prompt
        params1 = get_base_params(
            "What is 5+5?",
            "/tmp/test_update1.txt",
            "You are a verbose math teacher. Explain everything in great detail with examples.",
        )
        result1 = ask_func(**params1)
        assert result1.content is not None
        content1 = result1.content

        # Second call: Change to brief system prompt
        params2 = get_base_params(
            "What is 6+6?",
            "/tmp/test_update2.txt",
            "You are brief. Give only the answer.",
        )
        result2 = ask_func(**params2)
        assert result2.content is not None
        content2 = result2.content

        # Third call: No system prompt - should use the new brief one
        params3 = get_base_params(
            "What is 7+7?",
            "/tmp/test_update3.txt",
            None,  # No system prompt
        )
        result3 = ask_func(**params3)
        assert result3.content is not None
        content3 = result3.content

        # First response should be verbose, second and third should be brief
        assert len(content1) > len(content2)  # Verbose vs brief
        assert len(content3) < 100  # Third response should also be brief

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_different_agents_different_prompts(self, ask_func, api_key, model):
        """Test that different agents can have different system prompts."""

        # Provider-specific parameters for Agent 1
        def get_base_params(prompt, output_file, agent_name, system_prompt=None):
            base_params = {
                "prompt": prompt,
                "output_file": output_file,
                "agent_name": agent_name,
                "model": model,
                "files": [],
            }
            if system_prompt:
                base_params["system_prompt"] = system_prompt
            else:
                base_params["system_prompt"] = None

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
            return base_params

        # Agent 1: Formal style
        params1 = get_base_params(
            "What is 8+2?",
            "/tmp/test_agent1.txt",
            f"formal_agent_{model.replace('-', '_')}",
            "You are a formal mathematics professor. Use proper mathematical terminology.",
        )
        result1 = ask_func(**params1)
        assert result1.content is not None
        content1 = result1.content

        # Agent 2: Casual style
        params2 = get_base_params(
            "What is 8+2?",
            "/tmp/test_agent2.txt",
            f"casual_agent_{model.replace('-', '_')}",
            "You are a friendly buddy. Be casual and use simple words.",
        )
        result2 = ask_func(**params2)
        assert result2.content is not None
        content2 = result2.content

        # Both should contain "10" but in different styles
        assert "10" in content1 or "ten" in content1.lower()
        assert "10" in content2 or "ten" in content2.lower()
        # Responses should be different due to different system prompts
        assert content1 != content2


class TestSystemPromptMemoryIntegration:
    """Test integration between system prompts and agent memory."""

    def test_agent_creation_with_system_prompt(self):
        """Test that agents are created with system prompts in memory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_storage_dir = memory_manager.storage_dir

            try:
                # Temporarily change storage directory
                memory_manager.storage_dir = Path(temp_dir)
                memory_manager.agents_dir = Path(temp_dir) / "agents"
                memory_manager.agents_dir.mkdir(parents=True, exist_ok=True)
                memory_manager._agents = {}

                # Create agent with system prompt
                agent = memory_manager.create_agent("test_agent", "You are helpful")

                assert agent.system_prompt == "You are helpful"
                assert (
                    memory_manager.get_agent("test_agent").system_prompt
                    == "You are helpful"
                )

                # Check file persistence
                agent_file = memory_manager.agents_dir / "test_agent.json"
                assert agent_file.exists()

                # Verify file content
                import json

                agent_data = json.loads(agent_file.read_text())
                assert agent_data["system_prompt"] == "You are helpful"

            finally:
                # Restore original storage
                memory_manager.storage_dir = original_storage_dir
                memory_manager.agents_dir = original_storage_dir / "agents"
                memory_manager._load_agents()

    def test_system_prompt_update_in_memory(self):
        """Test that system prompt updates are persisted in memory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_storage_dir = memory_manager.storage_dir

            try:
                # Setup temporary storage
                memory_manager.storage_dir = Path(temp_dir)
                memory_manager.agents_dir = Path(temp_dir) / "agents"
                memory_manager.agents_dir.mkdir(parents=True, exist_ok=True)
                memory_manager._agents = {}

                # Create agent
                agent = memory_manager.create_agent("test_agent", "Original prompt")
                assert agent.system_prompt == "Original prompt"

                # Update system prompt
                agent.system_prompt = "Updated prompt"
                memory_manager._save_agent(agent)

                # Verify update
                updated_agent = memory_manager.get_agent("test_agent")
                assert updated_agent.system_prompt == "Updated prompt"

                # Check file persistence
                agent_file = memory_manager.agents_dir / "test_agent.json"
                import json

                agent_data = json.loads(agent_file.read_text())
                assert agent_data["system_prompt"] == "Updated prompt"

            finally:
                # Restore original storage
                memory_manager.storage_dir = original_storage_dir
                memory_manager.agents_dir = original_storage_dir / "agents"
                memory_manager._load_agents()


class TestSystemPromptEdgeCases:
    """Test edge cases and error scenarios for system prompts."""

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_empty_system_prompt(self, ask_func, api_key, model):
        """Test behavior with empty system prompt."""

        # Provider-specific parameters
        base_params = {
            "prompt": "What is 9+1?",
            "output_file": "/tmp/test_empty_prompt.txt",
            "agent_name": f"empty_prompt_agent_{model.replace('-', '_')}",
            "model": model,
            "system_prompt": "",  # Empty string
            "files": [],
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
        assert result.content is not None

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_none_system_prompt(self, ask_func, api_key, model):
        """Test behavior with None system prompt."""

        # Provider-specific parameters
        base_params = {
            "prompt": "What is 1+9?",
            "output_file": "/tmp/test_none_prompt.txt",
            "agent_name": f"none_prompt_agent_{model.replace('-', '_')}",
            "model": model,
            "system_prompt": None,
            "files": [],
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
        assert result.content is not None

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_very_long_system_prompt(self, ask_func, api_key, model):
        """Test behavior with very long system prompt."""
        long_prompt = "You are a helpful assistant. " * 100  # Very long prompt

        # Provider-specific parameters
        base_params = {
            "prompt": "What is 6+4?",
            "output_file": "/tmp/test_long_prompt.txt",
            "agent_name": f"long_prompt_agent_{model.replace('-', '_')}",
            "model": model,
            "system_prompt": long_prompt,
            "files": [],
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
        assert result.content is not None

    @pytest.mark.vcr
    @pytest.mark.parametrize("ask_func,api_key,model", system_prompt_providers)
    def test_special_characters_system_prompt(self, ask_func, api_key, model):
        """Test system prompt with special characters and Unicode."""
        special_prompt = (
            "You are a helpful assistant 🤖. Use emojis: ∑, ∏, ∆, ∇, ∈, ∉, ∀, ∃"
        )

        # Provider-specific parameters
        base_params = {
            "prompt": "What is 3+7?",
            "output_file": "/tmp/test_special_prompt.txt",
            "agent_name": f"special_prompt_agent_{model.replace('-', '_')}",
            "model": model,
            "system_prompt": special_prompt,
            "files": [],
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
        assert result.content is not None
