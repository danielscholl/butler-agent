"""Tests for create_cluster addon integration."""

from unittest.mock import MagicMock, patch

import pytest

from agent.cluster.tools import create_cluster
from agent.config import AgentConfig


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = AgentConfig()
    config.data_dir = "/tmp/test-data"
    config.default_k8s_version = "v1.34.0"
    return config


@pytest.fixture
def setup_tools(mock_config):
    """Initialize tools with mocks."""
    with (
        patch("agent.cluster.tools._kind_manager") as mock_kind,
        patch("agent.cluster.tools._kubectl_manager") as mock_kubectl,
        patch("agent.cluster.tools._cluster_status") as mock_status,
        patch("agent.cluster.tools._config", mock_config),
    ):

        # Setup mock kind manager
        mock_kind.create_cluster.return_value = {
            "cluster_name": "test",
            "status": "running",
            "nodes": 2,
            "kubernetes_version": "v1.34.0",
        }
        mock_kind.get_kubeconfig.return_value = "fake-kubeconfig"
        mock_kind.cluster_exists.return_value = False

        yield {
            "kind": mock_kind,
            "kubectl": mock_kubectl,
            "status": mock_status,
            "config": mock_config,
        }


@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
def test_create_cluster_without_addons(mock_write, mock_mkdir, mock_get_config, setup_tools):
    """Test cluster creation without add-ons."""
    _ = setup_tools  # noqa: F841
    mock_get_config.return_value = ("fake-config", "built-in default")

    result = create_cluster("test", "default")

    assert result.get("cluster_name") == "test"
    assert result.get("status") == "running"
    assert "addons_installed" not in result
    assert "created successfully" in result.get("message", "")


@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
def test_create_cluster_with_addons(
    mock_addon_manager_class, mock_write, mock_mkdir, mock_get_config, setup_tools
):
    """Test cluster creation with add-ons."""
    _ = setup_tools  # noqa: F841
    mock_get_config.return_value = ("fake-config", "built-in default")

    # Mock addon manager
    mock_addon_manager = MagicMock()
    mock_addon_manager.install_addons.return_value = {
        "success": True,
        "results": {"ingress": {"success": True, "message": "Installed"}},
        "failed": [],
        "message": "Addons: 1/1 succeeded",
    }
    mock_addon_manager_class.return_value = mock_addon_manager

    result = create_cluster("test", "default", addons=["ingress"])

    assert result.get("cluster_name") == "test"
    assert "addons_installed" in result
    assert result["addons_installed"]["success"] is True
    assert "Addons: 1/1 succeeded" in result.get("message", "")

    # Verify addon manager was created and used
    mock_addon_manager_class.assert_called_once()
    mock_addon_manager.install_addons.assert_called_once_with(["ingress"])


@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
def test_create_cluster_addon_failure(
    mock_addon_manager_class, mock_write, mock_mkdir, mock_get_config, setup_tools
):
    """Test cluster creation when addon fails (cluster should still succeed)."""
    mock_get_config.return_value = ("fake-config", "built-in default")

    # Mock addon manager with failure
    mock_addon_manager = MagicMock()
    mock_addon_manager.install_addons.return_value = {
        "success": False,
        "results": {"ingress": {"success": False, "error": "Install failed"}},
        "failed": ["ingress"],
        "message": "Addons: 0/1 succeeded, 1 failed: ingress",
    }
    mock_addon_manager_class.return_value = mock_addon_manager

    result = create_cluster("test", "default", addons=["ingress"])

    # Cluster creation should succeed
    assert result.get("cluster_name") == "test"
    assert result.get("status") == "running"

    # But addon should be reported as failed
    assert result["addons_installed"]["success"] is False
    assert "ingress" in result["addons_installed"]["failed"]


@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
def test_create_cluster_multiple_addons(
    mock_addon_manager_class, mock_write, mock_mkdir, mock_get_config, setup_tools
):
    """Test cluster creation with multiple add-ons."""
    mock_get_config.return_value = ("fake-config", "built-in default")

    # Mock addon manager with multiple addons
    mock_addon_manager = MagicMock()
    mock_addon_manager.install_addons.return_value = {
        "success": True,
        "results": {
            "ingress": {"success": True, "message": "Installed"},
            "registry": {"success": True, "skipped": True, "message": "Already installed"},
        },
        "failed": [],
        "message": "Addons: 2/2 succeeded, 1 already installed",
    }
    mock_addon_manager_class.return_value = mock_addon_manager

    result = create_cluster("test", "default", addons=["ingress", "registry"])

    assert result["addons_installed"]["success"] is True
    assert len(result["addons_installed"]["results"]) == 2


@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
def test_create_cluster_addon_without_kubeconfig(
    mock_write, mock_mkdir, mock_get_config, setup_tools
):
    """Test that addons are skipped if kubeconfig is not saved."""
    mocks = setup_tools
    mock_get_config.return_value = ("fake-config", "built-in default")

    # Make kubeconfig save fail
    mocks["kind"].get_kubeconfig.side_effect = Exception("kubeconfig error")

    with patch("agent.cluster.tools.logger"):
        result = create_cluster("test", "default", addons=["ingress"])

        # Cluster should succeed
        assert result.get("cluster_name") == "test"

        # But addons should not be installed (no kubeconfig)
        assert "addons_installed" not in result
