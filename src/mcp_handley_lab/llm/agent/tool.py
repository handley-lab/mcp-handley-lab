"""Agent management tool for persistent conversation memory across LLM providers."""

from mcp.server.fastmcp import FastMCP
from pydantic import constr

from mcp_handley_lab.common.memory import memory_manager

mcp = FastMCP("Agent Management Tool")


@mcp.tool(
    description="Creates a new persistent conversation agent with optional personality. Agents maintain conversation history across sessions and can be used with any LLM tool by specifying the agent_name parameter."
)
def create_agent(
    agent_name: constr(min_length=1), personality: str | None = None
) -> str:
    """Create a new agent with optional personality."""
    memory_manager.create_agent(agent_name, personality)
    personality_info = f" with personality: {personality}" if personality else ""
    return f"✅ Agent '{agent_name}' created successfully{personality_info}!"


@mcp.tool(
    description="Lists all persistent agents with statistics: creation date, message count, token usage, and cost. Essential for managing agent resources and monitoring usage across projects."
)
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
        if stats["personality"]:
            result += f"- Personality: {stats['personality']}\n"
        result += "\n"

    return result


@mcp.tool(
    description="Retrieves detailed statistics and recent conversation history for a specific agent. Shows total tokens, cost, and last 5 messages for usage analysis."
)
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

    if stats["personality"]:
        result += f"- Personality: {stats['personality']}\n"

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


@mcp.tool(
    description="Clears all conversation history for an agent while preserving the agent and its personality. Useful for starting fresh conversations without recreating the agent."
)
def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history."""
    memory_manager.clear_agent_history(agent_name)
    return f"✅ Agent '{agent_name}' history cleared successfully!"


@mcp.tool(
    description="Permanently deletes an agent and all conversation data. WARNING: Irreversible action. Use clear_agent() to only reset conversation history instead."
)
def delete_agent(agent_name: constr(min_length=1)) -> str:
    """Delete an agent permanently."""
    memory_manager.delete_agent(agent_name)
    return f"✅ Agent '{agent_name}' deleted permanently!"


@mcp.tool(
    description="Retrieves a specific message from an agent's conversation history by index. Use -1 for latest message (default), 0 for first message, or positive integers for specific positions."
)
def get_response(agent_name: str, index: int = -1) -> str:
    """Get a message from an agent's conversation history by index."""
    return memory_manager.get_response(agent_name, index)


@mcp.tool(
    description="Checks the status of the Agent Tool server and displays total agent count with available functions."
)
def server_info() -> str:
    """Get server status."""
    agents = memory_manager.list_agents()

    return f"""Agent Tool Server Status
========================
Status: Connected and ready
Total Agents: {len(agents)}

Available tools:
- create_agent: Create new persistent agents
- list_agents: List all agents with statistics
- agent_stats: Get detailed agent statistics
- clear_agent: Clear agent conversation history
- delete_agent: Permanently delete an agent
- get_response: Get specific message from agent history
- server_info: Get server status"""
