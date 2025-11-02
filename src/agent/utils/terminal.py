"""Terminal utilities for CLI operations.

This module provides terminal control functions for the CLI interface.
"""

import os
import sys


def clear_screen() -> bool:
    """Clear the terminal screen.

    Uses a multi-strategy approach for cross-platform compatibility:
    1. ANSI escape codes (works on most modern terminals)
    2. Platform-specific commands as fallback

    Returns:
        True if screen was cleared successfully, False otherwise
    """
    try:
        # Try ANSI escape codes first (universal approach)
        # \033[2J clears the screen, \033[H moves cursor to home
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        return True
    except Exception:
        # Fallback to platform-specific commands
        try:
            if os.name == "nt":  # Windows
                os.system("cls")
            else:  # Unix/Linux/macOS
                os.system("clear")
            return True
        except Exception:
            return False
