import { useCallback, useEffect, useRef, useState } from "react";
import { getBridge } from "@/lib/bridge";
import type {
  AppSettings,
  ExportFormat,
  HistoryItem,
  ProgressEvent,
  RunResult,
  RunStatus,
  StepName,
  StepStatus,
} from "@/lib/types";
import { dirName, fileName, stem } from "@/lib/utils";

export const STEP_ORDER: StepName[] = ["preprocess", "transcribe", "summarize", "export"];

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

export interface RunOverrides {
  provider: string;
  model: string;
  transcription_language: string;
  summary_language: string;
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
  const [overrides, setOverrides] = useState<RunOverrides | null>(null);

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
    setOverrides((prev) =>
      prev ?? {
        provider: s.summarization.model.provider,
        model: s.summarization.model.name,
        transcription_language: s.transcription.language,
        summary_language: s.summarization.language ?? "ru",
        mode: s.summarization.mode,
      },
    );
    return s;
  }, []);

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
    const path = await bridge.pickAudioFile();
    if (path) selectFile(path);
  }, [selectFile]);

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
    if (!audioPath || !settings || !overrides) return;
    setActiveHistoryId(null);
    setPhase("running");
    setResult(null);
    setSteps(initialSteps());
    setLogs([]);
    pushLog("success", `Файл выбран: ${fileName(audioPath)}`);

    const dir = dirName(audioPath);
    const base = stem(audioPath);
    // Honor the user-configured output paths from the "Пути" settings screen.
    // Fall back to audio-derived defaults only when a setting is empty/unset.
    const transcriptPath = settings.transcript.trim() || `${dir}/${base}.txt`;
    const summaryPath = settings.summary.trim() || `${dir}/${base}_summary.txt`;
    const bridge = await getBridge();
    try {
      const res = await bridge.runRecap(
        {
          audio_path: audioPath,
          transcript_path: transcriptPath,
          summary_path: summaryPath,
          overrides: {
            provider: overrides.provider,
            model: overrides.model,
            mode: overrides.mode,
            transcription_language: overrides.transcription_language,
            summary_language: overrides.summary_language,
          },
        },
        applyEvent,
      );
      setResult(res);
      setEditedSummary(res.summary_text ?? "");
      setPhase("done");
      // Reflect terminal step states for any step left pending.
      setSteps((prev) => {
        const next = { ...prev };
        if (res.status === "success") {
          for (const step of STEP_ORDER) {
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
  }, [audioPath, settings, overrides, applyEvent, pushLog, refreshHistory]);

  const retrySummarization = useCallback(async () => {
    // Re-run summarization ONLY, reusing the transcript already on disk. Never
    // re-transcribe (that would re-process the whole meeting).
    const transcriptPath = result?.transcript_path;
    if (!audioPath || !overrides || !transcriptPath) return;

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
          overrides: {
            provider: overrides.provider,
            model: overrides.model,
            mode: overrides.mode,
            transcription_language: overrides.transcription_language,
            summary_language: overrides.summary_language,
          },
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
  }, [audioPath, overrides, result, applyEvent, pushLog, refreshHistory]);

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
    overrides,
    setOverrides,
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
    start,
    retrySummarization,
    cancel,
    openHistoryItem,
    removeHistoryItem,
  };
}

export type RecapController = ReturnType<typeof useRecap>;

export const DEFAULT_EXPORT_FORMATS: ExportFormat[] = ["telegram", "plain", "json"];
