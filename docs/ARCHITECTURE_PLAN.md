# Butler Agent - Architecture Refactor Plan

## Executive Summary

Refactoring Butler Agent to follow Microsoft Agent Framework best practices, focusing on:
- ✅ Proper framework patterns
- ✅ Testability (60%+ coverage target)
- ✅ Multi-turn conversation support
- ✅ Clean, maintainable code

## Current State Analysis

### What Works ✅
- Multi-provider support (Azure OpenAI, OpenAI)
- gpt-5-codex and gpt-5-mini model support
- Tool definitions with @ai_function decorators
- Configuration management via environment variables
- All MyPy type errors fixed

### What Needs Fixing ❌
1. **Not using framework patterns** - Manual ChatAgent creation instead of `client.create_agent()`
2. **No testability** - 0% coverage, tightly coupled, can't mock
3. **No multi-turn support** - Single queries only, no conversation threads
4. **Over-engineered** - Complex factory patterns where simple is better

## Architecture Refactor

### 1. Client Creation Pattern

**Before (Wrong):**
```python
# src/butler/llm_client.py - Complex factory
def create_llm_client(config: ButlerConfig) -> Any:
    # 200+ lines of complex logic
    if provider == "azure":
        return _create_azure_openai_client(config)
    # ...
```

**After (Correct):**
```python
# src/butler/clients.py - Simple, framework-aligned
def create_chat_client(config: ButlerConfig) -> BaseChatClient:
    """Create chat client following framework patterns."""
    if config.llm_provider == "azure":
        return AzureOpenAIChatClient(
            endpoint=config.azure_openai_endpoint,
            credential=DefaultAzureCredential(),
            model_id=config.model_name or "gpt-5-codex",
        )
    elif config.llm_provider == "openai":
        # Use OpenAIResponsesClient for codex, OpenAIChatClient for others
        if "codex" in (config.model_name or "").lower():
            return OpenAIResponsesClient(
                model_id=config.model_name,
                api_key=config.openai_api_key,
            )
        return OpenAIChatClient(
            model_id=config.model_name or "gpt-5-mini",
            api_key=config.openai_api_key,
        )
    raise ValueError(f"Unsupported provider: {config.llm_provider}")
```

### 2. Agent Creation Pattern

**Before (Wrong):**
```python
# src/butler/agent.py
class Agent:
    def __init__(self, config: ButlerConfig):
        self.llm_client = create_llm_client(config)
        self.agent = ChatAgent(
            chat_client=self.llm_client,
            instructions=SYSTEM_PROMPT,
            tools=tools,
            middleware=middleware,
        )
```

**After (Correct):**
```python
# src/butler/agent.py
class ButlerAgent:
    """Butler Agent for Kubernetes management."""

    def __init__(
        self,
        chat_client: BaseChatClient | None = None,
        config: ButlerConfig | None = None,
    ):
        """Initialize Butler Agent.

        Args:
            chat_client: Pre-configured chat client (for testing)
            config: Configuration (will create client if not provided)
        """
        if chat_client is None:
            if config is None:
                config = ButlerConfig()
            chat_client = create_chat_client(config)

        self.config = config or ButlerConfig()
        self.chat_client = chat_client

        # Use framework pattern
        self.agent = chat_client.create_agent(
            name="Butler",
            instructions=SYSTEM_PROMPT,
            tools=CLUSTER_TOOLS,
            middleware=create_function_middleware(),
        )

    async def run(self, query: str, thread: AgentThread | None = None) -> str:
        """Run agent with optional conversation thread."""
        if thread is None:
            thread = self.agent.get_new_thread()

        response = await self.agent.run(query, thread)

        # Extract text from ChatMessage
        if hasattr(response, "text"):
            return str(response.text)
        return str(response)

    def get_new_thread(self) -> AgentThread:
        """Create new conversation thread."""
        return self.agent.get_new_thread()
```

### 3. Testing Architecture

**Create Mock Client:**
```python
# tests/mocks/mock_client.py
from agent_framework import BaseChatClient, ChatMessage, AgentThread

class MockChatClient(BaseChatClient):
    """Mock chat client for testing."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["Mock response"]
        self.call_count = 0

    def create_agent(self, **kwargs):
        """Create a mock agent."""
        return MockAgent(self)

    async def get_response(self, messages, **kwargs):
        """Return mock response."""
        response_text = self.responses[
            self.call_count % len(self.responses)
        ]
        self.call_count += 1
        return ChatMessage(role="assistant", text=response_text)
```

**Unit Tests:**
```python
# tests/unit/test_agent.py
from butler.agent import ButlerAgent
from tests.mocks.mock_client import MockChatClient

def test_agent_initialization():
    """Test agent can be created with mock client."""
    mock_client = MockChatClient()
    agent = ButlerAgent(chat_client=mock_client)
    assert agent is not None

async def test_agent_run():
    """Test agent can run queries."""
    mock_client = MockChatClient(responses=["Hello!"])
    agent = ButlerAgent(chat_client=mock_client)

    response = await agent.run("hi")
    assert response == "Hello!"

async def test_multi_turn_conversation():
    """Test multi-turn conversations preserve context."""
    mock_client = MockChatClient(responses=["Created!", "Running"])
    agent = ButlerAgent(chat_client=mock_client)

    thread = agent.get_new_thread()
    response1 = await agent.run("create cluster", thread)
    response2 = await agent.run("check status", thread)

    assert response1 == "Created!"
    assert response2 == "Running"
```

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create `tests/mocks/mock_client.py`
- [ ] Simplify `src/butler/clients.py` (rename from llm_client.py)
- [ ] Refactor `src/butler/agent.py` to use dependency injection
- [ ] Add `get_new_thread()` support

### Phase 2: Testing
- [ ] Create test fixtures in `tests/conftest.py`
- [ ] Add unit tests for `ButlerConfig`
- [ ] Add unit tests for `create_chat_client()`
- [ ] Add unit tests for `ButlerAgent`
- [ ] Add unit tests for CLI commands (mocked)
- [ ] Target: 60%+ coverage

### Phase 3: Integration
- [ ] Update CLI to support multi-turn mode
- [ ] Add interactive conversation mode
- [ ] Test end-to-end with real Azure/OpenAI

### Phase 4: Documentation
- [ ] Update README with new patterns
- [ ] Add testing guide
- [ ] Document architecture decisions

## Success Criteria

- ✅ All tests pass
- ✅ 60%+ test coverage
- ✅ MyPy, Black, Ruff all pass
- ✅ Follows Microsoft Agent Framework patterns
- ✅ Multi-turn conversation support
- ✅ Fully testable with mocks
- ✅ Clean, maintainable code

## Timeline

Estimated: 2-3 hours of focused work

## References

- [Run Agent Tutorial](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/run-agent)
- [Multi-turn Conversations](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/multi-turn-conversation)
- [Function Tools](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/function-tools)
- [Tool Approvals](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/function-tools-approvals)
