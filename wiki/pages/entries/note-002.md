---
id: note-002
tags: [agents]
created: 2026-05-10T08:15:21.328944+00:00
source: AGENTS.md
---

# AGENTS

# Village - Agent Development Guide

For command references, configuration, architecture, and quickstart guides, see [README.md](README.md).

## Build, Lint, and Test Commands

```bash
uv sync                                  # Install dependencies
uv run village <command>                 # Run CLI during development
uv run ruff check .                      # Lint
uv run ruff check --fix .                # Auto-fix lint issues
uv run ruff format .                     # Format
uv run mypy village/                     # Type check
uv run pytest                            # All tests
uv run pytest tests/test_module.py       # Single file
uv run pytest tests/test_module.py::test # Single test
uv run pytest -k "test_lock_"            # Pattern match
uv run pytest --cov=village              # With coverage
```

## Code Style Guidelines

### General Principles
- **Explicit over implicit** - no magic, side effects, or hidden state
- **Truth over intention** - use authoritative handles (tmux pane IDs, file paths)
- **One source of truth** - probe actual state, don't cache
- **Safe by default** - plan/dry-run before mutations
- **Everything inspectable** - plain text, JSON contracts, shell access

### Imports and Formatting
- Group: stdlib → third-party → local imports
- Use `ruff` for all formatting
- Avoid wildcard imports
- Sort with `isort`-compatible ordering (ruff handles this)

### Type Hints
- Use modern syntax (`|` for unions, not `Union`)
- Type all params and returns
- Use `dataclasses` for structured data
- Avoid `Any` - prefer `Unknown` or specific types

### Naming Conventions
- **Files**: `snake_case.py` - `lock_manager.py`, `tmux_probe.py`
- **Classes**: `PascalCase` - `LockManager`, `TmuxProbe`
- **Functions/Variables**: `snake_case` - `get_pane_id()`, `is_active`
- **Constants**: `UPPER_SNAKE_CASE` - `VILLAGE_DIR`, `LOCK_FILE_PATTERN`
- **Private**: `_leading_underscore` - `_parse_pane_id()`
- **CLI options**: `kebab-case` - `--dry-run`, `--detached`

### Error Handling
- Define specific exception types
- Include context in messages (IDs, paths, pane IDs)
- Never catch `Exception` broadly
- Use `click.ClickException` for CLI errors
- Use `sys.exit(code)` for fatal errors

### CLI Structure (Click)
- Use `click` decorators
- Default to plan/dry-run for ambiguous commands
- Explicit commands act immediately
- Use `click.echo()` never `print()`
- Support `--json` flag where appropriate

### File I/O
- Use `pathlib.Path` exclusively
- Prefer atomic operations for lock/state files
- Specify `encoding='utf-8'` for text files
- Keep state as plain text (INI, JSON, key=value)

### Subprocess Execution
- Use `subprocess.run()` for sync commands
- Use `subprocess.Popen()` for long-running processes
- Always check `returncode`
- Use list form for safety (no shell injection)

### JSON Contracts
- Define TypedDict or dataclasses for contracts
- Version schemas (top-level `"version": 1`)
- Use `sort_keys=True` for stable output
- No ANSI codes in `--json` output

### Testing
- Use `pytest` with `tmp_path` fixture
- Test both success and failure paths
- Keep tests focused and independent

## Landing the Plane (Session Completion)

**When ending a work session in a Village-created project**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Evaluate version impact** - Review your changes and apply bump label:
   ```bash
   village tasks label <task-id> add bump:<type>
   ```

   | Type   | When to use                          |
   |--------|--------------------------------------|
   | major  | Breaking changes, API removal        |
   | minor  | New features, backwards-compatible   |
   | patch  | Bug fixes, small improvements        |
   | none   | Docs, tests, internal refactors      |

   Default mapping from scope: fix→patch, feature→minor, others→none.
   Override with explicit label if actual impact differs.

   **ENFORCEMENT**: `village builder arrange` will BLOCK if any closed task has no bump label.
   Every task — including docs-only changes — MUST have a bump label before release.
   Use `bump:none` for tasks with no version impact. Use `--force` only in emergencies.
5. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
6. **Clean up** - Clear stashes, prune remote branches
7. **Verify** - All changes committed AND pushed
8. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Task Tracking

Village uses the built-in task store for issue tracking. See [Task Management](README.md#task-management) for CLI commands.

> **IMPORTANT**: This project uses the built-in **Village task store** for ALL issue tracking in Village-created projects. Do NOT use markdown TODOs, task lists, or external trackers.

**Statuses**: `open` (ready), `draft` (needs definition), `in_progress` (claimed), `done` (pending arrange), `closed` (released), `deferred` (blocked)

**Types**: `bug`, `feature`, `task` (tests/docs/refactor), `epic` (large feature with subtasks), `chore` (maintenance)

**Priorities**: 0 (critical), 1 (high), 2 (medium/default), 3 (low), 4 (backlog)

### Workflow for AI Agents

1. **Check ready work**: `village tasks ready` shows unblocked tasks
2. **Claim your task**: `village tasks update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked task:
   - `village tasks create "Found bug" --description="..." --depends-on <parent-id>`
5. **Complete**: `village tasks close <id> --reason "Done"`

### Important Rules

- ✅ Use `village tasks` for ALL issue tracking
- ✅ Always use `--json` for programmatic output
- ✅ Link discovered work with `--depends-on`
- ✅ Check `village tasks ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

## Village Development (Beads)

For Village's own development (this repo), use **bd (Beads)** instead:

> **IMPORTANT**: This is Village's own development repo. Use **bd** for issue tracking.

**Setup** (if not already initialized):
```bash
bd init
bd onboard
```

**Quick Start:**
```bash
bd ready                    # Show ready tasks
bd create "Title" -t bug      # Create new task
bd update <id> --claim      # Claim a task
bd close <id> --reason "Done"  # Complete work
```

**Important Rules:**
- ✅ Use bd for ALL task tracking in Village development
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT use village tasks for this repo

## Changelog Management

See [Release Automation](README.md#release-automation) for the release process (`village builder arrange`).

When completing a task:
1. **Apply bump label**: `village tasks label <task-id> add bump:<type>` (major/minor/patch/none)
2. **Ensure task title is clear and user-facing** (will appear in changelog)
   - ✅ "Add retry logic to queue processing"
   - ✅ "Fix deadlock in lock acquisition"
   - ❌ "Refactor _internal_helper function"
3. **Close task**: `village tasks close <task-id> --reason "Completed"`

Changes are auto-categorized by task type: feature→Added, bug→Fixed, task/chore→Changed, bump:major→Breaking. bump:none tasks are excluded from the changelog.

