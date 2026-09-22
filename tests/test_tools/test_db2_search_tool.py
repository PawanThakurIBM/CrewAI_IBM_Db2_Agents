"""
Unit tests for DB2VectorSearchTool (exported as Db2SearchTool alias).
The tool is now imported directly from crewai_tools — no custom BaseTool subclass.
"""
from __future__ import annotations

import pytest

from src.tools.db2_search_tool import DB2VectorSearchTool, Db2SearchTool, db2_search_tool


class TestDb2SearchToolContract:
    """Verify the contract all agents depend on."""

    def test_tool_name_is_exact_string(self):
        assert db2_search_tool.name == "IBM Db2 Enterprise Knowledge Search"

    def test_tool_description_is_non_empty(self):
        assert len(db2_search_tool.description) > 50

    def test_singleton_instance_is_db2vectorsearchtool_class(self):
        """db2_search_tool singleton must be a DB2VectorSearchTool instance."""
        assert isinstance(db2_search_tool, DB2VectorSearchTool)

    def test_db2searchtool_alias_is_same_class(self):
        """Db2SearchTool must be the exact same class as DB2VectorSearchTool."""
        assert Db2SearchTool is DB2VectorSearchTool

    def test_singleton_instance_is_also_alias_class(self):
        """Alias check: singleton must pass isinstance for both names."""
        assert isinstance(db2_search_tool, Db2SearchTool)

    def test_tool_uses_cosine_distance(self):
        assert db2_search_tool.distance_metric == "COSINE"

    def test_tool_uses_embedding_column(self):
        assert db2_search_tool.vector_column == "embedding"

    def test_tool_uses_granite_embedding_fn(self):
        assert db2_search_tool.custom_embedding_fn is not None

    def test_tool_returns_content_column(self):
        assert "content" in db2_search_tool.return_columns

    def test_tool_connection_string_is_non_empty(self):
        # DSN is built from settings — just verify it's a non-empty string
        assert isinstance(db2_search_tool.connection_string, str)
        assert len(db2_search_tool.connection_string) > 0
