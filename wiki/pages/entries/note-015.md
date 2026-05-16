---
id: note-015
tags: [monorepo]
created: 2026-05-10T09:33:14.285687+00:00
source: docs/templates/monorepo.md
---

# monorepo

# Monorepo Template

A pre-configured setup for monorepo projects — single repository containing multiple packages or services.

---

## When to Use This Template

Use this template if your project has:
- A single Git repository
- Multiple packages or services (e.g., backend, frontend, shared libraries)
- Different types of work requiring specialized agents (backend changes, frontend changes, tests, etc.)
- Task dependencies across packages

---

## Architecture

```
monorepo/
├── packages/
│   ├── backend/           # Backend service (API, business logic)
│   ├── frontend/          # Frontend (React, Vue, etc.)
│   └── shared/            # Shared libraries (utils, types)
└── .village/
    └── config
```

### Agent Types

| Agent | Purpose | Village Task Pattern | Example Tasks |
|-------|---------|---------------------|---------------|
| `backend` | Backend work | `backend-*` | "backend-api-auth", "backend-db-migration" |
| `frontend` | Frontend work | `frontend-*` | "frontend-user-profile", "frontend-auth-flow" |
| `test` | Testing work | `test-*` | "test-e2e-auth", "test-integration-api" |

### Task DAG Example

```
backend-api-auth → frontend-user-profile → test-e2e-auth
              ↘ test-integration-api ↗
```

---

## Configuration

### Step 1: Create `.village/config`

Copy the configuration from [docs/examples/00-templates/monorepo-config.ini](../examples/00-templates/monorepo-config.ini) into your monorepo:

```bash
cp docs/examples/00-templates/monorepo-config.ini .village/config
```

### Step 2: Customize for Your Project

Edit `.village/config` to match your project structure:

```ini
[DEFAULT]
DEFAULT_AGENT=backend
SCM=git
MAX_WORKERS=3

[agent.backend]
# Backend agent: API, business logic, database changes
opencode_args=--mode patch
contract=contracts/backend.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown

[agent.frontend]
# Frontend agent: UI components, user flows, styling
opencode_args=--mode patch
contract=contracts/frontend.md
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown

[agent.test]
# Test agent: E2E tests, integration tests, test coverage
opencode_args=--mode patch --safe
contract=contracts/test.md
ppc_mode=explore
ppc_traits=terse
ppc_format=markdown
```

### Step 3: Create Agent Contracts (Optional)

If using custom contracts, create them in `contracts/`:

```bash
mkdir -p contracts
```

Then create `contracts/backend.md`, `contracts/frontend.md`, `contracts/test.md` with task-specific instructions.

**Alternatively:** If `ppc` is installed, Village can generate contracts automatically. The `ppc_mode` and `ppc_traits` settings in `.village/config` will be used.

---

## Workflow

### Queue Tasks Across Agent Types

```bash
# Queue all ready tasks (backend, frontend, test)
village queue --n 3

# Queue only backend tasks
village queue --agent backend --n 2

# Queue only frontend tasks
village queue --agent frontend --n 1
```

### Inspect Workers by Agent Type

```bash
# See all workers (includes agent type)
village status --workers
```

Expected output:
```
TASK_ID           STATUS    PANE     AGENT    WINDOW                  CLAIMED_AT
backend-api-auth   ACTIVE    %12      backend  backend-1-backend-api    2026-01-25 10:30:45
frontend-profile   ACTIVE    %13      frontend frontend-1-frontend-p   2026-01-25 10:30:46
test-e2e-auth      ACTIVE    %14      test     test-1-test-e2e-auth    2026-01-25 10:30:47
```

### Resume a Task

```bash
# Resume a backend task
village builder resume --task backend-api-auth

# Resume with specific agent (override auto-detection)
village builder resume --task backend-api-auth --agent backend
```

---

## Task Naming Convention

To enable auto-detection of agent types, name your tasks consistently:

```bash
# Backend tasks
village tasks create "backend: Add authentication API"
village tasks create "backend: Migrate user table to new schema"

# Frontend tasks
village tasks create "frontend: Add user profile page"
village tasks create "frontend: Implement auth flow"

# Test tasks
village tasks create "test: E2E authentication flow"
village tasks create "test: Integration test for user API"
```

**Note:** Village uses the first part of the task ID (before the colon) to auto-detect the agent type. If your naming convention differs, use `--agent` flag explicitly.

---

## Example Task DAG

Here's a realistic task DAG for a monorepo adding user authentication:

```bash
# 1. Backend work
village tasks create "backend: Add authentication API" --depends-on village-setup
village tasks create "backend: Add JWT token handling" --depends-on backend-auth-api

# 2. Shared library work
village tasks create "shared: Add auth utility functions" --depends-on backend-jwt

# 3. Frontend work
village tasks create "frontend: Add login page" --depends-on shared-auth-utils
village tasks create "frontend: Implement auth flow" --depends-on frontend-login-page

# 4. Testing work
village tasks create "test: Integration tests for auth API" --depends-on backend-auth-api
village tasks create "test: E2E authentication flow" --depends-on frontend-auth-flow
```

Now queue tasks:
```bash
village queue --n 5
```

Village will start tasks in dependency order, respecting the DAG.

---

## Customization

### Adding a New Agent Type

To add a `docs` agent for documentation work:

```ini
[agent.docs]
opencode_args=--mode patch
contract=contracts/docs.md
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown
```

Then create documentation tasks:
```bash
village tasks create "docs: Document authentication API"
```

### Changing PPC Traits

For a more exploratory backend agent:
```ini
[agent.backend]
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown
```

For a more conservative frontend agent:
```ini
[agent.frontend]
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

---

## Troubleshooting

**Issue: Tasks not starting for specific agent type**

**Fix:** Verify task names match agent naming convention:
```bash
# Check task names
village tasks list | grep "backend:"
```

**Issue: Wrong agent assigned to a task**

**Fix:** Use explicit `--agent` flag:
```bash
village queue --agent backend --n 2
```

Or check `.village/config` for correct agent definitions.

---

## Next Steps

- See [docs/examples/02-configuration/custom-agent.md](../examples/02-configuration/custom-agent.md) for detailed agent customization
- See [docs/examples/04-configuration/multiple-agents.md](../examples/04-configuration/multiple-agents.md) for advanced multi-agent workflows
- See [docs/examples/05-advanced/workflow.md](../examples/05-advanced/workflow.md) for handling interrupts and recovery

