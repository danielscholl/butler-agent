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
    """Log agent execution lifecycle.

    Args:
        context: Agent run context
        next: Next middleware in chain
    """
    logger.debug("Agent run starting...")

    try:
        await next(context)
        logger.debug("Agent run completed successfully")
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
    """Middleware to log function/tool calls.

    Args:
        context: Function invocation context
        next: Next middleware in chain

    Returns:
        Result from next middleware
    """
    tool_name = context.function.name
    args = context.arguments

    logger.info(f"Tool call: {tool_name} with args: {args}")

    try:
        result = await next(context)
        logger.info(f"Tool call {tool_name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool call {tool_name} failed: {e}")
        raise


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
