"""Unit tests for middleware."""

from unittest.mock import MagicMock

import pytest
from agent_framework import AgentRunContext, FunctionInvocationContext

from agent.middleware import (
    activity_tracking_middleware,
    agent_observability_middleware,
    agent_run_logging_middleware,
    create_middleware,
    logging_function_middleware,
)


@pytest.fixture
def mock_agent_context():
    """Create mock AgentRunContext."""
    context = MagicMock(spec=AgentRunContext)
    return context


@pytest.fixture
def mock_function_context():
    """Create mock FunctionInvocationContext."""
    context = MagicMock(spec=FunctionInvocationContext)
    context.function = MagicMock()
    context.function.name = "test_function"
    context.arguments = {"arg1": "value1"}
    return context


class TestAgentMiddleware:
    """Test suite for agent-level middleware."""

    @pytest.mark.asyncio
    async def test_agent_run_logging_middleware_success(self, mock_agent_context):
        """Test agent run logging middleware with successful execution."""
        next_called = False

        async def mock_next(ctx):
            nonlocal next_called
            next_called = True

        await agent_run_logging_middleware(mock_agent_context, mock_next)

        assert next_called

    @pytest.mark.asyncio
    async def test_agent_run_logging_middleware_error(self, mock_agent_context):
        """Test agent run logging middleware with error."""

        async def mock_next(ctx):
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await agent_run_logging_middleware(mock_agent_context, mock_next)

    @pytest.mark.asyncio
    async def test_agent_observability_middleware(self, mock_agent_context):
        """Test agent observability middleware tracks timing."""
        next_called = False

        async def mock_next(ctx):
            nonlocal next_called
            next_called = True

        await agent_observability_middleware(mock_agent_context, mock_next)

        assert next_called

    @pytest.mark.asyncio
    async def test_agent_observability_middleware_with_error(self, mock_agent_context):
        """Test observability middleware completes timing even with errors."""

        async def mock_next(ctx):
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            await agent_observability_middleware(mock_agent_context, mock_next)


class TestFunctionMiddleware:
    """Test suite for function-level middleware."""

    @pytest.mark.asyncio
    async def test_logging_function_middleware_success(self, mock_function_context):
        """Test function logging middleware with successful execution."""
        next_called = False

        async def mock_next(ctx):
            nonlocal next_called
            next_called = True
            return "result"

        result = await logging_function_middleware(mock_function_context, mock_next)

        assert next_called
        assert result == "result"

    @pytest.mark.asyncio
    async def test_logging_function_middleware_error(self, mock_function_context):
        """Test function logging middleware with error."""

        async def mock_next(ctx):
            raise ValueError("Function failed")

        with pytest.raises(ValueError, match="Function failed"):
            await logging_function_middleware(mock_function_context, mock_next)

    @pytest.mark.asyncio
    async def test_activity_tracking_middleware(self, mock_function_context):
        """Test activity tracking middleware."""
        next_called = False

        async def mock_next(ctx):
            nonlocal next_called
            next_called = True
            return "result"

        result = await activity_tracking_middleware(mock_function_context, mock_next)

        assert next_called
        assert result == "result"

    @pytest.mark.asyncio
    async def test_activity_tracking_middleware_error(self, mock_function_context):
        """Test activity tracking middleware with error."""

        async def mock_next(ctx):
            raise RuntimeError("Activity failed")

        with pytest.raises(RuntimeError, match="Activity failed"):
            await activity_tracking_middleware(mock_function_context, mock_next)


class TestMiddlewareFactory:
    """Test suite for middleware factory."""

    def test_create_middleware_returns_dict(self):
        """Test create_middleware returns dict with agent and function keys."""
        middleware = create_middleware()

        assert isinstance(middleware, dict)
        assert "agent" in middleware
        assert "function" in middleware

    def test_create_middleware_agent_list(self):
        """Test agent middleware list contains expected middleware."""
        middleware = create_middleware()
        agent_middleware = middleware["agent"]

        assert isinstance(agent_middleware, list)
        assert len(agent_middleware) == 2
        assert agent_run_logging_middleware in agent_middleware
        assert agent_observability_middleware in agent_middleware

    def test_create_middleware_function_list(self):
        """Test function middleware list contains expected middleware."""
        middleware = create_middleware()
        function_middleware = middleware["function"]

        assert isinstance(function_middleware, list)
        assert len(function_middleware) == 2
