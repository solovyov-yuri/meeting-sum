import { Copy, Download, FolderOpen, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getBridge } from "@/lib/bridge";
import type { AppSettings, ExportFormat, RunResult, SummaryMode } from "@/lib/types";
import { dirName, stem } from "@/lib/utils";
import type { Phase, RunConfig } from "@/hooks/useRecap";

const LANG_LABELS: Record<string, string> = { ru: "Русский", en: "English", auto: "Авто" };
const MODE_LABELS: Record<SummaryMode, string> = { brief: "краткий", medium: "средний", detailed: "подробный" };

const EXPORT_LABELS: Record<ExportFormat, string> = {
  telegram: "Telegram (.txt)",
  plain: "Plain text (.txt)",
  json: "JSON",
};

interface InspectorProps {
  phase: Phase;
  result: RunResult | null;
  settings: AppSettings;
  runConfig: RunConfig | null;
  audioPath: string | null;
  editedSummary: string;
  onRetry: () => void;
}

export function Inspector(props: InspectorProps) {
  const showResult = props.phase === "done" && props.result && props.result.status !== "failed";
  return (
    <aside className="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto border-l border-border bg-panel px-3.5 py-4 scrollbar-thin">
      {showResult ? <ResultInspector {...props} /> : <RunInspector {...props} />}
    </aside>
  );
}

function InfoBox({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <div className="flex flex-col gap-2 rounded-card border border-border bg-panel-soft p-3">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3 text-base">
          <span className="text-ink-muted">{label}</span>
          <span className="font-semibold text-ink">{value}</span>
        </div>
      ))}
    </div>
  );
}

function RunInspector({ settings }: InspectorProps) {
  // Read-only: runs always use the saved Settings (single source of truth). No per-run editing.
  const s = settings.summarization;
  return (
    <>
      <h2 className="text-[15px] font-semibold text-ink">Параметры запуска</h2>
      <InfoBox
        rows={[
          ["Провайдер", s.model.provider],
          ["Модель", s.model.name],
          ["Режим саммари", MODE_LABELS[s.mode]],
          ["Язык распознавания", LANG_LABELS[settings.transcription.language] ?? settings.transcription.language],
          ["Предобработка", settings.preprocessing.enabled ? "вкл" : "выкл"],
          ["Chunking", s.chunking_mode],
        ]}
      />
      <div className="rounded-card border border-border bg-panel-soft p-3 text-base text-ink-muted">
        Параметры берутся из раздела «Настройки». Чтобы изменить провайдера, модель или режим —
        откройте «Настройки» и запустите разбор заново.
      </div>
    </>
  );
}

function ResultInspector({ result, settings, audioPath, editedSummary, runConfig, onRetry }: InspectorProps) {
  const { toast } = useToast();
  const [formats, setFormats] = useState<ExportFormat[]>(["telegram", "plain", "json"]);
  const [busy, setBusy] = useState(false);
  if (!result) return null;

  const partial = result.status === "partial_success";
  const mode = runConfig?.mode ?? settings.summarization.mode;
  const basePath = result.summary_path ?? result.transcript_path ?? audioPath ?? "summary";
  const targetDir = dirName(basePath);

  const toggle = (f: ExportFormat) =>
    setFormats((prev) => (prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]));

  const reveal = async () => {
    const path = result.summary_path ?? result.transcript_path;
    if (!path) return;
    const bridge = await getBridge();
    await bridge.revealPath(path);
  };

  const copy = async () => {
    await navigator.clipboard.writeText(editedSummary);
    toast("Саммари скопировано", "ok");
  };

  const doExport = async () => {
    if (formats.length === 0) {
      toast("Выберите хотя бы один формат", "error");
      return;
    }
    setBusy(true);
    try {
      const bridge = await getBridge();
      await bridge.exportSummary({
        summary_text: editedSummary,
        formats,
        target_dir: targetDir,
        base_name: stem(audioPath ?? basePath),
        mode,
      });
      toast(`Сохранено в: ${targetDir}`, "ok");
      await bridge.revealPath(targetDir); // open the folder so it's clear where files went
    } catch (e) {
      toast(e instanceof Error ? e.message : "Ошибка экспорта", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2 className="text-[15px] font-semibold text-ink">Результат</h2>
      <InfoBox
        rows={[
          ["Транскрипт", <span key="t" className="text-ok">{result.transcript_path ? "сохранён" : "—"}</span>],
          [
            "Саммари",
            <span key="s" className={partial ? "text-warn" : "text-ok"}>
              {result.summary_path ? "сохранено" : "не создано"}
            </span>,
          ],
          ["Провайдер", runConfig?.provider ?? "—"],
          ["Модель", runConfig?.model ?? "—"],
        ]}
      />

      {partial ? (
        <Button variant="primary" size="lg" className="w-full" onClick={onRetry}>
          <RotateCcw className="h-4 w-4" /> Повторить суммаризацию
        </Button>
      ) : (
        <Button variant="primary" size="lg" className="w-full" onClick={copy} disabled={!editedSummary}>
          <Copy className="h-4 w-4" /> Копировать саммари
        </Button>
      )}
      <Button variant="secondary" size="lg" className="w-full" onClick={reveal}>
        <FolderOpen className="h-4 w-4" /> Открыть папку
      </Button>

      <div className="flex flex-col gap-2 rounded-card border border-border bg-panel-soft p-3">
        <h3 className="text-base font-semibold text-ink">Экспорт саммари</h3>
        {(Object.keys(EXPORT_LABELS) as ExportFormat[]).map((f) => (
          <label key={f} className="flex cursor-pointer items-center gap-2 text-base text-ink">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 accent-accent"
              checked={formats.includes(f)}
              onChange={() => toggle(f)}
            />
            {EXPORT_LABELS[f]}
          </label>
        ))}
        <p className="text-sm text-ink-soft">Папка: {targetDir}</p>
        <Button variant="secondary" size="lg" className="w-full" onClick={doExport} disabled={busy || !editedSummary}>
          <Download className="h-4 w-4" /> Экспортировать
        </Button>
      </div>
    </>
  );
}
