"""Provider factory: pick the LLM backend by mode (demo / real) and LLM_PROVIDER."""
from ..config import Settings
from .base import LLMProvider, LLMResponse
from .mock import MockProvider

__all__ = ["LLMProvider", "LLMResponse", "get_provider"]


def get_provider(mode: str, settings: Settings) -> LLMProvider:
    if mode == "demo":
        return MockProvider()
    if mode != "real":
        raise ValueError(f"Unknown mode: {mode}")

    problem = settings.real_mode_problem
    if problem:
        raise ValueError(f"Real mode is not configured: {problem}.")

    if settings.llm_provider == "anthropic":
        try:
            from .anthropic_provider import AnthropicProvider  # optional dependency
        except ImportError:
            raise ValueError("The anthropic provider needs: pip install -r backend/requirements-anthropic.txt") from None
        return AnthropicProvider(settings.llm_api_key, settings.llm_model, settings.llm_effort)

    from .openai_compatible import OpenAICompatibleProvider

    return OpenAICompatibleProvider(
        name=settings.llm_provider, base_url=settings.llm_base_url, api_key=settings.llm_api_key,
        model=settings.llm_model, temperature=settings.llm_temperature,
    )
