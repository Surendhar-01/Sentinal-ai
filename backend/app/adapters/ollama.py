import json
import urllib.request

from ..config import settings
from .base import AIAdapter, AIResponse
from .mock import SYSTEM_POLICY


class OllamaAdapter(AIAdapter):
    name = "ollama-local"
    is_local = True

    def __init__(self, url: str | None = None, model: str | None = None, timeout: int | None = None):
        self.url = (url or settings.ollama_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout

    def generate(self, system: str, prompt: str, context: dict | None = None) -> AIResponse:
        payload = json.dumps(
            {"model": self.model, "system": system or SYSTEM_POLICY, "prompt": prompt, "stream": False}
        ).encode()
        request = urllib.request.Request(
            f"{self.url}/api/generate", data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)
        text = (data.get("response") or "").strip()
        if not text:
            raise ValueError("local model returned an empty completion")
        return AIResponse(text=text, provider=self.name, model=self.model)

    @staticmethod
    def available(timeout: float = 0.8) -> bool:
        try:
            with urllib.request.urlopen(f"{settings.ollama_url}/api/tags", timeout=timeout) as response:
                return response.status == 200
        except Exception:
            return False
