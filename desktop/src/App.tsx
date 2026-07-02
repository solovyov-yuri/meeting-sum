import { useEffect, useState } from "react";
import { Inspector } from "@/components/Inspector";
import { SettingsScreen } from "@/components/SettingsScreen";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ui/toast";
import { Workspace } from "@/components/Workspace";
import { getBridge, isTauri } from "@/lib/bridge";
import type { HistoryItem } from "@/lib/types";
import { useRecap } from "@/hooks/useRecap";

type View = "run" | "settings";

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}

function Shell() {
  const recap = useRecap();
  const [view, setView] = useState<View>("run");
  const [dragActive, setDragActive] = useState(false);

  // Native (Tauri) drag-and-drop delivers real file paths; the browser cannot.
  useEffect(() => {
    if (!isTauri()) return;
    let dispose: (() => void) | undefined;
    (async () => {
      const { getCurrentWebview } = await import("@tauri-apps/api/webview");
      dispose = await getCurrentWebview().onDragDropEvent((event) => {
        if (event.payload.type === "over" || event.payload.type === "enter") setDragActive(true);
        else if (event.payload.type === "leave") setDragActive(false);
        else if (event.payload.type === "drop") {
          setDragActive(false);
          const path = event.payload.paths?.[0];
          if (path) {
            setView("run");
            recap.selectFile(path);
          }
        }
      });
    })();
    return () => dispose?.();
    // recap.selectFile is stable (useCallback); intentionally run once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openHistory = (item: HistoryItem) => {
    setView("run");
    void recap.openHistoryItem(item);
  };

  const revealHistory = async (item: HistoryItem) => {
    const path = item.summary_path ?? item.transcript_path;
    if (!path) return;
    const bridge = await getBridge();
    await bridge.revealPath(path);
  };

  if (recap.loadError) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center">
        <div>
          <p className="text-md font-medium text-danger">Не удалось загрузить настройки</p>
          <p className="mt-1 text-base text-ink-muted">{recap.loadError}</p>
        </div>
      </div>
    );
  }

  if (!recap.settings) {
    return <div className="flex h-full items-center justify-center text-base text-ink-muted">Загрузка…</div>;
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        view={view}
        onNewRun={() => {
          recap.newRun();
          setView("run");
        }}
        onOpenHistory={() => setView("run")}
        onOpenSettings={() => setView("settings")}
        history={recap.history}
        activeHistoryId={recap.activeHistoryId}
        onSelectHistory={openHistory}
        onRevealHistory={revealHistory}
        onDeleteHistory={recap.removeHistoryItem}
      />

      {view === "settings" ? (
        <SettingsScreen settings={recap.settings} onSaved={recap.reloadSettings} />
      ) : (
        <>
          <Workspace
            phase={recap.phase}
            audioPath={recap.audioPath}
            runMode={recap.runMode}
            setRunMode={recap.setRunMode}
            steps={recap.steps}
            logs={recap.logs}
            result={recap.result}
            editedSummary={recap.editedSummary}
            setEditedSummary={recap.setEditedSummary}
            dragActive={dragActive}
            onPick={recap.pickFile}
            onBrowserDrop={(name) => recap.selectFile(`C:/meetings/${name}`)}
            onStart={recap.start}
            onCancel={recap.cancel}
            onRetry={recap.retrySummarization}
          />
          <Inspector
            phase={recap.phase}
            result={recap.result}
            settings={recap.settings}
            runMode={recap.runMode}
            runConfig={recap.runConfig}
            audioPath={recap.audioPath}
            editedSummary={recap.editedSummary}
            onRetry={recap.retrySummarization}
          />
        </>
      )}
    </div>
  );
}
