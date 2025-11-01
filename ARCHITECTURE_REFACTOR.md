# Butler Agent Architecture Refactoring

## Current Issues

### 1. **Agent Initialization Pattern** ❌
**Problem**: We're manually creating ChatAgent instead of using the framework pattern
```python
# Current (Wrong)
self.llm_client = create_llm_client(config)
self.agent = ChatAgent(chat_client=self.llm_client, ...)
```

**Solution**: Use client.create_agent() pattern
```python
# Correct
agent = client.create_agent(instructions="...", name="Butler", tools=tools)
```

### 2. **No Multi-turn Conversation Support** ❌
**Problem**: Single-turn only, no conversation context
**Solution**: Implement AgentThread for conversation management

### 3. **Untestable Architecture** ❌
**Problem**:
- Tight coupling between components
- No dependency injection
- Can't mock LLM clients
- 0% test coverage

**Solution**:
- Dependency injection
- Mock client implementations
- Proper test fixtures

### 4. **Over-Complex Configuration** ❌
**Problem**: Too many environment variables, complex validation
**Solution**: Simplify to essential config only

## Refactoring Plan

### Phase 1: Client Simplification (High Priority)
1. Simplify `llm_client.py` to return chat clients directly
2. Remove complex factory pattern
3. Follow framework's client creation pattern

### Phase 2: Agent Architecture (High Priority)
1. Refactor `Agent` class to use `client.create_agent()`
2. Add thread support for conversations
3. Simplify initialization

### Phase 3: Testability (High Priority)
1. Create mock chat client for testing
2. Add dependency injection
3. Create test fixtures and helpers
4. Write unit tests for:
   - Configuration loading
   - Client creation
   - Agent initialization
   - Tool execution (mocked)
   - CLI commands (mocked)

### Phase 4: Documentation & Cleanup
1. Update README with new patterns
2. Add architecture diagrams
3. Document testing approach

## Target Architecture

```python
# Simple client creation
client = AzureOpenAIChatClient(
    endpoint=config.azure_openai_endpoint,
    credential=DefaultAzureCredential(),
    model=config.model_name
)

# Agent creation using framework pattern
agent = client.create_agent(
    instructions=SYSTEM_PROMPT,
    name="Butler",
    tools=CLUSTER_TOOLS
)

# Multi-turn conversation
thread = agent.get_new_thread()
response = await agent.run("create cluster", thread)
response = await agent.run("show status", thread)  # Context preserved
```

## Testing Strategy

1. **Unit Tests** - Test individual components with mocks
2. **Integration Tests** - Test with real Azure (optional)
3. **Mock Client** - Fake LLM responses for deterministic tests

## Success Criteria

- ✅ 60%+ test coverage
- ✅ All quality checks pass (Black, Ruff, MyPy)
- ✅ Follow Microsoft Agent Framework patterns
- ✅ Dependency injection throughout
- ✅ Multi-turn conversation support
- ✅ Maintainable, clean code
