"""Shell command handler for commands starting with !

This handler intercepts commands that start with ! and executes them as shell
commands instead of sending them to the AI agent.
"""

import logging
from typing import Any

from rich.console import Console

from agent.utils.keybindings.handler import KeybindingHandler
from agent.utils.terminal import execute_shell_command

logger = logging.getLogger(__name__)
console = Console()


class ShellCommandHandler(KeybindingHandler):
    """Handler that executes shell commands when Enter is pressed on lines starting with !

    This handler provides a quick way to run shell commands without leaving
    Butler's interactive session. When the user types a command starting with !
    and presses Enter, it executes as a shell command instead of being sent to the AI.

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
        """Enter key triggers this handler when line starts with !

        Returns:
            "enter" - the Enter/Return key
        """
        return "enter"

    @property
    def description(self) -> str:
        """Description of what this handler does.

        Returns:
            Human-readable description
        """
        return "Execute shell command directly (e.g., !ls, !docker ps)"

    def should_handle(self, event: Any) -> bool:
        """Check if this handler should process the event.

        Only handles Enter key presses when the buffer text starts with !

        Args:
            event: prompt_toolkit KeyPressEvent

        Returns:
            True if buffer starts with !, False otherwise
        """
        buffer = event.app.current_buffer
        text = buffer.text.strip()
        return text.startswith("!")

    def handle(self, event: Any) -> None:
        """Handle shell command execution.

        When Enter is pressed on a line starting with !, this handler
        intercepts it, extracts the command, executes it, and displays results.

        Args:
            event: prompt_toolkit KeyPressEvent
        """
        buffer = event.app.current_buffer
        current_text = buffer.text.strip()

        # Only process if line starts with !
        if not current_text.startswith("!"):
            # Not a shell command, trigger default Enter behavior (submit to AI)
            buffer.validate_and_handle()
            return

        # Extract the command (strip the leading !)
        command = current_text[1:].strip()

        if not command:
            # Just "!" with no command, clear buffer and return
            buffer.text = ""
            console.print(
                "\n[yellow]No command specified. Type !<command> to execute shell commands.[/yellow]\n"
            )
            return

        logger.debug(f"ShellCommandHandler: Executing shell command: {command}")

        # Clear the buffer
        buffer.text = ""

        # Show what we're executing
        console.print(f"\n[dim]$ {command}[/dim]")

        # Execute the command
        exit_code, stdout, stderr = execute_shell_command(command)

        # Display output
        self._display_output(exit_code, stdout, stderr)

        logger.info(f"Shell command executed: {command} (exit code: {exit_code})")

        # Prevent the default Enter behavior (don't send to AI)
        # This is critical - we've handled the command, don't process further
        return None

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
