"""Unit tests for kubectl manager."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from agent.cluster.kubectl_manager import KubectlManager
from agent.utils.errors import (
    ClusterNotFoundError,
    InvalidManifestError,
    KubeconfigNotFoundError,
    KubectlCommandError,
    ResourceNotFoundError,
)


class TestKubectlManager:
    """Tests for KubectlManager class."""

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_init_success(self, mock_run):
        """Test successful initialization."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")

        manager = KubectlManager()
        assert manager is not None

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "kubectl"
        assert args[1] == "version"
        assert args[2] == "--client"

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_init_kubectl_not_found(self, mock_run):
        """Test initialization when kubectl is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(KubectlCommandError) as exc_info:
            KubectlManager()

        assert "kubectl CLI not found" in str(exc_info.value)
        assert "install kubectl" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_init_kubectl_timeout(self, mock_run):
        """Test initialization timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("kubectl", 10)

        with pytest.raises(KubectlCommandError) as exc_info:
            KubectlManager()

        assert "timed out" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_kubeconfig_path(self, mock_run):
        """Test kubeconfig path resolution."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        path = manager._get_kubeconfig_path("test-cluster")
        assert path == Path("./data/test-cluster/kubeconfig")

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_validate_kubeconfig_success(self, mock_run):
        """Test successful kubeconfig validation."""
        # First call for __init__
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Second call for cluster-info validation
        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        with patch.object(Path, "exists", return_value=True):
            path = manager._validate_kubeconfig("test-cluster")
            assert path == Path("./data/test-cluster/kubeconfig")

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_validate_kubeconfig_not_found(self, mock_run):
        """Test kubeconfig file not found."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(KubeconfigNotFoundError) as exc_info:
                manager._validate_kubeconfig("test-cluster")

            assert "test-cluster" in str(exc_info.value)
            assert "Kubeconfig not found" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_validate_kubeconfig_cluster_not_accessible(self, mock_run):
        """Test cluster not accessible."""
        # First call for __init__
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Second call for cluster-info returns error
        mock_run.return_value = Mock(returncode=1, stderr="connection refused")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(ClusterNotFoundError) as exc_info:
                manager._validate_kubeconfig("test-cluster")

            assert "test-cluster" in str(exc_info.value)
            assert "not accessible" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_resources_success(self, mock_run):
        """Test successful resource retrieval."""
        # Mock __init__
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Mock validation
        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        # Mock get resources
        resources_data = {
            "items": [
                {"metadata": {"name": "pod-1"}},
                {"metadata": {"name": "pod-2"}},
            ]
        }
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(resources_data), stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.get_resources("test-cluster", "pods")

        assert result["cluster_name"] == "test-cluster"
        assert result["resource_type"] == "pods"
        assert result["namespace"] == "default"
        assert result["count"] == 2
        assert len(result["resources"]) == 2

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_resources_with_label_selector(self, mock_run):
        """Test resource retrieval with label selector."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        resources_data = {"items": [{"metadata": {"name": "nginx-pod"}}]}
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(resources_data), stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.get_resources("test-cluster", "pods", label_selector="app=nginx")

        assert result["label_selector"] == "app=nginx"
        assert result["count"] == 1

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_resources_empty(self, mock_run):
        """Test resource retrieval with no results."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        resources_data = {"items": []}
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(resources_data), stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.get_resources("test-cluster", "pods")

        assert result["count"] == 0
        assert result["resources"] == []

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_resources_command_fails(self, mock_run):
        """Test resource retrieval command failure."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Mock for validation (cluster-info) and get resources
        mock_run.side_effect = [
            Mock(returncode=0, stdout="cluster info"),  # validation
            Mock(returncode=1, stdout="", stderr="resource not found"),  # get resources
        ]

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(KubectlCommandError) as exc_info:
                manager.get_resources("test-cluster", "invalid-resource")

            assert "Failed to get" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    @patch("agent.cluster.kubectl_manager.tempfile.NamedTemporaryFile")
    def test_apply_manifest_success(self, mock_tempfile, mock_file, mock_run):
        """Test successful manifest application."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        # Mock temp file
        temp_mock = MagicMock()
        temp_mock.name = "/tmp/test.yaml"
        temp_mock.__enter__.return_value = temp_mock
        mock_tempfile.return_value = temp_mock

        # Mock apply output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="deployment.apps/nginx created\nservice/nginx created",
            stderr="",
        )

        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
"""

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "unlink"):
                result = manager.apply_manifest("test-cluster", manifest)

        assert result["cluster_name"] == "test-cluster"
        assert result["applied"] is True
        assert len(result["resources"]) == 2
        assert "deployment.apps/nginx created" in result["resources"]

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_apply_manifest_invalid_yaml(self, mock_run):
        """Test manifest application with invalid YAML."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        invalid_manifest = "this is not valid: yaml: ]["

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(InvalidManifestError) as exc_info:
                manager.apply_manifest("test-cluster", invalid_manifest)

            assert "Invalid YAML" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_delete_resource_success(self, mock_run):
        """Test successful resource deletion."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        mock_run.return_value = Mock(
            returncode=0, stdout="deployment.apps/nginx deleted", stderr=""
        )

        with patch.object(Path, "exists", return_value=True):
            result = manager.delete_resource("test-cluster", "deployment", "nginx")

        assert result["cluster_name"] == "test-cluster"
        assert result["deleted"] is True
        assert result["name"] == "nginx"

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_delete_resource_not_found(self, mock_run):
        """Test delete resource that doesn't exist."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Mock for validation (cluster-info) and delete
        mock_run.side_effect = [
            Mock(returncode=0, stdout="cluster info"),  # validation
            Mock(returncode=1, stdout="", stderr='Error: deployments.apps "nginx" not found'),
        ]

        with patch.object(Path, "exists", return_value=True):
            result = manager.delete_resource("test-cluster", "deployment", "nginx")

        # Should not raise, should return graceful response
        assert result["deleted"] is False
        assert "not found" in result["message"]

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_delete_resource_with_force(self, mock_run):
        """Test forced resource deletion."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        mock_run.return_value = Mock(returncode=0, stdout="pod/broken-pod deleted", stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.delete_resource("test-cluster", "pod", "broken-pod", force=True)

        assert result["deleted"] is True

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_logs_success(self, mock_run):
        """Test successful log retrieval."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        mock_logs = "log line 1\nlog line 2\nlog line 3"
        mock_run.return_value = Mock(returncode=0, stdout=mock_logs, stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.get_logs("test-cluster", "test-pod")

        assert result["cluster_name"] == "test-cluster"
        assert result["pod_name"] == "test-pod"
        assert result["logs"] == mock_logs
        assert result["lines"] == 3

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_logs_pod_not_found(self, mock_run):
        """Test log retrieval for non-existent pod."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Mock for validation (cluster-info) and get logs
        mock_run.side_effect = [
            Mock(returncode=0, stdout="cluster info"),  # validation
            Mock(returncode=1, stdout="", stderr='Error: pods "test-pod" not found'),
        ]

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                manager.get_logs("test-cluster", "test-pod")

            assert "test-pod" in str(exc_info.value)
            assert "not found" in str(exc_info.value)

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_get_logs_with_container(self, mock_run):
        """Test log retrieval with specific container."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        mock_logs = "container logs"
        mock_run.return_value = Mock(returncode=0, stdout=mock_logs, stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.get_logs("test-cluster", "test-pod", container="app", tail_lines=50)

        assert result["container"] == "app"

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_describe_resource_success(self, mock_run):
        """Test successful resource description."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        mock_run.return_value = Mock(returncode=0, stdout="cluster info")

        mock_description = """
Name:         nginx
Namespace:    default
Status:       Running
Events:       <none>
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_description, stderr="")

        with patch.object(Path, "exists", return_value=True):
            result = manager.describe_resource("test-cluster", "pod", "nginx")

        assert result["cluster_name"] == "test-cluster"
        assert result["resource_type"] == "pod"
        assert result["name"] == "nginx"
        assert "Name:         nginx" in result["description"]

    @patch("agent.cluster.kubectl_manager.subprocess.run")
    def test_describe_resource_not_found(self, mock_run):
        """Test describe resource that doesn't exist."""
        mock_run.return_value = Mock(returncode=0, stdout="kubectl version")
        manager = KubectlManager()

        # Mock for validation (cluster-info) and describe
        mock_run.side_effect = [
            Mock(returncode=0, stdout="cluster info"),  # validation
            Mock(returncode=1, stdout="", stderr='Error: pods "nginx" not found'),
        ]

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                manager.describe_resource("test-cluster", "pod", "nginx")

            assert "nginx" in str(exc_info.value)
            assert "not found" in str(exc_info.value)
