"""Shared utilities for LLM providers."""
from collections.abc import Callable

from ..common.memory import memory_manager
from ..common.pricing import calculate_cost
from .common import get_session_id, handle_agent_memory, handle_output


async def process_llm_request(
    prompt: str,
    output_file: str,
    agent_name: str | bool | None,
    model: str,
    provider: str,
    generation_func: Callable,
    mcp_instance,
    **kwargs,
) -> str:
    """Generic handler for LLM requests that abstracts common patterns."""
    # Input validation
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file.strip():
        raise ValueError("Output file is required and cannot be empty")
    if isinstance(agent_name, str) and not agent_name.strip():
        raise ValueError("Agent name cannot be empty")

    # Store original prompt for memory
    user_prompt = prompt
    history = []
    system_instruction = None
    actual_agent_name = agent_name

    # Handle agent memory
    use_memory = agent_name is not False
    if use_memory:
        if not actual_agent_name:
            actual_agent_name = get_session_id(mcp_instance)

        agent = memory_manager.get_agent(actual_agent_name)
        if agent:
            history = agent.get_history()
            system_instruction = agent.personality

    # Handle image analysis specific prompt modification
    if "image_data" in kwargs or "images" in kwargs:
        focus = kwargs.get("focus", "general")
        if focus != "general":
            prompt = f"Focus on {focus} aspects. {prompt}"
        # Add image description for memory
        image_count = 0
        if kwargs.get("image_data"):
            image_count += 1
        if kwargs.get("images"):
            image_count += len(kwargs.get("images", []))
        if image_count > 0:
            user_prompt = f"{user_prompt} [Image analysis: {image_count} image(s)]"

    # Call provider-specific generation function
    response_data = await generation_func(
        prompt=prompt,
        model=model,
        history=history,
        system_instruction=system_instruction,
        **kwargs,
    )

    # Extract common response data
    response_text = response_data["text"]
    input_tokens = response_data["input_tokens"]
    output_tokens = response_data["output_tokens"]
    cost = calculate_cost(model, input_tokens, output_tokens, provider)

    # Handle memory
    if use_memory:
        handle_agent_memory(
            actual_agent_name,
            user_prompt,
            response_text,
            input_tokens,
            output_tokens,
            cost,
            lambda: actual_agent_name,
        )

    # Handle output
    return handle_output(
        response_text, output_file, model, input_tokens, output_tokens, cost, provider
    )


def create_client_decorator(client_check_func: Callable, error_message: str):
    """Create a decorator that ensures client is initialized."""
    from functools import wraps

    def require_client(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not client_check_func():
                raise RuntimeError(error_message)
            return await func(*args, **kwargs)

        return wrapper

    return require_client
