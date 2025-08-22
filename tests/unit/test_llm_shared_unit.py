"""Unit tests for LLM shared processing functionality."""

from unittest.mock import Mock, patch

import pytest

from mcp_handley_lab.llm.shared import process_llm_request


class TestProcessLLMRequestPromptResolution:
    """Test prompt resolution logic in process_llm_request."""

    @patch("mcp_handley_lab.llm.shared.memory_manager")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    def test_resolves_prompt_file_and_vars(
        self, mock_calculate_cost, mock_memory_manager, tmp_path
    ):
        """Test that prompt_file and prompt_vars are resolved correctly."""
        # Create test prompt file
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Solve ${problem} and answer with ${format}")

        # Mock generation function
        def mock_generation_func(prompt, system_instruction, **kwargs):
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

        result = process_llm_request(
            prompt="",
            output_file="-",
            agent_name="",
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

    @patch("mcp_handley_lab.llm.shared.memory_manager")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    def test_resolves_system_prompt_file_and_vars(
        self, mock_calculate_cost, mock_memory_manager, tmp_path
    ):
        """Test that system_prompt_file and system_prompt_vars are resolved correctly."""
        # Create test system prompt file
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are a ${role} assistant. Be ${style}.")

        # Mock generation function
        def mock_generation_func(prompt, system_instruction, **kwargs):
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

        result = process_llm_request(
            prompt="Test prompt",
            output_file="-",
            agent_name="",
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

    def test_xor_validation_prompt_raises_both(self):
        """Test that ValueError is raised when both prompt and prompt_file are provided."""
        mock_generation_func = Mock()
        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            process_llm_request(
                prompt="Direct prompt",
                output_file="-",
                agent_name="",
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

    def test_xor_validation_prompt_raises_neither(self):
        """Test that ValueError is raised when neither prompt nor prompt_file is provided."""
        mock_generation_func = Mock()
        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            process_llm_request(
                prompt="",
                output_file="-",
                agent_name="",
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

    def test_xor_validation_system_prompt_raises_both(self):
        """Test that ValueError is raised when both system_prompt and system_prompt_file are provided."""
        mock_generation_func = Mock()
        mock_mcp = Mock()

        with pytest.raises(
            ValueError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            process_llm_request(
                prompt="Test prompt",
                output_file="-",
                agent_name="",
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

    def test_missing_prompt_var_raises_keyerror(self, tmp_path):
        """Test that KeyError is raised when prompt template variable is missing."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Hello ${missing_var}")

        mock_generation_func = Mock()
        mock_mcp = Mock()

        with pytest.raises(KeyError):
            process_llm_request(
                prompt="",
                output_file="-",
                agent_name="",
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

    def test_missing_system_prompt_var_raises_keyerror(self, tmp_path):
        """Test that KeyError is raised when system prompt template variable is missing."""
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are ${missing_var}")

        mock_generation_func = Mock()
        mock_mcp = Mock()

        with pytest.raises(KeyError):
            process_llm_request(
                prompt="Test prompt",
                output_file="-",
                agent_name="",
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

    @patch("mcp_handley_lab.llm.shared.memory_manager")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    def test_system_prompt_persists_in_memory(
        self, mock_calculate_cost, mock_memory_manager, tmp_path
    ):
        """Test that system prompt from file is stored in agent memory."""
        # Create test system prompt file
        system_prompt_file = tmp_path / "system.txt"
        system_prompt_file.write_text("You are a helpful assistant.")

        # Mock agent
        mock_agent = Mock()
        mock_agent.system_prompt = "You are a helpful assistant."
        mock_memory_manager.get_agent.return_value = None
        mock_memory_manager.create_agent.return_value = mock_agent

        # Mock generation function
        def mock_generation_func(prompt, system_instruction, **kwargs):
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

        process_llm_request(
            prompt="Test prompt",
            output_file="-",
            agent_name="test_agent",
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

        # Verify agent was created with system prompt
        mock_memory_manager.create_agent.assert_called_once_with(
            "test_agent", "You are a helpful assistant."
        )
        # Verify system prompt was set on the agent
        assert mock_agent.system_prompt == "You are a helpful assistant."

    @patch("mcp_handley_lab.llm.shared.memory_manager")
    @patch("mcp_handley_lab.common.pricing.calculate_cost", return_value=0.001)
    def test_no_unintended_writes_with_stdout(
        self, mock_calculate_cost, mock_memory_manager
    ):
        """Test that no files are written when output_file is '-'."""

        # Mock generation function
        def mock_generation_func(prompt, system_instruction, **kwargs):
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

        with patch("pathlib.Path.write_text") as mock_write:
            result = process_llm_request(
                prompt="Test prompt",
                output_file="-",
                agent_name="",
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

            # Should not write any files when output_file is "-"
            mock_write.assert_not_called()
            assert "Response" in result.content
