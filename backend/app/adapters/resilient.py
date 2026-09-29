from .base import AIAdapter, AIResponse
from .mock import MockAIAdapter, SYSTEM_POLICY


class ResilientAdapter(AIAdapter):
    name = "resilient-local"

    def __init__(self, primary: AIAdapter, fallback: AIAdapter):
        self.primary = primary
        self.fallback = fallback
        self.is_local = primary.is_local and fallback.is_local

    def generate(self, system: str, prompt: str, context: dict | None = None) -> AIResponse:
        try:
            return self.primary.generate(system, prompt, context)
        except Exception:
            response = self.fallback.generate(system, prompt, context)
            return AIResponse(
                text=response.text,
                provider=f"{response.provider}+{self.primary.name}",
                model=response.model,
                fallback=True,
            )
