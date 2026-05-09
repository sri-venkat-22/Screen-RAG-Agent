from __future__ import annotations

import re
from collections import OrderedDict
from io import BytesIO

from pypdf import PdfReader

from backend.app.schemas import ResumeProfile

SKILL_KEYWORDS = (
    "python",
    "fastapi",
    "flask",
    "django",
    "sqlalchemy",
    "postgresql",
    "mysql",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "microservices",
    "rest api",
    "graphql",
    "celery",
    "kafka",
    "rabbitmq",
    "spark",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "transformers",
    "llm",
    "llms",
    "openai",
    "langchain",
    "llamaindex",
    "vector database",
    "chromadb",
    "faiss",
    "rag",
    "retrieval",
    "embeddings",
    "embedding",
    "reranking",
    "prompt engineering",
    "nlp",
    "computer vision",
    "mlops",
    "llmops",
    "model monitoring",
    "observability",
    "evaluation",
    "monitoring",
    "airflow",
    "dbt",
    "ci/cd",
    "terraform",
    "react",
    "next.js",
    "typescript",
)

DOMAIN_KEYWORDS = OrderedDict(
    {
        "retrieval systems": ("rag", "retrieval", "vector", "embedding", "reranking"),
        "model serving": ("serving", "deployment", "inference", "latency", "monitoring"),
        "backend platforms": ("api", "microservice", "database", "queue", "cache", "observability"),
        "experimentation": ("ab test", "evaluation", "metrics", "offline", "online", "benchmark"),
        "data pipelines": ("etl", "pipeline", "airflow", "spark", "batch", "stream"),
        "frontend systems": ("react", "frontend", "browser", "accessibility", "hydration"),
        "cloud infrastructure": ("aws", "gcp", "azure", "docker", "kubernetes", "terraform"),
    }
)


def extract_resume_text(filename: str, content: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return _extract_pdf_text(content)

    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def build_resume_profile(
    resume_text: str,
    role: str,
    candidate_name_hint: str | None = None,
) -> ResumeProfile:
    cleaned = _normalize_whitespace(resume_text)
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    candidate_name = candidate_name_hint or _infer_candidate_name(lines)
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", cleaned)
    phone_match = re.search(r"(\+?\d[\d\s().-]{8,}\d)", cleaned)
    skills = _find_keywords(cleaned, SKILL_KEYWORDS)
    domains = _find_domains(cleaned)
    years = _infer_experience_years(cleaned)
    seniority = _infer_seniority(cleaned, years)
    highlights = _build_highlights(resume_text, skills, domains, role)
    summary = _build_summary(candidate_name, skills, domains, seniority)

    return ResumeProfile(
        candidate_name=candidate_name or "Candidate",
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        skills=skills[:8],
        technologies=skills[:10],
        domains=domains[:5],
        seniority=seniority,
        experience_years=years,
        highlights=highlights[:4],
        summary=summary,
    )


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(page for page in pages if page)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _infer_candidate_name(lines: list[str]) -> str:
    for line in lines[:6]:
        if "@" in line or len(line.split()) > 5:
            continue
        if re.search(r"\d", line):
            continue
        return line.title()
    return "Candidate"


def _find_keywords(text: str, vocabulary: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for keyword in vocabulary:
        pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
        if re.search(pattern, lowered):
            matches.append(keyword)
    return matches


def _find_domains(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for label, tokens in DOMAIN_KEYWORDS.items():
        if any(token in lowered for token in tokens):
            matches.append(label)
    return matches


def _infer_experience_years(text: str) -> int | None:
    match = re.search(r"(\d+)\+?\s+(?:years|yrs)", text.lower())
    return int(match.group(1)) if match else None


def _infer_seniority(text: str, years: int | None) -> str:
    lowered = text.lower()
    if years and years >= 5:
        return "advanced"
    if years and years >= 2:
        return "intermediate"
    if any(token in lowered for token in ("senior", "lead", "architect")):
        return "advanced"
    if any(token in lowered for token in ("intern", "student", "graduate", "fresher")):
        return "early-career"
    return "emerging"


def _build_highlights(text: str, skills: list[str], domains: list[str], role: str) -> list[str]:
    lines = [line.strip("•- ").strip() for line in text.splitlines() if line.strip()]
    highlights: list[str] = []
    if skills:
        highlights.append(f"Relevant stack for {role}: {', '.join(skills[:4])}")
    if domains:
        highlights.append(f"Domain exposure: {', '.join(domains[:3])}")
    for line in lines:
        if len(line.split()) < 6:
            continue
        if any(token in line.lower() for token in ("built", "designed", "implemented", "improved")):
            highlights.append(line)
        if len(highlights) >= 4:
            break
    return highlights


def _build_summary(
    candidate_name: str,
    skills: list[str],
    domains: list[str],
    seniority: str,
) -> str:
    skill_phrase = ", ".join(skills[:4]) if skills else "general engineering foundations"
    domain_phrase = ", ".join(domains[:2]) if domains else "product and systems work"
    return (
        f"{candidate_name or 'The candidate'} appears {seniority} with strengths in "
        f"{skill_phrase} and exposure to {domain_phrase}."
    )
