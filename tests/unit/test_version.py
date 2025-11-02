"""Unit tests for version management."""



def test_version_format():
    """Test version follows semantic versioning format."""
    from agent import __version__

    # Version should be in format X.Y.Z or X.Y.Z.devN
    parts = __version__.split(".")
    assert len(parts) >= 3, f"Version {__version__} should have at least 3 parts"

    # First three parts should be numeric
    major, minor, patch = parts[0], parts[1], parts[2].split("-")[0].split("+")[0]
    assert major.isdigit(), f"Major version '{major}' should be numeric"
    assert minor.isdigit(), f"Minor version '{minor}' should be numeric"
    assert patch.isdigit() or patch.endswith(
        "dev0"
    ), f"Patch version '{patch}' should be numeric or dev"


def test_version_matches_pyproject():
    """Test version matches pyproject.toml."""
    import tomllib
    from pathlib import Path

    from agent import __version__

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
    from agent import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0
