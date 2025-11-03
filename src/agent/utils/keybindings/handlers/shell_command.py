"""Shell command handler for ! key.

This handler allows executing shell commands directly from Butler's interactive
prompt by pressing '!' followed by the command.
"""

import logging
from typing import Any

from rich.console import Console

from agent.utils.keybindings.handler import KeybindingHandler
from agent.utils.terminal import execute_shell_command

logger = logging.getLogger(__name__)
console = Console()


class ShellCommandHandler(KeybindingHandler):
    """Handler that executes shell commands when ! is pressed.

    This handler provides a quick way to run shell commands without leaving
    Butler's interactive session. When the user presses '!' at the beginning
    of a line (or when the buffer is empty), they can type a shell command
    that will be executed immediately.

    The output (stdout, stderr, and exit code) is displayed inline, and then
    the prompt returns to normal Butler mode.

    Example usage:
        !ls -la                 # List files
        !docker ps              # Show containers
        !kubectl get pods       # List Kubernetes pods
        !git status            # Check git status

    Security note:
        Commands are executed with the user's permissions in their current
        directory. Only commands typed directly by the user are executed -
        there is no risk of command injection from external sources.
    """

    @property
    def trigger_key(self) -> str:
        """! key triggers this handler.

        Returns:
            "!" - the exclamation mark key
        """
        return "!"

    @property
    def description(self) -> str:
        """Description of what this handler does.

        Returns:
            Human-readable description
        """
        return "Execute shell command directly (e.g., !ls, !docker ps)"

    def handle(self, event: Any) -> None:
        """Handle shell command execution.

        When '!' is pressed and the buffer is empty or starts with '!', this
        handler intercepts the input, prompts for a command, executes it, and
        displays the results.

        Args:
            event: prompt_toolkit KeyPressEvent
        """
        buffer = event.app.current_buffer
        current_text = buffer.text.strip()

        # Only trigger if buffer is empty or already starts with !
        # This prevents triggering in the middle of Butler queries
        if current_text and not current_text.startswith("!"):
            # Let the ! character be inserted normally
            buffer.insert_text("!")
            return

        logger.debug("ShellCommandHandler: Triggering shell command mode")

        # If buffer is empty, insert ! to indicate shell mode
        if not current_text:
            buffer.insert_text("!")
            return

        # Buffer starts with !, so we're in shell command mode
        # Extract the command (strip the leading !)
        command = current_text[1:].strip()

        if not command:
            # User just pressed ! again, do nothing
            return

        # Clear the buffer
        buffer.text = ""

        # Show what we're executing
        console.print(f"\n[dim]$ {command}[/dim]")

        # Execute the command
        exit_code, stdout, stderr = execute_shell_command(command)

        # Display output
        self._display_output(exit_code, stdout, stderr)

        logger.info(f"Shell command executed: {command} (exit code: {exit_code})")

    def _display_output(self, exit_code: int, stdout: str, stderr: str) -> None:
        """Display command output with formatting.

        Args:
            exit_code: Command exit code
            stdout: Standard output
            stderr: Standard error
        """
        # Display stdout if present
        if stdout:
            console.print(stdout, end="")

        # Display stderr in red if present
        if stderr:
            console.print(f"[red]{stderr}[/red]", end="")

        # Display exit code with color coding
        if exit_code == 0:
            console.print(f"\n[dim][green]Exit code: {exit_code}[/green][/dim]")
        elif exit_code == 124:
            # Timeout
            console.print(f"\n[dim][yellow]Exit code: {exit_code} (timeout)[/yellow][/dim]")
        else:
            console.print(f"\n[dim][red]Exit code: {exit_code}[/red][/dim]")

        console.print()  # Extra newline for spacing
