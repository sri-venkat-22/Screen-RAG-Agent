const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "http://127.0.0.1:8000/api";

export type Role =
  | "backend"
  | "ai-ml"
  | "frontend"
  | "fullstack"
  | "data"
  | "devops"
  | "software"
  | "cloud"
  | "data-analyst"
  | "cybersecurity"
  | "testing";
export type QuestionType =
  | "theoretical"
  | "coding"
  | "scenario"
  | "debugging"
  | "project"
  | "behavioral"
  | "architecture"
  | "mcq"
  | "problem_solving"
  | "open"
  | "code"
  | "system";
export type Difficulty =
  | "easy"
  | "medium"
  | "hard"
  | "warmup"
  | "core"
  | "deep"
  | "system";

export const ROLES: { value: Role; label: string; blurb: string }[] = [
  {
    value: "ai-ml",
    label: "AI / ML Engineer",
    blurb: "RAG, retrieval, evaluation",
  },
  {
    value: "software",
    label: "Software Engineer",
    blurb: "Coding, design, debugging",
  },
  {
    value: "backend",
    label: "Backend Engineer",
    blurb: "APIs, systems, observability",
  },
  {
    value: "frontend",
    label: "Frontend Engineer",
    blurb: "React, performance, accessibility",
  },
  {
    value: "fullstack",
    label: "Full-Stack Engineer",
    blurb: "UI, APIs, data, delivery",
  },
  {
    value: "data",
    label: "Data Engineer",
    blurb: "Pipelines, modeling, quality",
  },
  {
    value: "data-analyst",
    label: "Data Analyst",
    blurb: "SQL, dashboards, metrics",
  },
  {
    value: "cloud",
    label: "Cloud Engineer",
    blurb: "Cloud architecture, operations",
  },
  {
    value: "devops",
    label: "DevOps / SRE",
    blurb: "Infra, reliability, observability",
  },
  {
    value: "cybersecurity",
    label: "Cybersecurity",
    blurb: "Threats, security, incidents",
  },
  {
    value: "testing",
    label: "Testing Engineer",
    blurb: "QA, automation, release quality",
  },
];

export interface ResumeProject {
  name: string;
  description: string;
  technologies: string[];
  domain?: string | null;
  evidence: string[];
}

export interface ResumeExperience {
  title: string;
  organization?: string | null;
  description: string;
  technologies: string[];
  evidence: string[];
}

export interface ResumeProfile {
  candidateName: string;
  email?: string | null;
  phone?: string | null;
  skills: string[];
  technologies: string[];
  tools: string[];
  frameworks: string[];
  certifications: string[];
  workExperience: ResumeExperience[];
  internships: ResumeExperience[];
  projects: ResumeProject[];
  achievements: string[];
  education: string[];
  domains: string[];
  domainExpertise: string[];
  semanticTags: string[];
  fullTextDigest?: string | null;
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
  correctness: number;
  technicalDepth: number;
  completeness: number;
  practicalReasoning: number;
  communication: number;
  confidence: number;
  expectedAnswer: string;
  evaluationSummary: string;
  missingConcepts: string[];
  weaknesses: string[];
  improvementSuggestion: string;
  evidence: string[];
  strengths: string[];
  improvements: string[];
}

export interface SessionInsights {
  overallScore: number;
  strengths: string[];
  weaknesses: string[];
  improvements: string[];
  signal: { label: string; score: number }[];
  recommendation: string;
  technicalRating: number;
  communicationRating: number;
  problemSolvingRating: number;
  recommendedSkillImprovements: string[];
  readinessLevel: string;
}

export interface InterviewResult {
  index: number;
  question: string;
  candidateAnswer: string;
  expectedAnswer: string;
  aiEvaluation: AnswerEvaluation;
  score: number;
  scoreOutOf10: number;
  improvementSuggestion: string;
  answerSeconds: number;
}

export interface SessionSummary {
  sessionId: string;
  role: Role;
  candidate: string;
  durationSec: number;
  resumeProfile: ResumeProfile;
  results: InterviewResult[];
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
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    throw new Error(
      `Unable to connect to the interview engine. Please check your network connection and try again.`,
      { cause: error },
    );
  }
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
    results: (summary.results ?? []).map(mapInterviewResult),
    insights: {
      overallScore: summary.insights.overall_score,
      strengths: summary.insights.strengths,
      weaknesses: summary.insights.weaknesses ?? [],
      improvements: summary.insights.improvements,
      signal: summary.insights.signal,
      recommendation: summary.insights.recommendation,
      technicalRating: summary.insights.technical_rating ?? 0,
      communicationRating: summary.insights.communication_rating ?? 0,
      problemSolvingRating: summary.insights.problem_solving_rating ?? 0,
      recommendedSkillImprovements:
        summary.insights.recommended_skill_improvements ?? [],
      readinessLevel: summary.insights.readiness_level ?? "Needs review",
    },
  };
}

function mapInterviewResult(result: BackendInterviewResult): InterviewResult {
  return {
    index: result.index,
    question: result.question,
    candidateAnswer: result.candidate_answer,
    expectedAnswer: result.expected_answer,
    aiEvaluation: mapEvaluation(result.ai_evaluation),
    score: result.score,
    scoreOutOf10: result.score_out_of_10,
    improvementSuggestion: result.improvement_suggestion,
    answerSeconds: result.answer_seconds ?? 0,
  };
}

function mapResumeProfile(profile: BackendResumeProfile): ResumeProfile {
  return {
    candidateName: profile.candidate_name,
    email: profile.email,
    phone: profile.phone,
    skills: profile.skills ?? [],
    technologies: profile.technologies ?? [],
    tools: profile.tools ?? [],
    frameworks: profile.frameworks ?? [],
    certifications: profile.certifications ?? [],
    workExperience: profile.work_experience ?? [],
    internships: profile.internships ?? [],
    projects: profile.projects ?? [],
    achievements: profile.achievements ?? [],
    education: profile.education ?? [],
    domains: profile.domains ?? [],
    domainExpertise: profile.domain_expertise ?? [],
    semanticTags: profile.semantic_tags ?? [],
    fullTextDigest: profile.full_text_digest,
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
    correctness: evaluation.correctness ?? evaluation.keyword_coverage,
    technicalDepth: evaluation.technical_depth ?? evaluation.depth,
    completeness: evaluation.completeness ?? evaluation.keyword_coverage,
    practicalReasoning:
      evaluation.practical_reasoning ?? evaluation.specificity,
    communication: evaluation.communication ?? evaluation.clarity,
    confidence: evaluation.confidence ?? evaluation.clarity,
    expectedAnswer: evaluation.expected_answer ?? "",
    evaluationSummary: evaluation.evaluation_summary ?? "",
    missingConcepts: evaluation.missing_concepts ?? [],
    weaknesses: evaluation.weaknesses ?? [],
    improvementSuggestion:
      evaluation.improvement_suggestion ?? evaluation.improvements?.[0] ?? "",
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
  tools: string[];
  frameworks: string[];
  certifications: string[];
  work_experience: ResumeExperience[];
  internships: ResumeExperience[];
  projects: ResumeProject[];
  achievements: string[];
  education: string[];
  domains: string[];
  domain_expertise: string[];
  semantic_tags: string[];
  full_text_digest?: string | null;
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
  correctness?: number;
  technical_depth?: number;
  completeness?: number;
  practical_reasoning?: number;
  communication?: number;
  confidence?: number;
  expected_answer?: string;
  evaluation_summary?: string;
  missing_concepts?: string[];
  weaknesses?: string[];
  improvement_suggestion?: string;
  evidence: string[];
  strengths: string[];
  improvements: string[];
}

interface BackendInterviewResult {
  index: number;
  question: string;
  candidate_answer: string;
  expected_answer: string;
  ai_evaluation: BackendEvaluation;
  score: number;
  score_out_of_10: number;
  improvement_suggestion: string;
  answer_seconds?: number;
}

interface BackendSessionSummary {
  session_id: string;
  role: Role;
  candidate: string;
  duration_sec: number;
  resume_profile: BackendResumeProfile;
  results: BackendInterviewResult[];
  insights: {
    overall_score: number;
    strengths: string[];
    weaknesses?: string[];
    improvements: string[];
    signal: { label: string; score: number }[];
    recommendation: string;
    technical_rating?: number;
    communication_rating?: number;
    problem_solving_rating?: number;
    recommended_skill_improvements?: string[];
    readiness_level?: string;
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
