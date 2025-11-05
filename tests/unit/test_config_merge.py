"""Tests for cluster config merge utilities."""

import pytest

from agent.cluster.config_merge import merge_addon_requirements


def test_merge_empty_requirements():
    """Test merging with no addon requirements."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = []

    result = merge_addon_requirements(base_config, addon_requirements)

    assert result == base_config
    assert result is not base_config  # Should be a copy


def test_merge_port_mappings():
    """Test merging port mapping requirements."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {"port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}]},
        {"port_mappings": [{"containerPort": 443, "hostPort": 443, "protocol": "TCP"}]},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    assert "extraPortMappings" in result["nodes"][0]
    port_mappings = result["nodes"][0]["extraPortMappings"]
    assert len(port_mappings) == 2
    assert {"containerPort": 80, "hostPort": 80, "protocol": "TCP"} in port_mappings
    assert {"containerPort": 443, "hostPort": 443, "protocol": "TCP"} in port_mappings


def test_merge_port_mappings_dedupe():
    """Test that duplicate port mappings are deduplicated."""
    base_config = {
        "nodes": [
            {
                "role": "control-plane",
                "extraPortMappings": [
                    {"containerPort": 80, "hostPort": 80, "protocol": "TCP"}
                ],
            }
        ]
    }
    addon_requirements = [
        {"port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}]},
        {"port_mappings": [{"containerPort": 443, "hostPort": 443, "protocol": "TCP"}]},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    port_mappings = result["nodes"][0]["extraPortMappings"]
    # Should only add 443, not duplicate 80
    assert len(port_mappings) == 2


def test_merge_node_labels():
    """Test merging node label requirements."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {"node_labels": {"ingress-ready": "true"}},
        {"node_labels": {"storage-class": "local"}},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    # Should have kubeadmConfigPatches with labels
    assert "kubeadmConfigPatches" in result["nodes"][0]
    patches = result["nodes"][0]["kubeadmConfigPatches"]
    assert len(patches) > 0

    # Check that patch contains labels
    patch_text = patches[0]
    assert "ingress-ready=true" in patch_text
    assert "storage-class=local" in patch_text


def test_merge_containerd_patches():
    """Test merging containerd config patches."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {
            "containerdConfigPatches": [
                '[plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]'
            ]
        },
        {"containerdConfigPatches": ['[plugins."some.other.config"]']},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    assert "containerdConfigPatches" in result
    assert len(result["containerdConfigPatches"]) == 2


def test_merge_multiple_requirements():
    """Test merging multiple requirement types from same addon."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {
            "port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}],
            "node_labels": {"ingress-ready": "true"},
            "containerdConfigPatches": ['[plugins."test"]'],
        }
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    # Check all requirements were applied
    assert "extraPortMappings" in result["nodes"][0]
    assert len(result["nodes"][0]["extraPortMappings"]) == 1

    assert "kubeadmConfigPatches" in result["nodes"][0]
    patch_text = result["nodes"][0]["kubeadmConfigPatches"][0]
    assert "ingress-ready=true" in patch_text

    assert "containerdConfigPatches" in result
    assert len(result["containerdConfigPatches"]) == 1


def test_merge_preserves_base_config():
    """Test that base config is not mutated."""
    base_config = {
        "nodes": [
            {
                "role": "control-plane",
                "extraPortMappings": [
                    {"containerPort": 6443, "hostPort": 6443, "protocol": "TCP"}
                ],
            }
        ]
    }
    addon_requirements = [
        {"port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}]}
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    # Original base_config should be unchanged
    assert len(base_config["nodes"][0]["extraPortMappings"]) == 1

    # Result should have both
    assert len(result["nodes"][0]["extraPortMappings"]) == 2


def test_merge_no_control_plane_node():
    """Test merging when there's no control-plane node (edge case)."""
    base_config = {"nodes": [{"role": "worker"}]}
    addon_requirements = [
        {"port_mappings": [{"containerPort": 80, "hostPort": 80, "protocol": "TCP"}]}
    ]

    # Should not crash, just skip port mapping
    result = merge_addon_requirements(base_config, addon_requirements)

    assert result["nodes"][0]["role"] == "worker"
    assert "extraPortMappings" not in result["nodes"][0]


def test_merge_networking_settings():
    """Test merging networking configuration."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {"networking": {"podSubnet": "10.244.0.0/16"}},
        {"networking": {"serviceSubnet": "10.96.0.0/12"}},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    assert "networking" in result
    assert result["networking"]["podSubnet"] == "10.244.0.0/16"
    assert result["networking"]["serviceSubnet"] == "10.96.0.0/12"


def test_merge_feature_gates():
    """Test merging feature gates."""
    base_config = {"nodes": [{"role": "control-plane"}]}
    addon_requirements = [
        {"featureGates": {"GatewayAPI": True}},
        {"featureGates": {"NetworkPolicy": True}},
    ]

    result = merge_addon_requirements(base_config, addon_requirements)

    assert "featureGates" in result
    assert result["featureGates"]["GatewayAPI"] is True
    assert result["featureGates"]["NetworkPolicy"] is True
