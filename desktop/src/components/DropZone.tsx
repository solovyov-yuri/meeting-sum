import { FileAudio, UploadCloud } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onPick: () => void;
  /** Browser fallback only — Tauri delivers real paths via the window drag-drop event. */
  onBrowserDrop?: (fileName: string) => void;
  dragActive?: boolean;
  /** What kind of file this run mode expects — drives the wording. */
  kind?: "audio" | "transcript";
}

export function DropZone({ onPick, onBrowserDrop, dragActive, kind = "audio" }: DropZoneProps) {
  const [hover, setHover] = useState(false);
  const active = hover || dragActive;
  const title = kind === "transcript" ? "Выберите файл транскрипта" : "Выберите аудиофайл встречи";
  const supports = kind === "transcript" ? "Поддерживается TXT." : "Поддерживаются WAV, MP3, M4A, OGG, MP4, MKV, WEBM, FLAC.";

  return (
    <div
      onClick={onPick}
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        const file = e.dataTransfer.files?.[0];
        if (file && onBrowserDrop) onBrowserDrop(file.name);
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed bg-panel px-6 py-12 text-center transition-colors",
        active ? "border-accent bg-accent-soft" : "border-border hover:border-accent/50",
      )}
    >
      <span className={cn("flex h-12 w-12 items-center justify-center rounded-full", active ? "bg-white" : "bg-app")}>
        {active ? <FileAudio className="h-6 w-6 text-accent" /> : <UploadCloud className="h-6 w-6 text-ink-muted" />}
      </span>
      <div>
        <p className="text-lg font-medium text-ink">{title}</p>
        <p className="mt-1 text-base text-ink-muted">Перетащите файл сюда или нажмите, чтобы выбрать.</p>
        <p className="mt-0.5 text-sm text-ink-muted">{supports}</p>
      </div>
      <Button
        variant="secondary"
        size="md"
        onClick={(e) => {
          e.stopPropagation();
          onPick();
        }}
      >
        Выбрать файл
      </Button>
    </div>
  );
}
