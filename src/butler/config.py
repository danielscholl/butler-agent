"""Configuration management for Butler Agent.

This module handles configuration loading from environment variables and .env files,
including multi-provider LLM configuration (OpenAI, Anthropic, Gemini, Azure OpenAI).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


@dataclass
class ButlerConfig:
    """Butler Agent configuration.

    Loads configuration from environment variables with support for multiple LLM providers.
    """

    # LLM Provider Configuration
    llm_provider: Literal["openai", "anthropic", "gemini", "azure"] = "azure"
    model_name: str | None = None

    # OpenAI Configuration
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_organization: str | None = None

    # Anthropic Configuration
    anthropic_api_key: str | None = None

    # Gemini Configuration
    gemini_api_key: str | None = None

    # Azure OpenAI Configuration
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2025-03-01-preview"

    # Butler Configuration
    data_dir: str = "./data"
    cluster_prefix: str = "butler-"
    default_k8s_version: str = "v1.34.0"
    log_level: str = "info"

    # Observability Configuration (optional)
    applicationinsights_connection_string: str | None = None

    def __post_init__(self):
        """Load configuration from environment variables after initialization."""
        # Load .env file if present
        load_dotenv()

        # LLM Provider Configuration
        self.llm_provider = os.getenv("LLM_PROVIDER", self.llm_provider).lower()  # type: ignore
        self.model_name = os.getenv("MODEL_NAME", self.model_name)

        # OpenAI Configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", self.openai_base_url)
        self.openai_organization = os.getenv("OPENAI_ORGANIZATION", self.openai_organization)

        # Anthropic Configuration
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)

        # Gemini Configuration
        self.gemini_api_key = os.getenv(
            "GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", self.gemini_api_key)
        )

        # Azure OpenAI Configuration
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint)
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", self.azure_openai_api_key)
        self.azure_openai_deployment = os.getenv(
            "AZURE_OPENAI_DEPLOYMENT_NAME", self.azure_openai_deployment
        )
        self.azure_openai_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", self.azure_openai_api_version
        )

        # Butler Configuration
        self.data_dir = os.getenv("BUTLER_DATA_DIR", self.data_dir)
        self.cluster_prefix = os.getenv("BUTLER_CLUSTER_PREFIX", self.cluster_prefix)
        self.default_k8s_version = os.getenv("BUTLER_DEFAULT_K8S_VERSION", self.default_k8s_version)
        self.log_level = os.getenv("LOG_LEVEL", self.log_level).lower()

        # Observability Configuration
        self.applicationinsights_connection_string = os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", self.applicationinsights_connection_string
        )

        # Set default model name based on provider if not specified
        if not self.model_name:
            self.model_name = self._get_default_model_name()

    def _get_default_model_name(self) -> str:
        """Get default model name based on provider."""
        defaults = {
            "openai": "gpt-5-codex",
            "anthropic": "claude-3-5-sonnet-20241022",
            "gemini": "gemini-2.0-flash-exp",
            "azure": "gpt-5-codex",
        }
        return defaults.get(self.llm_provider, "gpt-5-codex")

    def validate(self) -> None:
        """Validate configuration based on selected provider.

        Raises:
            ValueError: If required credentials for the selected provider are missing.
        """
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "OpenAI API key is required when using OpenAI provider. "
                    "Set OPENAI_API_KEY environment variable."
                )
        elif self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "Anthropic API key is required when using Anthropic provider. "
                    "Set ANTHROPIC_API_KEY environment variable."
                )
        elif self.llm_provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError(
                    "Gemini API key is required when using Gemini provider. "
                    "Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
                )
        elif self.llm_provider == "azure":
            if not self.azure_openai_endpoint:
                raise ValueError(
                    "Azure OpenAI endpoint is required when using Azure provider. "
                    "Set AZURE_OPENAI_ENDPOINT environment variable."
                )
            if not self.azure_openai_deployment:
                raise ValueError(
                    "Azure OpenAI deployment name is required when using Azure provider. "
                    "Set AZURE_OPENAI_DEPLOYMENT_NAME environment variable."
                )
            # API key is optional if using Azure CLI authentication
        else:
            raise ValueError(
                f"Invalid LLM provider: {self.llm_provider}. "
                "Must be one of: openai, anthropic, gemini, azure"
            )

    def get_cluster_data_dir(self, cluster_name: str) -> Path:
        """Get data directory path for a specific cluster.

        Args:
            cluster_name: Name of the cluster

        Returns:
            Path to cluster data directory
        """
        return Path(self.data_dir) / cluster_name

    def get_kubeconfig_path(self, cluster_name: str) -> Path:
        """Get kubeconfig file path for a specific cluster.

        Args:
            cluster_name: Name of the cluster

        Returns:
            Path to kubeconfig file
        """
        return self.get_cluster_data_dir(cluster_name) / "kubeconfig"

    def get_provider_display_name(self) -> str:
        """Get friendly display name for the current provider.

        Returns:
            Display name like "OpenAI gpt-4o" or "Azure OpenAI gpt-4"
        """
        provider_names = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "gemini": "Google Gemini",
            "azure": "Azure OpenAI",
        }
        provider = provider_names.get(self.llm_provider, self.llm_provider)
        return f"{provider} {self.model_name}"
