"""
Retrieval Pipeline (no Haystack Pipeline — direct Db2 query).

Given a natural-language query string, returns the top-k most relevant
document excerpts from IBM Db2 as a formatted string ready for agent consumption.

Steps:
    1. Embed query with ibm-granite/granite-embedding-125m-english (768-dim)
    2. IBMDb2EmbeddingRetriever — runs VECTOR_DISTANCE in Db2, returns top-k Documents
    3. Rerank with cross-encoder/ms-marco-MiniLM-L-6-v2 (top_k=5)
    4. Format and return as plain string

Both IBMDb2DocumentStore and IBMDb2EmbeddingRetriever are from the official
ibm-db-haystack package — no custom Db2 wrapper required.
"""
from __future__ import annotations

from sentence_transformers import CrossEncoder, SentenceTransformer
from haystack.utils import Secret
from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore
from haystack_integrations.components.retrievers.ibm_db import IBMDb2EmbeddingRetriever

from src.config.settings import get_settings
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
        self._retriever = IBMDb2EmbeddingRetriever(
            document_store=self._doc_store,
            top_k=self._retrieval_top_k,
        )
        self._embedder: SentenceTransformer | None = None
        self._reranker: CrossEncoder | None = None

    # ── Lazy setup ───────────────────────────────────────────────────────────

    def _ensure_ready(self) -> None:
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

        # 2. Vector similarity search via IBMDb2EmbeddingRetriever
        result = self._retriever.run(query_embedding=query_embedding)
        hits = result.get("documents", [])
        log.debug("retrieval.vector_hits", count=len(hits))

        if not hits:
            log.warning("retrieval.no_vector_hits", query=query[:120])
            return []

        # 3. Rerank with cross-encoder
        pairs = [(query, doc.content or "") for doc in hits]
        rerank_scores = self._reranker.predict(pairs)

        candidates = []
        for doc, score in zip(hits, rerank_scores):
            source = doc.meta.get("file_path", doc.meta.get("source", ""))
            candidates.append({
                "id": doc.id,
                "content": doc.content,
                "source": source,
                "rerank_score": float(score),
            })

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        top = candidates[: self._reranker_top_k]

        log.info("retrieval.query_done", query=query[:80], returned=len(top))
        return top


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
    Convenience function used by DB2VectorSearchTool._run().

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
