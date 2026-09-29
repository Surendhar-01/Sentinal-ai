from ..config import settings
from .base import AIAdapter, AIResponse
from .mock import MockAIAdapter, SYSTEM_POLICY
from .ollama import OllamaAdapter
from .groq import GroqAdapter
from .resilient import ResilientAdapter

_cached: AIAdapter | None = None
_mock = MockAIAdapter()


def build_adapter() -> AIAdapter:
    provider = (settings.llm_provider or "auto").lower()
    if provider in {"mock", "none", "off"}:
        return _mock
    if provider == "ollama":
        return ResilientAdapter(OllamaAdapter(), _mock)
    if provider == "groq":
        return ResilientAdapter(GroqAdapter(), _mock)
    if OllamaAdapter.available():
        return ResilientAdapter(OllamaAdapter(), _mock)
    return _mock


def get_adapter() -> AIAdapter:
    global _cached
    if _cached is None:
        _cached = build_adapter()
    return _cached


def reset_adapter() -> AIAdapter:
    global _cached
    _cached = None
    return get_adapter()


def adapter_status() -> dict:
    adapter = get_adapter()
    return {
        "provider": adapter.name,
        "local": adapter.is_local,
        "proprietary_api": not adapter.is_local,
        "external_service": not adapter.is_local,
        "configured": settings.llm_provider,
        "fallback": _mock.name,
    }


__all__ = [
    "AIAdapter",
    "AIResponse",
    "MockAIAdapter",
    "OllamaAdapter",
    "GroqAdapter",
    "ResilientAdapter",
    "SYSTEM_POLICY",
    "get_adapter",
    "build_adapter",
    "adapter_status",
    "reset_adapter",
]
