"""Built-in task management commands."""

import json

import click

from village.logging import get_logger
from village.tasks import TaskStoreError, get_task_store

logger = get_logger(__name__)


@click.group()
def tasks() -> None:
    """Manage tasks (built-in task store)."""


@tasks.command(name="list")
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--type", "issue_type", default=None, help="Filter by issue type")
@click.option("--label", type=str, default=None, help="Filter by label")
@click.option("--project", "project_filter", default=None, help="Filter by project label")
@click.option("--limit", type=int, default=50, help="Max tasks to show")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def list_tasks(
    status: str | None,
    issue_type: str | None,
    label: str | None,
    project_filter: str | None,
    limit: int,
    json_output: bool,
) -> None:
    """List tasks."""
    try:
        store = get_task_store()
        result = store.list_tasks(
            status=status,
            issue_type=issue_type,
            label=label,
            limit=limit,
        )
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if project_filter:
        from village.plans.project import filter_by_project

        filtered = filter_by_project([t.to_dict() for t in result], project_filter)
        filtered_ids = {d["id"] for d in filtered}
        result = [t for t in result if t.id in filtered_ids]

    if json_output:
        click.echo(json.dumps([t.to_dict() for t in result], indent=2))
        return

    if not result:
        click.echo("No tasks found.")
        return

    for task in result:
        status_str = task.status
        priority_str = f"P{task.priority}"
        labels_str = f" [{', '.join(task.labels)}]" if task.labels else ""
        click.echo(f"  {task.id} [{status_str}] [{priority_str}] {task.title}{labels_str}")


@tasks.command()
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def show(task_id: str, json_output: bool) -> None:
    """Show task details."""
    try:
        store = get_task_store()
        task = store.get_task(task_id)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if task is None:
        click.echo(f"Task not found: {task_id}")
        return

    if json_output:
        click.echo(json.dumps(task.to_dict(), indent=2))
        return

    click.echo(f"  ID:          {task.id}")
    click.echo(f"  Title:       {task.title}")
    click.echo(f"  Status:      {task.status}")
    click.echo(f"  Type:        {task.issue_type}")
    click.echo(f"  Priority:    P{task.priority}")
    click.echo(f"  Estimate:    {task.estimate} min")
    click.echo(f"  Owner:       {task.owner or '(none)'}")
    click.echo(f"  Created:     {task.created_at}")
    click.echo(f"  Updated:     {task.updated_at}")

    if task.description:
        click.echo(f"  Description: {task.description}")

    if task.labels:
        click.echo(f"  Labels:      {', '.join(task.labels)}")

    if task.depends_on:
        click.echo(f"  Depends on:   {', '.join(task.depends_on) or '(none)'}")

    if task.blocks:
        click.echo(f"  Blocks:       {', '.join(task.blocks) or '(none)'}")


@tasks.command()
@click.argument("title")
@click.option("--description", "-d", default="", help="Task description")
@click.option("--type", "issue_type", default="task", help="Issue type (bug|feature|task|epic|chore)")
@click.option("--priority", "-p", type=int, default=2, help="Priority (0-4, 0=critical)")
@click.option("--label", "-l", multiple=True, help="Labels (can specify multiple)")
@click.option("--depends-on", multiple=True, help="Task IDs this depends on")
@click.option("--blocks", multiple=True, help="Task IDs this blocks")
@click.option("--estimate", type=int, default=0, help="Estimate in minutes")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def create(
    title: str,
    description: str,
    issue_type: str,
    priority: int,
    label: tuple[str, ...],
    depends_on: tuple[str, ...],
    blocks: tuple[str, ...],
    estimate: int,
    json_output: bool,
) -> None:
    """Create a new task."""
    from village.tasks import TaskCreate

    spec = TaskCreate(
        title=title,
        description=description,
        issue_type=issue_type,
        priority=priority,
        labels=list(label),
        depends_on=list(depends_on),
        blocks=list(blocks),
        estimate=estimate,
    )

    try:
        store = get_task_store()
        task = store.create_task(spec)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        click.echo(json.dumps(task.to_dict(), indent=2))
    else:
        click.echo(f"Created task: {task.id}")
        click.echo(f"  Title: {task.title}")


@tasks.command()
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--label", type=str, default=None, help="Filter by label")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def ready(status: str | None, label: str | None, json_output: bool) -> None:
    """Show tasks ready to work (unblocked)."""
    try:
        store = get_task_store()
        result = store.get_ready_tasks()
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if status:
        result = [t for t in result if t.status == status]

    if label:
        result = [t for t in result if label in t.labels]

    if json_output:
        click.echo(json.dumps([t.to_dict() for t in result], indent=2))
        return

    if not result:
        click.echo("No ready tasks.")
        return

    for task in result:
        priority_str = f"P{task.priority}"
        labels_str = f" [{', '.join(task.labels)}]" if task.labels else ""
        click.echo(f"  {task.id} [{priority_str}] {task.title}{labels_str}")


@tasks.command()
@click.argument("task_id")
@click.option("--status", "-s", type=str, default=None, help="New status")
@click.option("--label", "-l", multiple=True, help="Labels to add")
@click.option("--remove-label", multiple=True, help="Labels to remove")
@click.option("--priority", "-p", type=int, default=None, help="New priority (0-4)")
@click.option("--description", "-d", default=None, help="New description")
@click.option("--title", default=None, help="New title")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def update(
    task_id: str,
    status: str | None,
    label: tuple[str, ...],
    remove_label: tuple[str, ...],
    priority: int | None,
    description: str | None,
    title: str | None,
    json_output: bool,
) -> None:
    """Update a task."""
    from village.tasks import TaskUpdate

    update_spec = TaskUpdate(
        status=status,
        add_labels=list(label),
        remove_labels=list(remove_label),
        priority=priority,
        description=description,
        title=title,
    )

    if not update_spec.has_changes():
        click.echo("Error: No changes specified.")
        return

    try:
        store = get_task_store()
        task = store.update_task(task_id, update_spec)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        click.echo(json.dumps(task.to_dict(), indent=2))
    else:
        click.echo(f"Updated task: {task_id}")
        click.echo(f"  Status: {task.status}")
        if update_spec.add_labels:
            click.echo(f"  Added labels: {', '.join(update_spec.add_labels)}")
        if update_spec.remove_labels:
            click.echo(f"  Removed labels: {', '.join(update_spec.remove_labels)}")


@tasks.command(name="label")
@click.argument("task_id")
@click.option("--add", "add_labels", multiple=True, help="Labels to add (repeatable)")
@click.option("--remove", "remove_labels", multiple=True, help="Labels to remove (repeatable)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def label(task_id: str, add_labels: tuple[str, ...], remove_labels: tuple[str, ...], json_output: bool) -> None:
    """Add or remove labels from a task."""
    if not add_labels and not remove_labels:
        click.echo("Error: specify --add <label> or --remove <label>", err=True)
        raise SystemExit(1)

    try:
        store = get_task_store()
        if add_labels:
            for lbl in add_labels:
                store.add_label(task_id, lbl)
        if remove_labels:
            from village.tasks import TaskUpdate

            update_spec = TaskUpdate(remove_labels=list(remove_labels))
            store.update_task(task_id, update_spec)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        task = store.get_task(task_id)
        if task:
            click.echo(json.dumps(task.to_dict(), indent=2))
    else:
        if add_labels:
            click.echo(f"Added label(s) to {task_id}: {', '.join(add_labels)}")
        if remove_labels:
            click.echo(f"Removed label(s) from {task_id}: {', '.join(remove_labels)}")


@tasks.command()
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def deps(task_id: str, json_output: bool) -> None:
    """Show task dependencies."""
    try:
        store = get_task_store()
        info = store.get_dependencies(task_id)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        click.echo(
            json.dumps(
                {
                    "task_id": info.task_id,
                    "blocks": [t.to_dict() for t in info.blocks],
                    "blocked_by": [t.to_dict() for t in info.blocked_by],
                },
                indent=2,
            )
        )
        return

    if info.blocks:
        click.echo("  Blocks:")
        for t in info.blocks:
            click.echo(f"    {t.id}: {t.title}")

    if info.blocked_by:
        click.echo("  Blocked by:")
        for t in info.blocked_by:
            click.echo(f"    {t.id}: {t.title}")

    if not info.blocks and not info.blocked_by:
        click.echo("  No dependencies.")


@tasks.command()
@click.argument("task_id")
def delete(task_id: str) -> None:
    """Delete a task."""
    try:
        store = get_task_store()
        store.delete_task(task_id)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    click.echo(f"Deleted task: {task_id}")


@tasks.command()
@click.argument("query")
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--limit", type=int, default=20, help="Max results")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def search(query: str, status: str | None, limit: int, json_output: bool) -> None:
    """Search tasks by keyword."""
    try:
        store = get_task_store()
        result = store.search_tasks(query, status=status, limit=limit)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        click.echo(json.dumps([t.to_dict() for t in result.tasks], indent=2))
        return

    if not result.tasks:
        click.echo("No matching tasks found.")
        return

    click.echo(f"Found {result.total} matching task(s):")
    for task in result.tasks:
        click.echo(f"  {task.id} [{task.status}] P{task.priority} {task.title}")


@tasks.command()
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def count(status: str | None, json_output: bool) -> None:
    """Count tasks."""
    try:
        store = get_task_store()
        total = store.count_tasks(status=status)
    except TaskStoreError as e:
        click.echo(f"Error: {e}", err=True)
        return

    if json_output:
        click.echo(json.dumps({"total": total, "status": status}))
    else:
        if status:
            click.echo(f"{total} task(s) with status '{status}'")
        else:
            click.echo(f"{total} total task(s)")
