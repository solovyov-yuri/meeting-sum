import { describe, expect, it } from "vitest";
import { isExternalProvider } from "./providers";

describe("isExternalProvider", () => {
  it("treats openai with no base_url as external", () => {
    expect(isExternalProvider(null, "openai")).toBe(true);
  });

  it("treats localhost as internal", () => {
    expect(isExternalProvider("http://localhost:11434/v1", "ollama")).toBe(false);
  });

  it("treats a remote host as external", () => {
    expect(isExternalProvider("https://api.x.ai/v1", "xai")).toBe(true);
  });

  it("treats a local provider with no base_url as internal", () => {
    expect(isExternalProvider(null, "ollama")).toBe(false);
  });
});
