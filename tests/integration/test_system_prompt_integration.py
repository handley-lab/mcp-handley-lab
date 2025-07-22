"""Integration tests for system_prompt functionality across all LLM providers."""
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.claude.tool import mcp as claude_mcp
from mcp_handley_lab.llm.gemini.tool import mcp as gemini_mcp
from mcp_handley_lab.llm.grok.tool import mcp as grok_mcp
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.openai.tool import mcp as openai_mcp
from PIL import Image

# Provider configurations for testing
system_prompt_providers = [
    pytest.param(
        gemini_mcp,
        "ask",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        id="gemini",
    ),
    pytest.param(
        openai_mcp,
        "ask",
        "OPENAI_API_KEY",
        "gpt-4o-mini",
        id="openai",
    ),
    pytest.param(
        claude_mcp,
        "ask",
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        id="claude",
    ),
    pytest.param(
        grok_mcp,
        "ask",
        "XAI_API_KEY",
        "grok-3-mini",
        id="grok",
        marks=pytest.mark.skip(reason="Grok uses gRPC (no VCR cassettes)"),
    ),
]

image_analysis_providers = [
    pytest.param(
        gemini_mcp,
        "analyze_image",
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini",
    ),
    pytest.param(
        openai_mcp,
        "analyze_image",
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai",
    ),
    pytest.param(
        claude_mcp,
        "analyze_image",
        "ANTHROPIC_API_KEY",
        "claude-3-5-sonnet-20240620",
        id="claude",
    ),
    pytest.param(
        grok_mcp,
        "analyze_image",
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
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_system_prompt_parameter_exists(
        self, mcp_instance, tool_name, api_key, model
    ):
        """Test that system_prompt parameter is accepted by all providers."""
        # Test with a simple math question and specific system prompt
        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 2+2?",
                "output_file": "/tmp/test_system_prompt.txt",
                "agent_name": "test_system_prompt_param",
                "model": model,
                "system_prompt": "You are a helpful math tutor. Always explain your reasoning.",
            },
        )

        assert "error" not in result
        assert "content" in result
        assert len(result["content"]) > 0

        # Verify response reflects the system prompt (should be explanatory)
        content = result["content"]
        assert len(content) > 10  # Should be more than just "4"

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", image_analysis_providers
    )
    async def test_system_prompt_image_analysis(
        self, mcp_instance, tool_name, api_key, model, sample_image_path
    ):
        """Test system_prompt works with image analysis tools."""
        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What do you see in this image?",
                "output_file": "/tmp/test_image_system_prompt.txt",
                "agent_name": "test_image_system_prompt",
                "model": model,
                "files": [str(sample_image_path)],
                "system_prompt": "You are a professional art critic. Provide detailed, sophisticated analysis.",
            },
        )

        assert "error" not in result
        assert "content" in result
        assert len(result["content"]) > 0


class TestSystemPromptPersistence:
    """Test that system prompts are remembered across calls."""

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_system_prompt_persistence(
        self, mcp_instance, tool_name, api_key, model
    ):
        """Test that system prompt is remembered across multiple calls."""
        agent_name = f"test_persistence_{model.replace('-', '_')}"

        # First call: Set system prompt
        _, result1 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 3+3?",
                "output_file": "/tmp/test_persistence1.txt",
                "agent_name": agent_name,
                "model": model,
                "system_prompt": "You are a concise math expert. Give only the answer and one short explanation.",
            },
        )

        assert "error" not in result1
        content1 = result1["content"]

        # Second call: No system prompt provided - should use remembered one
        _, result2 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 4+4?",
                "output_file": "/tmp/test_persistence2.txt",
                "agent_name": agent_name,
                "model": model,
                # Note: no system_prompt parameter
            },
        )

        assert "error" not in result2
        content2 = result2["content"]

        # Both responses should be concise (reflecting the system prompt)
        # This is a heuristic test - responses should be relatively short
        assert len(content1) < 200  # Concise response
        assert len(content2) < 200  # Also concise (using remembered system prompt)

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_system_prompt_update(self, mcp_instance, tool_name, api_key, model):
        """Test that system prompt can be updated and new one is remembered."""
        agent_name = f"test_update_{model.replace('-', '_')}"

        # First call: Detailed system prompt
        _, result1 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 5+5?",
                "output_file": "/tmp/test_update1.txt",
                "agent_name": agent_name,
                "model": model,
                "system_prompt": "You are a verbose math teacher. Explain everything in great detail with examples.",
            },
        )

        assert "error" not in result1
        content1 = result1["content"]

        # Second call: Change to brief system prompt
        _, result2 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 6+6?",
                "output_file": "/tmp/test_update2.txt",
                "agent_name": agent_name,
                "model": model,
                "system_prompt": "You are brief. Give only the answer.",
            },
        )

        assert "error" not in result2
        content2 = result2["content"]

        # Third call: No system prompt - should use the new brief one
        _, result3 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 7+7?",
                "output_file": "/tmp/test_update3.txt",
                "agent_name": agent_name,
                "model": model,
                # Note: no system_prompt parameter
            },
        )

        assert "error" not in result3
        content3 = result3["content"]

        # First response should be verbose, second and third should be brief
        assert len(content1) > len(content2)  # Verbose vs brief
        assert len(content3) < 100  # Third response should also be brief

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_different_agents_different_prompts(
        self, mcp_instance, tool_name, api_key, model
    ):
        """Test that different agents can have different system prompts."""
        # Agent 1: Formal style
        _, result1 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 8+2?",
                "output_file": "/tmp/test_agent1.txt",
                "agent_name": f"formal_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": "You are a formal mathematics professor. Use proper mathematical terminology.",
            },
        )

        assert "error" not in result1

        # Agent 2: Casual style
        _, result2 = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 8+2?",
                "output_file": "/tmp/test_agent2.txt",
                "agent_name": f"casual_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": "You are a friendly buddy. Be casual and use simple words.",
            },
        )

        assert "error" not in result2

        # Both should answer the same question but in different styles
        content1 = result1["content"]
        content2 = result2["content"]

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
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_empty_system_prompt(self, mcp_instance, tool_name, api_key, model):
        """Test behavior with empty system prompt."""
        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 9+1?",
                "output_file": "/tmp/test_empty_prompt.txt",
                "agent_name": f"empty_prompt_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": "",  # Empty string
            },
        )

        assert "error" not in result
        assert "content" in result

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_none_system_prompt(self, mcp_instance, tool_name, api_key, model):
        """Test behavior with None system prompt."""
        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 1+9?",
                "output_file": "/tmp/test_none_prompt.txt",
                "agent_name": f"none_prompt_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": None,
            },
        )

        assert "error" not in result
        assert "content" in result

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_very_long_system_prompt(
        self, mcp_instance, tool_name, api_key, model
    ):
        """Test behavior with very long system prompt."""
        long_prompt = "You are a helpful assistant. " * 100  # Very long prompt

        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 6+4?",
                "output_file": "/tmp/test_long_prompt.txt",
                "agent_name": f"long_prompt_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": long_prompt,
            },
        )

        assert "error" not in result
        assert "content" in result

    @pytest.mark.vcr
    @pytest.mark.parametrize(
        "mcp_instance,tool_name,api_key,model", system_prompt_providers
    )
    async def test_special_characters_system_prompt(
        self, mcp_instance, tool_name, api_key, model
    ):
        """Test system prompt with special characters and Unicode."""
        special_prompt = (
            "You are a helpful assistant 🤖. Use emojis: ∑, ∏, ∆, ∇, ∈, ∉, ∀, ∃"
        )

        _, result = await mcp_instance.call_tool(
            tool_name,
            {
                "prompt": "What is 3+7?",
                "output_file": "/tmp/test_special_prompt.txt",
                "agent_name": f"special_prompt_agent_{model.replace('-', '_')}",
                "model": model,
                "system_prompt": special_prompt,
            },
        )

        assert "error" not in result
        assert "content" in result
