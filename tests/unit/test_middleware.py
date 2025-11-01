"""Unit tests for middleware functions."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from butler.middleware import (
    activity_tracking_middleware,
    create_function_middleware,
    logging_function_middleware,
)


class TestLoggingFunctionMiddleware:
    """Test logging function middleware."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, caplog):
        """Test middleware logs successful tool execution."""
        context = MagicMock()
        context.function = "test_tool"
        context.arguments = {"arg1": "value1"}

        next_func = AsyncMock(return_value="result")

        with caplog.at_level(logging.INFO):
            result = await logging_function_middleware(context, next_func)

        assert result == "result"
        assert "Tool call: test_tool" in caplog.text
        assert "completed successfully" in caplog.text
        next_func.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_error_handling(self, caplog):
        """Test middleware logs errors."""
        context = MagicMock()
        context.function = "failing_tool"
        context.arguments = {}

        next_func = AsyncMock(side_effect=ValueError("Tool failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="Tool failed"):
                await logging_function_middleware(context, next_func)

        assert "Tool call failing_tool failed" in caplog.text


class TestActivityTrackingMiddleware:
    """Test activity tracking middleware."""

    @pytest.mark.asyncio
    async def test_tracks_activity(self):
        """Test middleware tracks tool execution."""
        context = MagicMock()
        context.function = "test_tool"

        next_func = AsyncMock(return_value="result")

        with patch("butler.middleware.activity_tracker") as mock_tracker:
            result = await activity_tracking_middleware(context, next_func)

        assert result == "result"
        mock_tracker.set_activity.assert_called_once_with("Executing: test_tool")
        mock_tracker.reset.assert_called_once()
        next_func.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_tracks_errors(self):
        """Test middleware tracks errors."""
        context = MagicMock()
        context.function = "failing_tool"

        next_func = AsyncMock(side_effect=ValueError("Error"))

        with patch("butler.middleware.activity_tracker") as mock_tracker:
            with pytest.raises(ValueError):
                await activity_tracking_middleware(context, next_func)

        mock_tracker.set_activity.assert_any_call("Executing: failing_tool")
        assert mock_tracker.set_activity.call_count == 2


class TestCreateFunctionMiddleware:
    """Test middleware factory function."""

    def test_creates_middleware_list(self):
        """Test factory creates list of middleware functions."""
        middleware = create_function_middleware()

        assert len(middleware) == 2
        assert logging_function_middleware in middleware
        assert activity_tracking_middleware in middleware
