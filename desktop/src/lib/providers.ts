// Mirror of workflows.is_external_provider (src/workflows.py) for inline UI hints.

/** Default base URL per provider, mirroring config.PROVIDER_PRESETS. openai has no preset
 *  (None in Python → the SDK's api.openai.com); shown here so the field can hint the default. */
export const PROVIDER_BASE_URLS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  xai: "https://api.x.ai/v1",
  ollama: "http://localhost:11434/v1",
  "lm-studio": "http://localhost:1234/v1",
  vllm: "http://localhost:8000/v1",
};

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export function isExternalProvider(baseUrl: string | null, provider: string): boolean {
  if (provider === "openai" && !baseUrl) return true;
  if (!baseUrl) return false;
  try {
    const host = new URL(baseUrl).hostname;
    return !LOCAL_HOSTS.has(host);
  } catch {
    return false;
  }
}
