"""Output formatting utilities for Butler Agent.

This module provides functions to format various data structures into
Rich-formatted output for the console.
"""

from typing import Any

from rich.panel import Panel
from rich.table import Table


def format_cluster_status(status_dict: dict[str, Any]) -> Table:
    """Format cluster status as a Rich table.

    Args:
        status_dict: Cluster status dictionary

    Returns:
        Rich Table with cluster status
    """
    table = Table(title=f"Cluster Status: {status_dict.get('cluster_name', 'Unknown')}")

    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Status", status_dict.get("status", "unknown"))
    table.add_row("Total Nodes", str(status_dict.get("total_nodes", 0)))
    table.add_row("Ready Nodes", str(status_dict.get("ready_nodes", 0)))

    # Add nodes table
    nodes = status_dict.get("nodes", [])
    if nodes:
        table.add_row("", "")
        table.add_row("[bold]Nodes", "")
        for node in nodes:
            status_emoji = "✓" if node.get("ready") else "✗"
            table.add_row(
                f"  {node.get('name', 'unknown')}",
                f"{status_emoji} {node.get('role', 'unknown')} - {node.get('version', 'unknown')}",
            )

    return table


def format_cluster_list(clusters: list[str]) -> Table:
    """Format cluster list as a Rich table.

    Args:
        clusters: List of cluster names

    Returns:
        Rich Table with cluster list
    """
    table = Table(title="KinD Clusters")

    table.add_column("Cluster Name", style="cyan")
    table.add_column("Context", style="white")

    for cluster in clusters:
        table.add_row(cluster, f"kind-{cluster}")

    if not clusters:
        table.add_row("[dim]No clusters found[/dim]", "")

    return table


def format_error(message: str) -> Panel:
    """Format error message as a Rich panel.

    Args:
        message: Error message

    Returns:
        Rich Panel with error styling
    """
    return Panel(
        message,
        title="Error",
        border_style="red",
        title_align="left",
    )


def format_success(message: str) -> Panel:
    """Format success message as a Rich panel.

    Args:
        message: Success message

    Returns:
        Rich Panel with success styling
    """
    return Panel(
        message,
        title="Success",
        border_style="green",
        title_align="left",
    )


def format_info(message: str) -> Panel:
    """Format info message as a Rich panel.

    Args:
        message: Info message

    Returns:
        Rich Panel with info styling
    """
    return Panel(
        message,
        title="Info",
        border_style="blue",
        title_align="left",
    )


def format_warning(message: str) -> Panel:
    """Format warning message as a Rich panel.

    Args:
        message: Warning message

    Returns:
        Rich Panel with warning styling
    """
    return Panel(
        message,
        title="Warning",
        border_style="yellow",
        title_align="left",
    )
