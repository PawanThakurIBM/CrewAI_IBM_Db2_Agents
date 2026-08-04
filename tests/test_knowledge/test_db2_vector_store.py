"""
Unit tests for Db2VectorStore.
Mocks ibm_db so no live Db2 connection is required.
"""
from __future__ import annotations

import json
import math
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge.db2_vector_store import Db2VectorStore, _cosine_similarity, _l2_norm


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_ibm_db():
    with patch("src.knowledge.db2_vector_store.ibm_db") as mock:
        mock.connect.return_value = MagicMock(name="conn")
        mock.prepare.return_value = MagicMock(name="stmt")
        mock.execute.return_value = None
        mock.free_result.return_value = None
        yield mock


@pytest.fixture()
def store(mock_ibm_db) -> Db2VectorStore:
    s = Db2VectorStore()
    s.connect()
    return s


# ── Math helpers ─────────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors_score_1(self):
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_score_0(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors_score_negative_1(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector_returns_0(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_norm_precomputed(self):
        v = [3.0, 4.0]
        norm = _l2_norm(v)  # 5.0
        score = _cosine_similarity(v, v, norm_a=norm)
        assert abs(score - 1.0) < 1e-6


# ── Store tests ───────────────────────────────────────────────────────────────

class TestDb2VectorStoreWrite:
    def test_write_vectors_returns_count(self, mock_ibm_db, store):
        vecs = [
            {"doc_id": "doc1", "embedding": [0.1, 0.2, 0.3]},
            {"doc_id": "doc2", "embedding": [0.4, 0.5, 0.6]},
        ]
        count = store.write_vectors(vecs)
        assert count == 2

    def test_write_vectors_logs_error_on_insert_failure(self, mock_ibm_db, store):
        mock_ibm_db.execute.side_effect = Exception("some db error")
        vecs = [{"doc_id": "x", "embedding": [1.0, 2.0]}]
        count = store.write_vectors(vecs)
        assert count == 0


class TestDb2VectorStoreSimilaritySearch:
    def _make_row(self, doc_id: str, vec: list[float]) -> dict:
        return {"DOC_ID": doc_id, "EMBEDDING": json.dumps(vec)}

    def test_returns_sorted_by_score_descending(self, mock_ibm_db, store):
        # Two docs: doc_b is more similar to query than doc_a
        query = [1.0, 0.0]
        rows = [
            self._make_row("doc_a", [0.0, 1.0]),   # orthogonal → score ≈ 0
            self._make_row("doc_b", [1.0, 0.0]),   # identical  → score = 1
        ]
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        mock_ibm_db.fetch_assoc.side_effect = rows + [False]

        results = store.similarity_search(query, top_k=2)
        assert results[0]["doc_id"] == "doc_b"
        assert results[1]["doc_id"] == "doc_a"
        assert results[0]["score"] > results[1]["score"]

    def test_top_k_limits_results(self, mock_ibm_db, store):
        query = [1.0, 0.0]
        rows = [self._make_row(f"doc_{i}", [float(i), 0.0]) for i in range(1, 6)]
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        mock_ibm_db.fetch_assoc.side_effect = rows + [False]

        results = store.similarity_search(query, top_k=2)
        assert len(results) == 2

    def test_returns_empty_when_no_rows(self, mock_ibm_db, store):
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        mock_ibm_db.fetch_assoc.return_value = False

        results = store.similarity_search([1.0, 0.0], top_k=5)
        assert results == []
