"""Agent tools for cluster operations.

These functions are exposed as tools that the AI agent can use to manage KinD clusters.
"""

import logging
from typing import Any

from agent.cluster.config import get_cluster_config
from agent.cluster.kind_manager import KindManager
from agent.cluster.kubectl_manager import KubectlManager
from agent.cluster.status import ClusterStatus
from agent.config import AgentConfig
from agent.utils.errors import (
    ClusterAlreadyExistsError,
    ClusterAlreadyRunningError,
    ClusterNotFoundError,
    ClusterNotRunningError,
    InvalidManifestError,
    KindCommandError,
    KubeconfigNotFoundError,
    KubectlCommandError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)

# Global instances
_kind_manager: KindManager | None = None
_kubectl_manager: KubectlManager | None = None
_cluster_status: ClusterStatus | None = None
_config: AgentConfig | None = None


def initialize_tools(config: AgentConfig) -> None:
    """Initialize tools with configuration.

    Args:
        config: Butler configuration
    """
    global _kind_manager, _kubectl_manager, _cluster_status, _config
    _config = config
    _kind_manager = KindManager()
    _kubectl_manager = KubectlManager()
    _cluster_status = ClusterStatus()


def create_cluster(
    name: str,
    config: str = "default",
    kubernetes_version: str | None = None,
) -> dict[str, Any]:
    """Create a new KinD cluster.

    This tool creates a new Kubernetes in Docker (KinD) cluster with the specified
    configuration. The cluster will be running locally and ready for deployment.

    Configuration discovery (automatic):
    1. Named custom: ./data/infra/kind-{config}.yaml (when config != minimal/default/custom)
    2. Default custom: ./data/infra/kind-config.yaml (when config = default/custom)
    3. Built-in templates: Fallback for minimal/default/custom

    Examples:
    - create_cluster("dev", "production") → looks for kind-production.yaml
    - create_cluster("app", "default") → looks for kind-config.yaml, falls back to built-in
    - create_cluster("test", "minimal") → uses built-in minimal template

    Args:
        name: Name for the cluster (lowercase alphanumeric with hyphens)
        config: Configuration template or custom config name
                Built-in templates: "minimal", "default", "custom"
                Custom configs: any name (will look for kind-{name}.yaml)
        kubernetes_version: Kubernetes version to use (e.g., "v1.34.0", default: latest)

    Returns:
        Dict containing:
        - cluster_name: Name of the created cluster
        - status: Cluster status ("running")
        - kubernetes_version: K8s version used
        - nodes: Number of nodes
        - kubeconfig_path: Path to kubeconfig file (if configured)
        - config_source: Description of which config was used
        - message: Success message

    Raises:
        ClusterAlreadyExistsError: If cluster with this name already exists
        KindCommandError: If cluster creation fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        # Get cluster configuration with automatic discovery
        cluster_config, config_source = get_cluster_config(
            config, name, infra_dir=_config.get_infra_path()
        )

        # Use configured default version if not specified
        k8s_version = kubernetes_version or _config.default_k8s_version

        logger.info(
            f"Creating cluster '{name}' with config '{config}' ({config_source}), "
            f"version {k8s_version}"
        )

        # Create cluster
        result = _kind_manager.create_cluster(name, cluster_config, k8s_version)

        # Add kubeconfig path if data directory is configured
        if _config:
            result["kubeconfig_path"] = str(_config.get_kubeconfig_path(name))

        result["config_source"] = config_source
        result["message"] = (
            f"Cluster '{name}' created successfully with {result['nodes']} node(s) "
            f"using {config_source}"
        )

        return result

    except ClusterAlreadyExistsError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' already exists. Use a different name or delete the existing cluster first.",
        }
    except (FileNotFoundError, ValueError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Configuration error: {e}",
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


def start_cluster(name: str) -> dict[str, Any]:
    """Start a stopped KinD cluster.

    This tool starts a previously stopped cluster without recreating it.
    The cluster resumes with all its previous state and data intact.
    This is useful for saving resources when not actively developing.

    Args:
        name: Name of the cluster to start

    Returns:
        Dict containing:
        - cluster_name: Name of the cluster
        - status: Cluster status ("running")
        - startup_time_seconds: Time taken to start
        - message: Success message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        ClusterAlreadyRunningError: If cluster is already running
        KindCommandError: If startup fails
    """
    if not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Starting cluster '{name}'")

        result = _kind_manager.start_cluster(name)
        result["message"] = (
            f"Cluster '{name}' started successfully in {result['startup_time_seconds']} seconds"
        )

        return result

    except ClusterNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' not found. Use list_clusters to see available clusters.",
        }
    except ClusterAlreadyRunningError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' is already running.",
        }
    except KindCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to start cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error starting cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error starting cluster: {e}",
        }


def stop_cluster(name: str) -> dict[str, Any]:
    """Stop a running KinD cluster without deleting it.

    This tool stops a cluster to save resources while preserving all data
    and configuration. The cluster can be restarted later with start_cluster.
    Use this when you want to pause development without losing your work.

    Note: This is different from delete_cluster - stopped clusters preserve
    all state and can be restarted quickly.

    Args:
        name: Name of the cluster to stop

    Returns:
        Dict containing:
        - cluster_name: Name of the cluster
        - status: Cluster status ("stopped")
        - message: Success message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        ClusterNotRunningError: If cluster is not running
        KindCommandError: If stopping fails
    """
    if not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Stopping cluster '{name}'")

        result = _kind_manager.stop_cluster(name)
        result["message"] = (
            f"Cluster '{name}' stopped successfully. Data preserved. "
            f"Use start_cluster to resume."
        )

        return result

    except ClusterNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' not found. Use list_clusters to see available clusters.",
        }
    except ClusterNotRunningError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Cluster '{name}' is not running.",
        }
    except KindCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to stop cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error stopping cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error stopping cluster: {e}",
        }


def restart_cluster(name: str) -> dict[str, Any]:
    """Restart a KinD cluster (stop + start cycle).

    This tool performs a quick restart of a cluster, useful during
    development iteration when you need to reset the cluster state
    or apply configuration changes. Faster than delete + recreate.

    Args:
        name: Name of the cluster to restart

    Returns:
        Dict containing:
        - cluster_name: Name of the cluster
        - status: Cluster status ("running")
        - startup_time_seconds: Time taken to restart
        - message: Success message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        KindCommandError: If restart fails
    """
    if not _kind_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Restarting cluster '{name}'")

        result = _kind_manager.restart_cluster(name)
        result["message"] = (
            f"Cluster '{name}' restarted successfully in "
            f"{result['startup_time_seconds']} seconds"
        )

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
            "message": f"Failed to restart cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error restarting cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error restarting cluster: {e}",
        }


def kubectl_get_resources(
    cluster_name: str,
    resource_type: str,
    namespace: str = "default",
    label_selector: str | None = None,
) -> dict[str, Any]:
    """Get Kubernetes resources from a cluster.

    This tool queries Kubernetes resources (pods, services, deployments, etc.) from
    a KinD cluster. Use this to inspect what's running in your cluster, check
    resource status, or filter by labels.

    Common resource types:
    - pods: Running application instances
    - services: Network services exposing pods
    - deployments: Declarative pod deployments
    - namespaces: Virtual clusters for resource isolation
    - configmaps: Configuration data
    - secrets: Sensitive configuration data
    - nodes: Cluster nodes

    Args:
        cluster_name: Name of the cluster to query
        resource_type: Type of resource to get (pods, services, deployments, etc.)
        namespace: Kubernetes namespace (default: "default")
        label_selector: Optional label selector (e.g., "app=nginx")

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - resource_type: Resource type queried
        - namespace: Namespace queried
        - resources: List of resources (JSON format)
        - count: Number of resources found
        - message: Summary message

    Examples:
        - kubectl_get_resources("dev", "pods")
        - kubectl_get_resources("staging", "services", namespace="kube-system")
        - kubectl_get_resources("prod", "pods", label_selector="app=nginx")
    """
    if not _kubectl_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(
            f"Getting {resource_type} from cluster '{cluster_name}', namespace '{namespace}'"
        )

        result = _kubectl_manager.get_resources(
            cluster_name, resource_type, namespace, label_selector
        )

        result["message"] = (
            f"Found {result['count']} {resource_type} in cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        return result

    except (KubeconfigNotFoundError, ClusterNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except KubectlCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to get {resource_type}: {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error getting {resource_type} from cluster '{cluster_name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error getting resources: {e}",
        }


def kubectl_apply(
    cluster_name: str,
    manifest: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """Apply a Kubernetes manifest to a cluster.

    This tool deploys applications and resources to a cluster by applying
    Kubernetes YAML manifests. Use this to deploy applications, create services,
    or apply any Kubernetes configuration.

    Args:
        cluster_name: Name of the cluster to apply to
        manifest: YAML manifest content to apply
        namespace: Kubernetes namespace (default: "default")

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - namespace: Namespace where resources were created
        - applied: Whether apply was successful
        - resources: List of created/updated resources
        - output: kubectl apply output
        - message: Summary message

    Examples:
        - kubectl_apply("dev", nginx_deployment_yaml)
        - kubectl_apply("staging", service_yaml, namespace="apps")
    """
    if not _kubectl_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Applying manifest to cluster '{cluster_name}', namespace '{namespace}'")

        result = _kubectl_manager.apply_manifest(cluster_name, manifest, namespace)

        result["message"] = (
            f"Successfully applied {len(result['resources'])} resource(s) to "
            f"cluster '{cluster_name}', namespace '{namespace}'"
        )

        return result

    except (KubeconfigNotFoundError, ClusterNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except InvalidManifestError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Invalid manifest: {e}",
        }
    except KubectlCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to apply manifest: {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error applying manifest to cluster '{cluster_name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error applying manifest: {e}",
        }


def kubectl_delete(
    cluster_name: str,
    resource_type: str,
    name: str,
    namespace: str = "default",
    force: bool = False,
) -> dict[str, Any]:
    """Delete a Kubernetes resource from a cluster.

    This tool removes specific resources from a cluster. Use this to clean up
    deployments, services, pods, or any other Kubernetes resources.

    Args:
        cluster_name: Name of the cluster
        resource_type: Type of resource (pod, service, deployment, etc.)
        name: Name of the resource to delete
        namespace: Kubernetes namespace (default: "default")
        force: Force deletion with zero grace period (default: False)

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - resource_type: Resource type deleted
        - name: Resource name
        - namespace: Namespace
        - deleted: Whether resource was deleted
        - message: Status message

    Examples:
        - kubectl_delete("dev", "deployment", "nginx")
        - kubectl_delete("staging", "service", "api", namespace="apps")
        - kubectl_delete("prod", "pod", "broken-pod", force=True)
    """
    if not _kubectl_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(
            f"Deleting {resource_type}/{name} from cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        result = _kubectl_manager.delete_resource(
            cluster_name, resource_type, name, namespace, force
        )

        return result

    except (KubeconfigNotFoundError, ClusterNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except KubectlCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to delete {resource_type}/{name}: {e}",
        }
    except Exception as e:
        logger.exception(
            f"Unexpected error deleting {resource_type}/{name} from cluster '{cluster_name}'"
        )
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error deleting resource: {e}",
        }


def kubectl_logs(
    cluster_name: str,
    pod_name: str,
    namespace: str = "default",
    container: str | None = None,
    tail_lines: int = 100,
    previous: bool = False,
) -> dict[str, Any]:
    """Get logs from a pod for debugging.

    This tool retrieves container logs from pods in a cluster. Use this to
    debug application issues, view output, or troubleshoot failures.

    Args:
        cluster_name: Name of the cluster
        pod_name: Name of the pod
        namespace: Kubernetes namespace (default: "default")
        container: Container name (required for multi-container pods)
        tail_lines: Number of recent lines to retrieve (default: 100)
        previous: Get logs from previous container instance (default: False)

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - pod_name: Pod name
        - namespace: Namespace
        - container: Container name (if specified)
        - logs: Log output
        - lines: Number of log lines
        - message: Summary message

    Examples:
        - kubectl_logs("dev", "nginx-pod")
        - kubectl_logs("staging", "api-pod", container="app", tail_lines=200)
        - kubectl_logs("prod", "crashed-pod", previous=True)
    """
    if not _kubectl_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(f"Getting logs from pod '{pod_name}' in cluster '{cluster_name}'")

        result = _kubectl_manager.get_logs(
            cluster_name, pod_name, namespace, container, tail_lines, previous
        )

        result["message"] = (
            f"Retrieved {result['lines']} lines of logs from pod '{pod_name}' "
            f"in cluster '{cluster_name}', namespace '{namespace}'"
        )

        return result

    except (KubeconfigNotFoundError, ClusterNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except ResourceNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except KubectlCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to get logs from pod '{pod_name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error getting logs from pod '{pod_name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error getting logs: {e}",
        }


def kubectl_describe(
    cluster_name: str,
    resource_type: str,
    name: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """Describe a Kubernetes resource in detail.

    This tool provides comprehensive information about a resource including
    its configuration, status, events, and more. Use this to debug issues,
    understand resource configuration, or view detailed status.

    Args:
        cluster_name: Name of the cluster
        resource_type: Type of resource (pod, service, deployment, etc.)
        name: Name of the resource
        namespace: Kubernetes namespace (default: "default")

    Returns:
        Dict containing:
        - cluster_name: Cluster name
        - resource_type: Resource type
        - name: Resource name
        - namespace: Namespace
        - description: Detailed resource description (includes events)
        - message: Summary message

    Examples:
        - kubectl_describe("dev", "pod", "nginx-abc123")
        - kubectl_describe("staging", "deployment", "api")
        - kubectl_describe("prod", "service", "web", namespace="apps")
    """
    if not _kubectl_manager:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info(
            f"Describing {resource_type}/{name} in cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        result = _kubectl_manager.describe_resource(cluster_name, resource_type, name, namespace)

        result["message"] = (
            f"Retrieved description for {resource_type}/{name} in cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        return result

    except (KubeconfigNotFoundError, ClusterNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except ResourceNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": str(e),
        }
    except KubectlCommandError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to describe {resource_type}/{name}: {e}",
        }
    except Exception as e:
        logger.exception(
            f"Unexpected error describing {resource_type}/{name} in cluster '{cluster_name}'"
        )
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error describing resource: {e}",
        }


# Tool metadata for agent framework
CLUSTER_TOOLS = [
    create_cluster,
    delete_cluster,
    list_clusters,
    cluster_status,
    get_cluster_health,
    start_cluster,
    stop_cluster,
    restart_cluster,
    kubectl_get_resources,
    kubectl_apply,
    kubectl_delete,
    kubectl_logs,
    kubectl_describe,
]
