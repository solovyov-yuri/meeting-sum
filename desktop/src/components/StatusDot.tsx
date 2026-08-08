import type { RunStatus, StepStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  success: "bg-ok",
  partial_success: "bg-warn",
  warning: "bg-warn",
  failed: "bg-danger",
  error: "bg-danger",
  cancelled: "bg-ink-muted",
  running: "bg-accent",
  pending: "bg-border",
};

export function StatusDot({ status, className }: { status: RunStatus | StepStatus; className?: string }) {
  return <span className={cn("inline-block h-2 w-2 shrink-0 rounded-full", colors[status] ?? "bg-border", className)} />;
}

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  success: "Успешно",
  partial_success: "Частично",
  failed: "Ошибка",
  cancelled: "Остановлено",
};
