"""Terminal utilities for CLI operations.

This module provides terminal control functions for the CLI interface.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


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


def execute_shell_command(
    command: str, timeout: int = 30, cwd: str | None = None
) -> tuple[int, str, str]:
    """Execute shell command and return results.

    This function executes a shell command and captures its output. It uses
    subprocess.run with shell=True to support complex commands with pipes,
    redirects, and environment variable expansion.

    WARNING: This function uses shell=True, which can be dangerous if executing
    untrusted input. In Butler's interactive mode, the user types the command
    directly, so this is safe. Do not use this function with programmatically
    generated commands from untrusted sources.

    Args:
        command: Shell command to execute
        timeout: Command timeout in seconds (default: 30)
        cwd: Working directory for command execution (default: current directory)

    Returns:
        Tuple of (exit_code, stdout, stderr)
        - exit_code: Process exit code (0 = success, non-zero = error)
        - stdout: Standard output as string
        - stderr: Standard error as string

    Example:
        >>> exit_code, stdout, stderr = execute_shell_command("ls -la")
        >>> if exit_code == 0:
        ...     print(stdout)
    """
    logger.debug(f"Executing shell command: {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        logger.debug(f"Command completed with exit code {result.returncode}")
        return (result.returncode, result.stdout, result.stderr)

    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout}s"
        logger.warning(f"Shell command timeout: {command}")
        return (124, "", error_msg)  # 124 is conventional timeout exit code

    except Exception as e:
        error_msg = f"Command execution failed: {str(e)}"
        logger.error(f"Shell command error: {error_msg}")
        return (1, "", error_msg)
