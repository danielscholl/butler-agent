"""Utilities for merging addon configuration requirements into cluster configs.

This module handles the merging of addon-specific configuration requirements
(like port mappings, containerd patches, node labels) into Kind cluster configurations.
"""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def merge_addon_requirements(
    base_config: dict[str, Any], addon_requirements: list[dict[str, Any]]
) -> dict[str, Any]:
    """Merge addon configuration requirements into base cluster config.

    This function implements the two-phase addon pattern, where addons can declare
    configuration requirements that must be applied BEFORE cluster creation.

    Strategy:
    - containerdConfigPatches: APPEND all patches
    - extraPortMappings: APPEND to control-plane node (dedupe by containerPort)
    - node labels: MERGE into kubeletExtraArgs.node-labels
    - networking: MERGE (log warnings on conflicts)
    - featureGates: MERGE (log warnings on conflicts)

    Args:
        base_config: Base cluster configuration dict
        addon_requirements: List of addon requirement dicts, each containing:
            - containerdConfigPatches: list[str] (optional)
            - port_mappings: list[dict] (optional)
            - node_labels: dict[str, str] (optional)
            - networking: dict (optional)
            - featureGates: dict[str, bool] (optional)

    Returns:
        Merged cluster configuration dict

    Example:
        >>> base = {"nodes": [{"role": "control-plane"}]}
        >>> reqs = [
        ...     {"port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}]},
        ...     {"node_labels": {"ingress-ready": "true"}}
        ... ]
        >>> merged = merge_addon_requirements(base, reqs)
    """
    merged = copy.deepcopy(base_config)

    # Collect all requirements from addons
    all_containerd_patches: list[str] = []
    all_port_mappings: list[dict[str, Any]] = []
    all_node_labels: dict[str, str] = {}
    networking_overrides: dict[str, Any] = {}
    feature_gates: dict[str, bool] = {}

    for addon_req in addon_requirements:
        # Collect containerd patches
        if "containerdConfigPatches" in addon_req:
            all_containerd_patches.extend(addon_req["containerdConfigPatches"])

        # Collect port mappings
        if "port_mappings" in addon_req:
            all_port_mappings.extend(addon_req["port_mappings"])

        # Collect node labels
        if "node_labels" in addon_req:
            all_node_labels.update(addon_req["node_labels"])

        # Collect networking settings
        if "networking" in addon_req:
            for key, value in addon_req["networking"].items():
                if key in networking_overrides and networking_overrides[key] != value:
                    logger.warning(
                        f"Networking conflict for '{key}': "
                        f"existing={networking_overrides[key]}, new={value}. Using existing value."
                    )
                else:
                    networking_overrides[key] = value

        # Collect feature gates
        if "featureGates" in addon_req:
            for gate, enabled in addon_req["featureGates"].items():
                if gate in feature_gates and feature_gates[gate] != enabled:
                    logger.warning(
                        f"Feature gate conflict for '{gate}': "
                        f"existing={feature_gates[gate]}, new={enabled}. Using existing value."
                    )
                else:
                    feature_gates[gate] = enabled

    # Apply containerd patches
    if all_containerd_patches:
        if "containerdConfigPatches" not in merged:
            merged["containerdConfigPatches"] = []
        merged["containerdConfigPatches"].extend(all_containerd_patches)
        logger.info(f"Added {len(all_containerd_patches)} containerd config patch(es)")

    # Apply port mappings to control-plane node
    if all_port_mappings:
        control_plane_node = _find_control_plane_node(merged)
        if control_plane_node:
            if "extraPortMappings" not in control_plane_node:
                control_plane_node["extraPortMappings"] = []

            # Deduplicate by (containerPort, hostPort, protocol) tuple
            # Also detect conflicts where same (hostPort, protocol) is used for different container ports
            existing_mappings = {
                (p["containerPort"], p["hostPort"], p.get("protocol", "TCP"))
                for p in control_plane_node["extraPortMappings"]
            }
            # Track (hostPort, protocol) -> containerPort for conflict detection
            # Note: Same host port can be used for both TCP and UDP
            existing_host_port_protocols = {
                (p["hostPort"], p.get("protocol", "TCP")): p["containerPort"]
                for p in control_plane_node["extraPortMappings"]
            }

            added_count = 0
            skipped_count = 0
            for mapping in all_port_mappings:
                container_port = mapping["containerPort"]
                host_port = mapping["hostPort"]
                protocol = mapping.get("protocol", "TCP")
                mapping_tuple = (container_port, host_port, protocol)
                host_port_protocol = (host_port, protocol)

                if mapping_tuple in existing_mappings:
                    # Exact duplicate - skip silently
                    logger.debug(
                        f"Skipping duplicate port mapping: {container_port}:{host_port}/{protocol}"
                    )
                    skipped_count += 1
                elif host_port_protocol in existing_host_port_protocols:
                    # Conflict: same (hostPort, protocol) for different container ports
                    existing_container = existing_host_port_protocols[host_port_protocol]
                    logger.warning(
                        f"Port mapping conflict: host port {host_port}/{protocol} already mapped to "
                        f"container port {existing_container}, cannot map to {container_port}. "
                        f"Skipping conflicting mapping."
                    )
                    skipped_count += 1
                else:
                    # New mapping - add it
                    control_plane_node["extraPortMappings"].append(mapping)
                    existing_mappings.add(mapping_tuple)
                    existing_host_port_protocols[host_port_protocol] = container_port
                    added_count += 1

            if added_count > 0:
                logger.info(f"Added {added_count} port mapping(s) to control-plane node")
            if skipped_count > 0:
                logger.debug(f"Skipped {skipped_count} duplicate/conflicting port mapping(s)")

    # Apply node labels to control-plane node
    if all_node_labels:
        control_plane_node = _find_control_plane_node(merged)
        if control_plane_node:
            _apply_node_labels(control_plane_node, all_node_labels)
            logger.info(f"Added {len(all_node_labels)} node label(s) to control-plane")

    # Apply networking overrides
    if networking_overrides:
        if "networking" not in merged:
            merged["networking"] = {}
        merged["networking"].update(networking_overrides)
        logger.info(f"Applied {len(networking_overrides)} networking override(s)")

    # Apply feature gates
    if feature_gates:
        if "featureGates" not in merged:
            merged["featureGates"] = {}
        merged["featureGates"].update(feature_gates)
        logger.info(f"Applied {len(feature_gates)} feature gate(s)")

    return merged


def _find_control_plane_node(config: dict[str, Any]) -> dict[str, Any] | None:
    """Find the control-plane node in cluster config.

    Args:
        config: Cluster configuration dict

    Returns:
        Control-plane node dict or None if not found
    """
    nodes: list[dict[str, Any]] = config.get("nodes", [])
    for node in nodes:
        if node.get("role") == "control-plane":
            return node
    return None


def _apply_node_labels(node: dict[str, Any], labels: dict[str, str]) -> None:
    """Apply node labels to a node's kubeadm configuration.

    Labels are added to kubeletExtraArgs.node-labels in the InitConfiguration patch.
    Multiple InitConfiguration patches are merged by kubeadm, so we always append
    a new patch to ensure labels from all addons are applied.

    Args:
        node: Node configuration dict
        labels: Dict of label key-value pairs
    """
    if "kubeadmConfigPatches" not in node:
        node["kubeadmConfigPatches"] = []

    # Format labels as comma-separated string
    label_str = ",".join(f"{k}={v}" for k, v in labels.items())

    # Always append a new InitConfiguration patch with the labels
    # Kubeadm will merge multiple patches, so this ensures all addon labels are applied
    patch = f"""kind: InitConfiguration
nodeRegistration:
  kubeletExtraArgs:
    node-labels: "{label_str}"
"""
    node["kubeadmConfigPatches"].append(patch)
    logger.debug(f"Appended InitConfiguration patch with labels: {label_str}")
