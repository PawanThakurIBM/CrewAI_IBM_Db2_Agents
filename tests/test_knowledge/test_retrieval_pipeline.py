"""
Unit tests for the Retrieval Pipeline and the retrieve() function.
Mocks IBMDb2DocumentStore, IBMDb2EmbeddingRetriever, and SentenceTransformer — no live Db2.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from haystack import Document

from src.knowledge.retrieval_pipeline import RetrievalPipeline, retrieve


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_pipeline_singleton():
    """Reset the module-level pipeline singleton between tests."""
    import src.knowledge.retrieval_pipeline as rp
    original = rp._pipeline
    rp._pipeline = None
    yield
    rp._pipeline = original


def _make_pipeline_with_mocks():
    """Build a RetrievalPipeline with all external deps mocked."""
    retriever = MagicMock()
    embedder = MagicMock()
    reranker = MagicMock()

    embedder.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("src.knowledge.retrieval_pipeline.IBMDb2DocumentStore"), \
         patch("src.knowledge.retrieval_pipeline.IBMDb2EmbeddingRetriever", return_value=retriever):
        pipeline = RetrievalPipeline()

    pipeline._retriever = retriever
    pipeline._embedder = embedder
    pipeline._reranker = reranker

    return pipeline, retriever, embedder, reranker


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRetrievalPipelineRetrieve:
    def test_returns_empty_list_when_no_vector_hits(self):
        pipeline, retriever, _, _ = _make_pipeline_with_mocks()
        retriever.run.return_value = {"documents": []}

        results = pipeline.retrieve("some query")
        assert results == []

    def test_returns_top_k_results(self):
        pipeline, retriever, _, reranker = _make_pipeline_with_mocks()

        # IBMDb2EmbeddingRetriever.run() returns documents directly with content
        retriever.run.return_value = {"documents": [
            Document(id="id1", content="SOP content",    meta={"file_path": "sops/delay.md"}),
            Document(id="id2", content="Policy content", meta={"file_path": "policies/comp.md"}),
        ]}
        # Reranker gives higher score to id2
        reranker.predict.return_value = [0.5, 0.9]

        results = pipeline.retrieve("compensation rules")
        assert len(results) == 2
        # After reranking, id2 should be first
        assert results[0]["id"] == "id2"

    def test_skips_docs_with_none_content(self):
        pipeline, retriever, _, reranker = _make_pipeline_with_mocks()

        retriever.run.return_value = {"documents": [
            Document(id="id1", content="Found",  meta={"file_path": "a.md"}),
        ]}
        reranker.predict.return_value = [0.8]

        results = pipeline.retrieve("test")
        assert len(results) == 1
        assert results[0]["id"] == "id1"


class TestRetrieveFunction:
    def test_returns_string(self):
        """retrieve() must always return a str (CrewAI tool contract)."""
        with patch("src.knowledge.retrieval_pipeline._get_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.retrieve.return_value = [
                {"id": "x", "content": "doc content", "source": "sops/delay.md"}
            ]
            mock_get.return_value = mock_pipeline

            result = retrieve("what is the delay policy?")
            assert isinstance(result, str)

    def test_formats_output_with_document_headers(self):
        with patch("src.knowledge.retrieval_pipeline._get_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.retrieve.return_value = [
                {"id": "x", "content": "SOP text here", "source": "sops/flight_delay_sop.md"}
            ]
            mock_get.return_value = mock_pipeline

            result = retrieve("delay procedure")
            assert "[Document 1 — flight_delay_sop.md]" in result
            assert "SOP text here" in result

    def test_returns_no_results_message_when_empty(self):
        with patch("src.knowledge.retrieval_pipeline._get_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.retrieve.return_value = []
            mock_get.return_value = mock_pipeline

            result = retrieve("completely irrelevant query xyz")
            assert isinstance(result, str)
            assert "No relevant documents" in result
