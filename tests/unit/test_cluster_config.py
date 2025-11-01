"""Unit tests for cluster configuration."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from butler.cluster.config import (
    _get_config_template,
    get_cluster_config,
)


class TestGetClusterConfig:
    """Test cluster configuration loading."""

    def test_minimal_config(self):
        """Test minimal cluster configuration."""
        config = get_cluster_config("minimal")

        assert "kind: Cluster" in config
        assert "apiVersion" in config
        assert "role: control-plane" in config

    def test_default_config(self):
        """Test default cluster configuration."""
        config = get_cluster_config("default")

        assert "kind: Cluster" in config
        assert "apiVersion" in config
        # Default config has more features than minimal
        assert len(config) > len(get_cluster_config("minimal"))

    def test_with_custom_version(self):
        """Test configuration with custom Kubernetes version."""
        config = get_cluster_config("minimal", kubernetes_version="v1.30.0")

        assert "kind: Cluster" in config
        # Version is embedded in node image name
        # This test just ensures the function completes without error

    @patch("butler.cluster.config.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="custom: config\n")
    def test_custom_config_file(self, mock_file, mock_exists):
        """Test loading custom config from file."""
        mock_exists.return_value = True
        mock_config = MagicMock()
        mock_config.data_dir = "/test/data"

        with patch("butler.cluster.config._config", mock_config):
            config = get_cluster_config("custom")

        assert config == "custom: config\n"

    def test_unknown_config_name(self):
        """Test unknown configuration name."""
        # Should use default config for unknown names
        config = get_cluster_config("unknown")
        default_config = get_cluster_config("default")
        assert config == default_config
