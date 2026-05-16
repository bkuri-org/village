---
id: note-011
tags: [proposals]
created: 2026-05-10T09:33:09.559722+00:00
source: docs/PROPOSALS.md
---

# PROPOSALS

# Village - Optional Extensions (Proposals)

## Status: Draft

This document defines where optional extensions provide clear value without compromising Village's core guarantees. All features are organized by ROI (Return on Investment) to help prioritize development efforts.

**Important**: All features in this document are **optional** and **out of scope** for v1.0. This is a proposal catalog for future consideration, not a commitment to implement.

---

## Evaluation Framework

Each proposal includes:
- **Problem**: What user pain does it solve?
- **Solution**: How would it work?
- **Value**: What benefits does it provide?
- **Effort**: How long to implement?
- **Use Cases**: When would it be useful?
- **Risks**: What could go wrong?
- **Alternatives**: What else could solve this?
- **Dependencies**: What systems would need to integrate with?

**ROI Calculation**: Value ÷ Effort (rough estimate)

---

## Tier 1: High ROI (High Value, Low/Medium Effort)

### Proposal: GitHub Integration

**Problem**:
- Manual PR descriptions are time-consuming
- No consistency in PR format across team
- PR status doesn't sync with village tasks completion
- Manual labeling and organization

**Solution**:
Automate GitHub PR workflows via Village. Provide bidirectional sync between village tasks and GitHub PRs.

**Proposal**:
```bash
# Generate PR description from task + git diff
village pr describe <task-id>

# Sync PR status with village tasks
village pr sync --from-tasks
```

**Value**:
- **Huge time savings**: Automates repetitive PR documentation
- **Consistent PR quality**: Standard format across all PRs
- **Better review process**: Automatic testing checklists, linked to tasks
- **Status visibility**: PRs reflect village tasks completion status

**Effort**: Medium (12-16 hours)

**Use Cases**:
- Generate PR description from task metadata + git diff
- Include testing checklist from task success criteria
- Link PR to related village tasks
- Sync PR status (open, merged) back to village tasks
- Add PR labels based on task metadata (scope, agent, tags)

**Integration Points**:
- GitHub CLI for PR creation and status queries
- village tasks data extraction
- Git diff parsing in worktrees
- Village task completion events (from event log)

**Risks**:
- GitHub API rate limiting
- GitHub API changes require updates
- PR description quality depends on task metadata completeness
- Need to handle authentication (GitHub tokens)

**Alternatives**:
- Manual PR creation (current approach)
- Existing PR description tools (e.g., GitHub CLI templates)
- Custom scripts (less integrated)

**Dependencies**:
- GitHub CLI (gh) installed and configured
- GitHub PAT/token for API access
- village tasks with proper metadata

---

### Proposal: CI/CD Hooks

**Problem**:
- Manual build triggering after task completion
- No automatic status updates when builds fail
- Delayed feedback on broken code
- Manual blocking of dependent tasks

**Solution**:
Trigger CI/CD builds automatically when tasks complete and sync build status back to village tasks.

**Proposal**:
```bash
# Configuration (in .village/config or environment)
[ci.github_actions]
enabled=true
trigger_on_task_complete=true
notify_on_failure=true
blocking_on_failure=true

# Village automatically triggers on task completion
```

**Value**:
- **Catches regressions early**: Immediate build execution on task completion
- **Prevents merging broken code**: Build failures block dependent tasks
- **Faster feedback loop**: Build status visible in Village
- **Automated workflow**: No manual build triggering

**Effort**: Medium (12-16 hours)

**Use Cases**:
- Trigger GitHub Actions build when task completes
- Trigger GitLab CI/CD pipeline on task completion
- Trigger Jenkins job on task completion
- Sync build status (success/failure) to village tasks
- Block dependent tasks on build failure
- Send notifications on build failure

**Integration Points**:
- Village task completion events (event log)
- GitHub Actions API / GitLab CI API / Jenkins API
- village tasks status update (to mark as blocked)
- Notification systems (Slack, Discord, Email)

**Risks**:
- CI/CD configuration complexity (different CI systems)
- Build failures require manual intervention to unblock
- API rate limits (GitHub Actions, GitLab, Jenkins)
- Authentication management (tokens, keys)

**Alternatives**:
- Manual build triggering (current approach)
- Webhook-based CI triggers (custom infrastructure)
- Cron-based build schedules
- CI/CD plugins (less integrated)

**Dependencies**:
- GitHub Actions / GitLab CI / Jenkins API access
- Village event log hooking system
- village tasks status update capability
- Notification system (optional)

---

### Proposal: Notification Systems

**Problem**:
- No awareness of task failures or critical events
- Need to manually check logs for issues
- Slow incident response time
- No proactive alerts on system problems

**Solution**:
Webhook-based notification system for critical events (task failures, orphan detection, high-priority task completion).

**Proposal**:
```bash
# Configuration (in .village/config)
[notifications.slack]
enabled=true
webhook_url=https://hooks.slack.com/services/...
events=task_failed,orphan_detected,high_priority_task,queue_stalled

[notifications.email]
enabled=false
address=team@example.com
events=task_failed
```

**Value**:
- **Faster incident response**: Immediate awareness of failures
- **Better visibility**: Proactive alerts on critical events
- **Reduced manual monitoring**: No need to check logs constantly
- **Team coordination**: All team members see same notifications

**Effort**: Low (8-12 hours)

**Use Cases**:
- Alert on task failure (with error details)
- Alert on orphan detection (worktrees without locks)
- Alert when queue is stalled (no tasks running)
- Alert on high-priority task completion
- Alert on system anomalies (stale locks, resource exhaustion)

**Integration Points**:
- Village event log hooking system
- Webhook POST requests (Slack, Discord, Email)
- Village status queries (to extract context)
- village tasks metadata (for alert details)

**Risks**:
- Notification service outages (Slack downtime, etc.)
- Webhook failures (rate limits, network issues)
- Spam risk (too many notifications)
- Alert fatigue (too sensitive)

**Alternatives**:
- Manual log monitoring (current approach)
- Terminal-based notifications (desktop notifications)
- Existing monitoring tools (Prometheus alerts, etc.)
- Village status commands (manual polling)

**Dependencies**:
- Webhook endpoints (Slack, Discord, Email)
- Village event log hooking system
- Network connectivity for webhook delivery

---

## Tier 2: Medium ROI (Medium Value, Medium Effort)

### Proposal: Advanced Scheduling Policies

**Problem**:
- FIFO scheduling doesn't optimize throughput
- No consideration for task priority or impact
- System resources may be underutilized or overloaded
- No fair-share balancing across agents

**Solution**:
Customizable scheduling policies for priority-based, resource-aware, and fair-share task selection.

**Proposal**:
```python
# Configuration (in .village/config or code)
[scheduler]
policy=default

# .village/scheduler.py
def should_schedule(task, active_workers, system_state):
    # Priority-based: High-impact tasks first
    if task.metadata.get("impact") == "high":
        return True, "high priority"
    
    # Resource-aware: Respect CPU/memory limits
    if system_state.load_average > 4.0:
        return False, "system overloaded"
    
    # Fair-share: Balance agent allocation
    agent_load = count_by_agent(active_workers)
    if agent_load.get(task.agent) >= system_state.max_workers:
        return False, "agent overloaded"
    
    return default_policy(task, active_workers, system_state)
```

**Value**:
- **Better resource utilization**: Optimal task ordering based on priority and resources
- **Faster task completion**: High-impact tasks get priority
- **System stability**: Resource-aware scheduling prevents overload
- **Fair allocation**: Balanced workload across agents

**Effort**: Medium (12-16 hours)

**Use Cases**:
- High-priority task steals STALE lock after shorter timeout
- Resource-aware scheduling (respect CPU/memory limits)
- Fair-share scheduling (prevent agent starvation)
- Dependency-aware scheduling (optimal DAG traversal)
- Custom policies per team or project

**Integration Points**:
- System load monitoring (psutil or similar)
- Task metadata (priority tags, impact labels)
- Extend `arbitrate_locks()` in queue.py
- Village config system for policy selection

**Risks**:
- Complexity in scheduling logic
- Tuning required for optimal performance
- Policy conflicts (priority vs fairness trade-offs)
- Resource monitoring inaccuracies

**Alternatives**:
- Manual task prioritization (current approach)
- External schedulers (less integrated)
- Fixed task ordering (no flexibility)
- Single worker (no coordination needed)

**Dependencies**:
- System load monitoring (psutil, htop, etc.)
- Task metadata enriched with priority/impact
- village tasks with priority fields

---

### Proposal: PR Description Generator

**Problem**:
- Inconsistent PR descriptions across team
- Manual PR documentation is time-consuming
- Missing testing checklists in PRs
- PRs don't link back to village tasks

**Solution**:
Automatically generate PR descriptions from task metadata and git diff.

**Proposal**:
```bash
village pr describe <task-id>
> [Extracts task metadata from village tasks]
> [Analyzes git diff in worktree]
> [Generates PR description with:]
>   - Summary (from task title/description)
>   - Changes (git diff summary)
>   - Testing checklist (from task success criteria)
>   - Related tasks (from village tasks dependencies)
```

**Value**:
- **Improved PR quality**: Consistent format, complete information
- **Faster PR submission**: Auto-generated, just review and submit
- **Better review process**: Testing checklist ensures quality
- **Traceability**: Links PR back to village tasks

**Effort**: Low (8-12 hours)

**Use Cases**:
- Generate PR description for completed task
- Include testing checklist based on task success criteria
- Link to related village tasks (dependencies)
- Format: Summary, Changes, Checklist, Related Issues
- Output to stdout (to paste into PR form) or create PR directly

**Integration Points**:
- village tasks data extraction
- Git diff parsing in worktrees
- Markdown formatting for PR description
- GitHub CLI (optional, for direct PR creation)

**Risks**:
- Template quality (generic descriptions)
- Context limitations (git diff alone may miss details)
- Task metadata completeness (requires good task definitions)
- Formatting inconsistencies (different PR requirements)

**Alternatives**:
- Manual PR descriptions (current approach)
- GitHub PR templates (repository-level)
- Existing PR description tools (e.g., release-drafter)
- AI-powered PR descriptions (less integrated)

**Dependencies**:
- village tasks with proper metadata
- Git worktree for task
- Village event log (to know task completed)

---

### Proposal: Multi-Repo Coordination

**Problem**:
- Coordinating tasks across microservices/monorepos is manual
- No unified view of cross-repo dependencies
- Separate Village instances per repo (fragmented coordination)
- Cross-repo task dependencies are manual

**Solution**:
Configurable multi-repo support with shared lock state and unified task routing.

**Proposal**:
```ini
# .village/config
[repo.backend]
path=../backend
agent=backend-build
scm=git

[repo.frontend]
path=../frontend
agent=frontend-build
scm=git

# Commands
village queue --repo backend --n 3
village queue --repo frontend --n 2
village status --repos
```

**Value**:
- **Unified coordination**: Single view across all repositories
- **Cross-repo task routing**: Automatic routing to correct repo
- **Shared lock state**: No duplicate work across repos
- **Microservices support**: Essential for multi-service architectures

**Effort**: High (20-24 hours)

**Use Cases**:
- Queue tasks for backend and frontend simultaneously
- Status view across all repositories
- Cross-repo dependencies (frontend task depends on backend task)
- Different SCM per repo (Git for backend, jj for frontend)
- Shared configuration (max_workers, policies)

**Integration Points**:
- Config parser (multi-repo support)
- Path resolution (relative paths from config)
- Worktree isolation per repo (`.worktrees/backend/bd-a3f8/`)
- Lock state (shared across repos or per-repo)
- Queue scheduler (repo-aware routing)

**Risks**:
- Complex state management across repos
- Path resolution ambiguity (relative vs absolute)
- Worktree isolation conflicts (same task ID in multiple repos)
- Configuration complexity
- village tasks routing (cross-repo dependencies)

**Alternatives**:
- Separate Village instances per repo (current approach)
- Manual cross-repo coordination
- Monorepo with single Village instance
- External coordination tools (less integrated)

**Dependencies**:
- village tasks with repo metadata (labels, custom fields)
- Path resolution for multiple repositories
- Per-repo SCM backend (Git, jj, etc.)
- Unified lock state or isolated per-repo locks

---

## Tier 3: Low ROI (Low Value or High Effort)

### Proposal: Resource Quotas

**Problem**:
- No enforcement of resource limits (CPU, memory, disk)
- Resource exhaustion under high load
- Tasks may compete for resources unpredictably
- No visibility into resource usage

**Solution**:
Enforce resource quotas per agent (CPU, memory, disk) with pre-flight checks.

**Proposal**:
```ini
# .village/config
[resources]
max_cpu=4.0
max_memory_gb=16
max_disk_gb=50

[agent.build]
quota_cpu=2.0
quota_memory_gb=8
quota_disk_gb=20
```

**Value**:
- **Production reliability**: Prevents resource exhaustion
- **Stable performance**: Predictable resource allocation
- **Fair resource distribution**: Quotas prevent resource hogging
- **Capacity planning**: Clear limits enable better forecasting

**Effort**: High (16-20 hours)

**Use Cases**:
- CPU limits per agent (prevent CPU starvation)
- Memory limits per agent (prevent OOM kills)
- Disk limits per task (prevent disk exhaustion)
- Pre-flight checks before claiming tasks
- Resource-aware scheduling (respect quotas)

**Integration Points**:
- System load monitoring (psutil, /proc/loadavg)
- Memory monitoring (psutil, /proc/meminfo)
- Disk usage monitoring (psutil, df)
- Extend `arbitrate_locks()` in queue.py (quota checks)

**Risks**:
- Monitoring inaccuracies (resource reporting errors)
- Quota tuning complexity (optimal values differ per workload)
- False positives (prevent valid work due to quota)
- Resource monitoring overhead (performance impact)

**Alternatives**:
- External resource limits (cgroups, containers)
- Manual resource management
- System-level resource quotas (OS-level)
- No resource limits (current approach, accept exhaustion risk)

**Dependencies**:
- Resource monitoring tools (psutil, /proc)
- Village config system for quota definitions
- System access for resource queries

---

### Proposal: Dynamic DAG Re-evaluation

**Problem**:
- Stale village tasks DAG state may cause incorrect scheduling
- Static DAG queries don't reflect runtime changes
- Manual village tasks updates required when DAG changes
- Dependencies may be outdated

**Solution**:
Re-calculate task readiness at queue time by querying village tasks DAG and resolving dependencies dynamically.

**Proposal**:
```python
# village/dag_reeval.py
def generate_queue_plan(session_name, max_workers):
    # Re-evaluate dependencies (village tasks might be stale)
    tasks = get_tasks_ready()
    
    for task in tasks:
        dependencies = get_task_dependencies(task.id)
        if not all_dependencies_satisfied(dependencies):
            tasks.remove(task)
    
    return tasks

# village tasks sync
village sync --to-tasks
```

**Value**:
- **Marginal improvement**: Current village tasks integration works well
- **Runtime correctness**: Always uses latest DAG state
- **Reduced manual work**: No need to manually refresh village tasks
- **Dependency accuracy**: Correct task ordering based on current state

**Effort**: High (16-20 hours)

**Use Cases**:
- Re-calculate readiness at queue time
- Detect stale village tasks DAG state
- Optimize task ordering based on current dependencies
- Sync Village lock status back to village tasks
- Update task statuses (CLAIMED, IN_PROGRESS, FAILED) in village tasks

**Integration Points**:
- village tasks DAG API (tasks, dependencies, status)
- Village queue scheduler (dynamic re-evaluation)
- village tasks status update API
- Village event log (sync events to village tasks)

**Risks**:
- village tasks API changes require updates
- Performance impact (DAG queries can be expensive)
- Complex dependency resolution logic
- Stale data caching (if queries are too frequent)

**Alternatives**:
- Static village tasks DAG queries (current approach)
- Manual village tasks refresh (when DAG changes)
- External task management (less integrated)
- Cached DAG with manual invalidation

**Dependencies**:
- village tasks DAG API access
- village tasks status update API
- village tasks CLI installed and configured

---

## Experimental / Future (Very Low ROI or High Effort)

### Proposal: Remote Tmux Sessions

**Problem**:
- Scaling beyond single machine is manual
- Distributed teams need shared coordination
- Resource scaling requires multiple machines
- No unified view across distributed workers

**Solution**:
SSH-based remote tmux session management for distributed Village across multiple machines.

**Proposal**:
```bash
# Configuration
village up --session=user@server:village
village queue --session=user@server:village --n 3
village status --session=user@server:village
```

**Value**:
- **Niche use case**: Distributed teams, resource scaling
- **Resource scaling**: Utilize multiple machines
- **Team coordination**: Unified view across distributed workers
- **Remote development**: Development on remote servers

**Effort**: Very High (32-40 hours)

**Use Cases**:
- Coordinate agents on multiple servers
- Run resource-intensive tasks on dedicated machines
- Distributed team collaboration
- Remote resource monitoring
- Cross-machine task scheduling

**Integration Points**:
- SSH key management
- Remote tmux session control (SSH tmux)
- Network reliability (SSH connection resilience)
- Remote command execution
- Distributed lock state (shared across machines)

**Risks**:
- **Network failures**: SSH connection drops break coordination
- **SSH security**: Key management, access control
- **Complexity**: Distributed state management, network partitions
- **Latency**: Remote commands slower than local
- **Debugging complexity**: Harder to debug distributed issues

**Alternatives**:
- Separate Village instance per machine (current approach)
- Containerized workers (Docker, Kubernetes)
- Cloud-based CI/CD (GitHub Actions, etc.)
- Manual coordination across machines

**Dependencies**:
- SSH access to remote machines
- tmux installed on remote machines
- Village installed on remote machines
- Network connectivity between machines

**Note**: This is explicitly **non-goal** for v1-v2. Consider only if strong user demand exists.

---

### Proposal: Fabric Integration (Task Drafting, Summaries)

**Problem**:
- Manual task definition is slow
- Slow documentation updates
- No AI-powered task creation
- Project summaries require manual effort

**Solution**:
LLM-powered task drafting, project summaries, and decision extraction via Fabric integration.

**Proposal**:
```bash
# Task drafting (already partially in village chat)
village chat --create
> [Fabric analyzes codebase, asks clarifying questions]
> [Human refines scope, success criteria, dependencies]
> /submit

# Project summaries
village chat --digest
> [Fabric reviews conversation history]
> [Generates project overview, blockers, decisions]
> [Writes to .village/context/summary.md]
```

**Value**:
- **Convenience improvement**: Faster task creation and documentation
- **LLM-powered analysis**: Codebase understanding, insights
- **Quality improvements**: Better task definitions, consistent summaries
- **Productivity boost**: Less manual work, more focus on code

**Effort**: Medium (12-16 hours)

**Use Cases**:
- Draft tasks with LLM assistance
- Generate project summaries from conversation history
- Extract decisions and constraints
- Analyze codebase for context
- Automate documentation updates

**Integration Points**:
- Fabric CLI installed and configured
- Village chat interface (already supports conversational LLM)
- village tasks creation API
- Village context file management

**Risks**:
- **Fabric dependency**: External tool requirement
- **LLM variability**: Inconsistent outputs
- **Context limitations**: Fabric may not have full context
- **API costs**: Fabric LLM usage may incur costs
- **Fabric changes**: Updates to Fabric require Village updates

**Alternatives**:
- Manual task creation (current approach)
- Village chat without Fabric (current, but less powerful)
- AI-powered IDE features (Copilot, Codeium)
- LLM web interfaces (ChatGPT, Claude)

**Dependencies**:
- Fabric CLI installed
- Fabric configured with prompts
- LLM API keys for Fabric
- Village chat interface (LLM client)

**Note**: This is **experimental** and depends on external tool (Fabric) availability.

---

### Proposal: Release Notes Generation

**Problem**:
- Manual release documentation is time-consuming
- Inconsistent release note formats
- Missing links to tasks and changes
- No categorization (features, fixes, breaking changes)

**Solution**:
Automatically generate release notes from completed village tasks and git history.

**Proposal**:
```bash
village release notes v1.0.0 v0.9.0
> [Fabric extracts completed tasks in range]
> [Fabric groups by type/impact]
> [Generates markdown release notes]
```

**Value**:
- **Nice convenience**: Faster release preparation
- **Consistent format**: Standard release note structure
- **Task linkage**: Links to village tasks and changes
- **Categorization**: Features, fixes, breaking changes

**Effort**: Low (8-12 hours)

**Use Cases**:
- Generate release notes between version tags
- Group tasks by type (features, fixes, breaking changes)
- Include links to tasks and git changes
- Output to markdown (to paste in release)
- Optional: Create release directly (GitHub Releases, GitLab Releases)

**Integration Points**:
- village tasks data (completed tasks in range)
- Git history between version tags
- Markdown formatting for release notes
- Optional GitHub/GitLab Releases API

**Risks**:
- **Template quality**: Generic release notes
- **Context limitations**: Tasks + git diff may miss details
- **Categorization errors**: Wrong classification of changes
- **Formatting inconsistencies**: Different release requirements

**Alternatives**:
- Manual release notes (current approach)
- GitHub Releases UI (manual entry)
- Release notes tools (release-drafter, etc.)
- AI-powered release notes (less integrated)

**Dependencies**:
- village tasks with version tags
- Git history between tags
- Village event log (to determine task completion)
- Optional: Fabric for intelligent summarization

**Note**: This is **experimental** and low-priority (nice-to-have, not essential).

---

## Proposal Evaluation Framework (For Future Consideration)

When evaluating proposals for implementation, consider:

### ROI Alignment
- Does it solve real user pain?
- Is implementation cost justified?
- Can it be done simply?
- High, Medium, or Low ROI?

### Safety Guarantee
- Can it violate Village's core principles?
- Does it introduce hidden state?
- Is it transparent and inspectable?
- Can Village work without it?

### Optional Nature
- Can Village work without it?
- Is it opt-in?
- Does it increase complexity for non-users?
- Are scope boundaries clear?

### Maintainability
- Does it bloat the codebase?
- Is it well-scoped?
- Can it be tested independently?
- Clear separation of concerns?

### User Control
- Does the human remain in control?
- Can outputs be reviewed/edited?
- Is invocation explicit?
- Configurable behavior?

---

## Summary

Village's core value is **coordination infrastructure** with audit trails, safety guarantees, and production reliability. Optional extensions may enhance productivity but must never compromise Village's core guarantees:

- Village remains the scheduler
- Humans remain in control
- State remains file-based and inspectable
- No magic, no hidden processes, no side effects

When in doubt, keep it simple. A small, reliable coordination tool is better than a complex, feature-rich one.

**Current Status**: Village v0.2.3 (Jujutsu support complete)
**Next Target**: v0.3.0 (Safety & Coordination - Essential)
**Production Goal**: v1.0.0 (Production-ready coordination layer)

