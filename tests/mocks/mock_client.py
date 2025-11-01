"""Mock chat client and agent for testing."""

from typing import Any


class MockAgent:
    """Mock agent for testing.

    This mock agent simulates the behavior of a ChatAgent without making
    real LLM API calls.
    """

    def __init__(
        self,
        name: str = "MockAgent",
        instructions: str = "",
        tools: list[Any] | None = None,
        middleware: Any | None = None,
        responses: list[str] | None = None,
    ):
        """Initialize mock agent.

        Args:
            name: Agent name
            instructions: Agent instructions/system prompt
            tools: List of tools available to agent
            middleware: Middleware for function calls
            responses: List of responses to return in sequence (cycles through)
        """
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        self.middleware = middleware
        self.responses = responses or ["Mock response"]
        self._response_index = 0
        self._threads = []

    async def run(self, query: str, thread: Any | None = None) -> "MockResponse":
        """Run a query and return mock response.

        Args:
            query: User query
            thread: Optional conversation thread

        Returns:
            Mock response with text attribute
        """
        response = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1
        return MockResponse(response)

    async def run_stream(self, query: str, thread: Any | None = None):
        """Run a query with streaming response.

        Args:
            query: User query
            thread: Optional conversation thread

        Yields:
            Mock response chunks
        """
        response = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1
        # Split response into chunks to simulate streaming
        for word in response.split():
            yield MockResponse(word + " ")

    def get_new_thread(self) -> "MockThread":
        """Create a new conversation thread.

        Returns:
            New mock thread
        """
        thread = MockThread()
        self._threads.append(thread)
        return thread


class MockResponse:
    """Mock response object with text attribute."""

    def __init__(self, text: str):
        """Initialize mock response.

        Args:
            text: Response text
        """
        self.text = text
        self.content = text

    def __str__(self) -> str:
        """Return string representation."""
        return self.text


class MockThread:
    """Mock conversation thread for multi-turn conversations."""

    def __init__(self):
        """Initialize mock thread."""
        self.messages: list[dict[str, str]] = []
        self.id = f"mock_thread_{id(self)}"

    def add_message(self, role: str, content: str):
        """Add message to thread.

        Args:
            role: Message role (user/assistant)
            content: Message content
        """
        self.messages.append({"role": role, "content": content})


class MockChatClient:
    """Mock chat client for testing.

    This mock client simulates BaseChatClient without making real API calls.
    """

    def __init__(
        self,
        model_id: str = "mock-model",
        api_key: str | None = None,
        responses: list[str] | None = None,
    ):
        """Initialize mock chat client.

        Args:
            model_id: Model identifier
            api_key: API key (not used in mock)
            responses: List of responses to return from agent
        """
        self.model_id = model_id
        self.api_key = api_key
        self.responses = responses or ["Mock response"]
        self._agents: list[MockAgent] = []

    def create_agent(
        self,
        name: str = "Agent",
        instructions: str = "",
        tools: list[Any] | None = None,
        middleware: Any | None = None,
        **kwargs: Any,
    ) -> MockAgent:
        """Create a mock agent.

        Args:
            name: Agent name
            instructions: Agent instructions
            tools: Agent tools
            middleware: Function middleware
            **kwargs: Additional arguments (ignored)

        Returns:
            Mock agent
        """
        agent = MockAgent(
            name=name,
            instructions=instructions,
            tools=tools,
            middleware=middleware,
            responses=self.responses,
        )
        self._agents.append(agent)
        return agent

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Mock completion method.

        Args:
            messages: Conversation messages
            **kwargs: Additional arguments

        Returns:
            Mock completion response
        """
        return {"choices": [{"message": {"role": "assistant", "content": self.responses[0]}}]}
