import { AlertTriangle, FileAudio, Play, Square, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/controls";
import { cn, fileName } from "@/lib/utils";
import type { LogEntry, Phase, StepState } from "@/hooks/useRecap";
import type { RunResult, StepName } from "@/lib/types";
import { DropZone } from "./DropZone";
import { LogView } from "./LogView";
import { ProgressSteps } from "./ProgressSteps";
import { RUN_STATUS_LABEL } from "./StatusDot";
import { TranscriptView } from "./TranscriptView";

type Tab = "transcript" | "summary" | "log";

interface WorkspaceProps {
  phase: Phase;
  audioPath: string | null;
  steps: Record<StepName, StepState>;
  logs: LogEntry[];
  result: RunResult | null;
  editedSummary: string;
  setEditedSummary: (v: string) => void;
  dragActive: boolean;
  onPick: () => void;
  onBrowserDrop: (name: string) => void;
  onStart: () => void;
  onCancel: () => void;
  onRetry: () => void;
}

export function Workspace(props: WorkspaceProps) {
  const { phase, audioPath, steps, logs, result } = props;
  const [tab, setTab] = useState<Tab>("log");

  useEffect(() => {
    if (phase === "running") setTab("log");
    else if (phase === "done" && result) setTab(result.status === "success" ? "summary" : "transcript");
  }, [phase, result]);

  if (!audioPath) {
    return (
      <main className="flex flex-1 flex-col gap-3 overflow-y-auto p-4 scrollbar-thin">
        <DropZone onPick={props.onPick} onBrowserDrop={props.onBrowserDrop} dragActive={props.dragActive} />
        <p className="px-1 text-sm text-ink-muted">
          После выбора файла настройте параметры запуска справа и нажмите «Запустить».
        </p>
      </main>
    );
  }

  const showSteps = phase !== "idle";

  return (
    <main className="flex flex-1 flex-col gap-3 overflow-hidden p-4">
      <FileHeader {...props} />
      {showSteps && <ProgressSteps steps={steps} />}
      {phase === "done" && result && <ResultBanner result={result} onRetry={props.onRetry} onSwitchTranscript={() => setTab("transcript")} />}

      <div className="flex min-h-0 flex-1 flex-col rounded-card border border-border bg-panel">
        <div className="flex h-[42px] items-center gap-0.5 border-b border-border px-2">
          <TabButton active={tab === "transcript"} onClick={() => setTab("transcript")}>
            Транскрипт
          </TabButton>
          <TabButton active={tab === "summary"} onClick={() => setTab("summary")}>
            Резюме
          </TabButton>
          <TabButton active={tab === "log"} onClick={() => setTab("log")}>
            Лог
          </TabButton>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {tab === "transcript" && <TranscriptView text={result?.transcript_text ?? ""} />}
          {tab === "summary" && (
            <SummaryTab phase={phase} result={result} value={props.editedSummary} onChange={props.setEditedSummary} />
          )}
          {tab === "log" && <LogView logs={logs} />}
        </div>
      </div>
    </main>
  );
}

const PILL_TONE: Record<string, string> = {
  success: "bg-ok-soft text-ok border-ok-line",
  partial_success: "bg-warn-soft text-warn border-warn-line",
  failed: "bg-danger-soft text-danger border-danger-line",
  cancelled: "bg-app text-ink-muted border-border",
};

function FileHeader({ phase, audioPath, result, onStart, onCancel }: WorkspaceProps) {
  return (
    <div className="flex min-h-[68px] items-center gap-3 rounded-card border border-border bg-panel p-3">
      <span className="grid h-10 w-10 place-items-center rounded-card bg-accent-soft font-bold text-accent">
        <FileAudio className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold text-ink">{fileName(audioPath ?? "")}</h1>
        <p className="mt-0.5 truncate text-base text-ink-muted">{audioPath}</p>
      </div>
      {phase === "running" ? (
        <div className="flex flex-col items-end gap-1">
          <Button variant="danger" size="lg" onClick={onCancel}>
            <Square className="h-4 w-4" /> Остановить
          </Button>
          <span className="text-xs text-ink-muted">Остановка произойдёт после завершения текущего этапа</span>
        </div>
      ) : phase === "done" && result ? (
        <span
          className={cn(
            "inline-flex h-[30px] items-center rounded-md border px-2.5 text-base font-bold",
            PILL_TONE[result.status],
          )}
        >
          {RUN_STATUS_LABEL[result.status]}
        </span>
      ) : (
        <Button variant="primary" size="lg" onClick={onStart}>
          <Play className="h-4 w-4" /> Запустить
        </Button>
      )}
    </div>
  );
}

function ResultBanner({
  result,
  onRetry,
  onSwitchTranscript,
}: {
  result: RunResult;
  onRetry: () => void;
  onSwitchTranscript: () => void;
}) {
  if (result.status === "partial_success") {
    return (
      <div className="flex items-start gap-3 rounded-card border border-warn-line bg-warn-soft p-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
        <div className="flex-1">
          <p className="text-base font-semibold text-ink">Транскрипт сохранён, но резюме не создано.</p>
          <p className="mt-0.5 text-sm text-warn">
            Причина: {result.error_message}. Исправьте настройки и повторите только суммаризацию.
          </p>
          <div className="mt-2 flex gap-2">
            <Button variant="primary" size="sm" onClick={onRetry}>
              Повторить суммаризацию
            </Button>
            <Button variant="secondary" size="sm" onClick={onSwitchTranscript}>
              Открыть транскрипт
            </Button>
          </div>
        </div>
      </div>
    );
  }
  if (result.status === "failed") {
    return (
      <div className="flex items-start gap-3 rounded-card border border-danger-line bg-danger-soft p-3">
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
        <div className="flex-1">
          <p className="text-base font-semibold text-ink">Не удалось выполнить разбор.</p>
          <p className="mt-0.5 text-sm text-danger">{result.error_message}</p>
        </div>
      </div>
    );
  }
  return null;
}

function SummaryTab({
  phase,
  result,
  value,
  onChange,
}: {
  phase: Phase;
  result: RunResult | null;
  value: string;
  onChange: (v: string) => void;
}) {
  if (phase !== "done" || !result || result.status === "failed") {
    return <p className="p-3.5 text-base text-ink-muted">Резюме появится после завершения суммаризации.</p>;
  }
  if (result.status === "partial_success") {
    return <p className="p-3.5 text-base text-ink-muted">Резюме не создано. Исправьте настройки и повторите суммаризацию.</p>;
  }
  return (
    <div className="h-full p-3.5">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-full resize-none"
        aria-label="Редактируемое резюме"
      />
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative h-full px-3 text-base font-semibold transition-colors",
        active ? "text-accent" : "text-ink-muted hover:text-ink",
      )}
    >
      {children}
      {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />}
    </button>
  );
}
