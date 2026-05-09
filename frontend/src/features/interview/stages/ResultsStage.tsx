import { motion } from "framer-motion";
import {
  Award,
  TrendingUp,
  Target,
  Download,
  RefreshCcw,
  Sparkles,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SessionSummary } from "@/lib/interview-api";
import { ROLES } from "@/lib/interview-api";

interface Props {
  summary: SessionSummary;
  onRestart: () => void;
}

export function ResultsStage({ summary, onRestart }: Props) {
  const roleLabel =
    ROLES.find((r) => r.value === summary.role)?.label ?? summary.role;

  function downloadJson() {
    const blob = new Blob([JSON.stringify(summary, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `interview-${summary.candidate.replace(/\s+/g, "-").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="max-w-5xl mx-auto"
    >
      <div className="text-center mb-10">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, type: "spring" }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full glass text-xs font-mono mb-5"
        >
          <Sparkles className="h-3 w-3 text-primary" />
          Session complete
        </motion.div>
        <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight">
          Nice work, <span className="text-gradient">{summary.candidate}</span>
        </h1>
        <p className="text-muted-foreground mt-3">
          {roleLabel} · {summary.transcript.length} questions ·{" "}
          {formatDuration(summary.durationSec)}
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-5 mb-6">
        <ScoreCard score={summary.insights.overallScore} />
        <div className="glass rounded-2xl p-6 lg:col-span-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <TrendingUp className="h-4 w-4" />
            Signal breakdown
          </div>
          <div className="space-y-4">
            {summary.insights.signal.map((s, i) => (
              <SignalBar key={s.label} {...s} delay={i * 0.08} />
            ))}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5 mb-6">
        <InsightCard
          icon={Award}
          title="Strengths"
          tone="success"
          items={summary.insights.strengths}
        />
        <InsightCard
          icon={Target}
          title="Areas to develop"
          tone="warning"
          items={summary.insights.improvements}
        />
      </div>

      <div className="glass rounded-2xl p-6 mb-6">
        <h3 className="font-display text-xl font-medium mb-4">
          Resume signals used
        </h3>
        <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
          {summary.resumeProfile.summary}
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {summary.resumeProfile.skills.map((skill) => (
            <span
              key={skill}
              className="px-2 py-1 rounded-md bg-primary/10 text-primary text-xs"
            >
              {skill}
            </span>
          ))}
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono mb-2">
              Highlights
            </p>
            <ul className="space-y-2">
              {summary.resumeProfile.highlights.map((item, index) => (
                <li
                  key={index}
                  className="text-sm text-muted-foreground flex gap-2"
                >
                  <span className="text-primary">·</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono mb-2">
              Domains
            </p>
            <div className="flex flex-wrap gap-2">
              {summary.resumeProfile.domains.map((domain) => (
                <span
                  key={domain}
                  className="px-2 py-1 rounded-md bg-muted text-muted-foreground text-xs"
                >
                  {domain}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="glass rounded-2xl p-6 mb-6 border-l-4 border-primary">
        <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono mb-2">
          Recommendation
        </p>
        <p className="text-lg font-medium">{summary.insights.recommendation}</p>
      </div>

      <div className="glass rounded-2xl p-6 mb-6">
        <h3 className="font-display text-xl font-medium mb-5">
          Full transcript
        </h3>
        <div className="space-y-5">
          {summary.transcript.map((turn) => {
            const q = turn.question;
            return (
              <div
                key={q.id}
                className="border-l-2 border-border pl-4 hover:border-primary transition-colors"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-mono text-xs text-muted-foreground">
                    Q{q.index}
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
                    {q.stage}
                  </span>
                  <span className="ml-auto text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDuration(turn.answerSeconds)}
                  </span>
                </div>
                <p className="text-sm text-foreground/90 mb-2 font-medium">
                  {q.prompt}
                </p>
                <p className="text-xs text-primary mb-2">{q.rationale}</p>
                <div className="flex flex-wrap gap-2 mb-3">
                  {q.sources.slice(0, 3).map((source) => (
                    <span
                      key={source.chunkId}
                      className="px-2 py-1 rounded-md bg-background/50 border border-border/60 text-[11px] text-muted-foreground"
                    >
                      {source.title}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed mb-3">
                  {turn.answer}
                </p>
                <div className="grid sm:grid-cols-4 gap-3">
                  {[
                    { label: "Score", value: turn.evaluation.score },
                    {
                      label: "Grounding",
                      value: turn.evaluation.keywordCoverage,
                    },
                    { label: "Clarity", value: turn.evaluation.clarity },
                    { label: "Depth", value: turn.evaluation.depth },
                  ].map((metric) => (
                    <div
                      key={metric.label}
                      className="rounded-xl bg-background/40 border border-border/60 p-3"
                    >
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                        {metric.label}
                      </p>
                      <p className="font-display text-xl">{metric.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Button
          variant="outline"
          size="lg"
          onClick={downloadJson}
          className="border-border/60"
        >
          <Download className="h-4 w-4 mr-2" />
          Export JSON
        </Button>
        <Button
          onClick={onRestart}
          size="lg"
          className="bg-gradient-to-r from-primary to-accent text-primary-foreground hover:opacity-90 shadow-glow"
        >
          <RefreshCcw className="h-4 w-4 mr-2" />
          Start a new session
        </Button>
      </div>
    </motion.div>
  );
}

function ScoreCard({ score }: { score: number }) {
  const tone =
    score >= 75
      ? "text-success"
      : score >= 55
        ? "text-warning"
        : "text-destructive";
  return (
    <div className="glass rounded-2xl p-6 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-accent/10 pointer-events-none" />
      <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono mb-3">
        Overall signal
      </p>
      <div className="relative">
        <motion.div
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", delay: 0.15 }}
          className={`font-display text-7xl font-semibold ${tone}`}
        >
          {score}
        </motion.div>
        <span className="absolute -right-6 top-2 text-sm text-muted-foreground font-mono">
          /100
        </span>
      </div>
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
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs font-mono text-muted-foreground">{score}</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ delay, duration: 0.7, ease: "easeOut" }}
          className="h-full bg-gradient-to-r from-primary to-accent rounded-full"
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
  tone: "success" | "warning";
}) {
  const toneClasses =
    tone === "success"
      ? "text-success bg-success/10"
      : "text-warning bg-warning/10";
  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <div
          className={`grid place-items-center h-8 w-8 rounded-lg ${toneClasses}`}
        >
          <Icon className="h-4 w-4" />
        </div>
        <h3 className="font-medium">{title}</h3>
      </div>
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className="text-sm text-muted-foreground flex gap-2">
            <span
              className={tone === "success" ? "text-success" : "text-warning"}
            >
              ·
            </span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatDuration(s: number) {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return sec ? `${m}m ${sec}s` : `${m}m`;
}
