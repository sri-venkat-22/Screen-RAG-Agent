import { useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Upload,
  Sparkles,
  X,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ROLES, type Role, startSession } from "@/lib/interview-api";
import { toast } from "sonner";

interface Props {
  onReady: (
    data: Awaited<ReturnType<typeof startSession>> & { role: Role },
  ) => void;
}

export function SetupStage({ onReady }: Props) {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [candidateName, setCandidateName] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Please upload a file under 5MB");
      return;
    }
    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");
    const isText =
      file.type.startsWith("text/") || /\.(txt|md|markdown)$/i.test(file.name);

    if (!isPdf && !isText) {
      toast.error("Only PDF or text resumes are supported");
      return;
    }
    setResumeFile(file);
    toast.success("Resume attached");
  }

  async function start() {
    if (!resumeFile) return toast.error("Upload your resume first");
    if (!role) return toast.error("Select a target role");
    setLoading(true);
    try {
      const session = await startSession({
        resumeFile,
        role: role as Role,
        candidateName,
      });
      onReady({ ...session, role: role as Role });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to start interview",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="max-w-3xl mx-auto"
    >
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full glass text-xs font-mono text-muted-foreground mb-5">
          <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
          AI interviewer ready
        </div>
        <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight">
          Let's set up your{" "}
          <span className="text-gradient">screening session</span>
        </h1>
        <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
          Upload your resume and pick a role. Questions are grounded in a role
          knowledge base and adapt to your answers.
        </p>
      </div>

      <div className="glass rounded-2xl p-6 sm:p-8 shadow-elevated space-y-7">
        <div className="space-y-2">
          <Label className="text-sm font-medium">Resume</Label>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) handleFile(f);
            }}
            onClick={() => !resumeFile && fileInput.current?.click()}
            className={`relative rounded-xl border-2 border-dashed transition-all cursor-pointer overflow-hidden ${
              dragOver
                ? "border-primary bg-primary/5"
                : resumeFile
                  ? "border-success/40 bg-success/5 cursor-default"
                  : "border-border hover:border-primary/50 hover:bg-surface-elevated"
            }`}
          >
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.txt,.md,text/*,application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            {resumeFile ? (
              <div className="flex items-center gap-3 p-5">
                <div className="grid place-items-center h-11 w-11 rounded-lg bg-success/15 text-success">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{resumeFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(resumeFile.size / 1024).toFixed(1)} KB · ready for
                    analysis
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setResumeFile(null);
                  }}
                  className="p-2 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center text-center py-10 px-6">
                <div className="grid place-items-center h-12 w-12 rounded-xl bg-primary/10 text-primary mb-3">
                  <Upload className="h-5 w-5" />
                </div>
                <p className="font-medium">Drop your resume here</p>
                <p className="text-xs text-muted-foreground mt-1">
                  PDF or text · max 5MB
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-5">
          <div className="space-y-2">
            <Label htmlFor="name" className="text-sm font-medium">
              Your name{" "}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </Label>
            <Input
              id="name"
              placeholder="e.g. Alex Chen"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              className="h-11 bg-input/40"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm font-medium">Target role</Label>
            <Select value={role} onValueChange={(v) => setRole(v as Role)}>
              <SelectTrigger className="h-11 bg-input/40">
                <SelectValue placeholder="Pick a role" />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    <div className="flex flex-col">
                      <span className="font-medium">{r.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {r.blurb}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />7 balanced
            questions · RAG-backed · ~20 min
          </div>
          <Button
            onClick={start}
            disabled={loading || !resumeFile || !role}
            size="lg"
            className="bg-gradient-to-r from-primary to-accent text-primary-foreground hover:opacity-90 transition-opacity shadow-glow disabled:opacity-50 disabled:shadow-none"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating questions
              </>
            ) : (
              <>
                Begin interview <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
