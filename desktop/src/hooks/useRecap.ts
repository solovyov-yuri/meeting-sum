import { useCallback, useEffect, useRef, useState } from "react";
import { getBridge } from "@/lib/bridge";
import type {
  AppSettings,
  ExportFormat,
  HistoryItem,
  ProgressEvent,
  RunMode,
  RunRequest,
  RunResult,
  RunStatus,
  StepName,
  StepStatus,
} from "@/lib/types";
import { dirName, fileName, stem } from "@/lib/utils";

export const STEP_ORDER: StepName[] = ["preprocess", "transcribe", "summarize", "export"];

// Which steps each run mode actually executes — drives the progress display (#10).
export const MODE_STEPS: Record<RunMode, StepName[]> = {
  full: ["preprocess", "transcribe", "summarize", "export"],
  preprocess: ["preprocess"],
  transcribe: ["preprocess", "transcribe"],
  summarize: ["summarize", "export"],
};

export interface StepState {
  status: StepStatus;
  percent: number | null;
}

export interface LogEntry {
  id: number;
  time: string;
  status: StepStatus;
  message: string;
}

/** Read-only snapshot of the config a run used, for display in the Inspector.
 *  Runs always use the *saved* settings (single source of truth) — there are no per-run
 *  overrides, so changing a setting and re-running or retrying always takes effect. */
export interface RunConfig {
  provider: string;
  model: string;
  mode: string;
}

export type Phase = "idle" | "running" | "done";

function initialSteps(): Record<StepName, StepState> {
  return {
    preprocess: { status: "pending", percent: null },
    transcribe: { status: "pending", percent: null },
    summarize: { status: "pending", percent: null },
    export: { status: "pending", percent: null },
  };
}

function nowTime(): string {
  return new Date().toLocaleTimeString("ru-RU", { hour12: false });
}

function stepsForStatus(status: RunStatus): Record<StepName, StepState> {
  const s = initialSteps();
  if (status === "success") {
    return { preprocess: ok, transcribe: ok, summarize: ok, export: ok };
  }
  if (status === "partial_success") {
    return { ...s, transcribe: ok, summarize: { status: "error", percent: null } };
  }
  if (status === "failed") {
    return { ...s, transcribe: { status: "error", percent: null } };
  }
  return { ...s, transcribe: { status: "cancelled", percent: null } };
}

const ok: StepState = { status: "success", percent: null };

export function useRecap() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [audioPath, setAudioPath] = useState<string | null>(null);
  const [runMode, setRunMode] = useState<RunMode>("full");
  const [runConfig, setRunConfig] = useState<RunConfig | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [steps, setSteps] = useState(initialSteps());
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [editedSummary, setEditedSummary] = useState("");
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const logCounter = useRef(0);

  const refreshHistory = useCallback(async () => {
    const bridge = await getBridge();
    setHistory(await bridge.getHistory());
  }, []);

  const reloadSettings = useCallback(async () => {
    const bridge = await getBridge();
    const s = await bridge.getSettings();
    setSettings(s);
    return s;
  }, []);

  const configFromSettings = (s: AppSettings): RunConfig => ({
    provider: s.summarization.model.provider,
    model: s.summarization.model.name,
    mode: s.summarization.mode,
  });

  useEffect(() => {
    (async () => {
      try {
        await reloadSettings();
        await refreshHistory();
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [reloadSettings, refreshHistory]);

  const pushLog = useCallback((status: StepStatus, message: string) => {
    setLogs((prev) => [...prev, { id: logCounter.current++, time: nowTime(), status, message }]);
  }, []);

  const selectFile = useCallback(
    (path: string) => {
      setActiveHistoryId(null);
      setAudioPath(path);
      setPhase("idle");
      setResult(null);
      setSteps(initialSteps());
      setLogs([]);
      pushLog("success", `Файл выбран: ${fileName(path)}`);
    },
    [pushLog],
  );

  const pickFile = useCallback(async () => {
    const bridge = await getBridge();
    // Summarize takes a transcript (.txt); the other modes take audio/video.
    const path = runMode === "summarize" ? await bridge.pickTranscriptFile() : await bridge.pickAudioFile();
    if (path) selectFile(path);
  }, [runMode, selectFile]);

  const applyEvent = useCallback(
    (event: ProgressEvent) => {
      setSteps((prev) => ({
        ...prev,
        [event.step]: { status: event.status, percent: event.percent },
      }));
      pushLog(event.status, event.message);
    },
    [pushLog],
  );

  const start = useCallback(async () => {
    if (!audioPath || !settings) return;
    setActiveHistoryId(null);
    setRunConfig(configFromSettings(settings));
    setPhase("running");
    setResult(null);
    setSteps(initialSteps());
    setLogs([]);
    pushLog("success", `Файл выбран: ${fileName(audioPath)}`);

    const base = stem(audioPath);
    // Outputs go into the single configured "Папка для результатов" (output_dir), named by the
    // input stem — so distinct meetings don't overwrite each other. null → next to the input file.
    const outDir = settings.output_dir?.trim() || dirName(audioPath);
    const bridge = await getBridge();
    // No per-run overrides: the bridge uses the saved settings authoritatively (fixes the stale-model bug).
    try {
      let res: RunResult;
      if (runMode === "summarize") {
        // Input is a transcript (.txt); summarize only — no audio.
        res = await bridge.resummarize(
          { transcript_path: audioPath, summary_path: `${outDir}/${base}_summary.txt` },
          applyEvent,
        );
      } else {
        const req: RunRequest = { run_mode: runMode, audio_path: audioPath };
        if (runMode === "full" || runMode === "transcribe") req.transcript_path = `${outDir}/${base}.txt`;
        if (runMode === "full") req.summary_path = `${outDir}/${base}_summary.txt`;
        res = await bridge.runRecap(req, applyEvent);
      }
      setResult(res);
      setEditedSummary(res.summary_text ?? "");
      setPhase("done");
      // Reflect terminal step states for any of this mode's steps left pending.
      setSteps((prev) => {
        const next = { ...prev };
        if (res.status === "success") {
          for (const step of MODE_STEPS[runMode]) {
            if (next[step].status === "pending") next[step] = { status: "success", percent: null };
          }
        }
        return next;
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      pushLog("error", message);
      setResult({
        status: "failed",
        transcript_path: null,
        summary_path: null,
        summary_json_path: null,
        transcript_text: null,
        summary_text: null,
        error_message: message,
      });
      setPhase("done");
    }
    await refreshHistory();
  }, [audioPath, settings, runMode, applyEvent, pushLog, refreshHistory]);

  const retrySummarization = useCallback(async () => {
    // Re-run summarization ONLY, reusing the transcript already on disk. Never
    // re-transcribe (that would re-process the whole meeting). Uses the *current* saved
    // settings, so fixing the model/provider in Settings and retrying actually takes effect.
    const transcriptPath = result?.transcript_path;
    if (!audioPath || !settings || !transcriptPath) return;

    setRunConfig(configFromSettings(settings));
    setPhase("running");
    setActiveHistoryId(null);
    setSteps((prev) => ({ ...prev, summarize: { status: "pending", percent: null }, export: { status: "pending", percent: null } }));
    pushLog("running", "Повтор суммаризации по сохранённому транскрипту…");

    const summaryPath = result?.summary_path ?? `${dirName(audioPath)}/${stem(audioPath)}_summary.txt`;
    const bridge = await getBridge();
    try {
      const res = await bridge.resummarize(
        {
          audio_path: audioPath,
          transcript_path: transcriptPath,
          summary_path: summaryPath,
        },
        applyEvent,
      );
      setResult(res);
      setEditedSummary(res.summary_text ?? "");
      setPhase("done");
    } catch (e) {
      pushLog("error", e instanceof Error ? e.message : String(e));
      setPhase("done");
    }
    await refreshHistory();
  }, [audioPath, settings, result, applyEvent, pushLog, refreshHistory]);

  const newRun = useCallback(() => {
    setActiveHistoryId(null);
    setAudioPath(null);
    setRunConfig(null);
    setResult(null);
    setPhase("idle");
    setSteps(initialSteps());
    setLogs([]);
    setEditedSummary("");
  }, []);

  const changeRunMode = useCallback(
    (next: RunMode) => {
      setRunMode(next);
      // Switching between an audio mode and summarize (transcript input) changes the accepted file
      // type — clear the current selection so the user re-picks with the right filter.
      if ((runMode === "summarize") !== (next === "summarize")) {
        setActiveHistoryId(null);
        setAudioPath(null);
        setRunConfig(null);
        setResult(null);
        setPhase("idle");
        setSteps(initialSteps());
        setLogs([]);
        setEditedSummary("");
      }
    },
    [runMode],
  );

  const cancel = useCallback(async () => {
    const bridge = await getBridge();
    await bridge.cancelRun();
    pushLog("cancelled", "Остановка произойдёт после завершения текущего этапа.");
  }, [pushLog]);

  const openHistoryItem = useCallback(async (item: HistoryItem) => {
    const bridge = await getBridge();
    const [transcript, summary] = await Promise.all([
      bridge.readText(item.transcript_path),
      bridge.readText(item.summary_path),
    ]);
    setActiveHistoryId(item.id);
    setAudioPath(item.audio_path);
    setRunMode(item.run_mode ?? "full");
    setRunConfig({ provider: item.provider, model: item.model, mode: item.mode });
    setSteps(stepsForStatus(item.status));
    setLogs([
      { id: logCounter.current++, time: nowTime(), status: "success", message: `Открыт запуск: ${item.audio_name}` },
    ]);
    const res: RunResult = {
      status: item.status,
      transcript_path: item.transcript_path,
      summary_path: item.summary_path,
      summary_json_path: item.summary_json_path,
      transcript_text: transcript.text,
      summary_text: summary.text,
      error_message: item.error_message,
    };
    setResult(res);
    setEditedSummary(summary.text ?? "");
    setPhase("done");
  }, []);

  const removeHistoryItem = useCallback(
    async (id: string) => {
      const bridge = await getBridge();
      await bridge.deleteHistoryItem(id);
      if (activeHistoryId === id) {
        setActiveHistoryId(null);
        setResult(null);
        setPhase("idle");
        setAudioPath(null);
      }
      await refreshHistory();
    },
    [activeHistoryId, refreshHistory],
  );

  return {
    settings,
    setSettings,
    history,
    loadError,
    audioPath,
    runMode,
    setRunMode: changeRunMode,
    runConfig,
    phase,
    steps,
    logs,
    result,
    editedSummary,
    setEditedSummary,
    activeHistoryId,
    reloadSettings,
    refreshHistory,
    selectFile,
    pickFile,
    newRun,
    start,
    retrySummarization,
    cancel,
    openHistoryItem,
    removeHistoryItem,
  };
}

export type RecapController = ReturnType<typeof useRecap>;

export const DEFAULT_EXPORT_FORMATS: ExportFormat[] = ["telegram", "plain", "json"];
