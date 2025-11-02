"""Pytest fixtures for testing Butler Agent."""

import os
from typing import Any

import pytest

from agent.config import AgentConfig
from tests.mocks import MockChatClient


@pytest.fixture
def mock_chat_client() -> MockChatClient:
    """Create a mock chat client for testing.

    Returns:
        MockChatClient configured with test responses
    """
    return MockChatClient(
        model_id="mock-model",
        api_key="mock-api-key",
        responses=["Mock agent response"],
    )


@pytest.fixture
def mock_config() -> AgentConfig:
    """Create a mock configuration for testing.

    Returns:
        AgentConfig with test values
    """
    # Set test environment variables
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    os.environ["LLM_PROVIDER"] = "openai"

    config = AgentConfig(
        llm_provider="openai",
        openai_api_key="test-openai-key",
        model_name="gpt-5-mini",
    )

    return config


@pytest.fixture
def mock_azure_config() -> AgentConfig:
    """Create a mock Azure configuration for testing.

    Returns:
        AgentConfig with Azure test values
    """
    # Set test environment variables
    os.environ["LLM_PROVIDER"] = "azure"
    os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/"
    os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = "test-deployment"
    os.environ["AZURE_OPENAI_API_KEY"] = "test-azure-key"

    config = AgentConfig(
        llm_provider="azure",
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_deployment="test-deployment",
        azure_openai_api_key="test-azure-key",
    )

    return config


@pytest.fixture
def mock_butler_agent(mock_chat_client: MockChatClient, mock_config: AgentConfig) -> Any:
    """Create a mock Butler agent for testing.

    Args:
        mock_chat_client: Mock chat client
        mock_config: Mock configuration

    Returns:
        Agent instance with mock client
    """
    from agent.agent import Agent

    # Use dependency injection to provide mock client
    agent = Agent(config=mock_config, chat_client=mock_chat_client)
    return agent
