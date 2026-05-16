---
id: note-007
tags: [acp_integration]
created: 2026-05-10T09:33:05.159103+00:00
source: docs/ACP_INTEGRATION.md
---

# ACP_INTEGRATION

# ACP Integration Overview

**Agent Client Protocol (ACP)** integration enables Village to work with ecosystem tools while preserving its core coordination model.

---

## What is ACP?

ACP (Agent Client Protocol) is an open protocol that standardizes communication between AI agents and clients (editors, IDEs, orchestrators). It provides:

- **Standard interface** for agent-client communication
- **Session lifecycle** management (new, load, prompt, cancel)
- **File system** and **terminal** APIs
- **Real-time notifications** for state changes
- **Capability negotiation** between agents and clients

**Official SDK**: Village uses the official `agent-client-protocol` Python SDK.

---

## Village's Hybrid Architecture

Village uses a **hybrid approach** that adds ACP compatibility without changing Village core:

```
┌─────────────────────────────────────────┐
│         ACP Interface Layer             │
│  (village/acp/agent.py, bridge.py)      │
└────────────────┬────────────────────────┘
                 │ Protocol Translation
┌────────────────┴────────────────────────┐
│         Village Core (unchanged)        │
│  - Lock system                          │
│  - Worktree management                  │
│  - Task coordination                    │
│  - State machine                        │
└─────────────────────────────────────────┘
```

### Why Hybrid?

1. **Preserves Village's strengths** - Lock-based coordination, tmux truth, git worktrees
2. **Ecosystem compatibility** - Works with ACP-compliant editors and agents
3. **No core changes** - ACP is an interface layer, not a replacement
4. **Incremental adoption** - Use ACP features only when needed

---

## Usage

### Running Village as an ACP Agent

Village runs as a stdio-based ACP agent for editor integration:

```bash
village acp                    # Run stdio agent (for editors)
village acp --list-agents      # List configured ACP agents
village acp --test <agent>     # Test connection to external agent
```

**How it works:**
```
Editor (Zed/JetBrains) → stdin/stdout → Village ACP Agent → Village Core
                                                        ↓
                                                    tmux/git/locks
```

### External ACP Agents

Village can also spawn and orchestrate external ACP-compliant agents (Claude Code, Gemini CLI, etc.):

**Example:**
```bash
# List configured agents
village acp --list-agents

# Test connection to an external agent
village acp --test claude
```

---

## Architecture Components

### 1. ACP Agent (`village/acp/agent.py`)

Implements the ACP Agent protocol over stdio to expose Village to editors.

**Key responsibilities:**
- Initialize handshake with editors via stdio
- Create/load ACP sessions (maps to Village tasks)
- Handle prompt requests (maps to Village resume)
- Stream notifications to editors

**Implementation:**
```python
class VillageACPAgent:
    """Village as an ACP-compliant agent."""
    
    async def initialize(...)  # Protocol handshake
    async def new_session(...)  # Create Village task
    async def load_session(...)  # Load existing task
    async def prompt(...)       # Execute Village resume
    async def cancel(...)       # Pause/cancel task
```

### 2. ACP Client (`village/acp/external_client.py`)

Connects to external ACP agents for Village to orchestrate.

**Key responsibilities:**
- Spawn external agent processes
- Manage agent lifecycle
- Forward Village operations to agents
- Handle agent responses

**Implementation:**
```python
class VillageACPClient(Client):
    """Village's ACP client for external agents."""
    
    async def request_permission(...)  # Auto-approve or prompt
    async def session_update(...)      # Handle agent notifications
```

### 3. ACP Bridge (`village/acp/bridge.py`)

The critical integration layer that translates between ACP and Village.

**Key responsibilities:**
- Map ACP sessions to Village tasks
- Bridge ACP methods to Village operations
- Convert Village events to ACP notifications
- Handle state transitions and error translation

**Implementation:**
```python
class ACPBridge:
    """Bridge ACP protocol to Village core."""
    
    # Session lifecycle
    async def session_new(...)
    async def session_load(...)
    async def session_prompt(...)
    async def session_cancel(...)
    
    # File system
    async def fs_read_text_file(...)
    async def fs_write_text_file(...)
    
    # Terminal
    async def terminal_create(...)
    async def terminal_output(...)
    async def terminal_kill(...)
    
    # Notifications
    async def stream_notifications(...)
```

---

## Protocol Mapping

### ACP Sessions → Village Tasks

| ACP Concept | Village Concept | Notes |
|-------------|-----------------|-------|
| Session | Task | 1:1 mapping |
| Session ID | Task ID | Same identifier |
| New session | Task creation (QUEUED) | Via state machine |
| Load session | Task lookup | Read state + lock |
| Prompt | Resume execution | Spawns agent in tmux |
| Cancel | Pause or fail | State-dependent |

### ACP Methods → Village Operations

| ACP Method | Village Operation | Implementation |
|------------|-------------------|----------------|
| `session/new` | Create task | `state_machine.initialize_state()` |
| `session/load` | Load task | `state_machine.get_state()` + lock lookup |
| `session/prompt` | Execute task | `execute_resume()` |
| `session/cancel` | Pause/fail task | `state_machine.transition()` |
| `fs/read_text_file` | Read from worktree | Path validation + file read |
| `fs/write_text_file` | Write to worktree | Atomic write + validation |
| `terminal/create` | Create tmux pane | `create_window()` |
| `terminal/output` | Capture pane output | `capture_pane()` |
| `terminal/kill` | Kill tmux pane | `kill_session()` |

### Village Events → ACP Notifications

| Village Event | ACP Notification | Type |
|---------------|------------------|------|
| State transition | `session/update` | `state_change` |
| File modified | `session/update` | `file_change` |
| Conflict detected | `session/update` | `conflict` |
| Task queued | `session/update` | `lifecycle` |
| Error | `session/update` | `error` |

---

## Benefits for Village Users

### 1. Editor Integration

**Before ACP:** Village only accessible via CLI
```bash
village queue --n 3
village builder resume --task bd-a3f8
```

**After ACP:** Use Village from your favorite editor
```
[Zed Editor]
├── Assistant Panel
│   └── Village (ACP)
│       ├── Start task: bd-a3f8
│       ├── View status
│       └── Stream notifications
```

### 2. Multi-Agent Orchestration

**Before ACP:** Only OpenCode agents
```ini
[agent.worker]
type = opencode
```

**After ACP:** Mix OpenCode + Claude Code + Gemini CLI
```ini
[agent.worker]
type = opencode

[agent.claude]
type = acp
acp_command = claude-code

[agent.gemini]
type = acp
acp_command = gemini-cli
```

### 3. Ecosystem Compatibility

- **Zed Editor**: Built-in ACP support
- **JetBrains IDEs**: ACP plugin available
- **Claude Code**: ACP-compliant agent
- **Gemini CLI**: ACP-compliant agent
- **Custom agents**: Any ACP-compliant agent

### 4. Real-Time Notifications

**Before ACP:** Poll-based status checks
```bash
watch -n 5 'village status --workers'
```

**After ACP:** Real-time event streaming
```python
async for notification in bridge.stream_notifications(session_id):
    # React to state changes instantly
    handle_notification(notification)
```

---

## Supported Editors

### Zed Editor

**Status:** ✅ Supported (native ACP support)

**Setup:**
1. Install Zed (0.120+)
2. Configure ACP agent in Zed settings (`~/.config/zed/settings.json`):
   ```json
   {
     "assistant": {
       "default_model": {
         "provider": "custom",
         "command": ["village", "acp"]
       }
     }
   }
   ```
3. Open Zed, use Assistant panel - Village will start automatically via stdio

### JetBrains IDEs

**Status:** ✅ Supported (via ACP plugin)

**Setup:**
1. Install ACP plugin for JetBrains
2. Configure plugin to use custom agent command: `village acp`
3. Use AI assistant panel in IDE - Village will start automatically via stdio

### VS Code

**Status:** 🔄 Planned (community plugin needed)

**Setup:** Requires ACP extension development

### Other Editors

Any editor with ACP support can connect to Village. Check your editor's documentation for ACP integration.

---

## Supported External Agents

### Claude Code (Anthropic)

**Status:** ✅ Supported

**Configuration:**
```ini
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal,web
```

**Usage:**
```bash
village acp --test claude
```

### Gemini CLI (Google)

**Status:** ✅ Supported

**Configuration:**
```ini
[agent.gemini]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,terminal
```

**Usage:**
```bash
village acp --test gemini
```

### Custom ACP Agents

Any ACP-compliant agent can be integrated:

```ini
[agent.custom]
type = acp
acp_command = /path/to/your/agent
acp_capabilities = filesystem,terminal
```

---

## Comparison: Native vs ACP Agents

### Native Village Agents (OpenCode)

**Pros:**
- ✅ Tight integration with Village
- ✅ Direct access to Village APIs
- ✅ No protocol overhead
- ✅ Full control over execution

**Cons:**
- ❌ Limited to OpenCode
- ❌ No editor integration
- ❌ Custom tool integration requires code changes

**Best for:**
- Production workloads
- Maximum performance
- Deep Village integration

### ACP External Agents

**Pros:**
- ✅ Use any ACP-compliant agent
- ✅ Editor integration
- ✅ Standardized interface
- ✅ Ecosystem compatibility

**Cons:**
- ❌ Protocol overhead
- ❌ Limited to ACP capabilities
- ❌ Dependency on external agent

**Best for:**
- Editor-based workflows
- Multi-agent scenarios
- Specialized capabilities (Claude, Gemini)

---

## Hybrid Workflows

### Workflow 1: Editor + CLI

```
Morning: Start tasks from Zed
  ↓
[Editor] → Village ACP Server → Queue 3 tasks
  ↓
Afternoon: Monitor from CLI
  ↓
[CLI] village status --workers
  ↓
[CLI] village builder resume --task bd-a3f8
```

### Workflow 2: Mixed Agents

```
Backend tasks → OpenCode (native)
  ↓
[agent.build]
type = opencode
  ↓
Frontend tasks → Claude Code (ACP)
  ↓
[agent.frontend]
type = acp
acp_command = claude-code
  ↓
Research tasks → Gemini CLI (ACP)
  ↓
[agent.research]
type = acp
acp_command = gemini-cli
```

### Workflow 3: Editor-Based Task Management

```
Start work from editor
  ↓
[Zed/JetBrains] → village acp → Village Core
  ↓
Queue and monitor tasks
  ↓
Real-time notifications in editor
```

---

## Security Considerations

### File System Access

- ✅ ACP agents can only access files in worktrees
- ✅ Path validation prevents directory traversal
- ✅ Atomic writes prevent corruption

### Terminal Access

- ✅ ACP agents can create terminals in Village session
- ✅ Terminal IDs are scoped to sessions
- ✅ Kill/release operations are session-scoped

### Permission Model

Village supports configurable permission modes for ACP operations:

**Modes:**
- `auto` - Auto-approve all operations (development mode)
- `ask` - Prompt user for each permission request
- `policy` - Use policy file for rules-based decisions

**Configuration:**
```ini
[acp]
enabled = true
permission_mode = policy
permission_policy_file = .village/acp-permissions.json
```

---

## Performance

### Protocol Overhead

| Operation | Native | ACP | Overhead |
|-----------|--------|-----|----------|
| Session new | ~10ms | ~15ms | +50% |
| Prompt | ~100ms | ~120ms | +20% |
| File read | ~5ms | ~8ms | +60% |
| Notification | ~1ms | ~2ms | +100% |

**Recommendation:** Use native agents for high-frequency operations.

### Scalability

- **Stdio mode:** One Village process per editor session
- **External agents:** Spawns agents on-demand
- **Bridge:** Stateless, horizontally scalable

---

## Limitations

### Current Limitations

1. **No session forking** - ACP fork not implemented
2. **Limited model selection** - Uses agent's default model

### Planned Improvements

1. **Session forking** - Clone task state
2. **Model selection** - Override agent models

---

## Getting Started

### Quick Start: Editor Integration

```bash
# 1. Enable ACP in config
cat >> .village/config <<EOF
[acp]
enabled = true
EOF

# 2. Configure your editor (see Zed/JetBrains sections above)
# Village starts automatically when editor launches the agent

# 3. Use from command line to verify
village acp
```

### Quick Start: External Agents

```bash
# 1. Define an ACP agent
cat >> .village/config <<EOF
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal
EOF

# 2. List available agents
village acp --list-agents

# 3. Test connection
village acp --test claude
```

---

## Next Steps

- **[Configuration Guide](ACP_CONFIGURATION.md)** - Detailed config reference
- **[Examples](ACP_EXAMPLES.md)** - Real-world usage examples
- **[API Reference](ACP_API_REFERENCE.md)** - Complete API documentation

---

## Troubleshooting

### "ACP is disabled"

**Fix:** Enable ACP in config:
```ini
[acp]
enabled = true
```

### "Agent not found"

**Fix:** Check agent configuration:
```bash
village acp --list-agents
cat .village/config
```

### "Agent command not found"

**Fix:** Check agent command is executable:
```bash
which claude-code
chmod +x /path/to/agent
```

### Editor not connecting

**Fix:** Verify the command in editor settings:
```bash
# Test the command directly
village acp

# Should start and wait for ACP protocol input on stdin
```

---

## References

- **ACP Specification**: https://agent-client-protocol.dev
- **Official SDK**: `pip install agent-client-protocol`
- **Village ACP Code**: `village/acp/`
- **Task Breakdown**: [docs/archive/ACP_INTEGRATION_TASKS.md](archive/ACP_INTEGRATION_TASKS.md) (archived)

