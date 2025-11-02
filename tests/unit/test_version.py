"""Unit tests for version management."""

import tomllib
from pathlib import Path

from agent import __version__


def test_version_format():
    """Test version follows semantic versioning format."""
    # Version should be in format X.Y.Z or X.Y.Z.devN
    parts = __version__.split(".")
    assert len(parts) >= 3, f"Version {__version__} should have at least 3 parts"

    # First three parts should be numeric
    major, minor, patch_full = parts[0], parts[1], parts[2]
    # Extract patch number (before any suffix like .devN or -suffix or +build)
    patch = patch_full.split("-")[0].split("+")[0]

    assert major.isdigit(), f"Major version '{major}' should be numeric"
    assert minor.isdigit(), f"Minor version '{minor}' should be numeric"

    # Patch should be numeric, or contain 'dev' for development versions (e.g., dev0, 0.dev0, 1.dev2)
    if "dev" in patch:
        # Extract numeric part before 'dev'
        patch_base = patch.split("dev")[0].rstrip(".")
        assert (
            patch_base == "" or patch_base.isdigit()
        ), f"Patch version '{patch}' should have numeric base before dev suffix"
    else:
        assert patch.isdigit(), f"Patch version '{patch}' should be numeric"


def test_version_matches_pyproject():
    """Test version matches pyproject.toml."""

    # Read version from pyproject.toml
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)

    expected_version = pyproject_data["project"]["version"]

    # Version should match or be compatible (dev versions are ok during development)
    assert __version__ == expected_version or __version__.startswith(
        expected_version
    ), f"Version {__version__} should match pyproject.toml version {expected_version}"


def test_version_accessible():
    """Test version can be imported and is a string."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0
