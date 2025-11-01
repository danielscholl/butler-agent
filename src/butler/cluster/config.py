"""KinD cluster configuration templates and management."""

from typing import Any, Dict

# Minimal cluster configuration for quick testing
MINIMAL_CONFIG = """kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}
nodes:
- role: control-plane
"""

# Default cluster configuration with one control plane and one worker
DEFAULT_CONFIG = """kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
"""

# Custom multi-node cluster configuration
CUSTOM_CONFIG = """kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
- role: worker
- role: worker
"""

TEMPLATES: Dict[str, str] = {
    "minimal": MINIMAL_CONFIG,
    "default": DEFAULT_CONFIG,
    "custom": CUSTOM_CONFIG,
}


def get_cluster_config(template: str, name: str, **kwargs: Any) -> str:
    """Generate cluster configuration from template.

    Args:
        template: Template name (minimal, default, custom)
        name: Cluster name
        **kwargs: Additional template variables

    Returns:
        Rendered cluster configuration YAML

    Raises:
        ValueError: If template name is invalid
    """
    if template not in TEMPLATES:
        raise ValueError(
            f"Invalid template: {template}. Must be one of: {', '.join(TEMPLATES.keys())}"
        )

    config = TEMPLATES[template]
    variables = {"name": name, **kwargs}

    return config.format(**variables)


def validate_cluster_config(config: str) -> bool:
    """Validate cluster configuration.

    Args:
        config: YAML configuration string

    Returns:
        True if valid

    Raises:
        ValueError: If configuration is invalid
    """
    if not config or not config.strip():
        raise ValueError("Cluster configuration cannot be empty")

    # Basic validation - check for required fields
    if "kind: Cluster" not in config:
        raise ValueError("Configuration must contain 'kind: Cluster'")

    if "apiVersion: kind.x-k8s.io/v1alpha4" not in config:
        raise ValueError("Configuration must contain 'apiVersion: kind.x-k8s.io/v1alpha4'")

    return True
