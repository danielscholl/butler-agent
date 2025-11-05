"""Display utilities for Butler Agent."""

# Event system
from agent.display.events import (
    AddonProgressEvent,
    EventEmitter,
    ExecutionEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
    ToolStartEvent,
    get_current_tool_event_id,
    get_event_emitter,
    set_current_tool_event_id,
)

# Execution context
from agent.display.execution_context import (
    ExecutionContext,
    get_execution_context,
    is_interactive_mode,
    set_execution_context,
    should_show_visualization,
)

# Execution tree display
from agent.display.execution_tree import DisplayMode, ExecutionTreeDisplay

__all__ = [
    # Events
    "ExecutionEvent",
    "LLMRequestEvent",
    "LLMResponseEvent",
    "ToolStartEvent",
    "ToolCompleteEvent",
    "ToolErrorEvent",
    "AddonProgressEvent",
    "EventEmitter",
    "get_event_emitter",
    "get_current_tool_event_id",
    "set_current_tool_event_id",
    # Context
    "ExecutionContext",
    "set_execution_context",
    "get_execution_context",
    "is_interactive_mode",
    "should_show_visualization",
    # Display
    "ExecutionTreeDisplay",
    "DisplayMode",
]
