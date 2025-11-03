"""Clear prompt handler for ESC key.

This handler clears the current prompt text when the ESC key is pressed.
"""

import logging
from typing import Any

from agent.utils.keybindings.handler import KeybindingHandler

logger = logging.getLogger(__name__)


class ClearPromptHandler(KeybindingHandler):
    """Handler that clears the prompt text when ESC is pressed.

    This provides a quick way to clear the current input without having to
    manually delete all text. Useful when you change your mind about a query
    or want to start fresh.

    Example:
        User types: "create a cluster called..."
        User presses ESC
        Prompt is now empty: ""
    """

    @property
    def trigger_key(self) -> str:
        """ESC key triggers this handler.

        Returns:
            "escape" - prompt_toolkit key name for ESC
        """
        return "escape"

    @property
    def description(self) -> str:
        """Description of what this handler does.

        Returns:
            Human-readable description
        """
        return "Clear the current prompt text"

    def handle(self, event: Any) -> None:
        """Clear the prompt buffer.

        Args:
            event: prompt_toolkit KeyPressEvent
        """
        logger.debug("ClearPromptHandler: Clearing prompt text")
        event.app.current_buffer.text = ""
