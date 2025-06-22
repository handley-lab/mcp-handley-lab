"""Agent memory management for persistent LLM conversations."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class Message(BaseModel):
    """A single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    tokens: Optional[int] = None
    cost: Optional[float] = None


class AgentMemory(BaseModel):
    """Persistent memory for a named agent."""
    name: str
    personality: Optional[str] = None
    created_at: datetime
    messages: List[Message] = []
    total_tokens: int = 0
    total_cost: float = 0.0
    
    def add_message(self, role: str, content: str, tokens: int = 0, cost: float = 0.0):
        """Add a message to the agent's memory."""
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            tokens=tokens,
            cost=cost
        )
        self.messages.append(message)
        self.total_tokens += tokens
        self.total_cost += cost
    
    def clear_history(self):
        """Clear all conversation history."""
        self.messages = []
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history in format suitable for LLM APIs."""
        history = []
        if self.personality:
            history.append({"role": "system", "content": self.personality})
        
        for message in self.messages:
            history.append({
                "role": message.role,
                "content": message.content
            })
        
        return history
    
    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the agent."""
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "personality": self.personality
        }


class MemoryManager:
    """Manages agent memories with file-based persistence."""
    
    def __init__(self, storage_dir: str = "~/.mcp_framework"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(exist_ok=True)
        self.agents_file = self.storage_dir / "agents.json"
        self._agents: Dict[str, AgentMemory] = {}
        self._load_agents()
    
    def _load_agents(self):
        """Load agents from disk."""
        if self.agents_file.exists():
            try:
                with open(self.agents_file) as f:
                    agents_data = json.load(f)
                
                for name, data in agents_data.items():
                    # Convert datetime strings back to datetime objects
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                    for msg in data.get("messages", []):
                        msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])
                    
                    self._agents[name] = AgentMemory(**data)
            except (json.JSONDecodeError, KeyError, ValueError):
                # If file is corrupted, start fresh
                self._agents = {}
    
    def _save_agents(self):
        """Save agents to disk."""
        agents_data = {}
        for name, agent in self._agents.items():
            # Convert to dict and handle datetime serialization
            data = agent.model_dump()
            data["created_at"] = data["created_at"].isoformat()
            for msg in data["messages"]:
                msg["timestamp"] = msg["timestamp"].isoformat()
            agents_data[name] = data
        
        with open(self.agents_file, 'w') as f:
            json.dump(agents_data, f, indent=2)
    
    def create_agent(self, name: str, personality: Optional[str] = None) -> AgentMemory:
        """Create a new agent."""
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")
        
        agent = AgentMemory(
            name=name,
            personality=personality,
            created_at=datetime.now()
        )
        self._agents[name] = agent
        self._save_agents()
        return agent
    
    def get_agent(self, name: str) -> Optional[AgentMemory]:
        """Get an existing agent."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[AgentMemory]:
        """List all agents."""
        return list(self._agents.values())
    
    def delete_agent(self, name: str) -> bool:
        """Delete an agent."""
        if name in self._agents:
            del self._agents[name]
            self._save_agents()
            return True
        return False
    
    def add_message(self, agent_name: str, role: str, content: str, tokens: int = 0, cost: float = 0.0):
        """Add a message to an agent's memory."""
        agent = self.get_agent(agent_name)
        if agent:
            agent.add_message(role, content, tokens, cost)
            self._save_agents()
    
    def clear_agent_history(self, agent_name: str) -> bool:
        """Clear an agent's conversation history."""
        agent = self.get_agent(agent_name)
        if agent:
            agent.clear_history()
            self._save_agents()
            return True
        return False


# Global memory manager instance
memory_manager = MemoryManager()