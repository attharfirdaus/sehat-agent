from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, env_ignore_empty=True, extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://sehat:sehat@localhost:5432/sehat"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen3.5:9b"
    EMBED_MODEL: str | None = None  # TODO(PRD): pilih model embedding (bagian 12, 17)
    EMBED_DIM: int | None = None  # TODO(PRD): wajib diisi sebelum migrasi kb_chunks
    LLM_NUM_CTX: int = 8192
    JWT_SECRET: str = "change-me"
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_BOT_USERNAME: str | None = None
    APP_BASE_URL: str = "http://localhost:3000"
    TZ: str = "Asia/Jakarta"
    PHOENIX_ENABLED: bool = False


settings = Settings()
