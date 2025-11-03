"""Unit tests for cluster configuration management."""

from pathlib import Path

import yaml


class TestClusterConfigTemplates:
    """Test cluster configuration templates."""

    # Class-level constants to avoid duplication
    TEMPLATE_DIR = Path(__file__).parent.parent.parent / "src" / "agent" / "cluster" / "templates"
    TEMPLATE_NAMES = ["minimal", "default", "custom"]
    TEMPLATE_FILES = [f"{name}.yaml" for name in TEMPLATE_NAMES]

    def test_builtin_templates_exist(self):
        """Test that all built-in template files exist."""
        for template in self.TEMPLATE_FILES:
            template_path = self.TEMPLATE_DIR / template
            assert template_path.exists(), f"Template file {template} should exist"

    def test_builtin_templates_valid_yaml(self):
        """Test that all built-in templates are valid YAML."""
        for template in self.TEMPLATE_FILES:
            template_path = self.TEMPLATE_DIR / template
            with open(template_path) as f:
                content = f.read()
            
            # Basic structure validation before formatting
            # Full YAML parsing is done in test_template_formatting after {name} is replaced
            assert "kind: Cluster" in content
            assert "apiVersion: kind.x-k8s.io/v1alpha4" in content
            assert "name: {name}" in content
            assert "nodes:" in content

    def test_minimal_template_structure(self):
        """Test minimal template has correct structure."""
        template_path = self.TEMPLATE_DIR / "minimal.yaml"
        
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
        template_path = self.TEMPLATE_DIR / "default.yaml"
        
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
        template_path = self.TEMPLATE_DIR / "custom.yaml"
        
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
        for template_name in self.TEMPLATE_NAMES:
            template_path = self.TEMPLATE_DIR / f"{template_name}.yaml"
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
