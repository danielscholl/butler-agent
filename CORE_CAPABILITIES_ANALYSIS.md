# Butler Agent Core Capabilities Analysis
## Memory, Persistence, History, and Middleware

**Focus:** Agent infrastructure capabilities (not tools)
**Date:** 2025-11-01
**Status:** Foundation Phase 1 Review

---

## 🔍 Gap Analysis Summary

After comparing our implementation with Microsoft Agent Framework best practices, we have **significant room for improvement** in 4 core areas:

| Capability | Current Status | Framework Support | Gap | Priority |
|------------|---------------|-------------------|-----|----------|
| **Middleware** | ⚠️ Partial | Full agent + function | Missing agent middleware | HIGH |
| **Memory** | ❌ Missing | ContextProvider pattern | Not implemented | MEDIUM |
| **Persistence** | ❌ Missing | Thread serialization | Not implemented | HIGH |
| **History** | ⚠️ Default only | Custom ChatMessageStore | Using in-memory default | MEDIUM |

---

## 1. 🔧 Middleware: Incomplete Implementation

### Current State

**What we have:**
```python
# src/butler/middleware.py

# ✅ Function middleware (IMPLEMENTED)
async def logging_function_middleware(context: FunctionInvocationContext, next: Callable) -> Any:
    tool_name = context.function.name
    logger.info(f"Tool call: {tool_name} with args: {context.arguments}")
    await next(context)

async def activity_tracking_middleware(context: FunctionInvocationContext, next: Callable) -> Any:
    tool_name = context.function.name
    activity_tracker.set_activity(f"Executing: {tool_name}")
    await next(context)
```

**What we're NOT using:**
```python
# ⚠️ DEFINED BUT UNUSED!
async def logging_chat_middleware(messages: list[ChatMessage], next: Callable) -> Any:
    """Middleware to log chat interactions."""
    user_messages = [m for m in messages if m.role == "user"]
    if user_messages:
        last_message = user_messages[-1]
        logger.info(f"User query: {message_text[:100]}...")
    await next(messages)
```

### The Gap

**Problem:** We only pass function middleware to the agent, not agent-level middleware.

```python
# src/butler/agent.py:119
middleware = create_function_middleware()  # Only function middleware!

self.agent = self.chat_client.create_agent(
    name="Butler",
    instructions=SYSTEM_PROMPT,
    tools=tools,
    middleware=middleware,  # Missing agent middleware
)
```

### What We Should Have

According to the docs (ai-docs/middleware.md), we can have **both** agent middleware and function middleware:

```python
from agent_framework import AgentRunContext

# Agent-level middleware (intercepts agent runs)
async def logging_agent_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Log agent execution start/end."""
    print("Agent starting...")
    await next(context)
    print("Agent finished!")

# Function-level middleware (intercepts tool calls)
async def logging_function_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """Log function calls."""
    print(f"Calling function: {context.function.name}")
    await next(context)
    print(f"Function result: {context.result}")
```

### Recommended Implementation

**Step 1:** Update middleware.py to include agent middleware

```python
# src/butler/middleware.py

from agent_framework import AgentRunContext
from collections.abc import Awaitable

async def agent_run_logging_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Log agent execution lifecycle."""
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
    """Track agent execution metrics."""
    import time
    start_time = time.time()

    try:
        await next(context)
    finally:
        duration = time.time() - start_time
        logger.info(f"Agent execution took {duration:.2f}s")
        # Could send to Application Insights here

def create_middleware() -> dict:
    """Create both agent and function middleware.

    Returns:
        Dict with 'agent' and 'function' middleware lists
    """
    return {
        'agent': [
            agent_run_logging_middleware,
            agent_observability_middleware,
        ],
        'function': [
            logging_function_middleware,
            activity_tracking_middleware,
        ]
    }
```

**Step 2:** Update agent.py to use both middleware types

```python
# src/butler/agent.py

from butler.middleware import create_middleware

# In __init__:
middleware = create_middleware()

self.agent = self.chat_client.create_agent(
    name="Butler",
    instructions=SYSTEM_PROMPT,
    tools=tools,
    middleware=middleware['function'],  # Function middleware
    # Note: Agent middleware might need to be passed differently
    # depending on the framework version
)
```

**Impact:**
- Better observability of agent execution
- Performance metrics
- Centralized error handling
- Request/response logging

**Effort:** 2-3 hours

---

## 2. 🧠 Memory: Not Implemented

### Current State

**Status:** ❌ Not implemented

We have **no memory capability**. Each conversation starts fresh with no context about:
- User preferences (e.g., default cluster config)
- Previously created cluster names
- User's typical workflows
- Learned behaviors

### The Gap

The framework provides `ContextProvider` pattern for adding memory (ai-docs/memory.md):

```python
from agent_framework import ContextProvider, Context

class UserInfoMemory(ContextProvider):
    """Remember information about the user."""

    async def invoking(self, messages, **kwargs) -> Context:
        """Provide context before agent invocation."""
        # Add instructions with remembered information
        return Context(instructions="User's name is John...")

    async def invoked(self, request_messages, response_messages, **kwargs):
        """Learn from the conversation."""
        # Extract and store information from messages
        pass
```

### Recommended Implementation

**Create:** `src/butler/memory.py`

```python
"""Memory and context providers for Butler Agent."""

from typing import Any, Sequence
from pydantic import BaseModel
from agent_framework import ContextProvider, Context, ChatMessage


class ClusterPreferences(BaseModel):
    """User's cluster preferences and history."""
    default_config: str | None = None  # "minimal", "default", "custom"
    default_k8s_version: str | None = None
    recent_cluster_names: list[str] = []
    preferred_naming_pattern: str | None = None


class ClusterMemory(ContextProvider):
    """Remember user's cluster preferences and patterns."""

    def __init__(self, chat_client=None):
        """Initialize with empty preferences."""
        self.preferences = ClusterPreferences()
        self._chat_client = chat_client

    async def invoking(
        self,
        messages: ChatMessage | list[ChatMessage],
        **kwargs: Any
    ) -> Context:
        """Provide cluster preferences before agent invocation."""
        instructions = []

        # Add context about user's preferences
        if self.preferences.default_config:
            instructions.append(
                f"User typically prefers '{self.preferences.default_config}' "
                f"cluster configuration."
            )

        if self.preferences.default_k8s_version:
            instructions.append(
                f"User's default Kubernetes version is "
                f"{self.preferences.default_k8s_version}."
            )

        if self.preferences.recent_cluster_names:
            recent = ", ".join(self.preferences.recent_cluster_names[-3:])
            instructions.append(
                f"User's recent cluster names: {recent}. "
                f"Suggest similar naming patterns."
            )

        if instructions:
            return Context(instructions=" ".join(instructions))
        return Context()

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        **kwargs: Any,
    ) -> None:
        """Learn from cluster operations in the conversation."""
        # Extract cluster creation patterns
        if isinstance(request_messages, ChatMessage):
            request_messages = [request_messages]

        for msg in request_messages:
            text = getattr(msg, "text", "")

            # Look for cluster configuration preferences
            if "minimal" in text.lower():
                self.preferences.default_config = "minimal"
            elif "custom" in text.lower():
                self.preferences.default_config = "custom"

            # Extract cluster names (simple pattern matching)
            # In production, use the chat client with structured output
            import re
            cluster_matches = re.findall(r'cluster[- ](?:called|named) ([a-z0-9-]+)', text.lower())
            for cluster_name in cluster_matches:
                if cluster_name not in self.preferences.recent_cluster_names:
                    self.preferences.recent_cluster_names.append(cluster_name)
                    # Keep only last 10
                    if len(self.preferences.recent_cluster_names) > 10:
                        self.preferences.recent_cluster_names.pop(0)

    def serialize(self) -> dict:
        """Serialize preferences for persistence."""
        return self.preferences.model_dump()

    @classmethod
    def deserialize(cls, data: dict):
        """Deserialize preferences from stored data."""
        memory = cls()
        memory.preferences = ClusterPreferences.model_validate(data)
        return memory


class ConversationMetricsMemory(ContextProvider):
    """Track conversation metrics and provide insights."""

    def __init__(self):
        self.total_queries = 0
        self.clusters_created = 0
        self.clusters_deleted = 0
        self.errors_encountered = 0

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Track metrics from conversations."""
        self.total_queries += 1

        if invoke_exception:
            self.errors_encountered += 1

        # Track operations from response (simplified)
        if response_messages:
            response_text = ""
            if isinstance(response_messages, list):
                for msg in response_messages:
                    response_text += str(getattr(msg, "text", ""))
            else:
                response_text = str(getattr(response_messages, "text", ""))

            if "created successfully" in response_text.lower():
                self.clusters_created += 1
            elif "deleted successfully" in response_text.lower():
                self.clusters_deleted += 1

    async def invoking(self, messages, **kwargs) -> Context:
        """Provide metrics context periodically."""
        # Every 10 queries, remind agent of metrics
        if self.total_queries > 0 and self.total_queries % 10 == 0:
            return Context(
                instructions=f"Session stats: {self.clusters_created} clusters created, "
                f"{self.clusters_deleted} deleted, {self.errors_encountered} errors."
            )
        return Context()

    def serialize(self) -> dict:
        """Serialize metrics."""
        return {
            'total_queries': self.total_queries,
            'clusters_created': self.clusters_created,
            'clusters_deleted': self.clusters_deleted,
            'errors_encountered': self.errors_encountered,
        }
```

**Step 2:** Update agent.py to use memory

```python
# src/butler/agent.py

from butler.memory import ClusterMemory, ConversationMetricsMemory

class ButlerAgent:
    def __init__(
        self,
        config: ButlerConfig | None = None,
        chat_client: Any | None = None,
        mcp_tools: list | None = None,
        enable_memory: bool = True,  # New parameter
    ):
        # ... existing code ...

        # Create memory providers if enabled
        context_providers = []
        if enable_memory:
            context_providers = [
                ClusterMemory(chat_client=self.chat_client),
                ConversationMetricsMemory(),
            ]

        # Create agent with memory
        self.agent = self.chat_client.create_agent(
            name="Butler",
            instructions=SYSTEM_PROMPT,
            tools=tools,
            middleware=middleware,
            context_providers=context_providers if context_providers else None,
        )
```

**Benefits:**
- Personalized experience
- Learns user preferences over time
- Better suggestions based on history
- Session metrics and insights

**Effort:** 4-6 hours

---

## 3. 💾 Persistence: Not Implemented

### Current State

**Status:** ❌ Not implemented

We have **no thread persistence**. When the CLI exits:
- All conversation history is lost
- Users can't save interesting conversations
- No way to resume previous sessions
- No conversation management

### The Gap

The framework provides thread serialization (ai-docs/persistence.md):

```python
# Save conversation
serialized_thread = await thread.serialize()
# Store to file/database

# Load conversation
loaded_data = json.loads(saved_json)
resumed_thread = await agent.deserialize_thread(loaded_data)
```

### Recommended Implementation

**Create:** `src/butler/persistence.py`

```python
"""Thread persistence for Butler Agent."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ThreadPersistence:
    """Manage thread serialization and storage."""

    def __init__(self, storage_dir: Path | None = None):
        """Initialize persistence manager.

        Args:
            storage_dir: Directory for storing conversations
                        (default: ~/.butler/conversations)
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".butler" / "conversations"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file tracks all conversations
        self.metadata_file = self.storage_dir / "index.json"
        self._load_metadata()

    def _load_metadata(self):
        """Load conversation metadata index."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {'conversations': {}}

    def _save_metadata(self):
        """Save conversation metadata index."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    async def save_thread(
        self,
        thread: Any,
        name: str,
        description: str | None = None,
    ) -> Path:
        """Save a conversation thread.

        Args:
            thread: AgentThread to serialize
            name: Name for this conversation
            description: Optional description

        Returns:
            Path to saved conversation file
        """
        logger.info(f"Saving conversation '{name}'...")

        try:
            # Serialize thread
            serialized = await thread.serialize()

            # Add metadata
            conversation_data = {
                'name': name,
                'description': description,
                'created_at': datetime.now().isoformat(),
                'thread': serialized,
            }

            # Save to file
            file_path = self.storage_dir / f"{name}.json"
            with open(file_path, 'w') as f:
                json.dump(conversation_data, f, indent=2)

            # Update metadata index
            self.metadata['conversations'][name] = {
                'description': description,
                'created_at': conversation_data['created_at'],
                'file': str(file_path),
            }
            self._save_metadata()

            logger.info(f"Conversation saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            raise

    async def load_thread(self, agent: Any, name: str) -> Any:
        """Load a conversation thread.

        Args:
            agent: ButlerAgent instance for deserialization
            name: Name of conversation to load

        Returns:
            Deserialized AgentThread
        """
        logger.info(f"Loading conversation '{name}'...")

        file_path = self.storage_dir / f"{name}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Conversation '{name}' not found")

        try:
            # Load from file
            with open(file_path, 'r') as f:
                conversation_data = json.load(f)

            # Deserialize thread
            thread = await agent.agent.deserialize_thread(conversation_data['thread'])

            logger.info(f"Conversation '{name}' loaded successfully")
            return thread

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            raise

    def list_conversations(self) -> list[dict]:
        """List all saved conversations.

        Returns:
            List of conversation metadata
        """
        conversations = []
        for name, meta in self.metadata['conversations'].items():
            conversations.append({
                'name': name,
                'description': meta.get('description'),
                'created_at': meta.get('created_at'),
            })

        # Sort by creation time (newest first)
        conversations.sort(key=lambda x: x['created_at'], reverse=True)
        return conversations

    def delete_conversation(self, name: str) -> bool:
        """Delete a saved conversation.

        Args:
            name: Name of conversation to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.storage_dir / f"{name}.json"

        if file_path.exists():
            file_path.unlink()

            if name in self.metadata['conversations']:
                del self.metadata['conversations'][name]
                self._save_metadata()

            logger.info(f"Conversation '{name}' deleted")
            return True

        return False
```

**Step 2:** Update CLI to add save/load commands

```python
# src/butler/cli.py

from butler.persistence import ThreadPersistence

async def run_chat_mode(quiet: bool = False, verbose: bool = False) -> None:
    """Run interactive chat mode."""
    # ... existing setup ...

    # Create persistence manager
    persistence = ThreadPersistence()

    # Interactive loop
    while True:
        try:
            user_input = await session.prompt_async(prompt_text)

            # ... existing command handling ...

            # Add persistence commands
            if user_input.startswith("/save"):
                parts = user_input.split(maxsplit=1)
                name = parts[1] if len(parts) > 1 else f"conversation_{int(time.time())}"

                await persistence.save_thread(thread, name)
                console.print(f"[green]✓ Conversation saved as '{name}'[/green]")
                continue

            if user_input.startswith("/load"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    console.print("[red]Usage: /load <name>[/red]")
                    continue

                name = parts[1]
                try:
                    thread = await persistence.load_thread(agent, name)
                    message_count = len(thread.messages) if hasattr(thread, 'messages') else 0
                    console.print(f"[green]✓ Conversation '{name}' loaded ({message_count} messages)[/green]")
                except FileNotFoundError:
                    console.print(f"[red]Conversation '{name}' not found[/red]")
                continue

            if user_input.strip() == "/list":
                conversations = persistence.list_conversations()
                if conversations:
                    console.print("\n[bold]Saved Conversations:[/bold]")
                    for conv in conversations:
                        desc = conv.get('description', 'No description')
                        console.print(f"  • {conv['name']}: {desc}")
                else:
                    console.print("[dim]No saved conversations[/dim]")
                console.print()
                continue

            if user_input.startswith("/delete"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    console.print("[red]Usage: /delete <name>[/red]")
                    continue

                name = parts[1]
                if persistence.delete_conversation(name):
                    console.print(f"[green]✓ Conversation '{name}' deleted[/green]")
                else:
                    console.print(f"[red]Conversation '{name}' not found[/red]")
                continue

            # ... existing query execution ...
```

**Step 3:** Update help text

```python
def _show_help() -> None:
    """Show help information."""
    help_text = """
# Butler Agent Help

## Commands

- **exit, quit, q** - Exit Butler
- **help, ?** - Show this help
- **clear** - Clear screen
- **/new** - Start a new conversation
- **/save [name]** - Save current conversation
- **/load <name>** - Load a saved conversation
- **/list** - List saved conversations
- **/delete <name>** - Delete a saved conversation

## Example Usage

```
/save dev-setup
/load dev-setup
/list
```
    """
    console.print(Markdown(help_text))
```

**Benefits:**
- Save and resume conversations
- Conversation library management
- Share conversation contexts
- Better UX for long-running tasks

**Effort:** 4-6 hours

---

## 4. 📚 History: Using Default Only

### Current State

**Status:** ⚠️ Using default in-memory history

We rely on the framework's default `AgentThread` in-memory history storage. This works but has limitations:
- No external storage
- Limited to memory capacity
- No conversation analytics
- Can't implement custom history management (trimming, summarization, etc.)

### The Gap

The framework supports custom `ChatMessageStore` (ai-docs/history.md) for:
- External storage (Redis, files, database)
- Custom history management (summarization, trimming)
- Conversation analytics
- Scalable storage

### Should We Implement This Now?

**Recommendation:** ⏸️ **NOT for Phase 1**

**Reasoning:**
- Default in-memory history works fine for local CLI usage
- Custom storage adds complexity
- Thread persistence (above) handles most use cases
- Save for production/server deployment

**When to implement:**
- If deploying as a web service
- If need conversation analytics
- If memory constraints become an issue
- If implementing summarization/trimming strategies

**Future implementation would look like:**

```python
# Future: src/butler/storage.py

class FileChatMessageStore:
    """File-based chat message storage."""

    async def add_messages(self, messages: Sequence[ChatMessage]) -> None:
        """Append messages to file."""
        pass

    async def list_messages(self) -> list[ChatMessage]:
        """Load messages from file."""
        pass

    async def serialize_state(self) -> dict:
        """Serialize store state."""
        pass

# Use with agent
agent = ChatAgent(
    chat_client=client,
    chat_message_store_factory=lambda: FileChatMessageStore(...)
)
```

---

## 📋 Prioritized Implementation Plan

### Phase 1A: High Priority (Implement Now)

#### 1. Complete Middleware Implementation
**Effort:** 2-3 hours
**Impact:** HIGH - Better observability, performance metrics

**Tasks:**
- [ ] Add agent-level middleware to middleware.py
- [ ] Create `agent_run_logging_middleware`
- [ ] Create `agent_observability_middleware`
- [ ] Update agent.py to use both middleware types
- [ ] Test middleware execution
- [ ] Update tests for middleware

#### 2. Implement Thread Persistence
**Effort:** 4-6 hours
**Impact:** HIGH - Critical for user experience

**Tasks:**
- [ ] Create `src/butler/persistence.py`
- [ ] Implement ThreadPersistence class
- [ ] Add CLI commands: /save, /load, /list, /delete
- [ ] Create conversation storage directory
- [ ] Implement metadata indexing
- [ ] Test serialization/deserialization
- [ ] Update help text
- [ ] Add unit tests for persistence

### Phase 1B: Medium Priority (Next Sprint)

#### 3. Add Memory/Context Providers
**Effort:** 4-6 hours
**Impact:** MEDIUM - Enhanced UX, personalization

**Tasks:**
- [ ] Create `src/butler/memory.py`
- [ ] Implement ClusterMemory with preferences
- [ ] Implement ConversationMetricsMemory
- [ ] Update agent.py to support context providers
- [ ] Add enable_memory parameter
- [ ] Test memory learning and recall
- [ ] Add memory serialization for persistence
- [ ] Add unit tests for memory providers

### Phase 2: Low Priority (Future)

#### 4. Custom Chat History Storage
**Status:** ⏸️ **Defer to future phases**

Only implement when:
- Deploying as web service
- Need conversation analytics
- Memory constraints arise
- Implementing advanced history management

---

## 🎯 Expected Outcomes

### After Phase 1A Implementation

**Middleware:**
- ✅ Full agent execution observability
- ✅ Performance metrics tracked
- ✅ Better error tracking
- ✅ Request/response logging

**Persistence:**
- ✅ Save/load conversations
- ✅ Conversation library management
- ✅ Resume sessions across CLI restarts
- ✅ Better UX for complex tasks

### After Phase 1B Implementation

**Memory:**
- ✅ Personalized cluster suggestions
- ✅ Remember user preferences
- ✅ Better cluster naming suggestions
- ✅ Session metrics and insights

---

## 📊 Current vs. Target State

### Current State (Phase 1 Foundation)
```
Agent Infrastructure:
├── ✅ Agent creation (create_agent pattern)
├── ✅ Multi-turn conversations (thread support)
├── ✅ Dependency injection (testing)
├── ✅ Configuration management
├── ⚠️  Middleware (function only)
├── ❌ Memory (not implemented)
├── ❌ Persistence (not implemented)
└── ⚠️  History (default only)
```

### Target State (After Improvements)
```
Agent Infrastructure:
├── ✅ Agent creation (create_agent pattern)
├── ✅ Multi-turn conversations (thread support)
├── ✅ Dependency injection (testing)
├── ✅ Configuration management
├── ✅ Middleware (agent + function)
├── ✅ Memory (context providers)
├── ✅ Persistence (save/load threads)
└── ✅ History (flexible, can add custom later)
```

---

## 🎓 Key Insights from Documentation

### What Makes a Production-Ready Agent

1. **Complete Middleware Stack**
   - Agent-level for execution lifecycle
   - Function-level for tool calls
   - Both working together

2. **Conversation Persistence**
   - Save interesting conversations
   - Resume complex tasks
   - Better user experience

3. **Memory Capabilities**
   - Learn user preferences
   - Provide context-aware suggestions
   - Personalized experience

4. **Flexible History Management**
   - Default in-memory for simple cases
   - Custom storage for production
   - Can be added later without refactor

### Framework Philosophy

- **Layered Capabilities:** Start simple, add complexity as needed
- **Composable Components:** Memory, persistence, history work independently
- **Optional Features:** Don't over-engineer early
- **Test-Friendly:** All features support dependency injection

---

## 📝 Next Steps

1. **Review this analysis** - Confirm priorities
2. **Implement Phase 1A** - Middleware + Persistence (6-9 hours)
3. **Test thoroughly** - Unit + integration tests
4. **Implement Phase 1B** - Memory (4-6 hours)
5. **Document patterns** - Update README with new capabilities
6. **Share with OSDU** - Document learnings for community

---

## 📚 References

- **Middleware:** `ai-docs/middleware.md`
- **Memory:** `ai-docs/memory.md`
- **Persistence:** `ai-docs/persistence.md`
- **History:** `ai-docs/history.md`
- **Current Implementation:** `src/butler/`

---

**Conclusion:** We have **significant room for improvement** in core agent capabilities. The recommended implementations will transform Butler from a basic foundation into a **production-ready, user-friendly agent** with proper observability, persistence, and personalization. All improvements follow Microsoft Agent Framework best practices and patterns.
