"""Chat client factory for OpenAI and Azure OpenAI providers.

This module provides a factory function to create chat clients compatible with
Microsoft Agent Framework, supporting OpenAI and Azure OpenAI.
"""

import logging

from agent.config import AgentConfig
from agent.utils.errors import ConfigurationError

logger = logging.getLogger(__name__)


def create_chat_client(config: AgentConfig):
    """Create chat client based on configuration.

    This factory function creates an appropriate chat client based on the
    configured provider (OpenAI or Azure OpenAI).

    Args:
        config: Butler configuration with provider settings

    Returns:
        BaseChatClient compatible with Microsoft Agent Framework

    Raises:
        ConfigurationError: If provider is invalid or credentials are missing
    """
    provider = config.llm_provider.lower()

    logger.info(f"Creating chat client for provider: {provider}")

    try:
        if provider == "openai":
            return _create_openai_client(config)
        elif provider == "azure":
            return _create_azure_openai_client(config)
        else:
            raise ConfigurationError(
                f"Unsupported LLM provider: {provider}. Must be one of: openai, azure"
            )

    except ImportError as e:
        raise ConfigurationError(
            f"Failed to import SDK for provider '{provider}'. "
            f"Please ensure the required dependencies are installed. Error: {e}"
        ) from e
    except Exception as e:
        raise ConfigurationError(f"Failed to create chat client for '{provider}': {e}") from e


def _create_openai_client(config: AgentConfig):
    """Create OpenAI client.

    Args:
        config: Butler configuration

    Returns:
        OpenAI chat or responses client compatible with agent framework
    """
    try:
        from agent_framework.openai import OpenAIChatClient, OpenAIResponsesClient
    except ImportError as e:
        raise ConfigurationError(
            "Agent framework OpenAI support not installed. "
            "Install with: pip install agent-framework"
        ) from e

    if not config.openai_api_key:
        raise ConfigurationError(
            "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
        )

    model_name = config.model_name or "gpt-5-codex"

    # gpt-5-codex requires the responses endpoint, use OpenAIResponsesClient
    # gpt-5-mini and others use chat completions endpoint, use OpenAIChatClient
    if "codex" in model_name.lower():
        return OpenAIResponsesClient(
            model_id=model_name,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            org_id=config.openai_organization,
        )
    else:
        return OpenAIChatClient(
            model_id=model_name,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            org_id=config.openai_organization,
        )


def _create_azure_openai_client(config: AgentConfig):
    """Create Azure OpenAI client.

    Args:
        config: Butler configuration

    Returns:
        Azure OpenAI chat client
    """
    try:
        from agent_framework.azure import AzureOpenAIChatClient
        from azure.identity import AzureCliCredential, DefaultAzureCredential
    except ImportError as e:
        raise ConfigurationError(
            "Azure SDK not installed. Install with: pip install azure-identity agent-framework"
        ) from e

    if not config.azure_openai_endpoint:
        raise ConfigurationError(
            "Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT environment variable."
        )

    if not config.azure_openai_deployment:
        raise ConfigurationError(
            "Azure OpenAI deployment name is required. "
            "Set AZURE_OPENAI_DEPLOYMENT_NAME environment variable."
        )

    # Use Azure CLI credential or API key
    if config.azure_openai_api_key:
        # Use API key authentication
        client = AzureOpenAIChatClient(
            endpoint=config.azure_openai_endpoint,
            model=config.azure_openai_deployment,
            api_version=config.azure_openai_api_version,
            api_key=config.azure_openai_api_key,
        )
        logger.info("Created Azure OpenAI client with API key authentication")
    else:
        # Use Azure CLI credential
        try:
            credential: AzureCliCredential | DefaultAzureCredential = AzureCliCredential()
            client = AzureOpenAIChatClient(
                endpoint=config.azure_openai_endpoint,
                model=config.azure_openai_deployment,
                api_version=config.azure_openai_api_version,
                credential=credential,
            )
            logger.info("Created Azure OpenAI client with Azure CLI authentication")
        except Exception as e:
            logger.warning(f"Azure CLI authentication failed: {e}")
            logger.info("Trying DefaultAzureCredential...")
            credential = DefaultAzureCredential()
            client = AzureOpenAIChatClient(
                endpoint=config.azure_openai_endpoint,
                model=config.azure_openai_deployment,
                api_version=config.azure_openai_api_version,
                credential=credential,
            )
            logger.info("Created Azure OpenAI client with DefaultAzureCredential")

    logger.info(
        f"Created Azure OpenAI client: {config.azure_openai_endpoint}, "
        f"deployment: {config.azure_openai_deployment}"
    )
    return client


def get_model_name(config: AgentConfig) -> str:
    """Get the model name to use for the configured provider.

    Args:
        config: Butler configuration

    Returns:
        Model name string
    """
    if config.model_name:
        return config.model_name

    # Return default model name for provider
    return config._get_default_model_name()
