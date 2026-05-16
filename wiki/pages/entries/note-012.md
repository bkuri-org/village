---
id: note-012
tags: [execution-engine]
created: 2026-05-10T09:33:10.687041+00:00
source: docs/execution-engine.md
---

# execution-engine

# Execution Engine

The execution engine sits between AI agents and the filesystem. It classifies each
proposed action into a security tier, validates it against policy rules, and only
executes approved actions.

```
Agent proposes actions -> Engine validates -> Engine executes approved -> Agent observes results
```

## Prerequisites

- **PPC** (hard dependency) — compiles behavioral prompts for agent contracts.
  Install: https://github.com/bkuri/ppc. PPC must be available on `PATH`.

## Four-Layer Defense

### Layer 1: Contract integration (agent instructions)

PPC compiles behavioral constraints (base prompt + modes + traits + policies +
contracts + guardrails) into the agent's system prompt. Village then appends
village-specific sections: the execution_enforcement guardrail, the PlanProtocol
section, and goal context. Agents learn the rules before they start working.

### Layer 2: Execution engine (runtime validation)

All agent actions must pass through the engine as structured `<plan>` proposals.

1. Classify each action into a security tier
2. Validate against rules and manifests
3. Execute with resource limits and a sanitized environment
4. Scan the result for content violations

### Layer 3: Post-hoc verification (completion gate)

After the agent signals DONE, the engine runs final checks before marking the spec
complete:

- No forbidden patterns in new or modified files
- New files match the configured casing
- Test files exist for new source files

If verification fails, violations are written as "Inspect Notes" in the spec file
so the agent can fix them on retry.

### Layer 4: Remote CI (push-time enforcement)

Optional CI workflows validate that each role's commits only touch allowed paths.

## Tier Classification

| Tier | Name | Auto | Examples |
|------|------|------|----------|
| 0 | READ_ONLY | Yes | `cat`, `ls`, `grep`, `git log`, `git diff`, `git status` |
| 1 | SAFE_WRITE | Yes | `mkdir`, `pytest`, `ruff`, `touch`, `cp`, `mv` |
| 2 | DESTRUCTIVE | In manifest | `rm file`, `git reset`, `pip install`, `git push` |
| 3 | DANGEROUS | Never | `rm -rf`, `git push --force`, `chmod 777`, `sudo`, `chown` |

### Classification details

- **Executable resolution**: strips path prefixes (`/bin/rm` becomes `rm`).
- **Git subcommands**: `log/diff/status` are Tier 0; `add/commit` are Tier 1;
  `reset/push` are Tier 2; `push --force` is Tier 3.
- **Shell metacharacters**: any command with `$()`, backticks, `&&`, `||`, or `;` is
  elevated to at least Tier 2.
- **Pipe-to-shell**: commands piping to `sh`, `bash`, or `zsh` are elevated to Tier 3.

## Attack Vector Protection

| Vector | Protection |
|--------|------------|
| Config tampering | Builder reads from frozen git commit, not filesystem |
| Script injection | Content scanner blocks `subprocess.run`, `os.system`, `eval`, `exec` |
| Shell metacharacters | `shlex` parsing blocks `$()`, backticks, `&&`, `\|\|`, `;` |
| Symlink escape | `Path.resolve()` on every boundary check |
| Race conditions | Commit-time validation snapshots content at commit moment |
| Environment injection | Strips `SSH_AUTH_SOCK`, `PYTHONPATH`, `LD_PRELOAD`, `GIT_DIR` per command |
| Nested repo bypass | `git clone` is classified as Tier 2 minimum |
| Resource exhaustion | `setrlimit` on CPU, memory, file size, processes + wall-clock timeout |

## Contract Generation

Spec-driven contracts are built in a pipeline:

1. **PPC compilation** — PPC compiles the behavioral prompt from base prompt,
   modes, traits, policies, contracts, and guardrails.
2. **Dynamic variables** — Village passes `--var key=value` flags to PPC with
   runtime context (`spec_name`, `worktree_path`, `git_root`, `window_name`,
   `spec_content`).
3. **Policy loading** — Village passes `--policies spec_context` so PPC can
   include project-specific policy sections.
4. **execution_enforcement guardrail** — Village appends its own guardrail
   (from `village/guardrails/execution_enforcement.md`) after PPC output.
5. **PlanProtocol section** — Village appends the `<plan>`/`<executed>` protocol
   instructions.
6. **Goal context** — Village appends the current objective from `GOALS.md` if
   available.

For task-driven (non-spec) contracts, the pipeline is similar but omits steps
2–3 and 5 (no spec variables, no PlanProtocol).

## Modules

| Module | Class | Purpose |
|--------|-------|---------|
| `tiers.py` | `TierClassifier` | Classifies commands into security tiers |
| `validator.py` | `CommandValidator` | Validates actions against rules and manifests |
| `scanner.py` | `ContentScanner` | Scans files for pattern, filename, and TDD violations |
| `commit.py` | `CommitEngine` | Creates tamper-proof commits using low-level git plumbing |
| `env.py` | `EnvironmentSanitizer` | Builds a minimal, predictable execution environment |
| `paths.py` | `PathPolicy` | Path-based access control with symlink detection |
| `resources.py` | `ResourceGuard` | OS-level resource enforcement (CPU, memory, timeout) |
| `refs.py` | `freeze_build_commit`, `git_show` | Config freezing and reads from git objects |
| `manifest.py` | `ManifestStore`, `ApprovalManifest` | Per-spec approval manifests loaded from git |
| `verify.py` | `run_verification` | Post-hoc verification after agent signals completion |
| `protocol.py` | `PlanProtocol` | `<plan>`/`<executed>` protocol between agent and engine |
| `engine.py` | `ExecutionEngine` | Top-level pipeline: classify, validate, execute, scan |

## Configuration

### `.village/rules.yaml`

Global policy rules loaded at build start and read from the frozen git commit. Supports:

- `content_rules`: forbidden patterns (literal or regex) with optional path scoping
- `command_rules`: forbidden commands with flag, subcommand, and pipe-to checks
- `filename`: casing enforcement (`snake_case`, `kebab-case`, `camelCase`)
- `tdd`: test-driven development enforcement
- `guardrails`: list of PPC guardrail module names to include in contracts

PPC guardrails (configured via `guardrails` in `rules.yaml`) are compiled by PPC
into the agent's system prompt. Village also appends its own
`execution_enforcement` guardrail (`village/guardrails/execution_enforcement.md`)
which is village-specific and lives outside PPC.

### `.village/agents.yaml`

Per-role git identities and allowed paths. Each role maps to a git user/email and
a set of allowed path patterns.

### `.village/approvals/<spec-id>.yaml`

Per-spec command and script whitelists. Read from git objects during a build, never from
the filesystem:

```yaml
version: 1
spec_id: my-feature
allowed_commands:
  - pytest
  - ruff
  - git add
allowed_scripts:
  - build.py
allowed_paths:
  - src/**
  - tests/**
test_required: true
filename_casing: snake_case
```

## PPC Integration

PPC is invoked as a subprocess with the following flags:

- **`--var key=value`** — Pass dynamic variables (e.g., `spec_name`, `worktree_path`).
  Multiple `--var` flags can be supplied.
- **`--policies spec_context`** — Include project-specific policy sections in the
  compiled prompt.
- **`--guardrails mod1,mod2`** — Include named PPC guardrail modules from
  `rules.yaml`.

If PPC is not on `PATH`, contract generation fails with an error message
including installation instructions.

## Protocol

Agents communicate with the execution engine using `<plan>`/`<executed>` markers:

### Proposal

The agent outputs a structured JSON plan:

```
<plan>
[
  {"action": "write", "path": "src/foo.py", "content": "print('hello')"},
  {"action": "bash", "command": "pytest tests/test_foo.py -v"}
]
</plan>
```

### Execution

The engine:
1. Parses the `<plan>` block
2. Classifies each action into a security tier
3. Validates against rules and manifests
4. Executes approved actions with resource limits
5. Returns results

### Response

The engine sends back structured results:

```
<executed>
[
  {"id": 0, "status": "ok"},
  {"id": 1, "status": "ok", "stdout": "1 passed in 0.5s"}
]
</executed>
```

The agent reads the results and continues. This repeats until the spec is complete.

### Supported action types

- **`write`**: Write content to a file (`path` + `content`)
- **`bash`**: Execute a command (`command` string)
- **`delete`**: Delete a file (`path`)
- **`read`**: Read a file (`path`) — auto-approved

## Key Design Decisions

### Git plumbing for commits

The `CommitEngine` uses low-level git commands (`hash-object`, `update-index`,
`write-tree`, `commit-tree`) instead of `git add`/`git commit`. This prevents race
conditions where an agent modifies a file between validation and commit — each file's
content is hashed at the exact moment of commit.

### Frozen config reads

At the start of each build, `freeze_build_commit()` captures the current HEAD commit
hash. All config reads during the build use `git_show()` to read from that commit
object — never from the filesystem. This makes config files tamper-proof: an agent
can write anything to `.village/rules.yaml` on disk, but the builder always reads the
original approved version from git.

### Sanitized environment

Every agent command executes in a minimal environment built from scratch. Known-dangerous
variables (`SSH_AUTH_SOCK`, `PYTHONPATH`, `LD_PRELOAD`, `GIT_DIR`) are stripped.
Environment injection is prevented because the parent process's environment is never
inherited directly.

### Resource limits

OS-level resource limits (`setrlimit`) are applied to every subprocess:
- **CPU time**: 5 minutes (soft limit)
- **Memory**: 4 GB (address space)
- **File size**: 1 GB
- **Processes**: 100 (prevents fork bombs)
- **Wall clock**: 1 hour (subprocess timeout)

These prevent resource exhaustion attacks from runaway agent commands.

## Example: Full Pipeline

```python
from pathlib import Path
from village.execution import ExecutionEngine
from village.execution.manifest import ManifestStore
from village.execution.refs import freeze_build_commit, git_show
from village.rules.loader import load_rules
from village.rules.schema import RulesConfig

# 1. Freeze config at build start
build_commit = freeze_build_commit(Path("/path/to/repo"))

# 2. Load rules from frozen commit (not filesystem!)
rules = load_rules(Path("/path/to/repo"), build_commit)

# 3. Create engine
engine = ExecutionEngine(rules=rules, worktree=Path("/path/to/repo"))

# 4. Agent proposes an action
action = {"type": "bash", "command": "pytest tests/"}

# 5. Load manifest from git (tamper-proof)
store = ManifestStore(Path("/path/to/repo/.village/approvals"))
manifest = store.load_from_git("my-spec", build_commit)

# 6. Execute through pipeline
result = engine.execute(
    worktree=Path("/path/to/repo"),
    action=action,
    manifest=manifest,
)
print(f"Status: {result.status}")
print(f"Stdout: {result.stdout[:500]}")
```

