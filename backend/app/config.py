from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    secret_key: str = "dev-only-change-me"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'sentinel.db'}"
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
    chroma_path: str = str(BASE_DIR / "data" / "chroma")
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="SENTINEL_", extra="ignore")

settings = Settings()
(BASE_DIR / "data" / "uploads").mkdir(parents=True, exist_ok=True)
