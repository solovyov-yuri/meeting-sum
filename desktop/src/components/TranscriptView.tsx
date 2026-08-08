function formatTimecode(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const s = (total % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

interface Row {
  time: string | null;
  text: string;
}

function parseTranscript(text: string): Row[] {
  const re = /^\[(\d+(?:\.\d+)?)s\s*->\s*(\d+(?:\.\d+)?)s\]\s*(.*)$/;
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = re.exec(line);
      if (m) return { time: formatTimecode(parseFloat(m[1])), text: m[3] };
      return { time: null, text: line };
    });
}

export function TranscriptView({ text }: { text: string }) {
  if (!text.trim()) {
    return <p className="px-1 py-4 text-base text-ink-muted">Транскрипт пуст.</p>;
  }
  const rows = parseTranscript(text);
  return (
    <div className="h-full overflow-y-auto p-3.5 scrollbar-thin" data-selectable>
      {rows.map((row, i) => (
        <div key={i} className="grid grid-cols-[64px_1fr] gap-3 border-b border-border/70 py-2.5 last:border-0">
          <time className="select-text font-mono text-sm tabular-nums text-ink-soft">{row.time ?? ""}</time>
          <p className="m-0 text-base leading-relaxed text-ink">{row.text}</p>
        </div>
      ))}
    </div>
  );
}
