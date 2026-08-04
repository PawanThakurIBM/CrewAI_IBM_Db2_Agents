"""
IBM Db2 Search Tool — stub.

The full implementation is owned by Pawan (task P6).
This stub allows agents to import and instantiate the tool without Db2 being configured.
When Pawan's retrieval pipeline is ready, replace _run() with:

    from src.knowledge.retrieval_pipeline import retrieve

    def _run(self, query: str) -> str:
        docs = retrieve(query)
        return docs
"""
from crewai.tools import BaseTool
from pydantic import Field


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

    def _run(self, query: str) -> str:  # noqa: D401
        """
        Stub — returns a placeholder until Pawan's retrieval pipeline is integrated.
        Replace this method body with: return retrieve(query)
        """
        return (
            f"[IBM Db2 Search Tool — stub]\n"
            f"Query received: '{query}'\n"
            f"Pawan's retrieval pipeline is not yet connected. "
            f"Once integrated, this will return relevant policy/SOP excerpts from IBM Db2."
        )


# Singleton instance shared across all agents
db2_search_tool = Db2SearchTool()
