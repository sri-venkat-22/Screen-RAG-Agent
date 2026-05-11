import { motion } from "framer-motion";
import {
  Award,
  CheckCircle2,
  Clock,
  Download,
  Lightbulb,
  RefreshCcw,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type {
  AnswerEvaluation,
  InterviewResult,
  SessionSummary,
} from "@/lib/interview-api";
import { ROLES } from "@/lib/interview-api";

interface Props {
  summary: SessionSummary;
  onRestart: () => void;
}

export function ResultsStage({ summary, onRestart }: Props) {
  const roleLabel =
    ROLES.find((r) => r.value === summary.role)?.label ?? summary.role;

  function downloadJson() {
    const report = {
      candidate: summary.candidate,
      role: roleLabel,
      durationSeconds: summary.durationSec,
      overallScore: summary.insights.overallScore,
      technicalRating: summary.insights.technicalRating,
      communicationRating: summary.insights.communicationRating,
      problemSolvingRating: summary.insights.problemSolvingRating,
      readinessLevel: summary.insights.readinessLevel,
      strengths: summary.insights.strengths,
      weaknesses: summary.insights.weaknesses,
      recommendedSkillImprovements:
        summary.insights.recommendedSkillImprovements,
      recommendation: summary.insights.recommendation,
      results: summary.results.map((result) => ({
        question: result.question,
        candidateAnswer: result.candidateAnswer,
        expectedAnswer: result.expectedAnswer,
        evaluation: {
          correctness: result.aiEvaluation.correctness,
          technicalDepth: result.aiEvaluation.technicalDepth,
          missingConcepts: result.aiEvaluation.missingConcepts,
          strengths: result.aiEvaluation.strengths,
          weaknesses: result.aiEvaluation.weaknesses,
          summary: result.aiEvaluation.evaluationSummary,
        },
        score: result.scoreOutOf10,
        improvementSuggestion: result.improvementSuggestion,
      })),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `interview-report-${summary.candidate.replace(/\s+/g, "-").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="mx-auto max-w-6xl"
    >
      <div className="mb-8">
        <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-border/60 bg-background/35 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Recruiter-style technical report
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-5xl">
              {summary.candidate}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {roleLabel} · {summary.results.length} questions ·{" "}
              {formatDuration(summary.durationSec)}
            </p>
          </div>
          <div className="rounded-lg border border-border/60 bg-background/35 px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Readiness
            </p>
            <p className="mt-1 font-medium">
              {summary.insights.readinessLevel}
            </p>
          </div>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[280px_1fr]">
        <ScoreCard score={summary.insights.overallScore} />
        <div className="glass rounded-lg p-5">
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            Rating breakdown
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <RatingTile
              label="Technical Rating"
              score={summary.insights.technicalRating}
            />
            <RatingTile
              label="Communication Rating"
              score={summary.insights.communicationRating}
            />
            <RatingTile
              label="Problem Solving Rating"
              score={summary.insights.problemSolvingRating}
            />
          </div>
          <div className="mt-5 space-y-3">
            {summary.insights.signal.map((signal, index) => (
              <SignalBar key={signal.label} {...signal} delay={index * 0.06} />
            ))}
          </div>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <InsightCard
          icon={Award}
          title="Strengths Summary"
          tone="success"
          items={summary.insights.strengths}
        />
        <InsightCard
          icon={Target}
          title="Weaknesses Summary"
          tone="warning"
          items={summary.insights.weaknesses}
        />
        <InsightCard
          icon={Lightbulb}
          title="Recommended Improvements"
          tone="primary"
          items={summary.insights.recommendedSkillImprovements}
        />
      </div>

      <div className="glass mb-6 rounded-lg border-l-4 border-primary p-5">
        <p className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
          Recommendation
        </p>
        <p className="text-lg font-medium">{summary.insights.recommendation}</p>
      </div>

      <div className="mb-6 space-y-4">
        {summary.results.map((result) => (
          <QuestionResultCard key={result.index} result={result} />
        ))}
      </div>

      <div className="flex flex-col justify-center gap-3 sm:flex-row">
        <Button
          variant="outline"
          size="lg"
          onClick={downloadJson}
          className="border-border/60"
        >
          <Download className="mr-2 h-4 w-4" />
          Export report JSON
        </Button>
        <Button
          onClick={onRestart}
          size="lg"
          className="bg-gradient-to-r from-primary to-accent text-primary-foreground shadow-glow hover:opacity-90"
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          Start a new session
        </Button>
      </div>
    </motion.div>
  );
}

function QuestionResultCard({ result }: { result: InterviewResult }) {
  const evaluation = result.aiEvaluation;
  const missing = evaluation.missingConcepts.length
    ? evaluation.missingConcepts.join(", ")
    : "No major concept gaps identified.";

  return (
    <article className="glass rounded-lg p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
            Q{result.index}
          </span>
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            {formatDuration(result.answerSeconds)}
          </span>
        </div>
        <ScoreBadge score={result.score} scoreOutOf10={result.scoreOutOf10} />
      </div>

      <ReportSection title="Question">
        <p className="text-base font-medium leading-relaxed">
          {result.question}
        </p>
      </ReportSection>

      <ReportSection title="Candidate Answer">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
          {cleanDisplayText(result.candidateAnswer)}
        </p>
      </ReportSection>

      <ReportSection title="Expected / Ideal Answer">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {result.expectedAnswer}
        </p>
      </ReportSection>

      <ReportSection title="AI Evaluation">
        <div className="grid gap-3 md:grid-cols-2">
          <EvaluationLine
            label="Correctness"
            score={evaluation.correctness}
            text={evaluation.evaluationSummary}
          />
          <EvaluationLine
            label="Technical depth"
            score={evaluation.technicalDepth}
            text={depthText(evaluation)}
          />
          <EvaluationLine label="Missing concepts" text={missing} />
          <EvaluationLine
            label="Strengths"
            text={listText(evaluation.strengths)}
          />
          <EvaluationLine
            label="Weaknesses"
            text={listText(evaluation.weaknesses)}
          />
          <EvaluationLine
            label="Communication"
            score={evaluation.communication}
            text={communicationText(evaluation)}
          />
        </div>
      </ReportSection>

      <div className="mt-5 grid gap-4 border-t border-border/60 pt-4 md:grid-cols-[160px_1fr]">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Score
          </p>
          <p
            className={`mt-1 font-display text-3xl font-semibold ${scoreTone(result.score)}`}
          >
            {formatScore10(result.scoreOutOf10)}
            <span className="ml-1 text-base text-muted-foreground">/10</span>
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Improvement Suggestion
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {result.improvementSuggestion}
          </p>
        </div>
      </div>
    </article>
  );
}

function ReportSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border/60 py-4 first:border-t-0 first:pt-0">
      <p className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      {children}
    </section>
  );
}

function EvaluationLine({
  label,
  score,
  text,
}: {
  label: string;
  score?: number;
  text: string;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/25 p-3">
      <div className="mb-1 flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {typeof score === "number" && (
          <span className={`font-mono text-xs ${scoreTone(score)}`}>
            {score}
          </span>
        )}
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

function ScoreCard({ score }: { score: number }) {
  return (
    <div className="glass rounded-lg p-5">
      <p className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">
        Overall Score
      </p>
      <div className="flex items-end gap-2">
        <motion.span
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", delay: 0.1 }}
          className={`font-display text-7xl font-semibold ${scoreTone(score)}`}
        >
          {score}
        </motion.span>
        <span className="pb-3 font-mono text-sm text-muted-foreground">
          /100
        </span>
      </div>
      <div className="mt-5 h-2 overflow-hidden rounded-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ delay: 0.1, duration: 0.8, ease: "easeOut" }}
          className={`h-full rounded-full ${scoreFill(score)}`}
        />
      </div>
    </div>
  );
}

function RatingTile({ label, score }: { label: string; score: number }) {
  return (
    <div className="rounded-md border border-border/60 bg-background/25 p-4">
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <div className="mt-2 flex items-center justify-between gap-3">
        <span
          className={`font-display text-3xl font-semibold ${scoreTone(score)}`}
        >
          {score}
        </span>
        <span className="font-mono text-xs text-muted-foreground">/100</span>
      </div>
    </div>
  );
}

function ScoreBadge({
  score,
  scoreOutOf10,
}: {
  score: number;
  scoreOutOf10: number;
}) {
  return (
    <div className={`rounded-md border px-3 py-1.5 ${badgeTone(score)}`}>
      <span className="font-mono text-sm font-semibold">
        {formatScore10(scoreOutOf10)}/10
      </span>
    </div>
  );
}

function SignalBar({
  label,
  score,
  delay,
}: {
  label: string;
  score: number;
  delay: number;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="font-mono text-xs text-muted-foreground">{score}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ delay, duration: 0.7, ease: "easeOut" }}
          className={`h-full rounded-full ${scoreFill(score)}`}
        />
      </div>
    </div>
  );
}

function InsightCard({
  icon: Icon,
  title,
  items,
  tone,
}: {
  icon: typeof Award;
  title: string;
  items: string[];
  tone: "success" | "warning" | "primary";
}) {
  const toneClasses = {
    success: "text-success bg-success/10",
    warning: "text-warning bg-warning/10",
    primary: "text-primary bg-primary/10",
  }[tone];

  return (
    <div className="glass rounded-lg p-5">
      <div className="mb-4 flex items-center gap-2">
        <div
          className={`grid h-8 w-8 place-items-center rounded-md ${toneClasses}`}
        >
          <Icon className="h-4 w-4" />
        </div>
        <h3 className="font-medium">{title}</h3>
      </div>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function depthText(evaluation: AnswerEvaluation) {
  if (evaluation.technicalDepth >= 75) {
    return "Shows strong depth with implementation, tradeoff, and validation signal.";
  }
  if (evaluation.technicalDepth >= 55) {
    return "Shows partial depth but needs more edge cases, tradeoffs, and production detail.";
  }
  return "Needs much deeper technical reasoning and concrete implementation detail.";
}

function communicationText(evaluation: AnswerEvaluation) {
  if (evaluation.communication >= 75) {
    return "Clear and structured enough for a technical screen.";
  }
  if (evaluation.communication >= 55) {
    return "Understandable, but the answer should be more structured and direct.";
  }
  return "Hard to assess confidently; structure the answer around decision, tradeoff, and validation.";
}

function listText(items: string[]) {
  return items.length ? items.join(" ") : "No major item identified.";
}

function cleanDisplayText(text: string) {
  return text.trim() || "No answer provided.";
}

function scoreTone(score: number) {
  if (score >= 75) return "text-success";
  if (score >= 55) return "text-warning";
  return "text-destructive";
}

function scoreFill(score: number) {
  if (score >= 75) return "bg-success";
  if (score >= 55) return "bg-warning";
  return "bg-destructive";
}

function badgeTone(score: number) {
  if (score >= 75) return "border-success/40 bg-success/10 text-success";
  if (score >= 55) return "border-warning/40 bg-warning/10 text-warning";
  return "border-destructive/40 bg-destructive/10 text-destructive";
}

function formatScore10(score: number) {
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return sec ? `${minutes}m ${sec}s` : `${minutes}m`;
}
