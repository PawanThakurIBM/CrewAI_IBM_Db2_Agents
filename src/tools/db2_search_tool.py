"""
IBM Db2 Search Tool — CrewAI Tool.

All 10 agents call this tool to query the airline enterprise knowledge base.
Internally it runs the Haystack retrieval pipeline (embed → vector search → rerank)
against IBM Db2 and returns formatted document excerpts.

Contract (agreed with Dhruv):
- name: "IBM Db2 Enterprise Knowledge Search"   ← exact string, do not change
- _run() always returns a str
- Output format:
    [Document 1 — filename.md]
    <content>

    [Document 2 — filename.md]
    <content>
"""
from crewai.tools import BaseTool

from src.knowledge.retrieval_pipeline import retrieve
from src.utils.logger import get_logger

log = get_logger(__name__)


class Db2SearchTool(BaseTool):
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
        """Query Haystack retrieval pipeline and return formatted excerpts."""
        log.info("db2_search_tool.query", query=query[:120])
        result = retrieve(query)
        log.info("db2_search_tool.result_length", chars=len(result))
        return result


# Singleton instance shared across all agents
db2_search_tool = Db2SearchTool()
