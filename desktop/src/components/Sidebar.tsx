import { ChevronDown, FileText, FolderOpen, History, Plus, Settings as SettingsIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import iconUrl from "@/assets/recap-icon.png";
import { Button } from "@/components/ui/button";
import type { HistoryItem } from "@/lib/types";
import { cn, fileName, formatWhen } from "@/lib/utils";
import { StatusDot } from "./StatusDot";

interface SidebarProps {
  view: "run" | "settings";
  onNewRun: () => void;
  onOpenRun: () => void;
  onOpenHistory: () => void;
  onOpenSettings: () => void;
  history: HistoryItem[];
  activeHistoryId: string | null;
  onSelectHistory: (item: HistoryItem) => void;
  onRevealHistory: (item: HistoryItem) => void;
  onDeleteHistory: (id: string) => void;
}

export function Sidebar({
  view,
  onNewRun,
  onOpenRun,
  onOpenHistory,
  onOpenSettings,
  history,
  activeHistoryId,
  onSelectHistory,
  onRevealHistory,
  onDeleteHistory,
}: SidebarProps) {
  const [recentOpen, setRecentOpen] = useState(true);
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-panel">
      <div className="flex h-14 items-center gap-2.5 px-3.5 text-[15px] font-semibold">
        <img src={iconUrl} alt="Recap" className="h-7 w-7 rounded-md" />
        <span>Recap</span>
      </div>

      <div className="px-3.5 pb-2.5">
        <Button variant="primary" size="lg" className="w-full" onClick={onNewRun}>
          <Plus className="h-4 w-4" /> Новый разбор
        </Button>
      </div>

      <nav className="flex flex-col gap-0.5 px-2">
        <NavItem icon={FileText} label="Текущий разбор" active={view === "run"} onClick={onOpenRun} />
        <NavItem icon={SettingsIcon} label="Настройки" active={view === "settings"} onClick={onOpenSettings} />
        <button
          onClick={() => {
            onOpenHistory();
            setRecentOpen((o) => !o);
          }}
          className={cn(
            "flex h-[34px] items-center gap-2 rounded-md px-2.5 text-base transition-colors text-ink hover:bg-app",
          )}
        >
          <History className="h-4 w-4" />
          <span className="flex-1 text-left">История</span>
          <ChevronDown className={cn("h-4 w-4 transition-transform", !recentOpen && "-rotate-90")} />
        </button>
      </nav>

      {recentOpen && (
        <>
          <div className="mt-1.5 px-3.5 pb-1.5 text-xs font-bold uppercase text-ink-soft">Последние</div>
          <div className="flex-1 overflow-y-auto px-2 pb-3 scrollbar-thin">
            {history.length === 0 ? (
          <p className="px-2 py-2 text-sm text-ink-muted">Пока нет запусков.</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {history.map((item) => (
              <li
                key={item.id}
                className={cn(
                  "group flex min-h-[52px] items-start gap-2 rounded-md p-2 transition-colors hover:bg-app",
                  activeHistoryId === item.id && "bg-accent-soft",
                )}
              >
                <button onClick={() => onSelectHistory(item)} className="flex min-w-0 flex-1 items-start gap-2 text-left">
                  <StatusDot status={item.status} className="mt-1.5" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-base font-semibold text-ink">{fileName(item.audio_name)}</span>
                    <span className="mt-0.5 block truncate text-sm text-ink-muted">
                      {formatWhen(item.created_at)} · {item.provider} / {item.mode}
                    </span>
                  </span>
                </button>
                <span className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    title="Открыть папку"
                    onClick={() => onRevealHistory(item)}
                    className="rounded p-1 text-ink-muted hover:bg-white hover:text-ink"
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                  </button>
                  <button
                    title="Удалить из истории"
                    onClick={() => onDeleteHistory(item.id)}
                    className="rounded p-1 text-ink-muted hover:bg-white hover:text-danger"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

function NavItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof History;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex h-[34px] items-center gap-2 rounded-md px-2.5 text-base transition-colors",
        active ? "bg-accent-soft font-semibold text-accent" : "text-ink hover:bg-app",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}
