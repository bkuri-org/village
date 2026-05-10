"""File-based memory store using markdown entries with YAML frontmatter."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry stored as a markdown file."""

    id: str
    title: str
    text: str
    tags: list[str] = field(default_factory=list)
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str | list[str]] = field(default_factory=dict)

    def filename(self) -> str:
        return f"{self.id}.md"


def _parse_frontmatter(content: str) -> tuple[dict[str, str | list[str]], str]:
    """Parse YAML frontmatter from markdown content.

    Returns (metadata_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    frontmatter = content[3:end].strip()
    body = content[end + 3 :].strip()

    meta: dict[str, str | list[str]] = {}
    for line in frontmatter.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
            meta[key] = items
        else:
            meta[key] = value.strip("'\"")

    return meta, body


def _format_frontmatter(meta: dict[str, str | list[str]]) -> str:
    """Format metadata dict as YAML frontmatter string."""
    lines: list[str] = []
    for key, value in meta.items():
        if isinstance(value, list):
            items = ", ".join(value)
            lines.append(f"{key}: [{items}]")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _entry_from_file(path: Path) -> MemoryEntry | None:
    """Parse a MemoryEntry from a markdown file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    meta, body = _parse_frontmatter(content)

    title = ""
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        body = body[title_match.end() :].strip()

    tags_raw = meta.get("tags", [])
    tags = tags_raw if isinstance(tags_raw, list) else [tags_raw]

    created_str = meta.get("created", "")
    created: datetime = datetime.now(timezone.utc)
    if isinstance(created_str, str) and created_str:
        try:
            created = datetime.fromisoformat(created_str)
        except ValueError:
            pass

    clean_meta: dict[str, str | list[str]] = {}
    skip_keys = {"id", "tags", "created"}
    for k, v in meta.items():
        if k not in skip_keys:
            clean_meta[k] = v

    raw_id = meta.get("id", path.stem)
    entry_id = raw_id if isinstance(raw_id, str) else path.stem

    return MemoryEntry(
        id=entry_id,
        title=title,
        text=body,
        tags=tags,
        created=created,
        metadata=clean_meta,
    )


def _entry_to_file_content(entry: MemoryEntry) -> str:
    """Serialize a MemoryEntry to markdown with frontmatter."""
    meta: dict[str, str | list[str]] = {"id": entry.id, "tags": entry.tags}
    meta["created"] = entry.created.isoformat()

    for k, v in entry.metadata.items():
        meta[k] = v

    lines = ["---"]
    lines.append(_format_frontmatter(meta))
    lines.append("---")
    lines.append("")
    lines.append(f"# {entry.title}")
    lines.append("")
    lines.append(entry.text)
    lines.append("")

    return "\n".join(lines)


class MemoryStore:
    """File-based memory store backed by markdown files.

    Storage layout:
        <store_path>/
        ├── index.md
        ├── embeddings.json    (optional, created when semantic search is used)
        └── entries/
            ├── note-001.md
            └── note-002.md
    """

    def __init__(
        self,
        store_path: Path,
        ollama_url: str = "",
        embed_model: str = "",
    ) -> None:
        self.path = store_path
        self.entries_dir = store_path / "entries"
        self.index_path = store_path / "index.md"
        self._embed_cache: EmbeddingCache | None = None
        if ollama_url:
            from village.memory.embeddings import EmbeddingCache

            model = embed_model or "nomic-embed-text"
            self._embed_cache = EmbeddingCache(
                cache_path=store_path / "embeddings.json",
                ollama_url=ollama_url,
                model=model,
            )

    def _ensure_dirs(self) -> None:
        self.entries_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> str:
        existing = self.all_entries()
        if not existing:
            return "note-001"
        max_num = 0
        for entry in existing:
            match = re.search(r"(\d+)$", entry.id)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        return f"note-{max_num + 1:03d}"

    def put(
        self,
        title: str,
        text: str,
        tags: list[str] | None = None,
        metadata: dict[str, str | list[str]] | None = None,
        entry_id: str | None = None,
    ) -> str:
        """Write a new entry. Returns entry ID."""
        self._ensure_dirs()

        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}

        entry_id = entry_id or self._next_id()

        entry = MemoryEntry(
            id=entry_id,
            title=title,
            text=text,
            tags=tags,
            metadata=metadata,
        )

        file_path = self.entries_dir / entry.filename()
        file_path.write_text(_entry_to_file_content(entry), encoding="utf-8")

        # Compute embedding in background if semantic search is configured
        if self._embed_cache is not None:
            embed_text = f"{entry.title}\n{entry.text}"
            try:
                if not self._embed_cache.put_text(entry_id, embed_text):
                    logger.debug("Failed to embed entry %s — Ollama may be unavailable", entry_id)
            except Exception:
                logger.debug("Embedding failed for entry %s", entry_id, exc_info=True)

        self.rebuild_index()
        return entry.id

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Retrieve single entry by ID."""
        file_path = self.entries_dir / f"{entry_id}.md"
        if not file_path.exists():
            return None
        return _entry_from_file(file_path)

    def find(self, query: str, k: int = 5) -> list[MemoryEntry]:
        """Keyword search over entries (case-insensitive substring over title+text+tags)."""
        query_lower = query.lower()
        results: list[tuple[float, MemoryEntry]] = []

        for entry in self.all_entries():
            score = 0.0
            title_lower = entry.title.lower()
            text_lower = entry.text.lower()
            tags_lower = [t.lower() for t in entry.tags]

            if query_lower in title_lower:
                score += 2.0
            if query_lower in text_lower:
                score += 1.0
            for tag in tags_lower:
                if query_lower in tag:
                    score += 1.5

            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:k]]

    def find_semantic(self, query: str, k: int = 5) -> list[MemoryEntry]:
        """Semantic search using embedding cosine similarity.

        Falls back to keyword search if embeddings are unavailable.
        Returns entries sorted by semantic relevance.
        """
        if self._embed_cache is None:
            logger.debug("Semantic search requested but no embedding cache configured")
            return self.find(query, k=k)

        all_entries = self.all_entries()
        if not all_entries:
            return []

        entry_ids = [e.id for e in all_entries]
        entry_map = {e.id: e for e in all_entries}

        ranked = self._embed_cache.find(query, entry_ids, k=k)
        if not ranked:
            logger.debug("No embedding results — falling back to keyword search")
            return self.find(query, k=k)

        results: list[MemoryEntry] = []
        for eid, _score in ranked:
            entry = entry_map.get(eid)
            if entry is not None:
                results.append(entry)
        return results[:k]

    def rebuild_embeddings(self) -> int:
        """Rebuild the embedding cache for all existing entries.

        Returns the number of entries successfully embedded.
        Requires ollama_url to be configured in __init__.
        """
        if self._embed_cache is None:
            logger.warning("Cannot rebuild embeddings — no Ollama URL configured")
            return 0

        entries = {e.id: f"{e.title}\n{e.text}" for e in self.all_entries()}
        return self._embed_cache.rebuild(entries)

    def recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent entries by created timestamp."""
        entries = self.all_entries()
        entries.sort(key=lambda e: e.created, reverse=True)
        return entries[:limit]

    def related(self, entry_id: str, k: int = 5) -> list[MemoryEntry]:
        """Find entries related to given entry by tag overlap."""
        target = self.get(entry_id)
        if target is None:
            return []

        target_tags = set(t.lower() for t in target.tags)
        if not target_tags:
            return []

        results: list[tuple[float, MemoryEntry]] = []
        for entry in self.all_entries():
            if entry.id == entry_id:
                continue
            entry_tags = set(t.lower() for t in entry.tags)
            if not entry_tags:
                continue

            intersection = target_tags & entry_tags
            union = target_tags | entry_tags
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard > 0:
                results.append((jaccard, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:k]]

    def all_entries(self) -> list[MemoryEntry]:
        """List all entries."""
        if not self.entries_dir.exists():
            return []

        entries: list[MemoryEntry] = []
        for md_file in sorted(self.entries_dir.glob("*.md")):
            entry = _entry_from_file(md_file)
            if entry is not None:
                entries.append(entry)
        return entries

    def delete(self, entry_id: str) -> bool:
        """Remove entry by ID."""
        file_path = self.entries_dir / f"{entry_id}.md"
        if not file_path.exists():
            return False
        file_path.unlink()
        if self._embed_cache is not None:
            self._embed_cache.remove(entry_id)
        self.rebuild_index()
        return True

    def rebuild_index(self, exclude: set[str] | None = None) -> None:
        """Regenerate index.md from entries.

        Args:
            exclude: Optional set of entry IDs to omit from the index.
        """
        self._ensure_dirs()
        entries = self.all_entries()
        exclude_set = exclude or set()

        lines: list[str] = ["# Memory Index", ""]
        for entry in sorted(entries, key=lambda e: e.created, reverse=True):
            if entry.id in exclude_set:
                continue
            tags_str = ", ".join(entry.tags) if entry.tags else ""
            suffix = f" — {tags_str}" if tags_str else ""
            lines.append(f"- [{entry.id}] {entry.title}{suffix}")

        lines.append("")
        self.index_path.write_text("\n".join(lines), encoding="utf-8")
