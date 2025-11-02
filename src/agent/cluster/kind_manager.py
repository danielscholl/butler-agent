"""KinD cluster management operations."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from agent.utils.errors import (
    ClusterAlreadyExistsError,
    ClusterNotFoundError,
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
