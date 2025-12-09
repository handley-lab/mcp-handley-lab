"""Groq LLM tool for AI interactions via MCP."""

import os
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP
from openai import BadRequestError, OpenAI
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import get_structured_model_listing
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult, ModelListing, ServerInfo

mcp = FastMCP("Groq Tool")

# Lazy initialization of Groq client
_client: OpenAI | None = None
_client_lock = threading.Lock()


def _get_client() -> OpenAI:
    """Get or create the global Groq client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            # Check env var directly (for tests) or fall back to settings
            api_key = os.environ.get("GROQ_API_KEY") or settings.groq_api_key
            if not api_key or api_key == "YOUR_API_KEY_HERE":
                raise RuntimeError("GROQ_API_KEY is not configured.")
            try:
                _client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Groq client: {e}") from e
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("groq")


def _groq_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Groq-specific text generation function for the shared processor."""
    model_config = _get_model_config(model)

    # Extract Groq-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Build messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.extend(history)

    # Resolve files and add to prompt
    inline_content = resolve_files_for_llm(files)
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append({"role": "user", "content": user_content})

    param_name = model_config.get("param", "max_tokens")
    default_tokens = model_config.get("output_tokens")

    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        param_name: max_output_tokens or default_tokens,
    }

    try:
        response = _get_client().chat.completions.create(**request_params)
    except BadRequestError as e:
        raise ValueError(f"Groq API error: {str(e)}") from e
    except Exception as e:
        raise ValueError(f"Groq API error: {str(e)}") from e

    return {
        "text": response.choices[0].message.content or "",
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": response.choices[0].finish_reason,
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "grounding_metadata": None,  # Groq doesn't support grounding
    }


@mcp.tool(
    description="Delegates a user query to the Groq inference service. Supports models like Llama3 and Mixtral. Use `agent_name` for persistent conversation threads."
)
def ask(
    prompt: str = Field(
        default=None,
        description="The user's question to delegate to the Groq AI service.",
    ),
    prompt_file: str = Field(
        default=None,
        description="Path to a file containing the prompt. Cannot be used with 'prompt'.",
    ),
    prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="A dictionary of variables for template substitution in the prompt using ${var} syntax.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save the response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread. Use 'session' for temporary memory, a custom name for persistent memory, or 'false' to disable.",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Groq model to use (e.g., 'llama3-8b-8192', 'mixtral-8x7b-32768').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls response randomness (0.0-2.0). Higher is more creative.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="Max response tokens. 0 for model's default max.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="List of file paths to include as context.",
    ),
    system_prompt: str = Field(
        default=None,
        description="System instructions for the conversation thread.",
    ),
    system_prompt_file: str = Field(
        default=None,
        description="Path to a file containing system instructions.",
    ),
    system_prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for template substitution in the system prompt using ${var} syntax.",
    ),
) -> LLMResult:
    """Ask a Groq-hosted model a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_vars=prompt_vars,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="groq",
        generation_func=_groq_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
        system_prompt_file=system_prompt_file,
        system_prompt_vars=system_prompt_vars,
    )


@mcp.tool(
    description="Retrieves a catalog of available Groq models with capabilities and pricing."
)
def list_models() -> ModelListing:
    """List available Groq models with detailed information."""
    try:
        api_models = _get_client().models.list()
        api_model_ids = {m.id for m in api_models.data}
    except Exception:
        # If API call fails, return listing without availability check
        api_model_ids = None
    return get_structured_model_listing("groq", api_model_ids)


@mcp.tool(description="Checks Groq Tool server status and API connectivity.")
def server_info() -> ServerInfo:
    """Get server status and Groq configuration."""
    available_models = list(MODEL_CONFIGS.keys())
    return build_server_info(
        provider_name="Groq",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=False,
        image_generation=False,
    )


@mcp.tool(description="Tests the connection to the Groq API by listing models.")
def test_connection() -> str:
    """Tests the connection to the Groq API."""
    try:
        models = _get_client().models.list()
        model_count = len(models.data)
        return f"✅ Connection successful. Found {model_count} models."
    except Exception as e:
        return f"❌ Connection failed: {e}"
