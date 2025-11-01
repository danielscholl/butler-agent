"""Unit tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from butler.config import ButlerConfig


class TestButlerConfig:
    """Test ButlerConfig class."""

    def test_default_configuration(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = ButlerConfig()

            assert config.llm_provider == "azure"
            assert config.data_dir == "./data"
            assert config.cluster_prefix == "butler-"
            assert config.default_k8s_version == "v1.34.0"
            assert config.log_level == "info"

    def test_environment_variable_loading_azure(self):
        """Test loading Azure OpenAI configuration from environment."""
        env = {
            "LLM_PROVIDER": "azure",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
            "AZURE_OPENAI_API_VERSION": "2025-03-01-preview",
        }

        with patch.dict(os.environ, env, clear=True):
            config = ButlerConfig()

            assert config.llm_provider == "azure"
            assert config.azure_openai_endpoint == "https://test.openai.azure.com/"
            assert config.azure_openai_deployment == "gpt-4"
            assert config.azure_openai_api_version == "2025-03-01-preview"

    def test_environment_variable_loading_openai(self):
        """Test loading OpenAI configuration from environment."""
        env = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "OPENAI_BASE_URL": "https://api.openai.com/v1",
        }

        with patch.dict(os.environ, env, clear=True):
            config = ButlerConfig()

            assert config.llm_provider == "openai"
            assert config.openai_api_key == "sk-test123"
            assert config.openai_base_url == "https://api.openai.com/v1"

    def test_validation_success_azure(self):
        """Test validation passes with valid Azure configuration."""
        env = {
            "LLM_PROVIDER": "azure",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
        }

        with patch.dict(os.environ, env, clear=True):
            config = ButlerConfig()
            config.validate()  # Should not raise

    def test_validation_failure_azure_missing_endpoint(self):
        """Test validation fails when Azure endpoint is missing."""
        env = {
            "LLM_PROVIDER": "azure",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
        }

        with patch.dict(os.environ, env, clear=True):
            config = ButlerConfig()

            with pytest.raises(ValueError, match="Azure OpenAI endpoint is required"):
                config.validate()

    def test_validation_failure_openai_missing_key(self):
        """Test validation fails when OpenAI key is missing."""
        env = {
            "LLM_PROVIDER": "openai",
        }

        with patch.dict(os.environ, env, clear=True):
            config = ButlerConfig()

            with pytest.raises(ValueError, match="OpenAI API key is required"):
                config.validate()

    def test_get_cluster_data_dir(self):
        """Test getting cluster data directory path."""
        with patch.dict(os.environ, {"BUTLER_DATA_DIR": "/tmp/test"}, clear=True):
            config = ButlerConfig()
            path = config.get_cluster_data_dir("test-cluster")

            assert path == Path("/tmp/test/test-cluster")

    def test_get_kubeconfig_path(self):
        """Test getting kubeconfig file path."""
        with patch.dict(os.environ, {"BUTLER_DATA_DIR": "/tmp/test"}, clear=True):
            config = ButlerConfig()
            path = config.get_kubeconfig_path("test-cluster")

            assert path == Path("/tmp/test/test-cluster/kubeconfig")

    def test_get_provider_display_name(self):
        """Test getting provider display name."""
        test_cases = [
            ("openai", "OpenAI gpt-5-codex"),
            ("azure", "Azure OpenAI gpt-5-codex"),
        ]

        for provider, expected in test_cases:
            env = {"LLM_PROVIDER": provider}

            # Add required credentials for validation
            if provider == "openai":
                env["OPENAI_API_KEY"] = "test"
            elif provider == "azure":
                env["AZURE_OPENAI_ENDPOINT"] = "https://test.com"
                env["AZURE_OPENAI_DEPLOYMENT_NAME"] = "gpt-4"

            with patch.dict(os.environ, env, clear=True):
                config = ButlerConfig()
                assert config.get_provider_display_name() == expected

    def test_model_name_defaults(self):
        """Test default model names per provider."""
        test_cases = [
            ("openai", "gpt-5-codex"),
            ("azure", "gpt-5-codex"),
        ]

        for provider, expected_model in test_cases:
            env = {"LLM_PROVIDER": provider}

            with patch.dict(os.environ, env, clear=True):
                config = ButlerConfig()
                assert config.model_name == expected_model
