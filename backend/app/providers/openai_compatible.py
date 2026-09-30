"""Real-mode provider for any OpenAI-compatible chat API: Groq, OpenRouter, Ollama, LM Studio, vLLM, ...

It is one HTTP POST to  <base_url>/chat/completions  with the key in an Authorization header.
The key comes from the LLM_API_KEY environment variable on the server (see config.py). It is never
logged, stored in the database or sent to the browser, and error messages never contain it.
"""
import re
import time

import httpx

from ..text_utils import estimate_tokens
from .base import LLMProvider, LLMResponse

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)  # some open models print their reasoning inline
_FINISH_REASONS = {"stop": "stop", "length": "length", "content_filter": "refusal"}
_RETRY_STATUSES = {429, 500, 502, 503, 504}  # rate limit or temporary server trouble
_MAX_WAIT_SECONDS = 20


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, name: str, base_url: str, api_key: str | None, model: str, temperature: float | None = 0.3,
                 max_retries: int = 2, timeout: float = 90.0, client: httpx.Client | None = None, sleep=time.sleep):
        self.name = name
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.temperature = temperature
        self.max_retries = max_retries
        self.headers = {"Content-Type": "application/json"}
        if api_key:  # local servers such as Ollama need no key
            self.headers["Authorization"] = f"Bearer {api_key}"
        # `client` and `sleep` can be injected in tests, so no network call or waiting is needed.
        self.client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep

    def generate(self, prompt: str, max_tokens: int) -> LLMResponse:
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
        if self.temperature is not None:
            payload["temperature"] = self.temperature  # same low temperature for every variant = fairer comparison

        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()  # latency covers only the attempt that succeeds, not the waiting
            try:
                response = self.client.post(self.url, json=payload, headers=self.headers)
            except httpx.TimeoutException:
                raise RuntimeError("The API request timed out.") from None
            except httpx.HTTPError:
                raise RuntimeError("Could not reach the API (network problem, or wrong LLM_BASE_URL).") from None
            latency_ms = (time.perf_counter() - started) * 1000
            if response.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                self._sleep(_retry_delay(response, attempt))
                continue
            break

        if response.status_code >= 400:
            raise RuntimeError(_error_message(response))
        try:
            data = response.json()
            choice = data["choices"][0]
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("The API returned an unexpected response.") from None

        message = choice.get("message") or {}
        text = _THINK_BLOCK.sub("", message.get("content") or "").strip()
        usage = data.get("usage") or {}
        input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        estimated = input_tokens is None or output_tokens is None  # some local servers omit usage
        if estimated:
            input_tokens, output_tokens = estimate_tokens(prompt), estimate_tokens(text)
        finish = choice.get("finish_reason") or "stop"
        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,  # for "reasoning" models this includes hidden reasoning tokens
            latency_ms=latency_ms,
            finish_reason=_FINISH_REASONS.get(finish, finish),
            tokens_estimated=estimated,
        )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0**attempt  # 1 s, then 2 s
    return min(max(wait, 0.0), _MAX_WAIT_SECONDS)


def _error_message(response: httpx.Response) -> str:
    """A short, safe message. Authentication errors never echo anything the server sent back."""
    status = response.status_code
    if status in (401, 403):
        return "Authentication failed - check LLM_API_KEY (and that it belongs to LLM_PROVIDER)."
    if status == 429:
        return "Rate limit reached (free tiers are strict). Wait a minute, pick fewer techniques, or lower MAX_WORKERS."
    detail = ""
    try:
        error = response.json().get("error")
        detail = error.get("message", "") if isinstance(error, dict) else str(error or "")
    except (ValueError, AttributeError):
        pass
    return f"API error (HTTP {status})" + (f": {detail[:200]}" if detail else ".")
