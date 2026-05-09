from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

QuestionType = Literal["open", "scenario", "code", "system"]
Difficulty = Literal["warmup", "core", "deep", "system"]


class RoleOption(BaseModel):
    value: str
    label: str
    blurb: str


class ResumeProfile(BaseModel):
    candidate_name: str
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
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


class SessionInsights(BaseModel):
    overall_score: int
    strengths: list[str]
    improvements: list[str]
    signal: list[SignalScore]
    recommendation: str


class SessionSummary(BaseModel):
    session_id: str
    role: str
    candidate: str
    duration_sec: int
    resume_profile: ResumeProfile
    transcript: list[InterviewTurn]
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

