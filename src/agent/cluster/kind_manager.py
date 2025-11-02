"""KinD cluster management operations."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from agent.utils.errors import (
    ClusterAlreadyExistsError,
    ClusterAlreadyRunningError,
    ClusterNotFoundError,
    ClusterNotRunningError,
    KindCommandError,
)
from agent.utils.validation import validate_cluster_name, validate_k8s_version

logger = logging.getLogger(__name__)


class KindManager:
    """Manager for KinD cluster lifecycle operations."""

    def __init__(self):
        """Initialize KinD manager."""
        self._check_kind_available()

    def _check_kind_available(self) -> None:
        """Check if kind CLI is available.

        Raises:
            KindCommandError: If kind is not available
        """
        try:
            result = subprocess.run(
                ["kind", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise KindCommandError("kind CLI is not available or not working correctly")
            logger.debug(f"kind version: {result.stdout.strip()}")
        except FileNotFoundError as e:
            raise KindCommandError(
                "kind CLI not found. Please install kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise KindCommandError("kind version check timed out") from e

    def create_cluster(
        self,
        name: str,
        config: str,
        k8s_version: str | None = None,
    ) -> dict:
        """Create a new KinD cluster.

        Args:
            name: Cluster name
            config: Cluster configuration YAML
            k8s_version: Kubernetes version (e.g., v1.34.0)

        Returns:
            Dict with cluster information

        Raises:
            ClusterAlreadyExistsError: If cluster already exists
            KindCommandError: If cluster creation fails
        """
        validate_cluster_name(name)
        if k8s_version:
            validate_k8s_version(k8s_version)

        # Check if cluster already exists
        if self.cluster_exists(name):
            raise ClusterAlreadyExistsError(f"Cluster '{name}' already exists")

        # Write config to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config)
            config_path = f.name

        try:
            # Build command
            cmd = ["kind", "create", "cluster", "--name", name, "--config", config_path]
            if k8s_version:
                cmd.extend(["--image", f"kindest/node:{k8s_version}"])

            logger.info(f"Creating cluster '{name}' with config: {config_path}")

            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise KindCommandError(f"Failed to create cluster '{name}': {error_msg}")

            logger.info(f"Cluster '{name}' created successfully")

            # Get cluster info
            return {
                "cluster_name": name,
                "status": "running",
                "kubernetes_version": k8s_version or "latest",
                "nodes": self._get_node_count(name),
            }

        finally:
            # Clean up temporary config file
            Path(config_path).unlink(missing_ok=True)

    def delete_cluster(self, name: str) -> dict:
        """Delete a KinD cluster.

        Args:
            name: Cluster name

        Returns:
            Dict with deletion status

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
            KindCommandError: If deletion fails
        """
        validate_cluster_name(name)

        if not self.cluster_exists(name):
            raise ClusterNotFoundError(f"Cluster '{name}' not found")

        try:
            logger.info(f"Deleting cluster '{name}'")

            result = subprocess.run(
                ["kind", "delete", "cluster", "--name", name],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise KindCommandError(f"Failed to delete cluster '{name}': {error_msg}")

            logger.info(f"Cluster '{name}' deleted successfully")

            return {
                "success": True,
                "message": f"Cluster '{name}' deleted successfully",
            }

        except subprocess.TimeoutExpired as e:
            raise KindCommandError(f"Timeout while deleting cluster '{name}'") from e

    def list_clusters(self) -> list[str]:
        """List all KinD clusters.

        Returns:
            List of cluster names

        Raises:
            KindCommandError: If listing fails
        """
        try:
            result = subprocess.run(
                ["kind", "get", "clusters"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise KindCommandError(f"Failed to list clusters: {error_msg}")

            # Parse output - one cluster name per line
            clusters = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

            logger.debug(f"Found {len(clusters)} clusters")

            return clusters

        except subprocess.TimeoutExpired as e:
            raise KindCommandError("Timeout while listing clusters") from e

    def cluster_exists(self, name: str) -> bool:
        """Check if a cluster exists.

        Args:
            name: Cluster name

        Returns:
            True if cluster exists
        """
        try:
            clusters = self.list_clusters()
            return name in clusters
        except KindCommandError:
            return False

    def get_kubeconfig(self, name: str) -> str:
        """Get kubeconfig for a cluster.

        Args:
            name: Cluster name

        Returns:
            Kubeconfig YAML content

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
            KindCommandError: If getting kubeconfig fails
        """
        validate_cluster_name(name)

        if not self.cluster_exists(name):
            raise ClusterNotFoundError(f"Cluster '{name}' not found")

        try:
            result = subprocess.run(
                ["kind", "get", "kubeconfig", "--name", name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise KindCommandError(f"Failed to get kubeconfig for '{name}': {error_msg}")

            return result.stdout

        except subprocess.TimeoutExpired as e:
            raise KindCommandError(f"Timeout while getting kubeconfig for '{name}'") from e

    def start_cluster(self, name: str) -> dict:
        """Start a stopped KinD cluster.

        Args:
            name: Cluster name

        Returns:
            Dict with startup status and timing information

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
            ClusterAlreadyRunningError: If cluster is already running
            KindCommandError: If startup fails
        """
        validate_cluster_name(name)

        # Check if cluster containers exist
        if not self._container_exists(name):
            raise ClusterNotFoundError(f"Cluster '{name}' not found")

        # Check if already running
        if self._is_container_running(self._get_container_name(name)):
            raise ClusterAlreadyRunningError(f"Cluster '{name}' is already running")

        try:
            logger.info(f"Starting cluster '{name}'")
            import time

            start_time = time.time()

            # Get all containers for this cluster
            containers = self._get_all_containers(name)

            # Start all containers
            for container in containers:
                result = subprocess.run(
                    ["docker", "start", container],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout
                    raise KindCommandError(f"Failed to start container '{container}': {error_msg}")

            # Wait for Kubernetes API to be ready
            self._wait_for_api_ready(name, timeout=60)

            startup_time = time.time() - start_time
            logger.info(f"Cluster '{name}' started in {startup_time:.2f} seconds")

            return {
                "cluster_name": name,
                "status": "running",
                "startup_time_seconds": round(startup_time, 2),
                "message": f"Cluster '{name}' started successfully",
            }

        except subprocess.TimeoutExpired as e:
            raise KindCommandError(f"Timeout while starting cluster '{name}'") from e

    def stop_cluster(self, name: str) -> dict:
        """Stop a running KinD cluster without deleting it.

        Args:
            name: Cluster name

        Returns:
            Dict with stop status

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
            ClusterNotRunningError: If cluster is not running
            KindCommandError: If stopping fails
        """
        validate_cluster_name(name)

        # Check if cluster exists
        if not self._container_exists(name):
            raise ClusterNotFoundError(f"Cluster '{name}' not found")

        # Check if cluster is running
        if not self._is_container_running(self._get_container_name(name)):
            raise ClusterNotRunningError(f"Cluster '{name}' is not running")

        try:
            logger.info(f"Stopping cluster '{name}'")

            # Get all containers for this cluster
            containers = self._get_all_containers(name)

            # Stop all containers gracefully
            for container in containers:
                result = subprocess.run(
                    ["docker", "stop", container],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout
                    raise KindCommandError(f"Failed to stop container '{container}': {error_msg}")

            logger.info(f"Cluster '{name}' stopped successfully")

            return {
                "cluster_name": name,
                "status": "stopped",
                "message": f"Cluster '{name}' stopped successfully. Data preserved.",
            }

        except subprocess.TimeoutExpired as e:
            raise KindCommandError(f"Timeout while stopping cluster '{name}'") from e

    def restart_cluster(self, name: str) -> dict:
        """Restart a KinD cluster (stop + start).

        Args:
            name: Cluster name

        Returns:
            Dict with restart status

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
            KindCommandError: If restart fails
        """
        validate_cluster_name(name)

        if not self._container_exists(name):
            raise ClusterNotFoundError(f"Cluster '{name}' not found")

        try:
            logger.info(f"Restarting cluster '{name}'")

            # Stop if running
            if self._is_container_running(self._get_container_name(name)):
                stop_result = self.stop_cluster(name)
                logger.debug(f"Stop phase: {stop_result['message']}")

            # Start the cluster
            start_result = self.start_cluster(name)

            return {
                "cluster_name": name,
                "status": "running",
                "startup_time_seconds": start_result.get("startup_time_seconds", 0),
                "message": f"Cluster '{name}' restarted successfully",
            }

        except (ClusterNotRunningError, ClusterAlreadyRunningError):
            # Handle edge cases - just try to start
            return self.start_cluster(name)

    def _get_container_name(self, cluster_name: str) -> str:
        """Get the main container name for a cluster.

        Args:
            cluster_name: Cluster name

        Returns:
            Docker container name
        """
        return f"{cluster_name}-control-plane"

    def _get_all_containers(self, cluster_name: str) -> list[str]:
        """Get all container names for a cluster (control-plane + workers).

        Args:
            cluster_name: Cluster name

        Returns:
            List of Docker container names
        """
        try:
            # Find all containers with label for this KinD cluster
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"label=io.x-k8s.kind.cluster={cluster_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                containers = [line.strip() for line in result.stdout.strip().split("\n")]
                return containers

            # Fallback to control-plane only
            return [self._get_container_name(cluster_name)]

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Docker not available or timeout - fallback to control-plane only
            return [self._get_container_name(cluster_name)]

    def _container_exists(self, cluster_name: str) -> bool:
        """Check if cluster containers exist.

        Args:
            cluster_name: Cluster name

        Returns:
            True if containers exist
        """
        container_name = self._get_container_name(cluster_name)
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _is_container_running(self, container_name: str) -> bool:
        """Check if a Docker container is running.

        Args:
            container_name: Container name

        Returns:
            True if container is running
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Running}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return result.stdout.strip().lower() == "true"

            return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _wait_for_api_ready(self, name: str, timeout: int = 60) -> None:
        """Wait for Kubernetes API to be ready after starting cluster.

        Args:
            name: Cluster name
            timeout: Maximum time to wait in seconds

        Raises:
            KindCommandError: If API doesn't become ready in time
        """
        import time

        context = f"kind-{name}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["kubectl", "cluster-info", "--context", context],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    logger.debug(f"Kubernetes API ready for cluster '{name}'")
                    return

            except subprocess.TimeoutExpired:
                pass

            time.sleep(2)

        raise KindCommandError(
            f"Kubernetes API did not become ready within {timeout} seconds for cluster '{name}'"
        )

    def _get_node_count(self, name: str) -> int:
        """Get number of nodes in cluster.

        Args:
            name: Cluster name

        Returns:
            Number of nodes
        """
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "nodes",
                    "--context",
                    f"kind-{name}",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return len(data.get("items", []))

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(
                f"Failed to get node count for cluster '{name}': {type(e).__name__}: {e}"
            )

        return 0
