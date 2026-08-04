"""Shared LLM identifier — CrewAI v1.x passes Ollama as a string."""
from src.config.settings import get_settings

_s = get_settings()

# CrewAI v1.x resolves "ollama/model-name" via its own LiteLLM backend.
# No LangChain wrapper needed.
llm = f"ollama/{_s.ollama_model}"
