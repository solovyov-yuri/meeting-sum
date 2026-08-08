import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { LogEntry } from "@/hooks/useRecap";

export function LogView({ logs }: { logs: LogEntry[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [logs]);

  if (logs.length === 0) {
    return <p className="px-1 py-4 text-base text-ink-muted">Лог появится после запуска.</p>;
  }

  return (
    <div className="h-full overflow-y-auto p-3.5 scrollbar-thin" data-selectable>
      {logs.map((entry) => (
        <div
          key={entry.id}
          className="grid grid-cols-[76px_1fr] gap-3 border-b border-border/70 py-2 last:border-0"
        >
          <time className="font-mono text-sm text-ink-soft">{entry.time}</time>
          <span
            className={cn(
              "text-base",
              entry.status === "success" && "text-ok",
              entry.status === "error" && "text-danger",
              entry.status === "warning" && "text-warn",
              entry.status !== "success" &&
                entry.status !== "error" &&
                entry.status !== "warning" &&
                "text-ink",
            )}
          >
            {entry.message}
          </span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
