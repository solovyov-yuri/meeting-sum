import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRecap } from "./useRecap";
import type { HistoryItem, RunMode, RunStatus } from "@/lib/types";

// The browser mock reports the Ollama model as not installed, so start() should offer to download
// it (modelPrompt) rather than launch the run.
describe("useRecap — Ollama model pre-flight", () => {
  it("prompts to download a missing model and does NOT start the run", async () => {
    const { result } = renderHook(() => useRecap());
    await waitFor(() => expect(result.current.settings).not.toBeNull());

    act(() => result.current.selectFile("C:/meetings/demo.wav"));
    await waitFor(() => expect(result.current.audioPath).toBe("C:/meetings/demo.wav"));

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.modelPrompt?.model).toBe("qwen3.5:latest");
    expect(result.current.phase).toBe("idle"); // run was NOT started
  });

  it("confirming the download clears the prompt and proceeds to the run", async () => {
    const { result } = renderHook(() => useRecap());
    await waitFor(() => expect(result.current.settings).not.toBeNull());
    act(() => result.current.selectFile("C:/meetings/demo.wav"));
    await waitFor(() => expect(result.current.audioPath).toBe("C:/meetings/demo.wav"));
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.modelPrompt).not.toBeNull();

    await act(async () => {
      await result.current.confirmModelDownload();
    });

    expect(result.current.modelPrompt).toBeNull(); // downloaded → prompt gone
    await waitFor(() => expect(result.current.phase).toBe("done")); // and the run ran
  });
});

// Reopening a history entry has to mark a step the mode actually shows as a ring — otherwise a
// failed summarize-only run looks untouched.
describe("useRecap — step states when reopening history", () => {
  const historyItem = (runMode: RunMode | undefined, status: RunStatus): HistoryItem => ({
    id: `${runMode ?? "legacy"}-${status}`,
    created_at: "2026-07-05T10:00:00+03:00",
    run_mode: runMode,
    audio_path: "C:/meetings/demo.wav",
    audio_name: "demo.wav",
    status,
    transcript_path: null,
    summary_path: null,
    summary_json_path: null,
    provider: "ollama",
    model: "qwen3.5:latest",
    mode: "medium",
    transcription_language: "ru",
    summary_language: "ru",
    duration_seconds: null,
    error_message: "boom",
  });

  const openSteps = async (runMode: RunMode | undefined, status: RunStatus) => {
    const { result } = renderHook(() => useRecap());
    await waitFor(() => expect(result.current.settings).not.toBeNull());
    await act(async () => {
      await result.current.openHistoryItem(historyItem(runMode, status));
    });
    return result.current.steps;
  };

  it("puts a failed summarize-only run on the summarize step", async () => {
    const steps = await openSteps("summarize", "failed");
    expect(steps.summarize.status).toBe("error");
  });

  it("puts a cancelled summarize-only run on the summarize step", async () => {
    const steps = await openSteps("summarize", "cancelled");
    expect(steps.summarize.status).toBe("cancelled");
  });

  it("puts a failed preprocess-only run on the preprocess step", async () => {
    const steps = await openSteps("preprocess", "failed");
    expect(steps.preprocess.status).toBe("error");
  });

  it("keeps a failed transcribe-only run on the transcribe step", async () => {
    const steps = await openSteps("transcribe", "failed");
    expect(steps.transcribe.status).toBe("error");
  });

  it("keeps the full-mode mapping (failed → transcribe, partial → summarize)", async () => {
    expect((await openSteps("full", "failed")).transcribe.status).toBe("error");
    const partial = await openSteps("full", "partial_success");
    expect(partial.transcribe.status).toBe("success");
    expect(partial.summarize.status).toBe("error");
  });

  it("treats an entry without run_mode as a full run", async () => {
    const steps = await openSteps(undefined, "failed");
    expect(steps.transcribe.status).toBe("error");
  });
});
