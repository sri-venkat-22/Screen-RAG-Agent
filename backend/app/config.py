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
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_reranking: bool = True
    enable_local_question_generation: bool = True
    question_generator_model_name: str = "meta-llama/Llama-3.2-3B-Instruct"
    question_generator_fallback_model_names: list[str] = Field(
        default_factory=lambda: [
            "meta-llama/Llama-3.1-70B-Instruct",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "Qwen/Qwen2.5-7B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "microsoft/Phi-3-mini-4k-instruct",
        ]
    )
    question_generator_local_files_only: bool = True
    question_generator_max_new_tokens: int = 360
    question_similarity_threshold: float = 0.72
    question_regeneration_attempts: int = 8
    enable_local_answer_evaluation: bool = True
    answer_evaluator_model_name: str = "meta-llama/Llama-3.2-3B-Instruct"
    answer_evaluator_fallback_model_names: list[str] = Field(
        default_factory=lambda: [
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "Qwen/Qwen2.5-7B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "microsoft/Phi-3-mini-4k-instruct",
        ]
    )
    answer_evaluator_local_files_only: bool = True
    answer_evaluator_max_new_tokens: int = 900
    interview_question_count: int = 7
    retrieval_top_k: int = 4
    ingestion_batch_size: int = 64
    max_chunks_per_source_doc: int = 180
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
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

    @field_validator(
        "question_generator_fallback_model_names",
        "answer_evaluator_fallback_model_names",
        mode="before",
    )
    @classmethod
    def _parse_model_list(cls, value: str | list[str]) -> list[str]:
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
