"""Hierarchical execution tree display using Rich Live.

Adapted from osdu-agent for Butler's cluster management operations.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from agent.display.events import (
    AddonProgressEvent,
    EventEmitter,
    ExecutionEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
    ToolStartEvent,
    get_event_emitter,
)

logger = logging.getLogger(__name__)


class DisplayMode(Enum):
    """Display mode for execution tree.

    MINIMAL: Show active work only (default, clean)
    VERBOSE: Show all phases with full details
    """

    MINIMAL = "minimal"
    VERBOSE = "verbose"


# Symbols (Butler-themed)
SYMBOL_ACTIVE = "●"  # Active/working
SYMBOL_COMPLETE = "•"  # Completed
SYMBOL_TOOL = "→"  # Tool executing
SYMBOL_SUCCESS = "✓"  # Success
SYMBOL_ERROR = "✗"  # Error

# Colors
COLOR_ACTIVE = "yellow"
COLOR_COMPLETE = "dim white"
COLOR_SUCCESS = "green"
COLOR_ERROR = "red"


class TreeNode:
    """Node in the execution tree."""

    def __init__(self, event_id: str, label: str, status: str = "in_progress"):
        """Initialize tree node.

        Args:
            event_id: Unique identifier matching the event
            label: Display label
            status: Current status (in_progress, completed, error)
        """
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
        """Mark node as completed.

        Args:
            summary: Optional summary message
            duration: Optional duration in seconds
        """
        self.status = "completed"
        self.end_time = datetime.now()
        if summary:
            self.metadata["summary"] = summary
        if duration is not None:
            self.metadata["duration"] = duration

    def mark_error(self, error_message: str, duration: Optional[float] = None) -> None:
        """Mark node as error.

        Args:
            error_message: Error description
            duration: Optional duration in seconds
        """
        self.status = "error"
        self.end_time = datetime.now()
        self.metadata["error"] = error_message
        if duration is not None:
            self.metadata["duration"] = duration


class ExecutionPhase:
    """Represents a reasoning phase (LLM thinking + tool calls).

    A phase groups together:
    - One LLM request/response pair
    - Zero or more tool calls made during that thinking cycle
    """

    def __init__(self, phase_number: int):
        """Initialize execution phase.

        Args:
            phase_number: Sequential number for this phase
        """
        self.phase_number = phase_number
        self.llm_node: Optional[TreeNode] = None
        self.tool_nodes: list[TreeNode] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "in_progress"

    def add_llm_node(self, node: TreeNode) -> None:
        """Add LLM thinking node to this phase."""
        self.llm_node = node

    def add_tool_node(self, node: TreeNode) -> None:
        """Add tool execution node to this phase."""
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
    """Hierarchical execution tree display using Rich Live.

    This class manages a tree of execution events and renders them
    in real-time using Rich's Live display with visual hierarchy.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        display_mode: DisplayMode = DisplayMode.MINIMAL,
        show_completion_summary: bool = True,
    ):
        """Initialize execution tree display.

        Args:
            console: Rich console to use (creates new one if not provided)
            display_mode: Display verbosity level (MINIMAL or VERBOSE)
            show_completion_summary: Whether to show completion summary
        """
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

    def _render_node(self, node: TreeNode) -> RenderableType:
        """Render a node with its children.

        Args:
            node: Node to render

        Returns:
            Rich renderable (Text or Tree)
        """
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
                tree.add(child_renderable)
            return tree
        else:
            return label_text

    def _render_phases(self) -> RenderableType:
        """Render execution using phase-based view.

        Returns:
            Rich renderable with phase-grouped display
        """
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

            elif (
                completed_count == total_phases
                and total_phases > 0
                and self.show_completion_summary
            ):
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
                    style=COLOR_SUCCESS,
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

        return (
            Group(*renderables)
            if renderables
            else Text(f"{SYMBOL_ACTIVE} Thinking...", style=COLOR_ACTIVE)
        )

    async def _handle_event(self, event: ExecutionEvent) -> None:
        """Handle a single event.

        Args:
            event: Event to handle
        """
        logger.debug(f"Processing event: {type(event).__name__} - {event.event_id}")

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
        """Background task to process events from the queue."""
        while self._running:
            try:
                # Get events with timeout to allow checking _running flag
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
                logger.warning(f"Error processing execution tree event: {e}", exc_info=True)
                # Continue processing other events

    async def start(self) -> None:
        """Start the execution tree display.

        This starts the Rich Live display and background event processing.
        """
        if self._running:
            return

        self._running = True

        # Clear any stale events from previous runs
        self._event_emitter.clear()

        # Reset display state for clean start
        self._node_map.clear()
        self._phases.clear()
        self._current_phase = None
        self._session_start_time = datetime.now()

        # Start Rich Live display with reasonable refresh rate
        # 10Hz (100ms) provides smooth updates without excessive CPU usage
        self._live = Live(
            self._render_phases(),
            console=self.console,
            refresh_per_second=10,  # Smooth updates
            transient=not self.show_completion_summary,  # Transient when no completion summary
        )
        self._live.start()

        # Start background event processing task
        self._task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the execution tree display."""
        if not self._running:
            return

        # Process any remaining events before stopping
        while True:
            event = await self._event_emitter.get_event_nowait()
            if event is None:
                break
            await self._handle_event(event)

        # Complete any active phase
        if self._current_phase and self._current_phase.status == "in_progress":
            self._current_phase.complete()

        self._running = False

        # Cancel background task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass  # Expected

        # Stop Rich Live display
        if self._live:
            if self.show_completion_summary:
                # Non-transient: final render persists, so update before stopping
                self._live.update(self._render_phases())
            # Stop the live display
            self._live.stop()

            # Only add blank line for spacing if showing completion summary
            if self.show_completion_summary:
                self.console.print()

    async def __aenter__(self) -> "ExecutionTreeDisplay":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
