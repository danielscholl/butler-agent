"""Keybinding manager for registering and managing keyboard shortcuts.

This module provides the KeybindingManager class that serves as a central
registry for all keybinding handlers in Butler's interactive mode.
"""

import logging
from typing import Any

from prompt_toolkit.key_binding import KeyBindings

from agent.utils.keybindings.handler import KeybindingHandler

logger = logging.getLogger(__name__)


class KeybindingManager:
    """Manages keybinding handlers for Butler's interactive prompt.

    The KeybindingManager maintains a registry of KeybindingHandler instances
    and provides methods to register, unregister, and apply handlers to
    prompt_toolkit's KeyBindings object.

    Example:
        manager = KeybindingManager()
        manager.register_handler(ClearPromptHandler())
        manager.register_handler(ShellCommandHandler())

        key_bindings = manager.create_keybindings()
        session = PromptSession(key_bindings=key_bindings)
    """

    def __init__(self) -> None:
        """Initialize the keybinding manager with an empty registry."""
        self._handlers: dict[str, KeybindingHandler] = {}
        logger.debug("KeybindingManager initialized")

    def register_handler(self, handler: KeybindingHandler) -> None:
        """Register a keybinding handler.

        If a handler with the same trigger key is already registered, the existing handler
        will be replaced and a warning will be logged.

        Args:
            handler: KeybindingHandler instance to register
        """
        trigger_key = handler.trigger_key
        if trigger_key in self._handlers:
            logger.warning(
                f"Handler for trigger key '{trigger_key}' already registered. "
                f"Replacing existing handler."
            )

        self._handlers[trigger_key] = handler
        logger.info(f"Registered keybinding handler: {trigger_key} - {handler.description}")

    def unregister_handler(self, trigger_key: str) -> bool:
        """Unregister a keybinding handler by its trigger key.

        Args:
            trigger_key: The trigger key of the handler to remove

        Returns:
            True if handler was removed, False if not found
        """
        if trigger_key in self._handlers:
            self._handlers.pop(trigger_key)
            logger.info(f"Unregistered keybinding handler: {trigger_key}")
            return True

        logger.warning(f"No handler registered for trigger key '{trigger_key}'")
        return False

    def get_handlers(self) -> list[KeybindingHandler]:
        """Get list of all registered handlers.

        Returns:
            List of KeybindingHandler instances
        """
        return list(self._handlers.values())

    def get_help_text(self) -> str:
        """Generate formatted help text for all registered keybindings.

        Returns:
            Formatted string describing all available keybindings
        """
        if not self._handlers:
            return "No keybindings registered."

        help_lines = ["Available Keyboard Shortcuts:", ""]
        for handler in self._handlers.values():
            # Format trigger key for display
            trigger_display = handler.trigger_key.upper()
            if handler.trigger_key == "escape":
                trigger_display = "ESC"

            help_lines.append(f"  {trigger_display:10} - {handler.description}")

        return "\n".join(help_lines)

    def create_keybindings(self) -> KeyBindings:
        """Create prompt_toolkit KeyBindings object with all registered handlers.

        Returns:
            KeyBindings instance with all handlers bound
        """
        kb = KeyBindings()

        for trigger_key, handler in self._handlers.items():
            logger.debug(f"Binding key '{trigger_key}' to {handler.__class__.__name__}")

            # Create a closure to capture the handler
            def make_handler(h: KeybindingHandler) -> Any:
                def _handler(event: Any) -> None:
                    try:
                        # Check if handler has conditional logic
                        if hasattr(h, "should_handle") and not h.should_handle(event):
                            # Handler doesn't want to process this event, skip it
                            return

                        h.handle(event)
                    except Exception as e:
                        logger.error(f"Error in keybinding handler {h.__class__.__name__}: {e}")

                return _handler

            # Add the keybinding
            kb.add(trigger_key)(make_handler(handler))

        logger.info(f"Created KeyBindings with {len(self._handlers)} handlers")
        return kb
