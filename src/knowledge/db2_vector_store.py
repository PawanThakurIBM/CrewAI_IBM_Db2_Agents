"""
IBM Db2 Vector Store for Haystack.

Stores embedding vectors (id, document_id, vector) in IBM Db2 and performs
cosine similarity search using in-database computation.

Schema:

    CREATE TABLE <schema>.VECTORS (
        id          VARCHAR(64)    NOT NULL PRIMARY KEY,
        doc_id      VARCHAR(64)    NOT NULL,
        embedding   VARCHAR(32000) NOT NULL   -- JSON array of floats
    );

IBM Db2 does not ship a native vector similarity function in all editions, so
cosine similarity is computed in Python after fetching the top-N candidates.
For small-to-medium knowledge bases (< 100 k chunks) this is fast enough.
"""
from __future__ import annotations

import json
import math
import uuid
from typing import Any

import ibm_db

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)

# Maximum number of vectors fetched before Python-side ranking
_SCAN_LIMIT = 10_000


class Db2VectorStore:
    """Haystack-compatible vector store backed by IBM Db2."""

    TABLE = "VECTORS"

    def __init__(self) -> None:
        settings = get_settings()
        self._dsn = settings.db2_dsn
        self._schema = settings.db2_schema.upper()
        self._conn: Any = None

    # ── Connection ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open the Db2 connection."""
        if self._conn is None:
            log.info("db2_vector_store.connecting", schema=self._schema)
            self._conn = ibm_db.connect(self._dsn, "", "")
            log.info("db2_vector_store.connected")

    def close(self) -> None:
        if self._conn is not None:
            ibm_db.close(self._conn)
            self._conn = None
            log.info("db2_vector_store.closed")

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    # ── Schema ──────────────────────────────────────────────────────────────

    def create_table_if_not_exists(self) -> None:
        """Create VECTORS table if absent."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        if not self._table_exists():
            ddl = (
                f"CREATE TABLE {fq_table} ("
                f"  id        VARCHAR(64)    NOT NULL,"
                f"  doc_id    VARCHAR(64)    NOT NULL,"
                f"  embedding VARCHAR(32000) NOT NULL,"
                f"  PRIMARY KEY (id)"
                f")"
            )
            log.info("db2_vector_store.creating_table", table=fq_table)
            stmt = ibm_db.exec_immediate(self._conn, ddl)
            ibm_db.free_result(stmt)
            log.info("db2_vector_store.table_created", table=fq_table)
        else:
            log.debug("db2_vector_store.table_exists", table=fq_table)

    def _table_exists(self) -> bool:
        sql = (
            "SELECT COUNT(*) FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = ? AND TABNAME = ?"
        )
        stmt = ibm_db.prepare(self._conn, sql)
        ibm_db.bind_param(stmt, 1, self._schema)
        ibm_db.bind_param(stmt, 2, self.TABLE)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_tuple(stmt)
        ibm_db.free_result(stmt)
        return bool(row and row[0] > 0)

    # ── Write ────────────────────────────────────────────────────────────────

    def write_vectors(self, vectors: list[dict]) -> int:
        """
        Insert embedding vectors.

        Args:
            vectors: List of dicts with keys: doc_id (str), embedding (list[float]).

        Returns:
            Number inserted.
        """
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        sql = f"INSERT INTO {fq_table} (id, doc_id, embedding) VALUES (?, ?, ?)"
        inserted = 0
        for vec in vectors:
            vec_id = str(uuid.uuid4())
            doc_id = vec["doc_id"]
            embedding_json = json.dumps(vec["embedding"])
            try:
                stmt = ibm_db.prepare(self._conn, sql)
                ibm_db.bind_param(stmt, 1, vec_id)
                ibm_db.bind_param(stmt, 2, doc_id)
                ibm_db.bind_param(stmt, 3, embedding_json)
                ibm_db.execute(stmt)
                ibm_db.free_result(stmt)
                inserted += 1
            except Exception as exc:
                log.warning(
                    "db2_vector_store.insert_error",
                    doc_id=doc_id,
                    error=str(exc),
                )
        log.info("db2_vector_store.wrote", inserted=inserted, total=len(vectors))
        return inserted

    # ── Search ──────────────────────────────────────────────────────────────

    def similarity_search(
        self, query_embedding: list[float], top_k: int = 10
    ) -> list[dict]:
        """
        Retrieve the top-k most similar document ids by cosine similarity.

        Args:
            query_embedding: The query vector.
            top_k: Number of results to return.

        Returns:
            List of dicts: [{doc_id: str, score: float}, ...] sorted descending.
        """
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        sql = f"SELECT doc_id, embedding FROM {fq_table} FETCH FIRST {_SCAN_LIMIT} ROWS ONLY"
        stmt = ibm_db.exec_immediate(self._conn, sql)

        query_norm = _l2_norm(query_embedding)
        scored: list[tuple[float, str]] = []

        row = ibm_db.fetch_assoc(stmt)
        while row:
            stored_vec: list[float] = json.loads(row["EMBEDDING"])
            score = _cosine_similarity(query_embedding, stored_vec, query_norm)
            scored.append((score, row["DOC_ID"]))
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)

        scored.sort(key=lambda x: x[0], reverse=True)
        log.debug(
            "db2_vector_store.search_done",
            scanned=len(scored),
            top_k=top_k,
        )
        return [
            {"doc_id": doc_id, "score": round(score, 6)}
            for score, doc_id in scored[:top_k]
        ]

    def count_vectors(self) -> int:
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        stmt = ibm_db.exec_immediate(self._conn, f"SELECT COUNT(*) FROM {fq_table}")
        row = ibm_db.fetch_tuple(stmt)
        ibm_db.free_result(stmt)
        return int(row[0]) if row else 0

    def delete_all_vectors(self) -> None:
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        ibm_db.exec_immediate(self._conn, f"DELETE FROM {fq_table}")
        log.info("db2_vector_store.all_deleted")


# ── Math helpers ────────────────────────────────────────────────────────────

def _l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _cosine_similarity(
    a: list[float], b: list[float], norm_a: float | None = None
) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = norm_a if norm_a is not None else _l2_norm(a)
    nb = _l2_norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
