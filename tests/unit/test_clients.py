"""Unit tests for chat client factory."""

import os
from unittest.mock import patch

import pytest

from butler.clients import create_chat_client, get_model_name
from butler.config import ButlerConfig
from butler.utils.errors import ConfigurationError


class TestCreateChatClient:
    """Test create_chat_client function."""

    def test_create_openai_client_success(self):
        """Test creating OpenAI client successfully."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"},
            clear=True,
        ):
            config = ButlerConfig(
                llm_provider="openai",
                openai_api_key="test-key",
                model_name="gpt-5-mini",
            )

            with patch("agent_framework.openai.OpenAIChatClient") as mock_client:
                create_chat_client(config)

                # Verify OpenAIChatClient was called with correct params
                mock_client.assert_called_once_with(
                    model_id="gpt-5-mini",
                    api_key="test-key",
                    base_url=None,
                    org_id=None,
                )

    def test_create_openai_responses_client_for_codex(self):
        """Test creating OpenAI Responses client for codex model."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"},
            clear=True,
        ):
            config = ButlerConfig(
                llm_provider="openai",
                openai_api_key="test-key",
                model_name="gpt-5-codex",
            )

            with patch("agent_framework.openai.OpenAIResponsesClient") as mock_client:
                create_chat_client(config)

                # Verify OpenAIResponsesClient was called
                mock_client.assert_called_once_with(
                    model_id="gpt-5-codex",
                    api_key="test-key",
                    base_url=None,
                    org_id=None,
                )

    def test_create_openai_client_with_custom_settings(self):
        """Test creating OpenAI client with custom base_url and org_id."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://custom.openai.com",
                "OPENAI_ORGANIZATION": "org-123",
            },
            clear=True,
        ):
            config = ButlerConfig(
                llm_provider="openai",
                openai_api_key="test-key",
                openai_base_url="https://custom.openai.com",
                openai_organization="org-123",
                model_name="gpt-5-mini",
            )

            with patch("agent_framework.openai.OpenAIChatClient") as mock_client:
                create_chat_client(config)

                mock_client.assert_called_once_with(
                    model_id="gpt-5-mini",
                    api_key="test-key",
                    base_url="https://custom.openai.com",
                    org_id="org-123",
                )

    def test_create_openai_client_missing_api_key(self):
        """Test creating OpenAI client without API key raises error."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            config = ButlerConfig(
                llm_provider="openai",
                openai_api_key=None,
            )

            with pytest.raises(ConfigurationError, match="OpenAI API key is required"):
                create_chat_client(config)

    def test_create_azure_client_success_with_api_key(self):
        """Test creating Azure OpenAI client with API key."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "azure",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
                "AZURE_OPENAI_API_KEY": "test-azure-key",
            },
            clear=True,
        ):
            config = ButlerConfig(
                llm_provider="azure",
                azure_openai_endpoint="https://test.openai.azure.com/",
                azure_openai_deployment="gpt-4",
                azure_openai_api_key="test-azure-key",
                azure_openai_api_version="2025-03-01-preview",
            )

            with patch("agent_framework.azure.AzureOpenAIChatClient") as mock_client:
                create_chat_client(config)

                mock_client.assert_called_once_with(
                    endpoint="https://test.openai.azure.com/",
                    model="gpt-4",
                    api_version="2025-03-01-preview",
                    api_key="test-azure-key",
                )

    def test_create_azure_client_success_with_cli_credential(self):
        """Test creating Azure OpenAI client with Azure CLI credential."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "azure",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
            },
            clear=True,
        ):
            config = ButlerConfig(
                llm_provider="azure",
                azure_openai_endpoint="https://test.openai.azure.com/",
                azure_openai_deployment="gpt-4",
                azure_openai_api_key=None,
            )

            with (
                patch("agent_framework.azure.AzureOpenAIChatClient") as mock_client,
                patch("azure.identity.AzureCliCredential") as mock_credential,
            ):
                create_chat_client(config)

                # Verify credential was created
                mock_credential.assert_called_once()

                # Verify client was created with credential
                assert mock_client.call_args[1]["credential"] is not None

    def test_create_azure_client_missing_endpoint(self):
        """Test creating Azure client without endpoint raises error."""
        with patch.dict(os.environ, {}, clear=True):
            config = ButlerConfig(
                llm_provider="azure",
                azure_openai_endpoint=None,
                azure_openai_deployment="gpt-4",
            )

            with pytest.raises(ConfigurationError, match="Azure OpenAI endpoint is required"):
                create_chat_client(config)

    def test_create_azure_client_missing_deployment(self):
        """Test creating Azure client without deployment name raises error."""
        with patch.dict(os.environ, {}, clear=True):
            config = ButlerConfig(
                llm_provider="azure",
                azure_openai_endpoint="https://test.openai.azure.com/",
                azure_openai_deployment=None,
            )

            with pytest.raises(
                ConfigurationError, match="Azure OpenAI deployment name is required"
            ):
                create_chat_client(config)

    def test_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises ConfigurationError."""
        config = ButlerConfig(
            llm_provider="openai",  # Valid provider for type hint
        )
        # Manually set to invalid value to test error handling
        config.llm_provider = "invalid"  # type: ignore

        with pytest.raises(ConfigurationError, match="Unsupported LLM provider: invalid"):
            create_chat_client(config)


class TestGetModelName:
    """Test get_model_name function."""

    def test_get_model_name_from_config(self):
        """Test getting model name from config."""
        config = ButlerConfig(
            llm_provider="openai",
            model_name="custom-model",
        )

        assert get_model_name(config) == "custom-model"

    def test_get_default_model_name_openai(self):
        """Test getting default model name for OpenAI."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            config = ButlerConfig(llm_provider="openai")

            assert get_model_name(config) == "gpt-5-codex"

    def test_get_default_model_name_azure(self):
        """Test getting default model name for Azure."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "azure"}, clear=True):
            config = ButlerConfig(llm_provider="azure")

            assert get_model_name(config) == "gpt-5-codex"
