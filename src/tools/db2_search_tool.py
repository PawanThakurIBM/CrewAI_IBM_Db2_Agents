"""
IBM Db2 Vector Search Tool — CrewAI Tool.

DB2VectorSearchTool is the contributed CrewAI tool that gives agents semantic
vector search against IBM Db2 using the native VECTOR_DISTANCE function.

All 10 agents reference it via the Db2SearchTool alias for backward compatibility.

Contract:
- name: "IBM Db2 Enterprise Knowledge Search"   ← exact string, do not change
- _run() always returns a str
- Output format:
    [Document 1 — filename.md]
    <content>

    [Document 2 — filename.md]
    <content>
"""
from __future__ import annotations

from crewai.tools import BaseTool

from src.knowledge.retrieval_pipeline import retrieve
from src.utils.logger import get_logger

log = get_logger(__name__)


class DB2VectorSearchTool(BaseTool):
    """
    CrewAI tool for semantic vector search against IBM Db2.

    Embeds the query with ibm-granite/granite-embedding-125m-english (768-dim),
    runs VECTOR_DISTANCE(embedding, VECTOR(?, 768), 'COSINE') inside Db2 to rank
    the top-10 closest chunks, reranks them with a cross-encoder, and returns the
    top-5 excerpts as a plain string — no separate vector database required.
    """

    name: str = "IBM Db2 Enterprise Knowledge Search"
    description: str = (
        "Search the airline enterprise knowledge base stored in IBM Db2. "
        "Use this tool whenever you need to look up airline SOPs, compensation policies, "
        "passenger rights regulations, rebooking procedures, airport operations manuals, "
        "crew handling procedures, IATA delay codes, or any internal airline policy. "
        "Input: a natural-language query string. "
        "Output: the most relevant policy / procedure excerpts."
    )

    def _run(self, query: str) -> str:
        """Embed query, run VECTOR_DISTANCE in Db2, rerank, return formatted excerpts."""
        log.info("db2_search_tool.query", query=query[:120])
        result = retrieve(query)
        log.info("db2_search_tool.result_length", chars=len(result))
        return result


# Db2SearchTool is a backward-compatible alias for DB2VectorSearchTool.
#
# Why this alias exists:
#   DB2VectorSearchTool is the canonical class name — it matches the name of the
#   tool we contributed to the crewai-tools ecosystem. However, throughout this
#   project the agents, tasks, and tests were originally written importing
#   "Db2SearchTool". Rather than rename every import site, we expose both names
#   from this module so that:
#     • "from src.tools.db2_search_tool import DB2VectorSearchTool" — uses the
#       contributed tool name directly (preferred for new code).
#     • "from src.tools.db2_search_tool import Db2SearchTool" — still works
#       for all existing call sites without any change.
#
#   Because this is a plain assignment (not a subclass), both names refer to the
#   exact same class object:  Db2SearchTool is DB2VectorSearchTool → True
Db2SearchTool = DB2VectorSearchTool

# Singleton instance shared across all agents
db2_search_tool = DB2VectorSearchTool()
