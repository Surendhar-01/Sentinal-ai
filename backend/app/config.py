import os
import tempfile
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("SENTINEL_SERVERLESS"))


class Settings(BaseSettings):
    secret_key: str = "dev-only-change-me"
    serverless: bool = SERVERLESS
    data_dir: str = ""
    database_url: str = ""
    cors_origins: str = "http://localhost:5173"
    embedding_provider: str = "hash"
    embedding_model: str = "nomic-embed-text"
    ollama_url: str = "http://localhost:11434"
    llm_provider: str = "auto"
    llm_model: str = "llama3.2"
    llm_timeout: int = 60
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    allow_external_ai: bool = False
    jwt_ttl_hours: int = 8
    vector_store: str = "chroma"
    chroma_path: str = ""

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="SENTINEL_", extra="ignore")

    @model_validator(mode="after")
    def _resolve_paths(self):
        if self.data_dir:
            data_dir = Path(self.data_dir)
        elif self.serverless:
            data_dir = Path(tempfile.gettempdir()) / "sentinel-ai"
        else:
            data_dir = BASE_DIR / "data"
        self.data_dir = str(data_dir)
        if not self.database_url:
            self.database_url = f"sqlite:///{data_dir / 'sentinel.db'}"
        if not self.chroma_path:
            self.chroma_path = str(data_dir / "chroma")
        return self

    @property
    def uploads_dir(self) -> Path:
        return Path(self.data_dir) / "uploads"


settings = Settings()


def ensure_runtime_dirs() -> None:
    """Create writable runtime directories; skip silently on read-only filesystems."""
    for directory in (Path(settings.chroma_path), settings.uploads_dir):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


ensure_runtime_dirs()
