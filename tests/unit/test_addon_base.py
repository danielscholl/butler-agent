"""Tests for BaseAddon abstract class."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.cluster.addons.base import BaseAddon
from agent.utils.errors import HelmCommandError


class ConcreteAddon(BaseAddon):
    """Concrete implementation for testing."""

    def check_prerequisites(self) -> bool:
        return True

    def is_installed(self) -> bool:
        return False

    def install(self) -> dict:
        return {"success": True, "message": "Test addon installed"}


@pytest.fixture
def addon():
    """Create addon instance for testing."""
    kubeconfig = Path("/tmp/test-kubeconfig")
    return ConcreteAddon("test-cluster", kubeconfig, {"test": "config"})


def test_addon_initialization(addon):
    """Test addon initialization."""
    assert addon.cluster_name == "test-cluster"
    assert addon.kubeconfig_path == Path("/tmp/test-kubeconfig")
    assert addon.config == {"test": "config"}


def test_addon_logging(addon, caplog):
    """Test logging methods."""
    caplog.set_level(logging.INFO)

    addon.log_info("test info")
    assert "test info" in caplog.text

    addon.log_warn("test warning")
    assert "test warning" in caplog.text

    addon.log_error("test error")
    assert "test error" in caplog.text


@patch("subprocess.run")
def test_run_helm_success(mock_run, addon):
    """Test successful helm command execution."""
    mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")

    result = addon._run_helm(["version"])

    assert result.returncode == 0
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["helm", "version"]


@patch("subprocess.run")
def test_run_helm_failure(mock_run, addon):
    """Test failed helm command."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

    with pytest.raises(HelmCommandError, match="Helm command failed"):
        addon._run_helm(["invalid"], check=True)


@patch("subprocess.run")
def test_run_helm_timeout(mock_run, addon):
    """Test helm command timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="helm", timeout=30)

    with pytest.raises(HelmCommandError, match="timed out"):
        addon._run_helm(["version"])


@patch("subprocess.run")
def test_run_helm_not_found(mock_run, addon):
    """Test helm not found."""
    mock_run.side_effect = FileNotFoundError()

    with pytest.raises(HelmCommandError, match="helm CLI not found"):
        addon._run_helm(["version"])


@patch.object(ConcreteAddon, "_run_helm")
def test_add_helm_repo(mock_run_helm, addon):
    """Test adding helm repository."""
    addon._add_helm_repo("test-repo", "https://test.com")

    assert mock_run_helm.call_count == 2
    mock_run_helm.assert_any_call(["repo", "add", "test-repo", "https://test.com"], check=False)
    mock_run_helm.assert_any_call(["repo", "update"], check=False)


@patch.object(ConcreteAddon, "_run_helm")
def test_helm_install(mock_run_helm, addon):
    """Test helm install."""
    addon._helm_install(
        release_name="test-release",
        chart="test/chart",
        namespace="test-ns",
        values={"key": "value"},
        version="1.0.0",
    )

    mock_run_helm.assert_called_once()
    call_args = mock_run_helm.call_args[0][0]

    assert "upgrade" in call_args
    assert "--install" in call_args
    assert "test-release" in call_args
    assert "test/chart" in call_args
    assert "--namespace" in call_args
    assert "test-ns" in call_args
    assert "--set" in call_args
    assert "key=value" in call_args
    assert "--version" in call_args
    assert "1.0.0" in call_args


def test_run_success_flow(addon):
    """Test successful run flow."""
    result = addon.run()

    assert result["success"] is True
    assert result["addon"] == "concrete"
    assert "installed successfully" in result["message"]


def test_run_prerequisites_fail():
    """Test run when prerequisites fail."""

    class FailPrereqAddon(ConcreteAddon):
        def check_prerequisites(self):
            return False

    kubeconfig = Path("/tmp/test-kubeconfig")
    addon = FailPrereqAddon("test", kubeconfig)
    result = addon.run()

    assert result["success"] is False
    assert "Prerequisites not met" in result["error"]


def test_run_already_installed():
    """Test run when already installed."""

    class InstalledAddon(ConcreteAddon):
        def is_installed(self):
            return True

    kubeconfig = Path("/tmp/test-kubeconfig")
    addon = InstalledAddon("test", kubeconfig)
    result = addon.run()

    assert result["success"] is True
    assert result.get("skipped") is True
    assert "already installed" in result["message"]


def test_run_install_failure():
    """Test run when install fails."""

    class FailInstallAddon(ConcreteAddon):
        def install(self):
            return {"success": False, "error": "Install failed"}

    kubeconfig = Path("/tmp/test-kubeconfig")
    addon = FailInstallAddon("test", kubeconfig)
    result = addon.run()

    assert result["success"] is False
