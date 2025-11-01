"""Unit tests for validation utilities."""

import pytest

from butler.utils.validation import validate_cluster_name, validate_k8s_version


class TestValidateClusterName:
    """Test cluster name validation."""

    def test_valid_names(self):
        """Test valid cluster names."""
        valid_names = [
            "cluster",
            "my-cluster",
            "cluster-1",
            "a",
            "test123",
            "my-test-cluster-123",
        ]

        for name in valid_names:
            assert validate_cluster_name(name) is True

    def test_empty_name(self):
        """Test empty cluster name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_cluster_name("")

    def test_too_long_name(self):
        """Test cluster name exceeding 63 characters."""
        long_name = "a" * 64

        with pytest.raises(ValueError, match="63 characters or less"):
            validate_cluster_name(long_name)

    def test_invalid_uppercase(self):
        """Test cluster name with uppercase."""
        with pytest.raises(ValueError, match="lowercase alphanumeric"):
            validate_cluster_name("MyCluster")

    def test_invalid_special_characters(self):
        """Test cluster name with special characters."""
        invalid_names = [
            "cluster_name",
            "cluster.name",
            "cluster@name",
            "cluster name",
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="lowercase alphanumeric"):
                validate_cluster_name(name)

    def test_invalid_start_hyphen(self):
        """Test cluster name starting with hyphen."""
        with pytest.raises(ValueError, match="lowercase alphanumeric"):
            validate_cluster_name("-cluster")

    def test_invalid_end_hyphen(self):
        """Test cluster name ending with hyphen."""
        with pytest.raises(ValueError, match="lowercase alphanumeric"):
            validate_cluster_name("cluster-")


class TestValidateK8sVersion:
    """Test Kubernetes version validation."""

    def test_valid_versions(self):
        """Test valid Kubernetes versions."""
        valid_versions = [
            "v1.30.0",
            "v1.34.0",
            "v2.0.0",
            "v1.30",
            "v1.0",
        ]

        for version in valid_versions:
            assert validate_k8s_version(version) is True

    def test_empty_version(self):
        """Test empty version."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_k8s_version("")

    def test_invalid_format_no_v_prefix(self):
        """Test version without 'v' prefix."""
        with pytest.raises(ValueError, match="Invalid Kubernetes version format"):
            validate_k8s_version("1.30.0")

    def test_invalid_format_single_number(self):
        """Test version with single number."""
        with pytest.raises(ValueError, match="Invalid Kubernetes version format"):
            validate_k8s_version("v1")

    def test_invalid_format_letters(self):
        """Test version with letters."""
        with pytest.raises(ValueError, match="Invalid Kubernetes version format"):
            validate_k8s_version("v1.30.beta1")

    def test_invalid_format_four_parts(self):
        """Test version with four parts."""
        with pytest.raises(ValueError, match="Invalid Kubernetes version format"):
            validate_k8s_version("v1.30.0.1")
