from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from prompts import CHUNK_PROMPTS, PROMPTS, SUMMARY_PROMPT_MEDIUM_RU  # noqa: F401 — re-exported for consumers
from summary_schema import SUMMARY_JSON_SCHEMA

logger = logging.getLogger(__name__)

# The strongest structured-output request we can make, and the weaker one every OpenAI-compatible
# server understands. ``_final_call`` walks down this ladder; below it, the caller's text path.
_SCHEMA_FORMAT: dict = {
    "type": "json_schema",
    "json_schema": {"name": "meeting_summary", "schema": SUMMARY_JSON_SCHEMA},
}
_JSON_OBJECT_FORMAT: dict = {"type": "json_object"}


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
        ollama: bool = False,
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
        self._ollama = ollama
        self._context = num_ctx or 8192
        self._output_tokens = min(1536, self._context // 4)
        self._cancelled: Callable[[], bool] = lambda: False
        self._progress: Callable[[str], None] = lambda message: None
        self._prepared: tuple[str, str] | None = None
        self._chunk_cache: dict[str, str] = {}
        if ollama:
            from prompts import LOCAL_CHUNK_PROMPT_RU  # noqa: PLC0415

            self._chunk_prompt = (self._chunk_prompt[0], LOCAL_CHUNK_PROMPT_RU)

    def set_callbacks(self, cancelled: Callable[[], bool], progress: Callable[[str], None]) -> None:
        self._cancelled = cancelled
        self._progress = progress

    def _check_cancelled(self) -> None:
        from providers.ollama_chat import SummarizationCancelled  # noqa: PLC0415

        if self._cancelled():
            raise SummarizationCancelled()

    def _input_budget(self) -> int:
        from providers.ollama_chat import estimate_tokens  # noqa: PLC0415

        templates = [self._prompt_template, self._chunk_prompt]
        if self._json_prompt:
            templates.append(self._json_prompt)
        overhead = max(
            sum(estimate_tokens(m["content"]) for m in self._build_messages("", template)) for template in templates
        )
        schema = max(128, estimate_tokens(json.dumps(SUMMARY_JSON_SCHEMA)) if self._json_prompt else 0)
        budget = self._context - self._output_tokens - overhead - schema - 256
        if budget < 256:
            raise ValueError("Контекст Ollama слишком мал для инструкций и ответа; установите num_ctx не менее 4096.")
        return budget

    def _fits(self, text: str) -> bool:
        from providers.ollama_chat import estimate_tokens  # noqa: PLC0415

        return len(text) <= self._max_chars and (not self._ollama or estimate_tokens(text) <= self._input_budget())

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
        if self._ollama:
            system += (
                " Не превращай примеры, варианты и отсутствие планов в принятые решения или отмены."
                " Сохраняй условия и неопределённость. Не придумывай названия, исполнителей и сроки."
            )
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
            self._check_cancelled()
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
                if self._ollama:
                    from providers.ollama_chat import chat  # noqa: PLC0415

                    return chat(
                        client,
                        model=self._model,
                        messages=messages,
                        num_ctx=self._context,
                        num_predict=self._output_tokens,
                        response_format=response_format,
                        console=console,
                        cancelled=self._cancelled,
                    )
                chunks: list[str] = []
                # Known limitation: tokens printed to stderr during a failed attempt
                # remain visible; on retry they are printed again. The returned string
                # is always complete and correct — only the interactive display is affected.
                extra: dict = {}
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
                        self._check_cancelled()
                        if chunk.choices and (delta := chunk.choices[0].delta.content):
                            console.print(delta, end="", highlight=False, markup=False)
                            chunks.append(delta)
                console.print()
                return "".join(chunks)
            except _RETRYABLE as exc:
                self._check_cancelled()
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise
                last_exc = exc

        raise last_exc  # type: ignore[misc]

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text at line boundaries so each chunk fits within max_chars.

        Lines longer than max_chars are split at character boundaries so no
        chunk ever exceeds the limit, regardless of line structure.
        """
        if self._ollama:
            # Keep complete utterances where possible; oversized lines are split
            # without dropping characters. The same budget applies to merge passes.
            chunks: list[str] = []
            pending = ""
            for line in text.splitlines(keepends=True):
                while line:
                    if self._fits(pending + line):
                        pending += line
                        break
                    if pending:
                        chunks.append(pending)
                        pending = ""
                    if self._fits(line):
                        pending = line
                        break
                    lo, hi = 1, len(line)
                    while lo < hi:
                        mid = (lo + hi + 1) // 2
                        if self._fits(line[:mid]):
                            lo = mid
                        else:
                            hi = mid - 1
                    # Prefer a word boundary when a single ASR utterance is oversized.
                    boundary = line.rfind(" ", 0, lo)
                    if boundary >= lo // 2:
                        lo = boundary + 1
                    chunks.append(line[:lo])
                    line = line[lo:]
            if pending:
                chunks.append(pending)
            return chunks
        chunks = []
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
        if self._ollama:
            # The model only selects evidence; generated paraphrases never enter
            # subsequent reduction levels. Each retained excerpt is source text.
            excerpts: list[str] = []
            pending = ""
            for line in chunk.splitlines(keepends=True):
                if pending and len(pending) + len(line) > 500:
                    excerpts.append(pending)
                    pending = ""
                # A long unbroken line still needs selectable, bounded excerpts.
                while len(line) > 500:
                    excerpts.append(line[:500])
                    line = line[500:]
                pending += line
            if pending:
                excerpts.append(pending)
            if len(excerpts) <= 1:
                return chunk
            limit = max(1, len(excerpts) // 3)
            numbered = "\n".join(f"[{n}] {excerpt}" for n, excerpt in enumerate(excerpts))
            messages = self._build_messages(numbered, prompt_template=self._chunk_prompt)
            key = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()
            if key not in self._chunk_cache:
                schema = {
                    "type": "object",
                    "properties": {
                        "keep": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": limit,
                            "uniqueItems": True,
                            "items": {"type": "integer", "minimum": 0, "maximum": len(excerpts) - 1},
                        }
                    },
                    "required": ["keep"],
                    "additionalProperties": False,
                }
                raw = self._call_llm(
                    messages,
                    client,
                    console,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "evidence", "schema": schema},
                    },
                )
                selection = json.loads(raw)
                indices = selection.get("keep") if isinstance(selection, dict) else None
                if (
                    not isinstance(indices, list)
                    or not 1 <= len(indices) <= limit
                    or any(type(n) is not int or not 0 <= n < len(excerpts) for n in indices)
                    or len(set(indices)) != len(indices)
                ):
                    raise ValueError("Модель вернула недопустимые номера исходных отрывков.")
                self._chunk_cache[key] = "\n".join(excerpts[n].strip() for n in sorted(indices))
            return self._chunk_cache[key]
        messages = self._build_messages(chunk, prompt_template=self._chunk_prompt)
        return f"[Часть {i}]\n{self._call_llm(messages, client, console)}"

    def _final_call(self, text: str, client, console, structured: bool) -> str:
        """The final (whole-transcript or merged) summarization pass, optionally as JSON.

        Structured output degrades one step at a time: ask for the summary schema, and if the
        server refuses that ``response_format`` (older Ollama/lm-studio/vllm builds answer 400/422),
        ask again for a plain JSON object — the prompt alone then carries the shape. A refusal of
        *that* propagates, which is what puts the caller on its text-prompt fallback.
        """
        import httpx  # noqa: PLC0415
        import openai  # noqa: PLC0415 — deferred to keep CLI startup fast

        template = self._json_prompt if structured else None
        messages = self._build_messages(text, prompt_template=template)
        self._progress("Оформление итогового саммари…")
        if not structured:
            return self._call_llm(messages, client, console)
        try:
            return self._call_llm(messages, client, console, response_format=_SCHEMA_FORMAT)
        except (openai.BadRequestError, openai.UnprocessableEntityError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in (400, 422):
                raise
            logger.warning(
                "Provider rejected response_format=json_schema (%s); retrying with json_object.",
                exc,
            )
        return self._call_llm(messages, client, console, response_format=_JSON_OBJECT_FORMAT)

    def _chunked_summarize(
        self, transcript_text: str, client, console, structured: bool = False, _depth: int = 0
    ) -> str:
        chunks = self._split_into_chunks(transcript_text)
        logger.info("Transcript split into %d chunks for summarization.", len(chunks))

        indexed = list(enumerate(chunks, 1))
        if self._ollama:
            chunk_summaries = []
            for ic in indexed:
                self._check_cancelled()
                self._progress(f"Обработка фрагмента {ic[0]} из {len(chunks)} (уровень {_depth + 1})…")
                chunk_summaries.append(self._summarize_one_chunk(ic, client, console))
            merged = "\n\n".join(chunk_summaries)
            if not self._fits(merged):
                if _depth >= self._MAX_MERGE_DEPTH or len(merged.encode()) >= len(transcript_text.encode()):
                    raise ValueError(
                        "Модель не смогла сократить промежуточные результаты до размера контекста. Хвост не обрезан."
                    )
                return self._chunked_summarize(merged, client, console, structured, _depth + 1)
            self._prepared = (hashlib.sha256(self._source_text.encode()).hexdigest(), merged)
            return self._final_call(merged, client, console, structured)
        if self._is_local() or len(chunks) < 2:
            # Sequential: local servers are resource-starved by concurrency.
            chunk_summaries = [self._summarize_one_chunk(ic, client, console) for ic in indexed]
        else:
            # External providers tolerate concurrency; executor.map preserves input order.
            with ThreadPoolExecutor(max_workers=self._MAX_CHUNK_WORKERS) as executor:
                chunk_summaries = list(executor.map(lambda ic: self._summarize_one_chunk(ic, client, console), indexed))

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

        console = Console(stderr=True)

        if structured and self._json_prompt is None:
            raise ValueError("structured=True requires a json_prompt")

        if self._ollama:
            import httpx  # noqa: PLC0415

            self._check_cancelled()
            self._input_budget()  # validate before contacting the server
            source_key = hashlib.sha256(transcript_text.encode()).hexdigest()
            if getattr(self, "_source_text", None) != transcript_text:
                self._prepared = None
                self._chunk_cache.clear()
            self._source_text = transcript_text
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            base = (self._base_url or "http://localhost:11434/v1").rstrip("/").removesuffix("/v1")
            with httpx.Client(base_url=base + "/", headers=headers, timeout=self._timeout) as native_client:
                if self._prepared and self._prepared[0] == source_key:
                    return self._final_call(self._prepared[1], native_client, console, structured)
                if not self._fits(transcript_text):
                    if self._chunking_mode == "truncate":
                        logger.warning("Transcript explicitly truncated to Ollama input budget.")
                        transcript_text = self._split_into_chunks(transcript_text)[0]
                    else:
                        return self._chunked_summarize(transcript_text, native_client, console, structured)
                return self._final_call(transcript_text, native_client, console, structured)

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
