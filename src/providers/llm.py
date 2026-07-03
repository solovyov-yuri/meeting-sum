from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from prompts import CHUNK_PROMPTS, PROMPTS, SUMMARY_PROMPT_MEDIUM_RU  # noqa: F401 — re-exported for consumers

logger = logging.getLogger(__name__)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n", 0, max_chars)
    return text[: cut if cut != -1 else max_chars]


class LLMSummarizer:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        prompt_template: str | tuple[str, str] = PROMPTS["ru"]["medium"],
        chunk_prompt: tuple[str, str] | None = None,
        max_chars: int = 60_000,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_backoff: float = 2.0,
        chunking_mode: str = "chunk",
        num_ctx: int | None = None,
        json_prompt: tuple[str, str] | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._prompt_template = prompt_template
        self._chunk_prompt = chunk_prompt if chunk_prompt is not None else CHUNK_PROMPTS["ru"]
        self._max_chars = max_chars
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._chunking_mode = chunking_mode
        self._num_ctx = num_ctx
        self._json_prompt = json_prompt

    @property
    def supports_structured(self) -> bool:
        """True when a JSON prompt is configured, so ``summarize(structured=True)`` is available."""
        return self._json_prompt is not None

    def _build_messages(
        self,
        transcript_text: str,
        prompt_template: str | tuple[str, str] | None = None,
    ) -> list[dict[str, str]]:
        template = prompt_template if prompt_template is not None else self._prompt_template
        if isinstance(template, str):
            from prompts import SYSTEM_PROMPT_RU  # noqa: PLC0415

            system, user_template = SYSTEM_PROMPT_RU, template
        else:
            system, user_template = template
        user = user_template.replace("{transcript}", transcript_text)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _call_llm(self, messages: list[dict[str, str]], client, console, response_format: dict | None = None) -> str:
        """Make one streaming LLM call with retry. Returns the full response string."""
        import time  # noqa: PLC0415

        import httpx  # noqa: PLC0415
        import openai  # noqa: PLC0415

        # httpx.HTTPError covers network errors raised while iterating the SSE stream,
        # which some openai-python versions surface as httpx.ReadError / httpx.RemoteProtocolError
        # instead of wrapping them in openai.APIConnectionError.
        _RETRYABLE = (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
            httpx.HTTPError,
        )
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                logger.warning(
                    "LLM request failed, retrying (%d/%d): %s",
                    attempt,
                    self._max_retries,
                    last_exc,
                )
                time.sleep(self._retry_backoff)
            try:
                console.print(f"[bold cyan]Generating summary ({self._model})…[/bold cyan]")
                chunks: list[str] = []
                # Known limitation: tokens printed to stderr during a failed attempt
                # remain visible; on retry they are printed again. The returned string
                # is always complete and correct — only the interactive display is affected.
                extra: dict = {}
                if self._num_ctx is not None:
                    extra["options"] = {"num_ctx": self._num_ctx}
                kwargs: dict = {}
                if response_format is not None:
                    kwargs["response_format"] = response_format
                with client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    extra_body=extra or None,
                    **kwargs,
                ) as stream:
                    for chunk in stream:
                        if chunk.choices and (delta := chunk.choices[0].delta.content):
                            console.print(delta, end="", highlight=False, markup=False)
                            chunks.append(delta)
                console.print()
                return "".join(chunks)
            except _RETRYABLE as exc:
                last_exc = exc

        raise last_exc  # type: ignore[misc]

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text at line boundaries so each chunk fits within max_chars.

        Lines longer than max_chars are split at character boundaries so no
        chunk ever exceeds the limit, regardless of line structure.
        """
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in text.splitlines():
            if len(line) > self._max_chars:
                # Flush accumulated lines before handling the oversized line.
                if current:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                for start in range(0, len(line), self._max_chars):
                    chunks.append(line[start : start + self._max_chars])
                continue
            line_len = len(line) + 1  # +1 for the newline
            if current_len + line_len > self._max_chars and current:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            chunks.append("\n".join(current))
        return chunks

    _MAX_MERGE_DEPTH = 3
    _MAX_CHUNK_WORKERS = 3

    def _is_local(self) -> bool:
        """True when the endpoint targets a local host (Ollama/lm-studio/vllm).

        Local servers are resource-starved by concurrent requests, so per-chunk
        summarization stays sequential for them. `None` (OpenAI default) is external.
        """
        if self._base_url is None:
            return False
        return urlparse(self._base_url).hostname in {"localhost", "127.0.0.1", "::1"}

    def _summarize_one_chunk(self, indexed_chunk: tuple[int, str], client, console) -> str:
        i, chunk = indexed_chunk
        logger.info("Summarizing chunk %d…", i)
        messages = self._build_messages(chunk, prompt_template=self._chunk_prompt)
        return f"[Часть {i}]\n{self._call_llm(messages, client, console)}"

    def _final_call(self, text: str, client, console, structured: bool) -> str:
        """The final (whole-transcript or merged) summarization pass, optionally as JSON."""
        template = self._json_prompt if structured else None
        response_format = {"type": "json_object"} if structured else None
        messages = self._build_messages(text, prompt_template=template)
        return self._call_llm(messages, client, console, response_format=response_format)

    def _chunked_summarize(self, transcript_text: str, client, console, structured: bool = False, _depth: int = 0) -> str:
        chunks = self._split_into_chunks(transcript_text)
        logger.info("Transcript split into %d chunks for summarization.", len(chunks))

        indexed = list(enumerate(chunks, 1))
        if self._is_local() or len(chunks) < 2:
            # Sequential: local servers are resource-starved by concurrency.
            chunk_summaries = [self._summarize_one_chunk(ic, client, console) for ic in indexed]
        else:
            # External providers tolerate concurrency; executor.map preserves input order.
            with ThreadPoolExecutor(max_workers=self._MAX_CHUNK_WORKERS) as executor:
                chunk_summaries = list(
                    executor.map(lambda ic: self._summarize_one_chunk(ic, client, console), indexed)
                )

        merged = "\n\n".join(chunk_summaries)
        logger.info("Merging %d chunk summaries into final summary.", len(chunks))

        if len(merged) > self._max_chars:
            if _depth < self._MAX_MERGE_DEPTH:
                logger.warning(
                    "Merged summaries (%d chars) exceed max_chars; applying another round of chunking.",
                    len(merged),
                )
                return self._chunked_summarize(merged, client, console, structured, _depth + 1)
            logger.warning(
                "Merged summaries still exceed max_chars after %d rounds; truncating for final merge.",
                _depth,
            )
            merged = _truncate(merged, self._max_chars)

        # Chunks are summarized as text; only the final merge is asked for JSON (per design).
        return self._final_call(merged, client, console, structured)

    def summarize(self, transcript_text: str, structured: bool = False) -> str:
        """Summarize the transcript. With ``structured=True`` the final pass returns JSON
        (requires ``supports_structured``); otherwise it returns the Markdown-ish text summary."""
        import openai  # noqa: PLC0415 — deferred to keep CLI startup fast
        from rich.console import Console  # noqa: PLC0415

        if structured and self._json_prompt is None:
            raise ValueError("structured=True requires a json_prompt")

        if len(transcript_text) > self._max_chars and self._chunking_mode == "truncate":
            logger.warning(
                "Transcript truncated from %d to %d chars to fit context window.",
                len(transcript_text),
                self._max_chars,
            )
            transcript_text = _truncate(transcript_text, self._max_chars)

        logger.info("Calling %s (model: %s)…", self._base_url or "openai", self._model)
        # max_retries=0: disable SDK-level retries — we manage retry logic ourselves.
        client = openai.OpenAI(
            api_key=self._api_key or ("local" if self._base_url else None),
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=0,
        )
        console = Console(stderr=True)

        if len(transcript_text) > self._max_chars:
            return self._chunked_summarize(transcript_text, client, console, structured=structured)

        return self._final_call(transcript_text, client, console, structured)
