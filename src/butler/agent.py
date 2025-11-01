"""Core Butler Agent implementation.

This module provides the main Agent class that orchestrates LLM interactions,
tool execution, and cluster management operations.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

from agent_framework import ChatAgent

from butler.cluster.tools import CLUSTER_TOOLS, initialize_tools
from butler.config import ButlerConfig
from butler.llm_client import create_llm_client, get_model_name
from butler.middleware import create_function_middleware

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


class Agent:
    """Butler Agent for conversational Kubernetes infrastructure management."""

    def __init__(
        self,
        config: ButlerConfig,
        mcp_tools: list | None = None,
    ):
        """Initialize Butler Agent.

        Args:
            config: Butler configuration
            mcp_tools: Optional list of MCP tools to register
        """
        self.config = config
        self.provider = config.llm_provider
        self.model_name = get_model_name(config)

        logger.info(
            f"Initializing Butler Agent with provider: {config.get_provider_display_name()}"
        )

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        # Initialize cluster tools
        initialize_tools(config)

        # Create LLM client
        try:
            self.llm_client = create_llm_client(config)
            logger.info(f"LLM client created successfully: {config.llm_provider}")
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            raise

        # Prepare tools
        tools: Sequence[Callable[..., Any]] = list(CLUSTER_TOOLS)
        if mcp_tools:
            tools = list(tools) + mcp_tools
            logger.info(f"Registered {len(mcp_tools)} MCP tools")

        # Create middleware
        function_middleware = create_function_middleware()

        # Create chat agent
        try:
            # ChatAgent expects a chat_client parameter (not client)
            self.agent = ChatAgent(
                chat_client=self.llm_client,
                instructions=SYSTEM_PROMPT,
                tools=tools,
                model=self.model_name if config.llm_provider != "azure" else None,
                middleware=list(function_middleware),
            )

            logger.info(f"Butler Agent initialized with {len(tools)} tools")

        except Exception as e:
            logger.error(f"Failed to create chat agent: {e}")
            raise

    async def run(self, query: str) -> str:
        """Run a query through the agent.

        Args:
            query: User query

        Returns:
            Agent response
        """
        logger.info(f"Processing query: {query[:100]}...")

        try:
            response = await self.agent.run(query)
            logger.info("Query processed successfully")
            return str(response)

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise

    async def run_stream(self, query: str):
        """Run a query through the agent with streaming response.

        Args:
            query: User query

        Yields:
            Response chunks
        """
        logger.info(f"Processing query (streaming): {query[:100]}...")

        try:
            async for chunk in self.agent.run_stream(query):
                yield chunk

        except Exception as e:
            logger.error(f"Error processing streaming query: {e}")
            raise
