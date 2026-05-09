import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Toaster } from "@/components/ui/sonner";
import {
  StageIndicator,
  type StageKey,
} from "@/features/interview/components/StageIndicator";
import { SetupStage } from "@/features/interview/stages/SetupStage";
import { InterviewStage } from "@/features/interview/stages/InterviewStage";
import { ResultsStage } from "@/features/interview/stages/ResultsStage";
import type { Question, Role, SessionSummary } from "@/lib/interview-api";
import { Brain } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Cipher — AI Role-Based Interview Screening" },
      {
        name: "description",
        content:
          "Adaptive AI interviewer that screens candidates with questions tailored to their resume and target role.",
      },
      { property: "og:title", content: "Cipher — AI Interview Screening" },
      {
        property: "og:description",
        content:
          "Upload a resume, pick a role, and run a structured AI-led technical screen.",
      },
    ],
  }),
  component: Index,
});

interface SessionState {
  sessionId: string;
  question: Question;
  candidate: string;
  role: Role;
}

function Index() {
  const [stage, setStage] = useState<StageKey>("setup");
  const [session, setSession] = useState<SessionState | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  return (
    <div className="min-h-screen relative">
      <div className="absolute inset-0 grid-bg pointer-events-none opacity-40" />

      <header className="relative z-10 border-b border-border/40 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="grid place-items-center h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-glow">
              <Brain className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <p className="font-display font-semibold text-[15px]">Cipher</p>
              <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                AI screening
              </p>
            </div>
          </div>
          <StageIndicator current={stage} />
        </div>
      </header>

      <main className="relative z-10 px-5 sm:px-8 py-12 sm:py-16">
        <AnimatePresence mode="wait">
          {stage === "setup" && (
            <SetupStage
              key="setup"
              onReady={(s) => {
                setSession(s);
                setStage("interview");
              }}
            />
          )}
          {stage === "interview" && session && (
            <InterviewStage
              key="interview"
              sessionId={session.sessionId}
              candidate={session.candidate}
              role={session.role}
              initialQuestion={session.question}
              onComplete={(sum) => {
                setSummary(sum);
                setStage("results");
              }}
            />
          )}
          {stage === "results" && summary && (
            <ResultsStage
              key="results"
              summary={summary}
              onRestart={() => {
                setSummary(null);
                setSession(null);
                setStage("setup");
              }}
            />
          )}
        </AnimatePresence>
      </main>

      <footer className="relative z-10 border-t border-border/40 mt-12">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-6 text-center text-xs font-mono text-muted-foreground">
          Frontend connected to the FastAPI RAG backend · see{" "}
          <code className="text-foreground/70">src/lib/interview-api.ts</code>
        </div>
      </footer>

      <Toaster theme="dark" position="top-center" richColors />
    </div>
  );
}
