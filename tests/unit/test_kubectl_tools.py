"""Unit tests for kubectl agent tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from agent.cluster import tools
from agent.config import AgentConfig
from agent.utils.errors import (
    ClusterNotFoundError,
    InvalidManifestError,
    KubeconfigNotFoundError,
    KubectlCommandError,
    ResourceNotFoundError,
)


class TestKubectlTools:
    """Tests for kubectl agent tools."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Reset global instances before each test
        tools._kubectl_manager = None
        tools._kind_manager = None
        tools._cluster_status = None
        tools._config = None

    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    def test_initialize_tools_creates_kubectl_manager(self, mock_status, mock_kind, mock_kubectl):
        """Test that initialize_tools creates a KubectlManager instance."""
        config = Mock(spec=AgentConfig)

        tools.initialize_tools(config)

        assert tools._kubectl_manager is not None
        mock_kubectl.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_get_resources_success(self, mock_status, mock_kind, mock_kubectl):
        """Test successful resource retrieval."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        # Mock manager response
        mock_manager = Mock()
        mock_manager.get_resources = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "resource_type": "pods",
                "namespace": "default",
                "resources": [{"metadata": {"name": "pod-1"}}],
                "count": 1,
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_get_resources("test-cluster", "pods")

        assert "message" in result
        assert result["count"] == 1
        assert "Found 1 pods" in result["message"]
        mock_manager.get_resources.assert_called_once_with("test-cluster", "pods", "default", None)

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_get_resources_with_options(self, mock_status, mock_kind, mock_kubectl):
        """Test resource retrieval with namespace and label selector."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.get_resources = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "resource_type": "pods",
                "namespace": "kube-system",
                "label_selector": "app=nginx",
                "resources": [],
                "count": 0,
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_get_resources(
            "test-cluster", "pods", namespace="kube-system", label_selector="app=nginx"
        )

        assert result["count"] == 0
        mock_manager.get_resources.assert_called_once_with(
            "test-cluster", "pods", "kube-system", "app=nginx"
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_get_resources_kubeconfig_not_found(
        self, mock_status, mock_kind, mock_kubectl
    ):
        """Test kubectl_get_resources with missing kubeconfig."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.get_resources = AsyncMock(
            side_effect=KubeconfigNotFoundError("Kubeconfig not found")
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_get_resources("test-cluster", "pods")

        assert result["success"] is False
        assert "error" in result
        assert "Kubeconfig not found" in result["message"]

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_apply_success(self, mock_status, mock_kind, mock_kubectl):
        """Test successful manifest application."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.apply_manifest = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "namespace": "default",
                "applied": True,
                "resources": ["deployment.apps/nginx created"],
                "output": "deployment.apps/nginx created",
            }
        )
        tools._kubectl_manager = mock_manager

        manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test"
        result = await tools.kubectl_apply("test-cluster", manifest)

        assert "message" in result
        assert result["applied"] is True
        assert "Successfully applied" in result["message"]
        mock_manager.apply_manifest.assert_called_once_with("test-cluster", manifest, "default")

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_apply_invalid_manifest(self, mock_status, mock_kind, mock_kubectl):
        """Test manifest application with invalid YAML."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.apply_manifest = AsyncMock(
            side_effect=InvalidManifestError("Invalid YAML manifest")
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_apply("test-cluster", "invalid yaml:")

        assert result["success"] is False
        assert "Invalid manifest" in result["message"]

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_delete_success(self, mock_status, mock_kind, mock_kubectl):
        """Test successful resource deletion."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.delete_resource = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "resource_type": "deployment",
                "name": "nginx",
                "namespace": "default",
                "deleted": True,
                "message": "Successfully deleted deployment/nginx",
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_delete("test-cluster", "deployment", "nginx")

        assert result["deleted"] is True
        mock_manager.delete_resource.assert_called_once_with(
            "test-cluster", "deployment", "nginx", "default", False
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_delete_with_force(self, mock_status, mock_kind, mock_kubectl):
        """Test forced resource deletion."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.delete_resource = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "resource_type": "pod",
                "name": "broken-pod",
                "namespace": "default",
                "deleted": True,
                "message": "Successfully deleted pod/broken-pod",
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_delete("test-cluster", "pod", "broken-pod", force=True)

        assert result["deleted"] is True
        mock_manager.delete_resource.assert_called_once_with(
            "test-cluster", "pod", "broken-pod", "default", True
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_logs_success(self, mock_status, mock_kind, mock_kubectl):
        """Test successful log retrieval."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.get_logs = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "pod_name": "test-pod",
                "namespace": "default",
                "container": None,
                "logs": "log line 1\nlog line 2",
                "lines": 2,
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_logs("test-cluster", "test-pod")

        assert "message" in result
        assert result["lines"] == 2
        assert "Retrieved 2 lines" in result["message"]
        mock_manager.get_logs.assert_called_once_with(
            "test-cluster", "test-pod", "default", None, 100, False
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_logs_with_container(self, mock_status, mock_kind, mock_kubectl):
        """Test log retrieval with specific container."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.get_logs = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "pod_name": "test-pod",
                "namespace": "default",
                "container": "app",
                "logs": "container logs",
                "lines": 1,
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_logs(
            "test-cluster", "test-pod", container="app", tail_lines=50
        )

        assert result["container"] == "app"
        mock_manager.get_logs.assert_called_once_with(
            "test-cluster", "test-pod", "default", "app", 50, False
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_logs_pod_not_found(self, mock_status, mock_kind, mock_kubectl):
        """Test log retrieval for non-existent pod."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.get_logs = AsyncMock(
            side_effect=ResourceNotFoundError("Pod 'test-pod' not found")
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_logs("test-cluster", "test-pod")

        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_describe_success(self, mock_status, mock_kind, mock_kubectl):
        """Test successful resource description."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.describe_resource = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "resource_type": "pod",
                "name": "nginx",
                "namespace": "default",
                "description": "Name: nginx\nStatus: Running",
            }
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_describe("test-cluster", "pod", "nginx")

        assert "message" in result
        assert "Retrieved description" in result["message"]
        mock_manager.describe_resource.assert_called_once_with(
            "test-cluster", "pod", "nginx", "default"
        )

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_describe_resource_not_found(self, mock_status, mock_kind, mock_kubectl):
        """Test describe resource that doesn't exist."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        mock_manager.describe_resource = AsyncMock(
            side_effect=ResourceNotFoundError("Resource pod/nginx not found")
        )
        tools._kubectl_manager = mock_manager

        result = await tools.kubectl_describe("test-cluster", "pod", "nginx")

        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    def test_kubectl_tools_in_cluster_tools_list(self, mock_status, mock_kind, mock_kubectl):
        """Test that kubectl tools are added to CLUSTER_TOOLS list."""
        assert tools.kubectl_get_resources in tools.CLUSTER_TOOLS
        assert tools.kubectl_apply in tools.CLUSTER_TOOLS
        assert tools.kubectl_delete in tools.CLUSTER_TOOLS
        assert tools.kubectl_logs in tools.CLUSTER_TOOLS
        assert tools.kubectl_describe in tools.CLUSTER_TOOLS

    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    def test_kubectl_tools_count(self, mock_status, mock_kind, mock_kubectl):
        """Test that CLUSTER_TOOLS has the expected number of tools."""
        # 5 cluster lifecycle tools + 5 kubectl tools = 10 total
        # Cluster: create, remove, list, status, health
        # Kubectl: get_resources, apply, delete, logs, describe
        assert len(tools.CLUSTER_TOOLS) == 10

    @pytest.mark.asyncio
    async def test_kubectl_tools_not_initialized(self):
        """Test that tools raise error when not initialized."""
        # tools._kubectl_manager is None

        with pytest.raises(RuntimeError) as exc_info:
            await tools.kubectl_get_resources("test-cluster", "pods")

        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("agent.cluster.tools.KubectlManager")
    @patch("agent.cluster.tools.KindManager")
    @patch("agent.cluster.tools.ClusterStatus")
    async def test_kubectl_tools_return_dicts_not_exceptions(
        self, mock_status, mock_kind, mock_kubectl
    ):
        """Test that kubectl tools always return dicts, never raise exceptions."""
        config = Mock(spec=AgentConfig)
        tools.initialize_tools(config)

        mock_manager = Mock()
        # Simulate various errors
        mock_manager.get_resources = AsyncMock(side_effect=KubeconfigNotFoundError("error"))
        mock_manager.apply_manifest = AsyncMock(side_effect=KubectlCommandError("error"))
        mock_manager.delete_resource = AsyncMock(side_effect=ClusterNotFoundError("error"))
        mock_manager.get_logs = AsyncMock(side_effect=ResourceNotFoundError("error"))
        mock_manager.describe_resource = AsyncMock(side_effect=Exception("unexpected"))
        tools._kubectl_manager = mock_manager

        # All should return dicts, not raise
        result1 = await tools.kubectl_get_resources("test", "pods")
        assert isinstance(result1, dict)
        assert "success" in result1 and result1["success"] is False

        result2 = await tools.kubectl_apply("test", "manifest")
        assert isinstance(result2, dict)
        assert "success" in result2 and result2["success"] is False

        result3 = await tools.kubectl_delete("test", "pod", "name")
        assert isinstance(result3, dict)
        assert "success" in result3 and result3["success"] is False

        result4 = await tools.kubectl_logs("test", "pod")
        assert isinstance(result4, dict)
        assert "success" in result4 and result4["success"] is False

        result5 = await tools.kubectl_describe("test", "pod", "name")
        assert isinstance(result5, dict)
        assert "success" in result5 and result5["success"] is False
