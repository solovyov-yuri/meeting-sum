from __future__ import annotations

import logging

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

    def _call_llm(self, messages: list[dict[str, str]], client, console) -> str:
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
                with client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    extra_body=extra or None,
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

    def _chunked_summarize(self, transcript_text: str, client, console, _depth: int = 0) -> str:
        chunks = self._split_into_chunks(transcript_text)
        logger.info("Transcript split into %d chunks for summarization.", len(chunks))

        chunk_summaries: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            logger.info("Summarizing chunk %d/%d…", i, len(chunks))
            messages = self._build_messages(chunk, prompt_template=self._chunk_prompt)
            summary = self._call_llm(messages, client, console)
            chunk_summaries.append(f"[Часть {i}]\n{summary}")

        merged = "\n\n".join(chunk_summaries)
        logger.info("Merging %d chunk summaries into final summary.", len(chunks))

        if len(merged) > self._max_chars:
            if _depth < self._MAX_MERGE_DEPTH:
                logger.warning(
                    "Merged summaries (%d chars) exceed max_chars; applying another round of chunking.",
                    len(merged),
                )
                return self._chunked_summarize(merged, client, console, _depth + 1)
            logger.warning(
                "Merged summaries still exceed max_chars after %d rounds; truncating for final merge.",
                _depth,
            )
            merged = _truncate(merged, self._max_chars)

        messages = self._build_messages(merged)
        return self._call_llm(messages, client, console)

    def summarize(self, transcript_text: str) -> str:
        import openai  # noqa: PLC0415 — deferred to keep CLI startup fast
        from rich.console import Console  # noqa: PLC0415

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
            return self._chunked_summarize(transcript_text, client, console)

        messages = self._build_messages(transcript_text)
        return self._call_llm(messages, client, console)
