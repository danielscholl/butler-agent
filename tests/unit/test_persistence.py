"""Unit tests for thread persistence."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.persistence import ThreadPersistence, _sanitize_conversation_name


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary storage directory."""
    storage = tmp_path / "conversations"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def persistence(temp_storage_dir):
    """Create ThreadPersistence instance with temp directory."""
    return ThreadPersistence(storage_dir=temp_storage_dir)


@pytest.fixture
def mock_thread():
    """Create a mock AgentThread."""
    thread = AsyncMock()
    thread.serialize = AsyncMock(return_value={"messages": [], "metadata": {"test": "data"}})
    return thread


@pytest.fixture
def mock_agent():
    """Create a mock Agent."""
    agent = MagicMock()
    agent.agent = MagicMock()

    # Create a new mock thread for deserialization
    mock_deserialized_thread = AsyncMock()
    mock_deserialized_thread.messages = []

    agent.agent.deserialize_thread = AsyncMock(return_value=mock_deserialized_thread)
    return agent


class TestThreadPersistence:
    """Test suite for ThreadPersistence."""

    def test_init(self, temp_storage_dir):
        """Test initialization creates storage directory."""
        persistence = ThreadPersistence(storage_dir=temp_storage_dir)

        assert persistence.storage_dir == temp_storage_dir
        assert persistence.storage_dir.exists()
        assert persistence.metadata_file.exists()

    def test_init_default_directory(self):
        """Test initialization with default directory."""
        persistence = ThreadPersistence()

        expected_dir = Path.home() / ".butler" / "conversations"
        assert persistence.storage_dir == expected_dir

    @pytest.mark.asyncio
    async def test_save_thread(self, persistence, mock_thread):
        """Test saving a thread."""
        name = "test-conversation"
        description = "Test conversation description"

        file_path = await persistence.save_thread(mock_thread, name, description=description)

        # Verify file was created
        assert file_path.exists()
        assert file_path.name == f"{name}.json"

        # Verify file contents
        with open(file_path) as f:
            data = json.load(f)

        assert data["name"] == name
        assert data["description"] == description
        assert "created_at" in data
        assert "thread" in data

        # Verify metadata was updated
        assert name in persistence.metadata["conversations"]
        assert persistence.metadata["conversations"][name]["description"] == description

    @pytest.mark.asyncio
    async def test_load_thread(self, persistence, mock_agent, mock_thread):
        """Test loading a thread."""
        name = "test-load"

        # First save a thread
        await persistence.save_thread(mock_thread, name)

        # Then load it
        loaded_thread = await persistence.load_thread(mock_agent, name)

        # Verify deserialization was called
        mock_agent.agent.deserialize_thread.assert_called_once()
        assert loaded_thread is not None

    @pytest.mark.asyncio
    async def test_load_nonexistent_thread(self, persistence, mock_agent):
        """Test loading a nonexistent thread raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            await persistence.load_thread(mock_agent, "nonexistent")

    def test_list_conversations_empty(self, persistence):
        """Test listing conversations when none exist."""
        conversations = persistence.list_conversations()

        assert conversations == []

    @pytest.mark.asyncio
    async def test_list_conversations(self, persistence, mock_thread):
        """Test listing multiple conversations."""
        # Save multiple conversations
        await persistence.save_thread(mock_thread, "conv1", "First conversation")
        await persistence.save_thread(mock_thread, "conv2", "Second conversation")
        await persistence.save_thread(mock_thread, "conv3")

        conversations = persistence.list_conversations()

        assert len(conversations) == 3

        # Verify all conversations are present
        names = [c["name"] for c in conversations]
        assert "conv1" in names
        assert "conv2" in names
        assert "conv3" in names

        # Verify descriptions
        conv1 = next(c for c in conversations if c["name"] == "conv1")
        assert conv1["description"] == "First conversation"

    @pytest.mark.asyncio
    async def test_list_conversations_sorted_by_date(self, persistence, mock_thread):
        """Test conversations are sorted by creation date (newest first)."""
        # Save conversations in order
        await persistence.save_thread(mock_thread, "oldest")
        await persistence.save_thread(mock_thread, "middle")
        await persistence.save_thread(mock_thread, "newest")

        conversations = persistence.list_conversations()

        # Should be sorted newest first
        assert conversations[0]["name"] == "newest"
        assert conversations[2]["name"] == "oldest"

    @pytest.mark.asyncio
    async def test_delete_conversation(self, persistence, mock_thread):
        """Test deleting a conversation."""
        name = "test-delete"

        # Save a conversation
        await persistence.save_thread(mock_thread, name)

        # Verify it exists
        assert persistence.conversation_exists(name)

        # Delete it
        result = persistence.delete_conversation(name)

        assert result is True
        assert not persistence.conversation_exists(name)
        assert name not in persistence.metadata["conversations"]

    def test_delete_nonexistent_conversation(self, persistence):
        """Test deleting a nonexistent conversation."""
        result = persistence.delete_conversation("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_conversation_exists(self, persistence, mock_thread):
        """Test checking if conversation exists."""
        name = "test-exists"

        assert not persistence.conversation_exists(name)

        await persistence.save_thread(mock_thread, name)

        assert persistence.conversation_exists(name)

    @pytest.mark.asyncio
    async def test_get_conversation_info(self, persistence, mock_thread):
        """Test getting conversation metadata."""
        name = "test-info"
        description = "Test description"

        # Before saving
        info = persistence.get_conversation_info(name)
        assert info is None

        # After saving
        await persistence.save_thread(mock_thread, name, description=description)

        info = persistence.get_conversation_info(name)
        assert info is not None
        assert info["description"] == description
        assert "created_at" in info

    @pytest.mark.asyncio
    async def test_save_thread_overwrites_existing(self, persistence, mock_thread):
        """Test saving a thread with same name overwrites existing."""
        name = "test-overwrite"

        # Save first version
        await persistence.save_thread(mock_thread, name, description="First")

        # Save second version with same name
        await persistence.save_thread(mock_thread, name, description="Second")

        # Should only have one conversation
        conversations = persistence.list_conversations()
        assert len(conversations) == 1
        assert conversations[0]["description"] == "Second"

    @pytest.mark.asyncio
    async def test_metadata_persistence(self, temp_storage_dir, mock_thread):
        """Test metadata persists across instances."""
        # Create first instance and save conversation
        persistence1 = ThreadPersistence(storage_dir=temp_storage_dir)
        await persistence1.save_thread(mock_thread, "test", "Test conversation")

        # Create second instance and verify conversation is loaded
        persistence2 = ThreadPersistence(storage_dir=temp_storage_dir)
        conversations = persistence2.list_conversations()

        assert len(conversations) == 1
        assert conversations[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_save_thread_serialization_error(self, persistence):
        """Test saving thread handles serialization errors with fallback."""
        # Create thread that fails serialization
        bad_thread = AsyncMock()
        bad_thread.serialize = AsyncMock(side_effect=Exception("Serialization failed"))
        bad_thread.messages = []  # Empty messages for fallback

        # Should NOT raise - should use fallback serialization
        file_path = await persistence.save_thread(bad_thread, "test")

        # Verify file was created with fallback
        assert file_path.exists()
        with open(file_path) as f:
            data = json.load(f)
            # Check fallback metadata
            assert data["thread"]["metadata"]["fallback"] is True

    @pytest.mark.asyncio
    async def test_load_thread_deserialization_error(self, persistence, mock_thread, mock_agent):
        """Test loading thread handles deserialization errors."""
        # Save a valid thread
        name = "test-bad-load"
        await persistence.save_thread(mock_thread, name)

        # Make deserialization fail
        mock_agent.agent.deserialize_thread = AsyncMock(
            side_effect=Exception("Deserialization failed")
        )

        with pytest.raises(Exception, match="Deserialization failed"):
            await persistence.load_thread(mock_agent, name)


class TestConversationNameSanitization:
    """Test suite for conversation name sanitization (security)."""

    def test_sanitize_valid_names(self):
        """Test valid conversation names pass sanitization."""
        valid_names = [
            "my-conversation",
            "test_conv_123",
            "project-v1.2",
            "backup.old",
            "Test123",
            "a",  # Minimum length
            "a" * 64,  # Maximum length
        ]

        for name in valid_names:
            result = _sanitize_conversation_name(name)
            assert result == name.strip()

    def test_sanitize_whitespace_trimming(self):
        """Test whitespace is trimmed from names."""
        assert _sanitize_conversation_name("  test  ") == "test"
        assert _sanitize_conversation_name("\ttest\n") == "test"

    def test_sanitize_rejects_empty_name(self):
        """Test empty names are rejected."""
        with pytest.raises(ValueError, match="between 1 and 64 characters"):
            _sanitize_conversation_name("")

        with pytest.raises(ValueError, match="between 1 and 64 characters"):
            _sanitize_conversation_name("   ")

    def test_sanitize_rejects_too_long(self):
        """Test names over 64 characters are rejected."""
        long_name = "a" * 65
        with pytest.raises(ValueError, match="between 1 and 64 characters"):
            _sanitize_conversation_name(long_name)

    def test_sanitize_rejects_invalid_characters(self):
        """Test names with invalid characters are rejected."""
        invalid_names = [
            "test conversation",  # Space
            "test@conv",  # @
            "test#conv",  # #
            "test$conv",  # $
            "test%conv",  # %
            "test&conv",  # &
            "test*conv",  # *
            "test(conv",  # (
            "test)conv",  # )
            "test=conv",  # =
            "test+conv",  # +
            "test[conv",  # [
            "test]conv",  # ]
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="can only contain"):
                _sanitize_conversation_name(name)

    def test_sanitize_rejects_path_traversal(self):
        """Test path traversal attempts are rejected (security)."""
        malicious_names = [
            "../etc/passwd",
            "..\\windows\\system32",
            "..",
            "test/../other",
            "../../root",
            ".hidden",
            ".env",
        ]

        for name in malicious_names:
            # These names should be rejected (various error messages possible)
            with pytest.raises(ValueError):
                _sanitize_conversation_name(name)

    def test_sanitize_rejects_path_separators(self):
        """Test path separators are rejected (security)."""
        with pytest.raises(ValueError, match="can only contain"):
            _sanitize_conversation_name("test/conversation")

        with pytest.raises(ValueError, match="can only contain"):
            _sanitize_conversation_name("test\\conversation")

    def test_sanitize_rejects_reserved_names(self):
        """Test reserved filesystem names are rejected."""
        reserved_names = ["index", "metadata", "con", "prn", "aux", "nul", "INDEX", "CON"]

        for name in reserved_names:
            with pytest.raises(ValueError, match="Reserved name"):
                _sanitize_conversation_name(name)

    @pytest.mark.asyncio
    async def test_save_with_malicious_name_rejected(self, persistence, mock_thread):
        """Test saving thread with malicious name is rejected."""
        malicious_names = [
            "../malicious",
            "../../etc/passwd",
            ".hidden",
            "test/path",
            "con",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError):
                await persistence.save_thread(mock_thread, name)

    @pytest.mark.asyncio
    async def test_load_with_malicious_name_rejected(self, persistence, mock_agent):
        """Test loading thread with malicious name is rejected."""
        malicious_names = [
            "../malicious",
            "../../etc/passwd",
            ".hidden",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError):
                await persistence.load_thread(mock_agent, name)

    def test_delete_with_malicious_name_rejected(self, persistence):
        """Test deleting conversation with malicious name is rejected."""
        with pytest.raises(ValueError):
            persistence.delete_conversation("../malicious")

    def test_exists_with_malicious_name_rejected(self, persistence):
        """Test checking existence with malicious name is rejected."""
        with pytest.raises(ValueError):
            persistence.conversation_exists("../malicious")
