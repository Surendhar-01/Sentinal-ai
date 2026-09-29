from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AIResponse(BaseModel):
    text: str
    provider: str
    model: str = ""
    fallback: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AIAdapter(ABC):
    name: str = "base"
    is_local: bool = True

    @abstractmethod
    def generate(self, system: str, prompt: str, context: dict | None = None) -> AIResponse: ...
