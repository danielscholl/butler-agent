"""Unit tests for LLM client factory."""

from unittest.mock import MagicMock, patch

import pytest

from butler.config import ButlerConfig
from butler.llm_client import create_llm_client, get_model_name
from butler.utils.errors import ConfigurationError


class TestGetModelName:
    """Test get_model_name function."""

    def test_azure_provider(self):
        """Test model name for Azure provider."""
        config = MagicMock()
        config.llm_provider = "azure"
        config.azure_openai_deployment = "gpt-4"

        assert get_model_name(config) == "gpt-4"

    def test_openai_provider(self):
        """Test model name for OpenAI provider."""
        config = MagicMock()
        config.llm_provider = "openai"
        config.openai_model = "gpt-4-turbo"

        assert get_model_name(config) == "gpt-4-turbo"

    def test_anthropic_provider(self):
        """Test model name for Anthropic provider."""
        config = MagicMock()
        config.llm_provider = "anthropic"
        config.anthropic_model = "claude-3-opus"

        assert get_model_name(config) == "claude-3-opus"

    def test_gemini_provider(self):
        """Test model name for Gemini provider."""
        config = MagicMock()
        config.llm_provider = "gemini"
        config.gemini_model = "gemini-pro"

        assert get_model_name(config) == "gemini-pro"


class TestCreateLLMClient:
    """Test create_llm_client factory function."""

    def test_invalid_provider(self):
        """Test error with invalid provider."""
        config = MagicMock()
        config.llm_provider = "invalid_provider"

        with pytest.raises(ConfigurationError, match="Unsupported LLM provider"):
            create_llm_client(config)

    @patch("butler.llm_client._create_openai_client")
    def test_openai_provider(self, mock_create):
        """Test OpenAI client creation."""
        config = MagicMock()
        config.llm_provider = "openai"
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        result = create_llm_client(config)

        assert result == mock_client
        mock_create.assert_called_once_with(config)

    @patch("butler.llm_client._create_anthropic_client")
    def test_anthropic_provider(self, mock_create):
        """Test Anthropic client creation."""
        config = MagicMock()
        config.llm_provider = "anthropic"
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        result = create_llm_client(config)

        assert result == mock_client
        mock_create.assert_called_once_with(config)

    @patch("butler.llm_client._create_gemini_client")
    def test_gemini_provider(self, mock_create):
        """Test Gemini client creation."""
        config = MagicMock()
        config.llm_provider = "gemini"
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        result = create_llm_client(config)

        assert result == mock_client
        mock_create.assert_called_once_with(config)

    @patch("butler.llm_client._create_azure_openai_client")
    def test_azure_provider(self, mock_create):
        """Test Azure OpenAI client creation."""
        config = MagicMock()
        config.llm_provider = "azure"
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        result = create_llm_client(config)

        assert result == mock_client
        mock_create.assert_called_once_with(config)

    def test_openai_missing_api_key(self):
        """Test OpenAI client with missing API key."""
        config = MagicMock()
        config.llm_provider = "openai"
        config.openai_api_key = None

        with pytest.raises(ConfigurationError, match="API key is required"):
            create_llm_client(config)

    def test_anthropic_missing_api_key(self):
        """Test Anthropic client with missing API key."""
        config = MagicMock()
        config.llm_provider = "anthropic"
        config.anthropic_api_key = None

        with pytest.raises(ConfigurationError, match="API key is required"):
            create_llm_client(config)

    def test_gemini_missing_api_key(self):
        """Test Gemini client with missing API key."""
        config = MagicMock()
        config.llm_provider = "gemini"
        config.gemini_api_key = None

        with pytest.raises(ConfigurationError, match="API key is required"):
            create_llm_client(config)
