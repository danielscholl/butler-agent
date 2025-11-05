"""Cluster add-on management for Butler Agent.

This module provides a modular system for installing Kubernetes add-ons
during or after cluster creation.
"""

from agent.cluster.addons.ingress_nginx import IngressNginxAddon
from agent.cluster.addons.manager import AddonManager

__all__ = ["AddonManager", "IngressNginxAddon"]
