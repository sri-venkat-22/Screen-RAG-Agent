from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "PGAGI Candidate Screening Engine"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'app.db').resolve().as_posix()}"
    vector_store_dir: Path = BACKEND_DIR / "data" / "chroma"
    knowledge_base_dir: Path = BACKEND_DIR / "data" / "knowledge_base"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    interview_question_count: int = 5
    retrieval_top_k: int = 4
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("vector_store_dir", "knowledge_base_dir", mode="before")
    @classmethod
    def _resolve_paths(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (ROOT_DIR / path).resolve()

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def prepare_directories(self) -> None:
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.removeprefix("sqlite:///"))
            if not db_path.is_absolute():
                db_path = (ROOT_DIR / db_path).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare_directories()
    return settings

