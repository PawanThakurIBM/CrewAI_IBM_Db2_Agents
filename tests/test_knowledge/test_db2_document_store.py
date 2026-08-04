"""
Unit tests for Db2DocumentStore.
Mocks ibm_db so no live Db2 connection is required.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from src.knowledge.db2_document_store import Db2DocumentStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_ibm_db():
    """Patch ibm_db at the module level used by db2_document_store."""
    with patch("src.knowledge.db2_document_store.ibm_db") as mock:
        mock.connect.return_value = MagicMock(name="conn")
        mock.prepare.return_value = MagicMock(name="stmt")
        mock.execute.return_value = None
        mock.free_result.return_value = None
        yield mock


@pytest.fixture()
def store(mock_ibm_db) -> Db2DocumentStore:
    s = Db2DocumentStore()
    s.connect()
    return s


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDb2DocumentStoreConnect:
    def test_connect_calls_ibm_db_connect(self, mock_ibm_db):
        s = Db2DocumentStore()
        s.connect()
        mock_ibm_db.connect.assert_called_once()

    def test_connect_is_idempotent(self, mock_ibm_db):
        s = Db2DocumentStore()
        s.connect()
        s.connect()  # second call should NOT re-connect
        mock_ibm_db.connect.assert_called_once()

    def test_close_sets_conn_none(self, mock_ibm_db):
        s = Db2DocumentStore()
        s.connect()
        s.close()
        assert s._conn is None


class TestDb2DocumentStoreTableCheck:
    def test_table_exists_returns_true_when_count_gt_0(self, mock_ibm_db, store):
        # Simulate SYSCAT.TABLES returning count=1
        mock_ibm_db.fetch_tuple.return_value = (1,)
        assert store._table_exists() is True

    def test_table_exists_returns_false_when_count_is_0(self, mock_ibm_db, store):
        mock_ibm_db.fetch_tuple.return_value = (0,)
        assert store._table_exists() is False


class TestDb2DocumentStoreWrite:
    def test_write_documents_returns_inserted_count(self, mock_ibm_db, store):
        docs = [
            {"content": "SOP content one", "source": "sops/delay_sop.md"},
            {"content": "Policy content two", "source": "policies/comp.md"},
        ]
        count = store.write_documents(docs)
        assert count == 2

    def test_write_documents_skips_duplicate_key_error(self, mock_ibm_db, store):
        # SQL0803 = duplicate key in Db2
        mock_ibm_db.execute.side_effect = Exception("SQL0803N duplicate key")
        docs = [{"content": "dup", "source": "x.md"}]
        count = store.write_documents(docs)
        assert count == 0

    def test_write_documents_assigns_id_if_missing(self, mock_ibm_db, store):
        docs = [{"content": "no id doc", "source": "a.md"}]
        # Should not raise
        store.write_documents(docs)
        # bind_param call index 1 should receive a string (uuid)
        calls = mock_ibm_db.bind_param.call_args_list
        first_id_call = calls[0]
        assert isinstance(first_id_call[0][2], str)
        assert len(first_id_call[0][2]) > 0


class TestDb2DocumentStoreRead:
    def test_get_documents_by_ids_returns_empty_list_for_empty_input(self, store):
        result = store.get_documents_by_ids([])
        assert result == []

    def test_get_documents_by_ids_parses_rows(self, mock_ibm_db, store):
        meta = json.dumps({"chunk_index": 0})
        # fetch_assoc returns one row then False
        mock_ibm_db.fetch_assoc.side_effect = [
            {"ID": "abc123", "CONTENT": "hello", "META": meta, "SOURCE": "sops/a.md"},
            False,
        ]
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        result = store.get_documents_by_ids(["abc123"])
        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        assert result[0]["content"] == "hello"
        assert result[0]["meta"]["chunk_index"] == 0

    def test_count_documents_returns_integer(self, mock_ibm_db, store):
        mock_ibm_db.fetch_tuple.return_value = (42,)
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        assert store.count_documents() == 42
