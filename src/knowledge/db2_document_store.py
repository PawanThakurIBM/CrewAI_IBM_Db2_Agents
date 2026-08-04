"""
IBM Db2 Document Store for Haystack.

Stores document chunks (id, content, metadata) in IBM Db2.
Implements a subset of the Haystack DocumentStore interface sufficient
for this project's ingestion and retrieval pipeline.

Schema created on first use:

    CREATE TABLE <schema>.DOCUMENTS (
        id          VARCHAR(64)   NOT NULL PRIMARY KEY,
        content     CLOB          NOT NULL,
        meta        VARCHAR(4000) NOT NULL,   -- JSON string
        source      VARCHAR(512)  NOT NULL
    );
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import ibm_db

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class Db2DocumentStore:
    """Haystack-compatible document store backed by IBM Db2."""

    TABLE = "DOCUMENTS"

    def __init__(self) -> None:
        settings = get_settings()
        self._dsn = settings.db2_dsn
        self._schema = settings.db2_schema.upper()
        self._conn: Any = None

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open the Db2 connection (call once at startup or before operations)."""
        if self._conn is None:
            log.info("db2_document_store.connecting", schema=self._schema)
            self._conn = ibm_db.connect(self._dsn, "", "")
            log.info("db2_document_store.connected")

    def close(self) -> None:
        """Close the Db2 connection."""
        if self._conn is not None:
            ibm_db.close(self._conn)
            self._conn = None
            log.info("db2_document_store.closed")

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    # ── Schema ─────────────────────────────────────────────────────────────

    def create_table_if_not_exists(self) -> None:
        """Create the DOCUMENTS table if it does not already exist."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {fq_table} ("
            f"  id      VARCHAR(64)   NOT NULL,"
            f"  content CLOB(1048576) NOT NULL,"
            f"  meta    VARCHAR(4000) NOT NULL,"
            f"  source  VARCHAR(512)  NOT NULL,"
            f"  PRIMARY KEY (id)"
            f")"
        )
        # IBM Db2 does not support IF NOT EXISTS — check first
        if not self._table_exists():
            log.info("db2_document_store.creating_table", table=fq_table)
            stmt = ibm_db.exec_immediate(self._conn, ddl.replace("IF NOT EXISTS ", ""))
            ibm_db.free_result(stmt)
            log.info("db2_document_store.table_created", table=fq_table)
        else:
            log.debug("db2_document_store.table_exists", table=fq_table)

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

    # ── Write ───────────────────────────────────────────────────────────────

    def write_documents(self, documents: list[dict]) -> int:
        """
        Insert documents into the store. Skips duplicates (by id).

        Args:
            documents: List of dicts with keys: id (optional), content, meta, source.

        Returns:
            Number of documents actually inserted.
        """
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        sql = (
            f"INSERT INTO {fq_table} (id, content, meta, source) "
            f"VALUES (?, ?, ?, ?)"
        )
        inserted = 0
        for doc in documents:
            doc_id = doc.get("id") or str(uuid.uuid4())
            content = doc["content"]
            meta = json.dumps(doc.get("meta", {}))
            source = doc.get("source", "")
            try:
                stmt = ibm_db.prepare(self._conn, sql)
                ibm_db.bind_param(stmt, 1, doc_id)
                ibm_db.bind_param(stmt, 2, content)
                ibm_db.bind_param(stmt, 3, meta)
                ibm_db.bind_param(stmt, 4, source)
                ibm_db.execute(stmt)
                ibm_db.free_result(stmt)
                inserted += 1
            except Exception as exc:
                # Duplicate key — skip silently; log others
                err_str = str(exc)
                if "SQL0803" not in err_str:  # -803 = duplicate key
                    log.warning(
                        "db2_document_store.insert_error",
                        doc_id=doc_id,
                        error=err_str,
                    )
        log.info("db2_document_store.wrote", inserted=inserted, total=len(documents))
        return inserted

    # ── Read ────────────────────────────────────────────────────────────────

    def get_documents_by_ids(self, ids: list[str]) -> list[dict]:
        """Fetch full document records by their IDs."""
        self._ensure_connected()
        if not ids:
            return []
        fq_table = f"{self._schema}.{self.TABLE}"
        placeholders = ", ".join(["?"] * len(ids))
        sql = f"SELECT id, content, meta, source FROM {fq_table} WHERE id IN ({placeholders})"
        stmt = ibm_db.prepare(self._conn, sql)
        for i, doc_id in enumerate(ids, start=1):
            ibm_db.bind_param(stmt, i, doc_id)
        ibm_db.execute(stmt)
        results = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append({
                "id": row["ID"],
                "content": row["CONTENT"],
                "meta": json.loads(row["META"]),
                "source": row["SOURCE"],
            })
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)
        return results

    def count_documents(self) -> int:
        """Return total number of documents in the store."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        stmt = ibm_db.exec_immediate(self._conn, f"SELECT COUNT(*) FROM {fq_table}")
        row = ibm_db.fetch_tuple(stmt)
        ibm_db.free_result(stmt)
        return int(row[0]) if row else 0

    def delete_all_documents(self) -> None:
        """Delete all documents (used for re-ingestion)."""
        self._ensure_connected()
        fq_table = f"{self._schema}.{self.TABLE}"
        ibm_db.exec_immediate(self._conn, f"DELETE FROM {fq_table}")
        log.info("db2_document_store.all_deleted")
