import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from village.scribe.store import MAX_DISTILL_SIZE, ScribeStore


class TestSeeWithMarkdownFile:
    def test_ingests_markdown_file(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "auth-setup.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("# Auth Setup\nRequires VILLAGE_AUTH_KEY env var.", encoding="utf-8")

        elder = ScribeStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        assert result.entry_id != ""
        assert result.title == "auth-setup"
        assert result.tags == ["auth-setup"]


class TestSeeWithTextFile:
    def test_ingests_text_file(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "notes" / "deploy-guide.txt"
        txt_file.parent.mkdir(parents=True)
        txt_file.write_text("Deploy using kubectl apply -f manifest.yaml", encoding="utf-8")

        elder = ScribeStore(tmp_path / "wiki")
        result = elder.see(str(txt_file))

        assert result.status == "success"
        assert result.title == "deploy-guide"
        assert result.tags == ["deploy-guide"]


class TestSeeWithInvalidSource:
    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")
        result = elder.see(str(tmp_path / "nonexistent.md"))

        assert result.status == "error"
        assert result.entry_id == ""
        assert "not found" in result.error.lower() or "no such" in result.error.lower()


class TestLogAppended:
    def test_log_md_appended_after_see(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "config-notes.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("Configuration details here", encoding="utf-8")

        elder = ScribeStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        assert elder.log_path.exists()

        log_content = elder.log_path.read_text(encoding="utf-8")
        assert "# Ingest Log" in log_content
        assert result.entry_id in log_content
        assert "config-notes" in log_content


class TestIndexUpdated:
    def test_index_md_updated_after_see(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "testing-strategy.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("Use pytest for all testing", encoding="utf-8")

        elder = ScribeStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        index_path = elder.pages_dir / "index.md"
        assert index_path.exists()

        index_content = index_path.read_text(encoding="utf-8")
        assert "# Memory Index" in index_content
        assert result.entry_id in index_content


class TestFileMovedToProcessed:
    def test_ingest_file_moved_to_processed(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")
        elder._ensure_dirs()

        ingest_file = elder.ingest_dir / "readme.md"
        ingest_file.write_text("# Readme\nProject readme content", encoding="utf-8")

        result = elder.see(str(ingest_file))

        assert result.status == "success"
        assert not ingest_file.exists()
        processed_file = elder.processed_dir / "readme.md"
        assert processed_file.exists()
        content = processed_file.read_text(encoding="utf-8")
        assert "Project readme content" in content


class TestAskWithMatchingPages:
    def test_returns_relevant_pages(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md1 = tmp_path / "auth.md"
        md1.write_text("# Auth Setup\nConfigure authentication tokens", encoding="utf-8")
        elder.see(str(md1))

        md2 = tmp_path / "deploy.md"
        md2.write_text("# Deploy Guide\nDeploy using kubectl apply", encoding="utf-8")
        elder.see(str(md2))

        result = elder.ask("auth")

        assert "auth" in result.answer.lower()
        assert len(result.sources) >= 1
        assert result.saved is False


class TestAskWithNoMatches:
    def test_returns_no_relevant_message(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md = tmp_path / "cooking.md"
        md.write_text("# Cooking\nHow to bake bread", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("quantum physics")

        assert "No pages matched your query" in result.answer
        assert result.sources == []
        assert result.saved is False
        assert result.error == "no_matches"


class TestAskWithEmptyWiki:
    def test_returns_empty_wiki_message(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")
        result = elder.ask("anything")

        assert "Knowledge base is empty" in result.answer
        assert "village scribe fetch" in result.answer
        assert result.sources == []
        assert result.error == "empty_wiki"


class TestAskWithSave:
    def test_creates_new_page_when_save_true(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md = tmp_path / "config.md"
        md.write_text("# Config\nSet VILLAGE_HOME directory", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("config", save=True)

        assert result.saved is True
        assert len(result.sources) >= 1

        entries = elder.store.all_entries()
        synthesized = [e for e in entries if "synthesized" in e.tags]
        assert len(synthesized) == 1
        assert synthesized[0].title.startswith("Q: config")


class TestAskSourcesPopulated:
    def test_sources_match_hit_ids(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md1 = tmp_path / "logging.md"
        md1.write_text("# Logging\nConfigure structured logging", encoding="utf-8")
        elder.see(str(md1))

        md2 = tmp_path / "logrotate.md"
        md2.write_text("# Log Rotation\nRotate logs daily", encoding="utf-8")
        elder.see(str(md2))

        result = elder.ask("log")

        assert len(result.sources) >= 1
        assert all(isinstance(s, str) for s in result.sources)
        for source_id in result.sources:
            entry = elder.store.get(source_id)
            assert entry is not None


class TestDistillUnderThreshold:
    def test_returns_text_as_is_when_under_threshold(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        short_text = "Short content"
        text, failed = store._distill(short_text, "test-doc")
        assert text == short_text
        assert failed is False

    def test_returns_text_as_is_at_exact_threshold(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        text_input = "a" * MAX_DISTILL_SIZE
        text, failed = store._distill(text_input, "test-doc")
        assert text == text_input
        assert failed is False


class TestDistillWithLLMUnavailable:
    def test_falls_back_to_truncation(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        long_text = "a" * (MAX_DISTILL_SIZE + 100)

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client", side_effect=RuntimeError("LLM unavailable")),
        ):
            text, failed = store._distill(long_text, "test-doc")

        assert len(text) < len(long_text)
        assert "Content truncated" in text
        assert f"original was {len(long_text)} chars" in text
        assert failed is True


class TestDistillWithLLMSuccess:
    def test_calls_llm_and_returns_distilled_text(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        long_text = "a" * (MAX_DISTILL_SIZE + 100)
        mock_llm = MagicMock()
        mock_llm.call.return_value = "Distilled summary of key facts"

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client", return_value=mock_llm),
        ):
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            text, failed = store._distill(long_text, "test-doc")

        assert text == "Distilled summary of key facts"
        assert failed is False
        mock_llm.call.assert_called_once()


class TestRawFlag:
    def test_raw_bypasses_distillation(self, tmp_path: Path) -> None:
        large_content = "Large File\n" + ("This is filler content. " * 500)
        md_file = tmp_path / "large.md"
        md_file.write_text(large_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client") as mock_get_llm,
        ):
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_llm = MagicMock()
            mock_llm.call.return_value = "Distilled summary"
            mock_get_llm.return_value = mock_llm

            result_raw = store.see(str(md_file), raw=True)
            result_distilled = store.see(str(md_file), raw=False)

        mock_llm.call.assert_called_once()

        raw_entry = store.store.get(result_raw.entry_id)
        distilled_entry = store.store.get(result_distilled.entry_id)
        assert raw_entry is not None
        assert distilled_entry is not None
        assert raw_entry.text.strip() == large_content.strip()
        assert distilled_entry.text == "Distilled summary"


class TestSeeWithAndWithoutRaw:
    def test_see_default_distills_large_files(self, tmp_path: Path) -> None:
        large_content = "x" * (MAX_DISTILL_SIZE + 50)
        md_file = tmp_path / "big.md"
        md_file.write_text(large_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client") as mock_get_llm,
        ):
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_llm = MagicMock()
            mock_llm.call.return_value = "Distilled key insights"
            mock_get_llm.return_value = mock_llm

            result = store.see(str(md_file))

        assert result.status == "success"
        entry = store.store.get(result.entry_id)
        assert entry is not None
        assert entry.text == "Distilled key insights"

    def test_see_small_file_unchanged(self, tmp_path: Path) -> None:
        small_content = "Small content"
        md_file = tmp_path / "small.md"
        md_file.write_text(small_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")
        result = store.see(str(md_file))

        assert result.status == "success"
        entry = store.store.get(result.entry_id)
        assert entry is not None
        assert entry.text == small_content


class TestIngestResultDistillFailed:
    def test_see_small_file_distill_not_failed(self, tmp_path: Path) -> None:
        small_content = "Small content"
        md_file = tmp_path / "small.md"
        md_file.write_text(small_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")
        result = store.see(str(md_file))

        assert result.distill_failed is False

    def test_see_large_file_without_llm_sets_distill_failed(self, tmp_path: Path) -> None:
        large_content = "x" * (MAX_DISTILL_SIZE + 50)
        md_file = tmp_path / "big.md"
        md_file.write_text(large_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client", side_effect=RuntimeError("LLM unavailable")),
        ):
            result = store.see(str(md_file))

        assert result.status == "success"
        assert result.distill_failed is True

    def test_see_large_file_with_llm_success_distill_not_failed(self, tmp_path: Path) -> None:
        large_content = "x" * (MAX_DISTILL_SIZE + 50)
        md_file = tmp_path / "big.md"
        md_file.write_text(large_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")

        with (
            patch("village.config.get_config") as mock_get_config,
            patch("village.llm.factory.get_llm_client") as mock_get_llm,
        ):
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_llm = MagicMock()
            mock_llm.call.return_value = "Distilled key insights"
            mock_get_llm.return_value = mock_llm

            result = store.see(str(md_file))

        assert result.status == "success"
        assert result.distill_failed is False

    def test_see_raw_flag_distill_not_failed(self, tmp_path: Path) -> None:
        large_content = "x" * (MAX_DISTILL_SIZE + 50)
        md_file = tmp_path / "big.md"
        md_file.write_text(large_content, encoding="utf-8")

        store = ScribeStore(tmp_path / "wiki")
        result = store.see(str(md_file), raw=True)

        assert result.status == "success"
        assert result.distill_failed is False


class TestSeeFileMoveError:
    def test_oserror_on_move_logged(self, tmp_path: Path, caplog) -> None:
        store = ScribeStore(tmp_path / "wiki")
        store._ensure_dirs()

        ingest_file = store.ingest_dir / "readme.md"
        ingest_file.write_text("# Readme\nProject readme content", encoding="utf-8")

        with patch("pathlib.Path.rename", side_effect=OSError("Permission denied")):
            with caplog.at_level(logging.WARNING):
                result = store.see(str(ingest_file))

        assert result.status == "success"
        assert any("Failed to move" in rec.message for rec in caplog.records)


class TestExtractUrlFallbackWarning:
    def test_trafilatura_none_logs_warning(self, tmp_path: Path, caplog) -> None:
        store = ScribeStore(tmp_path / "wiki")
        mock_response = MagicMock()
        mock_response.text = "<html><body>raw</body></html>"
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.get", return_value=mock_response),
            patch("trafilatura.bare_extraction", return_value=None),
            caplog.at_level(logging.WARNING),
        ):
            title, text = store._extract_url("https://example.com")

        assert title == "https://example.com"
        assert text == "<html><body>raw</body></html>"
        assert any(
            "Trafilatura extraction failed" in rec.message for rec in caplog.records
        )


class TestAskSuccessfulNoError:
    def test_ask_with_matches_has_no_error(self, tmp_path: Path) -> None:
        elder = ScribeStore(tmp_path / "wiki")

        md = tmp_path / "auth.md"
        md.write_text("# Auth\nConfigure tokens", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("auth")

        assert result.error == ""
        assert len(result.sources) >= 1
