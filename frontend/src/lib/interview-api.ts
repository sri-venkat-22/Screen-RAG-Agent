const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "http://127.0.0.1:8000/api";

export type Role = "backend" | "ai-ml";
export type QuestionType = "open" | "code" | "scenario" | "system";
export type Difficulty = "warmup" | "core" | "deep" | "system";

export const ROLES: { value: Role; label: string; blurb: string }[] = [
  {
    value: "ai-ml",
    label: "AI / ML Engineer",
    blurb: "RAG, retrieval, evaluation",
  },
  {
    value: "backend",
    label: "Backend Engineer",
    blurb: "APIs, systems, observability",
  },
];

export interface ResumeProfile {
  candidateName: string;
  email?: string | null;
  phone?: string | null;
  skills: string[];
  technologies: string[];
  domains: string[];
  seniority: string;
  experienceYears?: number | null;
  highlights: string[];
  summary: string;
}

export interface RetrievedSource {
  chunkId: string;
  title: string;
  topic: string;
  score: number;
  excerpt: string;
  metadata: Record<string, unknown>;
}

export interface Question {
  id: string;
  index: number;
  total: number;
  type: QuestionType;
  difficulty: Difficulty;
  stage: string;
  prompt: string;
  hint?: string;
  focusTopic: string;
  query: string;
  rationale: string;
  sources: RetrievedSource[];
}

export interface AnswerEvaluation {
  score: number;
  keywordCoverage: number;
  clarity: number;
  specificity: number;
  depth: number;
  evidence: string[];
  strengths: string[];
  improvements: string[];
}

export interface SessionInsights {
  overallScore: number;
  strengths: string[];
  improvements: string[];
  signal: { label: string; score: number }[];
  recommendation: string;
}

export interface TranscriptTurn {
  question: Question;
  answer: string;
  answerSeconds: number;
  evaluation: AnswerEvaluation;
}

export interface SessionSummary {
  sessionId: string;
  role: Role;
  candidate: string;
  durationSec: number;
  resumeProfile: ResumeProfile;
  transcript: TranscriptTurn[];
  insights: SessionInsights;
}

export interface StartSessionInput {
  resumeFile: File;
  role: Role;
  candidateName: string;
}

export async function startSession(input: StartSessionInput): Promise<{
  sessionId: string;
  candidate: string;
  role: Role;
  resumeProfile: ResumeProfile;
  question: Question;
}> {
  const formData = new FormData();
  formData.append("resume", input.resumeFile);
  formData.append("role", input.role);
  if (input.candidateName.trim()) {
    formData.append("candidate_name", input.candidateName.trim());
  }

  const response = await request<BackendStartSessionResponse>(
    "/interviews/sessions",
    {
      method: "POST",
      body: formData,
    },
  );

  return {
    sessionId: response.session_id,
    candidate: response.candidate,
    role: response.role,
    resumeProfile: mapResumeProfile(response.resume_profile),
    question: mapQuestion(response.question),
  };
}

export async function submitAnswer(args: {
  sessionId: string;
  answerText: string;
  answerSeconds: number;
}): Promise<{
  done: boolean;
  latestEvaluation: AnswerEvaluation;
  nextQuestion?: Question;
  summary?: SessionSummary;
}> {
  const response = await request<BackendAnswerResponse>(
    `/interviews/sessions/${args.sessionId}/answers`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        answer_text: args.answerText,
        answer_seconds: args.answerSeconds,
      }),
    },
  );

  return {
    done: response.done,
    latestEvaluation: mapEvaluation(response.latest_evaluation),
    nextQuestion: response.next_question
      ? mapQuestion(response.next_question)
      : undefined,
    summary: response.summary ? mapSummary(response.summary) : undefined,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({
      detail: `Request failed with status ${response.status}`,
    }));
    throw new Error(payload.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

function mapSummary(summary: BackendSessionSummary): SessionSummary {
  return {
    sessionId: summary.session_id,
    role: summary.role,
    candidate: summary.candidate,
    durationSec: summary.duration_sec,
    resumeProfile: mapResumeProfile(summary.resume_profile),
    transcript: summary.transcript.map((turn) => ({
      question: mapQuestion(turn.question),
      answer: turn.answer,
      answerSeconds: turn.answer_seconds,
      evaluation: mapEvaluation(turn.evaluation),
    })),
    insights: {
      overallScore: summary.insights.overall_score,
      strengths: summary.insights.strengths,
      improvements: summary.insights.improvements,
      signal: summary.insights.signal,
      recommendation: summary.insights.recommendation,
    },
  };
}

function mapResumeProfile(profile: BackendResumeProfile): ResumeProfile {
  return {
    candidateName: profile.candidate_name,
    email: profile.email,
    phone: profile.phone,
    skills: profile.skills,
    technologies: profile.technologies,
    domains: profile.domains,
    seniority: profile.seniority,
    experienceYears: profile.experience_years,
    highlights: profile.highlights,
    summary: profile.summary,
  };
}

function mapQuestion(question: BackendQuestion): Question {
  return {
    id: question.id,
    index: question.index,
    total: question.total,
    type: question.type,
    difficulty: question.difficulty,
    stage: question.stage,
    prompt: question.prompt,
    hint: question.hint,
    focusTopic: question.focus_topic,
    query: question.query,
    rationale: question.rationale,
    sources: question.sources.map((source) => ({
      chunkId: source.chunk_id,
      title: source.title,
      topic: source.topic,
      score: source.score,
      excerpt: source.excerpt,
      metadata: source.metadata,
    })),
  };
}

function mapEvaluation(evaluation: BackendEvaluation): AnswerEvaluation {
  return {
    score: evaluation.score,
    keywordCoverage: evaluation.keyword_coverage,
    clarity: evaluation.clarity,
    specificity: evaluation.specificity,
    depth: evaluation.depth,
    evidence: evaluation.evidence,
    strengths: evaluation.strengths,
    improvements: evaluation.improvements,
  };
}

interface BackendResumeProfile {
  candidate_name: string;
  email?: string | null;
  phone?: string | null;
  skills: string[];
  technologies: string[];
  domains: string[];
  seniority: string;
  experience_years?: number | null;
  highlights: string[];
  summary: string;
}

interface BackendSource {
  chunk_id: string;
  title: string;
  topic: string;
  score: number;
  excerpt: string;
  metadata: Record<string, unknown>;
}

interface BackendQuestion {
  id: string;
  index: number;
  total: number;
  type: QuestionType;
  difficulty: Difficulty;
  stage: string;
  prompt: string;
  hint?: string;
  focus_topic: string;
  query: string;
  rationale: string;
  sources: BackendSource[];
}

interface BackendEvaluation {
  score: number;
  keyword_coverage: number;
  clarity: number;
  specificity: number;
  depth: number;
  evidence: string[];
  strengths: string[];
  improvements: string[];
}

interface BackendTranscriptTurn {
  question: BackendQuestion;
  answer: string;
  answer_seconds: number;
  evaluation: BackendEvaluation;
}

interface BackendSessionSummary {
  session_id: string;
  role: Role;
  candidate: string;
  duration_sec: number;
  resume_profile: BackendResumeProfile;
  transcript: BackendTranscriptTurn[];
  insights: {
    overall_score: number;
    strengths: string[];
    improvements: string[];
    signal: { label: string; score: number }[];
    recommendation: string;
  };
}

interface BackendStartSessionResponse {
  session_id: string;
  candidate: string;
  role: Role;
  resume_profile: BackendResumeProfile;
  question: BackendQuestion;
}

interface BackendAnswerResponse {
  done: boolean;
  latest_evaluation: BackendEvaluation;
  next_question?: BackendQuestion | null;
  summary?: BackendSessionSummary | null;
}
