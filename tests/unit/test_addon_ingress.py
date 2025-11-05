"""Tests for NGINX Ingress addon."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.cluster.addons.ingress_nginx import IngressNginxAddon


@pytest.fixture
def ingress_addon():
    """Create NGINX Ingress addon for testing."""
    kubeconfig = Path("/tmp/test-kubeconfig")
    return IngressNginxAddon("test-cluster", kubeconfig)


def test_ingress_addon_initialization(ingress_addon):
    """Test addon initialization."""
    assert ingress_addon.cluster_name == "test-cluster"
    assert ingress_addon.chart_version == IngressNginxAddon.DEFAULT_CHART_VERSION
    assert ingress_addon.namespace == IngressNginxAddon.DEFAULT_NAMESPACE
    assert ingress_addon.addon_name == "ingress-nginx"


def test_ingress_addon_custom_config():
    """Test addon with custom configuration."""
    kubeconfig = Path("/tmp/test-kubeconfig")
    config = {
        "chart_version": "4.12.0",
        "namespace": "custom-ns",
        "values": {"custom.key": "value"},
    }
    addon = IngressNginxAddon("test", kubeconfig, config)

    assert addon.chart_version == "4.12.0"
    assert addon.namespace == "custom-ns"
    assert addon.custom_values == {"custom.key": "value"}


@patch("subprocess.run")
def test_check_prerequisites_success(mock_run, ingress_addon):
    """Test prerequisites check success."""
    # Mock kubectl cluster-info
    mock_run.return_value = MagicMock(returncode=0, stdout="Kubernetes control plane")

    result = ingress_addon.check_prerequisites()

    assert result is True


@patch("subprocess.run")
def test_check_prerequisites_kubectl_fail(mock_run, ingress_addon):
    """Test prerequisites check when kubectl fails."""
    mock_run.return_value = MagicMock(returncode=1, stderr="cluster not accessible")

    result = ingress_addon.check_prerequisites()

    assert result is False


@patch("subprocess.run")
def test_check_prerequisites_helm_not_found(mock_run, ingress_addon):
    """Test prerequisites check when helm not found."""

    def run_side_effect(*args, **kwargs):
        if args[0][0] == "kubectl":
            return MagicMock(returncode=0)
        elif args[0][0] == "helm":
            raise FileNotFoundError()

    mock_run.side_effect = run_side_effect

    result = ingress_addon.check_prerequisites()

    assert result is False


@patch.object(IngressNginxAddon, "_run_helm")
def test_is_installed_via_helm(mock_run_helm, ingress_addon):
    """Test detecting installation via Helm."""
    mock_run_helm.return_value = MagicMock(returncode=0, stdout="ingress-nginx\n")

    result = ingress_addon.is_installed()

    assert result is True


@patch.object(IngressNginxAddon, "_run_helm")
@patch("subprocess.run")
def test_is_installed_via_kubectl(mock_subprocess, mock_run_helm, ingress_addon):
    """Test detecting installation via kubectl."""
    # Helm check fails
    mock_run_helm.side_effect = Exception("Helm error")

    # kubectl check succeeds
    mock_subprocess.return_value = MagicMock(returncode=0)

    result = ingress_addon.is_installed()

    assert result is True


@patch.object(IngressNginxAddon, "_run_helm")
@patch("subprocess.run")
def test_is_not_installed(mock_subprocess, mock_run_helm, ingress_addon):
    """Test when addon is not installed."""
    # Both Helm and kubectl checks fail
    mock_run_helm.return_value = MagicMock(returncode=0, stdout="")
    mock_subprocess.return_value = MagicMock(returncode=1)

    result = ingress_addon.is_installed()

    assert result is False


@patch.object(IngressNginxAddon, "_add_helm_repo")
@patch.object(IngressNginxAddon, "_helm_install")
def test_install_success(mock_helm_install, mock_add_repo, ingress_addon):
    """Test successful installation."""
    result = ingress_addon.install()

    assert result["success"] is True
    assert "NGINX Ingress Controller installed" in result["message"]

    # Verify helm repo was added
    mock_add_repo.assert_called_once_with(
        IngressNginxAddon.HELM_REPO_NAME, IngressNginxAddon.HELM_REPO_URL
    )

    # Verify helm install was called with correct parameters
    mock_helm_install.assert_called_once()
    call_kwargs = mock_helm_install.call_args[1]
    assert call_kwargs["release_name"] == IngressNginxAddon.RELEASE_NAME
    assert call_kwargs["chart"] == IngressNginxAddon.HELM_CHART
    assert call_kwargs["namespace"] == IngressNginxAddon.DEFAULT_NAMESPACE
    assert "controller.service.type" in call_kwargs["values"]


@patch.object(IngressNginxAddon, "_add_helm_repo")
@patch.object(IngressNginxAddon, "_helm_install")
def test_install_with_custom_values(mock_helm_install, mock_add_repo):
    """Test installation with custom values."""
    kubeconfig = Path("/tmp/test-kubeconfig")
    config = {"values": {"custom.key": "custom-value"}}
    addon = IngressNginxAddon("test", kubeconfig, config)

    addon.install()

    # Verify custom values are merged
    call_kwargs = mock_helm_install.call_args[1]
    assert "custom.key" in call_kwargs["values"]
    assert call_kwargs["values"]["custom.key"] == "custom-value"


@patch("subprocess.run")
def test_wait_for_ready_success(mock_run, ingress_addon):
    """Test waiting for deployment to be ready."""
    mock_run.return_value = MagicMock(returncode=0, stdout="deployment ready")

    result = ingress_addon.wait_for_ready(timeout=60)

    assert result is True


@patch("subprocess.run")
def test_wait_for_ready_timeout(mock_run, ingress_addon):
    """Test wait timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="kubectl wait", timeout=60)

    result = ingress_addon.wait_for_ready(timeout=60)

    assert result is False


@patch("subprocess.run")
def test_wait_for_ready_failure(mock_run, ingress_addon):
    """Test wait failure."""
    mock_run.return_value = MagicMock(returncode=1, stderr="deployment not ready")

    result = ingress_addon.wait_for_ready()

    assert result is False


@patch("subprocess.run")
def test_verify_success(mock_run, ingress_addon):
    """Test verification success."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="ingress-nginx-admission\nother-webhook\n"
    )

    result = ingress_addon.verify()

    assert result is True


@patch("subprocess.run")
def test_verify_failure(mock_run, ingress_addon):
    """Test verification failure."""
    mock_run.return_value = MagicMock(returncode=0, stdout="other-webhook\n")

    result = ingress_addon.verify()

    assert result is False


@patch("subprocess.run")
def test_verify_exception(mock_run, ingress_addon):
    """Test verification exception."""
    mock_run.side_effect = Exception("kubectl error")

    result = ingress_addon.verify()

    assert result is False
