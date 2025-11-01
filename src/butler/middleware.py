"""Middleware functions for Butler Agent.

This module provides middleware functions for logging and activity tracking
in the agent request/response pipeline.
"""

import logging
from collections.abc import Callable
from typing import Any

from agent_framework import ChatMessage, FunctionInvocationContext, FunctionMiddleware

from butler.activity import activity_tracker

logger = logging.getLogger(__name__)


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
    tool_name = context.function_name
    args = context.arguments

    logger.info(f"Tool call: {tool_name} with args: {args}")

    try:
        result = await next(context)
        logger.info(f"Tool call {tool_name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool call {tool_name} failed: {e}")
        raise


async def logging_chat_middleware(
    messages: list[ChatMessage],
    next: Callable,
) -> Any:
    """Middleware to log chat interactions.

    Args:
        messages: Chat messages
        next: Next middleware in chain

    Returns:
        Result from next middleware
    """
    # Log the last user message
    user_messages = [m for m in messages if m.role == "user"]
    if user_messages:
        last_message = user_messages[-1]
        logger.info(f"User query: {last_message.content[:100]}...")

    try:
        result = await next(messages)
        logger.debug("Chat completion successful")
        return result
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
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
    tool_name = context.function_name

    # Update activity tracker
    activity_tracker.set_activity(f"Executing: {tool_name}")

    try:
        result = await next(context)
        activity_tracker.reset()
        return result
    except Exception as e:
        activity_tracker.set_activity(f"Error in {tool_name}: {str(e)[:50]}")
        raise


def create_function_middleware() -> list[FunctionMiddleware]:
    """Create list of function middleware.

    Returns:
        List of middleware functions
    """
    return [
        logging_function_middleware,
        activity_tracking_middleware,
    ]
