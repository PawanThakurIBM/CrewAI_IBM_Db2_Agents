
from __future__ import annotations

from pathlib import Path

from haystack import Pipeline
from haystack.components.converters import MarkdownToDocument
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.utils import Secret
from haystack_integrations.components.embedders.sentence_transformers import (
    SentenceTransformersDocumentEmbedder,
)
from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class IngestionPipeline:


    def __init__(self) -> None:
        settings = get_settings()
        self._data_dir = Path(settings.data_dir)
        self._embedding_model = settings.embedding_model

        self._doc_store = IBMDb2DocumentStore(
            database=settings.db2_database,
            hostname=settings.db2_host,
            port=settings.db2_port,
            username=Secret.from_env_var("DB2_USERNAME"),
            password=Secret.from_env_var("DB2_PASSWORD"),
            schema=settings.db2_schema,
            table_name="DOCUMENTS",
            embedding_dim=settings.embedding_dim,
            distance_metric="COSINE",
        )
        self._pipeline: Pipeline | None = None

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _build_pipeline(self) -> Pipeline:
        """
        Assemble the Haystack ingestion Pipeline.

        Components wired as:
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

        log.info("ingestion.pipeline_built", embedding_model=self._embedding_model)
        return pipeline

    # ── Discovery ─────────────────────────────────────────────────────────────

    def discover_files(self) -> list[Path]:
        """Return sorted list of all .md files under DATA_DIR."""
        files = sorted(self._data_dir.rglob("*.md"))
        log.info("ingestion.discovered_files", count=len(files), dir=str(self._data_dir))
        return files

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, wipe_first: bool = False) -> dict:
        """
        Execute the full ingestion pipeline.

        Args:
            wipe_first: If True, delete all existing documents before ingesting.

        Returns:
            Summary dict: file_count, chunk_count, doc_inserted.
        """
        if wipe_first:
            log.warning("ingestion.wiping_existing_data")
            self._doc_store.delete_all_documents()

        files = self.discover_files()
        if not files:
            log.warning("ingestion.no_files_found", dir=str(self._data_dir))
            return {"file_count": 0, "chunk_count": 0, "doc_inserted": 0}

        pipeline = self._build_pipeline()

        log.info("ingestion.pipeline_start", file_count=len(files))
        result = pipeline.run(
            {"converter": {"sources": [str(p) for p in files]}},
            include_outputs_from={"embedder"},
        )

        doc_inserted: int = result.get("writer", {}).get("documents_written", 0)
        chunk_count: int = len(result.get("embedder", {}).get("documents", []))

        summary = {
            "file_count": len(files),
            "chunk_count": chunk_count,
            "doc_inserted": doc_inserted,
        }
        log.info("ingestion.complete", **summary)
        return summary
