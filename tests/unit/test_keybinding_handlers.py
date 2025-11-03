"""Unit tests for keybinding handlers."""

from unittest.mock import MagicMock, patch

from agent.utils.keybindings.handlers.clear_prompt import ClearPromptHandler
from agent.utils.keybindings.handlers.shell_command import ShellCommandHandler


class TestClearPromptHandler:
    """Tests for ClearPromptHandler."""

    def test_trigger_key(self):
        """Test that trigger key is 'escape'."""
        handler = ClearPromptHandler()
        assert handler.trigger_key == "escape"

    def test_description(self):
        """Test that description is set."""
        handler = ClearPromptHandler()
        assert isinstance(handler.description, str)
        assert len(handler.description) > 0
        assert "clear" in handler.description.lower()

    def test_handle_clears_buffer(self):
        """Test that handle() clears the buffer text."""
        handler = ClearPromptHandler()

        # Create mock event with buffer
        mock_buffer = MagicMock()
        mock_buffer.text = "some text to clear"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify buffer was cleared
        assert mock_buffer.text == ""

    def test_handle_with_empty_buffer(self):
        """Test that handle() works with empty buffer."""
        handler = ClearPromptHandler()

        # Create mock event with empty buffer
        mock_buffer = MagicMock()
        mock_buffer.text = ""
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle (should not raise)
        handler.handle(mock_event)

        # Verify buffer is still empty
        assert mock_buffer.text == ""


class TestShellCommandHandler:
    """Tests for ShellCommandHandler."""

    def test_trigger_key(self):
        """Test that trigger key is 'enter'."""
        handler = ShellCommandHandler()
        assert handler.trigger_key == "enter"

    def test_description(self):
        """Test that description is set."""
        handler = ShellCommandHandler()
        assert isinstance(handler.description, str)
        assert len(handler.description) > 0
        assert "shell" in handler.description.lower() or "command" in handler.description.lower()

    def test_should_handle_with_shell_command(self):
        """Test that should_handle returns True for commands starting with !"""
        handler = ShellCommandHandler()

        # Create mock event with shell command
        mock_buffer = MagicMock()
        mock_buffer.text = "!ls -la"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        result = handler.should_handle(mock_event)
        assert result is True

    def test_should_handle_with_normal_text(self):
        """Test that should_handle returns False for normal text."""
        handler = ShellCommandHandler()

        # Create mock event with normal text
        mock_buffer = MagicMock()
        mock_buffer.text = "create a cluster"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        result = handler.should_handle(mock_event)
        assert result is False

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_handle_executes_command(self, mock_console, mock_execute):
        """Test that handle() executes a shell command."""
        handler = ShellCommandHandler()

        # Setup mock
        mock_execute.return_value = (0, "output", "")

        # Create mock event with command in buffer
        mock_buffer = MagicMock()
        mock_buffer.text = "!ls -la"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify command was executed
        mock_execute.assert_called_once_with("ls -la")

        # Verify buffer was cleared
        assert mock_buffer.text == ""

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_handle_with_just_exclamation_shows_message(self, mock_console, mock_execute):
        """Test that handle() shows message when buffer has just !"""
        handler = ShellCommandHandler()

        # Create mock event with just !
        mock_buffer = MagicMock()
        mock_buffer.text = "!"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify buffer was cleared
        assert mock_buffer.text == ""

        # Verify message was shown
        assert mock_console.print.called

        # Verify command was not executed
        mock_execute.assert_not_called()

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_handle_with_non_shell_text_does_nothing(self, mock_console, mock_execute):
        """Test that handle() does nothing when buffer doesn't start with !"""
        handler = ShellCommandHandler()

        # Create mock event with non-shell text
        mock_buffer = MagicMock()
        mock_buffer.text = "create a cluster"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify command was not executed
        mock_execute.assert_not_called()

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_display_output_with_stdout(self, mock_console, mock_execute):
        """Test that stdout is displayed."""
        handler = ShellCommandHandler()

        # Setup mock
        mock_execute.return_value = (0, "test output\n", "")

        # Create mock event
        mock_buffer = MagicMock()
        mock_buffer.text = "!echo test"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify output was printed (console.print was called)
        assert mock_console.print.called

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_display_output_with_stderr(self, mock_console, mock_execute):
        """Test that stderr is displayed in red."""
        handler = ShellCommandHandler()

        # Setup mock
        mock_execute.return_value = (1, "", "error message")

        # Create mock event
        mock_buffer = MagicMock()
        mock_buffer.text = "!bad-command"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify console.print was called with stderr
        assert mock_console.print.called
        # Check that at least one call contains "red" formatting or error message
        print_calls = mock_console.print.call_args_list
        assert any("error message" in str(call) or "red" in str(call) for call in print_calls)

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_display_output_with_exit_code_zero(self, mock_console, mock_execute):
        """Test that exit code 0 is displayed in green."""
        handler = ShellCommandHandler()

        # Setup mock
        mock_execute.return_value = (0, "success", "")

        # Create mock event
        mock_buffer = MagicMock()
        mock_buffer.text = "!echo success"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify console.print was called
        assert mock_console.print.called
        # Check for exit code display
        print_calls = mock_console.print.call_args_list
        assert any("Exit code" in str(call) or "0" in str(call) for call in print_calls)

    @patch("agent.utils.keybindings.handlers.shell_command.execute_shell_command")
    @patch("agent.utils.keybindings.handlers.shell_command.console")
    def test_display_output_with_timeout(self, mock_console, mock_execute):
        """Test that timeout (exit code 124) is displayed with special message."""
        handler = ShellCommandHandler()

        # Setup mock for timeout
        mock_execute.return_value = (124, "", "Command timed out after 30s")

        # Create mock event
        mock_buffer = MagicMock()
        mock_buffer.text = "!sleep 100"
        mock_app = MagicMock()
        mock_app.current_buffer = mock_buffer
        mock_event = MagicMock()
        mock_event.app = mock_app

        # Call handle
        handler.handle(mock_event)

        # Verify timeout was displayed
        assert mock_console.print.called
        print_calls = mock_console.print.call_args_list
        assert any("timeout" in str(call).lower() or "124" in str(call) for call in print_calls)
