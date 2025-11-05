"""NGINX Ingress Controller addon."""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from agent.cluster.addons.base import BaseAddon
from agent.utils.async_subprocess import run_async
from agent.utils.errors import HelmCommandError


class IngressNginxAddon(BaseAddon):
    """NGINX Ingress Controller addon.

    Installs the NGINX Ingress Controller using Helm.
    Configured for Kind clusters with NodePort service type and hostPort access.

    Cluster Requirements (applied before cluster creation):
    - Port mappings: 80 (HTTP) and 443 (HTTPS)
    - Node label: ingress-ready=true (for Kind compatibility)
    """

    DEFAULT_CHART_VERSION = "4.13.2"
    DEFAULT_NAMESPACE = "kube-system"
    HELM_REPO_NAME = "ingress-nginx"
    HELM_REPO_URL = "https://kubernetes.github.io/ingress-nginx"
    HELM_CHART = "ingress-nginx/ingress-nginx"
    RELEASE_NAME = "ingress-nginx"
    DEPLOYMENT_NAME = "ingress-nginx-controller"

    def __init__(
        self, cluster_name: str, kubeconfig_path: Path, config: dict[str, Any] | None = None
    ):
        """Initialize NGINX Ingress addon.

        Args:
            cluster_name: Name of the cluster
            kubeconfig_path: Path to cluster's kubeconfig file
            config: Optional configuration:
                - chart_version: Helm chart version (default: 4.13.2)
                - namespace: Kubernetes namespace (default: kube-system)
                - values: Additional Helm values dict
        """
        super().__init__(cluster_name, kubeconfig_path, config)
        self.chart_version = self.config.get("chart_version", self.DEFAULT_CHART_VERSION)
        self.namespace = self.config.get("namespace", self.DEFAULT_NAMESPACE)
        self.custom_values = self.config.get("values", {})
        self.addon_name = "ingress-nginx"

    def get_port_requirements(self) -> list[dict[str, Any]]:
        """NGINX Ingress needs ports 80 and 443 mapped to host.

        These ports allow direct access to the ingress controller from the host machine.
        The cluster template must include these port mappings before cluster creation.
        """
        return [
            {"containerPort": 80, "hostPort": 80, "protocol": "TCP"},
            {"containerPort": 443, "hostPort": 443, "protocol": "TCP"},
        ]

    def get_node_labels(self) -> dict[str, str]:
        """NGINX Ingress requires the ingress-ready label for Kind compatibility.

        Kind uses this label to identify which nodes can run ingress controllers.
        """
        return {"ingress-ready": "true"}

    async def check_prerequisites(self) -> bool:
        """Check if prerequisites are met asynchronously.

        Returns:
            True if prerequisites are met
        """
        # Check if kubectl works with the cluster
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = await run_async(
                ["kubectl", "cluster-info"],
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
            )
            if result.returncode != 0:
                self.log_error("Cluster is not accessible via kubectl")
                return False
        except Exception as e:
            self.log_error(f"Error checking cluster access: {e}")
            return False

        # Check if helm is available
        try:
            await run_async(
                ["helm", "version"],
                timeout=10,
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            self.log_error("helm CLI not found. Please install helm")
            return False
        except Exception as e:
            self.log_error(f"Error checking helm: {e}")
            return False

        return True

    async def is_installed(self) -> bool:
        """Check if NGINX Ingress is already installed asynchronously.

        Returns:
            True if already installed
        """
        # Check via Helm release
        try:
            result = await self._run_helm(
                ["list", "-n", self.namespace, "-q"],
                check=False,
            )
            if result.returncode == 0 and self.RELEASE_NAME in result.stdout:
                self.log_info("Detected via Helm release")
                return True
        except Exception as e:
            # Helm check failed, fallback to kubectl
            self.log_info(f"Helm check failed, trying kubectl fallback: {e}")

        # Fallback: Check via kubectl deployment
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = await run_async(
                [
                    "kubectl",
                    "get",
                    "deployment",
                    self.DEPLOYMENT_NAME,
                    "-n",
                    self.namespace,
                ],
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
            )
            if result.returncode == 0:
                self.log_info("Detected via kubectl deployment")
                return True
        except Exception as e:
            # kubectl check failed
            self.log_info(f"kubectl check failed: {e}")

        return False

    async def install(self) -> dict[str, Any]:
        """Install NGINX Ingress Controller asynchronously.

        Returns:
            Installation result dict
        """
        try:
            # Add Helm repository
            await self._add_helm_repo(self.HELM_REPO_NAME, self.HELM_REPO_URL)

            # Prepare Helm values for Kind cluster
            # Note: Port mappings and node labels are handled in cluster config (pre-creation)
            # Here we configure the controller to use those ports via hostPort
            values = {
                "controller.service.type": "NodePort",
                "controller.hostPort.enabled": "true",
                "controller.hostPort.ports.http": "80",
                "controller.hostPort.ports.https": "443",
                "controller.updateStrategy.type": "RollingUpdate",
                "controller.updateStrategy.rollingUpdate.maxUnavailable": "1",
            }

            # Merge with custom values (user can override defaults)
            values.update(self.custom_values)

            # Install via Helm
            await self._helm_install(
                release_name=self.RELEASE_NAME,
                chart=self.HELM_CHART,
                namespace=self.namespace,
                values=values,
                version=self.chart_version,
            )

            return {
                "success": True,
                "message": f"NGINX Ingress Controller installed (version {self.chart_version})",
            }

        except HelmCommandError as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Helm installation failed: {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Installation failed: {e}",
            }

    async def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for NGINX Ingress Controller to be ready asynchronously.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if ready within timeout
        """
        self.log_info("Waiting for NGINX Ingress Controller to be ready")

        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = await run_async(
                [
                    "kubectl",
                    "wait",
                    "--namespace",
                    self.namespace,
                    "--for=condition=available",
                    f"deployment/{self.DEPLOYMENT_NAME}",
                    f"--timeout={timeout}s",
                ],
                env=env,
                timeout=timeout + 10,
                check=False,
                capture_output=True,
            )

            if result.returncode == 0:
                self.log_info("NGINX Ingress Controller is ready")
                return True
            else:
                self.log_warn(f"Wait failed: {result.stderr}")
                return False

        except asyncio.TimeoutError:
            self.log_warn(f"Timeout waiting for deployment (>{timeout}s)")
            return False
        except Exception as e:
            self.log_warn(f"Error waiting for deployment: {e}")
            return False

    async def verify(self) -> bool:
        """Verify NGINX Ingress Controller is functioning asynchronously.

        Returns:
            True if verification passes
        """
        # Check if admission webhook is configured
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = await run_async(
                [
                    "kubectl",
                    "get",
                    "validatingwebhookconfigurations",
                    "-o",
                    "name",
                ],
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
            )

            if "ingress-nginx-admission" in result.stdout:
                self.log_info("Admission webhook verified")
                return True
            else:
                self.log_warn("Admission webhook not found")
                return False

        except Exception as e:
            self.log_warn(f"Verification failed: {e}")
            return False
