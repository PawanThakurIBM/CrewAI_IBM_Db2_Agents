"""
Architecture separation tests.

Verifies that:
1. Ingestion uses Haystack Pipeline components and the official IBMDb2DocumentStore
2. Retrieval (CrewAI DB2VectorSearchTool / Db2SearchTool alias) does NOT use Haystack Pipeline — goes direct to Db2
3. The two pipelines are completely independent
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from haystack import Pipeline

# Project root — two levels up from tests/test_architecture/
ROOT = Path(__file__).resolve().parent.parent.parent


# ── File-level import analysis ────────────────────────────────────────────────

def _get_imports(filepath: Path) -> set[str]:
    """Parse all top-level import module names from a Python source file."""
    tree = ast.parse(filepath.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


class TestIngestionUsesHaystack:
    """Ingestion pipeline MUST use real Haystack components."""

    def test_ingestion_imports_haystack_pipeline(self):
        imports = _get_imports(ROOT / "src/knowledge/ingestion_pipeline.py")
        assert any("haystack" in imp for imp in imports), (
            "ingestion_pipeline.py does not import from haystack"
        )

    def test_ingestion_imports_document_splitter(self):
        imports = _get_imports(ROOT / "src/knowledge/ingestion_pipeline.py")
        assert any("preprocessors" in imp for imp in imports), (
            "ingestion_pipeline.py must import DocumentSplitter from haystack.components.preprocessors"
        )

    def test_ingestion_imports_sentence_transformers_embedder(self):
        imports = _get_imports(ROOT / "src/knowledge/ingestion_pipeline.py")
        assert any("embedders" in imp for imp in imports), (
            "ingestion_pipeline.py must import SentenceTransformersDocumentEmbedder from haystack"
        )

    def test_ingestion_imports_document_writer(self):
        imports = _get_imports(ROOT / "src/knowledge/ingestion_pipeline.py")
        assert any("writers" in imp for imp in imports), (
            "ingestion_pipeline.py must import DocumentWriter from haystack"
        )

    def test_ingestion_imports_markdown_converter(self):
        imports = _get_imports(ROOT / "src/knowledge/ingestion_pipeline.py")
        assert any("converters" in imp for imp in imports), (
            "ingestion_pipeline.py must import MarkdownToDocument from haystack"
        )

    def test_ingestion_uses_official_ibm_document_store(self):
        """IngestionPipeline must use IBMDb2DocumentStore from the official ibm-db-haystack package."""
        from src.knowledge.ingestion_pipeline import IngestionPipeline
        with patch("src.knowledge.ingestion_pipeline.IBMDb2DocumentStore") as mock_cls:
            IngestionPipeline()
        mock_cls.assert_called_once()

    def test_official_document_store_has_required_methods(self):
        """IBMDb2DocumentStore must implement the Haystack DocumentStore protocol."""
        from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore
        for method in ("write_documents", "filter_documents", "count_documents",
                       "delete_documents", "to_dict"):
            assert hasattr(IBMDb2DocumentStore, method), (
                f"IBMDb2DocumentStore missing required method: {method}"
            )


class TestRetrievalDoesNotUseHaystackPipeline:
    """Retrieval pipeline must NOT use Haystack Pipeline — uses Db2 + sentence-transformers directly."""

    def test_retrieval_pipeline_does_not_import_haystack_pipeline(self):
        imports = _get_imports(ROOT / "src/knowledge/retrieval_pipeline.py")
        # haystack.core.pipeline or haystack.Pipeline — none should be present
        pipeline_imports = [i for i in imports if "haystack" in i and "pipeline" in i.lower()]
        assert not pipeline_imports, (
            f"retrieval_pipeline.py must not import Haystack Pipeline: {pipeline_imports}"
        )

    def test_retrieval_uses_sentence_transformers_directly(self):
        imports = _get_imports(ROOT / "src/knowledge/retrieval_pipeline.py")
        assert "sentence_transformers" in imports, (
            "retrieval_pipeline.py must import sentence_transformers directly"
        )

    def test_db2_search_tool_does_not_import_haystack(self):
        imports = _get_imports(ROOT / "src/tools/db2_search_tool.py")
        haystack_imports = [i for i in imports if "haystack" in i]
        assert not haystack_imports, (
            f"db2_search_tool.py must not import haystack: {haystack_imports}"
        )

    def test_retrieval_uses_official_ibm_integrations(self):
        """retrieval_pipeline.py must import IBMDb2DocumentStore and IBMDb2EmbeddingRetriever."""
        imports = _get_imports(ROOT / "src/knowledge/retrieval_pipeline.py")
        ibm_imports = [i for i in imports if "ibm_db" in i]
        assert len(ibm_imports) >= 2, (
            f"retrieval_pipeline.py must import both IBMDb2DocumentStore and "
            f"IBMDb2EmbeddingRetriever from haystack_integrations: {imports}"
        )


class TestSeparationAtRuntime:
    """Runtime verification that ingestion and retrieval are truly independent."""

    def test_db2_search_tool_is_from_crewai_tools(self):
        """DB2VectorSearchTool must be imported from crewai_tools, not a local BaseTool subclass."""
        from src.tools.db2_search_tool import DB2VectorSearchTool
        from crewai_tools import DB2VectorSearchTool as UpstreamTool
        assert DB2VectorSearchTool is UpstreamTool, (
            "DB2VectorSearchTool in db2_search_tool.py must be the crewai_tools class, "
            "not a local reimplementation"
        )

    def test_ingestion_pipeline_class_has_build_pipeline_method(self):
        """IngestionPipeline must expose _build_pipeline() that returns a Haystack Pipeline."""
        from src.knowledge.ingestion_pipeline import IngestionPipeline
        assert hasattr(IngestionPipeline, "_build_pipeline"), (
            "IngestionPipeline must have _build_pipeline() method"
        )

    def test_retrieval_pipeline_does_not_have_build_pipeline_method(self):
        """RetrievalPipeline must NOT have a Haystack _build_pipeline() — it's custom."""
        from src.knowledge.retrieval_pipeline import RetrievalPipeline
        assert not hasattr(RetrievalPipeline, "_build_pipeline"), (
            "RetrievalPipeline must not have _build_pipeline() — retrieval is custom, not Haystack"
        )

    def test_ingestion_pipeline_imports_haystack_pipeline_class(self):
        """Verify at module level that IngestionPipeline uses Haystack Pipeline."""
        import src.knowledge.ingestion_pipeline as ing
        assert hasattr(ing, "Pipeline"), (
            "ingestion_pipeline module must have Pipeline in scope (imported from haystack)"
        )

    def test_retrieval_pipeline_does_not_have_haystack_pipeline_in_scope(self):
        """RetrievalPipeline module must not import Haystack Pipeline class."""
        import src.knowledge.retrieval_pipeline as ret
        assert not hasattr(ret, "Pipeline"), (
            "retrieval_pipeline module must not import Haystack Pipeline"
        )

    def test_ingestion_uses_official_ibm_document_store(self):
        """IngestionPipeline._doc_store must be an IBMDb2DocumentStore."""
        from src.knowledge.ingestion_pipeline import IngestionPipeline
        with patch("src.knowledge.ingestion_pipeline.IBMDb2DocumentStore") as mock_cls:
            IngestionPipeline()
        mock_cls.assert_called_once()

    def test_retrieval_pipeline_uses_official_ibm_integrations(self):
        """RetrievalPipeline must use IBMDb2DocumentStore and IBMDb2EmbeddingRetriever."""
        from src.knowledge.retrieval_pipeline import RetrievalPipeline
        with patch("src.knowledge.retrieval_pipeline.IBMDb2DocumentStore") as mock_store, \
             patch("src.knowledge.retrieval_pipeline.IBMDb2EmbeddingRetriever") as mock_retriever:
            RetrievalPipeline()
        mock_store.assert_called_once()
        mock_retriever.assert_called_once()
