---
id: note-008
tags: [acp_api_reference]
created: 2026-05-10T09:33:06.262409+00:00
source: docs/ACP_API_REFERENCE.md
---

# ACP_API_REFERENCE

# ACP API Reference

Complete API documentation for Village's ACP integration.

---

## Table of Contents

1. [Overview](#overview)
2. [Bridge API](#bridge-api)
3. [Session Methods](#session-methods)
4. [File System Methods](#file-system-methods)
5. [Terminal Methods](#terminal-methods)
6. [Notification Streaming](#notification-streaming)
7. [Error Types](#error-types)
8. [Type Definitions](#type-definitions)

---

## Overview

Village's ACP integration provides a bridge between ACP protocol and Village core operations.

### Architecture

```
ACP Request → ACPBridge → Village Core → Response/Notification
```

### Module Structure

```
village/acp/
├── __init__.py           # Public API exports
├── bridge.py             # ACPBridge (core integration)
├── agent.py              # VillageACPAgent (server)
└── external_client.py    # VillageACPClient (client)
```

### Quick Reference

| Category | Methods | Purpose |
|----------|---------|---------|
| Session | `new`, `load`, `prompt`, `cancel` | Task lifecycle |
| File System | `read_text_file`, `write_text_file` | Worktree access |
| Terminal | `create`, `output`, `kill`, `release`, `wait_for_exit` | Command execution |
| Notifications | `stream_notifications` | Real-time updates |

---

## Bridge API

### Class: ACPBridge

**Module:** `village.acp.bridge`

**Purpose:** Translate ACP protocol to Village operations.

#### Constructor

```python
ACPBridge(config: Config | None = None)
```

**Parameters:**
- `config` - Village configuration (uses default if not provided)

**Example:**
```python
from village.acp.bridge import ACPBridge
from village.config import get_config

config = get_config()
bridge = ACPBridge(config)
```

---

## Session Methods

### session_new

Create a new ACP session (Village task).

```python
async def session_new(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params` (dict) - Additional session parameters

**Returns:**
```python
{
    "sessionId": str,  # Session ID
    "state": "queued", # Initial state
}
```

**Raises:**
- `ACPBridgeError` - If sessionId not provided or creation fails

**Example:**
```python
result = await bridge.session_new({
    "sessionId": "bd-a3f8",
    "cwd": "/path/to/repo",
})
# Returns: {"sessionId": "bd-a3f8", "state": "queued"}
```

**Village Operation:**
- Creates task in `QUEUED` state via `TaskStateMachine`
- Logs initialization event

---

### session_load

Load an existing session (Village task).

```python
async def session_load(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID

**Returns:**
```python
{
    "sessionId": str,           # Session ID
    "state": str,               # Current state
    "lock": dict | None,        # Lock info if exists
}
```

**Raises:**
- `ACPBridgeError` - If sessionId not provided or task not found

**Example:**
```python
result = await bridge.session_load({
    "sessionId": "bd-a3f8",
})
# Returns: {
#     "sessionId": "bd-a3f8",
#     "state": "in_progress",
#     "lock": {
#         "taskId": "bd-a3f8",
#         "paneId": "%12",
#         "window": "worker-1-bd-a3f8",
#         "agent": "worker",
#         "claimedAt": "2026-01-25T10:30:45Z",
#     }
# }
```

**Village Operation:**
- Reads task state via `TaskStateMachine`
- Loads lock file if exists
- Returns current state and lock info

---

### session_prompt

Execute a session (Village resume).

```python
async def session_prompt(
    params: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.message` (str, optional) - Prompt message
- `params.agent` (str, optional) - Agent name (default: config.default_agent)

**Returns:**
```python
(
    {
        "sessionId": str,       # Session ID
        "stopReason": str,      # "end_turn" or "cancelled"
        "content": str,         # Formatted result
    },
    [                          # List of notifications
        {
            "method": "session/update",
            "params": {
                "sessionId": str,
                "update": dict,
            }
        }
    ]
)
```

**Raises:**
- `ACPBridgeError` - If sessionId not provided, task not found, or execution fails

**Example:**
```python
response, notifications = await bridge.session_prompt({
    "sessionId": "bd-a3f8",
    "message": "Fix the bug in auth.py",
    "agent": "worker",
})

print(response["content"])
# ✓ Task bd-a3f8 executed
# Agent: worker
# Worktree: .worktrees/bd-a3f8
# Window: worker-1-bd-a3f8
# Pane: %12

for notif in notifications:
    print(notif["params"]["update"]["type"])
# state_change
# lifecycle
# file_change
```

**Village Operation:**
- Transitions task to `IN_PROGRESS` state
- Executes `execute_resume()` to spawn agent
- Collects events and converts to notifications
- Returns formatted result

---

### session_cancel

Cancel or pause a session.

```python
async def session_cancel(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID

**Returns:**
```python
{
    "sessionId": str,  # Session ID
    "state": str,      # Final state
}
```

**Raises:**
- `ACPBridgeError` - If sessionId not provided or cancel fails

**State Transitions:**
| Current State | Action | Final State |
|---------------|--------|-------------|
| `QUEUED` | Fail task | `FAILED` |
| `CLAIMED` | Fail task | `FAILED` |
| `IN_PROGRESS` | Pause task | `PAUSED` |
| `PAUSED` | No change | `PAUSED` |
| `COMPLETED` | No change | `COMPLETED` |
| `FAILED` | No change | `FAILED` |

**Example:**
```python
result = await bridge.session_cancel({
    "sessionId": "bd-a3f8",
})
# Returns: {"sessionId": "bd-a3f8", "state": "paused"}
```

**Village Operation:**
- Checks current state
- Transitions to appropriate terminal state
- Logs cancellation event

---

## File System Methods

### fs_read_text_file

Read file from Village worktree.

```python
async def fs_read_text_file(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.path` (str, required) - File path (must be in worktree)

**Returns:**
```python
{
    "content": str,  # File content
    "path": str,     # Absolute path
}
```

**Raises:**
- `ACPBridgeError` - If path invalid, not in worktree, task not active, or file not found

**Security:**
- Path must be within a Village worktree
- Task must be active (has lock and running pane)

**Example:**
```python
result = await bridge.fs_read_text_file({
    "path": "/path/to/worktrees/bd-a3f8/src/main.py",
})
print(result["content"])
# def main():
#     print("Hello, Village!")
```

**Village Operation:**
- Validates path is in worktree
- Checks task is active
- Reads file with UTF-8 encoding

---

### fs_write_text_file

Write file to Village worktree (atomic).

```python
async def fs_write_text_file(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.path` (str, required) - File path (must be in worktree)
- `params.content` (str, required) - File content

**Returns:**
```python
{
    "success": bool,  # True if successful
    "path": str,      # Absolute path
}
```

**Raises:**
- `ACPBridgeError` - If path invalid, not in worktree, task not active, or write fails

**Security:**
- Path must be within a Village worktree
- Task must be active
- Write is atomic (temp file + rename)

**Example:**
```python
result = await bridge.fs_write_text_file({
    "path": "/path/to/worktrees/bd-a3f8/src/main.py",
    "content": 'def main():\n    print("Updated!")',
})
# Returns: {"success": True, "path": "/path/to/worktrees/bd-a3f8/src/main.py"}
```

**Village Operation:**
- Validates path is in worktree
- Checks task is active
- Performs atomic write (temp file + rename)
- Logs file modification event

---

## Terminal Methods

### terminal_create

Create terminal (tmux pane) in Village session.

```python
async def terminal_create(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.command` (str, optional) - Command to execute
- `params.args` (list[str], optional) - Command arguments
- `params.cwd` (str, optional) - Working directory
- `params.env` (list, optional) - Environment variables
- `params.output_byte_limit` (int, optional) - Output size limit

**Returns:**
```python
{
    "terminalId": str,   # Terminal ID (format: term-xxxxxxxx)
    "windowName": str,   # Tmux window name
}
```

**Raises:**
- `ACPBridgeError` - If sessionId not provided, task not active, or creation fails

**Example:**
```python
result = await bridge.terminal_create({
    "sessionId": "bd-a3f8",
    "command": "pytest",
    "args": ["tests/", "-v"],
    "cwd": "/path/to/worktrees/bd-a3f8",
})
# Returns: {"terminalId": "term-a1b2c3d4", "windowName": "bd-a3f8-term-a1b2c3d4"}
```

**Village Operation:**
- Validates task is active
- Creates tmux window in Village session
- Generates unique terminal ID
- Stores terminal metadata
- Logs terminal creation event

---

### terminal_output

Capture terminal output.

```python
async def terminal_output(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.terminalId` (str, required) - Terminal ID

**Returns:**
```python
{
    "terminalId": str,    # Terminal ID
    "output": str,        # Captured output
    "truncated": bool,    # True if output exceeded byte limit
}
```

**Raises:**
- `ACPBridgeError` - If sessionId/terminalId not provided or terminal not found

**Example:**
```python
result = await bridge.terminal_output({
    "sessionId": "bd-a3f8",
    "terminalId": "term-a1b2c3d4",
})
print(result["output"])
# ======== test session starts ========
# collected 10 items
# test_main.py ...           [100%]
# ======== 10 passed in 2.34s ========
```

**Village Operation:**
- Validates terminal exists and belongs to session
- Captures tmux pane output
- Applies byte limit if configured

---

### terminal_kill

Kill terminal (tmux pane).

```python
async def terminal_kill(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.terminalId` (str, required) - Terminal ID

**Returns:**
```python
{
    "terminalId": str,  # Terminal ID
    "killed": bool,     # True if killed
}
```

**Raises:**
- `ACPBridgeError` - If sessionId/terminalId not provided or terminal not found

**Example:**
```python
result = await bridge.terminal_kill({
    "sessionId": "bd-a3f8",
    "terminalId": "term-a1b2c3d4",
})
# Returns: {"terminalId": "term-a1b2c3d4", "killed": True}
```

**Village Operation:**
- Validates terminal exists and belongs to session
- Kills tmux window
- Removes terminal from tracking
- Logs terminal kill event

---

### terminal_release

Release terminal (keep alive but stop tracking).

```python
async def terminal_release(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.terminalId` (str, required) - Terminal ID

**Returns:**
```python
{
    "terminalId": str,    # Terminal ID
    "released": bool,     # True if released
}
```

**Raises:**
- `ACPBridgeError` - If sessionId/terminalId not provided or terminal not found

**Example:**
```python
result = await bridge.terminal_release({
    "sessionId": "bd-a3f8",
    "terminalId": "term-a1b2c3d4",
})
# Returns: {"terminalId": "term-a1b2c3d4", "released": True}
```

**Village Operation:**
- Validates terminal exists and belongs to session
- Removes terminal from tracking (window stays alive)
- Logs terminal release event

---

### terminal_wait_for_exit

Wait for terminal command to exit.

```python
async def terminal_wait_for_exit(params: dict[str, Any]) -> dict[str, Any]
```

**Parameters:**
- `params.sessionId` (str, required) - Session/task ID
- `params.terminalId` (str, required) - Terminal ID
- `params.timeout` (int, optional) - Timeout in seconds (default: 60)

**Returns:**
```python
{
    "terminalId": str,        # Terminal ID
    "exitStatus": int | None, # Exit code (None if timeout)
    "timeout": bool,          # True if timed out
    "elapsed": float,         # Elapsed time in seconds
}
```

**Raises:**
- `ACPBridgeError` - If sessionId/terminalId not provided or terminal not found

**Example:**
```python
result = await bridge.terminal_wait_for_exit({
    "sessionId": "bd-a3f8",
    "terminalId": "term-a1b2c3d4",
    "timeout": 30,
})
if result.get("timeout"):
    print("Command timed out")
else:
    print(f"Exit code: {result['exitStatus']}")
```

**Village Operation:**
- Validates terminal exists and belongs to session
- Polls tmux window existence
- Returns when window disappears or timeout

---

## Notification Streaming

### stream_notifications

Stream real-time notifications for a session.

```python
async def stream_notifications(
    session_id: str,
    poll_interval: float = 0.5,
) -> AsyncGenerator[dict[str, Any], None]
```

**Parameters:**
- `session_id` (str) - Session ID to stream notifications for
- `poll_interval` (float) - Poll interval in seconds (default: 0.5)

**Yields:**
```python
{
    "method": "session/update",
    "params": {
        "sessionId": str,
        "update": {
            "type": str,      # Notification type
            "cmd": str,       # Village command
            "ts": str,        # Timestamp (ISO 8601)
            "result": str,    # Result (optional)
            "error": str,     # Error message (optional)
            "pane": str,      # Pane ID (optional)
        }
    }
}
```

**Notification Types:**
| Type | When | Village Event |
|------|------|---------------|
| `state_change` | Task state transition | `state_transition` |
| `file_change` | File modified/created/deleted | `file_modified`, `file_created`, `file_deleted` |
| `conflict` | Merge conflict detected | `conflict_detected`, `merge_conflict` |
| `lifecycle` | Task lifecycle event | `queue`, `resume`, `cleanup`, `claim`, `release` |
| `error` | Error occurred | Any event with `result=error` |

**Example:**
```python
async for notification in bridge.stream_notifications("bd-a3f8"):
    update = notification["params"]["update"]
    print(f"[{update['type']}] {update['cmd']}")
    
    if update["type"] == "state_change":
        print(f"  Task state changed")
    elif update["type"] == "file_change":
        print(f"  File modified")
    elif update["type"] == "error":
        print(f"  Error: {update.get('error')}")
```

**Village Operation:**
- Reads Village event log
- Filters events for specified session
- Converts events to ACP notifications
- Yields new notifications as they occur

---

## Error Types

### ACPBridgeError

Base exception for ACP bridge errors.

**Module:** `village.acp.bridge`

```python
class ACPBridgeError(Exception):
    """Bridge operation error."""
    pass
```

**Raised by:**
- All bridge methods on validation failures
- All bridge methods on Village operation failures

**Example:**
```python
from village.acp.bridge import ACPBridge, ACPBridgeError

try:
    result = await bridge.session_new({})
except ACPBridgeError as e:
    print(f"Bridge error: {e}")
    # Bridge error: sessionId required
```

### Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `sessionId required` | Missing sessionId parameter | Provide sessionId in params |
| `Task not found: <id>` | Task doesn't exist | Create task first or check ID |
| `Cannot start task: <reason>` | Invalid task state | Check task state with `session_load` |
| `Task execution failed: <error>` | Resume execution failed | Check Village logs |
| `Path not in Village worktree: <path>` | Path outside worktree | Use path within worktree |
| `Task not active: <id>` | Task has no lock/pane | Start task first |
| `File not found: <path>` | File doesn't exist | Check path and create file |
| `Terminal not found: <id>` | Terminal doesn't exist | Create terminal first |
| `Terminal does not belong to session` | Wrong session ID | Use correct session ID |

---

## Type Definitions

### Session State

```python
class TaskState(Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
```

### Lock Structure

```python
@dataclass
class Lock:
    task_id: str
    pane_id: str
    window: str
    agent: str
    claimed_at: datetime
```

### Event Structure

```python
@dataclass
class Event:
    ts: str           # Timestamp (ISO 8601)
    cmd: str          # Command name
    task_id: str      # Task ID
    result: str       # Result ("success" or "error")
    error: str        # Error message (optional)
    pane: str         # Pane ID (optional)
```

### ResumeResult Structure

```python
@dataclass
class ResumeResult:
    task_id: str
    agent: str
    worktree_path: Path
    window_name: str
    pane_id: str
    error: str | None
```

---

## Complete Example

```python
"""Complete ACP bridge example."""

import asyncio
from village.acp.bridge import ACPBridge, ACPBridgeError
from village.config import get_config


async def main():
    # Initialize bridge
    config = get_config()
    bridge = ACPBridge(config)
    
    try:
        # Create session
        session = await bridge.session_new({
            "sessionId": "bd-example",
        })
        print(f"Created session: {session['sessionId']}")
        
        # Execute task
        response, notifications = await bridge.session_prompt({
            "sessionId": "bd-example",
            "message": "Fix the bug",
            "agent": "worker",
        })
        print(f"Task result: {response['stopReason']}")
        print(f"Notifications: {len(notifications)}")
        
        # Stream notifications
        print("\nStreaming notifications...")
        notification_count = 0
        async for notification in bridge.stream_notifications("bd-example"):
            update = notification["params"]["update"]
            print(f"  [{update['type']}] {update['cmd']}")
            notification_count += 1
            
            if notification_count >= 10:
                break
        
        # Cancel if needed
        # result = await bridge.session_cancel({"sessionId": "bd-example"})
        
    except ACPBridgeError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## See Also

- **[Integration Guide](ACP_INTEGRATION.md)** - Architecture and overview
- **[Configuration](ACP_CONFIGURATION.md)** - Configuration reference
- **[Examples](ACP_EXAMPLES.md)** - Practical examples
- **Village Source Code:** `village/acp/bridge.py`

