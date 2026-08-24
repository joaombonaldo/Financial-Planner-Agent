"""Deterministic chat model double, for tests that never depend on a real Ollama."""

from dataclasses import dataclass


@dataclass
class _FakeResponse:
    content: str


class FakeChatModel:
    """Always returns the same fixed response, configured at construction."""

    def __init__(self, response_text: str):
        self._response_text = response_text
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> _FakeResponse:
        self.calls.append(prompt)
        return _FakeResponse(content=self._response_text)


class RaisingChatModel:
    """Always raises the given exception on invoke() — simulates an unreachable LLM."""

    def __init__(self, exception: Exception):
        self._exception = exception

    def invoke(self, prompt: str):
        raise self._exception
