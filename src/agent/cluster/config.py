"""KinD cluster configuration templates and management."""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

# Template directory containing built-in KinD configurations
_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Lock for thread-safe template caching
_template_lock = threading.Lock()


def _load_builtin_template(template_name: str) -> str:
    """Load a built-in template from the templates directory.

    Args:
        template_name: Name of the template (e.g., 'minimal', 'default', 'custom')

    Returns:
        Template content as a string

    Raises:
        FileNotFoundError: If template file doesn't exist
        ValueError: If template file cannot be read
    """
    template_path = _TEMPLATE_DIR / f"{template_name}.yaml"

    if not template_path.exists():
        raise FileNotFoundError(f"Built-in template not found: {template_path}")

    try:
        with open(template_path) as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error reading built-in template {template_path}: {e}") from e


# Load built-in templates from YAML files
# These are loaded lazily to avoid file I/O at import time
# Type is Union because values start as Callable and become str after loading
TEMPLATES: dict[str, str | Callable[[], str]] = {
    "minimal": lambda: _load_builtin_template("minimal"),
    "default": lambda: _load_builtin_template("default"),
    "custom": lambda: _load_builtin_template("custom"),
}


def _get_template(template_name: str) -> str:
    """Get a template by name, loading it if necessary.

    Thread-safe lazy loading with caching. Uses a lock to prevent race conditions
    when multiple threads access the same template simultaneously.

    Args:
        template_name: Name of the template

    Returns:
        Template content as a string

    Raises:
        ValueError: If template doesn't exist
    """
    if template_name not in TEMPLATES:
        raise ValueError(
            f"Invalid template: {template_name}. Must be one of: {', '.join(TEMPLATES.keys())}"
        )

    template = TEMPLATES[template_name]
    # If it's a lambda function, call it to load the template
    if callable(template):
        # Use lock to prevent race condition in multi-threaded environments
        with _template_lock:
            # Double-check after acquiring lock (another thread might have loaded it)
            template = TEMPLATES[template_name]
            if callable(template):
                # Cache the loaded template
                template_content = template()
                TEMPLATES[template_name] = template_content
                return template_content
            # Already loaded by another thread
            return template
    # Already loaded and cached
    return template


def discover_config_file(config_name: str, infra_dir: Path) -> tuple[Path | None, str]:
    """Discover custom KinD configuration file with priority-based search.

    Priority order:
    1. Named custom configs: kind-{config_name}.yaml (when config_name not in built-in templates)
    2. Default custom config: kind-config.yaml (when config_name is "default" or "custom")
    3. Returns None if no custom config found (triggers built-in template fallback)

    Args:
        config_name: Configuration name to discover
        infra_dir: Path to infrastructure directory

    Returns:
        Tuple of (filepath, source_description) or (None, reason) if not found
    """
    # Ensure infra directory exists
    if not infra_dir.exists():
        return None, f"Infrastructure directory does not exist: {infra_dir}"

    # Priority 1: Named custom configs (when not using built-in template names)
    if config_name not in TEMPLATES:
        named_config = infra_dir / f"kind-{config_name}.yaml"
        if named_config.exists():
            return named_config, f"Named custom config: kind-{config_name}.yaml"
        return None, f"Named config kind-{config_name}.yaml not found"

    # Priority 2: Default custom config (for "default" or "custom" templates)
    if config_name in ["default", "custom"]:
        default_config = infra_dir / "kind-config.yaml"
        if default_config.exists():
            return default_config, "Default custom config: kind-config.yaml"

    # No custom config found - will fall back to built-in templates
    return None, f"No custom config found, using built-in template: {config_name}"


def load_config_from_file(filepath: Path, cluster_name: str) -> str:
    """Load and process KinD configuration from file.

    Args:
        filepath: Path to configuration file
        cluster_name: Cluster name to replace {name} placeholder

    Returns:
        Processed configuration YAML string

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If YAML is invalid or doesn't pass validation
        PermissionError: If file cannot be read
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")

    try:
        with open(filepath) as f:
            config_content = f.read()
    except PermissionError as e:
        raise PermissionError(f"Cannot read configuration file {filepath}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error reading configuration file {filepath}: {e}") from e

    # Replace {name} placeholder with actual cluster name
    config_content = config_content.replace("{name}", cluster_name)

    # Validate YAML syntax
    try:
        yaml.safe_load(config_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {filepath}: {e}") from e

    # Validate KinD cluster config structure
    validate_cluster_config(config_content)

    return config_content


def get_cluster_config(
    template: str, name: str, infra_dir: Path | None = None, **kwargs: Any
) -> tuple[str, str]:
    """Generate cluster configuration with automatic discovery.

    Configuration discovery (automatic):
    1. Named custom: ./data/infra/kind-{template}.yaml (when template != minimal/default/custom)
    2. Default custom: ./data/infra/kind-config.yaml (when template = default/custom)
    3. Built-in templates: Fallback for minimal/default/custom

    Args:
        template: Template name or custom config name
        name: Cluster name
        infra_dir: Path to infrastructure directory (optional, for custom configs)
        **kwargs: Additional template variables

    Returns:
        Tuple of (config_content, source_description) where source_description
        indicates whether a custom file or built-in template was used

    Raises:
        ValueError: If template/config is invalid
        FileNotFoundError: If a named custom config is requested but not found
    """
    source_description = ""

    # Try to discover custom configuration file if infra_dir is provided
    if infra_dir:
        config_path, description = discover_config_file(template, infra_dir)
        if config_path:
            # Custom config found - load it
            try:
                config_content = load_config_from_file(config_path, name)
                return config_content, description
            except Exception as e:
                # If loading fails, raise the error (don't fall back to templates)
                raise ValueError(f"Failed to load custom config: {e}") from e
        source_description = description

    # No custom config found - use built-in templates
    if template not in TEMPLATES:
        # If a named config was requested but not found, raise error
        if infra_dir and infra_dir.exists():
            raise FileNotFoundError(
                f"Named configuration '{template}' not found. "
                f"Expected file: {infra_dir / f'kind-{template}.yaml'}. "
                f"Available templates: {', '.join(TEMPLATES.keys())}"
            )
        # No infra_dir provided, invalid template name
        raise ValueError(
            f"Invalid template: {template}. Must be one of: {', '.join(TEMPLATES.keys())}"
        )

    # Use built-in template
    config = _get_template(template)
    variables = {"name": name, **kwargs}
    rendered_config = config.format(**variables)

    if not source_description:
        source_description = f"Built-in template: {template}"

    return rendered_config, source_description


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
