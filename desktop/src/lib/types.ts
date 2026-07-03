// Types mirroring docs/desktop-bridge-contract.md. Kept in sync with src/desktop_bridge.py.

export type SummaryMode = "brief" | "medium" | "detailed" | "lecture";
/** Which slice of the pipeline a run executes (distinct from SummaryMode). */
export type RunMode = "full" | "preprocess" | "transcribe" | "summarize";
export type ChunkingMode = "chunk" | "truncate";
export type SummaryProvider = "openai" | "xai" | "ollama" | "lm-studio" | "vllm";
export type WhisperDevice = "cuda" | "cpu" | "auto";
export type ComputeType = "default" | "float16" | "int8" | "int8_float16" | "float32";
export type ExportFormat = "markdown" | "plain" | "html" | "json";

export interface TranscriptionModelSettings {
  provider: "faster-whisper";
  name: string;
  device: WhisperDevice;
  compute_type: ComputeType;
  beam_size: number;
  vad_filter: boolean;
  condition_on_previous_text: boolean;
}

export interface SummarizationModelSettings {
  provider: SummaryProvider;
  name: string;
  api_key_configured: boolean;
  base_url: string | null;
  num_ctx: number | null;
}

export interface PreprocessingSettings {
  enabled: boolean;
  sample_rate: number;
  channels: number;
  codec: string;
  loudness_normalization: boolean;
  target_lufs: number;
  true_peak_db: number;
  loudness_range: number;
  highpass_hz: number | null;
  keep_temp: boolean;
}

export interface AppSettings {
  audio: string;
  transcript: string;
  summary: string;
  /** Desktop-only: single folder for run outputs (transcript + summary), named by audio stem.
   *  null → outputs land next to the audio file. */
  output_dir: string | null;
  privacy_ack: boolean;
  /** Per-provider key state (CODE-007): whether a key is stored for each provider. Read-only. */
  api_keys_configured: Record<string, boolean>;
  transcription: {
    language: string;
    model: TranscriptionModelSettings;
  };
  summarization: {
    language: string | null;
    mode: SummaryMode;
    max_transcript_chars: number;
    timeout_seconds: number;
    retries: number;
    chunking_mode: ChunkingMode;
    model: SummarizationModelSettings;
  };
  preprocessing: PreprocessingSettings;
}

export type StepName = "download" | "preprocess" | "transcribe" | "summarize" | "export";
export type StepStatus = "pending" | "running" | "success" | "warning" | "error" | "cancelled";

export interface ProgressEvent {
  step: StepName;
  status: StepStatus;
  message: string;
  percent: number | null;
  path: string | null;
}

export type RunStatus = "success" | "partial_success" | "failed" | "cancelled";

export interface RunResult {
  status: RunStatus;
  transcript_path: string | null;
  summary_path: string | null;
  summary_json_path: string | null;
  transcript_text: string | null;
  summary_text: string | null;
  error_message: string | null;
  /** preprocess-only: the produced *.preprocessed.wav (else null/absent). */
  output_path?: string | null;
}

export interface RunRequest {
  run_mode?: RunMode;
  /** Audio input for full/preprocess/transcribe; omitted for standalone summarize. */
  audio_path?: string | null;
  transcript_path?: string | null;
  summary_path?: string | null;
  overrides?: {
    transcription_language?: string | null;
    summary_language?: string | null;
    provider?: string | null;
    model?: string | null;
    mode?: string | null;
  };
}

export interface HistoryItem {
  id: string;
  created_at: string;
  run_mode?: RunMode;
  audio_path: string;
  audio_name: string;
  status: RunStatus;
  output_path?: string | null;
  transcript_path: string | null;
  summary_path: string | null;
  summary_json_path: string | null;
  provider: string;
  model: string;
  mode: string;
  transcription_language: string | null;
  summary_language: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

export interface ExportRequest {
  // Export renders every format from the base .json (summary_json_path). summary_text is a fallback
  // for when no JSON exists yet.
  summary_json_path: string | null;
  summary_text: string;
  formats: ExportFormat[];
  target_dir: string;
  base_name: string;
  mode: string;
}

export interface ExportResult {
  markdown_path: string | null;
  plain_path: string | null;
  html_path: string | null;
  json_path: string | null;
}

export interface SaveSummaryRequest {
  summary_text: string;
  summary_path: string;
  mode: string;
}

export interface SaveSummaryResult {
  summary_path: string;
  json_path: string;
}

export interface ModelStatus {
  installed: boolean;
  provider: string;
  model: string;
  base_url: string | null;
}

export interface PullModelRequest {
  model: string;
  base_url: string;
}
