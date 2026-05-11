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
    "software": RoleDefinition(
        value="software",
        label="Software Engineer",
        blurb="General software design, coding, debugging, and delivery",
        collection_name="software_engineer",
        knowledge_file="software_engineer.md",
        core_topics=(
            "data structures and algorithms",
            "object oriented design",
            "api contracts",
            "debugging",
            "testing",
            "performance",
            "maintainability",
            "system design fundamentals",
        ),
        query_seeds=(
            "software engineering data structures algorithms design patterns testing",
            "debugging performance maintainability code quality api contracts",
            "system design fundamentals scalability reliability tradeoffs",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "project", "easy", "candidate_background"),
            QuestionBlueprint("Implementation", "coding", "medium", "implementation"),
            QuestionBlueprint("Debugging", "debugging", "medium", "quality"),
            QuestionBlueprint("Design", "architecture", "hard", "production"),
            QuestionBlueprint("Tradeoffs", "behavioral", "medium", "tradeoffs"),
        ),
    ),
    "frontend": RoleDefinition(
        value="frontend",
        label="Frontend Engineer",
        blurb="React architecture, browser performance, accessibility, and UX systems",
        collection_name="frontend_engineer",
        knowledge_file="frontend_engineer.md",
        core_topics=(
            "react rendering",
            "state management",
            "web performance",
            "accessibility",
            "component architecture",
            "browser networking",
            "design systems",
            "testing strategy",
        ),
        query_seeds=(
            "react rendering state management component architecture",
            "web performance core web vitals bundle splitting hydration",
            "accessibility keyboard navigation aria semantic html",
            "frontend testing design systems browser networking resilience",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Rendering & State", "scenario", "core", "frontend_state"),
            QuestionBlueprint("Applied UI Architecture", "code", "core", "implementation"),
            QuestionBlueprint("Performance & Accessibility", "scenario", "deep", "quality"),
            QuestionBlueprint("Client Architecture", "system", "system", "production"),
        ),
    ),
    "cloud": RoleDefinition(
        value="cloud",
        label="Cloud Engineer",
        blurb="Cloud architecture, networking, security, cost, and operations",
        collection_name="cloud_engineer",
        knowledge_file="cloud_engineer.md",
        core_topics=(
            "cloud architecture",
            "networking",
            "identity and access management",
            "container deployment",
            "cost optimization",
            "observability",
            "high availability",
            "disaster recovery",
        ),
        query_seeds=(
            "cloud architecture networking iam containers observability cost optimization",
            "high availability disaster recovery autoscaling load balancing deployment",
        ),
        blueprints=(
            QuestionBlueprint("Cloud Project", "project", "easy", "candidate_background"),
            QuestionBlueprint("Architecture", "architecture", "medium", "production"),
            QuestionBlueprint("Troubleshooting", "debugging", "medium", "incident_response"),
            QuestionBlueprint("Security", "scenario", "hard", "quality"),
            QuestionBlueprint("Operations", "problem_solving", "hard", "reliability"),
        ),
    ),
    "fullstack": RoleDefinition(
        value="fullstack",
        label="Full-Stack Engineer",
        blurb="Product delivery across UI, APIs, data models, and deployment",
        collection_name="fullstack_engineer",
        knowledge_file="fullstack_engineer.md",
        core_topics=(
            "product architecture",
            "api contracts",
            "data modeling",
            "frontend state",
            "authentication",
            "testing",
            "deployment",
            "observability",
        ),
        query_seeds=(
            "full stack product architecture api contracts frontend state",
            "authentication authorization data modeling multi tenant applications",
            "testing deployment observability end to end feature ownership",
            "tradeoffs client server boundaries product engineering reliability",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Product Boundaries", "scenario", "core", "tradeoffs"),
            QuestionBlueprint("Feature Design", "code", "core", "implementation"),
            QuestionBlueprint("Reliability & Delivery", "scenario", "deep", "reliability"),
            QuestionBlueprint("End-to-End Architecture", "system", "system", "production"),
        ),
    ),
    "data": RoleDefinition(
        value="data",
        label="Data Engineer",
        blurb="Pipelines, data modeling, quality checks, and analytics platforms",
        collection_name="data_engineer",
        knowledge_file="data_engineer.md",
        core_topics=(
            "batch pipelines",
            "stream processing",
            "data modeling",
            "orchestration",
            "data quality",
            "warehousing",
            "lineage",
            "feature stores",
        ),
        query_seeds=(
            "batch pipelines orchestration data quality lineage",
            "stream processing exactly once semantics event time windows",
            "warehouse modeling star schema denormalized analytics tables",
            "feature store online offline parity machine learning data pipelines",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Pipeline Fundamentals", "scenario", "core", "pipeline"),
            QuestionBlueprint("Data Model Design", "code", "core", "implementation"),
            QuestionBlueprint("Quality & Lineage", "scenario", "deep", "quality"),
            QuestionBlueprint("Platform Architecture", "system", "system", "production"),
        ),
    ),
    "data-analyst": RoleDefinition(
        value="data-analyst",
        label="Data Analyst",
        blurb="SQL, dashboards, metrics, statistics, and business insight",
        collection_name="data_analyst",
        knowledge_file="data_analyst.md",
        core_topics=(
            "sql analysis",
            "dashboard design",
            "data cleaning",
            "statistical reasoning",
            "business metrics",
            "experimentation",
            "visualization",
            "stakeholder communication",
        ),
        query_seeds=(
            "data analyst sql dashboards metrics visualization statistics",
            "data cleaning experimentation business insight stakeholder communication",
        ),
        blueprints=(
            QuestionBlueprint("Analytics Project", "project", "easy", "candidate_background"),
            QuestionBlueprint("SQL Reasoning", "coding", "medium", "implementation"),
            QuestionBlueprint("Metrics", "scenario", "medium", "evaluation"),
            QuestionBlueprint("Dashboard Quality", "debugging", "hard", "quality"),
            QuestionBlueprint("Business Impact", "behavioral", "medium", "tradeoffs"),
        ),
    ),
    "devops": RoleDefinition(
        value="devops",
        label="DevOps / SRE",
        blurb="Infrastructure, reliability, observability, and deployment systems",
        collection_name="devops_sre",
        knowledge_file="devops_sre.md",
        core_topics=(
            "incident response",
            "slo design",
            "kubernetes",
            "deployment strategy",
            "infrastructure as code",
            "observability",
            "capacity planning",
            "security operations",
        ),
        query_seeds=(
            "slo error budget incident response observability",
            "kubernetes deployment strategy zero downtime rollout rollback",
            "infrastructure as code capacity planning reliability automation",
            "multi region architecture disaster recovery security operations",
        ),
        blueprints=(
            QuestionBlueprint("Resume Deep Dive", "open", "warmup", "candidate_background"),
            QuestionBlueprint("Reliability Fundamentals", "scenario", "core", "reliability"),
            QuestionBlueprint("Deployment Design", "code", "core", "implementation"),
            QuestionBlueprint("Incident Response", "scenario", "deep", "incident_response"),
            QuestionBlueprint("Platform Architecture", "system", "system", "production"),
        ),
    ),
    "cybersecurity": RoleDefinition(
        value="cybersecurity",
        label="Cybersecurity",
        blurb="Security fundamentals, threat modeling, testing, and incident response",
        collection_name="cybersecurity",
        knowledge_file="cybersecurity.md",
        core_topics=(
            "threat modeling",
            "owasp vulnerabilities",
            "authentication and authorization",
            "network security",
            "encryption",
            "secure coding",
            "incident response",
            "logging and detection",
        ),
        query_seeds=(
            "cybersecurity threat modeling owasp secure coding authentication authorization",
            "incident response logging detection network security encryption",
        ),
        blueprints=(
            QuestionBlueprint("Security Resume Deep Dive", "project", "easy", "candidate_background"),
            QuestionBlueprint("Threat Modeling", "scenario", "medium", "quality"),
            QuestionBlueprint("Secure Implementation", "coding", "medium", "implementation"),
            QuestionBlueprint("Incident Response", "debugging", "hard", "incident_response"),
            QuestionBlueprint("Architecture", "architecture", "hard", "production"),
        ),
    ),
    "testing": RoleDefinition(
        value="testing",
        label="Testing Engineer",
        blurb="QA automation, test design, reliability, and release confidence",
        collection_name="testing_engineer",
        knowledge_file="testing_engineer.md",
        core_topics=(
            "test strategy",
            "automation frameworks",
            "unit integration e2e testing",
            "test data management",
            "defect triage",
            "ci quality gates",
            "performance testing",
            "accessibility testing",
        ),
        query_seeds=(
            "testing engineer test strategy automation selenium playwright pytest quality gates",
            "defect triage test data performance testing integration e2e testing",
        ),
        blueprints=(
            QuestionBlueprint("QA Project", "project", "easy", "candidate_background"),
            QuestionBlueprint("Test Design", "scenario", "medium", "quality"),
            QuestionBlueprint("Automation", "coding", "medium", "implementation"),
            QuestionBlueprint("Debugging", "debugging", "hard", "incident_response"),
            QuestionBlueprint("Release Quality", "architecture", "hard", "production"),
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
