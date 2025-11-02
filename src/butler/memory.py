"""Memory and context providers for Butler Agent.

This module provides context providers that enable the agent to learn and remember
user preferences, patterns, and conversation history across interactions.
"""

import logging
import re
from collections.abc import MutableSequence, Sequence
from typing import Any

from agent_framework import ChatMessage, Context, ContextProvider
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ClusterPreferences(BaseModel):
    """User's cluster preferences and history."""

    default_config: str | None = None  # "minimal", "default", "custom"
    default_k8s_version: str | None = None
    recent_cluster_names: list[str] = []
    preferred_naming_pattern: str | None = None


class ClusterMemory(ContextProvider):
    """Remember user's cluster preferences and patterns.

    This context provider learns from user interactions to understand their
    preferences for cluster configurations, naming patterns, and Kubernetes versions.
    """

    def __init__(self, chat_client: Any = None):
        """Initialize with empty preferences.

        Args:
            chat_client: Optional chat client for advanced extraction
        """
        self.preferences = ClusterPreferences()
        self._chat_client = chat_client
        logger.debug("ClusterMemory initialized")

    async def invoking(
        self, messages: ChatMessage | MutableSequence[ChatMessage], **kwargs: Any
    ) -> Context:
        """Provide cluster preferences before agent invocation.

        Args:
            messages: Current conversation messages
            **kwargs: Additional context

        Returns:
            Context with personalized instructions
        """
        instructions = []

        # Add context about user's preferences
        if self.preferences.default_config:
            instructions.append(
                f"User typically prefers '{self.preferences.default_config}' "
                f"cluster configuration."
            )

        if self.preferences.default_k8s_version:
            instructions.append(
                f"User's default Kubernetes version is " f"{self.preferences.default_k8s_version}."
            )

        if self.preferences.recent_cluster_names:
            recent = ", ".join(self.preferences.recent_cluster_names[-3:])
            instructions.append(
                f"User's recent cluster names: {recent}. "
                f"Consider suggesting similar naming patterns."
            )

        if self.preferences.preferred_naming_pattern:
            instructions.append(
                f"User prefers cluster names matching pattern: "
                f"{self.preferences.preferred_naming_pattern}"
            )

        if instructions:
            context_text = " ".join(instructions)
            logger.debug(f"Providing cluster preferences: {context_text[:100]}...")
            return Context(instructions=context_text)

        return Context()

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Learn from cluster operations in the conversation.

        Args:
            request_messages: Messages sent to the agent
            response_messages: Messages returned by the agent
            invoke_exception: Exception if call failed
            **kwargs: Additional context
        """
        # Convert to list for easier processing
        if isinstance(request_messages, ChatMessage):
            request_messages = [request_messages]

        # Extract patterns from user messages
        for msg in request_messages:
            text = self._get_message_text(msg)

            if not text:
                continue

            # Look for cluster configuration preferences
            text_lower = text.lower()

            if "minimal" in text_lower and "cluster" in text_lower:
                if self.preferences.default_config != "minimal":
                    logger.info("Learning preference: minimal cluster configuration")
                    self.preferences.default_config = "minimal"
            elif "custom" in text_lower and "cluster" in text_lower:
                if self.preferences.default_config != "custom":
                    logger.info("Learning preference: custom cluster configuration")
                    self.preferences.default_config = "custom"

            # Extract cluster names from patterns like "cluster called/named X"
            cluster_patterns = [
                r"cluster\s+(?:called|named)\s+([a-z0-9-]+)",
                r"create\s+(?:a\s+)?([a-z0-9-]+)\s+cluster",
                r"delete\s+(?:the\s+)?([a-z0-9-]+)",
            ]

            for pattern in cluster_patterns:
                matches = re.findall(pattern, text_lower)
                for cluster_name in matches:
                    if cluster_name not in self.preferences.recent_cluster_names:
                        logger.info(f"Learning cluster name: {cluster_name}")
                        self.preferences.recent_cluster_names.append(cluster_name)
                        # Keep only last 10
                        if len(self.preferences.recent_cluster_names) > 10:
                            self.preferences.recent_cluster_names.pop(0)

            # Extract Kubernetes version patterns
            k8s_version_match = re.search(r"v(\d+\.\d+\.\d+)", text)
            if k8s_version_match:
                version = f"v{k8s_version_match.group(1)}"
                if self.preferences.default_k8s_version != version:
                    logger.info(f"Learning Kubernetes version preference: {version}")
                    self.preferences.default_k8s_version = version

        # Detect naming patterns from cluster names
        if len(self.preferences.recent_cluster_names) >= 3:
            self._detect_naming_pattern()

    def _detect_naming_pattern(self) -> None:
        """Detect common naming patterns from recent cluster names."""
        names = self.preferences.recent_cluster_names[-5:]

        # Check for common prefixes
        if len(names) >= 2:
            # Check if all names start with similar prefix
            prefixes = [name.split("-")[0] for name in names if "-" in name]
            if prefixes and len(set(prefixes)) <= 2:
                most_common = max(set(prefixes), key=prefixes.count)
                if prefixes.count(most_common) >= len(names) // 2:
                    pattern = f"{most_common}-*"
                    if self.preferences.preferred_naming_pattern != pattern:
                        logger.info(f"Detected naming pattern: {pattern}")
                        self.preferences.preferred_naming_pattern = pattern

    def _get_message_text(self, msg: ChatMessage) -> str:
        """Extract text from a ChatMessage.

        Args:
            msg: Chat message

        Returns:
            Message text or empty string
        """
        return getattr(msg, "text", str(msg) if msg else "")

    def serialize(self) -> dict:
        """Serialize preferences for persistence.

        Returns:
            Serialized preferences dict
        """
        return self.preferences.model_dump()

    @classmethod
    def deserialize(cls, data: dict, chat_client: Any = None) -> "ClusterMemory":
        """Deserialize preferences from stored data.

        Args:
            data: Serialized preferences
            chat_client: Optional chat client

        Returns:
            ClusterMemory instance with loaded preferences
        """
        memory = cls(chat_client=chat_client)
        memory.preferences = ClusterPreferences.model_validate(data)
        logger.info("ClusterMemory deserialized with preferences")
        return memory


class ConversationMetrics(BaseModel):
    """Conversation metrics and statistics."""

    total_queries: int = 0
    clusters_created: int = 0
    clusters_deleted: int = 0
    errors_encountered: int = 0
    successful_operations: int = 0


class ConversationMetricsMemory(ContextProvider):
    """Track conversation metrics and provide insights.

    This context provider tracks usage statistics and can provide periodic
    insights about the conversation session.
    """

    def __init__(self):
        """Initialize with zero metrics."""
        self.metrics = ConversationMetrics()
        logger.debug("ConversationMetricsMemory initialized")

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Track metrics from conversations.

        Args:
            request_messages: Messages sent to agent
            response_messages: Messages returned by agent
            invoke_exception: Exception if call failed
            **kwargs: Additional context
        """
        self.metrics.total_queries += 1

        if invoke_exception:
            self.metrics.errors_encountered += 1
            logger.debug(f"Error tracked: {invoke_exception}")
            return

        # Track operations from response messages
        if response_messages:
            response_text = self._extract_response_text(response_messages)

            if response_text:
                response_lower = response_text.lower()

                if "created successfully" in response_lower:
                    self.metrics.clusters_created += 1
                    self.metrics.successful_operations += 1
                    logger.debug("Cluster creation tracked")

                elif "deleted successfully" in response_lower:
                    self.metrics.clusters_deleted += 1
                    self.metrics.successful_operations += 1
                    logger.debug("Cluster deletion tracked")

                elif "cluster" in response_lower and "running" in response_lower:
                    self.metrics.successful_operations += 1

    async def invoking(
        self, messages: ChatMessage | MutableSequence[ChatMessage], **kwargs: Any
    ) -> Context:
        """Provide metrics context periodically.

        Args:
            messages: Current conversation messages
            **kwargs: Additional context

        Returns:
            Context with metrics information (every 10 queries)
        """
        # Provide metrics summary every 10 queries
        if self.metrics.total_queries > 0 and self.metrics.total_queries % 10 == 0:
            instructions = (
                f"Session stats: {self.metrics.clusters_created} clusters created, "
                f"{self.metrics.clusters_deleted} deleted, "
                f"{self.metrics.successful_operations} successful operations, "
                f"{self.metrics.errors_encountered} errors."
            )
            logger.info(f"Providing metrics: {instructions}")
            return Context(instructions=instructions)

        return Context()

    def _extract_response_text(self, response_messages: ChatMessage | Sequence[ChatMessage]) -> str:
        """Extract text from response messages.

        Args:
            response_messages: Response messages

        Returns:
            Combined response text
        """
        if isinstance(response_messages, ChatMessage):
            return getattr(response_messages, "text", str(response_messages))

        response_text = ""
        for msg in response_messages:
            response_text += getattr(msg, "text", str(msg))

        return response_text

    def serialize(self) -> dict:
        """Serialize metrics for persistence.

        Returns:
            Serialized metrics dict
        """
        return self.metrics.model_dump()

    @classmethod
    def deserialize(cls, data: dict) -> "ConversationMetricsMemory":
        """Deserialize metrics from stored data.

        Args:
            data: Serialized metrics

        Returns:
            ConversationMetricsMemory with loaded metrics
        """
        memory = cls()
        memory.metrics = ConversationMetrics.model_validate(data)
        logger.info("ConversationMetricsMemory deserialized")
        return memory

    def get_metrics(self) -> dict:
        """Get current metrics as dict.

        Returns:
            Metrics dictionary
        """
        return self.metrics.model_dump()
