from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionBlueprint:
    stage: str
    question_type: str
    difficulty: str
    lens: str


@dataclass(frozen=True)
class RoleDefinition:
    value: str
    label: str
    blurb: str
    collection_name: str
    knowledge_file: str
    core_topics: tuple[str, ...]
    query_seeds: tuple[str, ...]
    blueprints: tuple[QuestionBlueprint, ...]


ROLE_LIBRARY: dict[str, RoleDefinition] = {
    "ai-ml": RoleDefinition(
        value="ai-ml",
        label="AI / ML Engineer",
        blurb="RAG, evaluation, retrieval, and production ML systems",
        collection_name="ai_ml_engineer",
        knowledge_file="ai_ml_engineer.md",
        core_topics=(
            "feature engineering",
            "model evaluation",
            "retrieval augmented generation",
            "embedding models",
            "chunking strategy",
            "reranking",
            "hallucination mitigation",
            "deployment and monitoring",
        ),
        query_seeds=(
            "retrieval augmented generation chunking embeddings reranking grounding",
            "model evaluation overfitting bias variance offline metrics online metrics",
            "production ml monitoring drift latency rollback feedback loops",
            "llm systems prompt grounding context windows hallucination mitigation",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Retrieval Fundamentals", "scenario", "core", "retrieval"),
            QuestionBlueprint("Applied RAG Design", "code", "core", "implementation"),
            QuestionBlueprint("Evaluation & Reliability", "scenario", "deep", "evaluation"),
            QuestionBlueprint("Production Architecture", "system", "system", "production"),
        ),
    ),
    "backend": RoleDefinition(
        value="backend",
        label="Backend Engineer",
        blurb="APIs, databases, observability, and distributed systems",
        collection_name="backend_engineer",
        knowledge_file="backend_engineer.md",
        core_topics=(
            "api design",
            "database indexing",
            "caching",
            "queues and background jobs",
            "consistency and idempotency",
            "observability",
            "scalability",
            "authentication and authorization",
        ),
        query_seeds=(
            "api design validation pagination versioning idempotency error handling",
            "database indexing transactions consistency contention and caching",
            "distributed systems queues retries outbox rate limiting and observability",
            "backend scalability p99 latency bottlenecks debugging and incident response",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Service Fundamentals", "scenario", "core", "service_debugging"),
            QuestionBlueprint("Applied API Design", "code", "core", "implementation"),
            QuestionBlueprint("Reliability Tradeoffs", "scenario", "deep", "reliability"),
            QuestionBlueprint("System Design", "system", "system", "production"),
        ),
    ),
}


def get_role(role_value: str) -> RoleDefinition:
    try:
        return ROLE_LIBRARY[role_value]
    except KeyError as exc:
        raise ValueError(f"Unsupported role '{role_value}'.") from exc


def list_roles() -> list[RoleDefinition]:
    return list(ROLE_LIBRARY.values())

