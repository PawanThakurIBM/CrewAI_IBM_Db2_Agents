"""
Exhaustive tests for Db2HaystackDocumentStore.

Covers: connect/close lifecycle, DDL, write_documents (all DuplicatePolicies),
filter_documents, count_documents, delete_documents, get_documents_by_ids,
to_dict, _matches_filters.
All Db2 I/O is mocked at the ibm_db level — no live connection needed.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest
from haystack import Document
from haystack.document_stores.types import DuplicatePolicy

from src.knowledge.haystack_document_store import Db2HaystackDocumentStore


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture()
def store_and_mock():
    """Return (store, mock_ibm_db) with a live mock connection pre-attached."""
    with patch("src.knowledge.haystack_document_store.ibm_db") as mock_ibm_db:
        mock_conn = MagicMock()
        mock_ibm_db.connect.return_value = mock_conn
        mock_ibm_db.fetch_tuple.return_value = (1,)   # table exists by default

        s = Db2HaystackDocumentStore()
        s._conn = mock_conn
        yield s, mock_ibm_db, mock_conn


# ── Connection lifecycle ──────────────────────────────────────────────────────

class TestConnection:
    def test_connect_calls_ibm_db_connect(self):
        with patch("src.knowledge.haystack_document_store.ibm_db") as mock_ibm_db:
            mock_ibm_db.connect.return_value = MagicMock()
            s = Db2HaystackDocumentStore()
            assert s._conn is None
            s.connect()
            mock_ibm_db.connect.assert_called_once()

    def test_connect_is_idempotent(self):
        with patch("src.knowledge.haystack_document_store.ibm_db") as mock_ibm_db:
            mock_ibm_db.connect.return_value = MagicMock()
            s = Db2HaystackDocumentStore()
            s.connect()
            s.connect()  # second call — should not reconnect
            assert mock_ibm_db.connect.call_count == 1

    def test_close_sets_conn_none(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        s.close()
        assert s._conn is None
        mock_ibm_db.close.assert_called_once()

    def test_close_is_safe_when_not_connected(self):
        with patch("src.knowledge.haystack_document_store.ibm_db"):
            s = Db2HaystackDocumentStore()
            s._conn = None
            s.close()  # must not raise


# ── DDL / table creation ─────────────────────────────────────────────────────

class TestDDL:
    def test_create_table_skips_if_exists(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.fetch_tuple.return_value = (1,)  # table exists
        mock_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = mock_stmt
        s.create_table_if_not_exists()
        mock_ibm_db.exec_immediate.assert_not_called()

    def test_create_table_runs_ddl_when_absent(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        # First call: SYSCAT check → table absent; subsequent: exec_immediate
        mock_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = mock_stmt
        mock_ibm_db.fetch_tuple.return_value = (0,)  # table absent
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        s.create_table_if_not_exists()
        mock_ibm_db.exec_immediate.assert_called_once()
        ddl_arg = mock_ibm_db.exec_immediate.call_args[0][1]
        assert "CREATE TABLE" in ddl_arg
        assert "AIRLINE_KB" in ddl_arg or s._schema in ddl_arg


# ── write_documents ───────────────────────────────────────────────────────────

class TestWriteDocuments:
    def test_returns_inserted_count(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        docs = [
            Document(content="policy A", meta={"file_path": "sops/a.md"}),
            Document(content="policy B", meta={"file_path": "sops/b.md"}),
        ]
        count = s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        assert count == 2

    def test_skip_policy_swallows_sql0803(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.execute.side_effect = Exception("SQL0803N duplicate key")
        docs = [Document(content="dup", meta={})]
        count = s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        assert count == 0  # not inserted, not raised

    def test_fail_policy_raises_on_duplicate(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.execute.side_effect = Exception("SQL0803N duplicate key")
        docs = [Document(content="dup", meta={})]
        with pytest.raises(ValueError, match="Duplicate document id"):
            s.write_documents(docs, policy=DuplicatePolicy.FAIL)

    def test_overwrite_policy_deletes_then_inserts(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        delete_stmt = MagicMock()
        insert_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = delete_stmt
        # First prepare = DELETE, second = INSERT
        call_count = [0]
        def prepare_side(conn, sql):
            call_count[0] += 1
            return MagicMock()
        mock_ibm_db.prepare.side_effect = prepare_side
        docs = [Document(id="fixed-id", content="content", meta={})]
        count = s.write_documents(docs, policy=DuplicatePolicy.OVERWRITE)
        assert count == 1
        assert call_count[0] >= 2  # DELETE + INSERT

    def test_source_extracted_from_file_path_meta(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        captured = []
        def bind_side(stmt, pos, val):
            captured.append((pos, val))
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.bind_param.side_effect = bind_side
        docs = [Document(content="text", meta={"file_path": "sops/test.md"})]
        s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        sources = [v for pos, v in captured if v == "sops/test.md"]
        assert sources  # file_path was passed as source column

    def test_empty_list_returns_zero(self, store_and_mock):
        s, _, _ = store_and_mock
        count = s.write_documents([], policy=DuplicatePolicy.SKIP)
        assert count == 0

    def test_non_sql0803_error_is_logged_not_raised(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.execute.side_effect = Exception("Some other DB error")
        docs = [Document(content="text", meta={})]
        count = s.write_documents(docs, policy=DuplicatePolicy.SKIP)
        assert count == 0  # skipped, not raised


# ── filter_documents ──────────────────────────────────────────────────────────

class TestFilterDocuments:
    def _setup_rows(self, mock_ibm_db, rows):
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        row_iter = iter(rows + [False])
        mock_ibm_db.fetch_assoc.side_effect = lambda s: next(row_iter)

    def test_returns_all_when_no_filter(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        self._setup_rows(mock_ibm_db, [
            {"ID": "1", "CONTENT": "a", "META": json.dumps({"file_path": "a.md"}), "SOURCE": "a.md"},
            {"ID": "2", "CONTENT": "b", "META": json.dumps({"file_path": "b.md"}), "SOURCE": "b.md"},
        ])
        docs = s.filter_documents()
        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_filter_applies_equality(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        self._setup_rows(mock_ibm_db, [
            {"ID": "1", "CONTENT": "a", "META": json.dumps({"cat": "sop"}), "SOURCE": "a.md"},
            {"ID": "2", "CONTENT": "b", "META": json.dumps({"cat": "policy"}), "SOURCE": "b.md"},
        ])
        docs = s.filter_documents(filters={"cat": "sop"})
        assert len(docs) == 1
        assert docs[0].id == "1"

    def test_returns_haystack_document_objects(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        self._setup_rows(mock_ibm_db, [
            {"ID": "x", "CONTENT": "text", "META": json.dumps({}), "SOURCE": "f.md"},
        ])
        docs = s.filter_documents()
        assert isinstance(docs[0], Document)
        assert docs[0].id == "x"
        assert docs[0].content == "text"

    def test_returns_empty_when_no_rows(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        self._setup_rows(mock_ibm_db, [])
        docs = s.filter_documents()
        assert docs == []


# ── count_documents ───────────────────────────────────────────────────────────

class TestCountDocuments:
    def test_returns_integer(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        mock_ibm_db.fetch_tuple.return_value = (57,)
        assert s.count_documents() == 57

    def test_returns_zero_when_no_rows(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.exec_immediate.return_value = MagicMock()
        mock_ibm_db.fetch_tuple.return_value = None
        assert s.count_documents() == 0


# ── delete_documents ──────────────────────────────────────────────────────────

class TestDeleteDocuments:
    def test_delete_by_ids_calls_prepare_per_id(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        s.delete_documents(["id1", "id2", "id3"])
        assert mock_ibm_db.prepare.call_count == 3

    def test_delete_all_calls_exec_immediate(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        s.delete_all_documents()
        mock_ibm_db.exec_immediate.assert_called_once()
        sql = mock_ibm_db.exec_immediate.call_args[0][1]
        assert "DELETE FROM" in sql

    def test_delete_empty_list_is_safe(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        s.delete_documents([])  # must not raise or call prepare
        mock_ibm_db.prepare.assert_not_called()


# ── get_documents_by_ids ──────────────────────────────────────────────────────

class TestGetDocumentsByIds:
    def test_empty_input_returns_empty_list(self, store_and_mock):
        s, _, _ = store_and_mock
        assert s.get_documents_by_ids([]) == []

    def test_returns_document_objects(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_stmt = MagicMock()
        mock_ibm_db.prepare.return_value = mock_stmt
        mock_ibm_db.fetch_assoc.side_effect = [
            {"ID": "abc", "CONTENT": "text", "META": json.dumps({"file_path": "x.md"}), "SOURCE": "x.md"},
            False,
        ]
        docs = s.get_documents_by_ids(["abc"])
        assert len(docs) == 1
        assert isinstance(docs[0], Document)
        assert docs[0].id == "abc"
        assert docs[0].content == "text"

    def test_meta_is_parsed_as_dict(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.fetch_assoc.side_effect = [
            {"ID": "1", "CONTENT": "c", "META": json.dumps({"split_id": 3}), "SOURCE": "f.md"},
            False,
        ]
        docs = s.get_documents_by_ids(["1"])
        assert docs[0].meta["split_id"] == 3

    def test_multiple_ids_uses_in_clause(self, store_and_mock):
        s, mock_ibm_db, _ = store_and_mock
        mock_ibm_db.prepare.return_value = MagicMock()
        mock_ibm_db.fetch_assoc.return_value = False
        s.get_documents_by_ids(["a", "b", "c"])
        sql = mock_ibm_db.prepare.call_args[0][1]
        assert sql.count("?") == 3


# ── to_dict ───────────────────────────────────────────────────────────────────

class TestToDict:
    def test_contains_type_key(self, store_and_mock):
        s, _, _ = store_and_mock
        d = s.to_dict()
        assert d["type"] == "Db2HaystackDocumentStore"

    def test_contains_schema(self, store_and_mock):
        s, _, _ = store_and_mock
        d = s.to_dict()
        assert "schema" in d
        assert d["schema"] == "AIRLINE_KB"


# ── _matches_filters ──────────────────────────────────────────────────────────

class TestMatchesFilters:
    def test_matching_filter(self):
        assert Db2HaystackDocumentStore._matches_filters({"cat": "sop"}, {"cat": "sop"})

    def test_non_matching_filter(self):
        assert not Db2HaystackDocumentStore._matches_filters({"cat": "policy"}, {"cat": "sop"})

    def test_empty_filter_matches_all(self):
        assert Db2HaystackDocumentStore._matches_filters({"cat": "sop"}, {})

    def test_multiple_filters_all_must_match(self):
        meta = {"cat": "sop", "lang": "en"}
        assert Db2HaystackDocumentStore._matches_filters(meta, {"cat": "sop", "lang": "en"})
        assert not Db2HaystackDocumentStore._matches_filters(meta, {"cat": "sop", "lang": "fr"})

    def test_missing_key_does_not_match(self):
        assert not Db2HaystackDocumentStore._matches_filters({}, {"cat": "sop"})
