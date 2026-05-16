---
id: note-005
tags: [extensibility_guide]
created: 2026-05-10T09:33:02.668747+00:00
source: docs/EXTENSIBILITY_GUIDE.md
---

# EXTENSIBILITY_GUIDE

# Village Extensibility Guide

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Extension Points Reference](#extension-points-reference)
4. [Step-by-Step Tutorials](#step-by-step-tutorials)
5. [Configuration](#configuration)
6. [Best Practices](#best-practices)
7. [Examples](#examples)
8. [Migration Guide](#migration-guide)

---

## 1. Overview

### What is the Extensibility Framework?

The Village extensibility framework allows you to customize Village's chat loop and behavior for domain-specific use cases without modifying the core Village code. Instead of forking Village and maintaining your own version, you implement **extension points** — hook classes that Village calls at specific points during execution.

The framework consists of **7 extension points**, each responsible for a specific aspect of Village's behavior:

1. **ChatProcessor** — Pre/post-process chat messages
2. **ToolInvoker** — Customize MCP tool invocation
3. **ThinkingRefiner** — Domain-specific query refinement
4. **ChatContext** — Session state management
5. **TaskHooks** — Custom task creation/update hooks
6. **ServerDiscovery** — Dynamic MCP server discovery
7. **LLMProviderAdapter** — LLM provider customization

### When to Use Extensions vs Fork Village

**Use extensions when:**
- You need domain-specific behavior (trading, research, planning, etc.)
- You want to customize message processing, tool invocation, or state management
- You want to integrate with domain-specific services (backtesting engines, research databases)
- You want to maintain compatibility with Village updates

**Fork Village when:**
- You need to change Village's core architecture or execution model
- You need to remove core features or fundamentally change how Village works
- You have requirements that cannot be met through the 7 extension points

### Benefits of Extension Points

- **No merge conflicts** — Your extensions live in your own codebase
- **Easy upgrades** — Village updates won't overwrite your customizations
- **Loose coupling** — Extensions interact via well-defined contracts
- **Composability** — Mix and match multiple extensions
- **Testability** — Each extension can be tested independently
- **Maintainability** — Clear separation between Village core and domain logic

---

## 2. Quick Start

This 5-minute tutorial shows you how to create a simple `ChatProcessor` extension.

### Step 1: Create Your Extension

Create a new Python file, e.g., `my_extensions.py`:

```python
"""Custom Village extensions."""

from village.extensibility.processors import ChatProcessor


class UppercaseChatProcessor(ChatProcessor):
    """Example processor that converts input to uppercase."""

    async def pre_process(self, user_input: str) -> str:
        """Convert user input to uppercase before LLM."""
        return user_input.upper()

    async def post_process(self, response: str) -> str:
        """Leave response unchanged."""
        return response
```

### Step 2: Register Your Extension

Create a `bootstrap.py` file to register your extensions:

```python
"""Bootstrap custom extensions."""

from village.extensibility import ExtensionRegistry
from my_extensions import UppercaseChatProcessor


def bootstrap_custom_extensions() -> ExtensionRegistry:
    """Initialize and register custom extensions."""
    registry = ExtensionRegistry()

    # Register your custom processor
    registry.register_processor(UppercaseChatProcessor())

    return registry


# Export for use in your application
__all__ = ["bootstrap_custom_extensions"]
```

### Step 3: Test Locally

Create a test script `test_extension.py`:

```python
"""Test custom extension."""

import asyncio


async def main():
    from bootstrap import bootstrap_custom_extensions

    # Initialize registry
    registry = bootstrap_custom_extensions()

    # Get processor and test it
    processor = registry.get_processor()
    result = await processor.pre_process("hello world")

    print(f"Input: hello world")
    print(f"Output: {result}")
    print(f"Processor: {registry.get_all_names()}")


if __name__ == "__main__":
    asyncio.run(main())
```

Run the test:

```bash
python test_extension.py
```

Output:
```
Input: hello world
Output: HELLO WORLD
Processor: {'processor': 'UppercaseChatProcessor', ...}
```

### Step 4: Load from Config

Create a Village config file `.village/config`:

```ini
[extensions]
enabled = true
processor_module = my_extensions.UppercaseChatProcessor
```

Or use environment variables:

```bash
export VILLAGE_EXTENSIONS_ENABLED=true
export VILLAGE_EXTENSION_PROCESSOR=my_extensions.UppercaseChatProcessor
village chat
```

That's it! Village will now load your custom extension automatically.

---

## 3. Extension Points Reference

### Decision Matrix

Use this matrix to decide which extension point to implement:

| Requirement | Extension Point |
|-------------|-----------------|
| Modify user input before LLM, format LLM output | **ChatProcessor** |
| Cache tool results, add audit logging, transform arguments | **ToolInvoker** |
| Break down complex queries, add domain-specific analysis steps | **ThinkingRefiner** |
| Persist session state, load historical data, enrich with context | **ChatContext** |
| Create tasks with custom metadata, integrate with domain workflows | **TaskHooks** |
| Dynamically discover/load MCP servers based on availability | **ServerDiscovery** |
| Customize LLM models, routing, retry logic, timeouts | **LLMProviderAdapter** |

### Extension Point Details

#### 1. ChatProcessor

**Purpose**: Pre-process user input before LLM, post-process LLM response before user.

**Use cases:**
- Input validation and normalization
- Extract and enrich with domain-specific entities (trading pairs, research topics)
- Format output with domain-specific styling (Rich panels, markdown, citations)
- Add metadata or annotations to responses

**When to implement:**
- You need to transform user input or LLM output
- You need to add formatting, validation, or entity extraction

**Signature:**
```python
from village.extensibility.processors import ChatProcessor

class MyProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        # Transform input
        return transformed_input

    async def post_process(self, response: str) -> str:
        # Transform output
        return transformed_response
```

---

#### 2. ToolInvoker

**Purpose**: Customize how MCP tools are invoked, with support for caching, filtering, and argument transformation.

**Use cases:**
- Cache expensive tool calls (backtest results, API queries)
- Add audit logging for tool usage
- Inject default arguments based on context
- Skip tools based on conditions (rate limits, recent calls)

**When to implement:**
- You need to cache tool results
- You need to log or track tool usage
- You need to conditionally invoke tools

**Signature:**
```python
from village.extensibility.tool_invokers import (
    ToolInvoker,
    ToolInvocation,
    ToolResult,
)

class MyToolInvoker(ToolInvoker):
    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        # Return False to skip tool invocation
        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict:
        # Modify tool arguments
        return modified_args

    async def on_success(self, invocation: ToolInvocation, result) -> Any:
        # Cache result, log metrics
        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        # Handle errors
        pass
```

---

#### 3. ThinkingRefiner

**Purpose**: Break down vague or complex user queries into structured analysis steps using sequential thinking.

**Use cases:**
- Decompose "was aggressive better?" into specific analysis steps
- Add domain-specific analysis methodology
- Route queries to appropriate data sources
- Provide structured analysis plans

**When to implement:**
- Users ask vague questions that need decomposition
- Your domain has specific analysis methodologies
- You need to guide the AI through structured reasoning

**Signature:**
```python
from village.extensibility.thinking_refiners import (
    ThinkingRefiner,
    QueryRefinement,
)

class MyRefiner(ThinkingRefiner):
    async def should_refine(self, user_query: str) -> bool:
        # Return True if query needs refinement
        return True

    async def refine_query(self, user_query: str) -> QueryRefinement:
        return QueryRefinement(
            original_query=user_query,
            refined_steps=["Step 1", "Step 2", "Step 3"],
            context_hints={"required_data_sources": ["api_1", "api_2"]}
        )
```

---

#### 4. ChatContext

**Purpose**: Manage session state and enrich context with domain-specific data.

**Use cases:**
- Load/save session history
- Enrich context with market data, user preferences, project state
- Maintain conversation state across messages
- Load historical data for context

**When to implement:**
- You need to persist session state
- You need to enrich context with external data
- You need to maintain conversation history

**Signature:**
```python
from village.extensibility.context import (
    ChatContext,
    SessionContext,
)

class MyContext(ChatContext):
    async def load_context(self, session_id: str) -> SessionContext:
        # Load session from database, file, etc.
        return SessionContext(session_id=session_id, user_data={...})

    async def save_context(self, context: SessionContext) -> None:
        # Save session to database, file, etc.
        pass

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        # Add domain-specific data
        context.metadata["market_data"] = fetch_market_data()
        return context
```

---

#### 5. TaskHooks

**Purpose**: Create and manage tasks with custom metadata and domain-specific attributes.

**Use cases:**
- Create tasks with custom fields (risk style, strategy path, methodology)
- Integrate with domain workflows (trading strategies, research projects)
- Link tasks to domain objects (backtests, papers, experiments)
- Add custom tags and metadata

**When to implement:**
- You need to create tasks with domain-specific metadata
- You need to integrate village tasks with your domain's workflow
- You need to link tasks to domain objects

**Signature:**
```python
from village.extensibility.task_hooks import (
    TaskHooks,
    TaskHookSpec,
    TaskCreated,
)

class MyHooks(TaskHooks):
    async def should_create_task_hook(self, context: dict) -> bool:
        # Return True if hook should fire
        return True

    async def create_hook_spec(self, context: dict) -> TaskHookSpec:
        return TaskHookSpec(
            title=context["title"],
            description=context["description"],
            issue_type="task",
            priority=1,
            tags=["custom", "domain"],
            metadata={"custom_field": "value"}
        )

    async def on_task_created(self, created: TaskCreated, context: dict) -> None:
        # Handle task creation
        pass

    async def on_task_updated(self, task_id: str, updates: dict) -> None:
        # Handle task updates
        pass
```

---

#### 6. ServerDiscovery

**Purpose**: Dynamically discover and filter MCP servers based on availability and configuration.

**Use cases:**
- Load Jesse backtesting server only if strategy exists
- Discover available research APIs
- Conditionally load servers based on environment
- Filter servers by permissions or capabilities

**When to implement:**
- You need to dynamically discover MCP servers
- You need to conditionally load servers
- You need to filter servers based on runtime conditions

**Signature:**
```python
from village.extensibility.server_discovery import (
    ServerDiscovery,
    MCPServer,
)

class MyDiscovery(ServerDiscovery):
    async def discover_servers(self) -> list[MCPServer]:
        return [
            MCPServer(
                name="server1",
                type="stdio",
                command="mcp-server",
                args=["--config", "config.yaml"]
            )
        ]

    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        # Filter based on conditions
        return [s for s in servers if s.enabled]

    async def should_load_server(self, server: MCPServer) -> bool:
        # Return True if server should be loaded
        return server.enabled
```

---

#### 7. LLMProviderAdapter

**Purpose**: Customize LLM provider configuration, model routing, and retry logic.

**Use cases:**
- Route different query types to different models
- Use domain-specific models (e.g., Claude Sonnet for backtests)
- Customize timeouts and token limits per query type
- Add domain-specific retry logic

**When to implement:**
- You need to use different models for different queries
- You need to customize retry behavior
- You need to adjust timeouts or token limits dynamically

**Signature:**
```python
from village.extensibility.llm_adapters import (
    LLMProviderAdapter,
    LLMProviderConfig,
)

class MyAdapter(LLMProviderAdapter):
    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        # Modify config based on query type, context, etc.
        return modified_config

    async def should_retry(self, error: Exception) -> bool:
        # Return True if error is retryable
        return "rate_limit" in str(error).lower()

    async def get_retry_delay(self, attempt: int) -> float:
        # Return delay in seconds
        return 2 ** attempt  # Exponential backoff
```

---

## 4. Step-by-Step Tutorials

### Tutorial 1: Input Normalization with ChatProcessor

**Goal**: Normalize trading pair names (e.g., "btc-eth" → "BTC-ETH")

Create `trading_extensions/processors.py`:

```python
"""Trading-specific chat processor."""

import re
from village.extensibility.processors import ChatProcessor


class TradingChatProcessor(ChatProcessor):
    """Normalize trading pairs and extract risk styles."""

    def __init__(self):
        self._pair_pattern = re.compile(r'\b([a-z]{3,4})[-/_]([a-z]{3,4})\b')
        self._risk_styles = ["aggressive", "balanced", "conservative"]

    async def pre_process(self, user_input: str) -> str:
        """Normalize trading pairs to uppercase format."""
        # Convert pairs: btc-eth → BTC-ETH
        normalized = self._pair_pattern.sub(
            lambda m: f"{m.group(1).upper()}-{m.group(2).upper()}",
            user_input
        )

        # Detect and extract risk style
        for style in self._risk_styles:
            if style.lower() in normalized.lower():
                normalized = f"[risk_style:{style}] {normalized}"
                break

        return normalized

    async def post_process(self, response: str) -> str:
        """Add trading-specific formatting."""
        return f"📊 {response}"
```

Test it:

```python
"""Test trading processor."""

import asyncio
from trading_extensions.processors import TradingChatProcessor


async def test():
    processor = TradingChatProcessor()

    # Test pair normalization
    result = await processor.pre_process("analyze btc-eth pair")
    print(result)  # "analyze BTC-ETH pair"

    # Test risk style extraction
    result = await processor.pre_process("use aggressive strategy for btc-eth")
    print(result)  # "[risk_style:aggressive] use aggressive strategy for BTC-ETH"

    # Test output formatting
    result = await processor.post_process("Profit: +5.2%")
    print(result)  # "📊 Profit: +5.2%"

asyncio.run(test())
```

---

### Tutorial 2: Tool Caching with ToolInvoker

**Goal**: Cache backtest results to avoid redundant runs

Create `trading_extensions/tool_invokers.py`:

```python
"""Trading tool invoker with caching."""

import hashlib
import json
from datetime import datetime, timedelta
from village.extensibility.tool_invokers import (
    ToolInvoker,
    ToolInvocation,
    ToolResult,
)


class TradingToolInvoker(ToolInvoker):
    """Cache backtest results and add audit logging."""

    def __init__(self, cache_ttl_minutes: int = 60):
        self._cache: dict[str, dict] = {}
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)

    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        """Skip backtest if recent cache exists."""
        if invocation.tool_name != "jesse_backtest":
            return True

        cache_key = self._make_cache_key(invocation)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached["timestamp"] < self._cache_ttl:
                print(f"[CACHE] Using cached backtest: {cache_key}")
                return False

        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict:
        """Add default strategy parameters."""
        args = invocation.args.copy()

        if invocation.tool_name == "jesse_backtest":
            # Add default timeframe if not specified
            if "timeframe" not in args:
                args["timeframe"] = "1h"

            # Add default period if not specified
            if "period" not in args:
                args["period"] = "1m"

        return args

    async def on_success(self, invocation: ToolInvocation, result) -> dict:
        """Cache backtest results and log metrics."""
        if invocation.tool_name == "jesse_backtest":
            cache_key = self._make_cache_key(invocation)
            self._cache[cache_key] = {
                "timestamp": datetime.now(),
                "result": result,
            }
            print(f"[CACHE] Cached backtest: {cache_key}")

            # Extract and log metrics
            if "metrics" in result:
                print(f"[METRICS] Sharpe: {result['metrics'].get('sharpe', 'N/A')}")

        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        """Log tool errors."""
        print(f"[ERROR] {invocation.tool_name}: {error}")

    def _make_cache_key(self, invocation: ToolInvocation) -> str:
        """Create hash-based cache key."""
        key_str = f"{invocation.tool_name}:{json.dumps(invocation.args, sort_keys=True)}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
```

---

### Tutorial 3: Query Refinement with ThinkingRefiner

**Goal**: Break down "was aggressive better?" into analysis steps

Create `trading_extensions/thinking_refiners.py`:

```python
"""Trading thinking refiner."""

from village.extensibility.thinking_refiners import (
    ThinkingRefiner,
    QueryRefinement,
)


class TradingThinkingRefiner(ThinkingRefiner):
    """Refine trading queries into structured analysis steps."""

    def __init__(self):
        self._comparison_keywords = ["better", "worse", "compare", "vs", "versus"]

    async def should_refine(self, user_query: str) -> bool:
        """Refine queries asking for comparisons."""
        return any(keyword in user_query.lower() for keyword in self._comparison_keywords)

    async def refine_query(self, user_query: str) -> QueryRefinement:
        """Break comparison queries into analysis steps."""
        query_lower = user_query.lower()

        # Determine if asking about risk styles
        risk_styles = []
        for style in ["aggressive", "balanced", "conservative"]:
            if style in query_lower:
                risk_styles.append(style)

        if risk_styles:
            steps = [
                f"Retrieve {', '.join(risk_styles)} strategies from knowledge store",
                "Run counterfactual backtests on same period",
                "Calculate performance metrics (Sharpe, drawdown, hit rate)",
                "Compare metrics and identify best performer",
                "Generate summary with trade-offs"
            ]

            context_hints = {
                "required_data_sources": ["knowledge_store", "jesse"],
                "risk_styles": risk_styles,
            }
        else:
            steps = [user_query]
            context_hints = {}

        return QueryRefinement(
            original_query=user_query,
            refined_steps=steps,
            context_hints=context_hints,
        )
```

---

### Tutorial 4: Session Persistence with ChatContext

**Goal**: Load/save trading session state with market data

Create `trading_extensions/context.py`:

```python
"""Trading chat context with persistence."""

import json
from pathlib import Path
from datetime import datetime
from village.extensibility.context import (
    ChatContext,
    SessionContext,
)


class TradingChatContext(ChatContext):
    """Persist trading sessions with market data."""

    def __init__(self, sessions_dir: str = "~/.village/sessions"):
        self.sessions_dir = Path(sessions_dir).expanduser()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    async def load_context(self, session_id: str) -> SessionContext:
        """Load session from file."""
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            with open(session_file) as f:
                data = json.load(f)
                return SessionContext(
                    session_id=session_id,
                    user_data=data.get("user_data", {}),
                    metadata=data.get("metadata", {}),
                )
        else:
            return SessionContext(
                session_id=session_id,
                user_data={"recent_pairs": [], "default_risk_style": "balanced"},
            )

    async def save_context(self, context: SessionContext) -> None:
        """Save session to file."""
        session_file = self.sessions_dir / f"{context.session_id}.json"

        data = {
            "user_data": context.user_data,
            "metadata": context.metadata,
        }

        with open(session_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[CONTEXT] Saved session: {context.session_id}")

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Enrich with market snapshot and session info."""
        # Add timestamp
        context.metadata["timestamp"] = datetime.now().isoformat()

        # Add market data (simulated - in real use, call API)
        context.metadata["market_snapshot"] = {
            "BTC": 95000.0,
            "ETH": 3400.0,
            "timestamp": datetime.now().isoformat(),
        }

        # Track recently used pairs
        if "recent_pairs" not in context.user_data:
            context.user_data["recent_pairs"] = []

        return context
```

---

### Tutorial 5: Custom Task Metadata with TaskHooks

**Goal**: Create trading tasks with strategy and risk style metadata

Create `trading_extensions/task_hooks.py`:

```python
"""Trading task hooks."""

from village.extensibility.task_hooks import (
    TaskHooks,
    TaskHookSpec,
    TaskCreated,
)


class TradingTaskHooks(TaskHooks):
    """Create trading tasks with strategy and risk metadata."""

    async def should_create_task_hook(self, context: dict) -> bool:
        """Create hook for all trading tasks."""
        return context.get("task_type") == "trading"

    async def create_hook_spec(self, context: dict) -> TaskHookSpec:
        """Create hook with trading metadata."""
        title = context.get("title", "Trading Task")
        description = context.get("description", "")

        # Extract risk style
        risk_style = context.get("risk_style", "balanced").lower()

        # Extract strategy path
        strategy_path = context.get("strategy_path", "")

        # Determine priority based on risk style
        priority_map = {"aggressive": 0, "balanced": 1, "conservative": 2}
        priority = priority_map.get(risk_style, 2)

        tags = ["trading", risk_style]
        if strategy_path:
            tags.append(f"strategy:{strategy_path}")

        metadata = {
            "risk_style": risk_style,
            "strategy_path": strategy_path,
            "trading_pair": context.get("pair", ""),
            "timeframe": context.get("timeframe", "1h"),
        }

        return TaskHookSpec(
            title=title,
            description=description,
            issue_type="task",
            priority=priority,
            tags=tags,
            metadata=metadata,
        )

    async def on_task_created(self, created: TaskCreated, context: dict) -> None:
        """Handle task creation."""
        risk_style = created.metadata.get("risk_style", "unknown")
        print(f"[TASKS] Created trading task {created.task_id} (risk: {risk_style})")

    async def on_task_updated(self, task_id: str, updates: dict) -> None:
        """Handle task updates."""
        print(f"[TASKS] Updated task {task_id}: {updates}")
```

---

### Tutorial 6: Dynamic MCP Servers with ServerDiscovery

**Goal**: Load Jesse server only if trading strategy exists

Create `trading_extensions/server_discovery.py`:

```python
"""Trading server discovery."""

from pathlib import Path
from village.extensibility.server_discovery import (
    ServerDiscovery,
    MCPServer,
)


class TradingServerDiscovery(ServerDiscovery):
    """Discover MCP servers for trading domain."""

    def __init__(self, strategies_dir: str = "~/.village/strategies"):
        self.strategies_dir = Path(strategies_dir).expanduser()

    async def discover_servers(self) -> list[MCPServer]:
        """Discover available trading MCP servers."""
        servers = [
            MCPServer(
                name="perplexity",
                type="stdio",
                command="perplexity-mcp",
            )
        ]

        # Only load Jesse if strategies exist
        if self.strategies_dir.exists() and any(self.strategies_dir.iterdir()):
            servers.append(
                MCPServer(
                    name="jesse",
                    type="stdio",
                    command="jesse-mcp",
                    args=["--strategies-dir", str(self.strategies_dir)],
                )
            )
            print(f"[DISCOVERY] Found Jesse server (strategies in {self.strategies_dir})")
        else:
            print(f"[DISCOVERY] No strategies found, skipping Jesse server")

        return servers

    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        """Filter based on environment."""
        # In production, you might filter based on:
        # - API key availability
        # - Service health checks
        # - User permissions
        return [s for s in servers if s.enabled]

    async def should_load_server(self, server: MCPServer) -> bool:
        """Determine if server should be loaded."""
        # For Jesse, check if strategies directory exists
        if server.name == "jesse":
            return self.strategies_dir.exists()

        return server.enabled
```

---

### Tutorial 7: Model Routing with LLMProviderAdapter

**Goal**: Use different models for different query types

Create `trading_extensions/llm_adapters.py`:

```python
"""Trading LLM adapter with model routing."""

from village.extensibility.llm_adapters import (
    LLMProviderAdapter,
    LLMProviderConfig,
)


class TradingLLMAdapter(LLMProviderAdapter):
    """Route queries to appropriate models."""

    def __init__(self):
        self._query_keywords = {
            "backtest": ["backtest", "analyze", "optimize"],
            "research": ["research", "paper", "study"],
            "simple": ["what", "how", "explain", "status"],
        }

    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        """Route to appropriate model based on query type."""
        # Get query from context hint
        query_type = base_config.metadata.get("query_type", "simple")

        if query_type == "backtest":
            # Use faster model for backtest analysis
            return LLMProviderConfig(
                provider="anthropic",
                model="claude-3-5-sonnet",
                api_key_env="ANTHROPIC_API_KEY",
                timeout=180,
                max_tokens=2048,
                temperature=0.3,
                metadata={"query_type": query_type}
            )
        elif query_type == "research":
            # Use most capable model for research
            return LLMProviderConfig(
                provider="anthropic",
                model="claude-3-5-opus",
                api_key_env="ANTHROPIC_API_KEY",
                timeout=300,
                max_tokens=4096,
                temperature=0.5,
                metadata={"query_type": query_type}
            )
        else:
            # Use default for simple queries
            return base_config

    async def should_retry(self, error: Exception) -> bool:
        """Retry on rate limits and timeouts."""
        error_str = str(error).lower()
        retryable = [
            "rate_limit",
            "timeout",
            "connection",
            "temporary",
        ]
        return any(keyword in error_str for keyword in retryable)

    async def get_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        import random
        base_delay = 2 ** attempt
        jitter = random.uniform(0, 1)
        return base_delay + jitter
```

Bootstrap all trading extensions:

```python
"""Bootstrap trading extensions."""

from village.extensibility import ExtensionRegistry
from trading_extensions.processors import TradingChatProcessor
from trading_extensions.tool_invokers import TradingToolInvoker
from trading_extensions.thinking_refiners import TradingThinkingRefiner
from trading_extensions.context import TradingChatContext
from trading_extensions.task_hooks import TradingTaskHooks
from trading_extensions.server_discovery import TradingServerDiscovery
from trading_extensions.llm_adapters import TradingLLMAdapter


def bootstrap_trading_extensions() -> ExtensionRegistry:
    """Initialize all trading extensions."""
    registry = ExtensionRegistry()

    # Register all extensions
    registry.register_processor(TradingChatProcessor())
    registry.register_tool_invoker(TradingToolInvoker())
    registry.register_thinking_refiner(TradingThinkingRefiner())
    registry.register_chat_context(TradingChatContext())
    registry.register_task_hooks(TradingTaskHooks())
    registry.register_server_discovery(TradingServerDiscovery())
    registry.register_llm_adapter(TradingLLMAdapter())

    return registry
```

---

## 5. Configuration

### Config File Format

Village loads extensions from configuration files. Create `.village/config`:

```ini
[village]
# Core Village settings
llm_provider = "anthropic"
mcp_use_path = "mcp-use"

[extensions]
# Enable extension system
enabled = true

# Extension module paths (module.ClassName format)
processor_module = trading_extensions.processors.TradingChatProcessor
tool_invoker_module = trading_extensions.tool_invokers.TradingToolInvoker
thinking_refiner_module = trading_extensions.thinking_refiners.TradingThinkingRefiner
chat_context_module = trading_extensions.context.TradingChatContext
task_hooks_module = trading_extensions.task_hooks.TradingTaskHooks
server_discovery_module = trading_extensions.server_discovery.TradingServerDiscovery
llm_adapter_module = trading_extensions.llm_adapters.TradingLLMAdapter
```

### Environment Variable Options

You can also configure extensions via environment variables:

```bash
# Enable/disable extensions
export VILLAGE_EXTENSIONS_ENABLED=true

# Individual extensions
export VILLAGE_EXTENSION_PROCESSOR=trading_extensions.processors.TradingChatProcessor
export VILLAGE_EXTENSION_TOOL_INVOKER=trading_extensions.tool_invokers.TradingToolInvoker
export VILLAGE_EXTENSION_THINKING_REFINER=trading_extensions.thinking_refiners.TradingThinkingRefiner
export VILLAGE_EXTENSION_CHAT_CONTEXT=trading_extensions.context.TradingChatContext
export VILLAGE_EXTENSION_TASK_HOOKS=trading_extensions.task_hooks.TradingTaskHooks
export VILLAGE_EXTENSION_SERVER_DISCOVERY=trading_extensions.server_discovery.TradingServerDiscovery
export VILLAGE_EXTENSION_LLM_ADAPTER=trading_extensions.llm_adapters.TradingLLMAdapter
```

Environment variables take precedence over config file settings.

### Extension Loading Order

Extensions are loaded in this order:

1. **ExtensionConfig** is loaded from config and environment
2. **ExtensionRegistry** is created with defaults
3. Each extension module is loaded dynamically via `importlib`
4. Extensions are registered in the registry
5. Extensions are validated (must inherit from correct ABC)

If an extension fails to load, Village logs a warning and continues with defaults.

### Troubleshooting Loading Failures

**Problem**: Extension not loading

**Check**:
```python
from village.extensibility import ExtensionRegistry, initialize_extensions
from village.config import Config

config = Config.load()
registry = await initialize_extensions(config)

# Print loaded extensions
print(registry.get_all_names())
```

**Common issues**:

1. **Module not found**: Ensure module is in `PYTHONPATH`
2. **Class not found**: Verify `module.ClassName` format
3. **Wrong type**: Extension must inherit from correct ABC
4. **Import errors**: Check extension imports and dependencies

**Debug logging**:
```bash
export VILLAGE_DEBUG=true
village chat --verbose
```

---

## 6. Best Practices

### When to Implement vs Use Defaults

**Implement custom extension when**:
- You have domain-specific requirements
- You need custom logic that defaults don't provide
- You want to integrate with domain services
- You need to transform data in domain-specific ways

**Use defaults when**:
- Village's default behavior is sufficient
- You're just getting started
- You don't need domain-specific customization

**Rule of thumb**: Start with defaults, implement extensions as needed.

### Error Handling and Logging

**Always handle errors gracefully**:

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class MyProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        try:
            return self._transform(user_input)
        except Exception as e:
            logger.error(f"Pre-process failed: {e}", exc_info=True)
            return user_input  # Fallback to original input
```

**Use appropriate log levels**:
- `DEBUG`: Detailed flow information
- `INFO`: Important events (extension loaded, task created)
- `WARNING`: Recoverable issues (cache miss, missing data)
- `ERROR`: Failures that affect functionality

### Testing Extensions

**Unit test each extension independently**:

```python
import pytest
from trading_extensions.processors import TradingChatProcessor


@pytest.mark.asyncio
async def test_pair_normalization():
    processor = TradingChatProcessor()
    result = await processor.pre_process("analyze btc-eth")
    assert "BTC-ETH" in result


@pytest.mark.asyncio
async def test_risk_style_extraction():
    processor = TradingChatProcessor()
    result = await processor.pre_process("use aggressive strategy")
    assert "[risk_style:aggressive]" in result


@pytest.mark.asyncio
async def test_error_handling():
    processor = TradingChatProcessor()
    result = await processor.pre_process("invalid input @#$")
    assert isinstance(result, str)  # Should return something, not crash
```

**Test integration with Village**:

```python
from village.extensibility import ExtensionRegistry


@pytest.mark.asyncio
async def test_extension_registration():
    registry = ExtensionRegistry()
    processor = TradingChatProcessor()
    registry.register_processor(processor)

    assert registry.get_processor() is processor
    assert registry.get_all_names()["processor"] == "TradingChatProcessor"
```

### Performance Considerations

**Avoid blocking calls in async methods**:

```python
# BAD: Blocking I/O
class BadProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        data = open("large_file.txt").read()  # Blocks event loop
        return process(data, user_input)


# GOOD: Async I/O
class GoodProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        import aiofiles
        async with aiofiles.open("large_file.txt") as f:
            data = await f.read()
        return process(data, user_input)
```

**Cache expensive operations**:

```python
class CachedProcessor(ChatProcessor):
    def __init__(self):
        self._cache: dict[str, str] = {}

    async def pre_process(self, user_input: str) -> str:
        if user_input in self._cache:
            return self._cache[user_input]

        result = await self._expensive_transform(user_input)
        self._cache[user_input] = result
        return result
```

**Be mindful of memory usage**:

```python
# Implement cache eviction
class SmartCachedProcessor(ChatProcessor):
    def __init__(self, max_cache_size: int = 100):
        self._cache: dict[str, str] = {}
        self._max_size = max_cache_size

    async def pre_process(self, user_input: str) -> str:
        if user_input in self._cache:
            return self._cache[user_input]

        if len(self._cache) >= self._max_size:
            # Evict oldest entry
            self._cache.pop(next(iter(self._cache)))

        result = await self._transform(user_input)
        self._cache[user_input] = result
        return result
```

---

## 7. Examples

### Complete Example: Research Domain

The `examples/research/` directory shows a complete research domain implementation.

**Structure**:
```
examples/research/
├── __init__.py
└── chat/
    ├── __init__.py
    ├── processors.py          # ResearchChatProcessor
    ├── tool_invokers.py       # ResearchToolInvoker
    ├── thinking_refiners.py   # ResearchThinkingRefiner
    ├── context.py             # ResearchChatContext
    └── task_hooks.py           # ResearchTaskHooks
```

**Key features**:
- Query normalization for research topics
- Citation formatting (APA, MLA)
- Query caching for search tools
- Systematic review methodology injection
- Task creation with research field metadata

**Bootstrap**:
```python
from village.extensibility import ExtensionRegistry
from examples.research.chat import (
    ResearchChatProcessor,
    ResearchToolInvoker,
    ResearchThinkingRefiner,
    ResearchChatContext,
    ResearchTaskHooks,
)


def bootstrap_research_extensions() -> ExtensionRegistry:
    """Initialize research extensions."""
    registry = ExtensionRegistry()

    registry.register_processor(ResearchChatProcessor(citation_style="APA"))
    registry.register_tool_invoker(ResearchToolInvoker())
    registry.register_thinking_refiner(ResearchThinkingRefiner())
    registry.register_chat_context(ResearchChatContext())
    registry.register_task_hooks(ResearchTaskHooks())

    return registry
```

### Multi-Extension Example: Trading Domain

Combines all 7 extensions for a complete trading domain:

```python
"""Complete trading domain bootstrap."""

from village.extensibility import ExtensionRegistry
from trading_extensions.processors import TradingChatProcessor
from trading_extensions.tool_invokers import TradingToolInvoker
from trading_extensions.thinking_refiners import TradingThinkingRefiner
from trading_extensions.context import TradingChatContext
from trading_extensions.task_hooks import TradingTaskHooks
from trading_extensions.server_discovery import TradingServerDiscovery
from trading_extensions.llm_adapters import TradingLLMAdapter


def bootstrap_trading_domain() -> ExtensionRegistry:
    """Initialize complete trading domain."""
    registry = ExtensionRegistry()

    # Message processing: normalize pairs, extract risk styles
    registry.register_processor(TradingChatProcessor())

    # Tool invocation: cache backtests, log metrics
    registry.register_tool_invoker(TradingToolInvoker(cache_ttl_minutes=60))

    # Query refinement: break down comparisons
    registry.register_thinking_refiner(TradingThinkingRefiner())

    # Context: persist sessions, enrich with market data
    registry.register_chat_context(TradingChatContext(sessions_dir="~/.village/sessions"))

    # village tasks: create tasks with strategy and risk metadata
    registry.register_task_hooks(TradingTaskHooks())

    # Server discovery: load Jesse only if strategies exist
    registry.register_server_discovery(TradingServerDiscovery(strategies_dir="~/.village/strategies"))

    # LLM adapter: route to appropriate models
    registry.register_llm_adapter(TradingLLMAdapter())

    return registry


# Usage
async def main():
    from village.config import Config

    config = Config.load()
    registry = bootstrap_trading_domain()

    # Village will now use trading extensions
    from village.chat.llm_chat import LLMChat
    chat = LLMChat(config=config, registry=registry)

    # Use chat...
```

### Minimal Working Examples

**Minimal ChatProcessor**:
```python
from village.extensibility.processors import ChatProcessor


class SimpleProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        return user_input.strip().lower()

    async def post_process(self, response: str) -> str:
        return response.strip()
```

**Minimal ToolInvoker**:
```python
from village.extensibility.tool_invokers import ToolInvoker, ToolInvocation


class SimpleInvoker(ToolInvoker):
    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict:
        return invocation.args

    async def on_success(self, invocation: ToolInvocation, result) -> Any:
        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        print(f"Error: {error}")
```

---

## 8. Migration Guide

### Moving from Custom Fork to Extensions

If you have a custom Village fork, migrate to extensions:

**Step 1: Identify Customizations**

Review your fork's changes:
```bash
git diff village/main...upstream/main --stat
```

Categorize changes into:
- Message processing → `ChatProcessor`
- Tool invocation → `ToolInvoker`
- Query logic → `ThinkingRefiner`
- State management → `ChatContext`
- Task/metadata → `TaskHooks`
- Server config → `ServerDiscovery`
- LLM config → `LLMProviderAdapter`

**Step 2: Extract Extensions**

Create separate modules for each category:
```bash
mkdir my_extensions/
touch my_extensions/{processors,tool_invokers,thinking_refiners,context,task_hooks,server_discovery,llm_adapters}.py
```

**Step 3: Implement Extensions**

Move logic from fork to extension classes.

**Example**:
```python
# In your fork (village/chat/llm_chat.py):
def pre_process_message(self, message: str) -> str:
    # Custom logic here
    return normalized_message

# In your extension (my_extensions/processors.py):
from village.extensibility.processors import ChatProcessor

class MyProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        # Same logic here
        return normalized_message
```

**Step 4: Test Extensions**

Verify extensions reproduce fork behavior:
```python
import pytest
from my_extensions import MyProcessor


@pytest.mark.asyncio
async def test_matches_fork_behavior():
    processor = MyProcessor()
    result = await processor.pre_process("test input")
    assert result == "expected output"
```

**Step 5: Switch Village**

Update to use latest Village:
```bash
git remote add upstream https://github.com/bkuri/village.git
git fetch upstream
git checkout upstream/main
```

**Step 6: Load Extensions**

Configure extensions in `.village/config`:
```ini
[extensions]
enabled = true
processor_module = my_extensions.processors.MyProcessor
```

**Step 7: Validate**

Test that Village works with extensions:
```bash
village chat
```

**Step 8: Clean Up**

Delete custom fork repository (optional).

### Common Patterns and Anti-Patterns

**✅ DO**:
- Keep extensions focused and single-purpose
- Use sensible defaults and fallbacks
- Log extension activity for debugging
- Test extensions independently
- Document extension behavior

**❌ DON'T**:
- Mix multiple concerns in one extension
- Hardcode configuration (use config/kwargs)
- Make blocking I/O calls in async methods
- Assume Village internal state
- Forget error handling

**Example Anti-Pattern**:
```python
# BAD: Mixed concerns, blocking I/O, no error handling
class BadProcessor(ChatProcessor):
    async def pre_process(self, user_input: str) -> str:
        # Blocking database call
        data = db.query("SELECT * FROM users")  # Blocks!

        # Multiple concerns: validation, transformation, enrichment
        if not data:
            return "error"

        transformed = user_input.upper()
        enriched = f"{data}: {transformed}"
        return enriched
```

**Example Pattern**:
```python
# GOOD: Focused, async, error handling, fallback
class GoodProcessor(ChatProcessor):
    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def pre_process(self, user_input: str) -> str:
        try:
            # Async database call
            data = await self.db_pool.fetch("SELECT * FROM users")
        except Exception as e:
            logger.error(f"Database error: {e}")
            data = None

        # Single concern: transformation
        transformed = user_input.upper()
        return transformed
```

---

## Extension Flow Diagram

```
User Input
    ↓
[ChatProcessor.pre_process] ← Normalize input
    ↓
[ThinkingRefiner.refine_query] ← Break into steps (if needed)
    ↓
[ChatContext.enrich_context] ← Add domain data
    ↓
LLM Query
    ↓
LLM Response
    ↓
[ChatProcessor.post_process] ← Format output
    ↓
User Output

Tool Invocation Flow:
[ToolInvoker.should_invoke] ← Check cache/conditions
    ↓
[ToolInvoker.transform_args] ← Add defaults
    ↓
Execute Tool
    ↓
[ToolInvoker.on_success] ← Cache result, log metrics
    OR
[ToolInvoker.on_error] ← Handle error
```

---

## Summary

This guide covers:
- ✅ 7 extension points with use cases and examples
- ✅ 7 step-by-step tutorials with complete code
- ✅ Configuration via files and environment variables
- ✅ Testing and debugging strategies
- ✅ Performance best practices
- ✅ Migration guide from custom forks
- ✅ Anti-patterns to avoid

You now have everything you need to build custom Village extensions!

---

## Additional Resources

- **Source code**: `village/extensibility/`
- **Example implementations**: `examples/research/chat/`
- **PRD**: `docs/EXTENSIBILITY.md`
- **Main documentation**: `README.md`

For questions or contributions, see the Village repository.

