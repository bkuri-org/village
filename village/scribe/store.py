import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import trafilatura

from village.memory import MemoryStore

logger = logging.getLogger(__name__)

MAX_DISTILL_SIZE = 2000

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "it",
        "as",
        "be",
        "was",
        "are",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "not",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "before",
        "between",
        "into",
        "through",
        "during",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "then",
        "once",
        "here",
        "there",
        "if",
        "so",
        "than",
    }
)


@dataclass
class IngestResult:
    entry_id: str
    title: str
    tags: list[str] = field(default_factory=list)
    status: str = "success"
    error: str = ""
    distill_failed: bool = False


@dataclass
class AskResult:
    answer: str
    sources: list[str]
    saved: bool
    error: str = ""


class ScribeStore:
    def __init__(
        self,
        wiki_path: Path,
        ollama_url: str = "",
        embed_model: str = "",
    ) -> None:
        self.wiki_path = wiki_path
        self.ingest_dir = wiki_path / "ingest"
        self.processed_dir = wiki_path / "processed"
        self.pages_dir = wiki_path / "pages"
        self.log_path = wiki_path / "log.md"
        self.store = MemoryStore(wiki_path / "pages", ollama_url=ollama_url, embed_model=embed_model)

    def _ensure_dirs(self) -> None:
        self.ingest_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def _extract_url(self, url: str) -> tuple[str, str]:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        downloaded = trafilatura.bare_extraction(html, url=url)
        if downloaded is None:
            logger.warning(
                "Trafilatura extraction failed for %s — falling back to raw HTML",
                url,
            )
            return url, html
        if isinstance(downloaded, dict):
            title = downloaded.get("title") or url
            text = downloaded.get("text") or ""
        else:
            title = getattr(downloaded, "title", None) or url
            text = getattr(downloaded, "text", None) or ""
        return title, text

    def _distill(self, text: str, title: str) -> tuple[str, bool]:
        """Distill text. Returns (processed_text, distill_failed)."""
        if len(text) <= MAX_DISTILL_SIZE:
            return text, False

        try:
            from village.config import get_config
            from village.llm.factory import get_llm_client

            config = get_config()
            llm = get_llm_client(config)
            prompt = (
                f"Distill the following document into a concise summary of actionable knowledge. "
                f"Extract key conventions, patterns, rules, and important facts. "
                f"Document title: {title}\n\n{text}"
            )
            system_prompt = (
                "You are a knowledge distillation assistant. Produce a concise summary "
                "that preserves actionable information, conventions, and key patterns. "
                "Do not include preamble — output only the distilled content."
            )
            result = llm.call(prompt, system_prompt=system_prompt, max_tokens=2048, timeout=60)
            return result.strip(), False
        except Exception:
            logger.warning("LLM distillation failed, falling back to truncation", exc_info=True)
            truncated = f"{text[:MAX_DISTILL_SIZE]}\n\n[Content truncated — original was {len(text)} chars]"
            return truncated, True

    def _extract_file(self, path: Path, raw: bool = False) -> tuple[str, str, bool]:
        text = path.read_text(encoding="utf-8")
        title = path.stem
        distill_failed = False
        if not raw:
            text, distill_failed = self._distill(text, title)
        return title, text, distill_failed

    def _extract(self, source: str, raw: bool = False) -> tuple[str, str, bool]:
        if source.startswith("http://") or source.startswith("https://"):
            title, text = self._extract_url(source)
            return title, text, False
        path = Path(source)
        if path.exists():
            return self._extract_file(path, raw=raw)
        raise FileNotFoundError(f"Source not found: {source}")

    def _append_log(self, source: str, entry_id: str, title: str) -> None:
        if self.log_path.exists():
            existing = self.log_path.read_text(encoding="utf-8")
        else:
            existing = "# Ingest Log\n\n"
        line = f"- [{entry_id}] {title} — _{source}_\n"
        self.log_path.write_text(existing + line, encoding="utf-8")

    def _generate_tags(self, title: str) -> list[str]:
        words = title.lower().split()
        return [w for w in words if w not in STOP_WORDS and len(w) > 1]

    def see(self, source: str, raw: bool = False) -> IngestResult:
        self._ensure_dirs()
        try:
            title, text, distill_failed = self._extract(source, raw=raw)
        except Exception as exc:
            return IngestResult(
                entry_id="",
                title="",
                tags=[],
                status="error",
                error=str(exc),
            )

        tags = self._generate_tags(title)
        entry_id = self.store.put(
            title,
            text,
            tags=tags,
            metadata={"source": source},
        )
        self._append_log(source, entry_id, title)

        source_path = Path(source)
        if not source.startswith("http") and source_path.exists():
            try:
                ingest_file = self.ingest_dir / source_path.name
                if ingest_file.exists():
                    processed_file = self.processed_dir / source_path.name
                    ingest_file.rename(processed_file)
            except OSError as exc:
                logger.warning("Failed to move %s to processed: %s", ingest_file, exc)

        return IngestResult(
            entry_id=entry_id,
            title=title,
            tags=tags,
            status="success",
            error="",
            distill_failed=distill_failed,
        )

    def ask(self, question: str, save: bool = False) -> AskResult:
        """Query wiki and synthesize an answer.

        Uses semantic search (embedding similarity) when an Ollama URL
        is configured, otherwise falls back to keyword substring search.
        """
        hits = self.store.find_semantic(question, k=5)

        if not hits:
            entry_count = len(self.store.all_entries())
            if entry_count == 0:
                return AskResult(
                    answer=(
                        "Knowledge base is empty. "
                        "Run 'village scribe fetch <source>' to add content."
                    ),
                    sources=[],
                    saved=False,
                    error="empty_wiki",
                )
            return AskResult(
                answer=(
                    "No pages matched your query. "
                    "Try different keywords or check what's available "
                    "with 'village scribe curate'."
                ),
                sources=[],
                saved=False,
                error="no_matches",
            )

        context_parts = []
        source_ids = []
        for hit in hits:
            context_parts.append(f"[{hit.id}] {hit.title}\n{hit.text}")
            source_ids.append(hit.id)

        answer = "\n\n".join(context_parts)

        saved = False
        if save and answer:
            tags = ["synthesized", "query-result"]
            self.store.put(
                title=f"Q: {question[:80]}",
                text=answer,
                tags=tags,
                metadata={"synthesized_from": source_ids},
            )
            saved = True

        return AskResult(answer=answer, sources=source_ids, saved=saved)
