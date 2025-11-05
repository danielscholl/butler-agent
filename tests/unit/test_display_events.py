"""Unit tests for display event system."""

import pytest

from agent.display.events import (
    AddonProgressEvent,
    EventEmitter,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
    ToolStartEvent,
    get_current_tool_event_id,
    get_event_emitter,
    set_current_tool_event_id,
)


class TestEventEmitter:
    """Tests for EventEmitter class."""

    def test_init(self):
        """Test event emitter initialization."""
        emitter = EventEmitter()
        assert emitter.is_enabled
        assert not emitter.is_interactive_mode()
        assert not emitter.should_show_visualization()

    def test_emit_and_get_nowait(self):
        """Test emitting and retrieving events without blocking."""
        emitter = EventEmitter()
        event = LLMRequestEvent(message_count=5)

        emitter.emit(event)
        retrieved = emitter.get_event_nowait()

        assert retrieved is not None
        assert retrieved.event_id == event.event_id
        assert isinstance(retrieved, LLMRequestEvent)
        assert retrieved.message_count == 5

    def test_get_event_nowait_empty_queue(self):
        """Test getting event from empty queue returns None."""
        emitter = EventEmitter()
        event = emitter.get_event_nowait()
        assert event is None

    @pytest.mark.asyncio
    async def test_get_event_blocks(self):
        """Test that get_event blocks until event available."""
        emitter = EventEmitter()
        event = LLMRequestEvent(message_count=3)

        emitter.emit(event)
        retrieved = await emitter.get_event()

        assert retrieved.event_id == event.event_id
        assert isinstance(retrieved, LLMRequestEvent)

    def test_disable_enable(self):
        """Test disabling and enabling event emission."""
        emitter = EventEmitter()
        event = LLMRequestEvent(message_count=1)

        # Disable and emit - should not queue
        emitter.disable()
        assert not emitter.is_enabled
        emitter.emit(event)

        retrieved = emitter.get_event_nowait()
        assert retrieved is None

        # Enable and emit - should queue
        emitter.enable()
        assert emitter.is_enabled
        emitter.emit(event)

        retrieved = emitter.get_event_nowait()
        assert retrieved is not None

    def test_clear(self):
        """Test clearing pending events."""
        emitter = EventEmitter()

        # Add multiple events
        for i in range(5):
            emitter.emit(LLMRequestEvent(message_count=i))

        # Clear all
        emitter.clear()

        # Queue should be empty
        assert emitter.get_event_nowait() is None

    def test_set_interactive_mode(self):
        """Test setting interactive mode flags."""
        emitter = EventEmitter()

        emitter.set_interactive_mode(is_interactive=True, show_visualization=True)
        assert emitter.is_interactive_mode()
        assert emitter.should_show_visualization()

        emitter.set_interactive_mode(is_interactive=True, show_visualization=False)
        assert not emitter.is_interactive_mode()
        assert not emitter.should_show_visualization()

        emitter.set_interactive_mode(is_interactive=False, show_visualization=True)
        assert not emitter.is_interactive_mode()
        assert emitter.should_show_visualization()


class TestEventTypes:
    """Tests for event type classes."""

    def test_llm_request_event(self):
        """Test LLM request event creation."""
        event = LLMRequestEvent(message_count=10)
        assert event.message_count == 10
        assert event.event_id
        assert event.timestamp
        assert event.parent_id is None

    def test_llm_response_event(self):
        """Test LLM response event creation."""
        event = LLMResponseEvent(duration=2.5)
        assert event.duration == 2.5
        assert event.event_id
        assert event.timestamp

    def test_tool_start_event(self):
        """Test tool start event creation."""
        event = ToolStartEvent(
            tool_name="create_cluster",
            arguments={"name": "test", "config": "default"},
        )
        assert event.tool_name == "create_cluster"
        assert event.arguments["name"] == "test"
        assert event.event_id

    def test_tool_complete_event(self):
        """Test tool complete event creation."""
        event = ToolCompleteEvent(
            tool_name="create_cluster",
            result_summary="Cluster 'test' ready",
            duration=15.3,
        )
        assert event.tool_name == "create_cluster"
        assert event.result_summary == "Cluster 'test' ready"
        assert event.duration == 15.3

    def test_tool_error_event(self):
        """Test tool error event creation."""
        event = ToolErrorEvent(
            tool_name="create_cluster",
            error_message="Port conflict detected",
            duration=5.0,
        )
        assert event.tool_name == "create_cluster"
        assert event.error_message == "Port conflict detected"
        assert event.duration == 5.0

    def test_addon_progress_event(self):
        """Test addon progress event creation."""
        event = AddonProgressEvent(
            addon_name="ingress",
            status="installing",
            message="Installing NGINX Ingress Controller",
            duration=None,
        )
        assert event.addon_name == "ingress"
        assert event.status == "installing"
        assert event.message == "Installing NGINX Ingress Controller"
        assert event.duration is None

    def test_event_parent_nesting(self):
        """Test event parent_id for nesting."""
        parent_event = ToolStartEvent(tool_name="create_cluster")
        child_event = AddonProgressEvent(
            addon_name="ingress",
            status="starting",
            message="Starting addon",
            parent_id=parent_event.event_id,
        )

        assert child_event.parent_id == parent_event.event_id


class TestToolEventContext:
    """Tests for tool event context management."""

    def test_set_and_get_tool_event_id(self):
        """Test setting and getting current tool event ID."""
        test_id = "test-event-123"

        set_current_tool_event_id(test_id)
        retrieved_id = get_current_tool_event_id()

        assert retrieved_id == test_id

    def test_clear_tool_event_id(self):
        """Test clearing tool event ID by setting None."""
        set_current_tool_event_id("test-id")
        set_current_tool_event_id(None)

        retrieved_id = get_current_tool_event_id()
        assert retrieved_id is None

    def test_tool_event_context_nested_events(self):
        """Test that addon events can nest under tool events."""
        # Simulate tool execution
        tool_event = ToolStartEvent(tool_name="create_cluster")
        set_current_tool_event_id(tool_event.event_id)

        # Create addon event with parent context
        addon_event = AddonProgressEvent(
            addon_name="ingress",
            status="starting",
            message="Starting addon",
            parent_id=get_current_tool_event_id(),
        )

        assert addon_event.parent_id == tool_event.event_id

        # Clear context
        set_current_tool_event_id(None)
        assert get_current_tool_event_id() is None


class TestGlobalEventEmitter:
    """Tests for global event emitter singleton."""

    def test_get_event_emitter_singleton(self):
        """Test that get_event_emitter returns same instance."""
        emitter1 = get_event_emitter()
        emitter2 = get_event_emitter()

        assert emitter1 is emitter2

    def test_global_emitter_state_persists(self):
        """Test that global emitter state persists across calls."""
        emitter = get_event_emitter()
        emitter.set_interactive_mode(is_interactive=True, show_visualization=True)

        # Get emitter again
        emitter2 = get_event_emitter()
        assert emitter2.is_interactive_mode()
        assert emitter2.should_show_visualization()
