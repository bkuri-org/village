---
id: note-016
tags: [microservices]
created: 2026-05-10T09:33:15.618378+00:00
source: docs/templates/microservices.md
---

# microservices

# Microservices Template

A pre-configured setup for microservices projects — multiple services in separate repositories with a shared task DAG.

---

## When to Use This Template

Use this template if your project has:
- Multiple services in separate Git repositories
- A shared task DAG (via village tasks) coordinating work across services
- Service-specific agents (auth service, payment service, inventory service, etc.)
- Cross-service dependencies (e.g., auth service must be updated before payment service can use it)

---

## Architecture

```
service-auth/          # Authentication service
service-payment/       # Payment service
service-inventory/     # Inventory service
shared-tasks/          # (Optional) Shared repo with village tasks DAG
```

### Village Tasks Integration Options

**Option A: Centralized Task DAG (Recommended)**
- Create a `shared-tasks/` repository
- Task DAG lives in `shared-tasks/`
- Each service Village runs `village tasks ready` to get tasks
- Pro: Central coordination, easy to view all tasks
- Con: Requires shared repository

**Option B: Distributed Task DAG**
- Each service has its own task DAG
- Use cross-repo references for dependencies
- Pro: No shared repo needed
- Con: More complex setup

This guide assumes **Option A** (centralized).

---

## Agent Types

| Agent | Service | Village Task Pattern | Example Tasks |
|-------|---------|---------------------|---------------|
| `auth` | Authentication | `auth-*` | "auth-oauth2-migration", "auth-add-ratelimiting" |
| `payment` | Payment | `payment-*` | "payment-stripe-integration", "payment-webhook-refactor" |
| `inventory` | Inventory | `inventory-*` | "inventory-optimization", "inventory-stock-tracking" |

### Task DAG Example

```
auth-oauth2-migration → payment-stripe-integration → inventory-stock-tracking
                    ↗
auth-add-ratelimiting ↗
```

---

## Configuration

### Step 1: Create Centralized Task Repository

```bash
mkdir shared-tasks
cd shared-tasks
git init
village tasks init
```

Note: The village tasks store is created automatically when you first run `village tasks create` in a directory.

### Step 2: Create `.village/config` in Each Service

For each service repository, copy the appropriate configuration:

```bash
# In service-auth/
cp docs/examples/00-templates/microservices-config.ini .village/config
# Edit to set DEFAULT_AGENT=auth

# In service-payment/
cp docs/examples/00-templates/microservices-config.ini .village/config
# Edit to set DEFAULT_AGENT=payment

# In service-inventory/
cp docs/examples/00-templates/microservices-config.ini .village/config
# Edit to set DEFAULT_AGENT=inventory
```

### Step 3: Customize Each Service's Config

**service-auth/.village/config:**
```ini
[DEFAULT]
DEFAULT_AGENT=auth
SCM=git
MAX_WORKERS=2

[agent.auth]
opencode_args=--mode patch
contract=contracts/auth.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

**service-payment/.village/config:**
```ini
[DEFAULT]
DEFAULT_AGENT=payment
SCM=git
MAX_WORKERS=2

[agent.payment]
opencode_args=--mode patch
contract=contracts/payment.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

**service-inventory/.village/config:**
```ini
[DEFAULT]
DEFAULT_AGENT=inventory
SCM=git
MAX_WORKERS=2

[agent.inventory]
opencode_args=--mode patch
contract=contracts/inventory.md
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown
```

### Step 4: Configure Village Tasks to Use Centralized DAG

Each service's Village must reference the centralized `shared-tasks/` repository.

**Option A: Symlink (Simplest)**
```bash
# In each service repo
ln -s /path/to/shared-tasks .village-tasks
```

**Option B: Environment Variable**
```bash
# Set tasks config directory
export VILLAGE_TASKS_DIR=/path/to/shared-tasks
```

**Option C: Git Remote (Advanced)**
```bash
# In shared-tasks/
git remote add origin git@github.com:yourorg/shared-tasks.git
git push -u origin main
```

### Step 5: Create Agent Contracts (Optional)

In each service repository:
```bash
mkdir -p contracts
```

Create service-specific contracts (e.g., `contracts/auth.md`, `contracts/payment.md`, `contracts/inventory.md`).

**Alternatively:** If `ppc` is installed, Village can generate contracts automatically.

---

## Workflow

### Queue Tasks in Each Service

Each service Village instance queues tasks from the shared DAG:

```bash
# In service-auth/
village queue --n 2

# In service-payment/
village queue --n 2

# In service-inventory/
village queue --n 2
```

### Inspect Workers Across Services

Each service Village has its own `village status --workers`:

```bash
# In service-auth/
village status --workers
```

Output:
```
TASK_ID                  STATUS    PANE     AGENT   WINDOW                  CLAIMED_AT
auth-oauth2-migration    ACTIVE    %12      auth    auth-1-auth-oauth2-mig  2026-01-25 10:30:45
auth-add-ratelimiting     ACTIVE    %13      auth    auth-2-auth-add-rate     2026-01-25 10:30:46
```

### Cross-Service Coordination

Tasks depend on each other across services. Village tasks ensures dependencies are respected:

```bash
# In shared-tasks/
village tasks create "auth: Add OAuth2 migration" --depends-on village-setup
village tasks create "payment: Add Stripe integration" --depends-on auth-oauth2-migration
village tasks create "inventory: Add stock tracking" --depends-on payment-stripe-integration
```

When `service-auth/` completes `auth-oauth2-migration`, Village marks `payment-stripe-integration` as ready. The `service-payment/` Village will then queue it.

---

## Task Naming Convention

Use consistent prefixes for service-specific tasks:

```bash
# Auth service tasks
village tasks create "auth: OAuth2 migration"
village tasks create "auth: Add rate limiting"

# Payment service tasks
village tasks create "payment: Stripe integration"
village tasks create "payment: Webhook refactor"

# Inventory service tasks
village tasks create "inventory: Stock tracking optimization"
village tasks create "inventory: Low-stock alerts"
```

---

## Example Task DAG

Here's a realistic task DAG for adding payment processing across services:

```bash
# In shared-tasks/

# 1. Auth service work
village tasks create "auth: Add payment user role" --depends-on village-setup
village tasks create "auth: Add payment scopes" --depends-on auth-payment-role

# 2. Payment service work
village tasks create "payment: Add Stripe integration" --depends-on auth-payment-scopes
village tasks create "payment: Add webhook handler" --depends-on payment-stripe

# 3. Inventory service work
village tasks create "inventory: Add stock reservation" --depends-on payment-webhook
village tasks create "inventory: Add payment confirmation" --depends-on inventory-reservation
```

Now queue tasks in each service:
```bash
# service-auth/
village queue --n 2

# service-payment/
village queue --n 2

# service-inventory/
village queue --n 2
```

Tasks will execute in dependency order across services.

---

## Customization

### Adding a New Service

To add a `notification` service:

**1. Create service repository:**
```bash
mkdir service-notification
cd service-notification
git init
village up
```

**2. Create `.village/config`:**
```ini
[DEFAULT]
DEFAULT_AGENT=notification
SCM=git
MAX_WORKERS=2

[agent.notification]
opencode_args=--mode patch
contract=contracts/notification.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
```

**3. Create notification tasks in shared DAG:**
```bash
cd /path/to/shared-tasks
village tasks create "notification: Add payment success email" --depends-on payment-webhook
village tasks create "notification: Add payment failure alert" --depends-on payment-webhook
```

### Changing Concurrency Per Service

Adjust `MAX_WORKERS` per service based on resource constraints:

```ini
# service-payment/ might handle fewer concurrent tasks
[DEFAULT]
MAX_WORKERS=1  # Payment service is critical, limit concurrency

# service-inventory/ might handle more
[DEFAULT]
MAX_WORKERS=5  # Inventory service can handle more parallel work
```

---

## Troubleshooting

**Issue: Tasks not showing as ready in specific service**

**Fix:** Verify task DAG is accessible:
```bash
# Check can see tasks
village tasks list

# Verify dependencies are met
village tasks show <task-id>
```

**Issue: Cross-service dependencies not working**

**Fix:** Ensure all services reference the same shared-tasks repository:
```bash
# In each service, check task directory
ls -la .village/

# Verify VILLAGE_TASKS_DIR or symlink is correct
ls -la .village-tasks
```

**Issue: Tasks starting but completing immediately**

**Fix:** Check that contracts exist and are valid:
```bash
# In each service, verify contracts
ls -la contracts/
cat contracts/auth.md
```

---

## Next Steps

- See [docs/examples/02-configuration/custom-agent.md](../examples/02-configuration/custom-agent.md) for detailed agent customization
- See [docs/examples/04-configuration/multiple-agents.md](../examples/04-configuration/multiple-agents.md) for advanced multi-agent workflows
- See [docs/examples/05-advanced/workflow.md](../examples/05-advanced/workflow.md) for handling interrupts and recovery

---

## Alternative: Distributed Task DAG

If you prefer not to have a centralized `shared-tasks/` repository, you can use cross-repo references:

```bash
# In service-auth/
village tasks create "auth: OAuth2 migration"

# In service-payment/ (reference auth task)
village tasks create "payment: Stripe integration" --depends-on auth-oauth2-migration@../service-auth
```

This requires the task store to support cross-repo dependencies. Check Village documentation for setup instructions.

