"""Agent tools for cluster operations.

These functions are exposed as tools that the AI agent can use to manage KinD clusters.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from agent.cluster.addons import AddonManager
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
    _kubectl_manager = KubectlManager(config)
    _cluster_status = ClusterStatus(config)


async def create_cluster(
    name: str,
    config: str = "default",
    kubernetes_version: str | None = None,
    addons: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new KinD cluster with optional add-ons.

    This tool creates a new Kubernetes in Docker (KinD) cluster with the specified
    configuration. The cluster will be running locally and ready for deployment.
    Optionally installs add-ons like NGINX Ingress Controller.

    Configuration discovery (automatic):
    1. Named custom: ./data/infra/kind-{config}.yaml (when config != minimal/default/custom)
    2. Default custom: ./data/infra/kind-config.yaml (when config = default/custom)
    3. Built-in templates: Fallback for minimal/default/custom

    Examples:
    - create_cluster("dev", "production") → looks for kind-production.yaml
    - create_cluster("app", "default") → looks for kind-config.yaml, falls back to built-in
    - create_cluster("test", "minimal") → uses built-in minimal template
    - create_cluster("dev", "default", addons=["ingress"]) → cluster with NGINX Ingress

    Available add-ons:
    - ingress: NGINX Ingress Controller for HTTP/HTTPS routing

    Args:
        name: Name for the cluster (lowercase alphanumeric with hyphens)
        config: Configuration template or custom config name
                Built-in templates: "minimal", "default", "custom"
                Custom configs: any name (will look for kind-{name}.yaml)
        kubernetes_version: Kubernetes version to use (e.g., "v1.34.0", default: latest)
        addons: Optional list of add-on names to install (e.g., ["ingress"])

    Returns:
        Dict containing:
        - cluster_name: Name of the created cluster
        - status: Cluster status ("running")
        - kubernetes_version: K8s version used
        - nodes: Number of nodes
        - kubeconfig_path: Path to kubeconfig file (if configured)
        - config_source: Description of which config was used
        - addons_installed: Dict of addon installation results (if addons specified)
        - message: Success message

    Raises:
        ClusterAlreadyExistsError: If cluster with this name already exists
        KindCommandError: If cluster creation fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        # Get cluster configuration with automatic discovery
        cluster_config_yaml, config_source = get_cluster_config(
            config, name, infra_dir=_config.get_infra_path(), data_dir=Path(_config.data_dir)
        )

        # Parse YAML string to dict for manipulation
        cluster_config = yaml.safe_load(cluster_config_yaml)

        # Use configured default version if not specified
        k8s_version = kubernetes_version or _config.default_k8s_version

        # PHASE 1: Collect and merge addon configuration requirements (pre-cluster creation)
        if addons:
            from agent.cluster.config_merge import merge_addon_requirements
            from agent.utils.port_checker import check_ingress_ports

            logger.info(f"Collecting configuration requirements from {len(addons)} addon(s)")

            # Temporary addon manager to get addon classes (no kubeconfig yet)
            temp_manager = AddonManager(name, Path("/tmp/placeholder"))

            # Check for ingress addon and port conflicts BEFORE expensive operations
            has_ingress = any(
                addon.lower() in ["ingress", "ingress-nginx", "nginx"] for addon in addons
            )
            if has_ingress:
                logger.info("Checking ingress port availability (80, 443)")
                port_status = check_ingress_ports()

                if not port_status["available"]:
                    conflicting_cluster = port_status.get("conflicting_cluster")
                    conflicts = port_status.get("conflicts", [])

                    # Build detailed error message for LLM to present naturally
                    conflict_details = []
                    for c in conflicts:
                        port_num = c["port"]
                        if c.get("cluster_name"):
                            conflict_details.append(
                                f"Port {port_num} is in use by Kind cluster '{c['cluster_name']}'"
                            )
                        elif c.get("container"):
                            conflict_details.append(
                                f"Port {port_num} is in use by Docker container '{c['container']}'"
                            )
                        else:
                            conflict_details.append(f"Port {port_num} is in use")

                    logger.warning(
                        f"Port conflict detected for ingress addon: {'; '.join(conflict_details)}"
                    )

                    # Build clear, actionable error message
                    if conflicting_cluster:
                        error_msg = (
                            f"Cannot create cluster '{name}' with ingress: "
                            f"ports 80/443 are in use by existing cluster '{conflicting_cluster}'. "
                            f"Options: (1) Delete '{conflicting_cluster}' first, "
                            f"(2) Create '{name}' without ingress addon, or "
                            f"(3) Use alternative ports like 8080/8443."
                        )
                    else:
                        error_msg = (
                            f"Cannot create cluster '{name}' with ingress: "
                            f"ports 80/443 are already in use. "
                            f"Free the ports or create without ingress addon."
                        )

                    return {
                        "success": False,
                        "error": "ingress_port_conflict",
                        "conflicting_cluster": conflicting_cluster,
                        "message": error_msg,
                    }

            addon_requirements = []
            for addon_name in addons:
                try:
                    # Resolve addon name to canonical form
                    canonical_name = temp_manager.resolve_addon_name(addon_name)

                    # Get temporary addon instance for config collection
                    # Note: kubeconfig path is ignored for pre-creation methods
                    temp_addon = temp_manager.get_addon_instance(canonical_name, None)

                    # Collect all requirements from this addon
                    addon_req = {}

                    # Cluster config requirements
                    config_req = temp_addon.get_cluster_config_requirements()
                    if config_req:
                        addon_req.update(config_req)

                    # Port requirements
                    port_req = temp_addon.get_port_requirements()
                    if port_req:
                        addon_req["port_mappings"] = port_req

                    # Node label requirements
                    label_req = temp_addon.get_node_labels()
                    if label_req:
                        addon_req["node_labels"] = label_req

                    if addon_req:
                        addon_requirements.append(addon_req)
                        logger.debug(f"Addon '{addon_name}' has configuration requirements")

                except Exception as e:
                    logger.warning(
                        f"Failed to collect config requirements from addon '{addon_name}': {e}"
                    )

            # Merge all addon requirements into cluster config
            if addon_requirements:
                cluster_config = merge_addon_requirements(cluster_config, addon_requirements)
                logger.info(
                    f"Merged configuration requirements from {len(addon_requirements)} addon(s)"
                )

        # Convert cluster config dict back to YAML string for kind_manager
        # Use safe_dump for security.
        # The argument sort_keys=False preserves the original key order from the merged config dict
        # (insertion order in Python 3.7+), making diffs more readable.
        cluster_config_yaml = yaml.safe_dump(
            cluster_config, default_flow_style=False, sort_keys=False
        )

        logger.info(
            f"Creating cluster '{name}' with config '{config}' ({config_source}), "
            f"version {k8s_version}"
        )

        # Create cluster with merged configuration
        result = await _kind_manager.create_cluster(name, cluster_config_yaml, k8s_version)

        # Export and save kubeconfig if data directory is configured
        if _config:
            try:
                kubeconfig_path = _config.get_kubeconfig_path(name)
                kubeconfig_path.parent.mkdir(parents=True, exist_ok=True)

                # Export kubeconfig from kind
                kubeconfig_content = await _kind_manager.get_kubeconfig(name)
                kubeconfig_path.write_text(kubeconfig_content)

                result["kubeconfig_path"] = str(kubeconfig_path)
                logger.info(f"Kubeconfig saved to {kubeconfig_path}")

                # Save config snapshot for future recreation
                config_snapshot_path = kubeconfig_path.parent / "kind-config.yaml"
                config_snapshot_path.write_text(cluster_config_yaml)
                logger.info(f"Config snapshot saved to {config_snapshot_path}")

            except (OSError, PermissionError, KindCommandError, ClusterNotFoundError) as e:
                logger.warning(f"Failed to save kubeconfig for cluster '{name}': {e}")
                # Don't fail cluster creation if kubeconfig save fails
                result["kubeconfig_path"] = None

        result["config_source"] = config_source
        # Don't set success=True yet - wait until all operations complete

        # PHASE 2: Install add-ons (post-cluster creation, only if kubeconfig saved successfully)
        if addons and result.get("kubeconfig_path"):
            logger.info(f"Installing {len(addons)} add-on(s): {', '.join(addons)}")
            addon_manager = AddonManager(name, Path(result["kubeconfig_path"]))
            addon_result = await addon_manager.install_addons(addons)

            result["addons_installed"] = addon_result

            # Update message and success based on addon installation
            if addon_result.get("success"):
                result["success"] = True
                result["message"] = (
                    f"Cluster '{name}' created successfully with {result['nodes']} node(s) "
                    f"using {config_source}. {addon_result['message']}"
                )
            else:
                result["success"] = True
                result["message"] = (
                    f"Cluster '{name}' created successfully with {result['nodes']} node(s) "
                    f"using {config_source}. Add-ons: {addon_result['message']}"
                )
                # Log warning about addon failures
                logger.warning(f"Some add-ons failed to install: {addon_result.get('failed', [])}")
        else:
            # No addons to install, cluster creation was successful
            result["success"] = True
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


async def delete_cluster(
    name: str, preserve_data: bool = False, confirmed: bool = False
) -> dict[str, Any]:
    """Delete a KinD cluster.

    This tool deletes an existing KinD cluster. The cluster and all its resources
    will be permanently removed. This is a destructive operation that requires
    user confirmation.

    Args:
        name: Name of the cluster to delete
        preserve_data: Whether to preserve cluster data directory (default: False)
        confirmed: Whether user has confirmed the deletion (default: False)

    Returns:
        Dict containing:
        - success: Whether deletion was successful
        - confirmation_required: If True, user confirmation needed
        - message: Status message

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        KindCommandError: If deletion fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    # Require confirmation for destructive operation
    if not confirmed:
        cluster_data_dir = _config.get_cluster_data_dir(name)
        return {
            "success": False,
            "confirmation_required": True,
            "cluster_name": name,
            "preserve_data": preserve_data,
            "message": f"Deleting cluster '{name}' is permanent. This will remove the cluster and "
            + ("preserve" if preserve_data else "delete")
            + f" data in {cluster_data_dir}/. Do you want to proceed?",
        }

    try:
        logger.info(f"Deleting cluster '{name}' (preserve_data={preserve_data})")

        result = await _kind_manager.delete_cluster(name)

        # Handle data directory cleanup if preserve_data=False
        if not preserve_data and _config:
            cluster_data_dir = _config.get_cluster_data_dir(name)
            if cluster_data_dir.exists():
                try:
                    import shutil

                    shutil.rmtree(cluster_data_dir)
                    logger.info(f"Deleted cluster data directory: {cluster_data_dir}")
                    result["data_deleted"] = True
                    result["message"] = (
                        f"Cluster '{name}' deleted successfully. "
                        f"Data directory removed: {cluster_data_dir}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete cluster data directory: {e}")
                    result["data_deleted"] = False
                    result["message"] = (
                        f"Cluster '{name}' deleted but failed to remove data directory: {e}"
                    )
            else:
                logger.debug(f"No data directory found for cluster '{name}'")
        else:
            result["data_deleted"] = False
            if preserve_data:
                result["message"] = (
                    f"Cluster '{name}' deleted successfully. "
                    f"Data preserved in {_config.get_cluster_data_dir(name)}"
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
            "message": f"Failed to delete cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error deleting cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error deleting cluster: {e}",
        }


async def list_clusters() -> dict[str, Any]:
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

        clusters = await _kind_manager.list_clusters()

        return {
            "success": True,
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


async def cluster_status(name: str) -> dict[str, Any]:
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
        if not await _kind_manager.cluster_exists(name):
            return {
                "success": False,
                "error": f"Cluster '{name}' not found",
                "message": f"Cluster '{name}' not found. Use list_clusters to see available clusters.",
            }

        status = _cluster_status.get_cluster_status(name)
        status["success"] = True
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
        health["success"] = True
        health["message"] = f"Cluster '{name}' is {'healthy' if health['healthy'] else 'unhealthy'}"

        return health

    except Exception as e:
        logger.exception(f"Unexpected error checking health for cluster '{name}'")
        return {
            "healthy": False,
            "error": str(e),
            "message": f"Unexpected error checking cluster health: {e}",
        }


async def start_cluster(name: str) -> dict[str, Any]:
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

        result = await _kind_manager.start_cluster(name)
        result["success"] = True
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


async def stop_cluster(name: str) -> dict[str, Any]:
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

        result = await _kind_manager.stop_cluster(name)
        result["success"] = True
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


async def restart_cluster(name: str) -> dict[str, Any]:
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

        result = await _kind_manager.restart_cluster(name)
        result["success"] = True
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


async def kubectl_get_resources(
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

        result = await _kubectl_manager.get_resources(
            cluster_name, resource_type, namespace, label_selector
        )

        result["success"] = True
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


async def kubectl_apply(
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

        result = await _kubectl_manager.apply_manifest(cluster_name, manifest, namespace)

        result["success"] = True
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


async def kubectl_delete(
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

        result = await _kubectl_manager.delete_resource(
            cluster_name, resource_type, name, namespace, force
        )

        result["success"] = True
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


async def kubectl_logs(
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

        result = await _kubectl_manager.get_logs(
            cluster_name, pod_name, namespace, container, tail_lines, previous
        )

        result["success"] = True
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


async def kubectl_describe(
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

        result = await _kubectl_manager.describe_resource(
            cluster_name, resource_type, name, namespace
        )

        result["success"] = True
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
