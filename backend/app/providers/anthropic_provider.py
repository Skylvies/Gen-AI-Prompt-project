"""OPTIONAL real-mode provider: calls Claude through the official Anthropic Python SDK.

Used only when LLM_PROVIDER=anthropic (needs `pip install -r backend/requirements-anthropic.txt`).
The key is passed in by the caller (see config.py); it is never logged, stored in the database
or sent to the browser.
"""
import time

import anthropic

from .base import LLMProvider, LLMResponse

# Map the API's stop_reason to the simple vocabulary used by the evaluator.
_FINISH_REASONS = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "refusal": "refusal"}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str = "low", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        # `client` can be injected in tests so no network call is made.
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=90.0, max_retries=2)

    def generate(self, prompt: str, max_tokens: int) -> LLMResponse:
        kwargs = {}
        if self.effort:
            # Lower effort = less hidden "thinking", so prompt comparisons are cheaper and less noisy.
            kwargs["output_config"] = {"effort": self.effort}

        started = time.perf_counter()
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
        except anthropic.AuthenticationError:
            raise RuntimeError("Authentication failed - check ANTHROPIC_API_KEY on the server.") from None
        except anthropic.RateLimitError:
            raise RuntimeError("Rate limit reached - wait a moment and try again.") from None
        except anthropic.APITimeoutError:
            raise RuntimeError("The API request timed out.") from None
        except anthropic.APIConnectionError:
            raise RuntimeError("Could not reach the Anthropic API (network problem).") from None
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error (HTTP {exc.status_code}).") from None
        latency_ms = (time.perf_counter() - started) * 1000

        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(
            text=text.strip(),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,  # includes hidden thinking tokens, which are billed
            latency_ms=latency_ms,
            finish_reason=_FINISH_REASONS.get(message.stop_reason, message.stop_reason or "stop"),
        )
