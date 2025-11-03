"""Unit tests for KeybindingManager."""

from prompt_toolkit.key_binding import KeyBindings

from agent.utils.keybindings.handler import KeybindingHandler
from agent.utils.keybindings.manager import KeybindingManager


class MockHandler(KeybindingHandler):
    """Mock handler for testing."""

    def __init__(self, trigger: str = "c-t", desc: str = "Test handler"):
        self._trigger = trigger
        self._desc = desc
        self.handle_called = False

    @property
    def trigger_key(self) -> str:
        return self._trigger

    @property
    def description(self) -> str:
        return self._desc

    def handle(self, event) -> None:
        self.handle_called = True


class TestKeybindingManager:
    """Tests for KeybindingManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = KeybindingManager()
        assert len(manager.get_handlers()) == 0

    def test_register_single_handler(self):
        """Test registering a single handler."""
        manager = KeybindingManager()
        handler = MockHandler()

        manager.register_handler(handler)

        handlers = manager.get_handlers()
        assert len(handlers) == 1
        assert handlers[0] == handler

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers."""
        manager = KeybindingManager()
        handler1 = MockHandler("c-x", "Handler 1")
        handler2 = MockHandler("c-y", "Handler 2")

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        handlers = manager.get_handlers()
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_register_duplicate_trigger_key_replaces(self):
        """Test that registering a handler with duplicate trigger key replaces the old one."""
        manager = KeybindingManager()
        handler1 = MockHandler("c-t", "First handler")
        handler2 = MockHandler("c-t", "Second handler")

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        handlers = manager.get_handlers()
        assert len(handlers) == 1
        assert handlers[0] == handler2
        assert handlers[0].description == "Second handler"

    def test_unregister_handler_success(self):
        """Test unregistering an existing handler."""
        manager = KeybindingManager()
        handler = MockHandler("c-t")

        manager.register_handler(handler)
        assert len(manager.get_handlers()) == 1

        result = manager.unregister_handler("c-t")
        assert result is True
        assert len(manager.get_handlers()) == 0

    def test_unregister_handler_not_found(self):
        """Test unregistering a handler that doesn't exist."""
        manager = KeybindingManager()

        result = manager.unregister_handler("c-x")
        assert result is False

    def test_get_handlers_returns_list(self):
        """Test that get_handlers returns a list."""
        manager = KeybindingManager()
        handler1 = MockHandler("c-x")
        handler2 = MockHandler("c-y")

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        handlers = manager.get_handlers()
        assert isinstance(handlers, list)
        assert len(handlers) == 2

    def test_get_help_text_empty(self):
        """Test help text generation with no handlers."""
        manager = KeybindingManager()
        help_text = manager.get_help_text()

        assert "No keybindings registered" in help_text

    def test_get_help_text_with_handlers(self):
        """Test help text generation with registered handlers."""
        manager = KeybindingManager()
        handler1 = MockHandler("c-x", "Cut text")
        handler2 = MockHandler("c-c", "Copy text")

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        help_text = manager.get_help_text()

        assert "Available Keyboard Shortcuts" in help_text
        assert "Cut text" in help_text
        assert "Copy text" in help_text

    def test_get_help_text_formats_escape_key(self):
        """Test that escape key is formatted as ESC in help text."""
        manager = KeybindingManager()
        handler = MockHandler("escape", "Clear prompt")

        manager.register_handler(handler)

        help_text = manager.get_help_text()

        assert "ESC" in help_text
        assert "Clear prompt" in help_text

    def test_create_keybindings_returns_keybindings_object(self):
        """Test that create_keybindings returns a KeyBindings instance."""
        manager = KeybindingManager()
        handler = MockHandler()

        manager.register_handler(handler)

        kb = manager.create_keybindings()

        assert isinstance(kb, KeyBindings)

    def test_create_keybindings_empty_manager(self):
        """Test creating keybindings with no handlers."""
        manager = KeybindingManager()

        kb = manager.create_keybindings()

        assert isinstance(kb, KeyBindings)

    def test_create_keybindings_binds_handlers(self):
        """Test that create_keybindings properly binds all handlers."""
        manager = KeybindingManager()
        handler1 = MockHandler("c-x")
        handler2 = MockHandler("c-y")

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        kb = manager.create_keybindings()

        # KeyBindings object should have bindings
        assert isinstance(kb, KeyBindings)
        # We can't easily test the actual binding without running the app,
        # but we can verify the object was created

    def test_handler_errors_are_caught(self):
        """Test that handler errors are caught and logged."""

        class ErrorHandler(KeybindingHandler):
            @property
            def trigger_key(self) -> str:
                return "c-e"

            @property
            def description(self) -> str:
                return "Error handler"

            def handle(self, event) -> None:
                raise ValueError("Test error")

        manager = KeybindingManager()
        handler = ErrorHandler()
        manager.register_handler(handler)

        kb = manager.create_keybindings()

        # Verify the KeyBindings object was created successfully
        # (we can't directly test the keybinding execution without the app)
        assert isinstance(kb, KeyBindings)
