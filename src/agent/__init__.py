"""AI-powered Kubernetes infrastructure management agent.

Provides a conversational interface for managing KinD clusters and
Kubernetes infrastructure using natural language.
"""

from importlib.metadata import PackageNotFoundError, version

from agent.agent import Agent
from agent.config import AgentConfig

# Read version from package metadata with fallback
try:
    __version__ = version("butler-agent")
except PackageNotFoundError:
    # Fallback for development/testing environments
    __version__ = "0.1.5"

__all__ = [
    "Agent",
    "AgentConfig",
    "__version__",
]
