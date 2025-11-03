"""Unit tests for keybinding handlers."""

from unittest.mock import MagicMock

from agent.utils.keybindings.handlers.clear_prompt import ClearPromptHandler


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
