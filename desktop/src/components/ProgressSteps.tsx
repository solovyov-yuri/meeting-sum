import { AlertTriangle, Check, CircleSlash, Hourglass, Loader2, X } from "lucide-react";
import type { StepName, StepStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { STEP_ORDER, type StepState } from "@/hooks/useRecap";

const STEP_LABELS: Record<StepName, string> = {
  preprocess: "Подготовка",
  transcribe: "Транскрибация",
  summarize: "Суммаризация",
  export: "Экспорт",
};

const STATUS_LABELS: Record<StepStatus, string> = {
  pending: "Ожидает",
  running: "Выполняется",
  success: "Готово",
  warning: "Внимание",
  error: "Ошибка",
  cancelled: "Остановлено",
};

const BORDER_STRONG = "#D3D8DF";
const ACCENT = "#2563EB";
const SUCCESS = "#15803D";
const WARNING = "#B45309";
const DANGER = "#B91C1C";

function ringBackground(status: StepStatus, percent: number | null): string {
  switch (status) {
    case "success":
      return SUCCESS;
    case "error":
      return DANGER;
    case "warning":
      return WARNING;
    case "running": {
      if (percent != null) {
        const deg = Math.max(0, Math.min(360, Math.round((percent / 100) * 360)));
        return `conic-gradient(${ACCENT} ${deg}deg, ${BORDER_STRONG} ${deg}deg 360deg)`;
      }
      return ACCENT;
    }
    default:
      return BORDER_STRONG;
  }
}

function StepCircle({ status, percent }: { status: StepStatus; percent: number | null }) {
  let inner: React.ReactNode;
  if (status === "success") inner = <Check className="h-7 w-7 text-ok" strokeWidth={2.5} />;
  else if (status === "error") inner = <X className="h-6 w-6 text-danger" strokeWidth={2.5} />;
  else if (status === "warning") inner = <AlertTriangle className="h-5 w-5 text-warn" />;
  else if (status === "cancelled") inner = <CircleSlash className="h-5 w-5 text-ink-soft" />;
  else if (status === "running")
    inner =
      percent != null ? (
        <span className="text-[20px] font-semibold text-ink tabular-nums">{percent}%</span>
      ) : (
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
      );
  else inner = <Hourglass className="h-5 w-5 text-ink-soft" />;

  return (
    <div
      className="grid h-[78px] w-[78px] place-items-center rounded-full shadow-[0_1px_3px_rgba(23,26,31,0.08)]"
      style={{ background: ringBackground(status, percent) }}
    >
      <span className="grid h-[72px] w-[72px] place-items-center rounded-full bg-panel">{inner}</span>
    </div>
  );
}

export function ProgressSteps({
  steps,
  order = STEP_ORDER,
}: {
  steps: Record<StepName, StepState>;
  order?: StepName[];
}) {
  // Circles are centered in equal columns; the connector runs from the first to the last center.
  const edge = `${50 / order.length}%`;
  return (
    <section
      className="relative grid min-h-[166px] items-start rounded-card border border-border bg-panel px-11 pb-6 pt-[30px]"
      style={{ gridTemplateColumns: `repeat(${order.length}, minmax(0, 1fr))` }}
    >
      {order.length > 1 && (
        <div className="absolute top-[70px] h-0.5 bg-border-strong" style={{ left: edge, right: edge }} />
      )}
      {order.map((step) => {
        const state = steps[step];
        return (
          <div key={step} className="relative z-[1] flex flex-col items-center gap-[7px] text-center">
            <StepCircle status={state.status} percent={state.percent} />
            <strong className="mt-1 truncate text-md font-semibold text-ink">{STEP_LABELS[step]}</strong>
            <small
              className={cn(
                "text-sm font-semibold",
                state.status === "success" && "text-ok",
                state.status === "running" && "text-accent",
                state.status === "error" && "text-danger",
                state.status === "warning" && "text-warn",
                (state.status === "pending" || state.status === "cancelled") && "text-ink-soft",
              )}
            >
              {state.status === "running" && state.percent != null ? `${state.percent}%` : STATUS_LABELS[state.status]}
            </small>
          </div>
        );
      })}
    </section>
  );
}
