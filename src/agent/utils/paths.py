"""Path management utilities for Butler Agent."""

from pathlib import Path

from agent.config import AgentConfig


def ensure_data_dir(config: AgentConfig) -> Path:
    """Ensure data directory exists.

    Args:
        config: Butler configuration

    Returns:
        Path to data directory
    """
    data_path = Path(config.data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    return data_path


def get_cluster_data_path(config: AgentConfig, cluster_name: str) -> Path:
    """Get path for cluster-specific data.

    Args:
        config: Butler configuration
        cluster_name: Name of the cluster

    Returns:
        Path to cluster data directory
    """
    cluster_path = Path(config.data_dir) / cluster_name
    cluster_path.mkdir(parents=True, exist_ok=True)
    return cluster_path
