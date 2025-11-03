"""Base class for keybinding handlers.

This module defines the interface that all keybinding handlers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class KeybindingHandler(ABC):
    """Abstract base class for keybinding handlers.

    Each handler represents a specific keyboard shortcut and defines how to
    handle events when that shortcut is triggered.

    Subclasses must implement:
    - trigger_key: The key or key combination that activates this handler
    - description: Human-readable description for help text
    - handle(event): The action to perform when the key is pressed

    Example:
        class MyHandler(KeybindingHandler):
            @property
            def trigger_key(self) -> str:
                return "c-x"  # Ctrl+X

            @property
            def description(self) -> str:
                return "Execute custom action"

            def handle(self, event: Any) -> None:
                # Perform action using event.app, event.current_buffer, etc.
                event.app.current_buffer.text = "Custom action triggered"
    """

    @property
    @abstractmethod
    def trigger_key(self) -> str:
        """Key or key combination that triggers this handler.

        Returns:
            String representation of the key (e.g., "escape", "!", "c-x" for Ctrl+X)
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this handler does.

        Returns:
            Description string for help text and documentation
        """
        pass

    @abstractmethod
    def handle(self, event: Any) -> None:
        """Handle the keybinding event.

        This method is called when the trigger key is pressed. It receives
        a prompt_toolkit event object that provides access to the application
        state, current buffer, and other context.

        Args:
            event: prompt_toolkit KeyPressEvent containing app, buffer, etc.
        """
        pass
