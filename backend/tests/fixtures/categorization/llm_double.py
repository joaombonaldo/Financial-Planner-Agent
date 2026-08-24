"""Dublê determinístico do chat model, para testes que nunca dependem de Ollama real."""

from dataclasses import dataclass


@dataclass
class _FakeResponse:
    content: str


class FakeChatModel:
    """Sempre retorna a mesma resposta fixa, configurada na construção."""

    def __init__(self, response_text: str):
        self._response_text = response_text
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> _FakeResponse:
        self.calls.append(prompt)
        return _FakeResponse(content=self._response_text)
