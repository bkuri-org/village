"""Village Scribe — knowledge base and audit trail CLI commands."""

import json
import logging
from pathlib import Path

import click

from village.roles import run_role_chat
from village.scribe.curate import Curator
from village.scribe.store import ScribeStore

logger = logging.getLogger(__name__)


def _get_ollama_url() -> str:
    """Get Ollama embedding URL from environment.

    Checks VILLAGE_EMBED_URL first (explicit), then falls back to OLLAMA_BASE_URL.
    Returns empty string if neither is set — semantic search will be disabled.
    """
    import os

    return os.environ.get("VILLAGE_EMBED_URL", "") or os.environ.get("OLLAMA_BASE_URL", "")


def _make_store(wiki_path: Path) -> ScribeStore:
    """Create a ScribeStore with optional embedding support."""
    ollama_url = _get_ollama_url()
    return ScribeStore(wiki_path, ollama_url=ollama_url)


def _find_wiki_path() -> Path:
    cwd = Path.cwd()
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current / "wiki"
        current = current.parent
    logger.warning(
        "No .git directory found from %s — falling back to %s/wiki",
        cwd,
        cwd,
    )
    return cwd / "wiki"


@click.group(invoke_without_command=True)
@click.pass_context
def scribe_group(ctx: click.Context) -> None:
    """Manage project knowledge base."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("scribe")


@scribe_group.command()
@click.argument("source")
@click.option("--raw", is_flag=True, help="Bypass LLM distillation, store content as-is")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def fetch(source: str, raw: bool, json_output: bool) -> None:
    """Ingest a URL or file into the knowledge base."""
    wiki_path = _find_wiki_path()
    store = _make_store(wiki_path)

    result = store.see(source, raw=raw)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "entry_id": result.entry_id,
                    "title": result.title,
                    "tags": result.tags,
                    "status": result.status,
                }
            )
        )
    else:
        if result.status == "error":
            click.echo(f"Error: {result.error}")
            raise SystemExit(1)
        click.echo(f"Ingested: {result.title} ({result.entry_id})")
        if result.tags:
            click.echo(f"  Tags: {', '.join(result.tags)}")


@scribe_group.command()
@click.argument("question")
@click.option("--save", is_flag=True, help="Save answer as new wiki page")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ask(question: str, save: bool, json_output: bool) -> None:
    """Query the knowledge base and synthesize an answer."""
    wiki_path = _find_wiki_path()
    store = _make_store(wiki_path)

    result = store.ask(question, save=save)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "answer": result.answer,
                    "sources": result.sources,
                    "saved": result.saved,
                    "error": result.error,
                }
            )
        )
    else:
        click.echo(result.answer)
        if result.sources:
            click.echo(f"\nSources: {', '.join(result.sources)}")

    if result.error:
        raise SystemExit(1)


@scribe_group.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--fix", is_flag=True, help="Archive orphans to ORPHANS.md and exclude from wiki index")
def curate(json_output: bool, fix: bool) -> None:
    """Health check and maintain the knowledge base."""
    wiki_path = _find_wiki_path()
    project_root = wiki_path.parent
    store = _make_store(wiki_path)
    curator = Curator(store.store, wiki_path, project_root)

    result = curator.curate(fix=fix)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "total_entries": result.total_entries,
                    "orphans": result.orphans,
                    "stale_count": len(result.stale_entries),
                    "broken_links": len(result.broken_links),
                    "voice_updated": result.voice_updated,
                    "orphans_archived": result.orphans_archived,
                    "orphans_md_written": result.orphans_md_written,
                    "discovered": [str(d.path.relative_to(project_root)) for d in result.discovered],
                    "discovered_count": len(result.discovered),
                    "discovered_ingested": result.discovered_ingested,
                    "discovered_ingested_count": len(result.discovered_ingested),
                    "curate_log": result.curate_log,
                }
            )
        )
    else:
        click.echo(f"Entries: {result.total_entries}")
        click.echo(f"Orphans: {len(result.orphans)}")
        if result.orphans:
            for oid in result.orphans:
                click.echo(f"  - {oid}")
        click.echo(f"Stale: {len(result.stale_entries)}")
        click.echo(f"Broken links: {len(result.broken_links)}")
        if result.broken_links:
            for bl in result.broken_links:
                click.echo(f"  - {bl.url} ({bl.status_code or 'error'})")
        if result.discovered:
            ingested_count = len(result.discovered_ingested)
            click.echo(f"Discovered: {len(result.discovered)} files ({ingested_count} auto-ingested)")
            for df in result.discovered:
                rel = str(df.path.relative_to(project_root))
                click.echo(f"  - {rel}")
            if result.discovered_ingested:
                for eid in result.discovered_ingested:
                    click.echo(f"  ✓ {eid}")
        click.echo(f"VOICE.md updated: {result.voice_updated}")
        if result.orphans_archived:
            click.echo(f"Orphans archived: {len(result.orphans_archived)}")
            for oid in result.orphans_archived:
                click.echo(f"  - {oid}")
        if result.curate_log:
            click.echo("Actions:")
            for entry in result.curate_log:
                click.echo(f"  - {entry}")


@scribe_group.command()
@click.option("--scope", type=str, help="Filter by scope (feature|fix|investigation|refactoring)")
@click.option("--total", is_flag=True, help="Return draft count (for statusbar)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def drafts(scope: str | None, total: bool, json_output: bool) -> None:
    """List or count draft tasks."""
    from village.chat.drafts import list_drafts
    from village.config import get_config
    from village.render.text import render_drafts_table

    config = get_config()
    all_drafts = list_drafts(config)

    if total:
        if json_output:
            click.echo(json.dumps({"count": len(all_drafts)}, indent=2, sort_keys=True))
            return
        click.echo(str(len(all_drafts)))
        return

    if scope:
        all_drafts = [d for d in all_drafts if d.scope == scope]

    if json_output:
        drafts_data = [
            {
                "id": d.id,
                "title": d.title,
                "description": d.description,
                "scope": d.scope,
                "created_at": d.created_at.isoformat(),
                "relates_to_goals": d.relates_to_goals,
                "success_criteria": d.success_criteria,
                "blockers": d.blockers,
                "estimate": d.estimate,
                "tags": d.tags,
                "notes": d.notes,
                "llm_notes": d.llm_notes,
            }
            for d in all_drafts
        ]
        click.echo(json.dumps(drafts_data, indent=2, sort_keys=True, default=str))
        return

    table_output = render_drafts_table(all_drafts)
    click.echo(table_output)
