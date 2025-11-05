"""Event types and emission system for execution transparency.

This module provides event types for tracking agent execution, including LLM
requests/responses, tool calls, and addon progress. Events are emitted to an
asyncio queue for consumption by the execution tree display.
"""

import asyncio
import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExecutionEvent:
    """Base class for execution events.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When the event occurred
        parent_id: ID of parent event (for hierarchical display)
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    parent_id: str | None = None


@dataclass
class LLMRequestEvent(ExecutionEvent):
    """Event emitted when making an LLM request.

    Attributes:
        message_count: Number of messages in the request
    """

    message_count: int = 0


@dataclass
class LLMResponseEvent(ExecutionEvent):
    """Event emitted when LLM response is received.

    Attributes:
        duration: Request duration in seconds
    """

    duration: float = 0.0


@dataclass
class ToolStartEvent(ExecutionEvent):
    """Event emitted when a tool execution starts.

    Attributes:
        tool_name: Name of the tool being executed
        arguments: Tool arguments (sanitized, no secrets)
    """

    tool_name: str = ""
    arguments: dict[str, Any] | None = None


@dataclass
class ToolCompleteEvent(ExecutionEvent):
    """Event emitted when a tool execution completes successfully.

    Attributes:
        tool_name: Name of the tool that completed
        result_summary: Human-readable summary of results
        duration: Execution duration in seconds
    """

    tool_name: str = ""
    result_summary: str = ""
    duration: float = 0.0


@dataclass
class ToolErrorEvent(ExecutionEvent):
    """Event emitted when a tool execution fails.

    Attributes:
        tool_name: Name of the tool that failed
        error_message: Error message
        duration: Execution duration before failure in seconds
    """

    tool_name: str = ""
    error_message: str = ""
    duration: float = 0.0


@dataclass
class AddonProgressEvent(ExecutionEvent):
    """Event emitted for addon installation progress.

    Attributes:
        addon_name: Name of the addon (e.g., 'ingress')
        status: Current status (starting, installing, waiting, complete, error)
        message: Human-readable progress message
        duration: Operation duration (for complete/error status)
    """

    addon_name: str = ""
    status: str = ""  # starting, installing, waiting, complete, error
    message: str = ""
    duration: float | None = None


class EventEmitter:
    """Task-safe event emitter using asyncio queue.

    This emitter provides a task-safe way to emit execution events
    that can be consumed by the execution tree display. Uses asyncio.Queue
    to work across async task boundaries within the same event loop.

    Note:
        asyncio.Queue is not thread-safe. If emissions need to happen from
        different threads, use loop.call_soon_threadsafe() as a bridge.
    """

    def __init__(self) -> None:
        """Initialize event emitter with asyncio queue."""
        self._queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()
        self._enabled = True
        # Store execution mode flags (avoids ContextVar propagation issues)
        self._is_interactive = False
        self._show_visualization = False

    def emit(self, event: ExecutionEvent) -> None:
        """Emit an event to the queue.

        Args:
            event: Event to emit

        Note:
            This is safe to call from async contexts within the same event loop.
            For cross-thread emission, use loop.call_soon_threadsafe().
        """
        if not self._enabled:
            return

        # Use put_nowait since we don't want to block
        # Queue has no maxsize, so this should never raise QueueFull
        self._queue.put_nowait(event)

    async def get_event(self) -> ExecutionEvent:
        """Get next event from queue.

        Returns:
            Next event from queue

        Note:
            This will block until an event is available.
        """
        return await self._queue.get()

    def get_event_nowait(self) -> ExecutionEvent | None:
        """Get next event without blocking.

        Returns:
            Next event or None if queue is empty
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def disable(self) -> None:
        """Disable event emission."""
        self._enabled = False

    def enable(self) -> None:
        """Enable event emission."""
        self._enabled = True

    @property
    def is_enabled(self) -> bool:
        """Check if emitter is enabled."""
        return self._enabled

    def clear(self) -> None:
        """Clear all pending events from queue."""
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def set_interactive_mode(self, is_interactive: bool, show_visualization: bool) -> None:
        """Set the interactive mode flags.

        Args:
            is_interactive: Whether running in interactive mode
            show_visualization: Whether to show visualization
        """
        self._is_interactive = is_interactive
        self._show_visualization = show_visualization

    def is_interactive_mode(self) -> bool:
        """Check if in interactive mode with visualization.

        Returns:
            True if interactive mode with visualization enabled
        """
        return self._is_interactive and self._show_visualization

    def should_show_visualization(self) -> bool:
        """Check if visualization should be shown.

        Returns:
            True if visualization is enabled (regardless of interactive mode)
        """
        return self._show_visualization


# Global singleton instance
_event_emitter: EventEmitter | None = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance.

    Returns:
        EventEmitter singleton instance
    """
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = EventEmitter()
    return _event_emitter


# ============================================================================
# Tool Event Context for Parent ID Propagation
# ============================================================================

# ContextVar for propagating current tool event ID to child operations
_current_tool_event_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_tool_event_id", default=None
)


def set_current_tool_event_id(event_id: str | None) -> None:
    """Set the current tool event ID for child event nesting.

    This allows child operations (like addon installations) to automatically
    nest their events under the parent tool event in the execution tree.

    Args:
        event_id: Tool event ID to set as parent, or None to clear
    """
    _current_tool_event_id.set(event_id)


def get_current_tool_event_id() -> str | None:
    """Get the current tool event ID for child event nesting.

    Returns:
        Current tool event ID, or None if not in a tool context
    """
    return _current_tool_event_id.get()
