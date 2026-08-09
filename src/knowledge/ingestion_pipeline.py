"""
Haystack Ingestion Pipeline.

Loads all .md documents from src/data/, processes them through a real
Haystack Pipeline, and stores everything into IBM Db2.

Pipeline:
    MarkdownToDocument                    — reads .md files → Document objects
        ↓
    DocumentCleaner                       — strips whitespace / markdown noise
        ↓
    DocumentSplitter                      — 512-word chunks, 50-word overlap
        ↓
    SentenceTransformersDocumentEmbedder  — all-MiniLM-L6-v2 → adds .embedding
        ↓
    DocumentWriter                        — writes to Db2HaystackDocumentStore
        ↓ (embeddings extracted)
    Db2VectorStore                        — writes embedding vectors to Db2
"""
from __future__ import annotations

from pathlib import Path

from haystack import Pipeline
from haystack.components.converters import MarkdownToDocument
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy

from src.config.settings import get_settings
from src.knowledge.db2_vector_store import Db2VectorStore
from src.knowledge.haystack_document_store import Db2HaystackDocumentStore
from src.utils.logger import get_logger

log = get_logger(__name__)


class IngestionPipeline:
    """
    End-to-end Haystack ingestion pipeline:
    .md files → Db2HaystackDocumentStore (text) + Db2VectorStore (embeddings).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._data_dir = Path(settings.data_dir)
        self._embedding_model = settings.embedding_model

        self._doc_store = Db2HaystackDocumentStore()
        self._vec_store = Db2VectorStore()
        self._pipeline: Pipeline | None = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open Db2 connections and ensure tables exist."""
        self._doc_store.connect()
        self._vec_store.connect()
        self._doc_store.create_table_if_not_exists()
        self._vec_store.create_table_if_not_exists()

    def close(self) -> None:
        self._doc_store.close()
        self._vec_store.close()

    def _build_pipeline(self) -> Pipeline:
        """
        Assemble the Haystack ingestion Pipeline.

        Components are wired as:
            converter → cleaner → splitter → embedder → writer
        """
        converter = MarkdownToDocument()
        cleaner = DocumentCleaner(
            remove_empty_lines=True,
            remove_extra_whitespaces=True,
            remove_repeated_substrings=False,
        )
        splitter = DocumentSplitter(
            split_by="word",
            split_length=512,
            split_overlap=50,
        )
        embedder = SentenceTransformersDocumentEmbedder(
            model=self._embedding_model,
            progress_bar=True,
            normalize_embeddings=True,
            batch_size=32,
        )
        # Warm up the embedder so it loads the model once
        embedder.warm_up()

        writer = DocumentWriter(
            document_store=self._doc_store,
            policy=DuplicatePolicy.SKIP,
        )

        pipeline = Pipeline()
        pipeline.add_component("converter", converter)
        pipeline.add_component("cleaner", cleaner)
        pipeline.add_component("splitter", splitter)
        pipeline.add_component("embedder", embedder)
        pipeline.add_component("writer", writer)

        pipeline.connect("converter.documents", "cleaner.documents")
        pipeline.connect("cleaner.documents", "splitter.documents")
        pipeline.connect("splitter.documents", "embedder.documents")
        pipeline.connect("embedder.documents", "writer.documents")

        log.info(
            "ingestion.pipeline_built",
            embedding_model=self._embedding_model,
        )
        return pipeline

    # ── Discovery ─────────────────────────────────────────────────────────────

    def discover_files(self) -> list[Path]:
        """Return sorted list of all .md files under DATA_DIR."""
        files = sorted(self._data_dir.rglob("*.md"))
        log.info(
            "ingestion.discovered_files",
            count=len(files),
            dir=str(self._data_dir),
        )
        return files

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, wipe_first: bool = False) -> dict:
        """
        Execute the full ingestion pipeline.

        Args:
            wipe_first: If True, delete all existing documents and vectors
                        before ingesting.

        Returns:
            Summary dict: file_count, chunk_count, doc_inserted, vec_inserted.
        """
        self.connect()

        if wipe_first:
            log.warning("ingestion.wiping_existing_data")
            self._doc_store.delete_all_documents()
            self._vec_store.delete_all_vectors()

        files = self.discover_files()
        if not files:
            log.warning("ingestion.no_files_found", dir=str(self._data_dir))
            self.close()
            return {"file_count": 0, "chunk_count": 0, "doc_inserted": 0, "vec_inserted": 0}

        pipeline = self._build_pipeline()

        # ── Run the Haystack pipeline ─────────────────────────────────────────
        # include_outputs_from={"embedder"} exposes intermediate embedder output
        # so we can extract embeddings for Db2VectorStore (Haystack only returns
        # leaf-node outputs by default — embedder feeds into writer so it's hidden).
        log.info("ingestion.pipeline_start", file_count=len(files))
        sources = [str(p) for p in files]
        result = pipeline.run(
            {"converter": {"sources": sources}},
            include_outputs_from={"embedder"},
        )

        # DocumentWriter returns the count of written documents
        doc_inserted: int = result.get("writer", {}).get("documents_written", 0)

        # ── Extract embeddings and write to Db2VectorStore ───────────────────
        # The embedder output contains Documents with .embedding populated.
        # We need to persist these to AIRLINE_KB.VECTORS separately because
        # Haystack's DocumentWriter only writes content/meta to the DocumentStore.
        embedded_docs = result.get("embedder", {}).get("documents", [])
        chunk_count = len(embedded_docs)

        vec_payloads = [
            {"doc_id": doc.id, "embedding": doc.embedding}
            for doc in embedded_docs
            if doc.embedding is not None
        ]
        vec_inserted = self._vec_store.write_vectors(vec_payloads)

        summary = {
            "file_count": len(files),
            "chunk_count": chunk_count,
            "doc_inserted": doc_inserted,
            "vec_inserted": vec_inserted,
        }
        log.info("ingestion.complete", **summary)
        self.close()
        return summary
