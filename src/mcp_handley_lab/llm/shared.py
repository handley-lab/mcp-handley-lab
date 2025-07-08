"""Shared utilities for LLM providers."""
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.llm.common import (
    get_session_id,
    handle_agent_memory,
    handle_output,
)
from mcp_handley_lab.llm.memory import memory_manager


def process_llm_request(
    prompt: str,
    output_file: str,
    agent_name: str,
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
    # agent_name validation: "session", "" (no memory), or actual name
    # No validation needed - all string values are valid

    # Store original prompt for memory
    user_prompt = prompt
    history = []
    system_instruction = None
    actual_agent_name = agent_name

    # Handle agent memory with string-based pattern
    use_memory = should_use_memory(agent_name)
    if use_memory:
        if agent_name == "session":
            actual_agent_name = get_session_id(mcp_instance)
        else:
            actual_agent_name = agent_name

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
    response_data = generation_func(
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


def should_use_memory(agent_name: str | bool | None) -> bool:
    """Determines if agent memory should be used based on the agent_name parameter."""
    if isinstance(agent_name, bool):
        return agent_name
    if agent_name is None:
        return True
    return agent_name != "" and agent_name.lower() != "false"


def process_image_generation(
    prompt: str,
    agent_name: str,
    model: str,
    provider: str,
    generation_func: Callable,
    mcp_instance,
    **kwargs,
) -> str:
    """Generic handler for LLM image generation requests."""
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    # Call the provider-specific generation function to get the image
    response_data = generation_func(prompt=prompt, model=model, **kwargs)
    image_bytes = response_data["image_bytes"]
    input_tokens = response_data.get("input_tokens", 0)
    output_tokens = response_data.get("output_tokens", 1)

    # Save to temporary file
    file_id = str(uuid.uuid4())[:8]
    filename = f"{provider}_generated_{file_id}.png"
    filepath = Path(tempfile.gettempdir()) / filename
    filepath.write_bytes(image_bytes)

    # Calculate cost
    cost = calculate_cost(
        model, input_tokens, output_tokens, provider, images_generated=1
    )

    # Handle agent memory
    handle_agent_memory(
        agent_name,
        f"Generate image: {prompt}",
        f"Generated image saved to {filepath}",
        input_tokens,
        output_tokens,
        cost,
        lambda: get_session_id(mcp_instance),
    )

    # Format response
    file_size = len(image_bytes)
    cost_str = f"${cost:.4f}" if cost < 0.01 else f"${cost:.2f}"
    return f"✅ Image Generated Successfully\n📁 Saved to: {filepath}\n📏 Size: {file_size:,} bytes\n💰 Cost: {cost_str}"
