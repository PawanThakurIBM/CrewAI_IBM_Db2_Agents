"""
Unit tests for the Haystack Ingestion Pipeline.

Tests the real Haystack Pipeline components (converter, cleaner, splitter,
embedder, writer) with mocked Db2 stores — no live Db2 or model loading.

IBMDb2DocumentStore (ibm-db-haystack) is the official Haystack integration
for IBM Db2. It is mocked at the class level — no live Db2 needed.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from haystack import Document
from haystack.document_stores.types import DuplicatePolicy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_doc(content: str, file_path: str = "sops/test.md") -> Document:
    return Document(content=content, meta={"file_path": file_path})


# ── Haystack component smoke tests ────────────────────────────────────────────

class TestDocumentSplitter:
    """Verify Haystack DocumentSplitter behaves as expected for our config."""

    def test_short_text_produces_one_chunk(self):
        from haystack.components.preprocessors import DocumentSplitter
        splitter = DocumentSplitter(split_by="word", split_length=512, split_overlap=50)
        docs = splitter.run(documents=[_make_doc("Short text.")])
        assert len(docs["documents"]) == 1

    def test_long_text_produces_multiple_chunks(self):
        from haystack.components.preprocessors import DocumentSplitter
        splitter = DocumentSplitter(split_by="word", split_length=50, split_overlap=5)
        long_text = "word " * 300
        docs = splitter.run(documents=[_make_doc(long_text)])
        assert len(docs["documents"]) > 1

    def test_chunks_are_non_empty(self):
        from haystack.components.preprocessors import DocumentSplitter
        splitter = DocumentSplitter(split_by="word", split_length=50, split_overlap=5)
        docs = splitter.run(documents=[_make_doc("word " * 300)])
        for doc in docs["documents"]:
            assert doc.content and doc.content.strip()

    def test_empty_document_produces_no_chunks(self):
        from haystack.components.preprocessors import DocumentSplitter
        splitter = DocumentSplitter(split_by="word", split_length=512, split_overlap=50)
        docs = splitter.run(documents=[_make_doc("")])
        # Haystack either produces 0 or 1 empty doc — content must not be meaningful
        contents = [d.content for d in docs["documents"] if d.content and d.content.strip()]
        assert contents == []


class TestDocumentCleaner:
    """Verify Haystack DocumentCleaner strips noise."""

    def test_removes_extra_whitespace(self):
        from haystack.components.preprocessors import DocumentCleaner
        cleaner = DocumentCleaner(remove_extra_whitespaces=True)
        docs = cleaner.run(documents=[_make_doc("word1    word2   word3")])
        assert "  " not in docs["documents"][0].content

    def test_removes_empty_lines(self):
        from haystack.components.preprocessors import DocumentCleaner
        cleaner = DocumentCleaner(remove_empty_lines=True)
        docs = cleaner.run(documents=[_make_doc("line1\n\n\nline2")])
        assert "\n\n\n" not in docs["documents"][0].content


# ── IngestionPipeline integration tests (Haystack pipeline mocked) ────────────

@pytest.fixture()
def pipeline_with_mocks(tmp_path):
    """
    IngestionPipeline with Haystack pipeline fully mocked.
    The real Haystack Pipeline.run() is replaced so no model loads.
    IBMDb2DocumentStore is mocked at the class level — no live Db2 needed.
    """
    data_dir = tmp_path / "data"
    (data_dir / "sops").mkdir(parents=True)
    (data_dir / "sops" / "test_sop.md").write_text(
        "# Test SOP\nThis is a test document for ingestion testing.\n" * 10
    )

    doc_store = MagicMock()
    vec_store = MagicMock()
    doc_store.write_documents.return_value = 3
    vec_store.write_vectors.return_value = 3

    fake_docs = [
        Document(id=f"doc{i}", content=f"chunk {i}", meta={"file_path": "sops/test_sop.md"},
                 embedding=[0.1] * 384)
        for i in range(3)
    ]

    fake_pipeline_result = {
        "writer": {"documents_written": 3},
        "embedder": {"documents": fake_docs},
    }

    with patch("src.knowledge.ingestion_pipeline.IBMDb2DocumentStore", return_value=doc_store), \
         patch("src.knowledge.ingestion_pipeline.Db2VectorStore", return_value=vec_store), \
         patch("src.knowledge.ingestion_pipeline.Pipeline") as mock_pipeline_cls:

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = fake_pipeline_result
        mock_pipeline_cls.return_value = mock_pipeline

        with patch("src.knowledge.ingestion_pipeline.SentenceTransformersDocumentEmbedder"):
            from src.knowledge.ingestion_pipeline import IngestionPipeline
            p = IngestionPipeline()
            p._data_dir = data_dir
            p._doc_store = doc_store
            p._vec_store = vec_store

            yield p, doc_store, vec_store, mock_pipeline


class TestIngestionPipeline:
    def test_discover_files_finds_markdown(self, pipeline_with_mocks):
        pipeline, _, _, _ = pipeline_with_mocks
        files = pipeline.discover_files()
        assert len(files) == 1
        assert files[0].suffix == ".md"

    def test_run_calls_vec_store_write_vectors(self, pipeline_with_mocks):
        pipeline, doc_store, vec_store, mock_pipeline = pipeline_with_mocks
        pipeline._vec_store.connect = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.close = MagicMock()

        summary = pipeline.run(wipe_first=False)

        vec_store.write_vectors.assert_called_once()
        assert summary["chunk_count"] == 3
        assert summary["doc_inserted"] == 3
        assert summary["vec_inserted"] == 3
        assert summary["file_count"] == 1

    def test_run_with_wipe_calls_delete_all(self, pipeline_with_mocks):
        pipeline, doc_store, vec_store, _ = pipeline_with_mocks
        pipeline._vec_store.connect = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.close = MagicMock()

        pipeline.run(wipe_first=True)

        doc_store.delete_all_documents.assert_called_once()
        vec_store.delete_all_vectors.assert_called_once()

    def test_run_returns_summary_keys(self, pipeline_with_mocks):
        pipeline, _, _, _ = pipeline_with_mocks
        pipeline._vec_store.connect = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.close = MagicMock()

        summary = pipeline.run()
        assert {"file_count", "chunk_count", "doc_inserted", "vec_inserted"} == set(summary.keys())

    def test_run_empty_dir_returns_zeros(self, tmp_path):
        """Pipeline with empty data dir returns all-zero summary."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        doc_store = MagicMock()
        vec_store = MagicMock()

        with patch("src.knowledge.ingestion_pipeline.IBMDb2DocumentStore", return_value=doc_store), \
             patch("src.knowledge.ingestion_pipeline.Db2VectorStore", return_value=vec_store):
            from src.knowledge.ingestion_pipeline import IngestionPipeline
            p = IngestionPipeline()
            p._data_dir = empty_dir
            p._doc_store = doc_store
            p._vec_store = vec_store
            vec_store.connect = MagicMock()
            vec_store.create_table_if_not_exists = MagicMock()
            vec_store.close = MagicMock()

            summary = p.run()
            assert summary["file_count"] == 0
            assert summary["chunk_count"] == 0
