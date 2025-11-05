"""Tests for AddonManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.cluster.addons.manager import AddonManager


@pytest.fixture
def manager():
    """Create addon manager for testing."""
    kubeconfig = Path("/tmp/test-kubeconfig")
    return AddonManager("test-cluster", kubeconfig)


def test_manager_initialization(manager):
    """Test manager initialization."""
    assert manager.cluster_name == "test-cluster"
    assert manager.kubeconfig_path == Path("/tmp/test-kubeconfig")
    assert len(manager._addon_registry) > 0


def test_validate_addon_name_success(manager):
    """Test valid addon name."""
    assert manager._validate_addon_name("ingress") == "ingress"
    assert manager._validate_addon_name("INGRESS") == "ingress"
    assert manager._validate_addon_name(" ingress ") == "ingress"
    assert manager._validate_addon_name("nginx") == "nginx"


def test_validate_addon_name_invalid(manager):
    """Test invalid addon name."""
    with pytest.raises(ValueError, match="Unknown addon"):
        manager._validate_addon_name("invalid-addon")


def test_get_addon_instance(manager):
    """Test getting addon instance."""
    addon = manager._get_addon_instance("ingress")

    assert addon is not None
    assert addon.cluster_name == "test-cluster"
    assert addon.kubeconfig_path == Path("/tmp/test-kubeconfig")


def test_install_addons_empty_list(manager):
    """Test installing with empty addon list."""
    result = manager.install_addons([])

    assert result["success"] is True
    assert result["results"] == {}
    assert result["failed"] == []
    assert "No addons specified" in result["message"]


@patch("agent.cluster.addons.manager.IngressNginxAddon")
def test_install_addons_success(mock_addon_class, manager):
    """Test successful addon installation."""
    mock_addon = MagicMock()
    mock_addon.run.return_value = {
        "success": True,
        "addon": "ingress",
        "message": "Installed successfully",
    }
    mock_addon_class.return_value = mock_addon

    result = manager.install_addons(["ingress"])

    assert result["success"] is True
    assert "ingress" in result["results"]
    assert result["results"]["ingress"]["success"] is True
    assert result["failed"] == []
    assert "1/1 succeeded" in result["message"]


@patch("agent.cluster.addons.manager.IngressNginxAddon")
def test_install_addons_failure(mock_addon_class, manager):
    """Test addon installation failure."""
    mock_addon = MagicMock()
    mock_addon.run.return_value = {
        "success": False,
        "addon": "ingress",
        "error": "Installation failed",
        "message": "Failed",
    }
    mock_addon_class.return_value = mock_addon

    result = manager.install_addons(["ingress"])

    assert result["success"] is False
    assert "ingress" in result["failed"]
    assert "1 failed" in result["message"]


@patch("agent.cluster.addons.manager.IngressNginxAddon")
def test_install_addons_already_installed(mock_addon_class, manager):
    """Test addon already installed."""
    mock_addon = MagicMock()
    mock_addon.run.return_value = {
        "success": True,
        "addon": "ingress",
        "skipped": True,
        "message": "Already installed",
    }
    mock_addon_class.return_value = mock_addon

    result = manager.install_addons(["ingress"])

    assert result["success"] is True
    assert "1 already installed" in result["message"]


@patch("agent.cluster.addons.manager.IngressNginxAddon")
def test_install_multiple_addons(mock_addon_class, manager):
    """Test installing multiple addons."""
    mock_addon = MagicMock()
    mock_addon.run.return_value = {
        "success": True,
        "addon": "ingress",
        "message": "Installed",
    }
    mock_addon_class.return_value = mock_addon

    # Use aliases to test deduplication
    result = manager.install_addons(["ingress", "nginx", "ingress-nginx"])

    # Should deduplicate to single addon
    assert result["success"] is True
    assert mock_addon.run.call_count == 1


def test_install_addons_invalid_name(manager):
    """Test installing with invalid addon name."""
    result = manager.install_addons(["invalid-addon"])

    assert result["success"] is False
    assert "invalid-addon" in result["failed"]
    assert "Invalid addon name" in result["results"]["invalid-addon"]["message"]


@patch("agent.cluster.addons.manager.IngressNginxAddon")
def test_install_addons_exception(mock_addon_class, manager):
    """Test addon installation with exception."""
    mock_addon = MagicMock()
    mock_addon.run.side_effect = Exception("Unexpected error")
    mock_addon_class.return_value = mock_addon

    result = manager.install_addons(["ingress"])

    assert result["success"] is False
    assert "ingress" in result["failed"]
    assert "Unexpected error" in result["results"]["ingress"]["error"]
