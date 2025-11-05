"""Port conflict detection utilities for Kind clusters.

This module provides utilities to detect port conflicts before cluster creation,
preventing wasted time on failed operations.
"""

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def check_port_conflict(port: int) -> dict[str, Any] | None:
    """Check if a port is in use by a Docker container (likely Kind cluster).

    Args:
        port: Port number to check (e.g., 80, 443)

    Returns:
        Dict with conflict info if port is in use, None if free:
        - port: int - The conflicting port
        - cluster_name: str - Name of Kind cluster using the port (if identifiable)
        - container: str - Docker container name

    Example:
        conflict = check_port_conflict(80)
        if conflict:
            print(f"Port {conflict['port']} used by {conflict['cluster_name']}")
    """
    try:
        # Check with lsof first (more reliable)
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # If lsof finds nothing, port is free
        if result.returncode != 0 or not result.stdout.strip():
            return None

        # Port is in use - check if it's a Docker container
        if "docker" in result.stdout.lower() or "com.docke" in result.stdout:
            # Try to find which Docker container is using the port
            docker_result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"publish={port}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if docker_result.returncode == 0 and docker_result.stdout.strip():
                container_name = docker_result.stdout.strip().split("\n")[0]

                # Check if it's a Kind cluster (ends with -control-plane or -worker)
                if "-control-plane" in container_name or "-worker" in container_name:
                    # Extract cluster name (remove -control-plane or -worker suffix)
                    cluster_name = container_name.replace("-control-plane", "").replace(
                        "-worker", ""
                    )
                    logger.debug(f"Port {port} is in use by Kind cluster '{cluster_name}'")

                    return {
                        "port": port,
                        "cluster_name": cluster_name,
                        "container": container_name,
                    }
                else:
                    # Docker container but not Kind
                    logger.debug(f"Port {port} is in use by Docker container '{container_name}'")
                    return {
                        "port": port,
                        "cluster_name": None,
                        "container": container_name,
                    }

        # Port in use by non-Docker process
        logger.debug(f"Port {port} is in use by a non-Docker process")
        return {
            "port": port,
            "cluster_name": None,
            "container": None,
        }

    except FileNotFoundError:
        # lsof or docker not available - assume port is free (best effort)
        logger.warning(f"Cannot check port {port} - lsof or docker not available")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout checking port {port}")
        return None
    except Exception as e:
        logger.warning(f"Error checking port {port}: {e}")
        return None


def check_ingress_ports() -> dict[str, Any]:
    """Check if ingress ports (80 and 443) are available.

    Returns:
        Dict with availability status:
        - available: bool - True if both ports are free
        - conflicts: list - List of port conflicts (from check_port_conflict)
        - conflicting_cluster: str | None - Name of Kind cluster if identified

    Example:
        status = check_ingress_ports()
        if not status['available']:
            print(f"Ports in use by: {status['conflicting_cluster']}")
    """
    conflicts = []

    # Check both ports
    for port in [80, 443]:
        conflict = check_port_conflict(port)
        if conflict:
            conflicts.append(conflict)

    # Determine if available
    available = len(conflicts) == 0

    # Extract cluster name if found (prefer cluster over generic container)
    conflicting_cluster = None
    if conflicts:
        for conflict in conflicts:
            if conflict.get("cluster_name"):
                conflicting_cluster = conflict["cluster_name"]
                break

    return {
        "available": available,
        "conflicts": conflicts,
        "conflicting_cluster": conflicting_cluster,
    }
