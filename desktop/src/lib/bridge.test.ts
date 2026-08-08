import { describe, expect, it, vi } from "vitest";
import { getBridge } from "./bridge";
import type { ProgressEvent } from "./types";

describe("browser bridge (mock)", () => {
  it("runs a successful pipeline and records history", async () => {
    const bridge = await getBridge();
    const events: ProgressEvent[] = [];
    vi.useRealTimers();

    const result = await bridge.runRecap(
      {
        audio_path: "C:/meetings/demo.mp3",
        transcript_path: "C:/meetings/demo.txt",
        summary_path: "C:/meetings/demo_summary.txt",
        overrides: { provider: "ollama", mode: "medium" },
      },
      (e) => events.push(e),
    );

    expect(result.status).toBe("success");
    expect(result.transcript_text).toBeTruthy();
    expect(result.summary_text).toBeTruthy();
    expect(events.some((e) => e.step === "transcribe" && e.status === "success")).toBe(true);

    const history = await bridge.getHistory();
    expect(history.length).toBeGreaterThan(0);
    expect(history[0].status).toBe("success");
    // Re-opening the saved transcript returns its content.
    const reopened = await bridge.readText(result.transcript_path);
    expect(reopened.exists).toBe(true);
  });

  it("returns partial_success when an external provider has no key", async () => {
    const bridge = await getBridge();
    const result = await bridge.runRecap(
      {
        audio_path: "C:/meetings/demo2.mp3",
        overrides: { provider: "openai" },
      },
      () => {},
    );
    expect(result.status).toBe("partial_success");
    expect(result.transcript_path).toBeTruthy();
    expect(result.summary_path).toBeNull();
  });
});
