"""Local, opt-in real-transcript benchmark; writes private results under data/.

Example (from repository root):
  .venv/Scripts/python.exe scripts/benchmark_summaries.py --context 4096
No models are downloaded. No transcripts are sent to external services.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx  # noqa: E402

from formatters import to_plain  # noqa: E402
from prompts import JSON_PROMPTS, PROMPTS  # noqa: E402
from providers.llm import LLMSummarizer  # noqa: E402
from transcript import Transcript  # noqa: E402
from utils import write_text_atomic  # noqa: E402
from workflows import _generate_summary  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--mode", choices=sorted(PROMPTS["ru"]), default="medium")
    parser.add_argument("--output-dir", type=Path, default=Path("data/summary-benchmark"))
    args = parser.parse_args()
    files = args.files or sorted(Path("data/transcripts").glob("*.txt"))
    if not files:
        parser.error("No transcripts found")
    logging.basicConfig(level=logging.INFO)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        text = Transcript.from_file(path).to_text()
        summarizer = LLMSummarizer(
            model=args.model,
            base_url="http://localhost:11434/v1",
            ollama=True,
            num_ctx=args.context,
            max_chars=42000,
            timeout=120,
            max_retries=0,
            prompt_template=PROMPTS["ru"][args.mode],
            json_prompt=JSON_PROMPTS["ru"].get(args.mode),
        )
        summarizer.set_callbacks(lambda: False, lambda msg: print(msg, flush=True))
        measurements: list[dict] = []
        stop = threading.Event()

        def sample_memory() -> None:
            with httpx.Client(timeout=3) as client:
                while not stop.is_set():
                    try:
                        for model in client.get("http://localhost:11434/api/ps").json().get("models", []):
                            if model["name"] == args.model and model.get("context_length") == args.context:
                                measurements.append(model)
                    except (httpx.HTTPError, ValueError):
                        pass  # missing measurement is not a failed generation
                    stop.wait(2)

        sampler = threading.Thread(target=sample_memory, daemon=True)
        sampler.start()
        started = time.monotonic()
        record: dict = {
            "file": path.name,
            "model": args.model,
            "context": args.context,
            "mode": args.mode,
            "input_chars": len(text),
            "initial_chunks": len(summarizer._split_into_chunks(text)),
        }
        name = f"{path.stem}-{args.model.replace(':', '_').replace('/', '_')}-{args.context}-{args.mode}"
        try:
            summary = _generate_summary(summarizer, text, args.mode)
            rendered = to_plain(summary)
            write_text_atomic(args.output_dir / f"{name}.txt", rendered)
            record.update(success=True, output_chars=len(rendered))
        except Exception as exc:  # benchmark boundary: record failures and continue the corpus
            record.update(success=False, error=type(exc).__name__, message=str(exc))
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
            stop.set()
            sampler.join(timeout=5)
        record["peak_model_vram_bytes"] = max((m.get("size_vram", 0) for m in measurements), default=None)
        record["observed_contexts"] = sorted({m.get("context_length", 0) for m in measurements})
        write_text_atomic(args.output_dir / f"{name}.json", json.dumps(record, ensure_ascii=False, indent=2))
        print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
