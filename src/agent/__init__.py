"""AI-powered Kubernetes infrastructure management agent.

Provides a conversational interface for managing KinD clusters and
Kubernetes infrastructure using natural language.
"""

from agent.agent import Agent
from agent.config import AgentConfig

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentConfig",
    "__version__",
]
