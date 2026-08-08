import { Download, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PullModelRequest } from "@/lib/types";
import type { ModelPull } from "@/hooks/useRecap";

interface Props {
  prompt: PullModelRequest | null;
  pull: ModelPull | null;
  onConfirm: () => void;
  onCancelPull: () => void;
  onDismiss: () => void;
}

/** Confirm-first prompt shown before a run when the configured Ollama model isn't installed. */
export function ModelDownloadDialog({ prompt, pull, onConfirm, onCancelPull, onDismiss }: Props) {
  if (!prompt) return null;
  const pulling = pull !== null;
  const pct = pull?.percent != null ? Math.round(pull.percent * 100) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={pulling ? undefined : onDismiss}>
      <div className="w-full max-w-md rounded-card border border-border bg-panel p-5 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-ink">Модель не установлена</h2>
        <p className="mt-2 text-base text-ink-muted">
          Модель <span className="font-semibold text-ink">{prompt.model}</span> не найдена в Ollama.
          {pulling ? " Загружается…" : " Скачать её сейчас?"}
        </p>

        {pulling && (
          <div className="mt-4">
            <div className="h-2 overflow-hidden rounded-full bg-app">
              <div
                className="h-full bg-accent transition-[width]"
                style={{ width: pct != null ? `${pct}%` : "40%" }}
              />
            </div>
            <p className="mt-1.5 truncate text-sm text-ink-muted">
              {pull?.message}
              {pct != null ? ` — ${pct}%` : ""}
            </p>
            <p className="mt-1 text-xs text-ink-soft">При отмене загрузка может продолжиться в Ollama в фоне.</p>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          {pulling ? (
            <Button variant="danger" size="lg" onClick={onCancelPull}>
              <Square className="h-4 w-4" /> Отменить загрузку
            </Button>
          ) : (
            <>
              <Button variant="secondary" size="lg" onClick={onDismiss}>
                Отмена
              </Button>
              <Button variant="primary" size="lg" onClick={onConfirm}>
                <Download className="h-4 w-4" /> Скачать
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
