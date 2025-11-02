"""Unit tests for Agent."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from agent.agent import Agent
from agent.config import AgentConfig
from tests.mocks import MockChatClient


class TestAgentInitialization:
    """Test Agent initialization."""

    def test_init_with_mock_client(self, mock_chat_client, mock_config):
        """Test initializing agent with mock client (dependency injection)."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        assert agent.chat_client == mock_chat_client
        assert agent.config == mock_config
        assert agent.agent is not None

    def test_init_with_config_only(self, mock_config):
        """Test initializing agent with config only (production mode)."""
        with patch("agent.agent.create_chat_client") as mock_create:
            mock_client = MockChatClient()
            mock_create.return_value = mock_client

            agent = Agent(config=mock_config)

            # Verify client was created from config
            mock_create.assert_called_once_with(mock_config)
            assert agent.config == mock_config

    def test_init_requires_config_or_client(self):
        """Test that initialization requires either config or client."""
        with pytest.raises(ValueError, match="Either config or chat_client must be provided"):
            Agent(config=None, chat_client=None)

    def test_init_validates_config(self):
        """Test that invalid config raises validation error."""
        # Create config with invalid provider settings (defaults to azure)
        with patch.dict(os.environ, {}, clear=True):
            config = AgentConfig(
                llm_provider="azure",
                azure_openai_endpoint=None,  # Missing required endpoint
            )

            with pytest.raises(ValueError, match="Azure OpenAI endpoint is required"):
                Agent(config=config)

    def test_init_with_mcp_tools(self, mock_chat_client, mock_config):
        """Test initializing agent with MCP tools."""
        mcp_tools = [{"name": "test_tool", "description": "Test tool"}]

        agent = Agent(config=mock_config, chat_client=mock_chat_client, mcp_tools=mcp_tools)

        assert agent.agent is not None


class TestAgentRun:
    """Test Agent run method."""

    @pytest.mark.asyncio
    async def test_run_single_query(self, mock_chat_client, mock_config):
        """Test running a single query without thread."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        response = await agent.run("Test query")

        assert response == "Mock agent response"

    @pytest.mark.asyncio
    async def test_run_with_thread(self, mock_chat_client, mock_config):
        """Test running query with conversation thread."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)
        thread = agent.get_new_thread()

        response = await agent.run("First query", thread=thread)
        assert response == "Mock agent response"

        # Second query in same thread
        response2 = await agent.run("Second query", thread=thread)
        assert response2 == "Mock agent response"

    @pytest.mark.asyncio
    async def test_run_creates_thread_if_not_provided(self, mock_chat_client, mock_config):
        """Test that run creates a new thread if none provided."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        response = await agent.run("Test query")

        assert response == "Mock agent response"

    @pytest.mark.asyncio
    async def test_run_error_handling(self, mock_chat_client, mock_config):
        """Test error handling in run method."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        # Make the agent raise an error
        agent.agent.run = AsyncMock(side_effect=Exception("Test error"))

        with pytest.raises(Exception, match="Test error"):
            await agent.run("Test query")


class TestAgentRunStream:
    """Test Agent run_stream method."""

    @pytest.mark.asyncio
    async def test_run_stream_yields_chunks(self, mock_chat_client, mock_config):
        """Test streaming query yields chunks."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        chunks = []
        async for chunk in agent.run_stream("Test query"):
            chunks.append(chunk)

        # Mock client returns "Mock agent response" which gets split into words
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_run_stream_with_thread(self, mock_chat_client, mock_config):
        """Test streaming with conversation thread."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)
        thread = agent.get_new_thread()

        chunks = []
        async for chunk in agent.run_stream("Test query", thread=thread):
            chunks.append(chunk)

        assert len(chunks) > 0


class TestAgentThreadManagement:
    """Test Agent thread management."""

    def test_get_new_thread(self, mock_chat_client, mock_config):
        """Test creating new conversation thread."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)

        thread1 = agent.get_new_thread()
        thread2 = agent.get_new_thread()

        # Threads should be different objects
        assert thread1 is not thread2

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, mock_chat_client, mock_config):
        """Test multi-turn conversation with thread persistence."""
        agent = Agent(config=mock_config, chat_client=mock_chat_client)
        thread = agent.get_new_thread()

        # First turn
        response1 = await agent.run("What is Kubernetes?", thread=thread)
        assert response1 is not None

        # Second turn in same conversation
        response2 = await agent.run("Tell me more about that", thread=thread)
        assert response2 is not None

        # Responses should both work with the same thread
        assert response1 == "Mock agent response"
        assert response2 == "Mock agent response"
