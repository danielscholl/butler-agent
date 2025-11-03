"""Kubectl resource management operations."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import yaml

from agent.utils.errors import (
    ClusterNotFoundError,
    InvalidManifestError,
    KubeconfigNotFoundError,
    KubectlCommandError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


class KubectlManager:
    """Manager for kubectl operations on Kubernetes clusters."""

    def __init__(self):
        """Initialize kubectl manager."""
        self._check_kubectl_available()

    def _check_kubectl_available(self) -> None:
        """Check if kubectl CLI is available.

        Raises:
            KubectlCommandError: If kubectl is not available
        """
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise KubectlCommandError("kubectl CLI is not available or not working correctly")
            logger.debug(f"kubectl version: {result.stdout.strip()}")
        except FileNotFoundError as e:
            raise KubectlCommandError(
                "kubectl CLI not found. Please install kubectl: "
                "https://kubernetes.io/docs/tasks/tools/install-kubectl/"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise KubectlCommandError("kubectl version check timed out") from e

    def _get_kubeconfig_path(self, cluster_name: str) -> Path:
        """Get kubeconfig path for a cluster.

        Args:
            cluster_name: Cluster name

        Returns:
            Path to kubeconfig file
        """
        return Path(f"./data/{cluster_name}/kubeconfig")

    def _validate_kubeconfig(self, cluster_name: str) -> Path:
        """Validate kubeconfig exists and cluster is accessible.

        Args:
            cluster_name: Cluster name

        Returns:
            Path to validated kubeconfig file

        Raises:
            KubeconfigNotFoundError: If kubeconfig file doesn't exist
            ClusterNotFoundError: If cluster is not accessible
        """
        kubeconfig_path = self._get_kubeconfig_path(cluster_name)

        if not kubeconfig_path.exists():
            raise KubeconfigNotFoundError(
                f"Kubeconfig not found for cluster '{cluster_name}'. "
                f"Expected at: {kubeconfig_path}"
            )

        # Verify cluster is accessible
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise ClusterNotFoundError(
                    f"Cluster '{cluster_name}' is not accessible. It may be stopped or deleted. Try starting it first."
                )
        except subprocess.TimeoutExpired as e:
            raise ClusterNotFoundError(
                f"Timeout connecting to cluster '{cluster_name}'. The cluster may be stopped."
            ) from e

        return kubeconfig_path

    def _run_kubectl(
        self, args: list[str], kubeconfig_path: Path, timeout: int = 30
    ) -> subprocess.CompletedProcess[str]:
        """Run kubectl command with kubeconfig.

        Args:
            args: Command arguments
            kubeconfig_path: Path to kubeconfig file
            timeout: Command timeout in seconds

        Returns:
            Completed subprocess

        Raises:
            KubectlCommandError: If command fails
        """
        cmd = ["kubectl", "--kubeconfig", str(kubeconfig_path)] + args
        logger.debug(f"Running kubectl command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result

        except subprocess.TimeoutExpired as e:
            raise KubectlCommandError(f"kubectl command timed out after {timeout} seconds") from e
        except FileNotFoundError as e:
            raise KubectlCommandError("kubectl CLI not found in PATH") from e

    def get_resources(
        self,
        cluster_name: str,
        resource_type: str,
        namespace: str = "default",
        label_selector: str | None = None,
    ) -> dict:
        """Get Kubernetes resources by type.

        Args:
            cluster_name: Cluster name
            resource_type: Resource type (pods, services, deployments, etc.)
            namespace: Kubernetes namespace (default: "default")
            label_selector: Optional label selector (e.g., "app=nginx")

        Returns:
            Dict with resource information

        Raises:
            KubeconfigNotFoundError: If kubeconfig not found
            ClusterNotFoundError: If cluster not accessible
            KubectlCommandError: If kubectl command fails
        """
        kubeconfig_path = self._validate_kubeconfig(cluster_name)

        # Build command
        args = ["get", resource_type, "-n", namespace, "-o", "json"]
        if label_selector:
            args.extend(["-l", label_selector])

        result = self._run_kubectl(args, kubeconfig_path)

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise KubectlCommandError(
                f"Failed to get {resource_type} in cluster '{cluster_name}': {error_msg}"
            )

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
            items = data.get("items", [])

            logger.info(
                f"Found {len(items)} {resource_type} in cluster '{cluster_name}', "
                f"namespace '{namespace}'"
            )

            return {
                "cluster_name": cluster_name,
                "resource_type": resource_type,
                "namespace": namespace,
                "label_selector": label_selector,
                "resources": items,
                "count": len(items),
            }

        except json.JSONDecodeError as e:
            raise KubectlCommandError(f"Failed to parse kubectl output as JSON: {e}") from e

    def apply_manifest(
        self,
        cluster_name: str,
        manifest: str,
        namespace: str = "default",
    ) -> dict:
        """Apply Kubernetes manifest to cluster.

        Args:
            cluster_name: Cluster name
            manifest: YAML/JSON manifest content
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Dict with apply result

        Raises:
            KubeconfigNotFoundError: If kubeconfig not found
            ClusterNotFoundError: If cluster not accessible
            InvalidManifestError: If manifest is invalid
            KubectlCommandError: If kubectl command fails
        """
        kubeconfig_path = self._validate_kubeconfig(cluster_name)

        # Validate manifest is valid YAML
        try:
            yaml.safe_load(manifest)
        except yaml.YAMLError as e:
            raise InvalidManifestError(f"Invalid YAML manifest: {e}") from e

        # Write manifest to temporary file
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write(manifest)
                temp_file = f.name

            # Apply manifest
            args = ["apply", "-f", temp_file, "-n", namespace]
            result = self._run_kubectl(args, kubeconfig_path, timeout=60)

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise KubectlCommandError(
                    f"Failed to apply manifest to cluster '{cluster_name}': {error_msg}"
                )

            # Parse output to extract resource names
            output_lines = result.stdout.strip().split("\n")
            resources = [line.strip() for line in output_lines if line.strip()]

            logger.info(
                f"Applied manifest to cluster '{cluster_name}', namespace '{namespace}': "
                f"{len(resources)} resources"
            )

            return {
                "cluster_name": cluster_name,
                "namespace": namespace,
                "applied": True,
                "resources": resources,
                "output": result.stdout,
            }

        finally:
            # Clean up temporary file
            if temp_file:
                Path(temp_file).unlink(missing_ok=True)

    def delete_resource(
        self,
        cluster_name: str,
        resource_type: str,
        name: str,
        namespace: str = "default",
        force: bool = False,
    ) -> dict:
        """Delete a Kubernetes resource.

        Args:
            cluster_name: Cluster name
            resource_type: Resource type (pod, service, deployment, etc.)
            name: Resource name
            namespace: Kubernetes namespace (default: "default")
            force: Force deletion with zero grace period

        Returns:
            Dict with deletion status

        Raises:
            KubeconfigNotFoundError: If kubeconfig not found
            ClusterNotFoundError: If cluster not accessible
            KubectlCommandError: If kubectl command fails
        """
        kubeconfig_path = self._validate_kubeconfig(cluster_name)

        # Build command
        args = ["delete", resource_type, name, "-n", namespace]
        if force:
            args.extend(["--grace-period=0", "--force"])

        result = self._run_kubectl(args, kubeconfig_path, timeout=60)

        # Resource not found is not an error (idempotent delete)
        if result.returncode != 0:
            if "NotFound" in result.stderr or "not found" in result.stderr.lower():
                logger.info(
                    f"Resource {resource_type}/{name} not found in cluster '{cluster_name}', "
                    f"namespace '{namespace}' (already deleted)"
                )
                return {
                    "cluster_name": cluster_name,
                    "resource_type": resource_type,
                    "name": name,
                    "namespace": namespace,
                    "deleted": False,
                    "message": f"Resource {resource_type}/{name} not found (already deleted)",
                }

            # Other errors are real failures
            error_msg = result.stderr or result.stdout
            raise KubectlCommandError(
                f"Failed to delete {resource_type}/{name} from cluster '{cluster_name}': {error_msg}"
            )

        logger.info(
            f"Deleted {resource_type}/{name} from cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        return {
            "cluster_name": cluster_name,
            "resource_type": resource_type,
            "name": name,
            "namespace": namespace,
            "deleted": True,
            "message": f"Successfully deleted {resource_type}/{name}",
        }

    def get_logs(
        self,
        cluster_name: str,
        pod_name: str,
        namespace: str = "default",
        container: str | None = None,
        tail_lines: int = 100,
        previous: bool = False,
    ) -> dict:
        """Get logs from a pod.

        Args:
            cluster_name: Cluster name
            pod_name: Pod name
            namespace: Kubernetes namespace (default: "default")
            container: Container name (optional, for multi-container pods)
            tail_lines: Number of lines to retrieve (default: 100)
            previous: Get logs from previous container instance

        Returns:
            Dict with pod logs

        Raises:
            KubeconfigNotFoundError: If kubeconfig not found
            ClusterNotFoundError: If cluster not accessible
            ResourceNotFoundError: If pod not found
            KubectlCommandError: If kubectl command fails
        """
        kubeconfig_path = self._validate_kubeconfig(cluster_name)

        # Build command
        args = ["logs", pod_name, "-n", namespace, f"--tail={tail_lines}"]
        if container:
            args.extend(["-c", container])
        if previous:
            args.append("--previous")

        result = self._run_kubectl(args, kubeconfig_path, timeout=30)

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            if "NotFound" in error_msg or "not found" in error_msg.lower():
                raise ResourceNotFoundError(
                    f"Pod '{pod_name}' not found in cluster '{cluster_name}', namespace '{namespace}'"
                )
            raise KubectlCommandError(
                f"Failed to get logs for pod '{pod_name}' in cluster '{cluster_name}': {error_msg}"
            )

        logs = result.stdout
        log_lines = logs.split("\n") if logs.strip() else []

        logger.info(
            f"Retrieved {len(log_lines)} lines of logs from pod '{pod_name}' "
            f"in cluster '{cluster_name}', namespace '{namespace}'"
        )

        return {
            "cluster_name": cluster_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container,
            "logs": logs,
            "lines": len(log_lines),
        }

    def describe_resource(
        self,
        cluster_name: str,
        resource_type: str,
        name: str,
        namespace: str = "default",
    ) -> dict:
        """Describe a Kubernetes resource.

        Args:
            cluster_name: Cluster name
            resource_type: Resource type (pod, service, deployment, etc.)
            name: Resource name
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Dict with resource description

        Raises:
            KubeconfigNotFoundError: If kubeconfig not found
            ClusterNotFoundError: If cluster not accessible
            ResourceNotFoundError: If resource not found
            KubectlCommandError: If kubectl command fails
        """
        kubeconfig_path = self._validate_kubeconfig(cluster_name)

        # Build command
        args = ["describe", resource_type, name, "-n", namespace]

        result = self._run_kubectl(args, kubeconfig_path, timeout=30)

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            if "NotFound" in error_msg or "not found" in error_msg.lower():
                raise ResourceNotFoundError(
                    f"Resource {resource_type}/{name} not found in cluster '{cluster_name}', "
                    f"namespace '{namespace}'"
                )
            raise KubectlCommandError(
                f"Failed to describe {resource_type}/{name} in cluster '{cluster_name}': {error_msg}"
            )

        description = result.stdout

        logger.info(
            f"Described {resource_type}/{name} in cluster '{cluster_name}', "
            f"namespace '{namespace}'"
        )

        return {
            "cluster_name": cluster_name,
            "resource_type": resource_type,
            "name": name,
            "namespace": namespace,
            "description": description,
        }
