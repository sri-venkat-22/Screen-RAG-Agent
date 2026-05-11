from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

QuestionType = Literal[
    "theoretical",
    "coding",
    "scenario",
    "debugging",
    "project",
    "behavioral",
    "architecture",
    "mcq",
    "problem_solving",
    "open",
    "code",
    "system",
]
Difficulty = Literal["easy", "medium", "hard", "warmup", "core", "deep", "system"]


class RoleOption(BaseModel):
    value: str
    label: str
    blurb: str


class ResumeProject(BaseModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    domain: str | None = None
    evidence: list[str] = Field(default_factory=list)


class ResumeExperience(BaseModel):
    title: str
    organization: str | None = None
    description: str
    technologies: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    candidate_name: str
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    work_experience: list[ResumeExperience] = Field(default_factory=list)
    internships: list[ResumeExperience] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)
    semantic_tags: list[str] = Field(default_factory=list)
    full_text_digest: str | None = None
    seniority: str = "emerging"
    experience_years: int | None = None
    highlights: list[str] = Field(default_factory=list)
    summary: str


class RetrievedSource(BaseModel):
    chunk_id: str
    title: str
    topic: str
    score: float
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterviewQuestion(BaseModel):
    id: str
    index: int
    total: int
    type: QuestionType
    difficulty: Difficulty
    stage: str
    prompt: str
    hint: str | None = None
    focus_topic: str
    query: str
    sources: list[RetrievedSource] = Field(default_factory=list)
    rationale: str


class AnswerEvaluation(BaseModel):
    score: int
    keyword_coverage: int
    clarity: int
    specificity: int
    depth: int
    correctness: int = 0
    technical_depth: int = 0
    completeness: int = 0
    practical_reasoning: int = 0
    communication: int = 0
    confidence: int = 0
    expected_answer: str = ""
    evaluation_summary: str = ""
    missing_concepts: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_suggestion: str = ""
    evidence: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


class InterviewTurn(BaseModel):
    question: InterviewQuestion
    answer: str
    answer_seconds: int
    evaluation: AnswerEvaluation


class SignalScore(BaseModel):
    label: str
    score: int


class InterviewResult(BaseModel):
    index: int
    question: str
    candidate_answer: str
    expected_answer: str
    ai_evaluation: AnswerEvaluation
    score: int
    score_out_of_10: float
    improvement_suggestion: str
    answer_seconds: int = 0


class SessionInsights(BaseModel):
    overall_score: int
    strengths: list[str]
    weaknesses: list[str] = Field(default_factory=list)
    improvements: list[str]
    signal: list[SignalScore]
    recommendation: str
    technical_rating: int = 0
    communication_rating: int = 0
    problem_solving_rating: int = 0
    recommended_skill_improvements: list[str] = Field(default_factory=list)
    readiness_level: str = "Needs review"


class SessionSummary(BaseModel):
    session_id: str
    role: str
    candidate: str
    duration_sec: int
    resume_profile: ResumeProfile
    results: list[InterviewResult] = Field(default_factory=list)
    transcript: list[InterviewTurn] = Field(default_factory=list, exclude=True)
    insights: SessionInsights


class StartSessionResponse(BaseModel):
    session_id: str
    candidate: str
    role: str
    resume_profile: ResumeProfile
    question: InterviewQuestion


class SubmitAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=5)
    answer_seconds: int = Field(default=0, ge=0)


class AnswerResponse(BaseModel):
    done: bool
    latest_evaluation: AnswerEvaluation
    next_question: InterviewQuestion | None = None
    summary: SessionSummary | None = None
