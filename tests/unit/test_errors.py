"""Unit tests for error classes."""

import pytest

from butler.utils.errors import (
    ClusterAlreadyExistsError,
    ClusterNotFoundError,
    ConfigurationError,
    KindCommandError,
)


class TestErrorClasses:
    """Test custom error classes."""

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Test config error")
        assert str(error) == "Test config error"
        assert isinstance(error, Exception)

    def test_cluster_not_found_error(self):
        """Test ClusterNotFoundError."""
        error = ClusterNotFoundError("Cluster not found")
        assert str(error) == "Cluster not found"
        assert isinstance(error, Exception)

    def test_cluster_already_exists_error(self):
        """Test ClusterAlreadyExistsError."""
        error = ClusterAlreadyExistsError("Cluster exists")
        assert str(error) == "Cluster exists"
        assert isinstance(error, Exception)

    def test_kind_command_error(self):
        """Test KindCommandError."""
        error = KindCommandError("Command failed")
        assert str(error) == "Command failed"
        assert isinstance(error, Exception)
