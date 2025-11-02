"""Observability and telemetry integration for Butler Agent.

This module provides optional Azure Application Insights integration for
telemetry, logging, and distributed tracing.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global telemetry state
_telemetry_enabled = False
_connection_string: str | None = None


def initialize_observability(connection_string: str | None = None) -> bool:
    """Initialize observability with Azure Application Insights.

    Args:
        connection_string: Application Insights connection string

    Returns:
        True if initialized successfully, False otherwise
    """
    global _telemetry_enabled, _connection_string

    if not connection_string:
        logger.info("Observability not configured (no connection string provided)")
        return False

    _connection_string = connection_string

    try:
        # Try to import Azure Monitor OpenTelemetry
        from azure.monitor.opentelemetry import configure_azure_monitor

        # Configure Azure Monitor
        configure_azure_monitor(connection_string=connection_string)

        _telemetry_enabled = True
        logger.info("Azure Application Insights telemetry initialized")
        return True

    except ImportError:
        logger.warning(
            "Azure Monitor OpenTelemetry not available. "
            "Install with: pip install azure-monitor-opentelemetry"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")
        return False


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled.

    Returns:
        True if telemetry is enabled
    """
    return _telemetry_enabled


def set_user_context(user_id: str) -> None:
    """Set user context for telemetry.

    Args:
        user_id: User identifier
    """
    if not _telemetry_enabled:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span.set_attribute("user.id", user_id)
            logger.debug(f"Set user context: {user_id}")

    except Exception as e:
        logger.debug(f"Failed to set user context: {e}")


def set_session_context(session_id: str, thread_id: str | None = None) -> None:
    """Set session context for telemetry.

    Args:
        session_id: Session identifier
        thread_id: Optional thread identifier
    """
    if not _telemetry_enabled:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span.set_attribute("session.id", session_id)
            if thread_id:
                span.set_attribute("thread.id", thread_id)
            logger.debug(f"Set session context: {session_id}")

    except Exception as e:
        logger.debug(f"Failed to set session context: {e}")


def set_custom_attributes(**kwargs: Any) -> None:
    """Set custom attributes for current span.

    Args:
        **kwargs: Custom attributes as key-value pairs
    """
    if not _telemetry_enabled:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            for key, value in kwargs.items():
                span.set_attribute(key, str(value))
            logger.debug(f"Set custom attributes: {list(kwargs.keys())}")

    except Exception as e:
        logger.debug(f"Failed to set custom attributes: {e}")


def track_event(name: str, properties: dict[str, Any] | None = None) -> None:
    """Track a custom event.

    Args:
        name: Event name
        properties: Optional event properties
    """
    if not _telemetry_enabled:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes=properties or {})
            logger.debug(f"Tracked event: {name}")

    except Exception as e:
        logger.debug(f"Failed to track event: {e}")
