"""Único ponto de criação do client de LLM (Princípio III da constituição).

Hoje Ollama local com Qwen2.5, trocável para Claude/OpenAI via init_chat_model sem
alterar nenhum node ou módulo de categorização. Não conhece taxonomia nem regras de
negócio — só sabe conversar com um LLM.
"""

import os

from langchain.chat_models import init_chat_model


def get_chat_model():
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return init_chat_model(model, model_provider="ollama", base_url=base_url)
