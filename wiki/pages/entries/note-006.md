---
id: note-006
tags: [extensibility_api]
created: 2026-05-10T09:33:04.071999+00:00
source: docs/EXTENSIBILITY_API.md
---

# EXTENSIBILITY_API

# Village Extensibility API Reference

Complete API reference for all extensibility extension points, including abstract base classes, dataclasses, default implementations, and usage examples.

## Table of Contents

1. [ChatProcessor](#chatprocessor) - Pre/post message processing
2. [ToolInvoker](#toolinvoker) - MCP tool invocation customization
3. [ThinkingRefiner](#thinkingrefiner) - Domain-specific query refinement
4. [ChatContext](#chatcontext) - Session state management
5. [TaskHooks](#taskhooks) - Task management hooks
6. [ServerDiscovery](#serverdiscovery) - Dynamic MCP server discovery
7. [LLMProviderAdapter](#llmprovideradapter) - LLM provider configuration
8. [ExtensionRegistry](#extensionregistry) - Extension management

---

## ChatProcessor

Abstract base class for chat message processors. Allows domains to customize pre and post-processing of chat messages without modifying Village's core chat loop.

### Abstract Class

```python
from abc import ABC, abstractmethod

class ChatProcessor(ABC):
    """Base class for chat message processors.

    Allows domains to customize pre and post-processing of chat messages
    without modifying Village's core chat loop.
    """
```

### Methods

#### `pre_process(user_input: str) -> str`

Process user input before LLM invocation.

**Parameters:**
- `user_input` (str): Raw user input from chat

**Returns:**
- str: Processed input to send to LLM

**Raises:**
- None (implementations should handle errors gracefully)

**Usage:**

```python
async def pre_process(self, user_input: str) -> str:
    # Extract and normalize trading pairs
    return normalize_trading_pairs(user_input)
```

#### `post_process(response: str) -> str`

Process LLM response before returning to user.

**Parameters:**
- `response` (str): Raw response from LLM

**Returns:**
- str: Processed response to return to user

**Raises:**
- None (implementations should handle errors gracefully)

**Usage:**

```python
async def post_process(self, response: str) -> str:
    # Format trading-specific output
    return format_trading_response(response)
```

### Dataclasses

#### `ProcessingResult`

Result of message processing.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | str | - | Processed content |
| `metadata` | dict[str, object] \| None | None | Optional metadata dictionary |

**Usage:**

```python
from village.extensibility.processors import ProcessingResult

result = ProcessingResult(
    content="BTC-ETH pair analysis",
    metadata={"pairs": ["BTC", "ETH"], "timestamp": "2026-01-28"}
)
```

### Default Implementation

**Class:** `DefaultChatProcessor`

Provides no-op processing for backward compatibility.

**Behavior:**
- `pre_process()`: Returns input unchanged
- `post_process()`: Returns response unchanged

### Complete Usage Example

```python
from village.extensibility import ChatProcessor, DefaultChatProcessor

class TradingChatProcessor(ChatProcessor):
    """Trading-specific chat processor."""

    async def pre_process(self, user_input: str) -> str:
        # Normalize trading pairs to uppercase
        import re
        # Convert btc to BTC, eth to ETH, etc.
        processed = re.sub(
            r'\b[a-z]{2,4}\b',
            lambda m: m.group(0).upper(),
            user_input
        )
        return processed

    async def post_process(self, response: str) -> str:
        # Add trading disclaimer
        disclaimer = "\n\n⚠️ Trading involves risk. This is not financial advice."
        return response + disclaimer

# Register with registry
from village.extensibility import ExtensionRegistry
registry = ExtensionRegistry()
registry.register_processor(TradingChatProcessor())

# Use in chat loop
processor = registry.get_processor()
processed_input = await processor.pre_process("analyze btc eth")
# Result: "analyze BTC ETH"
```

---

## ToolInvoker

Abstract base class for tool invocation customization. Allows domains to customize how MCP tools are invoked, including caching, filtering, and argument transformation.

### Abstract Class

```python
from abc import ABC, abstractmethod

class ToolInvoker(ABC):
    """Base class for tool invocation customization.

    Allows domains to customize how MCP tools are invoked, including caching,
    filtering, and argument transformation.
    """
```

### Methods

#### `should_invoke(invocation: ToolInvocation) -> bool`

Determine whether to invoke the tool.

**Parameters:**
- `invocation` (ToolInvocation): Tool invocation request

**Returns:**
- bool: True if tool should be invoked, False to skip

**Raises:**
- None

**Usage:**

```python
async def should_invoke(self, invocation: ToolInvocation) -> bool:
    # Skip expensive backtest if recent cache exists
    return not self.has_recent_cache(invocation.tool_name)
```

#### `transform_args(invocation: ToolInvocation) -> dict[str, Any]`

Transform tool arguments before invocation.

**Parameters:**
- `invocation` (ToolInvocation): Tool invocation request

**Returns:**
- dict[str, Any]: Transformed arguments dictionary

**Raises:**
- None

**Usage:**

```python
async def transform_args(self, invocation: ToolInvocation) -> dict[str, Any]:
    # Enrich backtest args with historical context
    return enrich_backtest_args(invocation.args)
```

#### `on_success(invocation: ToolInvocation, result: Any) -> Any`

Handle successful tool invocation. Can cache results, log metrics, etc.

**Parameters:**
- `invocation` (ToolInvocation): Tool invocation request
- `result` (Any): Tool result

**Returns:**
- Any: Potentially transformed result

**Raises:**
- None

**Usage:**

```python
async def on_success(self, invocation: ToolInvocation, result: Any) -> Any:
    # Cache result
    self.cache.put(invocation.tool_name, invocation.args, result)
    return result
```

#### `on_error(invocation: ToolInvocation, error: Exception) -> None`

Handle tool invocation error.

**Parameters:**
- `invocation` (ToolInvocation): Tool invocation request
- `error` (Exception): Exception that occurred

**Returns:**
- None

**Raises:**
- None

**Usage:**

```python
async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
    # Log error with context
    self.logger.error(
        f"Tool {invocation.tool_name} failed: {error}",
        extra={"args": invocation.args}
    )
```

### Dataclasses

#### `ToolInvocation`

Tool invocation request.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tool_name` | str | - | Name of tool to invoke |
| `args` | dict[str, Any] | - | Tool arguments |
| `context` | dict[str, Any] \| None | None | Optional context dictionary |

**Usage:**

```python
from village.extensibility.tool_invokers import ToolInvocation

invocation = ToolInvocation(
    tool_name="backtest_strategy",
    args={
        "strategy_path": "/strategies/btc_momentum",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31"
    },
    context={"session_id": "session-123"}
)
```

#### `ToolResult`

Tool invocation result.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | bool | - | Whether invocation succeeded |
| `result` | Any | - | Result value (if successful) |
| `error` | Optional[str] | None | Error message (if failed) |
| `cached` | bool | False | Whether result was from cache |

**Usage:**

```python
from village.extensibility.tool_invokers import ToolResult

# Successful result
result = ToolResult(
    success=True,
    result={"sharpe_ratio": 1.8, "total_return": 0.45},
    cached=False
)

# Failed result
error_result = ToolResult(
    success=False,
    result=None,
    error="Strategy not found"
)
```

### Default Implementation

**Class:** `DefaultToolInvoker`

Provides no-op tool invocation for backward compatibility.

**Behavior:**
- `should_invoke()`: Always returns True
- `transform_args()`: Returns args unchanged
- `on_success()`: Returns result unchanged
- `on_error()`: Does nothing

### Complete Usage Example

```python
from village.extensibility import ToolInvoker
from village.extensibility.tool_invokers import ToolInvocation, ToolResult

class CachingToolInvoker(ToolInvoker):
    """Tool invoker with result caching."""

    def __init__(self):
        self.cache: dict[tuple, Any] = {}

    def _get_cache_key(self, tool_name: str, args: dict) -> tuple:
        """Create cache key from tool name and args."""
        import json
        return (tool_name, json.dumps(args, sort_keys=True))

    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        # Skip if result is cached
        key = self._get_cache_key(invocation.tool_name, invocation.args)
        return key not in self.cache

    async def transform_args(self, invocation: ToolInvocation) -> dict[str, Any]:
        # Add timestamp to args
        from datetime import datetime
        invocation.args["invoked_at"] = datetime.now().isoformat()
        return invocation.args

    async def on_success(self, invocation: ToolInvocation, result: Any) -> Any:
        # Cache result
        key = self._get_cache_key(invocation.tool_name, invocation.args)
        self.cache[key] = result
        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        # Log error
        print(f"Tool {invocation.tool_name} error: {error}")

# Register with registry
from village.extensibility import ExtensionRegistry
registry = ExtensionRegistry()
registry.register_tool_invoker(CachingToolInvoker())
```

---

## ThinkingRefiner

Abstract base class for domain-specific query refinement. Allows domains to break down vague or complex user queries into structured analysis steps using sequential thinking.

### Abstract Class

```python
from abc import ABC, abstractmethod

class ThinkingRefiner(ABC):
    """Base class for domain-specific query refinement.

    Allows domains to break down vague or complex user queries into
    structured analysis steps using sequential thinking.
    """
```

### Methods

#### `should_refine(user_query: str) -> bool`

Determine if query needs refinement.

**Parameters:**
- `user_query` (str): User's query

**Returns:**
- bool: True if query should be refined, False to use as-is

**Raises:**
- None

**Usage:**

```python
async def should_refine(self, user_query: str) -> bool:
    # Refine vague or ambiguous queries
    vague_keywords = ["better", "best", "good", "bad"]
    return any(kw in user_query.lower() for kw in vague_keywords)
```

#### `refine_query(user_query: str) -> QueryRefinement`

Refine user query into analysis steps.

**Parameters:**
- `user_query` (str): User's query

**Returns:**
- QueryRefinement: QueryRefinement with refined steps and hints

**Raises:**
- None

**Usage:**

```python
async def refine_query(self, user_query: str) -> QueryRefinement:
    # Break "was aggressive better?" into analysis steps:
    # 1. Compare aggressive vs balanced risk profiles
    # 2. Analyze Sharpe ratios and drawdowns
    # 3. Check hit rate to 2x profit goal
    return QueryRefinement(
        original_query=user_query,
        refined_steps=[
            "Compare aggressive vs balanced risk profiles",
            "Analyze Sharpe ratios and maximum drawdowns",
            "Check hit rate to 2x profit goal"
        ],
        context_hints={"asset_class": "crypto"}
    )
```

### Dataclasses

#### `QueryRefinement`

Refined query with analysis steps.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `original_query` | str | - | Original user query |
| `refined_steps` | list[str] | - | List of analysis steps |
| `context_hints` | dict[str, object] \| None | None | Optional context hints |

**Usage:**

```python
from village.extensibility.thinking_refiners import QueryRefinement

refinement = QueryRefinement(
    original_query="was aggressive better?",
    refined_steps=[
        "Compare aggressive vs balanced risk profiles",
        "Analyze Sharpe ratios and maximum drawdowns",
        "Check hit rate to 2x profit goal"
    ],
    context_hints={
        "asset_class": "crypto",
        "timeframe": "2025-01-01 to 2025-12-31"
    }
)
```

### Default Implementation

**Class:** `DefaultThinkingRefiner`

Provides no-op refinement for backward compatibility.

**Behavior:**
- `should_refine()`: Always returns False
- `refine_query()`: Returns query as single step

### Complete Usage Example

```python
from village.extensibility import ThinkingRefiner
from village.extensibility.thinking_refiners import QueryRefinement

class TradingThinkingRefiner(ThinkingRefiner):
    """Trading-specific query refiner."""

    async def should_refine(self, user_query: str) -> bool:
        # Refine queries that are vague or comparative
        vague_patterns = [
            r"was (?:an? )?\w+ better",
            r"which (?:strategy|approach)",
            r"compare \w+ and \w+",
            r"(?:best|worst) (?:strategy|performance)"
        ]
        import re
        return any(re.search(pattern, user_query.lower()) for pattern in vague_patterns)

    async def refine_query(self, user_query: str) -> QueryRefinement:
        """Break down comparative queries into structured analysis."""
        steps = []

        if "better" in user_query.lower() or "compare" in user_query.lower():
            steps.extend([
                "Extract risk profiles from strategies being compared",
                "Compare total returns over the time period",
                "Analyze risk-adjusted metrics (Sharpe ratio, Sortino ratio)",
                "Examine maximum drawdown and recovery time",
                "Check hit rate and profit factor"
            ])
        else:
            steps.append(user_query)

        return QueryRefinement(
            original_query=user_query,
            refined_steps=steps,
            context_hints={
                "domain": "trading",
                "requires_backtest": "compare" in user_query.lower()
            }
        )

# Register with registry
from village.extensibility import ExtensionRegistry
registry = ExtensionRegistry()
registry.register_thinking_refiner(TradingThinkingRefiner())

# Use in chat loop
refiner = registry.get_thinking_refiner()
if await refiner.should_refine("was aggressive better?"):
    refinement = await refiner.refine_query("was aggressive better?")
    # Refinement contains structured analysis steps
```

---

## ChatContext

Abstract base class for session context management. Allows domains to maintain and enrich session state, including loading historical data, enriching with market data, etc.

### Abstract Class

```python
from abc import ABC, abstractmethod

class ChatContext(ABC):
    """Base class for session context management.

    Allows domains to maintain and enrich session state, including
    loading historical data, enriching with market data, etc.
    """
```

### Methods

#### `load_context(session_id: str) -> SessionContext`

Load context for session.

**Parameters:**
- `session_id` (str): Session identifier

**Returns:**
- SessionContext: SessionContext with session data

**Raises:**
- None (implementations should handle errors gracefully)

**Usage:**

```python
async def load_context(self, session_id: str) -> SessionContext:
    # Load recent trading tasks and market data
    return SessionContext(
        session_id=session_id,
        user_data={
            "recent_tasks": [...],
            "market_data": {...},
            "portfolio_value": 100000
        }
    )
```

#### `save_context(context: SessionContext) -> None`

Save context for session.

**Parameters:**
- `context` (SessionContext): SessionContext to save

**Returns:**
- None

**Raises:**
- None (implementations should handle errors gracefully)

**Usage:**

```python
async def save_context(self, context: SessionContext) -> None:
    # Persist context to storage
    self.db.save_session(context.session_id, context.user_data)
```

#### `enrich_context(context: SessionContext) -> SessionContext`

Enrich context with domain-specific data.

**Parameters:**
- `context` (SessionContext): SessionContext to enrich

**Returns:**
- SessionContext: Enriched SessionContext

**Raises:**
- None

**Usage:**

```python
async def enrich_context(self, context: SessionContext) -> SessionContext:
    # Add current market prices
    context.set("current_prices", self.get_market_prices())
    return context
```

### Dataclasses

#### `SessionContext`

Session context data.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | str | - | Session identifier |
| `user_data` | dict[str, Any] | dict() | User data dictionary |
| `metadata` | dict[str, Any] | dict() | Metadata dictionary |

**Methods:**

- `get(key: str, default: Any = None) -> Any`: Get user data value
- `set(key: str, value: Any) -> None`: Set user data value

**Usage:**

```python
from village.extensibility.context import SessionContext

# Create context
context = SessionContext(
    session_id="session-123",
    user_data={
        "recent_tasks": ["task-1", "task-2"],
        "strategy_path": "/strategies/btc_momentum"
    },
    metadata={"created_at": "2026-01-28T10:00:00Z"}
)

# Access data
recent_tasks = context.get("recent_tasks")
strategy_path = context.get("strategy_path", "/default/strategy")

# Update data
context.set("portfolio_value", 100000)
context.set("last_trade", {"symbol": "BTC", "price": 45000})
```

### Default Implementation

**Class:** `DefaultChatContext`

Provides minimal context management for backward compatibility.

**Behavior:**
- `load_context()`: Returns empty SessionContext
- `save_context()`: Does nothing
- `enrich_context()`: Returns context unchanged

### Complete Usage Example

```python
from village.extensibility import ChatContext
from village.extensibility.context import SessionContext
import json
from pathlib import Path

class TradingChatContext(ChatContext):
    """Trading-specific chat context with persistence."""

    def __init__(self, context_dir: Path):
        self.context_dir = context_dir
        self.context_dir.mkdir(parents=True, exist_ok=True)

    def _get_context_path(self, session_id: str) -> Path:
        return self.context_dir / f"{session_id}.json"

    async def load_context(self, session_id: str) -> SessionContext:
        """Load context from file system."""
        context_path = self._get_context_path(session_id)

        if context_path.exists():
            with open(context_path) as f:
                data = json.load(f)
                return SessionContext(
                    session_id=session_id,
                    user_data=data.get("user_data", {}),
                    metadata=data.get("metadata", {})
                )
        else:
            # Return new empty context
            return SessionContext(session_id=session_id)

    async def save_context(self, context: SessionContext) -> None:
        """Save context to file system."""
        context_path = self._get_context_path(context.session_id)

        with open(context_path, "w") as f:
            json.dump({
                "user_data": context.user_data,
                "metadata": context.metadata
            }, f, indent=2)

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Enrich with current market data."""
        # Simulate fetching market data
        context.set("current_prices", {
            "BTC": 45000.0,
            "ETH": 2800.0
        })
        return context

# Register with registry
from village.extensibility import ExtensionRegistry
from pathlib import Path
registry = ExtensionRegistry()
registry.register_chat_context(
    TradingChatContext(context_dir=Path("~/.village/sessions").expanduser())
)

# Use in chat loop
context_mgr = registry.get_chat_context()
context = await context_mgr.load_context("session-123")
context = await context_mgr.enrich_context(context)
await context_mgr.save_context(context)
```

---

## TaskHooks

Abstract base class for task management customization. Allows domains to create and manage tasks with domain-specific metadata, links, and hierarchy.

### Abstract Class

```python
from abc import ABC, abstractmethod

class TaskHooks(ABC):
    """Base class for task management customization.

    Allows domains to create and manage tasks with domain-specific
    metadata, links, and hierarchy.
    """
```

### Methods

#### `should_create_task_hook(context: dict[str, Any]) -> bool`

Determine if task hook should fire.

**Parameters:**
- `context` (dict[str, Any]): Context dictionary with task info

**Returns:**
- bool: True if task hook should fire

**Raises:**
- None

**Usage:**

```python
async def should_create_task_hook(self, context: dict[str, Any]) -> bool:
    # Only fire for backtest tasks
    return context.get("task_type") == "backtest"
```

#### `create_hook_spec(context: dict[str, Any]) -> TaskHookSpec`

Create task hook specification from context.

**Parameters:**
- `context` (dict[str, Any]): Context dictionary with task info

**Returns:**
- TaskHookSpec: TaskHookSpec for task creation

**Raises:**
- None

**Usage:**

```python
async def create_hook_spec(self, context: dict[str, Any]) -> TaskHookSpec:
    return TaskHookSpec(
        title=context["title"],
        description=context["description"],
        issue_type="task",
        priority=1,
        metadata={
            "strategy_path": context["strategy_folder"],
            "risk_style": context["risk_style"],
            "linked_task_id": context["task_id"]
        }
    )
```

#### `on_task_created(created: TaskCreated, context: dict[str, Any]) -> None`

Handle task creation. Can link task to domain objects, update metadata, etc.

**Parameters:**
- `created` (TaskCreated): Created task
- `context` (dict[str, Any]): Original context

**Returns:**
- None

**Raises:**
- None

**Usage:**

```python
async def on_task_created(self, created: TaskCreated, context: dict[str, Any]) -> None:
    # Update task with linked ID
    task = self.get_task(context["task_id"])
    task.linked_id = created.task_id
    task.save()
```

#### `on_task_updated(task_id: str, updates: dict[str, Any]) -> None`

Handle task update.

**Parameters:**
- `task_id` (str): ID of updated task
- `updates` (dict[str, Any]): Dictionary of updates

**Returns:**
- None

**Raises:**
- None

**Usage:**

```python
async def on_task_updated(self, task_id: str, updates: dict[str, Any]) -> None:
    # Sync updates to linked task
    if "status" in updates:
        task = self.get_task_by_id(task_id)
        task.status = updates["status"]
        task.save()
```

### Dataclasses

#### `TaskHookSpec`

Task hook specification.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | str | - | Task title |
| `description` | str | - | Task description |
| `issue_type` | str | - | Issue type: bug, feature, task, epic, chore |
| `priority` | int | - | Priority: 0-4 (0=lowest, 4=highest) |
| `tags` | list[str] \| None | [] | Optional tags |
| `parent_id` | Optional[str] | None | Optional parent task ID |
| `deps` | list[str] \| None | [] | Optional dependency IDs |
| `metadata` | dict[str, Any] \| None | {} | Optional metadata |

**Usage:**

```python
from village.extensibility.task_hooks import TaskHookSpec

spec = TaskHookSpec(
    title="Backtest BTC momentum strategy",
    description="Run backtest on BTC momentum strategy for 2025",
    issue_type="task",
    priority=2,
    tags=["backtest", "btc", "momentum"],
    parent_id="parent-123",
    deps=["dep-1", "dep-2"],
    metadata={
        "strategy_path": "/strategies/btc_momentum",
        "risk_style": "aggressive",
        "timeframe": "2025-01-01 to 2025-12-31"
    }
)
```

#### `TaskCreated`

Result of task creation.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | str | - | Created task ID |
| `parent_id` | Optional[str] | None | Parent task ID (if any) |
| `created_at` | str | - | Creation timestamp (ISO 8601) |
| `metadata` | dict[str, Any] \| None | {} | Optional metadata |

**Usage:**

```python
from village.extensibility.task_hooks import TaskCreated

task = TaskCreated(
    task_id="task-abc123",
    parent_id="parent-123",
    created_at="2026-01-28T10:30:00Z",
    metadata={"source": "village"}
)
```

### Default Implementation

**Class:** `DefaultTaskHooks`

Provides no-op task hooks for backward compatibility.

**Behavior:**
- `should_create_task_hook()`: Always returns False
- `create_hook_spec()`: Returns minimal spec
- `on_task_created()`: Does nothing
- `on_task_updated()`: Does nothing

### Complete Usage Example

```python
from village.extensibility import TaskHooks
from village.extensibility.task_hooks import TaskHookSpec, TaskCreated

class TradingTaskHooks(TaskHooks):
    """Trading-specific task hooks."""

    async def should_create_task_hook(self, context: dict[str, Any]) -> bool:
        # Create hooks for backtest and optimization tasks
        task_types = ["backtest", "optimization", "analysis"]
        return context.get("task_type") in task_types

    async def create_hook_spec(self, context: dict[str, Any]) -> TaskHookSpec:
        """Create hook spec with trading-specific metadata."""
        task_type = context["task_type"]

        # Determine priority based on task type
        priority_map = {"backtest": 2, "optimization": 3, "analysis": 1}
        priority = priority_map.get(task_type, 2)

        # Create tags
        tags = [task_type, context.get("asset_class", "crypto").lower()]

        return TaskHookSpec(
            title=f"{task_type.capitalize()} {context.get('strategy_name', 'strategy')}",
            description=context.get("description", ""),
            issue_type="task",
            priority=priority,
            tags=tags,
            metadata={
                "strategy_path": context.get("strategy_path"),
                "risk_style": context.get("risk_style"),
                "timeframe": context.get("timeframe"),
                "linked_task_id": context.get("task_id"),
                "asset_class": context.get("asset_class", "crypto")
            }
        )

    async def on_task_created(self, created: TaskCreated, context: dict[str, Any]) -> None:
        """Link task to trading task."""
        # Update task with linked ID
        task_id = context.get("task_id")
        if task_id:
            self.update_task_linked_id(task_id, created.task_id)
            print(f"Linked task {task_id} to {created.task_id}")

    async def on_task_updated(self, task_id: str, updates: dict[str, Any]) -> None:
        """Sync task updates to trading task."""
        task = self.get_task_by_id(task_id)
        if task:
            if "status" in updates:
                task.status = updates["status"]
            if "metadata" in updates:
                task.metadata.update(updates["metadata"])
            task.save()

# Register with registry
from village.extensibility import ExtensionRegistry
registry = ExtensionRegistry()
registry.register_task_hooks(TradingTaskHooks())

# Use when creating tasks
hooks = registry.get_task_hooks()
context = {
    "task_type": "backtest",
    "strategy_name": "BTC Momentum",
    "strategy_path": "/strategies/btc_momentum",
    "risk_style": "aggressive",
    "timeframe": "2025-01-01 to 2025-12-31",
    "asset_class": "crypto",
    "task_id": "task-123"
}

if await hooks.should_create_task_hook(context):
    spec = await hooks.create_hook_spec(context)
    # Create task in native task store
    task_id = self.tasks_client.create(spec)
    task = TaskCreated(
        task_id=task_id,
        parent_id=None,
        created_at="2026-01-28T10:30:00Z"
    )
    await hooks.on_task_created(task, context)
```

---

## ServerDiscovery

Abstract base class for dynamic MCP server discovery. Allows domains to customize which MCP servers are loaded based on availability, configuration, and runtime conditions.

### Abstract Class

```python
from abc import ABC, abstractmethod

class ServerDiscovery(ABC):
    """Base class for dynamic MCP server discovery.

    Allows domains to customize which MCP servers are loaded based on
    availability, configuration, and runtime conditions.
    """
```

### Methods

#### `discover_servers() -> list[MCPServer]`

Discover available MCP servers.

**Returns:**
- list[MCPServer]: List of MCPServer specifications to load

**Raises:**
- None

**Usage:**

```python
async def discover_servers(self) -> list[MCPServer]:
    # Load Jesse backtesting server only if strategy is defined
    servers = [
        MCPServer(
            name="perplexity",
            type="stdio",
            command="perplexity-mcp"
        )
    ]
    if self.strategy_path.exists():
        servers.append(
            MCPServer(
                name="jesse",
                type="stdio",
                command="jesse-mcp",
                args=[str(self.strategy_path)]
            )
        )
    return servers
```

#### `filter_servers(servers: list[MCPServer]) -> list[MCPServer]`

Filter discovered servers. Can be used to disable certain servers based on conditions.

**Parameters:**
- `servers` (list[MCPServer]): List of discovered servers

**Returns:**
- list[MCPServer]: Filtered list of servers to load

**Raises:**
- None

**Usage:**

```python
async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
    # Disable expensive servers during tests
    if self.is_test_mode:
        return [s for s in servers if s.name not in ["jesse", "backtest"]]
    return servers
```

#### `should_load_server(server: MCPServer) -> bool`

Determine if server should be loaded.

**Parameters:**
- `server` (MCPServer): Server to check

**Returns:**
- bool: True if server should be loaded

**Raises:**
- None

**Usage:**

```python
async def should_load_server(self, server: MCPServer) -> bool:
    # Only load enabled servers
    return server.enabled and self.check_dependencies(server.name)
```

### Dataclasses

#### `MCPServer`

MCP server specification.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str | - | Server name (unique identifier) |
| `type` | str | - | Server type: stdio, sse, etc. |
| `command` | str | - | Command to start server |
| `args` | list[str] \| None | [] | Optional command arguments |
| `env` | dict[str, str] \| None | {} | Optional environment variables |
| `enabled` | bool | True | Whether server is enabled |

**Usage:**

```python
from village.extensibility.server_discovery import MCPServer

server = MCPServer(
    name="perplexity",
    type="stdio",
    command="perplexity-mcp",
    args=["--model", "sonnet"],
    env={"API_KEY": "sk-xxx"},
    enabled=True
)

server2 = MCPServer(
    name="jesse",
    type="stdio",
    command="jesse-mcp",
    args=["/strategies/btc_momentum"],
    enabled=True
)
```

### Default Implementation

**Class:** `DefaultServerDiscovery`

Provides no server discovery for backward compatibility.

**Behavior:**
- `discover_servers()`: Returns empty list
- `filter_servers()`: Returns servers unchanged
- `should_load_server()`: Returns server.enabled

### Complete Usage Example

```python
from village.extensibility import ServerDiscovery
from village.extensibility.server_discovery import MCPServer
from pathlib import Path

class TradingServerDiscovery(ServerDiscovery):
    """Trading-specific MCP server discovery."""

    def __init__(self, strategy_path: Path, test_mode: bool = False):
        self.strategy_path = strategy_path
        self.test_mode = test_mode

    async def discover_servers(self) -> list[MCPServer]:
        """Discover trading-specific MCP servers."""
        servers = []

        # Always load Perplexity for web search
        servers.append(MCPServer(
            name="perplexity",
            type="stdio",
            command="perplexity-mcp",
            enabled=not self.test_mode  # Disable in tests
        ))

        # Load Jesse backtesting if strategy exists
        if self.strategy_path.exists():
            servers.append(MCPServer(
                name="jesse",
                type="stdio",
                command="jesse-mcp",
                args=[str(self.strategy_path)],
                enabled=not self.test_mode  # Disable in tests
            ))

        # Load crypto-specific tools
        servers.append(MCPServer(
            name="crypto-prices",
            type="stdio",
            command="crypto-mcp",
            enabled=True
        ))

        return servers

    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        """Filter servers based on runtime conditions."""
        # In test mode, only keep simple servers
        if self.test_mode:
            return [s for s in servers if s.name == "crypto-prices"]

        # Remove disabled servers
        return [s for s in servers if s.enabled]

    async def should_load_server(self, server: MCPServer) -> bool:
        """Check if server should be loaded."""
        # Check if required dependencies are available
        if server.name == "jesse":
            return self.strategy_path.exists()

        # Check if API key is configured
        if server.name == "perplexity":
            import os
            return os.getenv("PERPLEXITY_API_KEY") is not None

        return server.enabled

# Register with registry
from village.extensibility import ExtensionRegistry
from pathlib import Path
registry = ExtensionRegistry()
registry.register_server_discovery(
    TradingServerDiscovery(
        strategy_path=Path("~/trading/strategies/btc_momentum").expanduser()
    )
)

# Use to discover servers
discovery = registry.get_server_discovery()
servers = await discovery.discover_servers()
servers = await discovery.filter_servers(servers)

for server in servers:
    if await discovery.should_load_server(server):
        print(f"Loading server: {server.name}")
```

---

## LLMProviderAdapter

Abstract base class for LLM provider customization. Allows domains to customize LLM provider selection, model routing, and parameter tuning per domain requirements.

### Abstract Class

```python
from abc import ABC, abstractmethod

class LLMProviderAdapter(ABC):
    """Base class for LLM provider customization.

    Allows domains to customize LLM provider selection, model routing,
    and parameter tuning per domain requirements.
    """
```

### Methods

#### `adapt_config(base_config: LLMProviderConfig) -> LLMProviderConfig`

Adapt LLM provider configuration.

**Parameters:**
- `base_config` (LLMProviderConfig): Base configuration from Village

**Returns:**
- LLMProviderConfig: Adapted configuration

**Raises:**
- None

**Usage:**

```python
async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
    # Use specialized model for trading analysis
    if self.task_type == "backtest_analysis":
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-sonnet",  # Faster model for backtests
            api_key_env="ANTHROPIC_API_KEY",
            timeout=180,
            max_tokens=2048,
            temperature=0.5  # Lower temp for consistency
        )
    return config
```

#### `should_retry(error: Exception) -> bool`

Determine if failed LLM call should be retried.

**Parameters:**
- `error` (Exception): Exception from LLM call

**Returns:**
- bool: True if call should be retried

**Raises:**
- None

**Usage:**

```python
async def should_retry(self, error: Exception) -> bool:
    # Retry on rate limits
    return "rate_limit" in str(error).lower()
```

#### `get_retry_delay(attempt: int) -> float`

Get delay for retry attempt.

**Parameters:**
- `attempt` (int): Retry attempt number (1-based)

**Returns:**
- float: Delay in seconds

**Raises:**
- None

**Usage:**

```python
async def get_retry_delay(self, attempt: int) -> float:
    # Exponential backoff: 2^attempt seconds
    return 2 ** attempt
```

### Dataclasses

#### `LLMProviderConfig`

LLM provider configuration.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | str | - | Provider name: anthropic, openai, etc. |
| `model` | str | - | Model identifier |
| `api_key_env` | str | - | Environment variable for API key |
| `timeout` | int | - | Request timeout in seconds |
| `max_tokens` | int | - | Maximum tokens in response |
| `temperature` | float | 0.7 | Sampling temperature |
| `metadata` | dict[str, Any] \| None | {} | Optional metadata |

**Usage:**

```python
from village.extensibility.llm_adapters import LLMProviderConfig

config = LLMProviderConfig(
    provider="anthropic",
    model="claude-3-sonnet",
    api_key_env="ANTHROPIC_API_KEY",
    timeout=180,
    max_tokens=4096,
    temperature=0.5,
    metadata={"use_case": "trading_analysis"}
)
```

### Default Implementation

**Class:** `DefaultLLMProviderAdapter`

Provides sensible default LLM configuration.

**Behavior:**
- `adapt_config()`: Returns config unchanged
- `should_retry()`: Retries on timeout, connection, rate_limit, temporarily
- `get_retry_delay()`: Exponential backoff with jitter (2^attempt + random(0,1))

### Complete Usage Example

```python
from village.extensibility import LLMProviderAdapter
from village.extensibility.llm_adapters import LLMProviderConfig

class TradingLLMAdapter(LLMProviderAdapter):
    """Trading-specific LLM provider adapter."""

    def __init__(self, task_type: str = "general"):
        self.task_type = task_type

    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        """Adapt config based on task type."""

        # Use faster model for backtest analysis
        if self.task_type == "backtest_analysis":
            return LLMProviderConfig(
                provider="anthropic",
                model="claude-3-sonnet",  # Faster model
                api_key_env="ANTHROPIC_API_KEY",
                timeout=180,
                max_tokens=2048,
                temperature=0.5,  # Lower temp for consistency
                metadata={"task": "backtest_analysis"}
            )

        # Use smartest model for complex queries
        if self.task_type == "complex_analysis":
            return LLMProviderConfig(
                provider="anthropic",
                model="claude-3-opus",
                api_key_env="ANTHROPIC_API_KEY",
                timeout=300,
                max_tokens=4096,
                temperature=0.7,
                metadata={"task": "complex_analysis"}
            )

        # Default config
        return base_config

    async def should_retry(self, error: Exception) -> bool:
        """Retry on specific error types."""
        error_str = str(error).lower()

        # Always retry rate limits
        if "rate_limit" in error_str:
            return True

        # Retry connection errors
        if any(kw in error_str for kw in ["connection", "timeout"]):
            return True

        # Retry temporary errors
        if "temporarily" in error_str:
            return True

        # Don't retry on other errors (invalid params, auth, etc.)
        return False

    async def get_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        import time
        import random

        # Exponential backoff: 2^attempt seconds
        base_delay = 2 ** attempt

        # Add jitter to avoid thundering herd
        jitter = random.uniform(0, 1)

        return base_delay + jitter

# Register with registry
from village.extensibility import ExtensionRegistry
registry = ExtensionRegistry()

# Create adapter for different task types
analysis_adapter = TradingLLMAdapter(task_type="backtest_analysis")
registry.register_llm_adapter(analysis_adapter)

# Use adapter to get config
adapter = registry.get_llm_adapter()
base_config = LLMProviderConfig(
    provider="anthropic",
    model="claude-3-sonnet",
    api_key_env="ANTHROPIC_API_KEY",
    timeout=180,
    max_tokens=4096
)

config = await adapter.adapt_config(base_config)
# Config is optimized for backtest analysis
```

---

## ExtensionRegistry

Registry for managing extension implementations. Provides single point for registering and retrieving extension implementations per domain. Uses sensible defaults if no domain-specific implementation provided.

### Class

```python
class ExtensionRegistry:
    """Registry for managing extension implementations.

    Provides single point for registering and retrieving extension implementations
    per domain. Uses sensible defaults if no domain-specific implementation provided.
    """
```

### Initialization

#### `__init__() -> None`

Initialize registry with default implementations.

**Parameters:**
- None

**Returns:**
- None

**Usage:**

```python
from village.extensibility import ExtensionRegistry

registry = ExtensionRegistry()
# All extensions initialized with defaults
```

### Register Methods

#### `register_processor(processor: ChatProcessor) -> None`

Register chat processor.

**Parameters:**
- `processor` (ChatProcessor): ChatProcessor implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.processors import ChatProcessor

class MyProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        return user_input.upper()

registry.register_processor(MyProcessor())
```

#### `register_tool_invoker(invoker: ToolInvoker) -> None`

Register tool invoker.

**Parameters:**
- `invoker` (ToolInvoker): ToolInvoker implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.tool_invokers import ToolInvoker

class MyInvoker(ToolInvoker):
    async def should_invoke(self, invocation) -> bool:
        return True

registry.register_tool_invoker(MyInvoker())
```

#### `register_thinking_refiner(refiner: ThinkingRefiner) -> None`

Register thinking refiner.

**Parameters:**
- `refiner` (ThinkingRefiner): ThinkingRefiner implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.thinking_refiners import ThinkingRefiner

class MyRefiner(ThinkingRefiner):
    async def should_refine(self, user_query: str) -> bool:
        return False

registry.register_thinking_refiner(MyRefiner())
```

#### `register_chat_context(context: ChatContext) -> None`

Register chat context.

**Parameters:**
- `context` (ChatContext): ChatContext implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.context import ChatContext

class MyContext(ChatContext):
    async def load_context(self, session_id: str):
        return SessionContext(session_id=session_id)

registry.register_chat_context(MyContext())
```

#### `register_task_hooks(hooks: TaskHooks) -> None`

Register task hooks.

**Parameters:**
- `hooks` (TaskHooks): TaskHooks implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.task_hooks import TaskHooks

class MyHooks(TaskHooks):
    async def should_create_task_hook(self, context: dict) -> bool:
        return False

registry.register_task_hooks(MyHooks())
```

#### `register_server_discovery(discovery: ServerDiscovery) -> None`

Register server discovery.

**Parameters:**
- `discovery` (ServerDiscovery): ServerDiscovery implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.server_discovery import ServerDiscovery

class MyDiscovery(ServerDiscovery):
    async def discover_servers(self):
        return []

registry.register_server_discovery(MyDiscovery())
```

#### `register_llm_adapter(adapter: LLMProviderAdapter) -> None`

Register LLM provider adapter.

**Parameters:**
- `adapter` (LLMProviderAdapter): LLMProviderAdapter implementation

**Returns:**
- None

**Usage:**

```python
from village.extensibility.llm_adapters import LLMProviderAdapter

class MyAdapter(LLMProviderAdapter):
    async def adapt_config(self, base_config):
        return base_config

registry.register_llm_adapter(MyAdapter())
```

### Getter Methods

#### `get_processor() -> ChatProcessor`

Get registered processor.

**Returns:**
- ChatProcessor: Registered ChatProcessor implementation

**Usage:**

```python
processor = registry.get_processor()
processed = await processor.pre_process("hello world")
```

#### `get_tool_invoker() -> ToolInvoker`

Get registered tool invoker.

**Returns:**
- ToolInvoker: Registered ToolInvoker implementation

**Usage:**

```python
invoker = registry.get_tool_invoker()
should_invoke = await invoker.should_invoke(invocation)
```

#### `get_thinking_refiner() -> ThinkingRefiner`

Get registered thinking refiner.

**Returns:**
- ThinkingRefiner: Registered ThinkingRefiner implementation

**Usage:**

```python
refiner = registry.get_thinking_refiner()
refinement = await refiner.refine_query("was it better?")
```

#### `get_chat_context() -> ChatContext`

Get registered chat context.

**Returns:**
- ChatContext: Registered ChatContext implementation

**Usage:**

```python
context_mgr = registry.get_chat_context()
context = await context_mgr.load_context("session-123")
```

#### `get_task_hooks() -> TaskHooks`

Get registered task hooks.

**Returns:**
- TaskHooks: Registered TaskHooks implementation

**Usage:**

```python
hooks = registry.get_task_hooks()
if await hooks.should_create_task_hook(context):
    spec = await hooks.create_hook_spec(context)
```

#### `get_server_discovery() -> ServerDiscovery`

Get registered server discovery.

**Returns:**
- ServerDiscovery: Registered ServerDiscovery implementation

**Usage:**

```python
discovery = registry.get_server_discovery()
servers = await discovery.discover_servers()
```

#### `get_llm_adapter() -> LLMProviderAdapter`

Get registered LLM adapter.

**Returns:**
- LLMProviderAdapter: Registered LLMProviderAdapter implementation

**Usage:**

```python
adapter = registry.get_llm_adapter()
config = await adapter.adapt_config(base_config)
```

#### `get_all_names() -> dict[str, str]`

Get names of all registered implementations.

**Returns:**
- dict[str, str]: Dictionary mapping extension type to implementation class name

**Usage:**

```python
names = registry.get_all_names()
# Returns: {
#     "processor": "TradingChatProcessor",
#     "tool_invoker": "CachingToolInvoker",
#     ...
# }
```

#### `reset_to_defaults() -> None`

Reset all extensions to default implementations.

**Returns:**
- None

**Usage:**

```python
registry.register_processor(MyProcessor())
names = registry.get_all_names()
# {"processor": "MyProcessor", ...}

registry.reset_to_defaults()
names = registry.get_all_names()
# {"processor": "DefaultChatProcessor", ...}
```

### Complete Usage Example

```python
from village.extensibility import (
    ExtensionRegistry,
    ChatProcessor,
    ToolInvoker,
    ThinkingRefiner,
    ChatContext,
    TaskHooks,
    ServerDiscovery,
    LLMProviderAdapter
)

# Create custom extensions
class TradingChatProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        return user_input.upper()

    async def post_process(self, response: str) -> str:
        return response + " [TRADING_MODE]"

class CachingToolInvoker(ToolInvoker):
    def __init__(self):
        self.cache = {}

    async def should_invoke(self, invocation) -> bool:
        key = (invocation.tool_name, str(invocation.args))
        return key not in self.cache

    async def transform_args(self, invocation) -> dict:
        return invocation.args

    async def on_success(self, invocation, result) -> Any:
        key = (invocation.tool_name, str(invocation.args))
        self.cache[key] = result
        return result

    async def on_error(self, invocation, error) -> None:
        pass

# Initialize registry and register extensions
registry = ExtensionRegistry()
registry.register_processor(TradingChatProcessor())
registry.register_tool_invoker(CachingToolInvoker())

# Use extensions in application
processor = registry.get_processor()
invoker = registry.get_tool_invoker()

# Get all registered names
names = registry.get_all_names()
print(f"Registered extensions: {names}")
# Output: Registered extensions: {
#     'processor': 'TradingChatProcessor',
#     'tool_invoker': 'CachingToolInvoker',
#     'thinking_refiner': 'DefaultThinkingRefiner',
#     'chat_context': 'DefaultChatContext',
#     'task_hooks': 'DefaultTaskHooks',
#     'server_discovery': 'DefaultServerDiscovery',
#     'llm_adapter': 'DefaultLLMProviderAdapter'
# }

# Reset to defaults if needed
registry.reset_to_defaults()
names = registry.get_all_names()
print(f"After reset: {names}")
# All extensions now return to Default* implementations
```

---

## Quick Reference Tables

### Extension Points Summary

| Extension | Purpose | Key Methods | Default Implementation |
|-----------|---------|-------------|----------------------|
| ChatProcessor | Pre/post message processing | pre_process(), post_process() | DefaultChatProcessor |
| ToolInvoker | Tool invocation hooks | should_invoke(), transform_args(), on_success(), on_error() | DefaultToolInvoker |
| ThinkingRefiner | Query refinement | should_refine(), refine_query() | DefaultThinkingRefiner |
| ChatContext | Session state management | load_context(), save_context(), enrich_context() | DefaultChatContext |
| TaskHooks | Task management hooks | should_create_task_hook(), create_hook_spec(), on_task_created(), on_task_updated() | DefaultTaskHooks |
| ServerDiscovery | MCP server discovery | discover_servers(), filter_servers(), should_load_server() | DefaultServerDiscovery |
| LLMProviderAdapter | LLM configuration | adapt_config(), should_retry(), get_retry_delay() | DefaultLLMProviderAdapter |

### Dataclasses Quick Reference

| Dataclass | Module | Purpose |
|-----------|--------|---------|
| ProcessingResult | processors | Message processing result |
| ToolInvocation | tool_invokers | Tool invocation request |
| ToolResult | tool_invokers | Tool invocation result |
| QueryRefinement | thinking_refiners | Refined query with steps |
| SessionContext | context | Session context data |
| TaskHookSpec | task_hooks | Task hook specification |
| TaskCreated | task_hooks | Task creation result |
| MCPServer | server_discovery | MCP server specification |
| LLMProviderConfig | llm_adapters | LLM provider configuration |

---

## Import Guide

```python
# Core imports
from village.extensibility import ExtensionRegistry

# Abstract base classes
from village.extensibility.processors import ChatProcessor
from village.extensibility.tool_invokers import ToolInvoker
from village.extensibility.thinking_refiners import ThinkingRefiner
from village.extensibility.context import ChatContext
from village.extensibility.task_hooks import TaskHooks
from village.extensibility.server_discovery import ServerDiscovery
from village.extensibility.llm_adapters import LLMProviderAdapter

# Default implementations
from village.extensibility.processors import DefaultChatProcessor
from village.extensibility.tool_invokers import DefaultToolInvoker
from village.extensibility.thinking_refiners import DefaultThinkingRefiner
from village.extensibility.context import DefaultChatContext
from village.extensibility.task_hooks import DefaultTaskHooks
from village.extensibility.server_discovery import DefaultServerDiscovery
from village.extensibility.llm_adapters import DefaultLLMProviderAdapter

# Dataclasses
from village.extensibility.processors import ProcessingResult
from village.extensibility.tool_invokers import ToolInvocation, ToolResult
from village.extensibility.thinking_refiners import QueryRefinement
from village.extensibility.context import SessionContext
from village.extensibility.task_hooks import TaskHookSpec, TaskCreated
from village.extensibility.server_discovery import MCPServer
from village.extensibility.llm_adapters import LLMProviderConfig
```

