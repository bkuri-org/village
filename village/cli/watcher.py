"""Village Watcher — observability and maintenance CLI commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from village.config import get_config
from village.errors import EXIT_BLOCKED, EXIT_ERROR
from village.probes.tmux import session_exists
from village.prompt import sync_prompt
from village.roles import run_role_chat
from village.scribe.store import ScribeStore
from village.status import collect_full_status, collect_workers
from village.trace import TraceReader, format_trace

if TYPE_CHECKING:
    from village.config import Config


def _find_wiki_path() -> Path:
    cwd = Path.cwd()
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current / "wiki"
        current = current.parent
    return cwd / "wiki"


@click.group(invoke_without_command=True)
@click.pass_context
def watcher_group(ctx: click.Context) -> None:
    """Observe and maintain village state."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("watcher")


@watcher_group.command()
@click.option("--short", is_flag=True, help="Short output")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--system", is_flag=True, help="Show workers, locks, and orphans")
@click.option("--task", "task_id", help="Show task state and history")
@click.option("--wiki", is_flag=True, help="Show wiki statistics")
def status(
    short: bool,
    json_output: bool,
    system: bool,
    task_id: str | None,
    wiki: bool,
) -> None:
    """
    Show village status.

    Non-mutating. Probes actual state, doesn't create directories.

    Flags:
      (no flags): General overview (high-level summary)
      --system: Workers, locks, and orphans
      --task <id>: Task state and history
      --wiki: Wiki statistics
      --short: Minimal status (tmux + locks count)
      --json: Full status as JSON
    """
    if task_id:
        from village.state_machine import TaskStateMachine

        config = get_config()
        state_machine = TaskStateMachine(config)

        current_state = state_machine.get_state(task_id)
        history = state_machine.get_state_history(task_id)

        if current_state is None and not history:
            click.echo(f"Task {task_id} not found (no lock file)", err=True)
            sys.exit(EXIT_BLOCKED)

        if json_output:
            state_output = {
                "task_id": task_id,
                "current_state": current_state.value if current_state else None,
                "history": [
                    {
                        "ts": h.ts,
                        "from_state": h.from_state.value if h.from_state else None,
                        "to_state": h.to_state.value,
                        "context": h.context,
                    }
                    for h in history
                ],
            }
            click.echo(json.dumps(state_output, sort_keys=True, indent=2))
        else:
            click.echo(f"Task: {task_id}")
            click.echo(f"Current State: {current_state.value if current_state else 'None'}")

            if history:
                click.echo("\nState History:")
                for h in history:
                    from_str = h.from_state.value if h.from_state else "initial"
                    click.echo(f"  {h.ts}: {from_str} → {h.to_state.value}")
                    if h.context:
                        for key, value in h.context.items():
                            click.echo(f"    {key}: {value}")
            else:
                click.echo("\nNo state history available")
        return

    if wiki:
        wiki_path = _find_wiki_path()
        store = ScribeStore(wiki_path, ollama_url=os.environ.get("VILLAGE_EMBED_URL", "") or os.environ.get("OLLAMA_BASE_URL", ""))

        entries = store.store.all_entries()
        log_path = wiki_path / "log.md"

        click.echo(f"Wiki path: {wiki_path}")
        click.echo(f"Total entries: {len(entries)}")

        if entries:
            all_tags: list[str] = []
            for e in entries:
                all_tags.extend(e.tags)
            unique_tags = set(all_tags)
            click.echo(f"Unique tags: {len(unique_tags)}")
            if unique_tags:
                click.echo(f"  Top tags: {', '.join(sorted(unique_tags)[:10])}")

            click.echo(f"Latest entry: {entries[-1].title} ({entries[-1].id})")

        if log_path.exists():
            log_content = log_path.read_text(encoding="utf-8")
            log_lines = [line for line in log_content.split("\n") if line.startswith("- [")]
            click.echo(f"Log entries: {len(log_lines)}")
        return

    from village.render.json import render_status_json
    from village.render.text import render_full_status

    config = get_config()

    if json_output:
        full_status = collect_full_status(config.tmux_session)
        click.echo(render_status_json(full_status))
    elif short:
        tmux_running = session_exists(config.tmux_session)
        lock_files = list(config.locks_dir.glob("*.lock")) if config.locks_dir.exists() else []
        parts = []
        if tmux_running:
            parts.append(f"tmux:{config.tmux_session}")
        else:
            parts.append("tmux:none")

        if config.locks_dir.exists():
            parts.append(f"locks:{len(lock_files)}")
        else:
            parts.append("locks:none")

        click.echo(" ".join(parts))
    else:
        full_status = collect_full_status(config.tmux_session)
        flags_dict = {
            "workers": system,
            "locks": system,
            "orphans": system,
        }
        output = render_full_status(full_status, flags_dict)
        click.echo(output)


@watcher_group.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def locks(json_output: bool) -> None:
    """List all locks with ACTIVE/STALE status."""
    from village.render.text import render_worker_table

    config = get_config()
    workers = collect_workers(config.tmux_session)

    if json_output:
        locks_data = [
            {
                "task_id": w.task_id,
                "pane_id": w.pane_id,
                "window": w.window,
                "agent": w.agent,
                "claimed_at": w.claimed_at,
                "status": w.status,
            }
            for w in workers
        ]
        click.echo(json.dumps(locks_data, indent=2, sort_keys=True))
        return

    if not workers:
        click.echo("No locks found")
        return

    table_output = render_worker_table(workers)
    click.echo(table_output)


@watcher_group.command()
@click.option("--task", "task_id", help="Filter by task ID")
@click.option("--cmd", "cmd_filter", help="Filter by command")
@click.option("--limit", "limit", default=20, help="Number of events to show")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def events(
    task_id: str | None,
    cmd_filter: str | None,
    limit: int,
    json_output: bool,
) -> None:
    """
    Show recent events.

    Non-mutating. Reads from event log.

    Examples:
      village watcher events
      village watcher events --task bd-4uv
      village watcher events --cmd resume --limit 50
      village watcher events --json
    """
    from village.event_log import read_events

    config = get_config()

    all_events = read_events(config.village_dir)

    if task_id:
        all_events = [e for e in all_events if e.task_id and task_id in e.task_id]
    if cmd_filter:
        all_events = [e for e in all_events if e.cmd and cmd_filter in e.cmd]

    all_events = all_events[-limit:] if len(all_events) > limit else all_events

    if json_output:
        output = []
        for event in all_events:
            output.append(
                {
                    "ts": event.ts,
                    "cmd": event.cmd,
                    "task_id": event.task_id,
                    "pane": event.pane,
                    "result": event.result,
                    "error": event.error,
                }
            )
        click.echo(json.dumps(output, indent=2))
    else:
        if not all_events:
            click.echo("No events found")
            return

        for event in all_events:
            parts = [event.ts, event.cmd]
            if event.task_id:
                parts.append(event.task_id)
            if event.pane:
                parts.append(f"pane={event.pane}")
            if event.result:
                parts.append(f"result={event.result}")
            if event.error:
                parts.append(f"error={event.error}")
            click.echo(" ".join(parts))


@watcher_group.command()
@click.option("--watch", is_flag=True, help="Auto-refresh mode")
@click.option(
    "--refresh-interval",
    type=int,
    default=None,
    help="Refresh interval in seconds (default: from config)",
)
def dashboard(watch: bool, refresh_interval: int | None) -> None:
    """
    Show real-time dashboard of Village state.

    Displays active workers, task queue, lock status, and orphans.
    Auto-refreshes every 2 seconds by default (configurable).

    \b
    Non-mutating. Probes actual state, doesn't create directories.

    Examples:
        village watcher dashboard
        village watcher dashboard --watch
        village watcher dashboard --watch --refresh-interval 5
        village watcher dashboard --refresh-interval 10
    \b

    Flags:
        --watch: Enable auto-refresh mode
        --refresh-interval: Set refresh interval in seconds

    Default: Static dashboard view (no auto-refresh)
    """
    from village.dashboard import VillageDashboard

    config = get_config()

    interval = refresh_interval or config.dashboard.refresh_interval_seconds
    enabled = config.dashboard.enabled

    if not enabled:
        click.echo("Dashboard is disabled. Enable with DASHBOARD_ENABLED=true")
        sys.exit(EXIT_ERROR)

    if watch:
        dash = VillageDashboard(config.tmux_session)
        dash.start_watch_mode(interval)
    else:
        from village.dashboard import render_dashboard_static

        output = render_dashboard_static(config.tmux_session)
        click.echo(output)


@watcher_group.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed")
@click.option("--plan", is_flag=True, help="Generate cleanup plan")
@click.option("--apply", is_flag=True, help="Include orphan and stale worktrees")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def cleanup(dry_run: bool, plan: bool, apply: bool, json_output: bool) -> None:
    """
    Remove stale locks and optionally remove orphan/stale worktrees.

    Default: Execute mode (remove stale locks only).
    Use --plan or --dry-run to preview.
    Use --apply to include orphan and stale worktrees for removal.

    Examples:
      village watcher cleanup                    # Remove stale locks only
      village watcher cleanup --apply            # Remove stale locks + orphan/stale worktrees
      village watcher cleanup --plan --apply      # Preview apply plan
      village watcher cleanup --dry-run --apply   # Preview apply execution
    """
    from village.cleanup import execute_cleanup, plan_cleanup

    config = get_config()

    cleanup_plan = plan_cleanup(config.tmux_session, apply=apply)

    if json_output:
        data = {
            "stale_locks": [
                {
                    "task_id": lock.task_id,
                    "pane_id": lock.pane_id,
                    "window": lock.window,
                    "agent": lock.agent,
                    "claimed_at": lock.claimed_at.isoformat(),
                }
                for lock in cleanup_plan.stale_locks
            ],
            "orphan_worktrees": [str(p) for p in cleanup_plan.orphan_worktrees],
            "stale_worktrees": [str(p) for p in cleanup_plan.stale_worktrees],
        }
        if dry_run or plan:
            data["dry_run"] = True
        click.echo(json.dumps(data, indent=2, sort_keys=True))
        return

    if apply:
        if cleanup_plan.orphan_worktrees:
            click.echo(f"Found {len(cleanup_plan.orphan_worktrees)} orphan worktrees:")
            for worktree in cleanup_plan.orphan_worktrees:
                click.echo(f"  - {worktree}")
        else:
            click.echo("No orphan worktrees found")

        if cleanup_plan.stale_worktrees:
            click.echo(f"Found {len(cleanup_plan.stale_worktrees)} stale worktrees:")
            for worktree in cleanup_plan.stale_worktrees:
                click.echo(f"  - {worktree}")
        else:
            click.echo("No stale worktrees found")

    if cleanup_plan.stale_locks:
        click.echo(f"Found {len(cleanup_plan.stale_locks)} stale locks:")
        for lock in cleanup_plan.stale_locks:
            click.echo(f"  - {lock.task_id} (pane: {lock.pane_id})")
    else:
        click.echo("No stale locks found")
        return

    if dry_run or plan:
        items_to_remove = len(cleanup_plan.stale_locks)
        if apply:
            items_to_remove += len(cleanup_plan.orphan_worktrees) + len(cleanup_plan.stale_worktrees)
        click.echo(f"(preview: would remove {items_to_remove} item(s))")
        return

    execute_cleanup(cleanup_plan, config)

    removed_count = len(cleanup_plan.stale_locks)
    if apply:
        removed_count += len(cleanup_plan.orphan_worktrees) + len(cleanup_plan.stale_worktrees)

    click.echo("Cleanup complete")


@watcher_group.command()
@click.argument("task_id", default=None, required=False, type=str)
@click.option("--force", is_flag=True, help="Force unlock even if pane is active")
@click.option("--select", "select_mode", is_flag=True, help="Select from list interactively")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def unlock(task_id: str | None, force: bool, select_mode: bool, json_output: bool) -> None:
    """
    Unlock a task (remove lock file).

    Raises:
        click.ClickException: If lock is ACTIVE and --force not provided
    """
    from village.interactive import select_from_list
    from village.locks import is_active, parse_lock
    from village.status import collect_workers

    config = get_config()

    if task_id is None or (select_mode and not json_output):
        workers = collect_workers(config.tmux_session)
        if not workers:
            if json_output:
                err_data = {"unlocked": False, "task_id": None, "error": "No locks found"}
                click.echo(json.dumps(err_data, indent=2, sort_keys=True))
                return
            click.echo("No locks found")
            if task_id is None:
                sys.exit(0)
            return

        if json_output:
            err_data = {"unlocked": False, "task_id": None, "error": "Task ID required with --json"}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return

        selected = select_from_list(
            workers,
            "Select task to unlock:",
            formatter=lambda w: f"{w.task_id} ({w.status})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected.task_id

    lock_path = config.locks_dir / f"{task_id}.lock"

    if not lock_path.exists():
        if json_output:
            err_data = {"unlocked": False, "task_id": task_id, "error": f"No such lock: {task_id}"}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        click.echo(f"Lock not found: {task_id}")
        raise click.ClickException(f"No such lock: {task_id}")

    lock = parse_lock(lock_path)
    if not lock:
        if json_output:
            err_data = {"unlocked": False, "task_id": task_id, "error": f"Failed to parse lock: {task_id}"}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        click.echo(f"Invalid lock file: {task_id}")
        raise click.ClickException(f"Failed to parse lock: {task_id}")

    if is_active(lock, config.tmux_session):
        if not force:
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "unlocked": False,
                            "task_id": task_id,
                            "error": f"Lock is ACTIVE (pane {lock.pane_id}) — use --force",
                            "active": True,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return
            click.echo(f"Lock is ACTIVE (pane {lock.pane_id} exists)")
            click.echo("Use --force to unlock anyway")
            raise click.ClickException(f"Lock {task_id} is active")

    lock_path.unlink()
    if json_output:
        click.echo(json.dumps({"unlocked": True, "task_id": task_id, "force": force}, indent=2, sort_keys=True))
        return
    click.echo(f"Unlocked: {task_id}")


@watcher_group.command()
@click.option("--interval", default=30, help="Poll interval in seconds")
def monitor(interval: int) -> None:
    """Watch wiki/ingest/ for new files and process them."""
    from village.scribe.monitor import Monitor

    wiki_path = _find_wiki_path()
    store = ScribeStore(wiki_path, ollama_url=os.environ.get("VILLAGE_EMBED_URL", "") or os.environ.get("OLLAMA_BASE_URL", ""))
    mon = Monitor(wiki_path, store, poll_interval=interval)

    click.echo(f"Monitoring {wiki_path / 'ingest'} every {interval}s (Ctrl+C to stop)")
    mon.start()


@watcher_group.group("ledger")
def ledger_group() -> None:
    """Audit trail commands."""


@ledger_group.command("show")
@click.argument("task_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def ledger_show(task_id: str | None, json_output: bool) -> None:
    """View audit trail for a task."""
    config = get_config()
    reader = TraceReader(config.traces_dir)

    if task_id is None:
        task_ids = reader.list_traced_tasks()
        if not task_ids:
            click.echo("No audit trails found.")
            return
        click.echo("Traced tasks:")
        for i, tid in enumerate(task_ids, 1):
            click.echo(f"  {i}. {tid}")
        choice = int(sync_prompt("Which task?", type=int))
        if choice < 1 or choice > len(task_ids):
            raise click.ClickException("Invalid selection")
        task_id = task_ids[choice - 1]

    assert task_id is not None
    events = reader.read(task_id)

    if not events:
        click.echo(f"No audit events for {task_id}")
        sys.exit(EXIT_ERROR)

    if json_output:
        data = []
        for event in events:
            data.append(
                {
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "task_id": event.task_id,
                    "agent": event.agent,
                    "data": event.data,
                    "sequence": event.sequence,
                }
            )
        click.echo(json.dumps(data, indent=2, sort_keys=True))
    else:
        click.echo(format_trace(events))


@ledger_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def ledger_list(json_output: bool) -> None:
    """List tasks with audit trails."""
    config = get_config()
    reader = TraceReader(config.traces_dir)
    task_ids = reader.list_traced_tasks()

    if not task_ids:
        click.echo("No audit trails found")
        return

    if json_output:
        click.echo(json.dumps(task_ids, indent=2))
    else:
        for task_id in task_ids:
            click.echo(task_id)


@watcher_group.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def ready(json_output: bool) -> None:
    """
    Check if village is ready for work.

    Non-mutating. Assesses environment, runtime, and work availability.

    Flags:
      --json: Full assessment as JSON (no suggested actions)

    Default: Text output with suggested actions
    """
    from village.ready import assess_readiness
    from village.render.json import render_ready_json
    from village.render.text import render_ready_text

    config = get_config()
    assessment = assess_readiness(config.tmux_session)

    if json_output:
        click.echo(render_ready_json(assessment))
    else:
        click.echo(render_ready_text(assessment))
        _show_objective_coverage(config)


def _show_objective_coverage(config: "Config") -> None:
    """Append objective coverage summary after readiness text."""
    from village.goals import get_objective_coverage_from_file, parse_goals

    goals_path = config.git_root / "GOALS.md"
    all_goals = parse_goals(goals_path)
    if not all_goals:
        return

    coverage = get_objective_coverage_from_file(goals_path)
    total_completed = 0
    total_objectives = 0
    for goal_id, (completed, total, _ratio) in coverage.items():
        total_completed += completed
        total_objectives += total

    if total_objectives > 0:
        pct = round(total_completed / total_objectives * 100, 1)
        click.echo(f"Objectives: {total_completed}/{total_objectives} completed ({pct}%)")
