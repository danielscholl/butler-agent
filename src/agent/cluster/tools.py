"""Agent tools for cluster operations.

These functions are exposed as tools that the AI agent can use to manage KinD clusters.
"""

import logging
from typing import Any

from agent.cluster.config import get_cluster_config
from agent.cluster.kind_manager import KindManager
from agent.cluster.status import ClusterStatus
from agent.config import AgentConfig
from agent.utils.errors import (
    ClusterAlreadyExistsError,
    ClusterNotFoundError,
    KindCommandError,
)

logger = logging.getLogger(__name__)

# Global instances
_kind_manager: KindManager | None = None
_cluster_status: ClusterStatus | None = None
_config: AgentConfig | None = None


def initialize_tools(config: AgentConfig) -> None:
    """Initialize tools with configuration.

    Args:
        config: Butler configuration
    """
    global _kind_manager, _cluster_status, _config
    _config = config
    _kind_manager = KindManager()
    _cluster_status = ClusterStatus()


def create_cluster(
    name: str,
    config: str = "default",
    kubernetes_version: str | None = None,
) -> dict[str, Any]:
    """Create a new KinD cluster.

    This tool creates a new Kubernetes in Docker (KinD) cluster with the specified
    configuration. The cluster will be running locally and ready for deployment.

    Args:
        name: Name for the cluster (lowercase alphanumeric with hyphens)
        config: Configuration template to use: "minimal", "default", or "custom"
                (default: "default" - one control-plane and one worker node)
        kubernetes_version: Kubernetes version to use (e.g., "v1.34.0", default: latest)

    Returns:
        Dict containing:
        - cluster_name: Name of the created cluster
        - status: Cluster status ("running")
        - kubernetes_version: K8s version used
        - nodes: Number of nodes
        - kubeconfig_path: Path to kubeconfig file (if configured)
        - message: Success message

    Raises:
        ClusterAlreadyExistsError: If cluster with this name already exists
        KindCommandError: If cluster creation fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        # Get cluster configuration
        cluster_config = get_cluster_config(config, name)

        # Use configured default version if not specified
        k8s_version = kubernetes_version or _config.default_k8s_version

        logger.info(f"Creating cluster '{name}' with template '{config}', version {k8s_version}")

        # Create cluster
        result = _kind_manager.create_cluster(name, cluster_config, k8s_version)

        # Add kubeconfig path if data directory is configured
        if _config:
            result["kubeconfig_path"] = str(_config.get_kubeconfig_path(name))

        result["message"] = f"Cluster '{name}' created successfully with {result['nodes']} node(s)"

        return result

    except ClusterAlreadyExistsError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' already exists. Use a different name or delete the existing cluster first.",
        }
    except KindCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error creating cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error creating cluster: {e}",
        }


def delete_cluster(name: str, preserve_data: bool = True) -> dict[str, Any]:
    """Delete a KinD cluster.

    This tool deletes an existing KinD cluster. The cluster and all its resources
    will be permanently removed.

    Args:
        name: Name of the cluster to delete
        preserve_data: Whether to preserve cluster data directory (default: True)

    Returns:
        Dict containing:
        - success: Whether deletion was successful
        - message: Status message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        KindCommandError: If deletion fails
    """
    if not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Deleting cluster '{name}' (preserve_data={preserve_data})")

        result = _kind_manager.delete_cluster(name)

        # TODO: Handle data directory cleanup if preserve_data=False

        return result

    except ClusterNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' not found. Use list_clusters to see available clusters.",
        }
    except KindCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to delete cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error deleting cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error deleting cluster: {e}",
        }


def list_clusters() -> dict[str, Any]:
    """List all KinD clusters.

    This tool lists all existing KinD clusters on the system.

    Returns:
        Dict containing:
        - clusters: List of cluster names
        - total: Total number of clusters
        - message: Summary message
    """
    if not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info("Listing all clusters")

        clusters = _kind_manager.list_clusters()

        return {
            "clusters": clusters,
            "total": len(clusters),
            "message": (
                f"Found {len(clusters)} cluster(s)"
                if clusters
                else "No clusters found. Use create_cluster to create a new cluster."
            ),
        }

    except KindCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to list clusters: {e}",
        }
    except Exception as e:
        logger.exception("Unexpected error listing clusters")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error listing clusters: {e}",
        }


def cluster_status(name: str) -> dict[str, Any]:
    """Get detailed status for a cluster.

    This tool provides comprehensive status information about a cluster including
    node status, resource usage, and health checks.

    Args:
        name: Name of the cluster

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - status: Overall cluster status
        - nodes: List of nodes with their status
        - total_nodes: Total number of nodes
        - ready_nodes: Number of ready nodes
        - resource_usage: Resource usage information (if available)
        - message: Summary message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
    """
    if not _cluster_status or not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Getting status for cluster '{name}'")

        # Check if cluster exists
        if not _kind_manager.cluster_exists(name):
            return {
                "success": False,
                "error": f"Cluster '{name}' not found",
                "message": f"Cluster '{name}' not found. Use list_clusters to see available clusters.",
            }

        status = _cluster_status.get_cluster_status(name)
        status["message"] = (
            f"Cluster '{name}' is {status['status']} with "
            f"{status['ready_nodes']}/{status['total_nodes']} nodes ready"
        )

        return status

    except ClusterNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' not found or not accessible.",
        }
    except Exception as e:
        logger.exception(f"Unexpected error getting status for cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error getting cluster status: {e}",
        }


def get_cluster_health(name: str) -> dict[str, Any]:
    """Check health of a cluster.

    This tool performs health checks on a cluster including node readiness
    and system pod status.

    Args:
        name: Name of the cluster

    Returns:
        Dict containing:
        - healthy: Overall health status (boolean)
        - checks: List of health check results
        - message: Summary message
    """
    if not _cluster_status:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Checking health for cluster '{name}'")

        health = _cluster_status.check_cluster_health(name)
        health["message"] = f"Cluster '{name}' is {'healthy' if health['healthy'] else 'unhealthy'}"

        return health

    except Exception as e:
        logger.exception(f"Unexpected error checking health for cluster '{name}'")
        return {
            "healthy": False,
            "error": str(e),
            "message": f"Unexpected error checking cluster health: {e}",
        }


# Tool metadata for agent framework
CLUSTER_TOOLS = [
    create_cluster,
    delete_cluster,
    list_clusters,
    cluster_status,
    get_cluster_health,
]
