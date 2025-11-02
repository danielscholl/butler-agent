"""Thread persistence for Butler Agent.

This module provides functionality to save and load conversation threads,
enabling users to maintain conversation history across sessions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
            Exception: If serialization or save fails
        """
        logger.info(f"Saving conversation '{name}'...")

        try:
            # Serialize thread
            serialized = await thread.serialize()

            # Add metadata
            conversation_data = {
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "thread": serialized,
            }

            # Save to file
            file_path = self.storage_dir / f"{name}.json"
            with open(file_path, "w") as f:
                json.dump(conversation_data, f, indent=2)

            # Update metadata index
            self.metadata["conversations"][name] = {
                "description": description,
                "created_at": conversation_data["created_at"],
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
            FileNotFoundError: If conversation doesn't exist
            Exception: If deserialization fails
        """
        logger.info(f"Loading conversation '{name}'...")

        file_path = self.storage_dir / f"{name}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Conversation '{name}' not found")

        try:
            # Load from file
            with open(file_path) as f:
                conversation_data = json.load(f)

            # Deserialize thread using agent
            thread = await agent.agent.deserialize_thread(conversation_data["thread"])

            logger.info(f"Conversation '{name}' loaded successfully")
            return thread

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            raise

    def list_conversations(self) -> list[dict]:
        """List all saved conversations.

        Returns:
            List of conversation metadata dicts with name, description, created_at
        """
        conversations = []
        for name, meta in self.metadata["conversations"].items():
            conversations.append(
                {
                    "name": name,
                    "description": meta.get("description"),
                    "created_at": meta.get("created_at"),
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
        """
        file_path = self.storage_dir / f"{name}.json"

        if file_path.exists():
            try:
                file_path.unlink()

                if name in self.metadata["conversations"]:
                    del self.metadata["conversations"][name]
                    self._save_metadata()

                logger.info(f"Conversation '{name}' deleted")
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
        """
        file_path = self.storage_dir / f"{name}.json"
        return file_path.exists()

    def get_conversation_info(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a specific conversation.

        Args:
            name: Name of conversation

        Returns:
            Conversation metadata dict or None if not found
        """
        return self.metadata["conversations"].get(name)  # type: ignore[no-any-return]
