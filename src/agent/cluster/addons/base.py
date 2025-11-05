"""Base addon class for all cluster add-ons."""

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from agent.utils.errors import HelmCommandError

logger = logging.getLogger(__name__)


class BaseAddon(ABC):
    """Abstract base class for cluster add-ons.

    All add-ons should inherit from this class and implement the abstract methods.
    """

    def __init__(
        self, cluster_name: str, kubeconfig_path: Path, config: dict[str, Any] | None = None
    ):
        """Initialize addon.

        Args:
            cluster_name: Name of the cluster
            kubeconfig_path: Path to cluster's kubeconfig file
            config: Optional configuration dict for the addon
        """
        self.cluster_name = cluster_name
        self.kubeconfig_path = kubeconfig_path
        self.config = config or {}
        self.addon_name = self.__class__.__name__.replace("Addon", "").lower()

    def log_info(self, message: str) -> None:
        """Log info message with addon prefix."""
        logger.info(f"[{self.addon_name}] {message}")

    def log_warn(self, message: str) -> None:
        """Log warning message with addon prefix."""
        logger.warning(f"[{self.addon_name}] {message}")

    def log_error(self, message: str) -> None:
        """Log error message with addon prefix."""
        logger.error(f"[{self.addon_name}] {message}")

    def _run_helm(
        self,
        args: list[str],
        check: bool = True,
        capture_output: bool = True,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        """Run helm command with kubeconfig.

        Args:
            args: Helm command arguments
            check: Whether to check return code
            capture_output: Whether to capture stdout/stderr
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess result

        Raises:
            HelmCommandError: If command fails and check=True
        """
        cmd = ["helm"] + args
        logger.debug(f"Running helm command: {' '.join(cmd)}")

        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env=env,
                check=False,
            )

            if check and result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise HelmCommandError(f"Helm command failed: {error_msg}")

            return result

        except subprocess.TimeoutExpired as e:
            raise HelmCommandError(f"Helm command timed out after {timeout} seconds") from e
        except FileNotFoundError as e:
            raise HelmCommandError(
                "helm CLI not found. Please install helm: https://helm.sh/docs/intro/install/"
            ) from e

    def _add_helm_repo(self, name: str, url: str) -> None:
        """Add or update a Helm repository.

        Args:
            name: Repository name
            url: Repository URL
        """
        self.log_info(f"Adding Helm repository: {name}")
        self._run_helm(["repo", "add", name, url], check=False)
        self._run_helm(["repo", "update"], check=False)

    def _helm_install(
        self,
        release_name: str,
        chart: str,
        namespace: str,
        values: dict[str, str] | None = None,
        version: str | None = None,
    ) -> None:
        """Install a Helm chart.

        Args:
            release_name: Name for the Helm release
            chart: Chart name (repo/chart)
            namespace: Kubernetes namespace
            values: Optional Helm values as --set key=value pairs
            version: Optional chart version
        """
        cmd_args = [
            "upgrade",
            "--install",
            release_name,
            chart,
            "--namespace",
            namespace,
            "--create-namespace",
        ]

        if version:
            cmd_args.extend(["--version", version])

        if values:
            for key, value in values.items():
                cmd_args.extend(["--set", f"{key}={value}"])

        self.log_info(f"Installing Helm chart: {chart}")
        self._run_helm(cmd_args, timeout=300)  # 5 minute timeout for installation

    def get_cluster_config_requirements(self) -> dict[str, Any]:
        """Return cluster config patches needed before cluster creation.

        This method is called BEFORE the cluster is created to gather any
        configuration requirements that must be baked into the Kind cluster config.

        Override this for addons that need cluster-level configuration like:
        - containerd patches for container registries
        - feature gates for alpha/beta Kubernetes features
        - network configuration changes

        Returns:
            Dict with optional keys:
            - containerdConfigPatches: list[str] - containerd config patches
            - networking: dict - networking configuration overrides
            - featureGates: dict[str, bool] - Kubernetes feature gates

        Example:
            {
                "containerdConfigPatches": [
                    '[plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]\\n  endpoint = ["http://registry:5000"]'
                ]
            }
        """
        return {}

    def get_port_requirements(self) -> list[dict[str, Any]]:
        """Return port mappings needed for this addon.

        This method is called BEFORE the cluster is created to gather port mapping
        requirements. Port mappings are applied to the control-plane node's
        extraPortMappings configuration.

        Override this for addons that need host port access like:
        - Ingress controllers (80, 443)
        - Registries (5000, 5001)
        - Gateway API controllers (custom ports)

        Returns:
            List of port mapping dicts with keys:
            - containerPort: int - Port inside the container
            - hostPort: int - Port on the host machine
            - protocol: str - "TCP" or "UDP"

        Example:
            [
                {"containerPort": 80, "hostPort": 80, "protocol": "TCP"},
                {"containerPort": 443, "hostPort": 443, "protocol": "TCP"}
            ]
        """
        return []

    def get_node_labels(self) -> dict[str, str]:
        """Return node labels needed for this addon.

        This method is called BEFORE the cluster is created to gather node label
        requirements. Labels are applied to control-plane nodes via kubeletExtraArgs.

        Override this for addons that need specific node labels like:
        - Ingress controllers (ingress-ready=true)
        - Storage classes (specific node capabilities)

        Returns:
            Dict of label key-value pairs

        Example:
            {"ingress-ready": "true", "storage-class": "local"}
        """
        return {}

    @abstractmethod
    def check_prerequisites(self) -> bool:
        """Check if prerequisites for addon installation are met.

        Returns:
            True if prerequisites are met, False otherwise
        """
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """Check if addon is already installed.

        Returns:
            True if addon is already installed, False otherwise
        """
        pass

    @abstractmethod
    def install(self) -> dict[str, Any]:
        """Install the addon.

        Returns:
            Dict with installation result:
            - success: bool
            - message: str
            - error: str (optional)
        """
        pass

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for addon to be ready.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if addon became ready, False otherwise
        """
        # Default implementation - subclasses can override
        return True

    def verify(self) -> bool:
        """Verify addon is functioning correctly.

        Returns:
            True if addon is verified, False otherwise
        """
        # Default implementation - subclasses can override
        return True

    def run(self) -> dict[str, Any]:
        """Run the complete addon installation flow.

        Returns:
            Dict with installation result
        """
        self.log_info(f"Starting installation for cluster '{self.cluster_name}'")

        # Check prerequisites
        if not self.check_prerequisites():
            return {
                "success": False,
                "addon": self.addon_name,
                "error": "Prerequisites not met",
                "message": f"Prerequisites check failed for {self.addon_name}",
            }

        # Check if already installed
        if self.is_installed():
            self.log_info("Already installed, skipping")
            return {
                "success": True,
                "addon": self.addon_name,
                "skipped": True,
                "message": f"{self.addon_name} is already installed",
            }

        # Install
        try:
            result = self.install()
            if not result.get("success"):
                return result

            # Wait for ready
            if not self.wait_for_ready():
                self.log_warn("Addon installed but not ready within timeout")
                return {
                    "success": False,
                    "addon": self.addon_name,
                    "error": "Timeout waiting for addon to be ready",
                    "message": f"{self.addon_name} installation timeout",
                }

            # Verify
            if not self.verify():
                self.log_warn("Addon verification failed")
                return {
                    "success": False,
                    "addon": self.addon_name,
                    "error": "Verification failed",
                    "message": f"{self.addon_name} verification failed",
                }

            self.log_info("Installation completed successfully")
            return {
                "success": True,
                "addon": self.addon_name,
                "message": f"{self.addon_name} installed successfully",
            }

        except Exception as e:
            self.log_error(f"Installation failed: {e}")
            return {
                "success": False,
                "addon": self.addon_name,
                "error": str(e),
                "message": f"{self.addon_name} installation failed: {e}",
            }
