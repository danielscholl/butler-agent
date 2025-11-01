"""Activity tracking for Butler Agent.

This module provides a singleton for tracking the current activity/operation
being performed by the agent.
"""

from typing import Optional


class ActivityTracker:
    """Singleton for tracking current agent activity."""

    _instance: Optional["ActivityTracker"] = None
    _current_activity: Optional[str] = None

    def __new__(cls) -> "ActivityTracker":
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_activity(self, message: str) -> None:
        """Set the current activity message.

        Args:
            message: Description of current activity
        """
        self._current_activity = message

    def get_current(self) -> Optional[str]:
        """Get the current activity message.

        Returns:
            Current activity message or None
        """
        return self._current_activity

    def reset(self) -> None:
        """Reset the current activity."""
        self._current_activity = None


# Global instance
activity_tracker = ActivityTracker()
