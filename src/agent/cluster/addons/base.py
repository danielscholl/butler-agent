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
        values: dict[str, Any] | None = None,
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

              **PRE-CREATION HOOK CONTRACT**:
              This method is called BEFORE the cluster is created. It must:
              - Return cluster configuration requirements ONLY (no side effects)
              - NOT access kubeconfig or attempt cluster operations
              - NOT access self.kubeconfig_path (it may not exist yet)
              - Be deterministic and idempotent

              This method is called during Phase 1 (pre-creation) of the two-phase addon
              pattern. The returned requirements are merged into the cluster config before
              the cluster is created.

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
                          '''[plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
        endpoint = ["http://registry:5000"]'''
                      ]
                  }
        """
        return {}

    def get_port_requirements(self) -> list[dict[str, Any]]:
        """Return port mappings needed for this addon.

        **PRE-CREATION HOOK CONTRACT**: See get_cluster_config_requirements() for
        contract details. This method must not access kubeconfig or cluster state.

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

        **PRE-CREATION HOOK CONTRACT**: See get_cluster_config_requirements() for
        contract details. This method must not access kubeconfig or cluster state.

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
        """Run the complete addon installation flow with progress tracking.

        Returns:
            Dict with installation result
        """
        import time

        from agent.display import AddonProgressEvent, get_event_emitter, should_show_visualization

        self.log_info(f"Starting installation for cluster '{self.cluster_name}'")
        start_time = time.time()

        # Get parent tool event ID from context (if available)
        parent_id = getattr(self, "_parent_event_id", None)

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

        # Emit starting event
        addon_event_id = None
        if should_show_visualization():
            event = AddonProgressEvent(
                addon_name=self.addon_name,
                status="starting",
                message=f"Installing {self.addon_name}",
                parent_id=parent_id,
            )
            addon_event_id = event.event_id
            get_event_emitter().emit(event)

        # Install
        try:
            result = self.install()
            if not result.get("success"):
                # Emit error event
                duration = time.time() - start_time
                if should_show_visualization() and addon_event_id:
                    error_event = AddonProgressEvent(
                        addon_name=self.addon_name,
                        status="error",
                        message=f"Installation failed",
                        duration=duration,
                        parent_id=parent_id,
                    )
                    error_event.event_id = addon_event_id
                    get_event_emitter().emit(error_event)
                return result

            # Emit waiting event
            if should_show_visualization() and addon_event_id:
                wait_event = AddonProgressEvent(
                    addon_name=self.addon_name,
                    status="waiting",
                    message=f"Waiting for {self.addon_name} to be ready",
                    parent_id=parent_id,
                )
                wait_event.event_id = addon_event_id
                get_event_emitter().emit(wait_event)

            # Wait for ready
            if not self.wait_for_ready():
                self.log_warn("Addon installed but not ready within timeout")
                duration = time.time() - start_time
                if should_show_visualization() and addon_event_id:
                    error_event = AddonProgressEvent(
                        addon_name=self.addon_name,
                        status="error",
                        message="Timeout waiting for ready",
                        duration=duration,
                        parent_id=parent_id,
                    )
                    error_event.event_id = addon_event_id
                    get_event_emitter().emit(error_event)
                return {
                    "success": False,
                    "addon": self.addon_name,
                    "error": "Timeout waiting for addon to be ready",
                    "message": f"{self.addon_name} installation timeout",
                }

            # Verify
            if not self.verify():
                self.log_warn("Addon verification failed")
                duration = time.time() - start_time
                if should_show_visualization() and addon_event_id:
                    error_event = AddonProgressEvent(
                        addon_name=self.addon_name,
                        status="error",
                        message="Verification failed",
                        duration=duration,
                        parent_id=parent_id,
                    )
                    error_event.event_id = addon_event_id
                    get_event_emitter().emit(error_event)
                return {
                    "success": False,
                    "addon": self.addon_name,
                    "error": "Verification failed",
                    "message": f"{self.addon_name} verification failed",
                }

            # Emit complete event
            duration = time.time() - start_time
            if should_show_visualization() and addon_event_id:
                complete_event = AddonProgressEvent(
                    addon_name=self.addon_name,
                    status="complete",
                    message="Ready",
                    duration=duration,
                    parent_id=parent_id,
                )
                complete_event.event_id = addon_event_id
                get_event_emitter().emit(complete_event)

            self.log_info("Installation completed successfully")
            return {
                "success": True,
                "addon": self.addon_name,
                "message": f"{self.addon_name} installed successfully",
                "duration": duration,
            }

        except Exception as e:
            self.log_error(f"Installation failed: {e}")
            duration = time.time() - start_time

            # Emit error event
            if should_show_visualization() and addon_event_id:
                error_event = AddonProgressEvent(
                    addon_name=self.addon_name,
                    status="error",
                    message=f"Failed: {str(e)}",
                    duration=duration,
                    parent_id=parent_id,
                )
                error_event.event_id = addon_event_id
                get_event_emitter().emit(error_event)

            return {
                "success": False,
                "addon": self.addon_name,
                "error": str(e),
                "message": f"{self.addon_name} installation failed: {e}",
                "duration": duration,
            }
