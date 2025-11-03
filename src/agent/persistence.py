"""Thread persistence for Butler Agent.

This module provides functionality to save and load conversation threads,
enabling users to maintain conversation history across sessions.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _sanitize_conversation_name(name: str) -> str:
    """Sanitize conversation name to prevent path traversal attacks.

    Args:
        name: User-provided conversation name

    Returns:
        Sanitized name safe for filesystem use

    Raises:
        ValueError: If name is invalid or unsafe
    """
    # Trim whitespace
    name = name.strip()

    # Check length (1-64 characters)
    if not name or len(name) > 64:
        raise ValueError("Conversation name must be between 1 and 64 characters")

    # Check for valid characters: alphanumeric, underscore, dash, dot
    if not re.match(r"^[A-Za-z0-9._-]+$", name):
        raise ValueError(
            "Conversation name can only contain letters, numbers, underscores, dashes, and dots"
        )

    # Prevent path traversal attempts (regex above already excludes slashes)
    if ".." in name or name.startswith("."):
        raise ValueError("Invalid conversation name: path traversal not allowed")

    # Prevent reserved names
    reserved_names = {"index", "metadata", "con", "prn", "aux", "nul"}
    if name.lower() in reserved_names:
        raise ValueError(f"Reserved name '{name}' cannot be used")

    return name


class ThreadPersistence:
    """Manage conversation thread serialization and storage."""

    def __init__(self, storage_dir: Path | None = None):
        """Initialize persistence manager.

        Args:
            storage_dir: Directory for storing conversations
                        (default: ~/.butler/conversations)
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".butler" / "conversations"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file tracks all conversations
        self.metadata_file = self.storage_dir / "index.json"
        self._load_metadata()

        logger.debug(f"Thread persistence initialized: {self.storage_dir}")

    def _load_metadata(self) -> None:
        """Load conversation metadata index."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file) as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata, starting fresh: {e}")
                self.metadata = {"conversations": {}}
        else:
            self.metadata = {"conversations": {}}
            # Create initial metadata file
            self._save_metadata()

    def _save_metadata(self) -> None:
        """Save conversation metadata index."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            raise

    def _fallback_serialize(self, thread: Any) -> dict:
        """Fallback serialization when thread.serialize() fails.

        Manually extracts messages and converts them to JSON-serializable format.

        Args:
            thread: AgentThread to serialize

        Returns:
            Dictionary with serialized thread data
        """
        messages_data = []

        if hasattr(thread, "messages") and thread.messages:
            for msg in thread.messages:
                msg_dict = {"role": getattr(msg, "role", "unknown")}

                # Extract message content
                if hasattr(msg, "text"):
                    msg_dict["content"] = str(msg.text)
                elif hasattr(msg, "content"):
                    msg_dict["content"] = str(msg.content)
                else:
                    msg_dict["content"] = str(msg)

                # Extract tool calls if present
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "name": getattr(tc, "name", "unknown"),
                            "arguments": str(getattr(tc, "arguments", "")),
                        }
                        for tc in msg.tool_calls
                    ]

                messages_data.append(msg_dict)

        return {
            "messages": messages_data,
            "metadata": {"fallback": True, "version": "1.0"},
        }

    async def save_thread(
        self,
        thread: Any,
        name: str,
        description: str | None = None,
    ) -> Path:
        """Save a conversation thread.

        Args:
            thread: AgentThread to serialize
            name: Name for this conversation
            description: Optional description

        Returns:
            Path to saved conversation file

        Raises:
            ValueError: If name is invalid or unsafe
            Exception: If serialization or save fails
        """
        # Sanitize name for security
        safe_name = _sanitize_conversation_name(name)
        logger.info(f"Saving conversation '{safe_name}'...")

        try:
            # Extract first message for preview
            first_message = ""
            message_count = 0
            if hasattr(thread, "messages") and thread.messages:
                message_count = len(thread.messages)
                # Try to get first user message
                for msg in thread.messages:
                    if hasattr(msg, "role") and msg.role == "user":
                        if hasattr(msg, "text"):
                            first_message = str(msg.text)[:100]
                        elif hasattr(msg, "content"):
                            first_message = str(msg.content)[:100]
                        break

            # Serialize thread
            serialized = None
            try:
                # Try async serialize first
                if hasattr(thread, "serialize"):
                    import inspect

                    if inspect.iscoroutinefunction(thread.serialize):
                        serialized = await thread.serialize()
                    else:
                        # Sync serialize method
                        serialized = thread.serialize()
                else:
                    raise AttributeError("Thread has no serialize method")

                # Verify the serialized data is actually JSON-serializable
                # Try to serialize and deserialize to check
                json.dumps(serialized)

            except (AttributeError, TypeError, json.JSONDecodeError, Exception) as serialize_error:
                # Fallback: Manual serialization if framework serialize fails or returns non-JSON data
                logger.warning(
                    f"Thread serialization failed or returned non-JSON data: {serialize_error}. "
                    "Using fallback serialization."
                )
                serialized = self._fallback_serialize(thread)

            # Add metadata
            conversation_data = {
                "name": safe_name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "message_count": message_count,
                "first_message": first_message,
                "thread": serialized,
            }

            # Save to file
            file_path = self.storage_dir / f"{safe_name}.json"
            with open(file_path, "w") as f:
                json.dump(conversation_data, f, indent=2)

            # Update metadata index
            self.metadata["conversations"][safe_name] = {
                "description": description,
                "created_at": conversation_data["created_at"],
                "message_count": message_count,
                "first_message": first_message,
                "file": str(file_path),
            }
            self._save_metadata()

            logger.info(f"Conversation saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            raise

    async def load_thread(self, agent: Any, name: str) -> Any:
        """Load a conversation thread.

        Args:
            agent: Agent instance for deserialization
            name: Name of conversation to load

        Returns:
            Deserialized AgentThread

        Raises:
            ValueError: If name is invalid or unsafe
            FileNotFoundError: If conversation doesn't exist
            Exception: If deserialization fails
        """
        # Sanitize name for security
        safe_name = _sanitize_conversation_name(name)
        logger.info(f"Loading conversation '{safe_name}'...")

        file_path = self.storage_dir / f"{safe_name}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Conversation '{safe_name}' not found")

        try:
            # Load from file
            with open(file_path) as f:
                conversation_data = json.load(f)

            # Check if this was saved with fallback serialization
            thread_data = conversation_data["thread"]
            if isinstance(thread_data, dict) and thread_data.get("metadata", {}).get("fallback"):
                logger.warning(
                    f"Session '{safe_name}' was saved with fallback serialization. "
                    "Full context restoration not supported yet."
                )
                # Create a new thread instead of trying to deserialize
                # User will see the conversation was loaded but context will be fresh
                thread = agent.get_new_thread()
            else:
                # Deserialize thread using agent framework
                thread = await agent.agent.deserialize_thread(thread_data)

            logger.info(f"Conversation '{safe_name}' loaded successfully")
            return thread

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            raise

    def list_conversations(self) -> list[dict]:
        """List all saved conversations.

        Returns:
            List of conversation metadata dicts with name, description, created_at, etc.
        """
        conversations = []
        for name, meta in self.metadata["conversations"].items():
            conversations.append(
                {
                    "name": name,
                    "description": meta.get("description"),
                    "created_at": meta.get("created_at"),
                    "message_count": meta.get("message_count", 0),
                    "first_message": meta.get("first_message", ""),
                }
            )

        # Sort by creation time (newest first)
        conversations.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return conversations

    def delete_conversation(self, name: str) -> bool:
        """Delete a saved conversation.

        Args:
            name: Name of conversation to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If name is invalid or unsafe
        """
        # Sanitize name for security
        safe_name = _sanitize_conversation_name(name)
        file_path = self.storage_dir / f"{safe_name}.json"

        if file_path.exists():
            try:
                file_path.unlink()

                if safe_name in self.metadata["conversations"]:
                    del self.metadata["conversations"][safe_name]
                    self._save_metadata()

                logger.info(f"Conversation '{safe_name}' deleted")
                return True
            except Exception as e:
                logger.error(f"Failed to delete conversation: {e}")
                raise

        return False

    def conversation_exists(self, name: str) -> bool:
        """Check if a conversation exists.

        Args:
            name: Name of conversation to check

        Returns:
            True if conversation exists

        Raises:
            ValueError: If name is invalid or unsafe
        """
        # Sanitize name for security
        safe_name = _sanitize_conversation_name(name)
        file_path = self.storage_dir / f"{safe_name}.json"
        return file_path.exists()

    def get_conversation_info(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a specific conversation.

        Args:
            name: Name of conversation

        Returns:
            Conversation metadata dict or None if not found

        Raises:
            ValueError: If name is invalid or unsafe
        """
        # Sanitize name for security
        safe_name = _sanitize_conversation_name(name)
        return self.metadata["conversations"].get(safe_name)  # type: ignore[no-any-return]
