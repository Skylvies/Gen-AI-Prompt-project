"""Request and response shapes (Pydantic). FastAPI validates input against these automatically."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .prompt_generator import TECHNIQUES
from .scoring import normalize_weights


class PreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(min_length=3, max_length=2000)
    techniques: list[str] = Field(default_factory=lambda: list(TECHNIQUES), min_length=1)
    target_words: int = Field(120, ge=10, le=1000)

    @field_validator("techniques")
    @classmethod
    def _valid_techniques(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Techniques must not repeat.")
        unknown = [t for t in value if t not in TECHNIQUES]
        if unknown:
            raise ValueError(f"Unknown technique(s): {', '.join(unknown)}. Valid: {', '.join(TECHNIQUES)}")
        return value


class ExperimentRequest(PreviewRequest):
    techniques: list[str] = Field(default_factory=lambda: list(TECHNIQUES), min_length=2)
    reference_answer: str | None = Field(None, max_length=2000)
    mode: Literal["demo", "real"] = "demo"
    weights: dict[str, float] | None = None

    @field_validator("weights")
    @classmethod
    def _valid_weights(cls, value):
        if value is not None:
            normalize_weights(value)  # raises ValueError with a clear message if invalid
        return value


class RescoreRequest(BaseModel):
    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def _valid_weights(cls, value):
        normalize_weights(value)
        return value


class VariantOut(BaseModel):
    id: int
    technique: str
    label: str
    prompt: str
    response: str
    error: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tokens_estimated: bool
    latency_ms: float
    cost_usd: float
    relevance: float
    validity: float
    reliability: float
    conciseness: float
    tokens_score: float
    cost_score: float
    latency_score: float
    overall_score: float
    rank: int | None
    is_recommended: bool
    details: dict


class ExperimentOut(BaseModel):
    id: int
    created_at: str
    task: str
    reference_answer: str | None
    mode: str
    simulated: bool
    provider: str
    model: str
    target_words: int
    weights: dict[str, float]
    price_input_per_mtok: float
    price_output_per_mtok: float
    recommended_technique: str | None
    recommendation_reason: str | None
    results: list[VariantOut]


class ExperimentSummary(BaseModel):
    id: int
    created_at: str
    task: str
    mode: str
    model: str
    variant_count: int
    recommended_technique: str | None
    best_score: float | None
