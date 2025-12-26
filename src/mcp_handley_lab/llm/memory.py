"""Agent memory management for persistent LLM conversations.

Stores conversation history in global ~/.mcp-handley-lab/projects/<encoded-path>/agents/
with JSONL format for append-only durability.
"""

import contextlib
import fcntl
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Valid agent name pattern: alphanumeric, underscores, hyphens, dots
VALID_AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def encode_project_path(path: Path) -> str:
    """Encode a project path to a directory-safe name.

    Follows Claude Code's convention: /home/will/project -> -home-will-project
    Uses Path.resolve() for canonicalization (handles symlinks, ., ..).
    Uses as_posix() for cross-platform consistency.
    """
    resolved = path.resolve()
    # Use as_posix() for consistent separators, then replace / with -
    # Also handle Windows drive letters (C: -> C)
    posix_path = resolved.as_posix()
    return posix_path.replace(":", "").replace("/", "-")


def get_global_storage_dir() -> Path:
    """Get the global storage directory for LLM memory."""
    base = Path(os.environ.get("MCP_HANDLEY_LAB_MEMORY_DIR", "~/.mcp-handley-lab"))
    return base.expanduser()


def get_project_dir(cwd: Path | None = None) -> Path:
    """Get the project-specific storage directory."""
    if cwd is None:
        cwd = Path.cwd()
    encoded = encode_project_path(cwd)
    return get_global_storage_dir() / "projects" / encoded


class MessageEvent(BaseModel):
    """A single message event in a conversation."""

    v: int = Field(default=1, description="Schema version")
    type: str = Field(default="message", description="Event type")
    timestamp: str = Field(..., description="ISO timestamp")
    uuid: str = Field(..., description="Unique message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    cwd: str | None = Field(default=None, description="Working directory context")
    usage: dict[str, Any] | None = Field(
        default=None, description="Token/cost usage with provider attribution"
    )


class SystemPromptEvent(BaseModel):
    """Event for system prompt changes."""

    v: int = Field(default=1, description="Schema version")
    type: str = Field(default="system_prompt_set", description="Event type")
    timestamp: str = Field(..., description="ISO timestamp")
    content: str = Field(..., description="System prompt content")


class AgentClearedEvent(BaseModel):
    """Event for when agent history is cleared."""

    v: int = Field(default=1, description="Schema version")
    type: str = Field(default="agent_cleared", description="Event type")
    timestamp: str = Field(..., description="ISO timestamp")


class ProjectMetadata(BaseModel):
    """Metadata for a project directory."""

    original_path: str = Field(..., description="Original project path")
    created_at: str = Field(..., description="When project was first used")
    last_used_at: str = Field(..., description="Last access time")
    schema_version: int = Field(default=1, description="Metadata schema version")


def validate_agent_name(name: str) -> None:
    """Validate agent name to prevent path traversal and invalid filenames.

    Raises:
        ValueError: If the agent name is invalid.
    """
    if not name:
        raise ValueError("Agent name cannot be empty")
    if not VALID_AGENT_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid agent name '{name}'. "
            "Agent names must contain only letters, numbers, underscores, hyphens, and dots."
        )
    # Prevent names that could be problematic on any filesystem
    if name in (".", "..") or name.startswith("."):
        raise ValueError(f"Invalid agent name '{name}'. Names cannot start with a dot.")


class AgentMemory:
    """Persistent memory for a named agent using JSONL storage."""

    def __init__(self, name: str, agents_dir: Path, cwd: Path | None = None):
        validate_agent_name(name)
        self.name = name
        self.agents_dir = agents_dir
        self.cwd = cwd or Path.cwd()
        self._file_path = agents_dir / f"{name}.jsonl"
        self._system_prompt: str | None = None
        self._messages: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load agent state from JSONL file.

        Uses classic append-only crash recovery: stop at first JSON decode error.
        This handles the common case of a partial/corrupted trailing line from a crash.
        """
        events: list[dict[str, Any]] = []

        try:
            with open(self._file_path, encoding="utf-8") as f:
                self._load_from_file(f, events)
        except FileNotFoundError:
            return

        self._process_events(events)

    def _load_from_file(self, f, events: list) -> int:
        """Load events from file, returns index of last clear event."""
        last_clear_idx = -1
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
                if event.get("type") == "agent_cleared":
                    last_clear_idx = len(events) - 1
            except json.JSONDecodeError as e:
                logger.warning(
                    "JSONL truncation at line %s in %s: %s. History truncated (crash recovery).",
                    line_num,
                    self._file_path,
                    e,
                )
                break
        return last_clear_idx

    def _process_events(self, events: list):
        """Process loaded events to reconstruct state."""
        # Find last clear boundary
        last_clear_idx = -1
        for i, event in enumerate(events):
            if event.get("type") == "agent_cleared":
                last_clear_idx = i

        for i, event in enumerate(events):
            if i <= last_clear_idx:
                continue

            event_type = event.get("type")
            if event_type == "message":
                self._messages.append(event)
            elif event_type == "system_prompt_set":
                self._system_prompt = event.get("content")

    def _append_event(self, event: dict[str, Any]):
        """Append an event to the JSONL file with crash resistance and locking."""
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "a", encoding="utf-8") as f:
            # Acquire exclusive lock for append operation
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(event) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    @property
    def system_prompt(self) -> str | None:
        """Get the current system prompt."""
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str | None):
        """Set the system prompt and persist it."""
        if value != self._system_prompt:
            self._system_prompt = value
            if value is not None:
                event = SystemPromptEvent(
                    timestamp=datetime.now().isoformat(),
                    content=value,
                )
                self._append_event(event.model_dump())

    def add_message(
        self,
        role: str,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        provider: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a message to the agent's memory.

        Args:
            role: Message role (user/assistant)
            content: Message content
            input_tokens: Number of input/prompt tokens (deprecated, use metadata)
            output_tokens: Number of output/completion tokens (deprecated, use metadata)
            cost: Cost in USD (deprecated, use metadata)
            provider: Provider name (e.g., "openai", "gemini")
            model: Model name (e.g., "gpt-4o", "gemini-2.5-pro")
            metadata: Full response metadata (tokens, cost, timing, etc.)
        """
        usage = None

        # Prefer metadata dict, fall back to individual args for backward compat
        if metadata:
            # Filter out response_text - it's already stored in content
            filtered_metadata = {
                k: v for k, v in metadata.items() if k != "response_text"
            }
            usage = {
                "provider": provider,
                "model": model,
                **filtered_metadata,
            }
        elif input_tokens > 0 or output_tokens > 0 or cost > 0 or provider or model:
            usage = {
                "provider": provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
            }

        event = MessageEvent(
            timestamp=datetime.now().isoformat(),
            uuid=str(uuid.uuid4()),
            role=role,
            content=content,
            cwd=str(self.cwd),
            usage=usage,
        )
        event_dict = event.model_dump()
        self._messages.append(event_dict)
        self._append_event(event_dict)

    def clear_history(self):
        """Clear all conversation history."""
        self._messages = []
        event = AgentClearedEvent(timestamp=datetime.now().isoformat())
        self._append_event(event.model_dump())

    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history in provider-agnostic format."""
        return [
            {"role": msg["role"], "content": msg["content"]} for msg in self._messages
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics for the agent."""
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        for msg in self._messages:
            usage = msg.get("usage")
            if usage:
                # Support both new schema (input_tokens/output_tokens) and legacy (tokens)
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)
                # Legacy fallback: add legacy "tokens" to output_tokens if present
                if "tokens" in usage and "input_tokens" not in usage:
                    total_output_tokens += usage.get("tokens", 0)
                total_cost += usage.get("cost", 0.0)

        # Derive created_at from first message timestamp or file mtime
        created_at = None
        if self._messages:
            created_at = self._messages[0].get("timestamp")
        else:
            try:
                mtime = self._file_path.stat().st_mtime
                created_at = datetime.fromtimestamp(mtime).isoformat()
            except FileNotFoundError:
                created_at = datetime.now().isoformat()

        return {
            "name": self.name,
            "created_at": created_at,
            "message_count": len(self._messages),
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost": total_cost,
            "system_prompt": self._system_prompt,
        }

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Get all messages (for backward compatibility)."""
        return self._messages

    def get_response(self, index: int = -1) -> dict[str, Any]:
        """Get an assistant response by index. Raises IndexError if not found.

        Only considers assistant messages. Index 0 is the first response,
        -1 is the last, -2 is second-to-last, etc.

        Returns a dict matching the LLMResult structure that ask() returns:
        - content: The response text
        - usage: Token/cost info (input_tokens, output_tokens, cost, model_used)
        - Plus any additional metadata from the original response
        """
        responses = [msg for msg in self._messages if msg["role"] == "assistant"]
        if not responses:
            raise IndexError("Cannot get response: agent has no assistant responses")

        msg = responses[index]
        stored_usage = msg.get("usage") or {}

        # Build result in LLMResult format
        result: dict[str, Any] = {"content": msg["content"]}

        # Build usage dict matching UsageStats structure
        usage = {
            "input_tokens": stored_usage.get("input_tokens", 0),
            "output_tokens": stored_usage.get("output_tokens", 0),
            "cost": stored_usage.get("cost", 0.0),
            "model_used": stored_usage.get("model", ""),
        }
        result["usage"] = usage

        # Add other LLMResult fields if present in stored metadata
        llm_result_fields = [
            "finish_reason",
            "avg_logprobs",
            "model_version",
            "generation_time_ms",
            "response_id",
            "system_fingerprint",
            "service_tier",
            "completion_tokens_details",
            "prompt_tokens_details",
            "stop_sequence",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "grounding_metadata",
        ]
        for field in llm_result_fields:
            if field in stored_usage:
                result[field] = stored_usage[field]

        # Add agent_name from stored message if present
        result["agent_name"] = self.name

        return result

    def get_conversation_summary(self, max_response_chars: int = 200) -> dict[str, Any]:
        """Get conversation data for LLM review with truncated assistant responses.

        Returns a dict with agent stats, system prompt, and messages.
        Assistant responses are truncated to max_response_chars with metadata.
        The `response_index` field on assistant messages is the index to pass
        to get_response() (-1 for the last response).

        Output is minimal - only includes fields that have meaningful values.
        """
        messages = []
        assistant_count = 0
        total_assistants = sum(1 for m in self._messages if m["role"] == "assistant")

        for msg in self._messages:
            content = msg["content"]
            full_length = len(content)

            entry: dict[str, Any] = {"role": msg["role"]}

            if msg.get("timestamp"):
                entry["timestamp"] = msg["timestamp"]

            if msg["role"] == "assistant":
                # Track the response index for get_response() calls
                # Use negative indexing (-1 = last, -2 = second-to-last)
                entry["response_index"] = assistant_count - total_assistants
                assistant_count += 1

                if len(content) > max_response_chars:
                    content = content[:max_response_chars] + "..."
                    entry["truncated"] = True
                    entry["full_length"] = full_length

            entry["content"] = content
            messages.append(entry)

        # Build minimal stats (exclude redundant name, null system_prompt)
        stats = self.get_stats()
        summary_stats = {
            "messages": stats["message_count"],
            "tokens": stats["total_tokens"],
            "cost": stats["total_cost"],
        }

        result: dict[str, Any] = {
            "name": self.name,
            "stats": summary_stats,
            "messages": messages,
        }
        if self._system_prompt:
            result["system_prompt"] = self._system_prompt

        return result


class GlobalMemoryManager:
    """Manages agent memories with global JSONL-based persistence."""

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()
        self._project_dir = get_project_dir(self.cwd)
        self._agents_dir = self._project_dir / "agents"
        self._agents: dict[str, AgentMemory] = {}
        self._ensure_project_metadata()

    def _ensure_project_metadata(self):
        """Ensure project.json exists with metadata, using atomic writes."""
        self._project_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = self._project_dir / "project.json"

        now = datetime.now().isoformat()

        # Read existing metadata if present (first run = no file)
        data = None
        try:
            with open(metadata_file, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            pass  # First run - expected

        # Build metadata
        if data:
            data["last_used_at"] = now
        else:
            data = ProjectMetadata(
                original_path=str(self.cwd.resolve()),
                created_at=now,
                last_used_at=now,
            ).model_dump()

        # Atomic write: tmp file + os.replace
        tmp_file = metadata_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, metadata_file)

    def create_agent(self, name: str, system_prompt: str | None = None) -> AgentMemory:
        """Create a new agent or get existing one."""
        validate_agent_name(name)
        if name in self._agents:
            agent = self._agents[name]
            if system_prompt is not None:
                agent.system_prompt = system_prompt
            return agent

        agent = AgentMemory(name, self._agents_dir, self.cwd)
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        self._agents[name] = agent
        return agent

    def get_agent(self, name: str) -> AgentMemory | None:
        """Get an existing agent."""
        validate_agent_name(name)
        if name not in self._agents:
            agent_file = self._agents_dir / f"{name}.jsonl"
            try:
                agent_file.stat()  # Check if file exists
                agent = AgentMemory(name, self._agents_dir, self.cwd)
                self._agents[name] = agent
                return agent
            except FileNotFoundError:
                return None
        return self._agents[name]

    def list_agents(self) -> list[AgentMemory]:
        """List all agents for this project (both in-memory and on disk)."""
        # Load agents from disk that aren't already in memory
        try:
            agent_files = list(self._agents_dir.glob("*.jsonl"))
        except FileNotFoundError:
            agent_files = []

        for agent_file in agent_files:
            name = agent_file.stem
            if name not in self._agents:
                try:
                    validate_agent_name(name)
                    self._agents[name] = AgentMemory(name, self._agents_dir, self.cwd)
                except ValueError as e:
                    # Log skipped invalid agent files for visibility
                    logger.debug(
                        "Skipping invalid agent file '%s': %s", agent_file.name, e
                    )

        return list(self._agents.values())

    def delete_agent(self, name: str) -> None:
        """Delete an agent."""
        validate_agent_name(name)
        if name in self._agents:
            del self._agents[name]
        agent_file = self._agents_dir / f"{name}.jsonl"
        with contextlib.suppress(FileNotFoundError):
            agent_file.unlink()

    def add_message(
        self,
        agent_name: str,
        role: str,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        provider: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a message to an agent's memory.

        Creates the agent if it doesn't exist.
        """
        agent = self.get_agent(agent_name)
        if not agent:
            # Auto-create agent if it doesn't exist
            agent = self.create_agent(agent_name)
        agent.add_message(
            role,
            content,
            input_tokens,
            output_tokens,
            cost,
            provider,
            model,
            metadata,
        )

    def clear_agent_history(self, agent_name: str) -> None:
        """Clear an agent's conversation history."""
        agent = self.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found")
        agent.clear_history()

    def get_response(self, agent_name: str, index: int = -1) -> dict[str, Any]:
        """Get a full message from an agent by index, including usage metadata."""
        agent = self.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found")
        return agent.get_response(index)


# Global memory manager instance - initialized lazily per project
_memory_manager: GlobalMemoryManager | None = None


def get_memory_manager(cwd: Path | None = None) -> GlobalMemoryManager:
    """Get or create the global memory manager for the current project."""
    global _memory_manager
    target_cwd = (cwd or Path.cwd()).resolve()

    if _memory_manager is None or _memory_manager.cwd.resolve() != target_cwd:
        _memory_manager = GlobalMemoryManager(target_cwd)

    return _memory_manager


# Backward compatibility: module-level memory_manager
# Uses lazy initialization to avoid issues during import
class _LazyMemoryManager:
    """Lazy proxy for memory_manager for backward compatibility."""

    def __getattr__(self, name: str):
        return getattr(get_memory_manager(), name)


memory_manager = _LazyMemoryManager()
