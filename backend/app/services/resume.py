from __future__ import annotations

import re
from collections import Counter, OrderedDict
from io import BytesIO

from pypdf import PdfReader

from backend.app.schemas import ResumeExperience, ResumeProfile, ResumeProject

TECHNOLOGY_KEYWORDS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "go",
    "rust",
    "sql",
    "html",
    "css",
    "react",
    "next.js",
    "node.js",
    "express",
    "fastapi",
    "flask",
    "django",
    "spring boot",
    "sqlalchemy",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "docker",
    "kubernetes",
    "jenkins",
    "github actions",
    "gitlab ci",
    "ci/cd",
    "terraform",
    "ansible",
    "aws",
    "gcp",
    "azure",
    "linux",
    "nginx",
    "kafka",
    "rabbitmq",
    "spark",
    "airflow",
    "dbt",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "keras",
    "transformers",
    "hugging face",
    "openai",
    "langchain",
    "llamaindex",
    "chromadb",
    "faiss",
    "rag",
    "llm",
    "nlp",
    "computer vision",
    "power bi",
    "tableau",
    "excel",
    "selenium",
    "pytest",
    "junit",
    "cypress",
    "playwright",
    "owasp",
    "burp suite",
    "wireshark",
    "metasploit",
)

FRAMEWORK_KEYWORDS = (
    "react",
    "next.js",
    "angular",
    "vue",
    "tailwind",
    "bootstrap",
    "fastapi",
    "flask",
    "django",
    "express",
    "spring boot",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "selenium",
    "cypress",
    "playwright",
)

TOOL_KEYWORDS = (
    "git",
    "github",
    "gitlab",
    "jira",
    "postman",
    "swagger",
    "docker",
    "kubernetes",
    "jenkins",
    "github actions",
    "terraform",
    "ansible",
    "grafana",
    "prometheus",
    "datadog",
    "linux",
    "aws",
    "gcp",
    "azure",
    "figma",
    "power bi",
    "tableau",
    "burp suite",
    "wireshark",
)

DOMAIN_KEYWORDS = OrderedDict(
    {
        "ai/ml systems": ("machine learning", "deep learning", "model", "classification", "prediction"),
        "retrieval systems": ("rag", "retrieval", "vector", "embedding", "reranking", "semantic search"),
        "llm applications": ("llm", "prompt", "langchain", "openai", "chatbot", "generation"),
        "backend platforms": ("api", "microservice", "database", "queue", "cache", "authentication"),
        "frontend systems": ("react", "frontend", "browser", "responsive", "accessibility", "hydration"),
        "cloud infrastructure": ("aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ci/cd"),
        "devops and sre": ("slo", "monitoring", "deployment", "pipeline", "incident", "observability"),
        "data analytics": ("dashboard", "power bi", "tableau", "analytics", "visualization", "excel"),
        "data pipelines": ("etl", "pipeline", "airflow", "spark", "batch", "stream", "warehouse"),
        "cybersecurity": ("security", "owasp", "vulnerability", "penetration", "encryption", "auth"),
        "testing and qa": ("testing", "automation", "selenium", "pytest", "junit", "test cases"),
        "healthcare": ("telemedicine", "medical", "patient", "health", "diagnosis"),
        "finance": ("payment", "banking", "fraud", "portfolio", "trading"),
        "education": ("learning", "student", "course", "education", "assessment"),
        "e-commerce": ("cart", "checkout", "order", "inventory", "recommendation"),
    }
)

SECTION_ALIASES = {
    "skills": (
        "skills",
        "technical skills",
        "technologies",
        "tech stack",
        "tools and technologies",
        "programming skills",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
    ),
    "internships": ("internship", "internships", "internship experience"),
    "projects": ("projects", "academic projects", "personal projects", "key projects"),
    "certifications": ("certifications", "certificates", "licenses", "courses"),
    "achievements": ("achievements", "awards", "accomplishments", "honors"),
    "education": ("education", "academics", "qualifications"),
}


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
    sections = _split_sections(lines)
    candidate_name = candidate_name_hint or _infer_candidate_name(lines)
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", cleaned)
    phone_match = re.search(r"(\+?\d[\d\s().-]{8,}\d)", cleaned)

    technologies = _rank_terms(cleaned, TECHNOLOGY_KEYWORDS, sections)
    frameworks = _rank_terms(cleaned, FRAMEWORK_KEYWORDS, sections)
    tools = _rank_terms(cleaned, TOOL_KEYWORDS, sections)
    skills = _merge_ranked(technologies, frameworks, tools, _extract_skill_section_terms(sections))
    domains = _find_domains(cleaned)
    projects = _extract_projects(sections, technologies, domains)
    work_experience = _extract_experience(sections.get("experience", []), technologies)
    internships = _extract_experience(sections.get("internships", []), technologies)
    inferred_internships = [
        item for item in work_experience if "intern" in f"{item.title} {item.description}".lower()
    ]
    internships = _dedupe_experience([*internships, *inferred_internships])
    certifications = _extract_list_items(sections.get("certifications", []), cleaned, ("certified", "certificate"))
    achievements = _extract_list_items(sections.get("achievements", []), cleaned, ("award", "rank", "winner"))
    education = _extract_list_items(sections.get("education", []), cleaned, ("university", "college", "b.tech", "bachelor"))
    years = _infer_experience_years(cleaned)
    seniority = _infer_seniority(cleaned, years, work_experience, internships, projects)
    semantic_tags = _semantic_tags(cleaned, skills, domains, projects)
    domain_expertise = _merge_ranked(domains, semantic_tags)
    highlights = _build_highlights(skills, domains, projects, work_experience, internships, achievements, role)
    summary = _build_summary(candidate_name, skills, domain_expertise, seniority, projects, work_experience)

    return ResumeProfile(
        candidate_name=candidate_name or "Candidate",
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        skills=skills[:12],
        technologies=technologies[:14],
        tools=tools[:12],
        frameworks=frameworks[:10],
        certifications=certifications[:6],
        work_experience=work_experience[:5],
        internships=internships[:4],
        projects=projects[:6],
        achievements=achievements[:6],
        education=education[:4],
        domains=domains[:8],
        domain_expertise=domain_expertise[:10],
        semantic_tags=semantic_tags[:14],
        full_text_digest=_digest_resume(cleaned),
        seniority=seniority,
        experience_years=years,
        highlights=highlights[:8],
        summary=summary,
    )


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(page for page in pages if page)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"overview": []}
    current = "overview"
    for raw_line in lines:
        line = raw_line.strip()
        section = _section_name(line)
        if section:
            current = section
            sections.setdefault(current, [])
            remainder = re.sub(r"^[A-Za-z /&+-]+:\s*", "", line).strip()
            if remainder and _section_name(remainder) is None and remainder.lower() != line.lower():
                sections[current].append(remainder)
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _section_name(line: str) -> str | None:
    clean = re.sub(r"[^a-z0-9/&+ .-]", "", line.lower()).strip(" :-")
    if not clean or len(clean.split()) > 6:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if clean in aliases:
            return canonical
    return None


def _infer_candidate_name(lines: list[str]) -> str:
    for line in lines[:8]:
        if "@" in line or len(line.split()) > 5:
            continue
        if re.search(r"\d|http|linkedin|github", line.lower()):
            continue
        return line.title()
    return "Candidate"


def _rank_terms(text: str, vocabulary: tuple[str, ...], sections: dict[str, list[str]]) -> list[str]:
    lowered = text.lower()
    section_text = " ".join(sections.get("skills", [])).lower()
    scored: list[tuple[str, int]] = []
    for keyword in vocabulary:
        pattern = r"(?<![\w.+#-])" + re.escape(keyword.lower()) + r"(?![\w.+#-])"
        count = len(re.findall(pattern, lowered))
        if count == 0:
            continue
        score = count + (3 if re.search(pattern, section_text) else 0)
        scored.append((keyword, score))
    return [term for term, _ in sorted(scored, key=lambda item: (-item[1], item[0]))]


def _extract_skill_section_terms(sections: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    for line in sections.get("skills", []):
        pieces = re.split(r"[,|;/]", line)
        for piece in pieces:
            term = piece.strip(" -:()")
            if 2 <= len(term) <= 32 and not term.lower().startswith(("technical", "skills")):
                terms.append(term)
    return _dedupe(terms)


def _find_domains(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for label, tokens in DOMAIN_KEYWORDS.items():
        score = sum(1 for token in tokens if token in lowered)
        if score:
            matches.append(label)
    return matches


def _extract_projects(
    sections: dict[str, list[str]],
    technologies: list[str],
    domains: list[str],
) -> list[ResumeProject]:
    project_lines = sections.get("projects", [])
    if not project_lines:
        project_lines = [
            line
            for lines in sections.values()
            for line in lines
            if any(token in line.lower() for token in ("project", "built", "developed", "implemented", "designed"))
        ]
    blocks = _entry_blocks(project_lines)
    projects: list[ResumeProject] = []
    for block in blocks[:8]:
        title = _clean_entry_title(block[0])
        description = " ".join(block[1:] or block)
        tech = _terms_in_text(description, technologies)
        domain = _first_domain(description, domains)
        projects.append(
            ResumeProject(
                name=title[:90] or "Resume project",
                description=_compact(description, 420),
                technologies=tech[:8],
                domain=domain,
                evidence=block[:4],
            )
        )
    return _dedupe_projects(projects)


def _extract_experience(lines: list[str], technologies: list[str]) -> list[ResumeExperience]:
    blocks = _entry_blocks(lines)
    experiences: list[ResumeExperience] = []
    for block in blocks[:8]:
        title, organization = _split_title_org(block[0])
        description = " ".join(block[1:] or block)
        experiences.append(
            ResumeExperience(
                title=title[:100] or "Experience",
                organization=organization,
                description=_compact(description, 420),
                technologies=_terms_in_text(description, technologies)[:8],
                evidence=block[:4],
            )
        )
    return experiences


def _entry_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in lines:
        line = raw_line.strip(" -\t")
        if not line:
            continue
        is_title = _looks_like_entry_title(line)
        if is_title and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _looks_like_entry_title(line: str) -> bool:
    lowered = line.lower().strip()
    if len(line.split()) <= 8 and not lowered.endswith((".", ";")):
        return True
    return bool(re.match(r"^[A-Z][A-Za-z0-9 /&+.-]{2,80}\s*[-|:]", line))


def _clean_entry_title(line: str) -> str:
    title = re.split(r"\s[-|:]\s", line, maxsplit=1)[0].strip()
    title = re.sub(r"^(project|title)\s*[:.-]\s*", "", title, flags=re.IGNORECASE)
    return title or line[:90]


def _split_title_org(line: str) -> tuple[str, str | None]:
    parts = re.split(r"\s[-|@]\s", line, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return _clean_entry_title(line), None


def _extract_list_items(lines: list[str], text: str, cues: tuple[str, ...]) -> list[str]:
    items = [line.strip(" -\t") for line in lines if len(line.strip().split()) >= 2]
    if not items:
        items = [
            line.strip(" -\t")
            for line in text.split(".")
            if any(cue in line.lower() for cue in cues) and len(line.split()) >= 3
        ]
    return _dedupe([_compact(item, 180) for item in items])[:8]


def _infer_experience_years(text: str) -> int | None:
    matches = re.findall(r"(\d+)\+?\s+(?:years|yrs)", text.lower())
    if matches:
        return max(int(match) for match in matches)
    year_ranges = re.findall(r"(20\d{2})\s*[-]\s*(20\d{2}|present|current)", text.lower())
    if year_ranges:
        total = 0
        for start, end in year_ranges:
            end_year = 2026 if end in {"present", "current"} else int(end)
            total += max(0, end_year - int(start))
        return total or None
    return None


def _infer_seniority(
    text: str,
    years: int | None,
    work_experience: list[ResumeExperience],
    internships: list[ResumeExperience],
    projects: list[ResumeProject],
) -> str:
    lowered = text.lower()
    if years and years >= 5:
        return "advanced"
    if years and years >= 2:
        return "intermediate"
    if any(token in lowered for token in ("senior", "lead", "architect", "principal")):
        return "advanced"
    if len(work_experience) >= 2:
        return "intermediate"
    if internships or any(token in lowered for token in ("intern", "student", "graduate", "fresher")):
        return "early-career"
    if len(projects) >= 2:
        return "emerging"
    return "emerging"


def _semantic_tags(
    text: str,
    skills: list[str],
    domains: list[str],
    projects: list[ResumeProject],
) -> list[str]:
    lowered = text.lower()
    scores: Counter[str] = Counter()
    for domain, tokens in DOMAIN_KEYWORDS.items():
        scores[domain] += sum(1 for token in tokens if token in lowered) * 3
    for skill in skills:
        scores[skill] += len(re.findall(re.escape(skill.lower()), lowered)) + 1
    for project in projects:
        project_text = f"{project.name} {project.description}".lower()
        for domain, tokens in DOMAIN_KEYWORDS.items():
            scores[domain] += sum(1 for token in tokens if token in project_text) * 2
    for domain in domains:
        scores[domain] += 4
    return [tag for tag, score in scores.most_common(16) if score > 0]


def _build_highlights(
    skills: list[str],
    domains: list[str],
    projects: list[ResumeProject],
    work_experience: list[ResumeExperience],
    internships: list[ResumeExperience],
    achievements: list[str],
    role: str,
) -> list[str]:
    highlights: list[str] = []
    if skills:
        highlights.append(f"Relevant stack for {role}: {', '.join(skills[:6])}")
    if domains:
        highlights.append(f"Domain exposure: {', '.join(domains[:4])}")
    for project in projects[:3]:
        highlights.append(f"Project: {project.name} - {project.description}")
    for exp in [*work_experience[:2], *internships[:1]]:
        org = f" at {exp.organization}" if exp.organization else ""
        highlights.append(f"Experience: {exp.title}{org} - {exp.description}")
    highlights.extend(achievements[:2])
    return [_compact(item, 240) for item in _dedupe(highlights)]


def _build_summary(
    candidate_name: str,
    skills: list[str],
    domains: list[str],
    seniority: str,
    projects: list[ResumeProject],
    work_experience: list[ResumeExperience],
) -> str:
    skill_phrase = ", ".join(skills[:5]) if skills else "general engineering foundations"
    domain_phrase = ", ".join(domains[:3]) if domains else "product and systems work"
    project_phrase = (
        f" Notable projects include {', '.join(project.name for project in projects[:2])}."
        if projects
        else ""
    )
    experience_phrase = (
        f" Work history includes {', '.join(exp.title for exp in work_experience[:2])}."
        if work_experience
        else ""
    )
    return (
        f"{candidate_name or 'The candidate'} appears {seniority} with strengths in "
        f"{skill_phrase} and exposure to {domain_phrase}.{project_phrase}{experience_phrase}"
    )


def _merge_ranked(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = item.strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
    return merged


def _terms_in_text(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def _first_domain(text: str, domains: list[str]) -> str | None:
    lowered = text.lower()
    for domain in domains:
        tokens = DOMAIN_KEYWORDS.get(domain, ())
        if any(token in lowered for token in tokens):
            return domain
    return domains[0] if domains else None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result


def _dedupe_projects(projects: list[ResumeProject]) -> list[ResumeProject]:
    seen: set[str] = set()
    result: list[ResumeProject] = []
    for project in projects:
        key = project.name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(project)
    return result


def _dedupe_experience(items: list[ResumeExperience]) -> list[ResumeExperience]:
    seen: set[str] = set()
    result: list[ResumeExperience] = []
    for item in items:
        key = f"{item.title}|{item.organization}|{item.description[:80]}".lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _compact(text: str, limit: int) -> str:
    normalized = _normalize_whitespace(text)
    return normalized[: limit - 3].rstrip() + "..." if len(normalized) > limit else normalized


def _digest_resume(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    useful = [sentence.strip() for sentence in sentences if len(sentence.split()) >= 6]
    return _compact(" ".join(useful[:18]) or text, 2600)
