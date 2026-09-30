"""Application settings.

Everything configurable comes from environment variables (or a local .env file,
which is git-ignored). Nothing secret is ever hard-coded in the source.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR.parent / ".env")  # <repo>/.env
load_dotenv(BACKEND_DIR / ".env")  # <repo>/backend/.env (optional)

# The seven metrics that make up the overall score.
METRIC_KEYS = ["relevance", "validity", "reliability", "conciseness", "tokens", "cost", "latency"]

# Default weights (they are re-normalised to sum to 1 before use).
DEFAULT_WEIGHTS = {
    "relevance": 0.30,
    "validity": 0.15,
    "reliability": 0.20,
    "conciseness": 0.10,
    "tokens": 0.10,
    "cost": 0.05,
    "latency": 0.10,
}


class Preset(NamedTuple):
    base_url: str
    model: str  # default model ("" = the user must choose one)
    needs_key: bool


# LLM_PROVIDER values. All except "anthropic" speak the OpenAI-compatible chat API,
# so they share one provider class (providers/openai_compatible.py).
PROVIDERS = {
    # Free tier, no credit card, open-weight Llama models: the default.
    "groq": Preset("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", True),
    # One key, many models. Choose a free one (ID ends in ":free") from https://openrouter.ai/models
    "openrouter": Preset("https://openrouter.ai/api/v1", "", True),
    # Models running on your own computer: completely free, no key. https://ollama.com
    "ollama": Preset("http://localhost:11434/v1", "llama3.2", False),
    # Any other OpenAI-compatible server (LM Studio, vLLM, Together, ...): set LLM_BASE_URL and LLM_MODEL.
    "custom": Preset("", "", True),
    # Optional: Claude through the official Anthropic SDK (pip install -r backend/requirements-anthropic.txt).
    "anthropic": Preset("", "claude-opus-5-5", True),
}

# USD per 1 million tokens: (input, output). Only used to turn token counts into a cost figure.
# Models not listed cost $0 (free tier / local) unless PRICE_INPUT_PER_MTOK and PRICE_OUTPUT_PER_MTOK are set.
# Sources: Anthropic price list (checked 2026-09-25) and the Groq models page (checked 2026-09-30).
# These are paid LIST prices; on a free tier you are not actually charged. Prices change - verify them.
MODEL_PRICES = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def _env(name: str, default: str = "") -> str:
    """Environment variable, treating a blank value (e.g. `NAME=` in .env) as 'not set'."""
    return os.getenv(name, "").strip() or default


def _float_env(name: str) -> float | None:
    raw = _env(name)
    return float(raw) if raw else None


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_provider: str
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str
    llm_temperature: float | None  # None = do not send (OpenAI-compatible providers only)
    llm_effort: str  # Anthropic provider only; "" = do not send
    max_output_tokens: int
    price_input_per_mtok: float
    price_output_per_mtok: float
    price_known: bool
    cors_origins: tuple[str, ...]
    real_mode_access_code: str | None
    max_workers: int

    @property
    def real_mode_problem(self) -> str | None:
        """Why Real mode cannot run (safe to show to users: never contains a secret), or None if it can."""
        preset = PROVIDERS.get(self.llm_provider)
        if preset is None:
            return f"LLM_PROVIDER '{self.llm_provider}' is not supported (use one of: {', '.join(PROVIDERS)})"
        if preset.needs_key and not self.llm_api_key:
            return "LLM_API_KEY is not set"
        if not self.llm_model:
            return "LLM_MODEL is not set"
        if self.llm_provider != "anthropic" and not self.llm_base_url:
            return "LLM_BASE_URL is not set"
        return None

    @property
    def real_mode_available(self) -> bool:
        return self.real_mode_problem is None

    @classmethod
    def from_env(cls) -> "Settings":
        provider = _env("LLM_PROVIDER", "groq").lower()
        preset = PROVIDERS.get(provider, Preset("", "", True))
        model = _env("LLM_MODEL", preset.model)

        # A Claude key is read ONLY when you explicitly choose the anthropic provider, so a key that
        # happens to sit in your shell environment can never be picked up by accident.
        api_key = _env("LLM_API_KEY") or (_env("ANTHROPIC_API_KEY") if provider == "anthropic" else "") or None

        price_in, price_out = MODEL_PRICES.get(model, (0.0, 0.0))
        price_known = model in MODEL_PRICES or provider == "ollama"  # local models are genuinely free
        override_in, override_out = _float_env("PRICE_INPUT_PER_MTOK"), _float_env("PRICE_OUTPUT_PER_MTOK")
        if override_in is not None and override_out is not None:
            price_in, price_out, price_known = override_in, override_out, True

        temperature = _float_env("LLM_TEMPERATURE") if os.getenv("LLM_TEMPERATURE") is not None else 0.3

        default_db = f"sqlite:///{(BACKEND_DIR / 'data' / 'prompt_lab.db').as_posix()}"
        origins = _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

        return cls(
            database_url=_env("DATABASE_URL", default_db),
            llm_provider=provider,
            llm_api_key=api_key,
            llm_model=model,
            llm_base_url=_env("LLM_BASE_URL", preset.base_url),
            llm_temperature=temperature,
            llm_effort=os.getenv("LLM_EFFORT", "low").strip(),  # blank is meaningful: send no effort
            max_output_tokens=int(_env("MAX_OUTPUT_TOKENS", "2048" if provider == "anthropic" else "1024")),
            price_input_per_mtok=price_in,
            price_output_per_mtok=price_out,
            price_known=price_known,
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            real_mode_access_code=_env("REAL_MODE_ACCESS_CODE") or None,
            max_workers=int(_env("MAX_WORKERS", "3")),
        )
