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
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history in format suitable for Gemini API."""
        history = []
        
        # For Gemini, personality/system messages should be added differently
        # We'll handle this in the tool itself rather than here
        
        for message in self.messages:
            # Convert to Gemini's expected format with 'parts'
            # Map "assistant" role to "model" for Gemini
            role = "model" if message.role == "assistant" else message.role
            history.append({
                "role": role,
                "parts": [{"text": message.content}]
            })
        
        return history
    
    def get_openai_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history in format suitable for OpenAI API."""
        history = []
        
        for message in self.messages:
            # OpenAI format: simple role/content structure
            history.append({
                "role": message.role,  # Keep original role (user/assistant)
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
    
    def get_response(self, index: int = -1) -> Optional[str]:
        """Get a message content by index. Default -1 gets the last message."""
        if not self.messages:
            return None
        
        try:
            return self.messages[index].content
        except IndexError:
            return None


class MemoryManager:
    """Manages agent memories with file-based persistence."""
    
    def __init__(self, storage_dir: str = ".mcp_handley_lab"):
        self.storage_dir = Path(storage_dir)
        self.agents_dir = self.storage_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, AgentMemory] = {}
        self._load_agents()
    
    def _get_agent_file(self, name: str) -> Path:
        """Get the file path for an agent."""
        return self.agents_dir / f"{name}.json"
    
    def _load_agents(self):
        """Load agents from disk."""
        if not self.agents_dir.exists():
            return
            
        for agent_file in self.agents_dir.glob("*.json"):
            try:
                with open(agent_file) as f:
                    data = json.load(f)
                
                # Convert datetime strings back to datetime objects
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                for msg in data.get("messages", []):
                    msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])
                
                agent = AgentMemory(**data)
                self._agents[agent.name] = agent
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted files
                continue
    
    def _save_agent(self, agent: AgentMemory):
        """Save a single agent to disk."""
        data = agent.model_dump()
        data["created_at"] = data["created_at"].isoformat()
        for msg in data["messages"]:
            msg["timestamp"] = msg["timestamp"].isoformat()
        
        agent_file = self._get_agent_file(agent.name)
        with open(agent_file, 'w') as f:
            json.dump(data, f, indent=2)
    
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
        self._save_agent(agent)
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
            agent_file = self._get_agent_file(name)
            if agent_file.exists():
                agent_file.unlink()
            return True
        return False
    
    def add_message(self, agent_name: str, role: str, content: str, tokens: int = 0, cost: float = 0.0):
        """Add a message to an agent's memory."""
        agent = self.get_agent(agent_name)
        if agent:
            agent.add_message(role, content, tokens, cost)
            self._save_agent(agent)
    
    def clear_agent_history(self, agent_name: str) -> bool:
        """Clear an agent's conversation history."""
        agent = self.get_agent(agent_name)
        if agent:
            agent.clear_history()
            self._save_agent(agent)
            return True
        return False
    
    def export_agent(self, name: str, export_path: str) -> bool:
        """Export an agent to a specified file path."""
        agent = self.get_agent(name)
        if not agent:
            return False
        
        try:
            data = agent.model_dump()
            data["created_at"] = data["created_at"].isoformat()
            for msg in data["messages"]:
                msg["timestamp"] = msg["timestamp"].isoformat()
            
            with open(export_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
    
    def import_agent(self, import_path: str, overwrite: bool = False) -> bool:
        """Import an agent from a specified file path."""
        try:
            with open(import_path) as f:
                data = json.load(f)
            
            # Convert datetime strings back to datetime objects
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            for msg in data.get("messages", []):
                msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])
            
            agent = AgentMemory(**data)
            
            # Check if agent already exists
            if agent.name in self._agents and not overwrite:
                return False
            
            self._agents[agent.name] = agent
            self._save_agent(agent)
            return True
        except Exception:
            return False
    
    def get_response(self, agent_name: str, index: int = -1) -> Optional[str]:
        """Get a message content from an agent by index. Default -1 gets the last message."""
        agent = self.get_agent(agent_name)
        if not agent:
            return None
        
        return agent.get_response(index)


# Global memory manager instance
memory_manager = MemoryManager()