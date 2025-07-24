"""Shared utility functions for agent management - not exposed as MCP tools."""

from mcp_handley_lab.llm.memory import memory_manager


def create_agent(agent_name: str, system_prompt: str = "") -> str:
    """Create a new agent with optional system prompt."""
    memory_manager.create_agent(agent_name, system_prompt)
    system_prompt_info = (
        f" with system prompt: {system_prompt}" if system_prompt else ""
    )
    return f"✅ Agent '{agent_name}' created successfully{system_prompt_info}!"


def list_agents() -> str:
    """List all agents with their statistics."""
    agents = memory_manager.list_agents()

    if not agents:
        return "No agents found. Create an agent with create_agent()."

    result = "📋 **Agent List**\n\n"
    for agent in agents:
        stats = agent.get_stats()
        result += f"**{stats['name']}**\n"
        result += f"- Created: {stats['created_at'][:10]}\n"
        result += f"- Messages: {stats['message_count']}\n"
        result += f"- Tokens: {stats['total_tokens']:,}\n"
        result += f"- Cost: ${stats['total_cost']:.4f}\n"
        if stats["system_prompt"]:
            result += f"- System Prompt: {stats['system_prompt']}\n"
        result += "\n"

    return result


def agent_stats(agent_name: str) -> str:
    """Get detailed statistics for a specific agent."""
    agent = memory_manager.get_agent(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found")

    stats = agent.get_stats()

    result = f"📊 **Agent Statistics: {agent_name}**\n\n"
    result += "**Overview:**\n"
    result += f"- Created: {stats['created_at']}\n"
    result += f"- Total Messages: {stats['message_count']}\n"
    result += f"- Total Tokens: {stats['total_tokens']:,}\n"
    result += f"- Total Cost: ${stats['total_cost']:.4f}\n"

    if stats["system_prompt"]:
        result += f"- System Prompt: {stats['system_prompt']}\n"

    # Recent message history (last 5)
    if agent.messages:
        result += "\n**Recent Messages:**\n"
        recent_messages = agent.messages[-5:]
        for i, msg in enumerate(recent_messages, 1):
            role = msg.role
            content = msg.content

            # Truncate long messages
            if len(content) > 100:
                content = content[:97] + "..."

            result += f"{i}. **{role.title()}:** {content}\n"

    return result


def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history."""
    memory_manager.clear_agent_history(agent_name)
    return f"✅ Agent '{agent_name}' history cleared successfully!"


def delete_agent(agent_name: str) -> str:
    """Delete an agent permanently."""
    memory_manager.delete_agent(agent_name)
    return f"✅ Agent '{agent_name}' deleted permanently!"


def get_response(agent_name: str, index: int = -1) -> str:
    """Get a message from an agent's conversation history by index."""
    return memory_manager.get_response(agent_name, index)
