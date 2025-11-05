"""NGINX Ingress Controller addon."""

import os
import subprocess
from typing import Any

from agent.cluster.addons.base import BaseAddon
from agent.utils.errors import HelmCommandError


class IngressNginxAddon(BaseAddon):
    """NGINX Ingress Controller addon.

    Installs the NGINX Ingress Controller using Helm.
    Configured for Kind clusters with NodePort service type.
    """

    DEFAULT_CHART_VERSION = "4.13.2"
    DEFAULT_NAMESPACE = "kube-system"
    HELM_REPO_NAME = "ingress-nginx"
    HELM_REPO_URL = "https://kubernetes.github.io/ingress-nginx"
    HELM_CHART = "ingress-nginx/ingress-nginx"
    RELEASE_NAME = "ingress-nginx"
    DEPLOYMENT_NAME = "ingress-nginx-controller"

    def __init__(self, cluster_name: str, kubeconfig_path, config: dict[str, Any] | None = None):
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

    def check_prerequisites(self) -> bool:
        """Check if prerequisites are met.

        Returns:
            True if prerequisites are met
        """
        # Check if kubectl works with the cluster
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = subprocess.run(
                ["kubectl", "cluster-info"],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                self.log_error("Cluster is not accessible via kubectl")
                return False
        except Exception as e:
            self.log_error(f"Error checking cluster access: {e}")
            return False

        # Check if helm is available
        try:
            subprocess.run(
                ["helm", "version"],
                capture_output=True,
                timeout=10,
                check=True,
            )
        except FileNotFoundError:
            self.log_error("helm CLI not found. Please install helm")
            return False
        except Exception as e:
            self.log_error(f"Error checking helm: {e}")
            return False

        return True

    def is_installed(self) -> bool:
        """Check if NGINX Ingress is already installed.

        Returns:
            True if already installed
        """
        # Check via Helm release
        try:
            result = self._run_helm(
                ["list", "-n", self.namespace, "-q"],
                check=False,
            )
            if result.returncode == 0 and self.RELEASE_NAME in result.stdout:
                self.log_info("Detected via Helm release")
                return True
        except Exception:
            pass

        # Fallback: Check via kubectl deployment
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "deployment",
                    self.DEPLOYMENT_NAME,
                    "-n",
                    self.namespace,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self.log_info("Detected via kubectl deployment")
                return True
        except Exception:
            pass

        return False

    def install(self) -> dict[str, Any]:
        """Install NGINX Ingress Controller.

        Returns:
            Installation result dict
        """
        try:
            # Add Helm repository
            self._add_helm_repo(self.HELM_REPO_NAME, self.HELM_REPO_URL)

            # Prepare Helm values for Kind cluster
            values = {
                "controller.service.type": "NodePort",
                "controller.hostPort.enabled": "true",
                "controller.hostPort.ports.http": "80",
                "controller.hostPort.ports.https": "443",
                "controller.updateStrategy.type": "RollingUpdate",
                "controller.updateStrategy.rollingUpdate.maxUnavailable": "1",
            }

            # Merge with custom values
            values.update(self.custom_values)

            # Install via Helm
            self._helm_install(
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

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for NGINX Ingress Controller to be ready.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if ready within timeout
        """
        self.log_info("Waiting for NGINX Ingress Controller to be ready")

        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = subprocess.run(
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
                capture_output=True,
                text=True,
                timeout=timeout + 10,
            )

            if result.returncode == 0:
                self.log_info("NGINX Ingress Controller is ready")
                return True
            else:
                self.log_warn(f"Wait failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.log_warn(f"Timeout waiting for deployment (>{timeout}s)")
            return False
        except Exception as e:
            self.log_warn(f"Error waiting for deployment: {e}")
            return False

    def verify(self) -> bool:
        """Verify NGINX Ingress Controller is functioning.

        Returns:
            True if verification passes
        """
        # Check if admission webhook is configured
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.kubeconfig_path)

            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "validatingwebhookconfigurations",
                    "-o",
                    "name",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
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
