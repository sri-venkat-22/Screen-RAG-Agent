import { motion } from "framer-motion";
import { Check } from "lucide-react";

const STAGES = [
  { key: "setup", label: "Setup" },
  { key: "interview", label: "Interview" },
  { key: "results", label: "Results" },
] as const;

export type StageKey = (typeof STAGES)[number]["key"];

export function StageIndicator({ current }: { current: StageKey }) {
  const currentIdx = STAGES.findIndex((s) => s.key === current);

  return (
    <div className="flex items-center gap-2 sm:gap-4">
      {STAGES.map((stage, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={stage.key} className="flex items-center gap-2 sm:gap-4">
            <div className="flex items-center gap-2">
              <motion.div
                initial={false}
                animate={{
                  scale: active ? 1.05 : 1,
                }}
                className={`relative grid place-items-center h-8 w-8 rounded-full text-xs font-mono font-semibold transition-colors ${
                  done
                    ? "bg-success/20 text-success border border-success/40"
                    : active
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground border border-border"
                }`}
              >
                {active && (
                  <span className="absolute inset-0 rounded-full bg-primary/40 animate-pulse-glow -z-10" />
                )}
                {done ? <Check className="h-4 w-4" /> : i + 1}
              </motion.div>
              <span
                className={`text-sm font-medium hidden sm:inline ${
                  active ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                {stage.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div className="h-px w-8 sm:w-16 bg-border relative overflow-hidden">
                {done && (
                  <motion.div
                    layoutId={`bar-${i}`}
                    className="absolute inset-0 bg-gradient-to-r from-primary to-accent"
                  />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
