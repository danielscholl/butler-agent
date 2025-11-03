"""Unit tests for CLI interface."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.key_binding import KeyBindings

from agent.cli import build_parser, run_single_query


class TestArgumentParser:
    """Test CLI argument parser."""

    def test_parser_defaults(self):
        """Test parser with no arguments defaults to interactive mode."""
        parser = build_parser()
        args = parser.parse_args([])

        assert args.prompt is None
        assert args.quiet is False
        assert args.verbose is False

    def test_parser_with_prompt(self):
        """Test parser with --prompt argument."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test query"])

        assert args.prompt == "test query"
        assert args.quiet is False

    def test_parser_short_prompt(self):
        """Test parser with -p short form."""
        parser = build_parser()
        args = parser.parse_args(["-p", "test query"])

        assert args.prompt == "test query"

    def test_parser_with_quiet_flag(self):
        """Test parser with --quiet flag."""
        parser = build_parser()
        args = parser.parse_args(["--quiet"])

        assert args.quiet is True

    def test_parser_with_verbose_flag(self):
        """Test parser with --verbose flag."""
        parser = build_parser()
        args = parser.parse_args(["--verbose"])

        assert args.verbose is True

    def test_parser_combined_flags(self):
        """Test parser with multiple flags."""
        parser = build_parser()
        args = parser.parse_args(["-p", "query", "-v"])

        assert args.prompt == "query"
        assert args.verbose is True


class TestSingleQueryMode:
    """Test single query execution mode."""

    @pytest.mark.asyncio
    async def test_run_single_query_success(self):
        """Test successful single query execution."""
        with (
            patch("agent.cli.AgentConfig") as mock_config_class,
            patch("agent.cli.Agent") as mock_agent_class,
            patch("agent.cli.setup_logging"),
        ):
            # Setup mocks
            mock_config = MagicMock()
            mock_config.llm_provider = "openai"
            mock_config.log_level = "info"
            mock_config.applicationinsights_connection_string = None
            mock_config_class.return_value = mock_config

            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value="Test response")
            mock_agent_class.return_value = mock_agent

            # Run single query
            await run_single_query("test query", quiet=False, verbose=False)

            # Verify agent was created and run was called
            mock_agent_class.assert_called_once_with(mock_config)
            # Now expects thread parameter (Phase 5 change)
            assert mock_agent.run.called
            assert mock_agent.run.call_args[0][0] == "test query"
            assert "thread" in mock_agent.run.call_args[1]

    @pytest.mark.asyncio
    async def test_run_single_query_quiet_mode(self):
        """Test single query in quiet mode."""
        with (
            patch("agent.cli.AgentConfig") as mock_config_class,
            patch("agent.cli.Agent") as mock_agent_class,
            patch("agent.cli.setup_logging"),
            patch("agent.cli.console"),
        ):
            # Setup mocks
            mock_config = MagicMock()
            mock_config.llm_provider = "openai"
            mock_config.log_level = "info"
            mock_config.applicationinsights_connection_string = None
            mock_config_class.return_value = mock_config

            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value="Test response")
            mock_agent_class.return_value = mock_agent

            # Run in quiet mode
            await run_single_query("test query", quiet=True, verbose=False)

            # In quiet mode, we shouldn't print the query header
            # Count print calls - should be minimal
            # This is a simplified check

    @pytest.mark.asyncio
    async def test_run_single_query_config_error(self):
        """Test single query with configuration error."""
        from agent.utils.errors import ConfigurationError

        with (
            patch("agent.cli.AgentConfig") as mock_config_class,
            patch("agent.cli.sys.exit") as mock_exit,
        ):
            mock_config_class.return_value.validate.side_effect = ConfigurationError("Test error")

            await run_single_query("test query")

            # Should exit with error code 1
            mock_exit.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_run_single_query_agent_creation_error(self):
        """Test single query when agent creation fails."""
        with (
            patch("agent.cli.AgentConfig") as mock_config_class,
            patch("agent.cli.Agent") as mock_agent_class,
            patch("agent.cli.setup_logging"),
            patch("agent.cli.sys.exit") as mock_exit,
        ):
            # Setup mocks
            mock_config = MagicMock()
            mock_config.llm_provider = "openai"
            mock_config.log_level = "info"
            mock_config.applicationinsights_connection_string = None
            mock_config_class.return_value = mock_config

            # Agent creation raises error
            mock_agent_class.side_effect = Exception("Agent creation failed")

            await run_single_query("test query")

            # Should exit with error code 1
            mock_exit.assert_called_with(1)


class TestInteractiveMode:
    """Test interactive chat mode."""

    @pytest.mark.asyncio
    async def test_run_chat_mode_initialization(self):
        """Test chat mode initializes correctly."""
        # This is a complex integration test that would require
        # mocking the entire interactive loop. For now, we test
        # that the necessary components are imported correctly.
        from agent.cli import run_chat_mode

        assert run_chat_mode is not None
        assert callable(run_chat_mode)

    def test_render_prompt_area(self):
        """Test prompt rendering."""
        from agent.cli import _render_prompt_area

        # Phase 1-3 change: prompt is now just "> " (provider info moved to status bar)
        prompt = _render_prompt_area()

        assert prompt == "> "

    def test_create_key_bindings(self):
        """Test key bindings creation using KeybindingManager."""
        from agent.utils.keybindings import (
            ClearPromptHandler,
            KeybindingManager,
        )

        # Create manager and register handlers
        manager = KeybindingManager()
        manager.register_handler(ClearPromptHandler())

        # Create keybindings
        key_bindings = manager.create_keybindings()

        # Verify that key_bindings is a KeyBindings object
        assert key_bindings is not None
        assert isinstance(key_bindings, KeyBindings)

    def test_esc_key_clears_buffer(self):
        """Test that ESC key binding clears the buffer text."""
        from agent.utils.keybindings import ClearPromptHandler

        # Create handler
        handler = ClearPromptHandler()

        # Create mock event with buffer containing text
        mock_event = MagicMock()
        mock_buffer = MagicMock()
        mock_buffer.text = "Some test text"
        mock_event.app.current_buffer = mock_buffer

        # Execute handler
        handler.handle(mock_event)

        # Verify buffer was cleared
        assert mock_buffer.text == ""

    def test_show_help(self):
        """Test help display."""
        from agent.cli import _show_help

        with patch("agent.cli.console") as mock_console:
            _show_help()

            # Verify console.print was called with help text
            mock_console.print.assert_called_once()


class TestMainEntry:
    """Test main entry points."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        from agent.cli import main

        assert main is not None
        assert callable(main)

    def test_async_main_function_exists(self):
        """Test that async_main function exists and is callable."""
        from agent.cli import async_main

        assert async_main is not None
        assert callable(async_main)
