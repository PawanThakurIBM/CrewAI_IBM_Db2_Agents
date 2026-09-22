"""
IBM Db2 Vector Search Tool — CrewAI Tool.

Uses DB2VectorSearchTool from the official crewai_tools package — the tool
contributed by IBM to the crewai-tools ecosystem.

The tool is instantiated with:
  - connection_string  — built from get_settings().db2_dsn
  - table_name         — "<schema>.VECTORS"
  - vector_column      — "embedding"
  - return_columns     — ["content"]
  - limit              — settings.retrieval_top_k (10)
  - distance_metric    — "COSINE"
  - custom_embedding_fn — ibm-granite/granite-embedding-125m-english (768-dim)

Db2SearchTool is a backward-compatible alias for DB2VectorSearchTool.

Why this alias exists:
  DB2VectorSearchTool is the canonical class name — it matches the name of the
  tool we contributed to the crewai-tools ecosystem. However, throughout this
  project the agents, tasks, and tests were originally written importing
  "Db2SearchTool". Rather than rename every import site, we expose both names
  from this module so that:
    • "from src.tools.db2_search_tool import DB2VectorSearchTool" — uses the
      contributed tool name directly (preferred for new code).
    • "from src.tools.db2_search_tool import Db2SearchTool" — still works
      for all existing call sites without any change.

  Because this is a plain assignment (not a subclass), both names refer to the
  exact same class object:  Db2SearchTool is DB2VectorSearchTool → True
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer
from crewai_tools import DB2VectorSearchTool

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_settings = get_settings()

# Lazy-load the Granite embedding model (loaded once at first tool instantiation)
_embedder = SentenceTransformer(_settings.embedding_model)


def _granite_embed(text: str) -> list[float]:
    """Embed text using ibm-granite/granite-embedding-125m-english (768-dim)."""
    return _embedder.encode(text, normalize_embeddings=True).tolist()


# Backward-compatible alias — Db2SearchTool IS DB2VectorSearchTool
Db2SearchTool = DB2VectorSearchTool

# Singleton instance shared across all agents.
# name is overridden to match the fixed contract string all agents depend on.
db2_search_tool = DB2VectorSearchTool(
    name="IBM Db2 Enterprise Knowledge Search",
    connection_string=_settings.db2_dsn,
    table_name=f"{_settings.db2_schema}.VECTORS",
    vector_column="embedding",
    return_columns=["content"],
    limit=_settings.retrieval_top_k,
    distance_metric="COSINE",
    custom_embedding_fn=_granite_embed,
)
