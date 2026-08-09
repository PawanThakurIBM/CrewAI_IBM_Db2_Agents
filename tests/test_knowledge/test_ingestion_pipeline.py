"""
Unit tests for the Haystack Ingestion Pipeline.

Tests the real Haystack Pipeline components (converter, cleaner, splitter,
embedder, writer) with mocked Db2 stores — no live Db2 or model loading.
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


# ── Db2HaystackDocumentStore unit tests ──────────────────────────────────────

class TestDb2HaystackDocumentStore:
    """Test the Haystack DocumentStore wrapper — Db2 is mocked at ibm_db level."""

    @pytest.fixture()
    def store(self):
        with patch("src.knowledge.haystack_document_store.ibm_db") as mock_ibm_db:
            mock_conn = MagicMock()
            mock_ibm_db.connect.return_value = mock_conn

            # _table_exists returns True so create_table_if_not_exists skips DDL
            mock_stmt = MagicMock()
            mock_ibm_db.prepare.return_value = mock_stmt
            mock_ibm_db.fetch_tuple.return_value = (1,)  # table exists

            from src.knowledge.haystack_document_store import Db2HaystackDocumentStore
            s = Db2HaystackDocumentStore()
            s._conn = mock_conn
            yield s, mock_ibm_db

    def test_write_documents_returns_inserted_count(self, store):
        s, mock_ibm_db = store
        mock_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = mock_stmt

        docs = [Document(content="policy text", meta={"file_path": "sops/test.md"})]
        count = s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        assert count == 1

    def test_write_documents_skip_on_duplicate(self, store):
        s, mock_ibm_db = store
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.execute.side_effect = Exception("SQL0803N duplicate key")

        docs = [Document(content="dup", meta={})]
        # Should not raise — SKIP policy swallows SQL0803
        count = s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        assert count == 0

    def test_write_documents_fail_on_duplicate_raises(self, store):
        s, mock_ibm_db = store
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.execute.side_effect = Exception("SQL0803N duplicate key")

        docs = [Document(content="dup", meta={})]
        with pytest.raises(ValueError, match="Duplicate document id"):
            s.write_documents(docs, policy=DuplicatePolicy.FAIL)

    def test_count_documents_returns_integer(self, store):
        s, mock_ibm_db = store
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_tuple.return_value = (42,)
        assert s.count_documents() == 42

    def test_to_dict_contains_type(self, store):
        s, _ = store
        d = s.to_dict()
        assert d["type"] == "Db2HaystackDocumentStore"
        assert "schema" in d

    def test_get_documents_by_ids_empty_input(self, store):
        s, _ = store
        result = s.get_documents_by_ids([])
        assert result == []

    def test_get_documents_by_ids_returns_documents(self, store):
        import json
        s, mock_ibm_db = store
        mock_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = mock_stmt
        # Simulate two rows returned
        mock_ibm_db.fetch_assoc.side_effect = [
            {"ID": "abc", "CONTENT": "text1", "META": json.dumps({"file_path": "a.md"}), "SOURCE": "a.md"},
            {"ID": "def", "CONTENT": "text2", "META": json.dumps({"file_path": "b.md"}), "SOURCE": "b.md"},
            False,
        ]
        docs = s.get_documents_by_ids(["abc", "def"])
        assert len(docs) == 2
        assert docs[0].id == "abc"
        assert docs[0].content == "text1"
        assert isinstance(docs[0], Document)


# ── IngestionPipeline integration tests (Haystack pipeline mocked) ────────────

@pytest.fixture()
def pipeline_with_mocks(tmp_path):
    """
    IngestionPipeline with Haystack pipeline fully mocked.
    The real Haystack Pipeline.run() is replaced so no model loads.
    """
    # Create a minimal test document
    data_dir = tmp_path / "data"
    (data_dir / "sops").mkdir(parents=True)
    (data_dir / "sops" / "test_sop.md").write_text(
        "# Test SOP\nThis is a test document for ingestion testing.\n" * 10
    )

    doc_store = MagicMock()
    vec_store = MagicMock()
    doc_store.write_documents.return_value = 3
    vec_store.write_vectors.return_value = 3

    # Fake embedded documents returned by the pipeline
    fake_docs = [
        Document(id=f"doc{i}", content=f"chunk {i}", meta={"file_path": "sops/test_sop.md"},
                 embedding=[0.1] * 384)
        for i in range(3)
    ]

    # Mock pipeline result matching real Haystack output structure
    fake_pipeline_result = {
        "writer": {"documents_written": 3},
        "embedder": {"documents": fake_docs},
    }

    with patch("src.knowledge.ingestion_pipeline.Db2HaystackDocumentStore", return_value=doc_store), \
         patch("src.knowledge.ingestion_pipeline.Db2VectorStore", return_value=vec_store), \
         patch("src.knowledge.ingestion_pipeline.Pipeline") as mock_pipeline_cls:

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = fake_pipeline_result
        mock_pipeline_cls.return_value = mock_pipeline

        # Also mock SentenceTransformersDocumentEmbedder warm_up
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
        pipeline._doc_store.connect = MagicMock()
        pipeline._vec_store.connect = MagicMock()
        pipeline._doc_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._doc_store.close = MagicMock()
        pipeline._vec_store.close = MagicMock()

        summary = pipeline.run(wipe_first=False)

        vec_store.write_vectors.assert_called_once()
        assert summary["chunk_count"] == 3
        assert summary["doc_inserted"] == 3
        assert summary["vec_inserted"] == 3
        assert summary["file_count"] == 1

    def test_run_with_wipe_calls_delete_all(self, pipeline_with_mocks):
        pipeline, doc_store, vec_store, _ = pipeline_with_mocks
        pipeline._doc_store.connect = MagicMock()
        pipeline._vec_store.connect = MagicMock()
        pipeline._doc_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._doc_store.close = MagicMock()
        pipeline._vec_store.close = MagicMock()

        pipeline.run(wipe_first=True)

        doc_store.delete_all_documents.assert_called_once()
        vec_store.delete_all_vectors.assert_called_once()

    def test_run_returns_summary_keys(self, pipeline_with_mocks):
        pipeline, _, _, _ = pipeline_with_mocks
        pipeline._doc_store.connect = MagicMock()
        pipeline._vec_store.connect = MagicMock()
        pipeline._doc_store.create_table_if_not_exists = MagicMock()
        pipeline._vec_store.create_table_if_not_exists = MagicMock()
        pipeline._doc_store.close = MagicMock()
        pipeline._vec_store.close = MagicMock()

        summary = pipeline.run()
        assert {"file_count", "chunk_count", "doc_inserted", "vec_inserted"} == set(summary.keys())

    def test_run_empty_dir_returns_zeros(self, tmp_path):
        """Pipeline with empty data dir returns all-zero summary."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        doc_store = MagicMock()
        vec_store = MagicMock()

        with patch("src.knowledge.ingestion_pipeline.Db2HaystackDocumentStore", return_value=doc_store), \
             patch("src.knowledge.ingestion_pipeline.Db2VectorStore", return_value=vec_store):
            from src.knowledge.ingestion_pipeline import IngestionPipeline
            p = IngestionPipeline()
            p._data_dir = empty_dir
            p._doc_store = doc_store
            p._vec_store = vec_store
            doc_store.connect = MagicMock()
            vec_store.connect = MagicMock()
            doc_store.create_table_if_not_exists = MagicMock()
            vec_store.create_table_if_not_exists = MagicMock()
            doc_store.close = MagicMock()
            vec_store.close = MagicMock()

            summary = p.run()
            assert summary["file_count"] == 0
            assert summary["chunk_count"] == 0
