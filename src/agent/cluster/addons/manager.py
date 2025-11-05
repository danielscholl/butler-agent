"""Addon manager for orchestrating addon installations."""

import logging
from pathlib import Path
from typing import Any

from agent.cluster.addons.ingress_nginx import IngressNginxAddon

logger = logging.getLogger(__name__)


class AddonManager:
    """Manages installation of cluster add-ons."""

    def __init__(self, cluster_name: str, kubeconfig_path: Path):
        """Initialize addon manager.

        Args:
            cluster_name: Name of the cluster
            kubeconfig_path: Path to cluster's kubeconfig file
        """
        self.cluster_name = cluster_name
        self.kubeconfig_path = kubeconfig_path
        self._addon_registry: dict[str, type] = {}
        self._register_addons()

    def _register_addons(self) -> None:
        """Register available addons."""
        self._addon_registry = {
            "ingress": IngressNginxAddon,
            "ingress-nginx": IngressNginxAddon,
            "nginx": IngressNginxAddon,
        }

    def _validate_addon_name(self, name: str) -> str:
        """Validate and normalize addon name.

        Args:
            name: Addon name

        Returns:
            Normalized addon name

        Raises:
            ValueError: If addon name is invalid
        """
        name_lower = name.lower().strip()
        if name_lower not in self._addon_registry:
            available = ", ".join(sorted(set(self._addon_registry.keys())))
            raise ValueError(f"Unknown addon: '{name}'. Available addons: {available}")
        return name_lower

    def _get_addon_instance(self, name: str, config: dict[str, Any] | None = None):
        """Get an addon instance.

        Args:
            name: Addon name
            config: Optional addon configuration

        Returns:
            Addon instance
        """
        addon_class = self._addon_registry[name]
        return addon_class(self.cluster_name, self.kubeconfig_path, config)

    def install_addons(
        self, addon_names: list[str], configs: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Install multiple addons.

        Args:
            addon_names: List of addon names to install
            configs: Optional dict of addon-specific configurations

        Returns:
            Dict with installation results:
            - success: bool (True if all succeeded or were skipped)
            - results: dict of addon_name -> result
            - failed: list of failed addon names
            - message: summary message
        """
        if not addon_names:
            return {
                "success": True,
                "results": {},
                "failed": [],
                "message": "No addons specified",
            }

        configs = configs or {}
        results = {}
        failed = []

        # Deduplicate and normalize addon names
        unique_addons = []
        seen = set()
        for name in addon_names:
            try:
                normalized = self._validate_addon_name(name)
                if normalized not in seen:
                    unique_addons.append(normalized)
                    seen.add(normalized)
            except ValueError as e:
                logger.warning(str(e))
                failed.append(name)
                results[name] = {
                    "success": False,
                    "error": str(e),
                    "message": f"Invalid addon name: {name}",
                }

        logger.info(
            f"Installing {len(unique_addons)} addon(s) for cluster '{self.cluster_name}': "
            f"{', '.join(unique_addons)}"
        )

        # Install addons in order
        # Future: Could implement dependency ordering here
        for addon_name in unique_addons:
            try:
                logger.info(f"Processing addon: {addon_name}")
                addon_config = configs.get(addon_name)
                addon = self._get_addon_instance(addon_name, addon_config)
                result = addon.run()
                results[addon_name] = result

                if not result.get("success"):
                    failed.append(addon_name)
                    logger.warning(
                        f"Addon '{addon_name}' installation failed (continuing with others)"
                    )

            except Exception as e:
                logger.error(f"Unexpected error installing addon '{addon_name}': {e}")
                failed.append(addon_name)
                results[addon_name] = {
                    "success": False,
                    "error": str(e),
                    "message": f"Unexpected error: {e}",
                }

        # Calculate success
        total = len(unique_addons)
        succeeded = sum(1 for r in results.values() if r.get("success"))
        skipped = sum(1 for r in results.values() if r.get("skipped"))

        success = len(failed) == 0
        message = f"Addons: {succeeded}/{total} succeeded"
        if skipped > 0:
            message += f", {skipped} already installed"
        if failed:
            message += f", {len(failed)} failed: {', '.join(failed)}"

        return {
            "success": success,
            "results": results,
            "failed": failed,
            "message": message,
        }
