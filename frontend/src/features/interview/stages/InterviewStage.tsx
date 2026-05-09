import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Lightbulb,
  Clock,
  Loader2,
  CheckCircle2,
  Code2,
  MessageSquare,
  Brain,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type AnswerEvaluation,
  type Question,
  type QuestionType,
  type Role,
  type SessionSummary,
  submitAnswer,
} from "@/lib/interview-api";
import { toast } from "sonner";

const TYPE_META: Record<
  QuestionType,
  { icon: typeof Code2; label: string; tone: string }
> = {
  open: {
    icon: MessageSquare,
    label: "Open-ended",
    tone: "text-primary bg-primary/10",
  },
  code: { icon: Code2, label: "Technical", tone: "text-accent bg-accent/10" },
  scenario: {
    icon: Brain,
    label: "Scenario",
    tone: "text-warning bg-warning/10",
  },
  system: {
    icon: Zap,
    label: "System design",
    tone: "text-success bg-success/10",
  },
};

interface Props {
  sessionId: string;
  candidate: string;
  role: Role;
  initialQuestion: Question;
  onComplete: (summary: SessionSummary) => void;
}

export function InterviewStage({
  sessionId,
  candidate,
  role,
  initialQuestion,
  onComplete,
}: Props) {
  const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
  const [evaluations, setEvaluations] = useState<AnswerEvaluation[]>([]);
  const [text, setText] = useState("");
  const [questionStart, setQuestionStart] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const q = currentQuestion;
  const TypeIcon = TYPE_META[q.type].icon;
  const wordCount = useMemo(
    () => text.trim().split(/\s+/).filter(Boolean).length,
    [text],
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - questionStart) / 1000));
    }, 500);
    return () => clearInterval(timer);
  }, [questionStart]);

  useEffect(() => {
    setText("");
    setShowHint(false);
    setQuestionStart(Date.now());
    setElapsed(0);
    setTimeout(() => taRef.current?.focus(), 350);
  }, [currentQuestion.id]);

  async function submit() {
    if (wordCount < 5) {
      toast.error("Try to give a more substantive answer");
      return;
    }

    setSubmitting(true);
    try {
      const response = await submitAnswer({
        sessionId,
        answerText: text.trim(),
        answerSeconds: Math.floor((Date.now() - questionStart) / 1000),
      });
      setEvaluations((prev) => [...prev, response.latestEvaluation]);

      if (response.done && response.summary) {
        onComplete(response.summary);
        return;
      }

      if (!response.nextQuestion) {
        toast.error("The backend did not return a next question");
        return;
      }

      setCurrentQuestion(response.nextQuestion);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to submit answer",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const idx = currentQuestion.index - 1;
  const overTime = elapsed > recommendedSeconds(q);
  const progressPct = (currentQuestion.index / currentQuestion.total) * 100;
  const lastEvaluation = evaluations.at(-1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="max-w-4xl mx-auto"
    >
      <div className="flex items-center justify-between mb-5 text-sm">
        <div className="flex items-center gap-3">
          <span className="font-mono text-muted-foreground">
            {String(currentQuestion.index).padStart(2, "0")}
            <span className="text-foreground/30"> / </span>
            {String(currentQuestion.total).padStart(2, "0")}
          </span>
          <span className="px-2 py-0.5 rounded-md bg-muted text-xs font-medium text-muted-foreground">
            {q.stage}
          </span>
        </div>
        <div
          className={`flex items-center gap-1.5 font-mono text-xs ${
            overTime ? "text-warning" : "text-muted-foreground"
          }`}
        >
          <Clock className="h-3.5 w-3.5" />
          {formatTime(elapsed)}
          <span className="text-foreground/30">
            / {formatTime(recommendedSeconds(q))}
          </span>
        </div>
      </div>

      <div className="h-1 w-full bg-muted rounded-full overflow-hidden mb-8">
        <motion.div
          className="h-full bg-gradient-to-r from-primary to-accent"
          initial={false}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={q.id}
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -24 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="glass rounded-2xl p-6 sm:p-8 shadow-elevated"
        >
          <div className="flex items-center justify-between mb-5">
            <div
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium ${
                TYPE_META[q.type].tone
              }`}
            >
              <TypeIcon className="h-3.5 w-3.5" />
              {TYPE_META[q.type].label}
            </div>
            <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
              {q.difficulty}
            </span>
          </div>

          <div className="mb-5 flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2 py-1 rounded-md bg-primary/10 text-primary">
              Topic: {q.focusTopic}
            </span>
            <span className="px-2 py-1 rounded-md bg-muted text-muted-foreground">
              Candidate: {candidate}
            </span>
            <span className="px-2 py-1 rounded-md bg-muted text-muted-foreground uppercase">
              {role.replace("-", " ")}
            </span>
          </div>

          <h2 className="font-display text-2xl sm:text-[28px] leading-snug font-medium text-foreground">
            {q.prompt}
          </h2>

          <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
            {q.rationale}
          </p>

          {q.hint && (
            <div className="mt-5">
              <button
                onClick={() => setShowHint(!showHint)}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
              >
                <Lightbulb className="h-3.5 w-3.5" />
                {showHint ? "Hide hint" : "Need a nudge?"}
              </button>
              <AnimatePresence>
                {showHint && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <p className="mt-2 text-sm text-muted-foreground italic border-l-2 border-primary/40 pl-3">
                      {q.hint}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-2">
            {q.sources.slice(0, 3).map((source) => (
              <span
                key={source.chunkId}
                className="px-2 py-1 rounded-md text-[11px] bg-background/50 border border-border/60 text-muted-foreground"
              >
                {source.title}
              </span>
            ))}
          </div>

          <div className="mt-7 space-y-3">
            <Textarea
              ref={taRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type your answer here. Think out loud — structure, tradeoffs, examples."
              className="min-h-[180px] bg-input/30 border-border/60 focus-visible:ring-primary/50 text-[15px] leading-relaxed resize-none"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
              }}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-mono">
                {wordCount} {wordCount === 1 ? "word" : "words"}
              </span>
              <span className="hidden sm:inline font-mono opacity-70">
                Ctrl/⌘ + ↵ to submit
              </span>
            </div>
          </div>

          {lastEvaluation && (
            <div className="mt-6 grid sm:grid-cols-4 gap-3">
              {[
                { label: "Last score", value: lastEvaluation.score },
                { label: "Grounding", value: lastEvaluation.keywordCoverage },
                { label: "Clarity", value: lastEvaluation.clarity },
                { label: "Specificity", value: lastEvaluation.specificity },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-xl border border-border/60 bg-background/40 p-3"
                >
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">
                    {metric.label}
                  </p>
                  <p className="font-display text-2xl">{metric.value}</p>
                </div>
              ))}
            </div>
          )}

          <div className="mt-7 flex items-center justify-between gap-4">
            <p className="text-xs text-muted-foreground">
              {currentQuestion.index === currentQuestion.total
                ? "This is your final question."
                : `${currentQuestion.total - currentQuestion.index} questions remaining`}
            </p>
            <Button
              onClick={submit}
              disabled={submitting}
              size="lg"
              className="bg-gradient-to-r from-primary to-accent text-primary-foreground hover:opacity-90 shadow-glow"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Sending answer
                </>
              ) : currentQuestion.index === currentQuestion.total ? (
                <>
                  Finish interview <CheckCircle2 className="h-4 w-4 ml-2" />
                </>
              ) : (
                <>
                  Next question <ArrowRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </motion.div>
      </AnimatePresence>

      <div className="mt-6 flex items-center justify-center gap-1.5">
        {Array.from({ length: currentQuestion.total }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all ${
              i < idx
                ? "w-4 bg-success"
                : i === idx
                  ? "w-8 bg-primary"
                  : "w-1.5 bg-muted"
            }`}
          />
        ))}
      </div>
    </motion.div>
  );
}

function recommendedSeconds(question: Question) {
  switch (question.difficulty) {
    case "warmup":
      return 180;
    case "core":
      return 240;
    case "deep":
      return 300;
    case "system":
      return 360;
    default:
      return 240;
  }
}

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}
