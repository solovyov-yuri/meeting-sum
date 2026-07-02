// Single integration point with the Python workflow. In a Tauri window we call Rust
// commands (which spawn `recap-bridge`); in a plain browser (vite dev/build/preview or
// tests) we fall back to an in-memory mock so the UI is fully demoable without Rust.

import type {
  AppSettings,
  ExportRequest,
  ExportResult,
  HistoryItem,
  ProgressEvent,
  RunRequest,
  RunResult,
} from "./types";

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export type ProgressHandler = (event: ProgressEvent) => void;

export interface Bridge {
  getSettings(): Promise<AppSettings>;
  saveSettings(settings: AppSettings): Promise<void>;
  setApiKey(provider: string, apiKey: string): Promise<void>;
  deleteApiKey(provider: string): Promise<void>;
  testConnection(provider: string): Promise<{ ok: boolean; message: string }>;
  getHistory(): Promise<HistoryItem[]>;
  deleteHistoryItem(id: string): Promise<void>;
  readText(path: string | null): Promise<{ text: string | null; exists: boolean }>;
  exportSummary(req: ExportRequest): Promise<ExportResult>;
  runRecap(req: RunRequest, onProgress: ProgressHandler): Promise<RunResult>;
  resummarize(req: RunRequest, onProgress: ProgressHandler): Promise<RunResult>;
  cancelRun(): Promise<void>;
  pickAudioFile(): Promise<string | null>;
  revealPath(path: string): Promise<void>;
}

// ── Tauri-backed implementation ─────────────────────────────────────────────

async function tauriBridge(): Promise<Bridge> {
  const { invoke } = await import("@tauri-apps/api/core");
  const { listen } = await import("@tauri-apps/api/event");
  const dialog = await import("@tauri-apps/plugin-dialog");
  const opener = await import("@tauri-apps/plugin-opener");

  return {
    getSettings: () => invoke<AppSettings>("get_settings"),
    saveSettings: (settings) => invoke("save_settings", { settings }),
    setApiKey: (provider, apiKey) => invoke("set_api_key", { provider, apiKey }),
    deleteApiKey: (provider) => invoke("delete_api_key", { provider }),
    testConnection: (provider) => invoke("test_connection", { provider }),
    getHistory: () => invoke<HistoryItem[]>("get_history"),
    deleteHistoryItem: (id) => invoke("delete_history_item", { id }),
    readText: (path) => invoke<{ text: string | null; exists: boolean }>("read_text", { path }),
    exportSummary: (req) => invoke<ExportResult>("export_summary", { req }),
    cancelRun: () => invoke("cancel_run"),
    async runRecap(req, onProgress) {
      const unlisten = await listen<ProgressEvent>("recap-progress", (e) => onProgress(e.payload));
      try {
        return await invoke<RunResult>("run_recap", { req });
      } finally {
        unlisten();
      }
    },
    async resummarize(req, onProgress) {
      const unlisten = await listen<ProgressEvent>("recap-progress", (e) => onProgress(e.payload));
      try {
        return await invoke<RunResult>("resummarize", { req });
      } finally {
        unlisten();
      }
    },
    async pickAudioFile() {
      const selected = await dialog.open({
        multiple: false,
        directory: false,
        // Kept in sync with AUDIO_EXTENSIONS in src/workflows.py
        filters: [{ name: "Аудио/видео", extensions: ["wav", "mp3", "m4a", "ogg", "mp4", "mkv", "webm", "flac"] }],
      });
      return typeof selected === "string" ? selected : null;
    },
    revealPath: (path) => opener.revealItemInDir(path),
  };
}

// ── Browser mock implementation ──────────────────────────────────────────────

const MOCK_SETTINGS: AppSettings = {
  audio: "data/meeting.wav",
  transcript: "data/transcript.txt",
  summary: "data/summary.txt",
  privacy_ack: false,
  transcription: {
    language: "ru",
    model: {
      provider: "faster-whisper",
      name: "large-v3",
      device: "cuda",
      compute_type: "default",
      beam_size: 5,
      vad_filter: true,
      condition_on_previous_text: true,
    },
  },
  summarization: {
    language: null,
    mode: "medium",
    max_transcript_chars: 60000,
    timeout_seconds: 60,
    retries: 2,
    chunking_mode: "chunk",
    model: {
      provider: "ollama",
      name: "qwen3.5:latest",
      api_key_configured: false,
      base_url: "http://localhost:11434/v1",
      num_ctx: null,
    },
  },
  preprocessing: {
    enabled: false,
    sample_rate: 16000,
    channels: 1,
    codec: "pcm_s16le",
    loudness_normalization: false,
    target_lufs: -16,
    true_peak_db: -1.5,
    loudness_range: 11,
    highpass_hz: null,
    keep_temp: false,
  },
};

const MOCK_TRANSCRIPT = [
  "[0.00s -> 12.40s] Всем привет, начнём с короткого статуса по литературе.",
  "[12.40s -> 31.80s] Сейчас основная проблема на API-авторизации: иногда подвисает первый запрос.",
  "[31.80s -> 58.10s] Обсудили план: сначала чиним авторизацию, потом ускоряем экспорт.",
  "[58.10s -> 72.30s] Решили: Лёша берёт авторизацию, Маша — экспорт, срок до пятницы.",
  "[72.30s -> 95.00s] Дополнительно договорились сделать ревью по QA в начале следующей недели.",
].join("\n");

const MOCK_SUMMARY = `*Тема встречи*
Статус по проекту и план на неделю.

*Ключевые обсуждения*
- Проблема с API-авторизацией: подвисает первый запрос
- Приоритет: сначала авторизация, затем ускорение экспорта

*Решения и задачи*
- Авторизация — Лёша — до пятницы
- Экспорт — Маша — до пятницы
- Ревью по QA — начало следующей недели`;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function browserBridge(): Bridge {
  let settings: AppSettings = structuredClone(MOCK_SETTINGS);
  const apiKeys: Record<string, boolean> = {};
  let history: HistoryItem[] = [];
  const files: Record<string, string> = {};
  let cancelled = false;

  const pushHistory = (req: RunRequest, result: RunResult, provider: string, name: string) => {
    history = [
      {
        id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
        audio_path: req.audio_path,
        audio_name: name,
        status: result.status,
        transcript_path: result.transcript_path,
        summary_path: result.summary_path,
        summary_json_path: result.summary_json_path,
        provider,
        model: req.overrides?.model ?? settings.summarization.model.name,
        mode: req.overrides?.mode ?? settings.summarization.mode,
        transcription_language: settings.transcription.language,
        summary_language: settings.summarization.language,
        duration_seconds: null,
        error_message: result.error_message,
      },
      ...history,
    ];
  };

  return {
    async getSettings() {
      const s = structuredClone(settings);
      s.summarization.model.api_key_configured = !!apiKeys[s.summarization.model.provider];
      return s;
    },
    async saveSettings(next) {
      settings = structuredClone(next);
    },
    async setApiKey(provider) {
      apiKeys[provider] = true;
    },
    async deleteApiKey(provider) {
      delete apiKeys[provider];
    },
    async testConnection() {
      await delay(500);
      return { ok: true, message: "Подключение успешно (демо-режим)." };
    },
    async getHistory() {
      return structuredClone(history);
    },
    async deleteHistoryItem(id) {
      history = history.filter((h) => h.id !== id);
    },
    async readText(path) {
      if (path && files[path] !== undefined) return { text: files[path], exists: true };
      return { text: null, exists: false };
    },
    async exportSummary(req) {
      await delay(150);
      const dir = req.target_dir || "C:/recap/output";
      return {
        telegram_path: req.formats.includes("telegram") ? `${dir}/${req.base_name}_summary.txt` : null,
        plain_path: req.formats.includes("plain") ? `${dir}/${req.base_name}_summary_plain.txt` : null,
        json_path: req.formats.includes("json") ? `${dir}/${req.base_name}_summary.json` : null,
      };
    },
    async cancelRun() {
      cancelled = true;
    },
    async runRecap(req, onProgress) {
      cancelled = false;
      const provider = req.overrides?.provider ?? settings.summarization.model.provider;
      const name = req.audio_path.split(/[\\/]/).pop() ?? req.audio_path;
      const emit = (e: ProgressEvent) => onProgress(e);

      if (settings.preprocessing.enabled) {
        emit({ step: "preprocess", status: "running", message: "Предобработка аудио…", percent: null, path: null });
        await delay(400);
        emit({ step: "preprocess", status: "success", message: "Аудио подготовлено.", percent: null, path: null });
      }
      emit({ step: "transcribe", status: "running", message: "Транскрибация началась.", percent: 0, path: null });
      for (const p of [25, 55, 85]) {
        await delay(450);
        if (cancelled) break;
        emit({ step: "transcribe", status: "running", message: `Транскрибация… ${p}%`, percent: p, path: null });
      }
      const transcriptPath = req.transcript_path ?? "C:/recap/transcript.txt";
      emit({
        step: "transcribe",
        status: "success",
        message: `Транскрипт сохранён: ${transcriptPath}`,
        percent: 100,
        path: transcriptPath,
      });
      files[transcriptPath] = MOCK_TRANSCRIPT;

      const summaryPath = req.summary_path ?? "C:/recap/summary.txt";
      const failLLM = provider === "openai" && !apiKeys["openai"];
      let result: RunResult;
      if (failLLM) {
        emit({
          step: "summarize",
          status: "error",
          message: "Ошибка авторизации LLM: проверьте сохранённый ключ API.",
          percent: null,
          path: null,
        });
        result = {
          status: "partial_success",
          transcript_path: transcriptPath,
          summary_path: null,
          summary_json_path: null,
          transcript_text: MOCK_TRANSCRIPT,
          summary_text: null,
          error_message: "Ошибка авторизации LLM: проверьте сохранённый ключ API.",
        };
      } else {
        emit({
          step: "summarize",
          status: "running",
          message: `Суммаризация началась: ${provider}.`,
          percent: null,
          path: null,
        });
        await delay(700);
        emit({ step: "summarize", status: "success", message: "Резюме готово.", percent: null, path: null });
        emit({ step: "export", status: "running", message: "Сохранение результатов…", percent: null, path: null });
        await delay(250);
        emit({ step: "export", status: "success", message: `Готово: ${summaryPath}`, percent: null, path: summaryPath });
        files[summaryPath] = MOCK_SUMMARY;
        result = {
          status: "success",
          transcript_path: transcriptPath,
          summary_path: summaryPath,
          summary_json_path: summaryPath.replace(/\.txt$/, ".json"),
          transcript_text: MOCK_TRANSCRIPT,
          summary_text: MOCK_SUMMARY,
          error_message: null,
        };
      }

      pushHistory(req, result, provider, name);
      return result;
    },
    async resummarize(req, onProgress) {
      const provider = req.overrides?.provider ?? settings.summarization.model.provider;
      const name = req.audio_path.split(/[\\/]/).pop() ?? req.audio_path;
      const transcriptPath = req.transcript_path ?? "C:/recap/transcript.txt";
      const summaryPath = req.summary_path ?? "C:/recap/summary.txt";
      const transcriptText = files[transcriptPath] ?? MOCK_TRANSCRIPT;
      onProgress({
        step: "transcribe",
        status: "success",
        message: "Используется сохранённый транскрипт.",
        percent: null,
        path: transcriptPath,
      });
      const failLLM = provider === "openai" && !apiKeys["openai"];
      let result: RunResult;
      if (failLLM) {
        onProgress({
          step: "summarize",
          status: "error",
          message: "Ошибка авторизации LLM: проверьте сохранённый ключ API.",
          percent: null,
          path: null,
        });
        result = {
          status: "partial_success",
          transcript_path: transcriptPath,
          summary_path: null,
          summary_json_path: null,
          transcript_text: transcriptText,
          summary_text: null,
          error_message: "Ошибка авторизации LLM: проверьте сохранённый ключ API.",
        };
      } else {
        onProgress({ step: "summarize", status: "running", message: `Суммаризация началась: ${provider}.`, percent: null, path: null });
        await delay(700);
        onProgress({ step: "summarize", status: "success", message: "Резюме готово.", percent: null, path: null });
        onProgress({ step: "export", status: "success", message: `Готово: ${summaryPath}`, percent: null, path: summaryPath });
        files[summaryPath] = MOCK_SUMMARY;
        result = {
          status: "success",
          transcript_path: transcriptPath,
          summary_path: summaryPath,
          summary_json_path: summaryPath.replace(/\.txt$/, ".json"),
          transcript_text: transcriptText,
          summary_text: MOCK_SUMMARY,
          error_message: null,
        };
      }
      pushHistory(req, result, provider, name);
      return result;
    },
    async pickAudioFile() {
      return "C:/meetings/meeting_2026_06_19.mp3";
    },
    async revealPath() {
      /* no-op in browser */
    },
  };
}

let cached: Promise<Bridge> | null = null;

export function getBridge(): Promise<Bridge> {
  if (!cached) {
    cached = isTauri() ? tauriBridge() : Promise.resolve(browserBridge());
  }
  return cached;
}
