---
id: note-017
tags: [single-service]
created: 2026-05-10T09:33:16.737244+00:00
source: docs/templates/single-service.md
---

# single-service

# Single Service Template

A pre-configured setup for single-service projects — simple parallel work on one codebase.

---

## When to Use This Template

Use this template if your project has:
- A single Git repository
- One service or codebase
- Multiple parallel tasks of similar type
- No need for specialized agents (all tasks use the same agent)

**Examples:**
- Backend API with multiple feature tasks
- Frontend app with multiple UI component tasks
- Library project with multiple feature implementations
- Documentation project with multiple doc page updates

---

## Architecture

```
my-service/
├── src/                    # Source code
├── tests/                  # Tests
└── .village/
    └── config
```

### Agent Type

| Agent | Purpose | Village Task Pattern | Example Tasks |
|-------|---------|---------------------|---------------|
| `worker` | General work | Any task ID | "add-auth-api", "refactor-user-model", "update-docs" |

### Task DAG Example

```
setup → add-auth-api → refactor-user-model → add-tests
      ↘ update-docs ↗
```

---

## Configuration

### Step 1: Create `.village/config`

Copy the configuration from [docs/examples/00-templates/single-service-config.ini](../examples/00-templates/single-service-config.ini):

```bash
cp docs/examples/00-templates/single-service-config.ini .village/config
```

### Step 2: Customize for Your Project

Edit `.village/config` to match your preferences:

```ini
[DEFAULT]
DEFAULT_AGENT=worker
SCM=git
MAX_WORKERS=3

[agent.worker]
# General worker: handles all tasks
opencode_args=--mode patch
contract=contracts/worker.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

### Step 3: Create Worker Contract (Optional)

If using a custom contract, create `contracts/worker.md`:

```bash
mkdir -p contracts
```

Then create `contracts/worker.md` with general task instructions.

**Alternatively:** If `ppc` is installed, Village can generate contracts automatically. The `ppc_mode` and `ppc_traits` settings in `.village/config` will be used.

---

## Workflow

### Queue Parallel Tasks

```bash
# Queue 3 ready tasks (all use the worker agent)
village queue --n 3

# Queue more tasks
village queue --n 5

# Dry-run preview (see what would be queued)
village queue --n 5 --dry-run
```

### Inspect Workers

```bash
# See all active workers
village status --workers
```

Expected output:
```
TASK_ID                STATUS    PANE     AGENT   WINDOW                   CLAIMED_AT
add-auth-api           ACTIVE    %12      worker  worker-1-add-auth-api    2026-01-25 10:30:45
refactor-user-model    ACTIVE    %13      worker  worker-2-refactor-user   2026-01-25 10:30:46
update-docs            ACTIVE    %14      worker  worker-3-update-docs     2026-01-25 10:30:47
```

### Resume a Task

```bash
# Resume a specific task
village builder resume --task add-auth-api

# Or open builder for interactive mode
village builder resume
```

---

## Task Naming Convention

With a single agent, task naming is flexible. Use descriptive names that make sense for your project:

```bash
# Feature tasks
village tasks create "Add authentication API"
village tasks create "Refactor user model"
village tasks create "Add rate limiting"

# Documentation tasks
village tasks create "Update API documentation"
village tasks create "Add getting started guide"

# Test tasks
village tasks create "Add unit tests for auth"
village tasks create "Add integration tests for API"
```

---

## Example Task DAG

Here's a realistic task DAG for adding authentication to a service:

```bash
# 1. Setup task
village tasks create "setup-auth" --description "Create auth module structure"

# 2. Feature tasks (can run in parallel)
village tasks create "add-auth-api" --depends-on setup-auth
village tasks create "add-jwt-tokens" --depends-on setup-auth
village tasks create "add-auth-middleware" --depends-on setup-auth

# 3. Refactoring task
village tasks create "refactor-user-model" --depends-on add-auth-api

# 4. Documentation task
village tasks create "update-auth-docs" --depends-on add-auth-api,add-jwt-tokens,add-auth-middleware

# 5. Testing task
village tasks create "add-auth-tests" --depends-on refactor-user-model
```

Now queue tasks:
```bash
village queue --n 3
```

Village will start tasks in dependency order:
1. `setup-auth` (first)
2. `add-auth-api`, `add-jwt-tokens`, `add-auth-middleware` (parallel)
3. `refactor-user-model`, `update-auth-docs` (after API tasks)
4. `add-auth-tests` (last)

---

## Customization

### Adjusting Concurrency

Change `MAX_WORKERS` based on your system and task type:

```ini
[DEFAULT]
# More parallelism for lightweight tasks
MAX_WORKERS=5

# Less parallelism for heavy tasks (e.g., database migrations)
MAX_WORKERS=1
```

### Changing Worker Behavior

For more exploratory work:
```ini
[agent.worker]
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown
```

For more conservative work:
```ini
[agent.worker]
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

### Adding a Specialized Agent (When Needed)

Even in a single-service project, you might eventually need specialized agents. For example, a `test` agent for testing tasks:

```ini
[agent.test]
opencode_args=--mode patch --safe
contract=contracts/test.md
ppc_mode=explore
ppc_traits=terse
ppc_format=markdown
```

Then create test-specific tasks:
```bash
village tasks create "test: Add unit tests for auth"
```

Queue with explicit agent:
```bash
village queue --agent test --n 2
```

---

## Common Patterns

### Pattern 1: Daily Feature Development

```bash
# Morning: Start 3 feature tasks
village queue --n 3

# During day: Inspect progress
village status --workers

# Resume a task to review progress
village builder resume --task add-auth-api

# End of day: Shutdown
village down
```

### Pattern 2: Batch Task Creation and Execution

```bash
# Create many tasks at once
village tasks create "Add user profile feature"
village tasks create "Add admin dashboard"
village tasks create "Add export functionality"
village tasks create "Add import functionality"

# Queue all ready tasks
village queue --n 10
```

### Pattern 3: Afternoon Testing Sprint

```bash
# Afternoon: Switch to testing tasks
village queue --agent test --n 5

# Review test results
village builder resume --task test-add-auth-tests
```

### Pattern 4: Documentation Sprint

```bash
# End of sprint: Documentation tasks
village tasks create "Update API docs for auth"
village tasks create "Add migration guide"
village tasks create "Add troubleshooting section"

# Queue documentation tasks
village queue --n 3
```

---

## Troubleshooting

**Issue: Tasks not starting despite village tasks showing ready tasks**

**Fix:** Verify Village is initialized:
```bash
village up
village tasks ready
```

**Issue: Workers starting but completing immediately**

**Fix:** Check contract file and task descriptions:
```bash
# Verify contract exists
cat contracts/worker.md

# Check task has description
village tasks show <task-id>
```

**Issue: Too many workers running, system slow**

**Fix:** Reduce concurrency:
```bash
# Set environment variable for single command
VILLAGE_MAX_WORKERS=2 village queue --n 3

# Or set permanently in .village/config
# Edit: MAX_WORKERS=2
```

**Issue: Task stuck, worker pane unresponsive**

**Fix:** Kill the worker and clean up:
```bash
# Kill tmux pane
tmux kill-pane -t %12

# Clean up stale lock
village cleanup --apply

# Re-queue the task
village queue --n 1
```

---

## Migration from Multiple Agents

If you started with multiple agents but want to simplify to a single agent:

**1. Remove agent-specific sections from `.village/config`:**
```ini
# Remove [agent.backend], [agent.frontend], etc.
# Keep only [agent.worker]
```

**2. Update task titles to remove prefixes:**
```bash
# Old: backend-add-auth-api
# New: add-auth-api
village tasks update backend-add-auth-api --title "add-auth-api"
```

**3. Use default agent for all tasks:**
```bash
village queue --n 3
```

---

## Next Steps

- See [docs/examples/02-configuration/custom-agent.md](../examples/02-configuration/custom-agent.md) for detailed agent customization
- See [docs/examples/03-commands/queue-multiple.md](../examples/03-commands/queue-multiple.md) for queue patterns
- See [docs/examples/05-advanced/workflow.md](../examples/05-advanced/workflow.md) for handling interrupts and recovery

