import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRecap } from "./useRecap";

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
