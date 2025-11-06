"""Agent tools for cluster operations.

These functions are exposed as tools that the AI agent can use to manage KinD clusters.
"""

import json
import logging
from datetime import datetime
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
    ClusterNotFoundError,
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


def _save_cluster_state(cluster_data_dir: Path, state: dict[str, Any]) -> None:
    """Save cluster state to JSON file.

    Args:
        cluster_data_dir: Cluster data directory
        state: State dictionary to save
    """
    cluster_data_dir.mkdir(parents=True, exist_ok=True)
    state_file = cluster_data_dir / "cluster-state.json"
    state_file.write_text(json.dumps(state, indent=2))
    logger.debug(f"Saved cluster state to {state_file}")


def _load_cluster_state(cluster_data_dir: Path) -> dict[str, Any] | None:
    """Load cluster state from JSON file.

    Args:
        cluster_data_dir: Cluster data directory

    Returns:
        State dictionary or None if file doesn't exist
    """
    state_file = cluster_data_dir / "cluster-state.json"
    if not state_file.exists():
        return None

    try:
        state: dict[str, Any] = json.loads(state_file.read_text())
        logger.debug(f"Loaded cluster state from {state_file}")
        return state
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load cluster state: {e}")
        return None


async def create_cluster(
    name: str,
    config: str | None = None,
    kubernetes_version: str | None = None,
    addons: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new cluster or restart a stopped one.

    Smart behavior based on cluster state:
    - **First-time creation**: If cluster data doesn't exist, creates new cluster with
      specified config/addons and saves state for future restarts.
    - **Restart from stopped**: If cluster data exists but cluster isn't running,
      recreates cluster from saved configuration and reinstalls addons. Ignores
      config/addons parameters (uses saved state).
    - **Already running**: Returns error if cluster is currently running.

    Configuration discovery (automatic for first-time creation):
    1. Cluster-specific: .local/clusters/{name}/kind-config.yaml (if pre-created)
    2. Built-in templates: minimal, default

    Examples:
    - create_cluster("dev") → first-time with default config
    - create_cluster("dev", "minimal") → first-time with minimal config
    - create_cluster("dev", addons=["ingress"]) → first-time with ingress
    - create_cluster("dev") → restart if dev was stopped (uses saved state)

    Available add-ons:
    - ingress: NGINX Ingress Controller for HTTP/HTTPS routing

    Args:
        name: Name for the cluster (lowercase alphanumeric with hyphens)
        config: Configuration template ("minimal" or "default") - only used for first-time
        kubernetes_version: Kubernetes version (e.g., "v1.34.0") - only for first-time
        addons: List of add-on names (e.g., ["ingress"]) - only for first-time

    Returns:
        Dict containing:
        - cluster_name: Name of the created cluster
        - status: Cluster status ("running")
        - kubernetes_version: K8s version used
        - nodes: Number of nodes
        - kubeconfig_path: Path to kubeconfig file
        - config_source: Description of which config was used
        - restarted: True if cluster was restarted from saved state
        - addons_installed: Dict of addon installation results (if addons present)
        - message: Success message

    Raises:
        RuntimeError: If tools not initialized
        KindCommandError: If cluster creation fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    cluster_data_dir = _config.get_cluster_data_dir(name)
    is_restart = cluster_data_dir.exists()

    try:
        # Check if cluster is already running
        if await _kind_manager.cluster_exists(name):
            return {
                "success": False,
                "error": "cluster_already_running",
                "message": f"Cluster '{name}' is already running. Use remove_cluster to stop it first if you want to recreate.",
            }

        # RESTART PATH: Recreate from saved state
        if is_restart:
            logger.info(f"Restarting cluster '{name}' from saved configuration")

            # Load saved state
            saved_state = _load_cluster_state(cluster_data_dir)
            if not saved_state:
                return {
                    "success": False,
                    "error": "missing_state",
                    "message": f"Cluster '{name}' data exists but state file is missing or corrupt. Cannot restart.",
                }

            # Load saved config
            saved_config_path = cluster_data_dir / "kind-config.yaml"
            if not saved_config_path.exists():
                return {
                    "success": False,
                    "error": "missing_config",
                    "message": f"Cluster '{name}' data exists but configuration file is missing. Cannot restart.",
                }

            cluster_config_yaml = saved_config_path.read_text()
            k8s_version = saved_state.get("kubernetes_version", _config.default_k8s_version)
            saved_addons = saved_state.get("addons", [])

            logger.info(f"Recreating cluster '{name}' with saved config, version {k8s_version}")

            # Create cluster from saved config
            result = await _kind_manager.create_cluster(name, cluster_config_yaml, k8s_version)

            # Export and save kubeconfig
            try:
                kubeconfig_path = _config.get_kubeconfig_path(name)
                kubeconfig_content = await _kind_manager.get_kubeconfig(name)
                kubeconfig_path.write_text(kubeconfig_content)
                result["kubeconfig_path"] = str(kubeconfig_path)
                logger.info(f"Kubeconfig saved to {kubeconfig_path}")
            except (OSError, PermissionError, KindCommandError, ClusterNotFoundError) as e:
                logger.warning(f"Failed to save kubeconfig: {e}")
                result["kubeconfig_path"] = None

            result["restarted"] = True
            result["config_source"] = "saved configuration"

            # Reinstall addons if they were configured
            if saved_addons and result.get("kubeconfig_path"):
                logger.info(
                    f"Reinstalling {len(saved_addons)} add-on(s): {', '.join(saved_addons)}"
                )
                addon_manager = AddonManager(name, Path(result["kubeconfig_path"]))
                addon_result = await addon_manager.install_addons(saved_addons)
                result["addons_installed"] = addon_result

                if addon_result.get("success"):
                    result["success"] = True
                    result["message"] = (
                        f"Cluster '{name}' restarted successfully with {result['nodes']} node(s). "
                        f"{addon_result['message']}"
                    )
                else:
                    result["success"] = True
                    result["message"] = (
                        f"Cluster '{name}' restarted successfully with {result['nodes']} node(s). "
                        f"Add-ons: {addon_result['message']}"
                    )
            else:
                result["success"] = True
                result["message"] = (
                    f"Cluster '{name}' restarted successfully with {result['nodes']} node(s) "
                    f"from saved configuration"
                )

            return result

        # FIRST-TIME CREATION PATH
        logger.info(f"Creating new cluster '{name}' (first-time)")

        # Use default config if not specified
        config = config or "default"

        # Get cluster configuration with automatic discovery
        cluster_config_yaml, config_source = get_cluster_config(
            config, name, data_dir=Path(_config.data_dir)
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
                            f"Options: (1) Remove '{conflicting_cluster}' first, "
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
        cluster_config_yaml = yaml.safe_dump(
            cluster_config, default_flow_style=False, sort_keys=False
        )

        logger.info(
            f"Creating cluster '{name}' with config '{config}' ({config_source}), "
            f"version {k8s_version}"
        )

        # Create cluster with merged configuration
        result = await _kind_manager.create_cluster(name, cluster_config_yaml, k8s_version)

        # Export and save kubeconfig
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

            # Save cluster state for restart
            cluster_state = {
                "addons": addons or [],
                "kubernetes_version": k8s_version,
                "config_template": config,
                "created_at": datetime.now().isoformat(),
            }
            _save_cluster_state(cluster_data_dir, cluster_state)
            logger.info("Cluster state saved")

        except (OSError, PermissionError, KindCommandError, ClusterNotFoundError) as e:
            logger.warning(f"Failed to save kubeconfig for cluster '{name}': {e}")
            result["kubeconfig_path"] = None

        result["config_source"] = config_source
        result["restarted"] = False

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
            "message": f"Cluster '{name}' already exists (internal error - should have been caught earlier).",
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


async def remove_cluster(
    name: str, purge_data: bool = False, confirmed: bool = False
) -> dict[str, Any]:
    """Remove a cluster, optionally purging all data.

    This tool stops a running cluster by removing its containers. By default,
    cluster configuration and data are preserved so the cluster can be restarted
    later with create_cluster.

    Behavior:
    - **Default (purge_data=False)**: Stops cluster, keeps data for restart. No confirmation needed.
    - **With purge_data=True**: Stops cluster AND deletes all data permanently. Requires confirmation.

    Args:
        name: Name of the cluster to remove
        purge_data: If False (default), stops cluster and preserves data.
                   If True, stops cluster AND deletes all data (requires confirmation).
        confirmed: User confirmation flag (auto-set by agent for purge operations)

    Returns:
        Dict containing:
        - success: Whether removal was successful
        - confirmation_required: If True, user confirmation needed (purge_data=True only)
        - data_deleted: Whether data was deleted
        - message: Status message

    Examples:
        - remove_cluster("dev") → stops dev, keeps data for restart
        - remove_cluster("test", purge_data=True) → asks for confirmation first
        - remove_cluster("test", purge_data=True, confirmed=True) → deletes test and all data

    Raises:
        ClusterNotFoundError: If cluster doesn't exist
        KindCommandError: If removal fails
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    # Require confirmation ONLY if purging data
    if purge_data and not confirmed:
        cluster_data_dir = _config.get_cluster_data_dir(name)
        return {
            "success": False,
            "confirmation_required": True,
            "cluster_name": name,
            "purge_data": True,
            "message": (
                f"This will permanently delete cluster '{name}' and ALL data in {cluster_data_dir}/. "
                f"The cluster cannot be restarted after purging. Do you want to proceed?"
            ),
        }

    try:
        # Check if cluster exists (either running or stopped with data)
        cluster_running = await _kind_manager.cluster_exists(name)
        cluster_data_dir = _config.get_cluster_data_dir(name)
        cluster_data_exists = cluster_data_dir.exists()

        if not cluster_running and not cluster_data_exists:
            return {
                "success": False,
                "error": "cluster_not_found",
                "message": f"Cluster '{name}' not found (no running cluster or saved data). Use list_clusters to see available clusters.",
            }

        # Stop cluster if running
        if cluster_running:
            logger.info(f"Stopping cluster '{name}' (purge_data={purge_data})")
            result = await _kind_manager.delete_cluster(name)
        else:
            logger.info(f"Cluster '{name}' not running, proceeding with data cleanup if requested")
            result = {"success": True, "cluster_name": name}

        # Handle data directory cleanup if purge_data=True
        if purge_data:
            if cluster_data_exists:
                try:
                    import shutil

                    shutil.rmtree(cluster_data_dir)
                    logger.info(f"Purged cluster data directory: {cluster_data_dir}")
                    result["data_deleted"] = True
                    result["message"] = (
                        f"Cluster '{name}' removed and all data permanently deleted."
                    )
                except Exception as e:
                    logger.error(f"Failed to purge cluster data directory: {e}")
                    result["data_deleted"] = False
                    result["success"] = False
                    result["message"] = (
                        f"Cluster '{name}' stopped but failed to purge data directory: {e}"
                    )
            else:
                result["data_deleted"] = False
                result["message"] = f"Cluster '{name}' removed (no data directory found to purge)."
        else:
            # Default: preserve data for restart
            result["data_deleted"] = False
            if cluster_data_exists:
                result["message"] = (
                    f"Cluster '{name}' stopped. Configuration saved in {cluster_data_dir}. "
                    f"Use create_cluster('{name}') to restart."
                )
            else:
                result["message"] = f"Cluster '{name}' removed (no configuration data found)."

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
            "message": f"Failed to remove cluster '{name}': {e}",
        }
    except Exception as e:
        logger.exception(f"Unexpected error removing cluster '{name}'")
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error removing cluster: {e}",
        }


async def list_clusters() -> dict[str, Any]:
    """List all clusters (running and stopped).

    This tool lists all clusters on the system, showing which are currently
    running and which are stopped (have saved configuration but aren't running).

    Running clusters: Currently active in Docker
    Stopped clusters: Have saved data in .local/clusters/ but containers removed

    Returns:
        Dict containing:
        - running: List of running cluster names
        - stopped: List of stopped cluster names (can be restarted)
        - total: Total number of clusters (running + stopped)
        - message: Summary message

    Examples:
        {"running": ["dev", "staging"], "stopped": ["test"], "total": 3}
        {"running": [], "stopped": ["old-cluster"], "total": 1}
    """
    if not _kind_manager or not _config:
        raise RuntimeError("Tools not initialized. Call initialize_tools() first.")

    try:
        logger.info("Listing all clusters")

        # Get running clusters from kind
        running_clusters = await _kind_manager.list_clusters()

        # Get stopped clusters by checking data directories
        stopped_clusters = []
        clusters_dir = Path(_config.data_dir) / "clusters"
        if clusters_dir.exists():
            for cluster_dir in clusters_dir.iterdir():
                if cluster_dir.is_dir():
                    cluster_name = cluster_dir.name
                    # Only include if not currently running
                    if cluster_name not in running_clusters:
                        # Verify it has valid cluster data (state file or config)
                        has_state = (cluster_dir / "cluster-state.json").exists()
                        has_config = (cluster_dir / "kind-config.yaml").exists()
                        if has_state or has_config:
                            stopped_clusters.append(cluster_name)

        total = len(running_clusters) + len(stopped_clusters)

        # Build summary message
        if total == 0:
            message = "No clusters found. Use create_cluster to create a new cluster."
        else:
            parts = []
            if running_clusters:
                parts.append(f"{len(running_clusters)} running")
            if stopped_clusters:
                parts.append(f"{len(stopped_clusters)} stopped")
            message = f"Found {total} cluster(s): {', '.join(parts)}"

        return {
            "success": True,
            "running": running_clusters,
            "stopped": stopped_clusters,
            "total": total,
            "message": message,
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
    remove_cluster,
    list_clusters,
    cluster_status,
    get_cluster_health,
    kubectl_get_resources,
    kubectl_apply,
    kubectl_delete,
    kubectl_logs,
    kubectl_describe,
]
