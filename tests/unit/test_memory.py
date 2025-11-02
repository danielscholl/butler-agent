"""Unit tests for memory context providers."""

from unittest.mock import MagicMock

import pytest
from agent_framework import ChatMessage

from agent.memory import (
    ClusterMemory,
    ClusterPreferences,
    ConversationMetrics,
    ConversationMetricsMemory,
)


@pytest.fixture
def mock_chat_message():
    """Create a mock chat message."""

    def _create_message(text: str, role: str = "user"):
        msg = MagicMock(spec=ChatMessage)
        msg.text = text
        msg.role = role
        return msg

    return _create_message


class TestClusterMemory:
    """Test suite for ClusterMemory context provider."""

    def test_init(self):
        """Test initialization."""
        memory = ClusterMemory()

        assert memory.preferences is not None
        assert isinstance(memory.preferences, ClusterPreferences)
        assert memory.preferences.default_config is None
        assert memory.preferences.recent_cluster_names == []

    @pytest.mark.asyncio
    async def test_invoking_empty_preferences(self, mock_chat_message):
        """Test invoking with no preferences returns empty context."""
        memory = ClusterMemory()
        message = mock_chat_message("create a cluster")

        context = await memory.invoking(message)

        assert context is not None
        # Should return empty context when no preferences
        assert context.instructions is None or context.instructions == ""

    @pytest.mark.asyncio
    async def test_invoking_with_preferences(self, mock_chat_message):
        """Test invoking with preferences provides context."""
        memory = ClusterMemory()
        memory.preferences.default_config = "minimal"
        memory.preferences.default_k8s_version = "v1.34.0"
        memory.preferences.recent_cluster_names = ["dev-env", "test-cluster"]

        message = mock_chat_message("create a cluster")

        context = await memory.invoking(message)

        assert context is not None
        assert context.instructions is not None
        assert "minimal" in context.instructions
        assert "v1.34.0" in context.instructions
        assert "dev-env" in context.instructions

    @pytest.mark.asyncio
    async def test_invoked_learns_minimal_config(self, mock_chat_message):
        """Test learning minimal cluster preference."""
        memory = ClusterMemory()
        message = mock_chat_message("create a minimal cluster called test")

        await memory.invoked(message)

        assert memory.preferences.default_config == "minimal"

    @pytest.mark.asyncio
    async def test_invoked_learns_custom_config(self, mock_chat_message):
        """Test learning custom cluster preference."""
        memory = ClusterMemory()
        message = mock_chat_message("create a custom cluster called prod")

        await memory.invoked(message)

        assert memory.preferences.default_config == "custom"

    @pytest.mark.asyncio
    async def test_invoked_learns_cluster_names(self, mock_chat_message):
        """Test learning cluster names from messages."""
        memory = ClusterMemory()

        messages = [
            mock_chat_message("create a cluster called dev-env"),
            mock_chat_message("cluster named test-cluster"),
            mock_chat_message("delete staging-cluster"),
        ]

        for msg in messages:
            await memory.invoked(msg)

        assert "dev-env" in memory.preferences.recent_cluster_names
        assert "test-cluster" in memory.preferences.recent_cluster_names
        assert "staging-cluster" in memory.preferences.recent_cluster_names

    @pytest.mark.asyncio
    async def test_invoked_limits_cluster_names(self, mock_chat_message):
        """Test cluster names are limited to 10."""
        memory = ClusterMemory()

        # Create 15 cluster names
        for i in range(15):
            msg = mock_chat_message(f"create cluster called cluster-{i}")
            await memory.invoked(msg)

        # Should only keep last 10
        assert len(memory.preferences.recent_cluster_names) == 10
        assert "cluster-14" in memory.preferences.recent_cluster_names
        assert "cluster-0" not in memory.preferences.recent_cluster_names

    @pytest.mark.asyncio
    async def test_invoked_learns_k8s_version(self, mock_chat_message):
        """Test learning Kubernetes version."""
        memory = ClusterMemory()
        message = mock_chat_message("create cluster with version v1.28.0")

        await memory.invoked(message)

        assert memory.preferences.default_k8s_version == "v1.28.0"

    @pytest.mark.asyncio
    async def test_invoked_detects_naming_pattern(self, mock_chat_message):
        """Test detecting naming patterns."""
        memory = ClusterMemory()

        # Create clusters with common prefix (needs hyphens for pattern detection)
        messages = [
            mock_chat_message("create cluster called dev-env1"),
            mock_chat_message("create cluster called dev-env2"),
            mock_chat_message("create cluster called dev-env3"),
        ]

        for msg in messages:
            await memory.invoked(msg)

        # Should detect "dev-" pattern
        assert memory.preferences.preferred_naming_pattern is not None
        assert "dev" in memory.preferences.preferred_naming_pattern

    def test_serialize(self):
        """Test serializing preferences."""
        memory = ClusterMemory()
        memory.preferences.default_config = "minimal"
        memory.preferences.recent_cluster_names = ["test-1", "test-2"]

        serialized = memory.serialize()

        assert isinstance(serialized, dict)
        assert serialized["default_config"] == "minimal"
        assert serialized["recent_cluster_names"] == ["test-1", "test-2"]

    def test_deserialize(self):
        """Test deserializing preferences."""
        data = {
            "default_config": "custom",
            "default_k8s_version": "v1.29.0",
            "recent_cluster_names": ["prod-1", "prod-2"],
            "preferred_naming_pattern": "prod-*",
        }

        memory = ClusterMemory.deserialize(data)

        assert memory.preferences.default_config == "custom"
        assert memory.preferences.default_k8s_version == "v1.29.0"
        assert memory.preferences.recent_cluster_names == ["prod-1", "prod-2"]
        assert memory.preferences.preferred_naming_pattern == "prod-*"

    @pytest.mark.asyncio
    async def test_invoked_handles_list_of_messages(self, mock_chat_message):
        """Test invoked handles both single message and list."""
        memory = ClusterMemory()

        # Test with list
        messages = [
            mock_chat_message("create minimal cluster called test-cluster"),
        ]

        await memory.invoked(messages)

        assert memory.preferences.default_config == "minimal"
        assert "test-cluster" in memory.preferences.recent_cluster_names


class TestConversationMetricsMemory:
    """Test suite for ConversationMetricsMemory context provider."""

    def test_init(self):
        """Test initialization."""
        memory = ConversationMetricsMemory()

        assert memory.metrics is not None
        assert isinstance(memory.metrics, ConversationMetrics)
        assert memory.metrics.total_queries == 0
        assert memory.metrics.clusters_created == 0

    @pytest.mark.asyncio
    async def test_invoked_tracks_queries(self, mock_chat_message):
        """Test tracking query count."""
        memory = ConversationMetricsMemory()
        message = mock_chat_message("list clusters")

        await memory.invoked(message)
        await memory.invoked(message)

        assert memory.metrics.total_queries == 2

    @pytest.mark.asyncio
    async def test_invoked_tracks_cluster_creation(self, mock_chat_message):
        """Test tracking cluster creation."""
        memory = ConversationMetricsMemory()

        request_msg = mock_chat_message("create cluster")
        response_msg = mock_chat_message("Cluster created successfully", role="assistant")

        await memory.invoked(request_msg, response_messages=response_msg)

        assert memory.metrics.clusters_created == 1
        assert memory.metrics.successful_operations == 1

    @pytest.mark.asyncio
    async def test_invoked_tracks_cluster_deletion(self, mock_chat_message):
        """Test tracking cluster deletion."""
        memory = ConversationMetricsMemory()

        request_msg = mock_chat_message("delete cluster")
        response_msg = mock_chat_message("Cluster deleted successfully", role="assistant")

        await memory.invoked(request_msg, response_messages=response_msg)

        assert memory.metrics.clusters_deleted == 1
        assert memory.metrics.successful_operations == 1

    @pytest.mark.asyncio
    async def test_invoked_tracks_errors(self, mock_chat_message):
        """Test tracking errors."""
        memory = ConversationMetricsMemory()

        message = mock_chat_message("create cluster")
        error = Exception("Failed to create")

        await memory.invoked(message, invoke_exception=error)

        assert memory.metrics.errors_encountered == 1

    @pytest.mark.asyncio
    async def test_invoking_empty_at_start(self, mock_chat_message):
        """Test invoking returns empty context initially."""
        memory = ConversationMetricsMemory()
        message = mock_chat_message("test")

        context = await memory.invoking(message)

        assert context is not None
        assert context.instructions is None or context.instructions == ""

    @pytest.mark.asyncio
    async def test_invoking_provides_metrics_at_10(self, mock_chat_message):
        """Test invoking provides metrics at 10th query."""
        memory = ConversationMetricsMemory()
        message = mock_chat_message("test")

        # Track 10 queries (invoked increments total_queries)
        for _ in range(10):
            await memory.invoked(message)

        # After 10 queries, invoking should provide metrics
        context = await memory.invoking(message)

        assert context is not None
        assert context.instructions is not None
        assert "Session stats" in context.instructions

    def test_serialize(self):
        """Test serializing metrics."""
        memory = ConversationMetricsMemory()
        memory.metrics.total_queries = 5
        memory.metrics.clusters_created = 2
        memory.metrics.errors_encountered = 1

        serialized = memory.serialize()

        assert isinstance(serialized, dict)
        assert serialized["total_queries"] == 5
        assert serialized["clusters_created"] == 2
        assert serialized["errors_encountered"] == 1

    def test_deserialize(self):
        """Test deserializing metrics."""
        data = {
            "total_queries": 10,
            "clusters_created": 3,
            "clusters_deleted": 2,
            "errors_encountered": 1,
            "successful_operations": 5,
        }

        memory = ConversationMetricsMemory.deserialize(data)

        assert memory.metrics.total_queries == 10
        assert memory.metrics.clusters_created == 3
        assert memory.metrics.clusters_deleted == 2
        assert memory.metrics.errors_encountered == 1
        assert memory.metrics.successful_operations == 5

    def test_get_metrics(self):
        """Test getting metrics as dict."""
        memory = ConversationMetricsMemory()
        memory.metrics.total_queries = 7
        memory.metrics.clusters_created = 3

        metrics = memory.get_metrics()

        assert isinstance(metrics, dict)
        assert metrics["total_queries"] == 7
        assert metrics["clusters_created"] == 3

    @pytest.mark.asyncio
    async def test_invoked_handles_list_of_response_messages(self, mock_chat_message):
        """Test invoked handles list of response messages."""
        memory = ConversationMetricsMemory()

        request_msg = mock_chat_message("create cluster")
        response_msgs = [
            mock_chat_message("Creating...", role="assistant"),
            mock_chat_message("Cluster created successfully", role="assistant"),
        ]

        await memory.invoked(request_msg, response_messages=response_msgs)

        assert memory.metrics.clusters_created == 1
