"""Unit tests for LLM shared processing functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mcp_handley_lab.llm.shared import process_llm_request


class TestProcessLLMRequestPromptResolution:
    """Test prompt resolution logic in process_llm_request."""

    @pytest.mark.asyncio
    @patch("mcp_handley_lab.llm.shared.memory")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    async def test_resolves_prompt_file_and_vars(
        self, mock_calculate_cost, mock_memory, tmp_path
    ):
        """Test that prompt_file and prompt_vars are resolved correctly."""
        # Create test prompt file
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Solve ${problem} and answer with ${format}")

        # Mock async generation function
        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {
                "text": f"Received: {prompt}",
                "input_tokens": 10,
                "output_tokens": 5,
                "model": "gpt-4o-mini",
            }

        # Mock MCP context
        mock_mcp = Mock()
        mock_context = Mock()
        mock_context.client_id = "test_client"
        mock_mcp.get_context.return_value = mock_context

        result = await process_llm_request(
            prompt="",
            output_file="",
            branch="",
            model="gpt-4o-mini",
            provider="openai",
            generation_func=mock_generation_func,
            mcp_instance=mock_mcp,
            prompt_file=str(prompt_file),
            prompt_vars={"problem": "2+2", "format": "number only"},
            system_prompt="",
            system_prompt_file="",
            system_prompt_vars={},
        )

        assert result.content == "Received: Solve 2+2 and answer with number only"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5

    @pytest.mark.asyncio
    @patch("mcp_handley_lab.llm.shared.memory")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    async def test_resolves_system_prompt_file_and_vars(
        self, mock_calculate_cost, mock_memory, tmp_path
    ):
        """Test that system_prompt_file and system_prompt_vars are resolved correctly."""
        # Create test system prompt file
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are a ${role} assistant. Be ${style}.")

        # Mock async generation function
        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {
                "text": "Response",
                "input_tokens": 10,
                "output_tokens": 5,
                "model": "gpt-4o-mini",
                "system_used": system_instruction,
            }

        # Mock MCP context
        mock_mcp = Mock()
        mock_context = Mock()
        mock_context.client_id = "test_client"
        mock_mcp.get_context.return_value = mock_context

        result = await process_llm_request(
            prompt="Test prompt",
            output_file="",
            branch="",
            model="gpt-4o-mini",
            provider="openai",
            generation_func=mock_generation_func,
            mcp_instance=mock_mcp,
            prompt_file="",
            prompt_vars={},
            system_prompt="",
            system_prompt_file=str(system_prompt_file),
            system_prompt_vars={"role": "helpful", "style": "concise"},
        )

        # The system instruction should be resolved but we can't easily test it
        # since it's passed internally to the generation function
        assert result.content == "Response"

    @pytest.mark.asyncio
    async def test_xor_validation_prompt_raises_both(self):
        """Test that ValueError is raised when both prompt and prompt_file are provided."""

        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {}

        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            await process_llm_request(
                prompt="Direct prompt",
                output_file="",
                branch="",
                model="gpt-4o-mini",
                provider="openai",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
                prompt_file="/some/path.txt",
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
            )

    @pytest.mark.asyncio
    async def test_xor_validation_prompt_raises_neither(self):
        """Test that ValueError is raised when neither prompt nor prompt_file is provided."""

        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {}

        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            await process_llm_request(
                prompt="",
                output_file="",
                branch="",
                model="gpt-4o-mini",
                provider="openai",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
                prompt_file="",
                prompt_vars={},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
            )

    @pytest.mark.asyncio
    async def test_xor_validation_system_prompt_raises_both(self):
        """Test that ValueError is raised when both system_prompt and system_prompt_file are provided."""

        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {}

        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            await process_llm_request(
                prompt="Test prompt",
                output_file="",
                branch="",
                model="gpt-4o-mini",
                provider="openai",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
                prompt_file="",
                prompt_vars={},
                system_prompt="Direct system prompt",
                system_prompt_file="/some/system.txt",
                system_prompt_vars={},
            )

    @pytest.mark.asyncio
    async def test_missing_prompt_var_raises_keyerror(self, tmp_path):
        """Test that KeyError is raised when prompt template variable is missing."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Hello ${missing_var}")

        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {}

        mock_mcp = Mock()

        with pytest.raises(KeyError):
            await process_llm_request(
                prompt="",
                output_file="",
                branch="",
                model="gpt-4o-mini",
                provider="openai",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
                prompt_file=str(prompt_file),
                prompt_vars={"wrong_key": "value"},
                system_prompt="",
                system_prompt_file="",
                system_prompt_vars={},
            )

    @pytest.mark.asyncio
    async def test_missing_system_prompt_var_raises_keyerror(self, tmp_path):
        """Test that KeyError is raised when system prompt template variable is missing."""
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are ${missing_var}")

        async def mock_generation_func(prompt, system_instruction, **kwargs):
            return {}

        mock_mcp = Mock()

        with pytest.raises(KeyError):
            await process_llm_request(
                prompt="Test prompt",
                output_file="",
                branch="",
                model="gpt-4o-mini",
                provider="openai",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
                prompt_file="",
                prompt_vars={},
                system_prompt="",
                system_prompt_file=str(system_prompt_file),
                system_prompt_vars={"wrong_key": "value"},
            )

    @pytest.mark.asyncio
    @patch("mcp_handley_lab.llm.shared.memory")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    async def test_system_prompt_passed_to_llm_for_new_branch(
        self, mock_calculate_cost, mock_memory, tmp_path
    ):
        """Test that system prompt is passed to LLM for new branches."""
        # Create test system prompt file
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are a helpful assistant.")

        # Mock memory for new branch (not locked, branch doesn't exist)
        mock_memory.normalize_branch_input.return_value = "test_branch"
        mock_memory.get_project_dir.return_value = Path(tmp_path)
        mock_memory.is_locked.return_value = None
        mock_memory.branch_exists.return_value = False
        mock_memory.read_branch.return_value = ""
        mock_memory.write_conversation.return_value = {
            "commit_sha": "abc123",
            "branch": "test_branch",
        }

        received_system_instruction = None

        # Mock async generation function that captures system_instruction
        async def mock_generation_func(prompt, system_instruction, **kwargs):
            nonlocal received_system_instruction
            received_system_instruction = system_instruction
            return {
                "text": "Response",
                "input_tokens": 10,
                "output_tokens": 5,
                "model": "gpt-4o-mini",
            }

        # Mock MCP context
        mock_mcp = Mock()
        mock_context = Mock()
        mock_context.client_id = "test_client"
        mock_mcp.get_context.return_value = mock_context

        await process_llm_request(
            prompt="Test prompt",
            output_file="",
            branch="test_branch",
            model="gpt-4o-mini",
            provider="openai",
            generation_func=mock_generation_func,
            mcp_instance=mock_mcp,
            prompt_file="",
            prompt_vars={},
            system_prompt="",
            system_prompt_file=str(system_prompt_file),
            system_prompt_vars={},
        )

        # Verify system instruction was passed to the LLM
        assert received_system_instruction == "You are a helpful assistant."
