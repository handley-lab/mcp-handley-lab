"""Shared utilities for LLM providers."""
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.llm.common import (
    get_session_id,
    handle_agent_memory,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.shared.models import (
    GroundingMetadata,
    ImageGenerationResult,
    LLMResult,
)


def process_llm_request(
    prompt: str,
    output_file: str,
    agent_name: str,
    model: str,
    provider: str,
    generation_func: Callable,
    mcp_instance,
    **kwargs,
) -> LLMResult:
    """Generic handler for LLM requests that abstracts common patterns."""
    # Input validation
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file.strip():
        raise ValueError("Output file is required and cannot be empty")
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
    grounding_metadata_dict = response_data.get("grounding_metadata")
    finish_reason = response_data["finish_reason"]
    avg_logprobs = response_data["avg_logprobs"]
    model_version = response_data["model_version"]
    generation_time_ms = response_data.get(
        "generation_time_ms", 0
    )  # Only Gemini has this
    response_id = response_data["response_id"]
    # OpenAI-specific fields
    system_fingerprint = response_data.get("system_fingerprint", "")
    service_tier = response_data.get("service_tier", "")
    completion_tokens_details = response_data.get("completion_tokens_details", {})
    prompt_tokens_details = response_data.get("prompt_tokens_details", {})
    # Claude-specific fields
    stop_sequence = response_data.get("stop_sequence", "")
    cache_creation_input_tokens = response_data.get("cache_creation_input_tokens", 0)
    cache_read_input_tokens = response_data.get("cache_read_input_tokens", 0)
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
    if output_file != "-":
        output_path = Path(output_file)
        output_path.write_text(response_text)

    from mcp_handley_lab.shared.models import UsageStats

    usage_stats = UsageStats(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model_used=model,
    )

    # Convert grounding metadata dict to GroundingMetadata object
    grounding_metadata = None
    if grounding_metadata_dict:
        grounding_metadata = GroundingMetadata(**grounding_metadata_dict)

    return LLMResult(
        content=response_text,
        usage=usage_stats,
        agent_name=actual_agent_name if use_memory else "",
        grounding_metadata=grounding_metadata,
        finish_reason=finish_reason,
        avg_logprobs=avg_logprobs,
        model_version=model_version,
        generation_time_ms=generation_time_ms,
        response_id=response_id,
        system_fingerprint=system_fingerprint,
        service_tier=service_tier,
        completion_tokens_details=completion_tokens_details,
        prompt_tokens_details=prompt_tokens_details,
        stop_sequence=stop_sequence,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
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
) -> ImageGenerationResult:
    """Generic handler for LLM image generation requests."""
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    # Call the provider-specific generation function to get the image
    response_data = generation_func(prompt=prompt, model=model, **kwargs)
    image_bytes = response_data["image_bytes"]
    input_tokens = response_data.get("input_tokens", 0)
    output_tokens = response_data.get("output_tokens", 1)

    file_id = str(uuid.uuid4())[:8]
    filename = f"{provider}_generated_{file_id}.png"
    filepath = Path(tempfile.gettempdir()) / filename
    filepath.write_bytes(image_bytes)

    cost = calculate_cost(
        model, input_tokens, output_tokens, provider, images_generated=1
    )

    handle_agent_memory(
        agent_name,
        f"Generate image: {prompt}",
        f"Generated image saved to {filepath}",
        input_tokens,
        output_tokens,
        cost,
        lambda: get_session_id(mcp_instance),
    )

    file_size = len(image_bytes)

    from mcp_handley_lab.shared.models import UsageStats

    usage_stats = UsageStats(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model_used=model,
    )

    return ImageGenerationResult(
        message="Image Generated Successfully",
        file_path=str(filepath),
        file_size_bytes=file_size,
        usage=usage_stats,
        agent_name=agent_name if agent_name else "",
    )
