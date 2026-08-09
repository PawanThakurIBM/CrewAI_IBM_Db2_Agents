"""
Architecture separation tests.

Verifies that:
1. Ingestion uses Haystack Pipeline components — never imports them from src/knowledge directly
2. Retrieval (CrewAI Db2SearchTool) does NOT use Haystack Pipeline — goes direct to Db2
3. The two pipelines are completely independent
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_haystack_document_store_has_write_documents_method(self):
        """Db2HaystackDocumentStore must implement the Haystack DocumentStore protocol."""
        from src.knowledge.haystack_document_store import Db2HaystackDocumentStore
        # Check all required DocumentStore protocol methods are present
        for method in ("write_documents", "filter_documents", "count_documents",
                       "delete_documents", "to_dict"):
            assert hasattr(Db2HaystackDocumentStore, method), (
                f"Db2HaystackDocumentStore missing required method: {method}"
            )

    def test_haystack_document_store_inherits_from_haystack(self):
        """Db2HaystackDocumentStore must inherit from haystack's DocumentStore."""
        from src.knowledge.haystack_document_store import Db2HaystackDocumentStore
        bases = [b.__name__ for b in Db2HaystackDocumentStore.__mro__]
        assert "DocumentStore" in bases, (
            f"Db2HaystackDocumentStore must inherit DocumentStore; MRO: {bases}"
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

    def test_retrieval_imports_haystack_document_store_not_old_store(self):
        imports = _get_imports(ROOT / "src/knowledge/retrieval_pipeline.py")
        # Must use haystack_document_store, not old db2_document_store
        assert any("haystack_document_store" in i for i in imports), (
            "retrieval_pipeline.py must import Db2HaystackDocumentStore"
        )
        old_store = [i for i in imports
                     if i.endswith("db2_document_store") and "haystack" not in i]
        assert not old_store, (
            f"retrieval_pipeline.py must not import old Db2DocumentStore: {old_store}"
        )


class TestSeparationAtRuntime:
    """Runtime verification that ingestion and retrieval are truly independent."""

    def test_db2_search_tool_calls_retrieve_not_haystack(self):
        """Db2SearchTool._run() must call retrieve() — not a Haystack Pipeline."""
        from src.tools.db2_search_tool import Db2SearchTool

        tool = Db2SearchTool()
        with patch("src.tools.db2_search_tool.retrieve", return_value="policy result") as mock_retrieve:
            result = tool._run("compensation policy")

        mock_retrieve.assert_called_once_with("compensation policy")
        assert result == "policy result"

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

    def test_ingestion_uses_haystack_document_store_subclass(self):
        """IngestionPipeline._doc_store must be a Db2HaystackDocumentStore."""
        from src.knowledge.ingestion_pipeline import IngestionPipeline
        from src.knowledge.haystack_document_store import Db2HaystackDocumentStore
        with patch("src.knowledge.ingestion_pipeline.Db2HaystackDocumentStore") as mock_cls, \
             patch("src.knowledge.ingestion_pipeline.Db2VectorStore"):
            IngestionPipeline()
        mock_cls.assert_called_once()

    def test_retrieval_pipeline_uses_haystack_document_store(self):
        """RetrievalPipeline._doc_store must be a Db2HaystackDocumentStore."""
        from src.knowledge.retrieval_pipeline import RetrievalPipeline
        with patch("src.knowledge.retrieval_pipeline.Db2HaystackDocumentStore") as mock_cls, \
             patch("src.knowledge.retrieval_pipeline.Db2VectorStore"):
            RetrievalPipeline()
        mock_cls.assert_called_once()
