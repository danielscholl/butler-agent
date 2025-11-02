"""Unit tests for cluster configuration management."""

from pathlib import Path

import pytest
import yaml


class TestClusterConfigTemplates:
    """Test cluster configuration templates."""

    def test_builtin_templates_exist(self):
        """Test that all built-in template files exist."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        
        expected_templates = ["minimal.yaml", "default.yaml", "custom.yaml"]
        for template in expected_templates:
            template_path = template_dir / template
            assert template_path.exists(), f"Template file {template} should exist"

    def test_builtin_templates_valid_yaml(self):
        """Test that all built-in templates are valid YAML."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        
        for template in ["minimal.yaml", "default.yaml", "custom.yaml"]:
            template_path = template_dir / template
            with open(template_path) as f:
                content = f.read()
            
            # Should be valid YAML (with placeholder)
            # We can't fully parse it because of {name} placeholder, but we can check structure
            assert "kind: Cluster" in content
            assert "apiVersion: kind.x-k8s.io/v1alpha4" in content
            assert "name: {name}" in content
            assert "nodes:" in content

    def test_minimal_template_structure(self):
        """Test minimal template has correct structure."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        template_path = template_dir / "minimal.yaml"
        
        with open(template_path) as f:
            content = f.read()
        
        # Minimal should have only control plane
        assert "- role: control-plane" in content
        # Should not have kubeadmConfigPatches
        assert "kubeadmConfigPatches" not in content
        # Should not have multiple nodes
        lines = content.strip().split("\n")
        control_plane_count = sum(1 for line in lines if "role: control-plane" in line)
        worker_count = sum(1 for line in lines if "role: worker" in line)
        assert control_plane_count == 1
        assert worker_count == 0

    def test_default_template_structure(self):
        """Test default template has correct structure."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        template_path = template_dir / "default.yaml"
        
        with open(template_path) as f:
            content = f.read()
        
        # Default should have control plane with ingress config and one worker
        assert "- role: control-plane" in content
        assert "kubeadmConfigPatches" in content
        assert "ingress-ready=true" in content
        assert "containerPort: 80" in content
        assert "containerPort: 443" in content
        
        # Should have exactly one worker
        lines = content.strip().split("\n")
        worker_count = sum(1 for line in lines if "role: worker" in line)
        assert worker_count == 1

    def test_custom_template_structure(self):
        """Test custom template has correct structure."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        template_path = template_dir / "custom.yaml"
        
        with open(template_path) as f:
            content = f.read()
        
        # Custom should have control plane with ingress config and three workers
        assert "- role: control-plane" in content
        assert "kubeadmConfigPatches" in content
        assert "ingress-ready=true" in content
        
        # Should have exactly three workers
        lines = content.strip().split("\n")
        worker_count = sum(1 for line in lines if "role: worker" in line)
        assert worker_count == 3

    def test_template_formatting(self):
        """Test that templates can be formatted with cluster name."""
        template_dir = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
        
        for template_name in ["minimal", "default", "custom"]:
            template_path = template_dir / f"{template_name}.yaml"
            with open(template_path) as f:
                content = f.read()
            
            # Test formatting with a cluster name
            formatted = content.format(name="test-cluster")
            assert "test-cluster" in formatted
            assert "{name}" not in formatted
            
            # Verify formatted content is valid YAML
            parsed = yaml.safe_load(formatted)
            assert parsed["kind"] == "Cluster"
            assert parsed["apiVersion"] == "kind.x-k8s.io/v1alpha4"
            assert parsed["name"] == "test-cluster"
            assert "nodes" in parsed
            assert len(parsed["nodes"]) > 0
