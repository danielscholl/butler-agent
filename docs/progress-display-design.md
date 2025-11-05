# Butler Agent: Real-Time Execution Display Design

## Overview

Butler Agent should feel like a coding agent - showing its reasoning and actions in real-time, allowing users to interrupt if needed. This design adapts OSDU-agent's execution tree pattern for Butler's cluster management and future GitLab/tool operations.

## Design Goals

1. **Real-Time Transparency**: Show LLM thinking and tool calls as they happen
2. **User Control**: Allow interruption (Ctrl+C) if agent takes wrong path
3. **Nested Operations**: Support tool → addon → substep hierarchy
4. **Agent-Centric**: Let agent summarize what it did (not just logs)
5. **Extensible**: Framework for future tools (GitLab, kubectl, etc.)

## Key Insight from User Feedback

> "It needs to feel more like a coding agent...showing messages and tool calls as they happen, then letting the agent give a summary when complete. The continuous feedback is important - I can break if I don't like what it is doing."

This is about **trust and control** - users need to see the agent's thought process and decision-making in real-time.

## Architecture (Adapted from OSDU-Agent)

```
src/agent/display/
├── __init__.py
├── events.py              # Event types (LLMRequestEvent, ToolStartEvent, AddonProgressEvent)
├── execution_tree.py      # ExecutionTreeDisplay with Rich Live
├── execution_context.py   # Mode detection (interactive vs CLI)
└── formatters.py          # Existing formatters
```

### Core Components

#### 1. Event System (events.py)

```python
"""Event types for execution transparency."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid


@dataclass
class ExecutionEvent:
    """Base class for execution events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    parent_id: Optional[str] = None  # For hierarchical display


@dataclass
class LLMRequestEvent(ExecutionEvent):
    """Event emitted when making an LLM request."""
    message_count: int = 0


@dataclass
class LLMResponseEvent(ExecutionEvent):
    """Event emitted when LLM response is received."""
    duration: float = 0.0


@dataclass
class ToolStartEvent(ExecutionEvent):
    """Event emitted when a tool execution starts."""
    tool_name: str = ""
    arguments: Optional[dict[str, Any]] = None  # Sanitized, no secrets


@dataclass
class ToolCompleteEvent(ExecutionEvent):
    """Event emitted when a tool execution completes."""
    tool_name: str = ""
    result_summary: str = ""  # Brief summary for display
    duration: float = 0.0


@dataclass
class ToolErrorEvent(ExecutionEvent):
    """Event emitted when a tool execution fails."""
    tool_name: str = ""
    error_message: str = ""
    duration: float = 0.0


@dataclass
class AddonProgressEvent(ExecutionEvent):
    """Event emitted for addon installation progress."""
    addon_name: str = ""
    status: str = ""  # "starting", "installing", "waiting", "complete", "error"
    message: str = ""
    duration: Optional[float] = None


class EventEmitter:
    """Thread-safe event emitter using asyncio queue."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()
        self._enabled = True
        self._is_interactive = False
        self._show_visualization = False

    def emit(self, event: ExecutionEvent) -> None:
        """Emit an event to the queue."""
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop event if queue full

    async def get_event(self) -> ExecutionEvent:
        """Get next event (blocks until available)."""
        return await self._queue.get()

    async def get_event_nowait(self) -> Optional[ExecutionEvent]:
        """Get next event without blocking."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def set_interactive_mode(self, is_interactive: bool, show_visualization: bool) -> None:
        """Set interactive mode flags."""
        self._is_interactive = is_interactive
        self._show_visualization = show_visualization

    def is_interactive_mode(self) -> bool:
        """Check if in interactive mode with visualization."""
        return self._is_interactive and self._show_visualization


# Global singleton
_event_emitter: Optional[EventEmitter] = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = EventEmitter()
    return _event_emitter
```

#### 2. Execution Tree Display (execution_tree.py)

```python
"""Hierarchical execution tree display using Rich Live.

Adapted from osdu-agent for Butler's cluster management operations.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from agent.display.events import (
    EventEmitter,
    ExecutionEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolStartEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
    AddonProgressEvent,
    get_event_emitter,
)


class DisplayMode(Enum):
    """Display mode for execution tree."""
    MINIMAL = "minimal"  # Show active work only (default)
    VERBOSE = "verbose"  # Show all phases with full details


# Symbols (Butler-themed)
SYMBOL_ACTIVE = "●"     # Active/working
SYMBOL_COMPLETE = "•"   # Completed
SYMBOL_TOOL = "→"       # Tool executing
SYMBOL_SUCCESS = "✓"    # Success
SYMBOL_ERROR = "✗"      # Error

# Colors
COLOR_ACTIVE = "yellow"
COLOR_COMPLETE = "dim white"
COLOR_SUCCESS = "green"
COLOR_ERROR = "red"


class TreeNode:
    """Node in the execution tree."""

    def __init__(self, event_id: str, label: str, status: str = "in_progress"):
        self.event_id = event_id
        self.label = label
        self.status = status
        self.children: list[TreeNode] = []
        self.metadata: dict = {}
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

    def add_child(self, child: "TreeNode") -> None:
        """Add a child node."""
        self.children.append(child)

    def complete(self, summary: Optional[str] = None, duration: Optional[float] = None) -> None:
        """Mark node as completed."""
        self.status = "completed"
        self.end_time = datetime.now()
        if summary:
            self.metadata["summary"] = summary
        if duration is not None:
            self.metadata["duration"] = duration

    def mark_error(self, error_message: str, duration: Optional[float] = None) -> None:
        """Mark node as error."""
        self.status = "error"
        self.end_time = datetime.now()
        self.metadata["error"] = error_message
        if duration is not None:
            self.metadata["duration"] = duration


class ExecutionPhase:
    """Represents a reasoning phase (LLM thinking + tool calls)."""

    def __init__(self, phase_number: int):
        self.phase_number = phase_number
        self.llm_node: Optional[TreeNode] = None
        self.tool_nodes: list[TreeNode] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "in_progress"

    def add_llm_node(self, node: TreeNode) -> None:
        """Add LLM thinking node."""
        self.llm_node = node

    def add_tool_node(self, node: TreeNode) -> None:
        """Add tool execution node."""
        self.tool_nodes.append(node)

    def complete(self) -> None:
        """Mark phase as completed."""
        self.status = "completed"
        self.end_time = datetime.now()

    @property
    def duration(self) -> float:
        """Get phase duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def has_nodes(self) -> bool:
        """Check if phase has any nodes."""
        return self.llm_node is not None or len(self.tool_nodes) > 0


class ExecutionTreeDisplay:
    """Hierarchical execution tree display using Rich Live."""

    def __init__(
        self,
        console: Optional[Console] = None,
        display_mode: DisplayMode = DisplayMode.MINIMAL,
        show_completion_summary: bool = True,
    ):
        self.console = console or Console()
        self.display_mode = display_mode
        self.show_completion_summary = show_completion_summary
        self._live: Optional[Live] = None
        self._node_map: dict[str, TreeNode] = {}
        self._event_emitter: EventEmitter = get_event_emitter()
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # Phase tracking
        self._phases: list[ExecutionPhase] = []
        self._current_phase: Optional[ExecutionPhase] = None
        self._session_start_time = datetime.now()

    def _render_node(self, node: TreeNode) -> Text | Tree:
        """Render a node with its children."""
        # Choose symbol and style based on status
        if node.status == "in_progress":
            symbol = SYMBOL_ACTIVE
            style = COLOR_ACTIVE
        elif node.status == "completed":
            symbol = SYMBOL_COMPLETE
            style = COLOR_COMPLETE
        else:  # error
            symbol = SYMBOL_ERROR
            style = COLOR_ERROR

        # Build label
        label_parts = [symbol, " ", node.label]
        if node.status == "completed" and "summary" in node.metadata:
            label_parts.append(f" - {node.metadata['summary']}")
        if "duration" in node.metadata:
            label_parts.append(f" ({node.metadata['duration']:.1f}s)")

        label_text = Text.from_markup("".join(label_parts), style=style)

        # If node has children, render as tree
        if node.children:
            tree = Tree(label_text)
            for child in node.children:
                child_renderable = self._render_node(child)
                if isinstance(child_renderable, Tree):
                    tree.add(child_renderable)
                else:
                    tree.add(child_renderable)
            return tree
        else:
            return label_text

    def _render_phases(self):
        """Render execution using phase-based view."""
        if not self._phases:
            return Text(f"{SYMBOL_ACTIVE} Thinking...", style=COLOR_ACTIVE)

        renderables = []

        # Calculate session progress
        completed_count = sum(1 for p in self._phases if p.status == "completed")
        total_phases = len(self._phases)
        session_duration = (datetime.now() - self._session_start_time).total_seconds()

        # MINIMAL mode: show only active phase
        if self.display_mode == DisplayMode.MINIMAL:
            if self._current_phase and self._current_phase.status == "in_progress":
                # Count tools and messages
                total_tools = sum(len(p.tool_nodes) for p in self._phases)
                current_message_count = (
                    self._current_phase.llm_node.metadata.get("message_count", 0)
                    if self._current_phase.llm_node
                    else 0
                )

                # Create phase label
                phase_label = Text()
                phase_label.append(f"{SYMBOL_ACTIVE} working... ", style=COLOR_ACTIVE)
                phase_label.append(f"(msg:{current_message_count} tool:{total_tools})", style="dim")
                phase_tree = Tree(phase_label)

                # Show LLM thinking
                if self._current_phase.llm_node:
                    phase_tree.add(self._render_node(self._current_phase.llm_node))

                # Show tool calls (these are the main operations)
                for tool_node in self._current_phase.tool_nodes:
                    phase_tree.add(self._render_node(tool_node))

                renderables.append(phase_tree)

            elif completed_count == total_phases and total_phases > 0 and self.show_completion_summary:
                # All done - show completion summary
                total_tools = sum(len(p.tool_nodes) for p in self._phases)
                final_phase = self._phases[-1] if self._phases else None
                final_messages = (
                    final_phase.llm_node.metadata.get("message_count", 0)
                    if (final_phase and final_phase.llm_node)
                    else 0
                )

                summary_text = Text()
                summary_text.append(
                    f"{SYMBOL_SUCCESS} Complete ({session_duration:.1f}s) - ",
                    style=COLOR_SUCCESS
                )
                summary_text.append(f"msg:{final_messages} tool:{total_tools}", style="dim")
                renderables.append(summary_text)

        # VERBOSE mode: show all phases
        else:
            for phase in self._phases:
                # Phase header
                if phase.status == "in_progress":
                    symbol = SYMBOL_ACTIVE
                    style = COLOR_ACTIVE
                elif phase.status == "completed":
                    symbol = SYMBOL_COMPLETE
                    style = COLOR_COMPLETE
                else:
                    symbol = SYMBOL_ERROR
                    style = COLOR_ERROR

                tool_count = len(phase.tool_nodes)
                phase_name = f"Phase {phase.phase_number}"
                if tool_count == 1:
                    tool_name = phase.tool_nodes[0].label.split(" ")[1] if phase.tool_nodes else ""
                    phase_name += f": {tool_name}"
                elif tool_count > 1:
                    phase_name += f": {tool_count} operations"

                phase_label = Text(f"{symbol} {phase_name} ({phase.duration:.1f}s)", style=style)
                phase_tree = Tree(phase_label)

                # LLM thinking
                if phase.llm_node:
                    phase_tree.add(self._render_node(phase.llm_node))

                # Tool calls
                for tool_node in phase.tool_nodes:
                    phase_tree.add(self._render_node(tool_node))

                renderables.append(phase_tree)

        return Group(*renderables) if renderables else Text(f"{SYMBOL_ACTIVE} Thinking...", style=COLOR_ACTIVE)

    async def _handle_event(self, event: ExecutionEvent) -> None:
        """Handle a single event."""
        if isinstance(event, LLMRequestEvent):
            # Start a new reasoning phase
            if self._current_phase and self._current_phase.has_nodes:
                self._current_phase.complete()

            # Create new phase
            phase_num = len(self._phases) + 1
            self._current_phase = ExecutionPhase(phase_num)
            self._phases.append(self._current_phase)

            # Create LLM node
            label = f"Thinking ({event.message_count} messages)"
            node = TreeNode(event.event_id, label)
            node.metadata["message_count"] = event.message_count
            self._node_map[event.event_id] = node
            self._current_phase.add_llm_node(node)

        elif isinstance(event, LLMResponseEvent):
            if event.event_id in self._node_map:
                node = self._node_map[event.event_id]
                node.complete("Response received", event.duration)

        elif isinstance(event, ToolStartEvent):
            # Create tool node
            label = f"{SYMBOL_TOOL} {event.tool_name}"
            if event.arguments:
                # Add key arguments to label
                if "name" in event.arguments:
                    label += f" ({event.arguments['name']})"
                elif "cluster_name" in event.arguments:
                    label += f" ({event.arguments['cluster_name']})"

            node = TreeNode(event.event_id, label)
            self._node_map[event.event_id] = node

            # Add to current phase
            if self._current_phase:
                self._current_phase.add_tool_node(node)

        elif isinstance(event, ToolCompleteEvent):
            if event.event_id in self._node_map:
                node = self._node_map[event.event_id]
                node.complete(event.result_summary, event.duration)

        elif isinstance(event, ToolErrorEvent):
            if event.event_id in self._node_map:
                node = self._node_map[event.event_id]
                node.mark_error(event.error_message, event.duration)

        elif isinstance(event, AddonProgressEvent):
            # Create or update addon node under current tool
            addon_label = f"{SYMBOL_TOOL} {event.addon_name} - {event.message}"

            if event.event_id not in self._node_map:
                # Create new addon node
                addon_node = TreeNode(event.event_id, addon_label)
                self._node_map[event.event_id] = addon_node

                # Find parent tool node and add as child
                if event.parent_id and event.parent_id in self._node_map:
                    parent_node = self._node_map[event.parent_id]
                    parent_node.add_child(addon_node)
            else:
                # Update existing addon node
                addon_node = self._node_map[event.event_id]
                addon_node.label = addon_label

                if event.status == "complete":
                    addon_node.complete(duration=event.duration)
                elif event.status == "error":
                    addon_node.mark_error(event.message, event.duration)

    async def _process_events(self) -> None:
        """Background task to process events."""
        while self._running:
            try:
                try:
                    event = await asyncio.wait_for(self._event_emitter.get_event(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                await self._handle_event(event)

                # Update display
                if self._live:
                    self._live.update(self._render_phases())

            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Error processing event: {e}", exc_info=True)

    async def start(self) -> None:
        """Start the execution tree display."""
        if self._running:
            return

        self._running = True

        # Start Rich Live display
        self._live = Live(
            self._render_phases(),
            console=self.console,
            refresh_per_second=10,  # Smooth updates
            transient=not self.show_completion_summary,
        )
        self._live.start()

        # Start background event processing
        self._task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the execution tree display."""
        if not self._running:
            return

        # Process remaining events
        while True:
            event = await self._event_emitter.get_event_nowait()
            if event is None:
                break
            await self._handle_event(event)

        # Complete active phase
        if self._current_phase and self._current_phase.status == "in_progress":
            self._current_phase.complete()

        self._running = False

        # Cancel background task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Stop display
        if self._live:
            if self.show_completion_summary:
                self._live.update(self._render_phases())
            self._live.stop()
            if self.show_completion_summary:
                self.console.print()

    async def __aenter__(self) -> "ExecutionTreeDisplay":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
```

#### 3. Execution Context (execution_context.py)

```python
"""Execution context for mode detection and visualization control."""

import contextvars
from dataclasses import dataclass
from typing import Optional

# Thread-local context variable
_execution_context: contextvars.ContextVar[Optional["ExecutionContext"]] = (
    contextvars.ContextVar("execution_context", default=None)
)


@dataclass
class ExecutionContext:
    """Context information about the current execution mode."""
    is_interactive: bool = False
    show_visualization: bool = False


def set_execution_context(context: Optional[ExecutionContext]) -> None:
    """Set the execution context."""
    from agent.display.events import get_event_emitter

    _execution_context.set(context)

    # Also set on EventEmitter singleton
    emitter = get_event_emitter()
    if context is None:
        emitter.set_interactive_mode(False, False)
    else:
        emitter.set_interactive_mode(context.is_interactive, context.show_visualization)


def is_interactive_mode() -> bool:
    """Check if currently in interactive mode with visualization."""
    from agent.display.events import get_event_emitter

    emitter = get_event_emitter()
    return emitter.is_interactive_mode()
```

### Integration Points

#### 1. Middleware Enhancement (middleware.py)

```python
"""Enhanced middleware to emit execution events."""

import time
from agent_framework import FunctionInvocationContext
from agent.display import (
    get_event_emitter,
    is_interactive_mode,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolStartEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
)

async def logging_function_middleware(
    context: FunctionInvocationContext,
    next: Callable,
) -> Any:
    """Middleware to log and emit tool execution events."""
    tool_name = context.function.name
    args = context.arguments

    logger.info(f"Tool call: {tool_name}")

    # Emit tool start event (if interactive)
    tool_event_id = None
    if is_interactive_mode():
        # Convert args to dict for event
        args_dict = args.dict() if hasattr(args, "dict") else (args if isinstance(args, dict) else {})
        # Sanitize (remove sensitive keys)
        safe_args = {k: v for k, v in args_dict.items() if k not in ["token", "api_key", "password"]}

        event = ToolStartEvent(tool_name=tool_name, arguments=safe_args)
        tool_event_id = event.event_id
        get_event_emitter().emit(event)

    start_time = time.time()
    status = "success"

    try:
        result = await next(context)
        logger.info(f"Tool {tool_name} completed")

        # Emit tool complete event
        if is_interactive_mode() and tool_event_id:
            duration = time.time() - start_time
            # Extract summary from result
            summary = _extract_tool_summary(tool_name, result)
            complete_event = ToolCompleteEvent(
                tool_name=tool_name,
                result_summary=summary,
                duration=duration
            )
            complete_event.event_id = tool_event_id
            get_event_emitter().emit(complete_event)

        return result

    except Exception as e:
        status = "error"
        logger.error(f"Tool {tool_name} failed: {e}")

        # Emit tool error event
        if is_interactive_mode() and tool_event_id:
            duration = time.time() - start_time
            error_event = ToolErrorEvent(
                tool_name=tool_name,
                error_message=str(e),
                duration=duration
            )
            error_event.event_id = tool_event_id
            get_event_emitter().emit(error_event)

        raise


def _extract_tool_summary(tool_name: str, result: Any) -> str:
    """Extract human-readable summary from tool result."""
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        elif "summary" in result:
            return result["summary"]
        elif "cluster_name" in result:
            return f"Cluster '{result['cluster_name']}' ready"
    return "Complete"
```

#### 2. Addon Progress Integration (addons/base.py)

```python
"""Base addon with progress event emission."""

from agent.display import get_event_emitter, is_interactive_mode, AddonProgressEvent

class BaseAddon(ABC):
    """Base class for cluster addons with progress tracking."""

    def run(self) -> dict[str, Any]:
        """Standard installation flow with progress events."""
        addon_name = self.get_name()
        start_time = time.time()

        # Get parent tool event ID from context (if available)
        parent_id = getattr(self, '_parent_event_id', None)

        try:
            # Check prerequisites
            if not self.check_prerequisites():
                return {"success": False, "error": "Prerequisites not met"}

            # Check if already installed
            if self.is_installed():
                return {"success": True, "message": "Already installed", "skipped": True}

            # Emit starting event
            if is_interactive_mode():
                event = AddonProgressEvent(
                    addon_name=addon_name,
                    status="starting",
                    message=f"Installing {self.get_display_name()}",
                    parent_id=parent_id
                )
                addon_event_id = event.event_id
                get_event_emitter().emit(event)
            else:
                addon_event_id = None

            # Install
            result = self.install()

            if result.get("success"):
                # Emit waiting event
                if is_interactive_mode() and addon_event_id:
                    wait_event = AddonProgressEvent(
                        addon_name=addon_name,
                        status="waiting",
                        message=f"Waiting for {self.get_display_name()} to be ready",
                        parent_id=parent_id
                    )
                    wait_event.event_id = addon_event_id
                    get_event_emitter().emit(wait_event)

                self.wait_for_ready()

                # Emit complete event
                duration = time.time() - start_time
                if is_interactive_mode() and addon_event_id:
                    complete_event = AddonProgressEvent(
                        addon_name=addon_name,
                        status="complete",
                        message="Ready",
                        duration=duration,
                        parent_id=parent_id
                    )
                    complete_event.event_id = addon_event_id
                    get_event_emitter().emit(complete_event)

                return {"success": True, "message": f"{self.get_display_name()} installed", "duration": duration}

            return result

        except Exception as e:
            duration = time.time() - start_time

            # Emit error event
            if is_interactive_mode() and addon_event_id:
                error_event = AddonProgressEvent(
                    addon_name=addon_name,
                    status="error",
                    message=f"Failed: {str(e)}",
                    duration=duration,
                    parent_id=parent_id
                )
                error_event.event_id = addon_event_id
                get_event_emitter().emit(error_event)

            return {"success": False, "error": str(e), "duration": duration}
```

#### 3. CLI Integration (cli.py)

```python
"""Enhanced CLI with execution tree display."""

from agent.display import (
    ExecutionTreeDisplay,
    ExecutionContext,
    set_execution_context,
    DisplayMode,
)

async def interactive_mode(agent: Agent, args: argparse.Namespace) -> None:
    """Interactive chat mode with execution visualization."""
    # Set execution context for interactive mode
    context = ExecutionContext(is_interactive=True, show_visualization=True)
    set_execution_context(context)

    # Determine display mode
    display_mode = DisplayMode.VERBOSE if args.verbose else DisplayMode.MINIMAL

    # Create execution tree display
    execution_display = ExecutionTreeDisplay(
        console=console,
        display_mode=display_mode,
        show_completion_summary=True,
    )

    # ... existing prompt session setup ...

    while True:
        try:
            user_input = await session.prompt_async("You: ")

            if user_input.lower() in ["exit", "quit"]:
                break

            # Start execution display
            await execution_display.start()

            try:
                # Run agent (events will be emitted automatically)
                response = await agent.run(user_input, thread=thread)

                # Stop display (shows completion summary)
                await execution_display.stop()

                # Agent's summary response
                console.print(f"\n[bold cyan]Butler:[/bold cyan] {response}\n")

            except KeyboardInterrupt:
                # User interrupted - stop display cleanly
                await execution_display.stop()
                console.print("\n[yellow]Interrupted by user[/yellow]\n")
                continue

        except KeyboardInterrupt:
            break


async def single_query_mode(agent: Agent, query: str, args: argparse.Namespace) -> None:
    """Single query mode with execution visualization."""
    # Set execution context (show visualization unless quiet)
    show_viz = not args.quiet
    context = ExecutionContext(is_interactive=False, show_visualization=show_viz)
    set_execution_context(context)

    if show_viz:
        display_mode = DisplayMode.VERBOSE if args.verbose else DisplayMode.MINIMAL
        execution_display = ExecutionTreeDisplay(
            console=console,
            display_mode=display_mode,
            show_completion_summary=True,
        )

        await execution_display.start()

    try:
        response = await agent.run(query)

        if show_viz:
            await execution_display.stop()

        console.print(f"\n{response}\n")

    except KeyboardInterrupt:
        if show_viz:
            await execution_display.stop()
        console.print("\n[yellow]Interrupted by user[/yellow]\n")
        sys.exit(130)
```

## Display Examples

### Interactive Mode - Creating Cluster with Addon

**During execution:**
```
● working... (msg:3 tool:1)
├── • Thinking (3 messages) - Response received (2.1s)
└── • → create_cluster (dev)
    ├── • → ingress - Installing NGINX Ingress Controller
    └── • → ingress - Waiting for NGINX Ingress Controller to be ready
```

**On completion:**
```
✓ Complete (42.3s) - msg:3 tool:1

Butler: I've successfully created your cluster 'dev' with the NGINX Ingress Controller. The cluster is running with 2 nodes and the ingress controller is ready to route HTTP/HTTPS traffic. You can now deploy applications to the cluster.
```

**User can Ctrl+C at any point** to interrupt if they don't like what's happening.

### Verbose Mode - Multiple Operations

```
● Phase 1: create_cluster (15.2s)
├── • Thinking (3 messages) - Response received (2.1s)
└── • → create_cluster (dev) - Cluster 'dev' ready (13.1s)
    └── • → ingress - Ready (12.5s)

● Phase 2: Thinking (3.4s)
└── • Thinking (5 messages) - Response received (3.4s)
```

### Future: GitLab Integration Example

```
● working... (msg:4 tool:2)
├── • Thinking (4 messages) - Response received (3.2s)
├── • → gitlab_list_merge_requests (osdu/partition) - Found 3 MRs (1.5s)
└── • → gitlab_get_pipeline_status (osdu/partition, !123) - Pipeline passed (0.8s)
```

## Implementation Plan

### Phase 1: Core Event System (Week 1)
- [ ] Port `events.py` from osdu-agent
- [ ] Port `execution_context.py`
- [ ] Create EventEmitter singleton
- [ ] Unit tests for event emission

### Phase 2: Execution Tree Display (Week 1-2)
- [ ] Port `execution_tree.py` with Butler adaptations
- [ ] Implement phase-based grouping
- [ ] Add MINIMAL and VERBOSE modes
- [ ] Test with Rich Live display

### Phase 3: Middleware Integration (Week 2)
- [ ] Update `middleware.py` to emit LLM events
- [ ] Update `middleware.py` to emit tool events
- [ ] Test event flow through Agent Framework
- [ ] Handle KeyboardInterrupt properly

### Phase 4: Tool & Addon Integration (Week 2)
- [ ] Update `create_cluster()` tool integration
- [ ] Update `BaseAddon` to emit AddonProgressEvent
- [ ] Update `IngressNginxAddon` implementation
- [ ] Test nested event hierarchy (tool → addon)

### Phase 5: CLI Integration (Week 3)
- [ ] Update interactive mode with ExecutionTreeDisplay
- [ ] Update single-query mode with display
- [ ] Add --verbose flag support
- [ ] Test KeyboardInterrupt handling

### Phase 6: Testing & Polish (Week 3)
- [ ] End-to-end testing with real cluster operations
- [ ] Test interrupt behavior (Ctrl+C)
- [ ] Performance testing (event queue behavior)
- [ ] Documentation updates

## Key Benefits

1. **Transparency**: Users see exactly what the agent is thinking and doing
2. **Control**: Ctrl+C works at any point to stop unwanted operations
3. **Trust**: Real-time feedback builds confidence in agent decisions
4. **Extensibility**: Framework ready for GitLab, kubectl, and other future tools
5. **Professional UX**: Matches patterns from modern coding agents

## Technical Challenges & Solutions

### Challenge 1: Event Emission Across Async Boundaries
**Solution**: Use EventEmitter singleton with asyncio.Queue (thread-safe, works across framework boundaries)

### Challenge 2: Nested Operations (Tool → Addon → Substeps)
**Solution**: Use `parent_id` field in events to build hierarchy, ExecutionTreeDisplay renders nested structure

### Challenge 3: Interrupt Handling
**Solution**: KeyboardInterrupt in CLI properly stops ExecutionTreeDisplay and cleans up, doesn't corrupt display

### Challenge 4: Mode Detection (Interactive vs CLI)
**Solution**: ExecutionContext with singleton pattern ensures mode is accessible everywhere

## Alternatives Considered

### Simple Progress Bars
**Rejected**: Doesn't show agent reasoning or allow detailed progress

### Pure Logging
**Rejected**: Too verbose for interactive use, doesn't feel like a coding agent

### No Real-Time Feedback
**Rejected**: Removes user control and trust - can't interrupt bad operations

## Conclusion

This design provides Butler Agent with a professional, coding-agent feel by showing real-time execution transparency. Users can see the agent's thinking, watch tool calls execute, and interrupt if needed. The architecture is extensible for future tools (GitLab, kubectl operations) while maintaining clean, minimal output focused on what's currently happening.

The key insight is that **continuous feedback = user control**, which is essential for building trust in AI-powered infrastructure management.
