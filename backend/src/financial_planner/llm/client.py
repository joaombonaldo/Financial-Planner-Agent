"""Single point of LLM client creation (Principle III of the constitution).

Today local Ollama with Qwen2.5, swappable to Claude/OpenAI via init_chat_model
without changing any node or categorization module. Knows nothing about taxonomy or
business rules — it only knows how to talk to an LLM.
"""

import os

from langchain.chat_models import init_chat_model


def get_chat_model():
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return init_chat_model(model, model_provider="ollama", base_url=base_url)
