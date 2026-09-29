import json
import urllib.request

from ..config import settings
from .base import AIAdapter, AIResponse
from .mock import SYSTEM_POLICY


class GroqAdapter(AIAdapter):
    """External Groq chat-completions adapter, enabled only by explicit policy."""
    name = "groq-external"
    is_local = False

    def __init__(self, model: str | None = None, timeout: int | None = None):
        self.model = model or settings.groq_model
        self.timeout = timeout or settings.llm_timeout

    def generate(self, system: str, prompt: str, context: dict | None = None) -> AIResponse:
        if not settings.allow_external_ai:
            raise PermissionError("Groq is blocked until SENTINEL_ALLOW_EXTERNAL_AI=true")
        if not settings.groq_api_key:
            raise ValueError("SENTINEL_GROQ_API_KEY is not configured")
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "max_completion_tokens": 1200,
            "messages": [
                {"role": "system", "content": system or SYSTEM_POLICY},
                {"role": "user", "content": f"{prompt}\n\nSupplied structured context:\n{json.dumps(context or {}, ensure_ascii=False, default=str)}"},
            ],
        }
        request = urllib.request.Request(
            f"{settings.groq_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            raise ValueError("Groq returned an empty completion")
        return AIResponse(text=text, provider=self.name, model=self.model)
