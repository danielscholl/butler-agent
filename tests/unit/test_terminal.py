"""Unit tests for terminal utilities."""

from unittest.mock import MagicMock, patch

from agent.utils.terminal import clear_screen, execute_shell_command


class TestClearScreen:
    """Tests for clear_screen function."""

    @patch("agent.utils.terminal.sys.stdout")
    def test_clear_screen_with_ansi_codes(self, mock_stdout):
        """Test clearing screen with ANSI escape codes."""
        result = clear_screen()

        assert result is True
        mock_stdout.write.assert_called()
        mock_stdout.flush.assert_called_once()

    @patch("agent.utils.terminal.sys.stdout")
    def test_clear_screen_ansi_failure_fallback(self, mock_stdout):
        """Test fallback to system command if ANSI codes fail."""
        # Make ANSI codes fail
        mock_stdout.write.side_effect = Exception("ANSI failed")

        with patch("agent.utils.terminal.os.system") as mock_system:
            result = clear_screen()

            assert result is True
            mock_system.assert_called_once()

    @patch("agent.utils.terminal.sys.stdout")
    @patch("agent.utils.terminal.os.system")
    def test_clear_screen_all_methods_fail(self, mock_system, mock_stdout):
        """Test when all clearing methods fail."""
        # Make both methods fail
        mock_stdout.write.side_effect = Exception("ANSI failed")
        mock_system.side_effect = Exception("System failed")

        result = clear_screen()

        assert result is False


class TestExecuteShellCommand:
    """Tests for execute_shell_command function."""

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_success(self, mock_run):
        """Test executing a successful command."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute
        exit_code, stdout, stderr = execute_shell_command("echo hello")

        # Verify
        assert exit_code == 0
        assert stdout == "command output"
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_with_error(self, mock_run):
        """Test executing a command that fails."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command error"
        mock_run.return_value = mock_result

        # Execute
        exit_code, stdout, stderr = execute_shell_command("false")

        # Verify
        assert exit_code == 1
        assert stdout == ""
        assert stderr == "command error"

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_with_stdout_and_stderr(self, mock_run):
        """Test executing a command with both stdout and stderr."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = "output"
        mock_result.stderr = "error"
        mock_run.return_value = mock_result

        # Execute
        exit_code, stdout, stderr = execute_shell_command("mixed-output")

        # Verify
        assert exit_code == 2
        assert stdout == "output"
        assert stderr == "error"

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_timeout(self, mock_run):
        """Test executing a command that times out."""
        # Setup mock to raise TimeoutExpired
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        # Execute
        exit_code, stdout, stderr = execute_shell_command("sleep 100", timeout=30)

        # Verify timeout handling
        assert exit_code == 124
        assert stdout == ""
        assert "timed out" in stderr.lower()

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_with_custom_timeout(self, mock_run):
        """Test executing a command with custom timeout."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute with custom timeout
        exit_code, stdout, stderr = execute_shell_command("echo test", timeout=60)

        # Verify timeout was passed
        assert mock_run.call_args[1]["timeout"] == 60

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_with_custom_cwd(self, mock_run):
        """Test executing a command with custom working directory."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute with custom cwd
        exit_code, stdout, stderr = execute_shell_command("pwd", cwd="/tmp")

        # Verify cwd was passed
        assert mock_run.call_args[1]["cwd"] == "/tmp"

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_uses_shell(self, mock_run):
        """Test that command is executed with shell=True."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute
        execute_shell_command("echo $HOME")

        # Verify shell=True was used
        assert mock_run.call_args[1]["shell"] is True

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_captures_output(self, mock_run):
        """Test that command output is captured."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute
        execute_shell_command("echo test")

        # Verify capture_output and text were set
        assert mock_run.call_args[1]["capture_output"] is True
        assert mock_run.call_args[1]["text"] is True

    @patch("agent.utils.terminal.subprocess.run")
    def test_execute_command_exception_handling(self, mock_run):
        """Test that exceptions are handled gracefully."""
        # Setup mock to raise exception
        mock_run.side_effect = RuntimeError("Test error")

        # Execute
        exit_code, stdout, stderr = execute_shell_command("bad-command")

        # Verify error handling
        assert exit_code == 1
        assert stdout == ""
        assert "Test error" in stderr
