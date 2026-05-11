"""Tests for MemoryConfig embed settings."""

import os
import pytest

from village.config._sub_configs import MemoryConfig


class TestMemoryConfigEmbedSettings:
    """MemoryConfig.ollama_url and embed_model resolution from env vars and config dict."""

    def test_defaults_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """By default, embed fields are empty strings (semantic search disabled)."""
        monkeypatch.delenv("VILLAGE_EMBED_URL", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("VILLAGE_EMBED_MODEL", raising=False)
        config = MemoryConfig.from_env_and_config({})
        assert config.ollama_url == ""
        assert config.embed_model == ""

    def test_village_embed_url_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VILLAGE_EMBED_URL takes highest priority."""
        monkeypatch.setenv("VILLAGE_EMBED_URL", "http://llm.lan:11434")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://other:11434")
        config = MemoryConfig.from_env_and_config({})
        assert config.ollama_url == "http://llm.lan:11434"

    def test_ollama_base_url_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OLLAMA_BASE_URL is used when VILLAGE_EMBED_URL is not set."""
        monkeypatch.delenv("VILLAGE_EMBED_URL", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://llm.lan:11434")
        config = MemoryConfig.from_env_and_config({})
        assert config.ollama_url == "http://llm.lan:11434"

    def test_config_dict_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config dict memory.ollama_url is used when no env vars are set."""
        monkeypatch.delenv("VILLAGE_EMBED_URL", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        config = MemoryConfig.from_env_and_config({"memory.ollama_url": "http://config:11434"})
        assert config.ollama_url == "http://config:11434"

    def test_config_dict_legacy_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy MEMORY.OLLAMA_URL key also works."""
        monkeypatch.delenv("VILLAGE_EMBED_URL", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        config = MemoryConfig.from_env_and_config({"MEMORY.OLLAMA_URL": "http://legacy:11434"})
        assert config.ollama_url == "http://legacy:11434"

    def test_env_overrides_config_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var always wins over config dict."""
        monkeypatch.setenv("VILLAGE_EMBED_URL", "http://env:11434")
        config = MemoryConfig.from_env_and_config({"memory.ollama_url": "http://config:11434"})
        assert config.ollama_url == "http://env:11434"

    def test_embed_model_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VILLAGE_EMBED_MODEL sets the embed model."""
        monkeypatch.setenv("VILLAGE_EMBED_MODEL", "nomic-embed-text")
        config = MemoryConfig.from_env_and_config({})
        assert config.embed_model == "nomic-embed-text"

    def test_embed_model_config_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config dict memory.embed_model is used when env var not set."""
        monkeypatch.delenv("VILLAGE_EMBED_MODEL", raising=False)
        config = MemoryConfig.from_env_and_config({"memory.embed_model": "all-minilm"})
        assert config.embed_model == "all-minilm"

    def test_embed_model_legacy_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy MEMORY.EMBED_MODEL key also works."""
        monkeypatch.delenv("VILLAGE_EMBED_MODEL", raising=False)
        config = MemoryConfig.from_env_and_config({"MEMORY.EMBED_MODEL": "custom-model"})
        assert config.embed_model == "custom-model"

    def test_both_fields_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both ollama_url and embed_model resolve correctly together."""
        monkeypatch.setenv("VILLAGE_EMBED_URL", "http://llm.lan:11434")
        monkeypatch.setenv("VILLAGE_EMBED_MODEL", "nomic-embed-text")
        config = MemoryConfig.from_env_and_config({})
        assert config.ollama_url == "http://llm.lan:11434"
        assert config.embed_model == "nomic-embed-text"

    def test_min_similarity_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default min_similarity is 0.0 (no filtering)."""
        monkeypatch.delenv("VILLAGE_MIN_SIMILARITY", raising=False)
        config = MemoryConfig.from_env_and_config({})
        assert config.min_similarity == 0.0

    def test_min_similarity_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VILLAGE_MIN_SIMILARITY env var sets the threshold."""
        monkeypatch.setenv("VILLAGE_MIN_SIMILARITY", "0.3")
        config = MemoryConfig.from_env_and_config({})
        assert config.min_similarity == 0.3

    def test_min_similarity_from_config_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config dict memory.min_similarity is used when env var not set."""
        monkeypatch.delenv("VILLAGE_MIN_SIMILARITY", raising=False)
        config = MemoryConfig.from_env_and_config({"memory.min_similarity": "0.5"})
        assert config.min_similarity == 0.5

    def test_min_similarity_legacy_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy MEMORY.MIN_SIMILARITY key also works."""
        monkeypatch.delenv("VILLAGE_MIN_SIMILARITY", raising=False)
        config = MemoryConfig.from_env_and_config({"MEMORY.MIN_SIMILARITY": "0.7"})
        assert config.min_similarity == 0.7
