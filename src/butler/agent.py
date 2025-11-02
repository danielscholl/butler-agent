"""Core Butler Agent implementation.

This module provides the main ButlerAgent class that orchestrates LLM interactions,
tool execution, and cluster management operations using Microsoft Agent Framework.
"""

import logging
from typing import Any

from butler.clients import create_chat_client
from butler.cluster.tools import CLUSTER_TOOLS, initialize_tools
from butler.config import ButlerConfig
from butler.memory import ClusterMemory, ConversationMetricsMemory
from butler.middleware import create_middleware

logger = logging.getLogger(__name__)

# System prompt template for Butler Agent
SYSTEM_PROMPT = """You are Butler, an AI-powered DevOps assistant specialized in Kubernetes infrastructure management.

Your primary expertise includes:
- Managing Kubernetes in Docker (KinD) clusters
- Cluster lifecycle operations (create, delete, status checks)
- Troubleshooting cluster issues
- Explaining Kubernetes concepts
- Providing best practices for local development environments

Key capabilities:
- Create KinD clusters with different configurations (minimal, default, custom)
- Check cluster status and health
- List all available clusters
- Delete clusters when no longer needed
- Provide clear, actionable guidance

Guidelines:
- Be concise and practical in your responses
- Always confirm destructive operations (like delete) before executing
- Provide helpful context when errors occur
- Suggest next steps and best practices
- If a cluster doesn't exist, suggest creating one with create_cluster
- When listing clusters, provide useful information about their status

Remember:
- KinD clusters run locally in Docker containers
- Each cluster has its own kubeconfig for access
- Cluster names should be lowercase with hyphens
- Default clusters include control-plane and worker nodes
- You can check node status, resource usage, and system pod health

Your goal is to make Kubernetes infrastructure management simple and conversational.
"""


class ButlerAgent:
    """Butler Agent for conversational Kubernetes infrastructure management.

    This agent uses the Microsoft Agent Framework's client.create_agent() pattern
    for proper framework integration and supports dependency injection for testing.
    """

    def __init__(
        self,
        config: ButlerConfig | None = None,
        chat_client: Any | None = None,
        mcp_tools: list | None = None,
        enable_memory: bool = True,
    ):
        """Initialize Butler Agent.

        Args:
            config: Butler configuration (required if chat_client not provided)
            chat_client: Optional chat client for dependency injection (testing)
            mcp_tools: Optional list of MCP tools to register
            enable_memory: Enable memory/context providers for learning user preferences

        Raises:
            ValueError: If neither config nor chat_client is provided
        """
        # Require either config or chat_client
        if config is None and chat_client is None:
            raise ValueError("Either config or chat_client must be provided")

        # Use provided config or create default
        self.config = config or ButlerConfig()

        logger.info(
            f"Initializing Butler Agent with provider: {self.config.get_provider_display_name()}"
        )

        # Validate configuration if provided
        if config is not None:
            try:
                config.validate()
            except ValueError as e:
                logger.error(f"Configuration validation failed: {e}")
                raise

        # Initialize cluster tools
        initialize_tools(self.config)

        # Create or use provided chat client
        if chat_client is not None:
            # Test mode: use provided mock client
            self.chat_client = chat_client
            logger.info("Using provided chat client (test mode)")
        else:
            # Production mode: create client from config
            try:
                self.chat_client = create_chat_client(self.config)
                logger.info(f"Chat client created successfully: {self.config.llm_provider}")
            except Exception as e:
                logger.error(f"Failed to create chat client: {e}")
                raise

        # Prepare tools
        tools = CLUSTER_TOOLS.copy()
        if mcp_tools:
            tools.extend(mcp_tools)
            logger.info(f"Registered {len(mcp_tools)} MCP tools")

        # Create middleware (both agent and function levels)
        middleware_config = create_middleware()

        # Create context providers (memory) if enabled
        context_providers = []
        if enable_memory:
            try:
                context_providers = [
                    ClusterMemory(chat_client=self.chat_client),
                    ConversationMetricsMemory(),
                ]
                logger.info("Memory context providers enabled")
            except Exception as e:
                logger.warning(f"Failed to create context providers: {e}")
                # Continue without memory if it fails
                context_providers = []

        # Create agent using framework's create_agent() pattern
        try:
            # Prepare agent creation kwargs
            agent_kwargs = {
                "name": "Butler",
                "instructions": SYSTEM_PROMPT,
                "tools": tools,
                "middleware": middleware_config["function"],  # Function middleware
            }

            # Add context providers if available
            if context_providers:
                agent_kwargs["context_providers"] = context_providers

            self.agent = self.chat_client.create_agent(**agent_kwargs)

            logger.info(
                f"Butler Agent initialized with {len(tools)} tools, "
                f"{len(middleware_config['function'])} function middleware, "
                f"and {len(context_providers)} context providers"
            )

            # Store agent middleware for potential use at run time
            self._agent_middleware = middleware_config["agent"]

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise

    async def run(self, query: str, thread: Any | None = None) -> str:
        """Run a query through the agent.

        Args:
            query: User query
            thread: Optional conversation thread for multi-turn conversations

        Returns:
            Agent response as string
        """
        logger.info(f"Processing query: {query[:100]}...")

        try:
            # Create new thread if not provided
            if thread is None:
                thread = self.get_new_thread()

            response = await self.agent.run(query, thread=thread)
            logger.info("Query processed successfully")

            # Extract message content from response
            # Check if response is a ChatMessage directly with text attribute
            if hasattr(response, "text"):
                return str(response.text)
            # Check if response has content attribute
            elif hasattr(response, "content"):
                return str(response.content)
            # Check if response has messages list
            elif hasattr(response, "messages") and response.messages:
                # Get the last message content
                last_message = response.messages[-1]
                if hasattr(last_message, "text"):
                    return str(last_message.text)
                elif hasattr(last_message, "content"):
                    return str(last_message.content)
                else:
                    return str(last_message)
            else:
                # Fallback to string representation
                return str(response)

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise

    async def run_stream(self, query: str, thread: Any | None = None):
        """Run a query through the agent with streaming response.

        Args:
            query: User query
            thread: Optional conversation thread for multi-turn conversations

        Yields:
            Response chunks
        """
        logger.info(f"Processing query (streaming): {query[:100]}...")

        try:
            # Create new thread if not provided
            if thread is None:
                thread = self.get_new_thread()

            async for chunk in self.agent.run_stream(query, thread=thread):
                yield chunk

        except Exception as e:
            logger.error(f"Error processing streaming query: {e}")
            raise

    def get_new_thread(self) -> Any:
        """Create a new conversation thread for multi-turn conversations.

        Returns:
            New AgentThread for maintaining conversation context
        """
        return self.agent.get_new_thread()
