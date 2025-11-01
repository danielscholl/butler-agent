"""Table rendering utilities for Butler Agent."""

from typing import Any, Dict, List

from rich.table import Table


def create_cluster_table(data: List[Dict[str, Any]]) -> Table:
    """Create a table for cluster information.

    Args:
        data: List of cluster data dictionaries

    Returns:
        Rich Table with cluster data
    """
    table = Table(title="Clusters")

    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Nodes", style="white")
    table.add_column("Version", style="white")

    for cluster in data:
        table.add_row(
            cluster.get("name", "unknown"),
            cluster.get("status", "unknown"),
            str(cluster.get("nodes", 0)),
            cluster.get("version", "unknown"),
        )

    return table


def create_resource_table(data: Dict[str, Any]) -> Table:
    """Create a table for resource usage information.

    Args:
        data: Resource usage data

    Returns:
        Rich Table with resource data
    """
    table = Table(title="Resource Usage")

    table.add_column("Node", style="cyan")
    table.add_column("CPU", style="yellow")
    table.add_column("Memory", style="blue")

    nodes = data.get("nodes", [])
    for node in nodes:
        table.add_row(
            node.get("name", "unknown"),
            f"{node.get('cpu_cores', 'N/A')} ({node.get('cpu_percent', 'N/A')})",
            f"{node.get('memory', 'N/A')} ({node.get('memory_percent', 'N/A')})",
        )

    return table


def create_health_table(checks: List[Dict[str, Any]]) -> Table:
    """Create a table for health check results.

    Args:
        checks: List of health check results

    Returns:
        Rich Table with health check data
    """
    table = Table(title="Health Checks")

    table.add_column("Check", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="white")

    for check in checks:
        status = check.get("status", "unknown")
        status_emoji = {"pass": "✓", "fail": "✗", "warn": "⚠"}.get(status, "?")
        status_style = {
            "pass": "green",
            "fail": "red",
            "warn": "yellow",
        }.get(status, "white")

        table.add_row(
            check.get("name", "unknown"),
            f"[{status_style}]{status_emoji} {status}[/{status_style}]",
            check.get("message", ""),
        )

    return table
