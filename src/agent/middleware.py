"""Middleware functions for Butler Agent.

This module provides middleware functions for logging and activity tracking
in the agent request/response pipeline.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from agent_framework import (
    AgentRunContext,
    FunctionInvocationContext,
    FunctionMiddleware,
)

from agent.activity import activity_tracker

logger = logging.getLogger(__name__)


# ============================================================================
# Agent-Level Middleware
# ============================================================================


async def agent_run_logging_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Log agent execution lifecycle and emit LLM request/response events.

    Args:
        context: Agent run context
        next: Next middleware in chain
    """
    from agent.display import (
        LLMRequestEvent,
        LLMResponseEvent,
        get_event_emitter,
        should_show_visualization,
    )

    logger.debug("Agent run starting...")

    # Emit LLM request event
    llm_event_id = None
    if should_show_visualization():
        message_count = len(context.messages) if hasattr(context, "messages") else 0
        event = LLMRequestEvent(message_count=message_count)
        llm_event_id = event.event_id
        get_event_emitter().emit(event)
        logger.debug(f"Emitted LLM request event with {message_count} messages")

    start_time = time.time()

    try:
        await next(context)
        duration = time.time() - start_time
        logger.debug("Agent run completed successfully")

        # Emit LLM response event
        if should_show_visualization() and llm_event_id:
            response_event = LLMResponseEvent(duration=duration)
            response_event.event_id = llm_event_id
            get_event_emitter().emit(response_event)
            logger.debug(f"Emitted LLM response event ({duration:.2f}s)")

    except Exception as e:
        logger.error(f"Agent run failed: {e}")
        raise


async def agent_observability_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Track agent execution metrics and timing.

    Args:
        context: Agent run context
        next: Next middleware in chain
    """
    start_time = time.time()

    try:
        await next(context)
    finally:
        duration = time.time() - start_time
        logger.info(f"Agent execution took {duration:.2f}s")

        # Could send to Application Insights or other observability platform
        # if config.applicationinsights_connection_string:
        #     track_metric("agent_execution_duration", duration)


# ============================================================================
# Function-Level Middleware
# ============================================================================


async def logging_function_middleware(
    context: FunctionInvocationContext,
    next: Callable,
) -> Any:
    """Middleware to log function/tool calls and emit execution events.

    Args:
        context: Function invocation context
        next: Next middleware in chain

    Returns:
        Result from next middleware
    """
    from agent.display import (
        ToolCompleteEvent,
        ToolErrorEvent,
        ToolStartEvent,
        get_event_emitter,
        set_current_tool_event_id,
        should_show_visualization,
    )

    tool_name = context.function.name
    args = context.arguments

    logger.info(f"Tool call: {tool_name}")

    # Emit tool start event (if visualization enabled)
    tool_event_id = None
    if should_show_visualization():
        # Convert args to dict for event (using Pydantic v2 model_dump)
        if hasattr(args, "model_dump"):
            args_dict = args.model_dump()
        elif hasattr(args, "dict"):
            # Fallback for Pydantic v1 compatibility
            args_dict = args.dict()
        elif isinstance(args, dict):
            args_dict = args
        else:
            args_dict = {}
        # Sanitize (remove sensitive keys)
        safe_args = {
            k: v for k, v in args_dict.items() if k not in ["token", "api_key", "password"]
        }

        event = ToolStartEvent(tool_name=tool_name, arguments=safe_args)
        tool_event_id = event.event_id
        get_event_emitter().emit(event)

        # Set tool context for child operations (enables nested event display)
        set_current_tool_event_id(tool_event_id)
        logger.debug(f"Set tool context: {tool_name} (event_id: {tool_event_id[:8]}...)")

    start_time = time.time()

    try:
        result = await next(context)
        duration = time.time() - start_time
        logger.info(f"Tool call {tool_name} completed successfully ({duration:.2f}s)")

        # Emit tool complete event
        if should_show_visualization() and tool_event_id:
            # Extract summary from result
            summary = _extract_tool_summary(tool_name, result)
            complete_event = ToolCompleteEvent(
                tool_name=tool_name,
                result_summary=summary,
                duration=duration,
            )
            complete_event.event_id = tool_event_id
            get_event_emitter().emit(complete_event)

        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Tool call {tool_name} failed: {e}")

        # Emit tool error event
        if should_show_visualization() and tool_event_id:
            error_event = ToolErrorEvent(
                tool_name=tool_name,
                error_message=str(e),
                duration=duration,
            )
            error_event.event_id = tool_event_id
            get_event_emitter().emit(error_event)

        raise
    finally:
        # Clear tool context when exiting tool
        if should_show_visualization():
            set_current_tool_event_id(None)
            logger.debug(f"Cleared tool context: {tool_name}")


def _extract_tool_summary(tool_name: str, result: Any) -> str:
    """Extract human-readable summary from tool result.

    Args:
        tool_name: Name of the tool
        result: Tool result

    Returns:
        Brief summary string
    """
    if isinstance(result, dict):
        if "message" in result:
            return str(result["message"])
        elif "summary" in result:
            return str(result["summary"])
        elif "cluster_name" in result:
            return f"Cluster '{result['cluster_name']}' ready"
    return "Complete"


async def activity_tracking_middleware(
    context: FunctionInvocationContext,
    next: Callable,
) -> Any:
    """Middleware to track current activity.

    Args:
        context: Function invocation context
        next: Next middleware in chain

    Returns:
        Result from next middleware
    """
    tool_name = context.function.name

    # Update activity tracker
    activity_tracker.set_activity(f"Executing: {tool_name}")

    try:
        result = await next(context)
        activity_tracker.reset()
        return result
    except Exception as e:
        activity_tracker.set_activity(f"Error in {tool_name}: {str(e)[:50]}")
        raise


def create_middleware() -> dict[str, list]:
    """Create middleware for agent and function levels.

    Returns:
        Dict with 'agent' and 'function' middleware lists
    """
    return {
        "agent": [
            agent_run_logging_middleware,
            agent_observability_middleware,
        ],
        "function": [
            cast(FunctionMiddleware, logging_function_middleware),
            cast(FunctionMiddleware, activity_tracking_middleware),
        ],
    }


# Backward compatibility
def create_function_middleware() -> list[FunctionMiddleware]:
    """Create list of function middleware (legacy).

    Returns:
        List of function middleware
    """
    return create_middleware()["function"]
