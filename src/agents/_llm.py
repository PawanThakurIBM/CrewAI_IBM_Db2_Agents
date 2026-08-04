"""Shared LLM instance — Ollama Granite (local)."""
from langchain_community.llms import Ollama
from src.config.settings import get_settings

_s = get_settings()
llm = Ollama(model=_s.ollama_model, base_url=_s.ollama_base_url)
