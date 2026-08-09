"""
Haystack-compatible DocumentStore backed by IBM Db2.

Implements the Haystack DocumentStore protocol so that Haystack's
DocumentWriter component can write Document objects directly to Db2.

The underlying SQL logic is unchanged from Db2DocumentStore — this class
wraps it in the Haystack interface.

Db2 table used:
    AIRLINE_KB.DOCUMENTS (id VARCHAR(64), content CLOB, meta VARCHAR(4000), source VARCHAR(512))
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import ibm_db
from haystack import Document
from haystack.document_stores.types import DocumentStore, DuplicatePolicy

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class Db2HaystackDocumentStore(DocumentStore):
    """
    Haystack DocumentStore backed by IBM Db2.

    Satisfies the Haystack DocumentStore protocol:
        - write_documents()
        - filter_documents()
        - count_documents()
        - delete_documents()
        - to_dict()

    Also exposes connect() / close() / create_table_if_not_exists()
    for lifecycle management by the ingestion pipeline.
    """

    TABLE = "DOCUMENTS"

    def __init__(self) -> None:
        settings = get_settings()
        self._dsn = settings.db2_dsn
        self._schema = settings.db2_schema.upper()
        self._conn: Any = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        if self._conn is None:
            log.info("haystack_store.connecting", schema=self._schema)
            self._conn = ibm_db.connect(self._dsn, "", "")
            log.info("haystack_store.connected")

    def close(self) -> None:
        if self._conn is not None:
            ibm_db.close(self._conn)
            self._conn = None
            log.info("haystack_store.closed")

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    def create_table_if_not_exists(self) -> None:
        """Create AIRLINE_KB.DOCUMENTS if absent (Db2 has no IF NOT EXISTS DDL)."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        if not self._table_exists():
            ddl = (
                f"CREATE TABLE {fq_table} ("
                f"  id      VARCHAR(64)      NOT NULL,"
                f"  content CLOB(1048576)    NOT NULL,"
                f"  meta    VARCHAR(4000)    NOT NULL,"
                f"  source  VARCHAR(512)     NOT NULL,"
                f"  PRIMARY KEY (id)"
                f")"
            )
            log.info("haystack_store.creating_table", table=fq_table)
            stmt = ibm_db.exec_immediate(self._conn, ddl)
            ibm_db.free_result(stmt)
            log.info("haystack_store.table_created", table=fq_table)

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

    # ── Haystack DocumentStore protocol ──────────────────────────────────────

    def write_documents(
        self,
        documents: list[Document],
        policy: DuplicatePolicy = DuplicatePolicy.SKIP,
    ) -> int:
        """
        Write Haystack Document objects to Db2.

        Embeddings are stored separately in Db2VectorStore — this method
        writes only the text content and metadata.

        DuplicatePolicy.SKIP  — silently skip existing IDs (default)
        DuplicatePolicy.OVERWRITE — delete then re-insert
        DuplicatePolicy.FAIL  — raise on duplicate
        """
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        insert_sql = (
            f"INSERT INTO {fq_table} (id, content, meta, source) "
            f"VALUES (?, ?, ?, ?)"
        )
        inserted = 0
        for doc in documents:
            doc_id = doc.id or str(uuid.uuid4())
            content = doc.content or ""
            # Preserve all Haystack meta; extract source for its own column
            source = doc.meta.get("file_path", doc.meta.get("source", ""))
            meta_json = json.dumps(doc.meta)

            if policy == DuplicatePolicy.OVERWRITE:
                self._delete_by_id(doc_id)

            try:
                stmt = ibm_db.prepare(self._conn, insert_sql)
                ibm_db.bind_param(stmt, 1, doc_id)
                ibm_db.bind_param(stmt, 2, content)
                ibm_db.bind_param(stmt, 3, meta_json)
                ibm_db.bind_param(stmt, 4, source)
                ibm_db.execute(stmt)
                ibm_db.free_result(stmt)
                inserted += 1
            except Exception as exc:
                err = str(exc)
                if "SQL0803" in err:  # duplicate key
                    if policy == DuplicatePolicy.FAIL:
                        raise ValueError(f"Duplicate document id: {doc_id}") from exc
                    # SKIP — continue silently
                else:
                    log.warning(
                        "haystack_store.insert_error",
                        doc_id=doc_id,
                        error=err[:120],
                    )
        log.info("haystack_store.wrote", inserted=inserted, total=len(documents))
        return inserted

    def filter_documents(
        self, filters: dict[str, Any] | None = None
    ) -> list[Document]:
        """
        Return documents matching filters. Supports simple equality filters
        on meta fields. No filter → returns all documents (up to 10,000).
        """
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        sql = f"SELECT id, content, meta, source FROM {fq_table} FETCH FIRST 10000 ROWS ONLY"
        stmt = ibm_db.exec_immediate(self._conn, sql)
        results: list[Document] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            meta = json.loads(row["META"])
            doc = Document(
                id=row["ID"],
                content=row["CONTENT"],
                meta=meta,
            )
            # Apply simple equality filter post-fetch
            if filters is None or self._matches_filters(meta, filters):
                results.append(doc)
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)
        return results

    def count_documents(self) -> int:
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        stmt = ibm_db.exec_immediate(
            self._conn, f"SELECT COUNT(*) FROM {fq_table}"
        )
        row = ibm_db.fetch_tuple(stmt)
        ibm_db.free_result(stmt)
        return int(row[0]) if row else 0

    def delete_documents(self, document_ids: list[str]) -> None:
        self._ensure_connected()
        for doc_id in document_ids:
            self._delete_by_id(doc_id)

    def delete_all_documents(self) -> None:
        """Delete every row — used by --wipe ingestion."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        ibm_db.exec_immediate(self._conn, f"DELETE FROM {fq_table}")
        log.info("haystack_store.all_deleted")

    def to_dict(self) -> dict[str, Any]:
        """Haystack serialisation — returns store type + schema."""
        return {
            "type": "Db2HaystackDocumentStore",
            "schema": self._schema,
        }

    # ── Retrieval helper (used by retrieval_pipeline.py) ─────────────────────

    def get_documents_by_ids(self, ids: list[str]) -> list[Document]:
        """Fetch full Document objects by their IDs."""
        self._ensure_connected()
        if not ids:
            return []
        fq_table = f"{self._schema}.{self.TABLE}"
        placeholders = ", ".join(["?"] * len(ids))
        sql = (
            f"SELECT id, content, meta, source "
            f"FROM {fq_table} WHERE id IN ({placeholders})"
        )
        stmt = ibm_db.prepare(self._conn, sql)
        for i, doc_id in enumerate(ids, start=1):
            ibm_db.bind_param(stmt, i, doc_id)
        ibm_db.execute(stmt)
        results: list[Document] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            meta = json.loads(row["META"])
            results.append(Document(
                id=row["ID"],
                content=row["CONTENT"],
                meta=meta,
            ))
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)
        return results

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _delete_by_id(self, doc_id: str) -> None:
        fq_table = f"{self._schema}.{self.TABLE}"
        sql = f"DELETE FROM {fq_table} WHERE id = ?"
        stmt = ibm_db.prepare(self._conn, sql)
        ibm_db.bind_param(stmt, 1, doc_id)
        ibm_db.execute(stmt)
        ibm_db.free_result(stmt)

    @staticmethod
    def _matches_filters(meta: dict, filters: dict) -> bool:
        """Simple equality filter check against document meta dict."""
        for key, value in filters.items():
            if meta.get(key) != value:
                return False
        return True
