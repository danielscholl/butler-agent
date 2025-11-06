"""Cluster status and health checking."""

import json
import logging
import subprocess
from typing import Any

from agent.utils.errors import ClusterNotFoundError, KindCommandError

logger = logging.getLogger(__name__)


class ClusterStatus:
    """Cluster status and health checking operations."""

    def __init__(self):
        """Initialize cluster status checker."""
        pass

    def get_cluster_status(self, name: str) -> dict[str, Any]:
        """Get comprehensive cluster status.

        Args:
            name: Cluster name

        Returns:
            Dict with cluster status information

        Raises:
            ClusterNotFoundError: If cluster doesn't exist
        """
        try:
            nodes = self.get_node_status(name)
            if not nodes:
                raise ClusterNotFoundError(f"Cluster '{name}' not found or not accessible")

            # Get basic cluster info
            status: dict[str, Any] = {
                "cluster_name": name,
                "status": "running" if nodes else "unknown",
                "nodes": nodes,
                "total_nodes": len(nodes),
                "ready_nodes": sum(1 for n in nodes if n.get("ready")),
            }

            # Try to get resource usage (requires metrics-server)
            try:
                resource_usage = self.get_resource_usage(name)
                status["resource_usage"] = resource_usage
            except Exception as e:
                logger.debug(f"Could not get resource usage: {e}")
                status["resource_usage"] = None

            # Detect installed addons (requires helm)
            try:
                addons = self.detect_addons(name)
                if addons:
                    status["addons"] = addons
            except Exception as e:
                logger.debug(f"Could not detect addons: {e}")
                # Don't fail status check if addon detection fails

            return status

        except subprocess.TimeoutExpired as e:
            raise KindCommandError(f"Timeout while getting status for cluster '{name}'") from e

    def get_node_status(self, name: str) -> list[dict[str, Any]]:
        """Get status of all nodes in cluster.

        Args:
            name: Cluster name

        Returns:
            List of node status dicts
        """
        context = f"kind-{name}"

        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "nodes",
                    "--context",
                    context,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to get nodes: {result.stderr}")
                return []

            data = json.loads(result.stdout)
            nodes = []

            for item in data.get("items", []):
                node_name = item.get("metadata", {}).get("name", "unknown")
                status = item.get("status", {})

                # Check if node is ready
                ready = False
                for condition in status.get("conditions", []):
                    if condition.get("type") == "Ready":
                        ready = condition.get("status") == "True"
                        break

                # Get node role
                labels = item.get("metadata", {}).get("labels", {})
                role = "worker"
                if "node-role.kubernetes.io/control-plane" in labels:
                    role = "control-plane"
                elif "node-role.kubernetes.io/master" in labels:
                    role = "control-plane"

                # Get version
                k8s_version = status.get("nodeInfo", {}).get("kubeletVersion", "unknown")

                nodes.append(
                    {
                        "name": node_name,
                        "role": role,
                        "ready": ready,
                        "version": k8s_version,
                        "status": "Ready" if ready else "NotReady",
                    }
                )

            return nodes

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Error getting node status: {e}")
            return []

    def get_resource_usage(self, name: str) -> dict[str, Any] | None:
        """Get resource usage for cluster (requires metrics-server).

        Args:
            name: Cluster name

        Returns:
            Dict with resource usage or None if metrics not available
        """
        context = f"kind-{name}"

        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "top",
                    "nodes",
                    "--context",
                    context,
                    "--no-headers",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return None

            # Parse output
            # Format: NAME   CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
            lines = result.stdout.strip().split("\n")
            nodes = []

            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    nodes.append(
                        {
                            "name": parts[0],
                            "cpu_cores": parts[1],
                            "cpu_percent": parts[2],
                            "memory": parts[3],
                            "memory_percent": parts[4],
                        }
                    )

            return {"nodes": nodes, "available": True}

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def detect_addons(self, name: str) -> dict[str, Any]:
        """Detect installed addons via Helm or kubectl.

        Checks both Helm releases and kubectl deployments to detect addons
        regardless of installation method.

        Args:
            name: Cluster name

        Returns:
            Dict mapping addon names to their status
        """
        addons = {}
        context = f"kind-{name}"

        # Method 1: Check Helm releases (for addons installed via create_cluster)
        try:
            result = subprocess.run(
                [
                    "helm",
                    "list",
                    "--namespace",
                    "kube-system",
                    "--kubeconfig",
                    f".local/clusters/{name}/kubeconfig",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                releases = json.loads(result.stdout)
                helm_addon_map = {
                    "ingress-nginx": ["ingress-nginx", "nginx-ingress"],
                    "metrics-server": ["metrics-server"],
                }

                for canonical_name, release_names in helm_addon_map.items():
                    found = next(
                        (r for r in releases if r.get("name") in release_names), None
                    )
                    if found:
                        addons[canonical_name] = {
                            "installed": True,
                            "method": "helm",
                            "version": found.get("app_version", "unknown"),
                            "chart": found.get("chart", "unknown"),
                        }

        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            logger.debug(f"Helm detection unavailable: {e}")

        # Method 2: Check kubectl deployments (for addons installed via kubectl apply)
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "deployments",
                    "-n",
                    "kube-system",
                    "--context",
                    context,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                deployment_names = {
                    item.get("metadata", {}).get("name", "") for item in data.get("items", [])
                }

                # Check for known deployment patterns
                kubectl_checks = {
                    "ingress-nginx": "ingress-nginx-controller",
                    "metrics-server": "metrics-server",
                }

                for canonical_name, deployment_name in kubectl_checks.items():
                    # Only add if not already found via Helm
                    if canonical_name not in addons and deployment_name in deployment_names:
                        addons[canonical_name] = {
                            "installed": True,
                            "method": "kubectl",
                        }

        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            logger.debug(f"kubectl detection failed: {e}")

        # Check ingress-nginx namespace too (some installs put it there)
        if "ingress-nginx" not in addons:
            try:
                result = subprocess.run(
                    [
                        "kubectl",
                        "get",
                        "deployments",
                        "-n",
                        "ingress-nginx",
                        "--context",
                        context,
                        "-o",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data.get("items"):
                        addons["ingress-nginx"] = {
                            "installed": True,
                            "method": "kubectl",
                            "namespace": "ingress-nginx",
                        }

            except Exception as e:
                logger.debug(f"ingress-nginx namespace check failed: {e}")

        return addons

    def check_cluster_health(self, name: str) -> dict[str, Any]:
        """Check overall cluster health.

        Args:
            name: Cluster name

        Returns:
            Dict with health check results
        """
        health: dict[str, Any] = {
            "healthy": True,
            "checks": [],
        }

        # Check nodes
        nodes = self.get_node_status(name)
        total_nodes = len(nodes)
        ready_nodes = sum(1 for n in nodes if n.get("ready"))

        health["checks"].append(
            {
                "name": "nodes",
                "status": "pass" if ready_nodes == total_nodes else "fail",
                "message": f"{ready_nodes}/{total_nodes} nodes ready",
            }
        )

        if ready_nodes != total_nodes:
            health["healthy"] = False

        # Check system pods
        try:
            context = f"kind-{name}"
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    "kube-system",
                    "--context",
                    context,
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                pods = data.get("items", [])
                running_pods = sum(
                    1 for p in pods if p.get("status", {}).get("phase") in ["Running", "Succeeded"]
                )

                health["checks"].append(
                    {
                        "name": "system_pods",
                        "status": "pass" if running_pods == len(pods) else "warn",
                        "message": f"{running_pods}/{len(pods)} system pods running",
                    }
                )

        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            health["checks"].append(
                {
                    "name": "system_pods",
                    "status": "warn",
                    "message": "Could not check system pods",
                }
            )

        return health
