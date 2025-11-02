"""Validation utilities for Butler Agent."""

import re


def validate_cluster_name(name: str) -> bool:
    """Validate cluster name follows Kubernetes naming conventions.

    Cluster names must:
    - Be lowercase
    - Start and end with alphanumeric characters
    - Contain only alphanumeric characters and hyphens
    - Be between 1 and 63 characters

    Args:
        name: Cluster name to validate

    Returns:
        True if valid

    Raises:
        ValueError: If name is invalid
    """
    if not name:
        raise ValueError("Cluster name cannot be empty")

    if len(name) > 63:
        raise ValueError("Cluster name must be 63 characters or less")

    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", name):
        raise ValueError(
            "Cluster name must be lowercase alphanumeric with hyphens, "
            "starting and ending with alphanumeric characters"
        )

    return True


def validate_k8s_version(version: str) -> bool:
    """Validate Kubernetes version format.

    Version must be in format: vX.Y.Z or vX.Y

    Args:
        version: Kubernetes version string

    Returns:
        True if valid

    Raises:
        ValueError: If version format is invalid
    """
    if not version:
        raise ValueError("Kubernetes version cannot be empty")

    if not re.match(r"^v\d+\.\d+(\.\d+)?$", version):
        raise ValueError(
            f"Invalid Kubernetes version format: {version}. "
            "Must be in format vX.Y.Z or vX.Y (e.g., v1.34.0)"
        )

    return True
