"""
Haystack Ingestion Pipeline.

Loads all .md documents from src/data/, splits them into chunks,
generates embeddings, and stores everything into IBM Db2.

Steps:
    1. Discover .md files under DATA_DIR
    2. Load and clean text
    3. Split into 512-token chunks (50-token overlap)
    4. Generate embeddings with sentence-transformers/all-MiniLM-L6-v2
    5. Write chunks to Db2DocumentStore
    6. Write vectors to Db2VectorStore
"""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from sentence_transformers import SentenceTransformer

from src.config.settings import get_settings
from src.knowledge.db2_document_store import Db2DocumentStore
from src.knowledge.db2_vector_store import Db2VectorStore
from src.utils.logger import get_logger

log = get_logger(__name__)


# ── Text helpers ─────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Normalise whitespace and remove markdown artefacts irrelevant to retrieval."""
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove horizontal rules
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _rough_token_count(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _split_into_chunks(
    text: str,
    chunk_tokens: int = 512,
    overlap_tokens: int = 50,
) -> list[str]:
    """
    Split text into overlapping word-boundary chunks.

    Uses words as splitting units and approximates token count at 4 chars/token.
    """
    chars_per_chunk = chunk_tokens * 4
    overlap_chars = overlap_tokens * 4

    words = text.split()
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    for word in words:
        buf.append(word)
        buf_len += len(word) + 1  # +1 for space

        if buf_len >= chars_per_chunk:
            chunk = " ".join(buf)
            chunks.append(chunk)
            # Retain overlap words
            overlap_text = chunk[-overlap_chars:]
            buf = overlap_text.split()
            buf_len = sum(len(w) + 1 for w in buf)

    if buf:
        chunks.append(" ".join(buf))

    return [c for c in chunks if c.strip()]


def _stable_id(source: str, chunk_index: int) -> str:
    """Generate a stable deterministic ID so re-ingestion skips duplicates."""
    raw = f"{source}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Pipeline ──────────────────────────────────────────────────────────────────

class IngestionPipeline:
    """End-to-end ingestion: files → Db2DocumentStore + Db2VectorStore."""

    def __init__(self) -> None:
        settings = get_settings()
        self._data_dir = Path(settings.data_dir)
        self._embedding_model_name = settings.embedding_model
        self._chunk_tokens = 512
        self._overlap_tokens = 50

        self._doc_store = Db2DocumentStore()
        self._vec_store = Db2VectorStore()
        self._embedder: SentenceTransformer | None = None

    # ── Setup ────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open Db2 connections and ensure tables exist."""
        self._doc_store.connect()
        self._vec_store.connect()
        self._doc_store.create_table_if_not_exists()
        self._vec_store.create_table_if_not_exists()

    def close(self) -> None:
        self._doc_store.close()
        self._vec_store.close()

    def _load_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            log.info("ingestion.loading_embedder", model=self._embedding_model_name)
            self._embedder = SentenceTransformer(self._embedding_model_name)
            log.info("ingestion.embedder_ready")
        return self._embedder

    # ── Discovery ────────────────────────────────────────────────────────────

    def discover_files(self) -> list[Path]:
        """Return sorted list of all .md files under DATA_DIR."""
        files = sorted(self._data_dir.rglob("*.md"))
        log.info("ingestion.discovered_files", count=len(files), dir=str(self._data_dir))
        return files

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self, wipe_first: bool = False) -> dict:
        """
        Execute the full ingestion pipeline.

        Args:
            wipe_first: If True, delete all existing documents and vectors before ingesting.

        Returns:
            Summary dict with file_count, chunk_count, doc_inserted, vec_inserted.
        """
        self.connect()

        if wipe_first:
            log.warning("ingestion.wiping_existing_data")
            self._doc_store.delete_all_documents()
            self._vec_store.delete_all_vectors()

        embedder = self._load_embedder()
        files = self.discover_files()

        all_docs: list[dict] = []
        all_vecs: list[dict] = []

        for file_path in files:
            # Use data_dir as anchor so absolute tmp paths work in tests
            try:
                relative = str(file_path.relative_to(self._data_dir.parent))
            except ValueError:
                relative = str(file_path)
            raw = file_path.read_text(encoding="utf-8")
            cleaned = _clean_text(raw)
            chunks = _split_into_chunks(
                cleaned,
                chunk_tokens=self._chunk_tokens,
                overlap_tokens=self._overlap_tokens,
            )
            log.info(
                "ingestion.file_processed",
                file=relative,
                chunks=len(chunks),
            )

            for idx, chunk in enumerate(chunks):
                doc_id = _stable_id(relative, idx)
                all_docs.append({
                    "id": doc_id,
                    "content": chunk,
                    "meta": {
                        "source_file": relative,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                    },
                    "source": relative,
                })

        log.info("ingestion.embedding_start", total_chunks=len(all_docs))
        texts = [d["content"] for d in all_docs]
        embeddings = embedder.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        log.info("ingestion.embedding_done")

        for doc, embedding in zip(all_docs, embeddings):
            all_vecs.append({
                "doc_id": doc["id"],
                "embedding": embedding.tolist(),
            })

        doc_inserted = self._doc_store.write_documents(all_docs)
        vec_inserted = self._vec_store.write_vectors(all_vecs)

        summary = {
            "file_count": len(files),
            "chunk_count": len(all_docs),
            "doc_inserted": doc_inserted,
            "vec_inserted": vec_inserted,
        }
        log.info("ingestion.complete", **summary)
        self.close()
        return summary
