"""The provider abstraction: every LLM backend implements `generate()` and nothing else.

To add a new vendor (OpenAI, Gemini, a local model...) write one class with this method
and register it in `providers/__init__.py`. No other file needs to change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float  # measured wall-clock time of the call (simulated in demo mode)
    finish_reason: str = "stop"  # "stop" | "length" | "refusal" | "error"
    tokens_estimated: bool = False  # True when token counts are estimates, not API usage
    error: str | None = None


class LLMProvider(ABC):
    name: str
    model: str
    simulated: bool = False  # True for the mock provider

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int) -> LLMResponse:
        """Send one prompt and return the response. May raise; the caller handles errors."""
