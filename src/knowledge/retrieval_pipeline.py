"""
Haystack Retrieval Pipeline.

Given a natural-language query string, returns the top-k most relevant
document excerpts from IBM Db2 as a formatted string ready for agent consumption.

Steps:
    1. Embed query with sentence-transformers/all-MiniLM-L6-v2
    2. Cosine similarity search in Db2VectorStore (top_k=10)
    3. Fetch full document text from Db2DocumentStore
    4. Rerank with cross-encoder/ms-marco-MiniLM-L-6-v2 (top_k=5)
    5. Format and return as plain string
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer, CrossEncoder

from src.config.settings import get_settings
from src.knowledge.db2_document_store import Db2DocumentStore
from src.knowledge.db2_vector_store import Db2VectorStore
from src.utils.logger import get_logger

log = get_logger(__name__)


class RetrievalPipeline:
    """
    Singleton-friendly retrieval pipeline.

    Lazy-loads models on first query to avoid startup cost when Db2 isn't needed.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._embedding_model_name = settings.embedding_model
        self._reranker_model_name = settings.reranker_model
        self._retrieval_top_k = settings.retrieval_top_k
        self._reranker_top_k = settings.reranker_top_k

        self._doc_store = Db2DocumentStore()
        self._vec_store = Db2VectorStore()
        self._embedder: SentenceTransformer | None = None
        self._reranker: CrossEncoder | None = None
        self._connected = False

    # ── Lazy setup ───────────────────────────────────────────────────────────

    def _ensure_ready(self) -> None:
        if not self._connected:
            self._doc_store.connect()
            self._vec_store.connect()
            self._connected = True
        if self._embedder is None:
            log.info("retrieval.loading_embedder", model=self._embedding_model_name)
            self._embedder = SentenceTransformer(self._embedding_model_name)
        if self._reranker is None:
            log.info("retrieval.loading_reranker", model=self._reranker_model_name)
            self._reranker = CrossEncoder(self._reranker_model_name)

    # ── Core query ───────────────────────────────────────────────────────────

    def retrieve(self, query: str) -> list[dict]:
        """
        Retrieve and rerank the most relevant documents for a query.

        Args:
            query: Natural-language query string.

        Returns:
            List of dicts [{id, content, source, score}, ...] top-k after reranking.
        """
        self._ensure_ready()
        log.info("retrieval.query_start", query=query[:120])

        # 1. Embed query
        query_embedding = self._embedder.encode(
            query, normalize_embeddings=True
        ).tolist()

        # 2. Vector similarity search
        vector_hits = self._vec_store.similarity_search(
            query_embedding, top_k=self._retrieval_top_k
        )
        log.debug("retrieval.vector_hits", count=len(vector_hits))

        if not vector_hits:
            log.warning("retrieval.no_vector_hits", query=query[:120])
            return []

        # 3. Fetch documents
        doc_ids = [h["doc_id"] for h in vector_hits]
        docs = self._doc_store.get_documents_by_ids(doc_ids)
        # Index by id for fast lookup
        doc_map = {d["id"]: d for d in docs}

        # Preserve hit order and attach content
        candidates = []
        for hit in vector_hits:
            doc = doc_map.get(hit["doc_id"])
            if doc:
                candidates.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "source": doc["source"],
                    "vector_score": hit["score"],
                })

        if not candidates:
            return []

        # 4. Rerank with cross-encoder
        pairs = [(query, c["content"]) for c in candidates]
        rerank_scores = self._reranker.predict(pairs)

        for candidate, score in zip(candidates, rerank_scores):
            candidate["rerank_score"] = float(score)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        top = candidates[: self._reranker_top_k]

        log.info(
            "retrieval.query_done",
            query=query[:80],
            returned=len(top),
        )
        return top

    def close(self) -> None:
        if self._connected:
            self._doc_store.close()
            self._vec_store.close()
            self._connected = False


# ── Module-level helpers ──────────────────────────────────────────────────────

# Shared pipeline instance (lazy-loaded)
_pipeline: RetrievalPipeline | None = None


def _get_pipeline() -> RetrievalPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RetrievalPipeline()
    return _pipeline


def retrieve(query: str) -> str:
    """
    Convenience function used by Db2SearchTool._run().

    Returns a formatted string of the top-k document excerpts ready
    for direct consumption by CrewAI agents.

    Format:
        [Document 1 — filename.md]
        <content>

        [Document 2 — filename.md]
        <content>
        ...
    """
    pipeline = _get_pipeline()
    results = pipeline.retrieve(query)

    if not results:
        return (
            "[IBM Db2 Knowledge Base]\n"
            "No relevant documents found for the given query.\n"
            "Ensure the knowledge base has been ingested via: python scripts/ingest_knowledge.py"
        )

    parts: list[str] = []
    for i, doc in enumerate(results, start=1):
        filename = doc["source"].split("/")[-1] if "/" in doc["source"] else doc["source"]
        parts.append(f"[Document {i} — {filename}]\n{doc['content']}")

    return "\n\n".join(parts)
