"""
Unit tests for Db2SearchTool.
Mocks the retrieval pipeline — no live Db2 or model loading.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.tools.db2_search_tool import Db2SearchTool, db2_search_tool


class TestDb2SearchToolContract:
    """Verify the contract Dhruv's agents depend on."""

    def test_tool_name_is_exact_string(self):
        assert db2_search_tool.name == "IBM Db2 Enterprise Knowledge Search"

    def test_tool_description_is_non_empty(self):
        assert len(db2_search_tool.description) > 50

    def test_run_returns_string(self):
        with patch("src.tools.db2_search_tool.retrieve") as mock_retrieve:
            mock_retrieve.return_value = "[Document 1 — sops/delay.md]\nSome content"
            result = db2_search_tool._run("passenger compensation policy")
            assert isinstance(result, str)

    def test_run_passes_query_to_retrieve(self):
        with patch("src.tools.db2_search_tool.retrieve") as mock_retrieve:
            mock_retrieve.return_value = "some result"
            db2_search_tool._run("crew rest requirements")
            mock_retrieve.assert_called_once_with("crew rest requirements")

    def test_run_returns_retrieve_output_unchanged(self):
        expected = "[Document 1 — policies/comp.md]\n€250 for short routes"
        with patch("src.tools.db2_search_tool.retrieve", return_value=expected):
            result = db2_search_tool._run("EU261 compensation amounts")
            assert result == expected

    def test_run_propagates_empty_string_result(self):
        """Even an empty retrieve() result must pass through as string."""
        with patch("src.tools.db2_search_tool.retrieve", return_value=""):
            result = db2_search_tool._run("anything")
            assert isinstance(result, str)

    def test_singleton_instance_is_db2_search_tool_class(self):
        assert isinstance(db2_search_tool, Db2SearchTool)
