"""
Unit tests for the Haystack Ingestion Pipeline.
Mocks Db2 stores and SentenceTransformer to avoid live connections.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

from src.knowledge.ingestion_pipeline import (
    IngestionPipeline,
    _clean_text,
    _split_into_chunks,
    _stable_id,
    _rough_token_count,
)


# ── Text helper tests ─────────────────────────────────────────────────────────

class TestCleanText:
    def test_collapses_multiple_blank_lines(self):
        text = "line1\n\n\n\nline2"
        result = _clean_text(text)
        assert "\n\n\n" not in result

    def test_removes_horizontal_rules(self):
        text = "section\n---\ncontent"
        result = _clean_text(text)
        assert "---" not in result

    def test_collapses_multiple_spaces(self):
        text = "word1    word2   word3"
        result = _clean_text(text)
        assert "  " not in result

    def test_strips_leading_trailing_whitespace(self):
        text = "  hello world  "
        assert _clean_text(text) == "hello world"


class TestSplitIntoChunks:
    def test_short_text_produces_one_chunk(self):
        text = "Short text that fits in one chunk."
        chunks = _split_into_chunks(text, chunk_tokens=512, overlap_tokens=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_produces_multiple_chunks(self):
        # ~2000 words × ~5 chars = 10000 chars ≈ 2500 tokens
        words = ["word"] * 2000
        text = " ".join(words)
        chunks = _split_into_chunks(text, chunk_tokens=512, overlap_tokens=50)
        assert len(chunks) > 1

    def test_chunks_are_non_empty(self):
        text = "hello world " * 300
        chunks = _split_into_chunks(text, chunk_tokens=128, overlap_tokens=20)
        for c in chunks:
            assert c.strip() != ""

    def test_empty_text_returns_empty_list(self):
        chunks = _split_into_chunks("", chunk_tokens=512, overlap_tokens=50)
        assert chunks == []


class TestStableId:
    def test_same_inputs_produce_same_id(self):
        id1 = _stable_id("sops/delay.md", 0)
        id2 = _stable_id("sops/delay.md", 0)
        assert id1 == id2

    def test_different_chunk_index_produces_different_id(self):
        id1 = _stable_id("sops/delay.md", 0)
        id2 = _stable_id("sops/delay.md", 1)
        assert id1 != id2

    def test_id_is_32_chars(self):
        assert len(_stable_id("any/file.md", 5)) == 32


# ── Pipeline integration tests (mocked) ──────────────────────────────────────

@pytest.fixture()
def mock_stores():
    """Mock both Db2DocumentStore and Db2VectorStore."""
    doc_store = MagicMock()
    vec_store = MagicMock()
    doc_store.write_documents.return_value = 5
    vec_store.write_vectors.return_value = 5
    return doc_store, vec_store


@pytest.fixture()
def pipeline_with_mocks(tmp_path, mock_stores):
    """IngestionPipeline with mocked stores and a small data directory."""
    doc_store, vec_store = mock_stores

    # Create a minimal test document
    data_dir = tmp_path / "data"
    (data_dir / "sops").mkdir(parents=True)
    (data_dir / "sops" / "test_sop.md").write_text(
        "# Test SOP\nThis is a test document for ingestion.\n" * 20
    )

    with patch("src.knowledge.ingestion_pipeline.Db2DocumentStore", return_value=doc_store), \
         patch("src.knowledge.ingestion_pipeline.Db2VectorStore", return_value=vec_store), \
         patch("src.knowledge.ingestion_pipeline.SentenceTransformer") as mock_st:

        # SentenceTransformer.encode returns fake embeddings
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 384).astype("float32")
        mock_st.return_value = mock_model

        pipeline = IngestionPipeline()
        pipeline._data_dir = data_dir
        pipeline._embedder = mock_model
        pipeline._doc_store = doc_store
        pipeline._vec_store = vec_store

        yield pipeline, doc_store, vec_store


class TestIngestionPipeline:
    def test_discover_files_finds_markdown(self, pipeline_with_mocks):
        pipeline, _, _ = pipeline_with_mocks
        files = pipeline.discover_files()
        assert len(files) == 1
        assert files[0].suffix == ".md"

    def test_run_calls_write_documents(self, pipeline_with_mocks):
        pipeline, doc_store, vec_store = pipeline_with_mocks
        pipeline._doc_store.connect = MagicMock()
        pipeline._vec_store.connect = MagicMock()
        pipeline._doc_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._doc_store.close = MagicMock()
        pipeline._vec_store.close = MagicMock()

        summary = pipeline.run(wipe_first=False)

        doc_store.write_documents.assert_called_once()
        vec_store.write_vectors.assert_called_once()
        assert "chunk_count" in summary
        assert "doc_inserted" in summary
        assert "vec_inserted" in summary

    def test_run_with_wipe_calls_delete_all(self, pipeline_with_mocks):
        pipeline, doc_store, vec_store = pipeline_with_mocks
        pipeline._doc_store.connect = MagicMock()
        pipeline._vec_store.connect = MagicMock()
        pipeline._doc_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._doc_store.close = MagicMock()
        pipeline._vec_store.close = MagicMock()

        pipeline.run(wipe_first=True)

        doc_store.delete_all_documents.assert_called_once()
        vec_store.delete_all_vectors.assert_called_once()
