"""LLM client factory for multi-provider support.

This module provides a factory function to create LLM clients compatible with
Microsoft Agent Framework, supporting OpenAI, Anthropic, Gemini, and Azure OpenAI.
"""

import logging
from typing import Any

from butler.config import ButlerConfig
from butler.utils.errors import ConfigurationError

logger = logging.getLogger(__name__)


def create_llm_client(config: ButlerConfig) -> Any:
    """Create LLM client based on configuration.

    This factory function creates an appropriate LLM client based on the
    configured provider (OpenAI, Anthropic, Gemini, or Azure OpenAI).

    Args:
        config: Butler configuration with provider settings

    Returns:
        LLM client compatible with Microsoft Agent Framework

    Raises:
        ConfigurationError: If provider is invalid or credentials are missing
    """
    provider = config.llm_provider.lower()

    logger.info(f"Creating LLM client for provider: {provider}")

    try:
        if provider == "openai":
            return _create_openai_client(config)
        elif provider == "anthropic":
            return _create_anthropic_client(config)
        elif provider == "gemini":
            return _create_gemini_client(config)
        elif provider == "azure":
            return _create_azure_openai_client(config)
        else:
            raise ConfigurationError(
                f"Unsupported LLM provider: {provider}. "
                "Must be one of: openai, anthropic, gemini, azure"
            )

    except ImportError as e:
        raise ConfigurationError(
            f"Failed to import SDK for provider '{provider}'. "
            f"Please ensure the required dependencies are installed. Error: {e}"
        )
    except Exception as e:
        raise ConfigurationError(f"Failed to create LLM client for '{provider}': {e}")


def _create_openai_client(config: ButlerConfig) -> Any:
    """Create OpenAI client.

    Args:
        config: Butler configuration

    Returns:
        OpenAI async client
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ConfigurationError(
            "OpenAI SDK not installed. Install with: pip install openai"
        )

    if not config.openai_api_key:
        raise ConfigurationError(
            "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
        )

    client = AsyncOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        organization=config.openai_organization,
    )

    logger.info(f"Created OpenAI client with model: {config.model_name}")
    return client


def _create_anthropic_client(config: ButlerConfig) -> Any:
    """Create Anthropic client.

    Args:
        config: Butler configuration

    Returns:
        Anthropic async client
    """
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise ConfigurationError(
            "Anthropic SDK not installed. Install with: pip install anthropic"
        )

    if not config.anthropic_api_key:
        raise ConfigurationError(
            "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable."
        )

    client = AsyncAnthropic(api_key=config.anthropic_api_key)

    logger.info(f"Created Anthropic client with model: {config.model_name}")
    return client


def _create_gemini_client(config: ButlerConfig) -> Any:
    """Create Google Gemini client.

    Args:
        config: Butler configuration

    Returns:
        Gemini generative model
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ConfigurationError(
            "Google Generative AI SDK not installed. Install with: pip install google-generativeai"
        )

    if not config.gemini_api_key:
        raise ConfigurationError(
            "Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
        )

    genai.configure(api_key=config.gemini_api_key)
    client = genai.GenerativeModel(config.model_name or "gemini-2.0-flash-exp")

    logger.info(f"Created Gemini client with model: {config.model_name}")
    return client


def _create_azure_openai_client(config: ButlerConfig) -> Any:
    """Create Azure OpenAI client.

    Args:
        config: Butler configuration

    Returns:
        Azure OpenAI responses client
    """
    try:
        from agent_framework.azure import AzureOpenAIResponsesClient
        from azure.identity import AzureCliCredential, DefaultAzureCredential
    except ImportError:
        raise ConfigurationError(
            "Azure SDK not installed. Install with: pip install azure-identity agent-framework"
        )

    if not config.azure_openai_endpoint:
        raise ConfigurationError(
            "Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT environment variable."
        )

    if not config.azure_openai_deployment:
        raise ConfigurationError(
            "Azure OpenAI deployment name is required. Set AZURE_OPENAI_DEPLOYMENT_NAME environment variable."
        )

    # Use Azure CLI credential or API key
    if config.azure_openai_api_key:
        # Use API key authentication
        client = AzureOpenAIResponsesClient(
            endpoint=config.azure_openai_endpoint,
            model=config.azure_openai_deployment,
            api_version=config.azure_openai_api_version,
            api_key=config.azure_openai_api_key,
        )
        logger.info("Created Azure OpenAI client with API key authentication")
    else:
        # Use Azure CLI credential
        try:
            credential = AzureCliCredential()
            client = AzureOpenAIResponsesClient(
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
            client = AzureOpenAIResponsesClient(
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


def get_model_name(config: ButlerConfig) -> str:
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
