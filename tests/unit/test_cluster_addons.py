"""Tests for create_cluster addon integration."""

from unittest.mock import AsyncMock, MagicMock, patch

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

        # Setup mock kind manager with async methods
        mock_kind.create_cluster = AsyncMock(
            return_value={
                "cluster_name": "test",
                "status": "running",
                "nodes": 2,
                "kubernetes_version": "v1.34.0",
            }
        )
        mock_kind.get_kubeconfig = AsyncMock(return_value="fake-kubeconfig")
        mock_kind.cluster_exists = AsyncMock(return_value=False)

        yield {
            "kind": mock_kind,
            "kubectl": mock_kubectl,
            "status": mock_status,
            "config": mock_config,
        }


@pytest.mark.asyncio
@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
async def test_create_cluster_without_addons(mock_write, mock_mkdir, mock_get_config, setup_tools):
    """Test cluster creation without add-ons."""
    # setup_tools fixture needed for its side effects (setting up mocks)
    mock_get_config.return_value = ("fake-config", "built-in default")

    result = await create_cluster("test", "default")

    assert result.get("cluster_name") == "test"
    assert result.get("status") == "running"
    assert "addons_installed" not in result
    assert "created successfully" in result.get("message", "")


@pytest.mark.asyncio
@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
@patch("agent.utils.port_checker.check_ingress_ports")
async def test_create_cluster_with_addons(
    mock_check_ports,
    mock_addon_manager_class,
    mock_write,
    mock_mkdir,
    mock_get_config,
    setup_tools,
):
    """Test cluster creation with add-ons (two-phase pattern)."""
    # setup_tools fixture needed for its side effects (setting up mocks)
    mock_get_config.return_value = (
        "nodes:\n- role: control-plane\n",
        "built-in default",
    )

    # Mock port checker to return available ports
    mock_check_ports.return_value = {"available": True, "conflicts": []}

    # Mock addon manager for both phases
    mock_addon_manager = MagicMock()

    # Phase 1: Config collection
    mock_addon_manager._validate_addon_name.return_value = "ingress"
    mock_addon_manager._alias_map = {"ingress": "ingress"}
    mock_addon_instance = MagicMock()
    mock_addon_instance.get_cluster_config_requirements.return_value = {}
    mock_addon_instance.get_port_requirements.return_value = []
    mock_addon_instance.get_node_labels.return_value = {}
    mock_addon_manager.get_addon_instance.return_value = mock_addon_instance

    # Phase 2: Installation (async method)
    mock_addon_manager.install_addons = AsyncMock(
        return_value={
            "success": True,
            "results": {"ingress": {"success": True, "message": "Installed"}},
            "failed": [],
            "message": "Addons: 1/1 succeeded",
        }
    )

    mock_addon_manager_class.return_value = mock_addon_manager

    result = await create_cluster("test", "default", addons=["ingress"])

    assert result.get("cluster_name") == "test"
    assert "addons_installed" in result
    assert result["addons_installed"]["success"] is True
    assert "Addons: 1/1 succeeded" in result.get("message", "")

    # Verify addon manager was created twice (Phase 1 and Phase 2)
    assert mock_addon_manager_class.call_count == 2
    mock_addon_manager.install_addons.assert_called_once_with(["ingress"])


@pytest.mark.asyncio
@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
@patch("agent.utils.port_checker.check_ingress_ports")
async def test_create_cluster_addon_failure(
    mock_check_ports,
    mock_addon_manager_class,
    mock_write,
    mock_mkdir,
    mock_get_config,
    setup_tools,
):
    """Test cluster creation when addon fails (cluster should still succeed)."""
    mock_get_config.return_value = (
        "nodes:\n- role: control-plane\n",
        "built-in default",
    )

    # Mock port checker to return available ports
    mock_check_ports.return_value = {"available": True, "conflicts": []}

    # Mock addon manager for both phases
    mock_addon_manager = MagicMock()

    # Phase 1: Config collection
    mock_addon_manager._validate_addon_name.return_value = "ingress"
    mock_addon_manager._alias_map = {"ingress": "ingress"}
    mock_addon_instance = MagicMock()
    mock_addon_instance.get_cluster_config_requirements.return_value = {}
    mock_addon_instance.get_port_requirements.return_value = []
    mock_addon_instance.get_node_labels.return_value = {}
    mock_addon_manager.get_addon_instance.return_value = mock_addon_instance

    # Phase 2: Installation with failure (async method)
    mock_addon_manager.install_addons = AsyncMock(
        return_value={
            "success": False,
            "results": {"ingress": {"success": False, "error": "Install failed"}},
            "failed": ["ingress"],
            "message": "Addons: 0/1 succeeded, 1 failed: ingress",
        }
    )
    mock_addon_manager_class.return_value = mock_addon_manager

    result = await create_cluster("test", "default", addons=["ingress"])

    # Cluster creation should succeed
    assert result.get("cluster_name") == "test"
    assert result.get("status") == "running"

    # But addon should be reported as failed
    assert result["addons_installed"]["success"] is False
    assert "ingress" in result["addons_installed"]["failed"]


@pytest.mark.asyncio
@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
@patch("agent.utils.port_checker.check_ingress_ports")
async def test_create_cluster_multiple_addons(
    mock_check_ports,
    mock_addon_manager_class,
    mock_write,
    mock_mkdir,
    mock_get_config,
    setup_tools,
):
    """Test cluster creation with multiple add-ons."""
    mock_get_config.return_value = (
        "nodes:\n- role: control-plane\n",
        "built-in default",
    )

    # Mock port checker to return available ports
    mock_check_ports.return_value = {"available": True, "conflicts": []}

    # Mock addon manager for both phases
    mock_addon_manager = MagicMock()

    # Phase 1: Config collection (support both ingress and registry)
    def validate_addon_name(name):
        return name

    mock_addon_manager._validate_addon_name.side_effect = validate_addon_name
    mock_addon_manager._alias_map = {"ingress": "ingress", "registry": "registry"}
    mock_addon_instance = MagicMock()
    mock_addon_instance.get_cluster_config_requirements.return_value = {}
    mock_addon_instance.get_port_requirements.return_value = []
    mock_addon_instance.get_node_labels.return_value = {}
    mock_addon_manager.get_addon_instance.return_value = mock_addon_instance

    # Phase 2: Installation with multiple addons (async method)
    mock_addon_manager.install_addons = AsyncMock(
        return_value={
            "success": True,
            "results": {
                "ingress": {"success": True, "message": "Installed"},
                "registry": {"success": True, "skipped": True, "message": "Already installed"},
            },
            "failed": [],
            "message": "Addons: 2/2 succeeded, 1 already installed",
        }
    )
    mock_addon_manager_class.return_value = mock_addon_manager

    result = await create_cluster("test", "default", addons=["ingress", "registry"])

    assert result["addons_installed"]["success"] is True
    assert len(result["addons_installed"]["results"]) == 2


@pytest.mark.asyncio
@patch("agent.cluster.tools.get_cluster_config")
@patch("agent.cluster.tools.Path.mkdir")
@patch("agent.cluster.tools.Path.write_text")
@patch("agent.cluster.tools.AddonManager")
@patch("agent.utils.port_checker.check_ingress_ports")
async def test_create_cluster_addon_without_kubeconfig(
    mock_check_ports,
    mock_addon_manager_class,
    mock_write,
    mock_mkdir,
    mock_get_config,
    setup_tools,
):
    """Test that addons are skipped if kubeconfig is not saved."""
    mocks = setup_tools
    mock_get_config.return_value = (
        "nodes:\n- role: control-plane\n",
        "built-in default",
    )

    # Mock port checker to return available ports
    mock_check_ports.return_value = {"available": True, "conflicts": []}

    # Mock addon manager for Phase 1 (config collection still happens)
    mock_addon_manager = MagicMock()
    mock_addon_manager._validate_addon_name.return_value = "ingress"
    mock_addon_manager._alias_map = {"ingress": "ingress"}
    mock_addon_instance = MagicMock()
    mock_addon_instance.get_cluster_config_requirements.return_value = {}
    mock_addon_instance.get_port_requirements.return_value = []
    mock_addon_instance.get_node_labels.return_value = {}
    mock_addon_manager.get_addon_instance.return_value = mock_addon_instance
    mock_addon_manager_class.return_value = mock_addon_manager

    # Make kubeconfig save fail
    from agent.utils.errors import KindCommandError

    mocks["kind"].get_kubeconfig.side_effect = KindCommandError("kubeconfig error")

    with patch("agent.cluster.tools.logger"):
        result = await create_cluster("test", "default", addons=["ingress"])

        # Cluster should succeed
        assert result.get("cluster_name") == "test"

        # But addons should not be installed (no kubeconfig for Phase 2)
        assert "addons_installed" not in result
