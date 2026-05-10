"""Tests for the embedding search feature (EmbeddingCache, MemoryStore, ScribeStore)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import numpy as np
import pytest

from village.memory import MemoryStore
from village.memory.embeddings import EmbeddingCache, _cosine_similarity
from village.scribe.store import ScribeStore


# ---------------------------------------------------------------------------
# 1. EmbeddingCache unit tests
# ---------------------------------------------------------------------------


class TestCosineSimilarityBasic:
    def test_identical_vectors_are_one(self) -> None:
        v = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
        result = _cosine_similarity(v, v.reshape(1, -1))
        np.testing.assert_almost_equal(result, [1.0], decimal=5)

    def test_orthogonal_vectors_are_zero(self) -> None:
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([[0.0, 1.0]], dtype=np.float32)
        result = _cosine_similarity(a, b)
        np.testing.assert_almost_equal(result, [0.0], decimal=5)


class TestEmbedCacheInitEmpty:
    def test_new_cache_has_no_entries(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        assert cache.get("any-id") is None

    def test_new_cache_needs_embedding_returns_all(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        missing = cache.needs_embedding({"a", "b", "c"})
        assert set(missing) == {"a", "b", "c"}


class TestEmbedCachePersistence:
    def test_put_then_reload_retains_data(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "embeddings.json"
        cache = EmbeddingCache(cache_path=cache_path)
        cache.put("entry-1", [0.1, 0.2, 0.3])
        cache.put("entry-2", [0.4, 0.5, 0.6])

        # Reload from disk
        cache2 = EmbeddingCache(cache_path=cache_path)
        np.testing.assert_array_almost_equal(cache2.get("entry-1"), [0.1, 0.2, 0.3])
        np.testing.assert_array_almost_equal(cache2.get("entry-2"), [0.4, 0.5, 0.6])


class TestEmbedCacheRemove:
    def test_remove_deletes_entry(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        cache.put("entry-1", [0.1, 0.2, 0.3])
        assert cache.get("entry-1") is not None

        cache.remove("entry-1")
        assert cache.get("entry-1") is None

    def test_remove_nonexistent_no_crash(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        cache.remove("does-not-exist")  # should not raise


class TestEmbedCacheNeedsEmbedding:
    def test_returns_unembedded_ids(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        cache.put("entry-1", [0.1, 0.2, 0.3])
        cache.put("entry-2", [0.4, 0.5, 0.6])

        missing = cache.needs_embedding({"entry-1", "entry-2", "entry-3"})
        assert missing == ["entry-3"]


class TestEmbedTextSuccess:
    @patch("village.memory.embeddings.httpx.post")
    def test_returns_embedding_list(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3, 0.4]]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        cache = EmbeddingCache(cache_path=Path("/dev/null"), ollama_url="http://localhost:11434")
        result = cache.embed_text("hello world")

        assert result == [0.1, 0.2, 0.3, 0.4]
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": "hello world"},
            timeout=30.0,
        )


class TestEmbedTextOllamaDown:
    @patch("village.memory.embeddings.httpx.post")
    def test_returns_none_on_httpx_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.RequestError("Connection refused")

        cache = EmbeddingCache(cache_path=Path("/dev/null"), ollama_url="http://localhost:11434")
        result = cache.embed_text("hello world")

        assert result is None


class TestFindReturnsRanked:
    @patch("village.memory.embeddings.httpx.post")
    def test_top_k_sorted_by_similarity(self, mock_post: MagicMock, tmp_path: Path) -> None:
        # Query embedding: similar to entry-2 but not entry-1
        query_emb = [1.0, 0.0]  # unit vector along x
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [query_emb]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        # entry-1: along y-axis (orthogonal)
        cache.put("entry-1", [0.0, 1.0])
        # entry-2: along x-axis (identical to query)
        cache.put("entry-2", [1.0, 0.0])
        # entry-3: diagonal
        cache.put("entry-3", [0.7, 0.7])

        results = cache.find("query", ["entry-1", "entry-2", "entry-3"], k=3)

        assert len(results) == 3
        ids = [r[0] for r in results]
        scores = [r[1] for r in results]
        # entry-2 should be first (highest similarity), entry-1 last
        assert ids[0] == "entry-2"
        assert ids[2] == "entry-1"
        # Scores should be descending
        assert scores[0] >= scores[1] >= scores[2]


class TestFindNoCandidates:
    @patch("village.memory.embeddings.httpx.post")
    def test_no_cached_embeddings_returns_empty(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2]]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        # No entries cached
        results = cache.find("query", ["entry-1", "entry-2"])

        assert results == []


class TestFindOllamaDown:
    @patch("village.memory.embeddings.httpx.post")
    def test_ollama_unavailable_returns_empty(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_post.side_effect = httpx.RequestError("Connection refused")

        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        cache.put("entry-1", [0.1, 0.2])

        results = cache.find("query", ["entry-1"])

        assert results == []


class TestRebuild:
    @patch("village.memory.embeddings.httpx.post")
    def test_all_entries_get_embedded(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.5, 0.5]]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        count = cache.rebuild({"e1": "text one", "e2": "text two", "e3": "text three"})

        assert count == 3
        assert mock_post.call_count == 3
        assert cache.get("e1") is not None
        assert cache.get("e2") is not None
        assert cache.get("e3") is not None

    @patch("village.memory.embeddings.httpx.post")
    def test_rebuild_clears_old_cache(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.5, 0.5]]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        cache = EmbeddingCache(cache_path=tmp_path / "embeddings.json")
        cache.put("old-entry", [0.1, 0.2])
        cache.rebuild({"new-entry": "fresh text"})

        assert cache.get("old-entry") is None
        assert cache.get("new-entry") is not None


class TestAvailableTrue:
    @patch("village.memory.embeddings.httpx.get")
    def test_ollama_reachable(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        cache = EmbeddingCache(cache_path=Path("/dev/null"), ollama_url="http://localhost:11434")
        assert cache.available is True
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=30.0)


class TestAvailableFalse:
    @patch("village.memory.embeddings.httpx.get")
    def test_ollama_unreachable(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.RequestError("Connection refused")

        cache = EmbeddingCache(cache_path=Path("/dev/null"), ollama_url="http://localhost:11434")
        assert cache.available is False

    @patch("village.memory.embeddings.httpx.get")
    def test_ollama_non_200(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        cache = EmbeddingCache(cache_path=Path("/dev/null"), ollama_url="http://localhost:11434")
        assert cache.available is False


# ---------------------------------------------------------------------------
# 2. MemoryStore integration tests
# ---------------------------------------------------------------------------


class TestMemoryStoreBackwardCompat:
    def test_no_ollama_still_works(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        eid = store.put("Title", "Some content", tags=["tag1"])
        assert eid != ""
        assert store.get(eid) is not None
        assert store.find("content") != []

    def test_no_embed_cache_attribute(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        assert store._embed_cache is None


class TestMemoryStoreWithOllamaCreatesCache:
    def test_creates_embedding_cache(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        assert store._embed_cache is not None
        assert isinstance(store._embed_cache, EmbeddingCache)

    def test_cache_path_location(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        assert store._embed_cache.cache_path == tmp_path / "embeddings.json"

    def test_custom_model_forwarded(self, tmp_path: Path) -> None:
        store = MemoryStore(
            tmp_path, ollama_url="http://ollama:11434", embed_model="custom-model"
        )
        assert store._embed_cache.model == "custom-model"
        assert store._embed_cache.ollama_url == "http://ollama:11434"


class TestPutComputesEmbedding:
    def test_put_calls_put_text(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store._embed_cache = MagicMock(spec=EmbeddingCache)
        store._embed_cache.put_text.return_value = True

        eid = store.put("Auth Setup", "Configure tokens", tags=["auth"])

        store._embed_cache.put_text.assert_called_once()
        call_args = store._embed_cache.put_text.call_args
        assert call_args[0][0] == eid
        assert "Auth Setup" in call_args[0][1]
        assert "Configure tokens" in call_args[0][1]


class TestPutEmbeddingFailureNoCrash:
    def test_put_succeeds_when_embed_fails(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store._embed_cache = MagicMock(spec=EmbeddingCache)
        store._embed_cache.put_text.return_value = False

        eid = store.put("Title", "Content", tags=["tag"])

        assert eid != ""
        # Entry should still be stored
        entry = store.get(eid)
        assert entry is not None
        assert entry.title == "Title"
        assert entry.text == "Content"

    def test_put_succeeds_when_embed_raises(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store._embed_cache = MagicMock(spec=EmbeddingCache)
        store._embed_cache.put_text.side_effect = RuntimeError("boom")

        eid = store.put("Title", "Content")

        assert eid != ""
        entry = store.get(eid)
        assert entry is not None


class TestFindSemanticNoCacheFallsBack:
    def test_no_ollama_url_falls_back_to_keyword(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put("Auth Setup", "Configure tokens", tags=["auth"])
        store.put("Deploy Guide", "kubectl apply", tags=["deploy"])

        results = store.find_semantic("auth")
        assert len(results) >= 1
        assert any("auth" in e.title.lower() for e in results)


class TestFindSemanticWithResults:
    def test_returns_ranked_entries(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store.put("Auth Setup", "Configure tokens", tags=["auth"])
        store.put("Deploy Guide", "kubectl apply", tags=["deploy"])

        # Mock the embedding cache to return controlled results
        mock_cache = MagicMock(spec=EmbeddingCache)
        mock_cache.find.return_value = [
            ("note-002", 0.95),
            ("note-001", 0.42),
        ]
        store._embed_cache = mock_cache

        results = store.find_semantic("auth")
        assert len(results) == 2
        assert results[0].id == "note-002"
        assert results[1].id == "note-001"

    def test_respects_k_parameter(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store.put("A", "text a")
        store.put("B", "text b")
        store.put("C", "text c")

        mock_cache = MagicMock(spec=EmbeddingCache)
        mock_cache.find.return_value = [
            ("note-003", 0.9),
            ("note-002", 0.8),
            ("note-001", 0.7),
        ]
        store._embed_cache = mock_cache

        results = store.find_semantic("query", k=2)
        assert len(results) == 2


class TestFindSemanticEmptyStore:
    def test_empty_store_returns_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        results = store.find_semantic("anything")
        assert results == []

    def test_empty_store_no_cache(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        results = store.find_semantic("anything")
        assert results == []


class TestFindSemanticOllamaDownFallsBack:
    def test_embed_returns_empty_falls_back_to_keyword(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store.put("Auth Setup", "Configure authentication tokens", tags=["auth"])

        # Simulate Ollama being down (find returns empty list)
        mock_cache = MagicMock(spec=EmbeddingCache)
        mock_cache.find.return_value = []
        store._embed_cache = mock_cache

        results = store.find_semantic("auth")
        # Should fall back to keyword search
        assert len(results) >= 1
        assert any("auth" in e.title.lower() for e in results)


class TestDeleteRemovesEmbedding:
    def test_delete_calls_embed_cache_remove(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store._embed_cache = MagicMock(spec=EmbeddingCache)

        eid = store.put("Title", "Content", tags=["tag"])
        store.delete(eid)

        store._embed_cache.remove.assert_called_once_with(eid)

    def test_delete_without_cache_no_crash(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        eid = store.put("Title", "Content", tags=["tag"])
        result = store.delete(eid)
        assert result is True


class TestRebuildEmbeddings:
    def test_calls_cache_rebuild_with_all_entries(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path, ollama_url="http://localhost:11434")
        store.put("Auth", "Setup tokens", tags=["auth"])
        store.put("Deploy", "kubectl apply", tags=["deploy"])

        store._embed_cache = MagicMock(spec=EmbeddingCache)
        store._embed_cache.rebuild.return_value = 2

        count = store.rebuild_embeddings()

        assert count == 2
        store._embed_cache.rebuild.assert_called_once()
        call_kwargs = store._embed_cache.rebuild.call_args
        entries_dict = call_kwargs[0][0]
        assert "note-001" in entries_dict
        assert "note-002" in entries_dict
        assert "Auth" in entries_dict["note-001"]

    def test_no_cache_returns_zero(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        count = store.rebuild_embeddings()
        assert count == 0


# ---------------------------------------------------------------------------
# 3. ScribeStore integration tests
# ---------------------------------------------------------------------------


class TestScribeAskUsesSemanticWhenConfigured:
    def test_ask_calls_find_semantic(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki", ollama_url="http://localhost:11434")

        md = tmp_path / "auth.md"
        md.write_text("# Auth\nConfigure tokens", encoding="utf-8")
        elder.see(str(md))

        # Mock find_semantic on the underlying MemoryStore
        with patch.object(elder.store, "find_semantic", wraps=elder.store.find_semantic) as spy:
            elder.ask("auth")
            spy.assert_called_once_with("auth", k=5)

    def test_ask_returns_semantic_results(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki", ollama_url="http://localhost:11434")

        md = tmp_path / "auth.md"
        md.write_text("# Auth\nConfigure tokens", encoding="utf-8")
        elder.see(str(md))

        # Mock find_semantic to return specific entry
        original_entries = elder.store.all_entries()
        with patch.object(
            elder.store,
            "find_semantic",
            return_value=original_entries,
        ):
            result = elder.ask("auth")
            assert result.error == ""
            assert len(result.sources) >= 1


class TestScribeAskKeywordWhenNoOllama:
    def test_ask_falls_back_to_keyword(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md = tmp_path / "auth.md"
        md.write_text("# Auth\nConfigure tokens", encoding="utf-8")
        elder.see(str(md))

        # Verify find_semantic is called (it falls back internally to keyword)
        with patch.object(elder.store, "find_semantic", wraps=elder.store.find_semantic) as spy:
            result = elder.ask("auth")
            spy.assert_called_once()
            assert len(result.sources) >= 1
            assert result.error == ""

    def test_ask_no_ollama_empty_wiki(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")
        result = elder.ask("anything")

        assert "Knowledge base is empty" in result.answer
        assert result.error == "empty_wiki"

    def test_ask_no_ollama_no_matches(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md = tmp_path / "cooking.md"
        md.write_text("# Cooking\nHow to bake bread", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("quantum physics")
        assert "No pages matched" in result.answer
        assert result.error == "no_matches"
