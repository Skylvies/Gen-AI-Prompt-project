"""The experiment pipeline: generate prompts -> call the LLM -> evaluate -> score -> save."""
import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .evaluator import evaluate_response
from .models import Experiment, VariantResult
from .prompt_generator import generate_variants
from .providers.base import LLMProvider, LLMResponse
from .scoring import explain_recommendation, normalize_weights, score_variants


def _call_llm(provider: LLMProvider, prompt: str, max_tokens: int) -> LLMResponse:
    """One failing variant must not break the whole experiment, so errors become a result."""
    try:
        return provider.generate(prompt, max_tokens)
    except Exception as exc:  # noqa: BLE001 - the message is already sanitised by the provider
        return LLMResponse(text="", input_tokens=0, output_tokens=0, latency_ms=0.0,
                           finish_reason="error", error=str(exc) or exc.__class__.__name__)


def _cost_usd(settings: Settings, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * settings.price_input_per_mtok + output_tokens * settings.price_output_per_mtok) / 1_000_000


def _row_from_db(result: VariantResult) -> dict:
    """The fields scoring.py needs, read back from the database (used when re-scoring)."""
    return {
        "relevance": result.relevance, "validity": result.validity, "reliability": result.reliability,
        "conciseness": result.conciseness, "total_tokens": result.total_tokens, "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms, "failed": result.error is not None,
    }


def _apply_scores(experiment: Experiment, rows: list[dict]) -> None:
    for result, row in zip(experiment.results, rows):
        result.tokens_score, result.cost_score = row["tokens_score"], row["cost_score"]
        result.latency_score, result.overall_score = row["latency_score"], row["overall_score"]
        result.rank, result.is_recommended = row["rank"], row["is_recommended"]
    experiment.recommendation_reason = explain_recommendation(rows)


def run_experiment(
    db: Session, provider: LLMProvider, settings: Settings, *, task: str, reference_answer: str | None,
    techniques: list[str], weights: dict[str, float] | None, target_words: int, mode: str,
) -> Experiment:
    variants = generate_variants(task, techniques, target_words)

    # The LLM calls are slow and independent, so run them in parallel threads.
    with ThreadPoolExecutor(max_workers=max(1, settings.max_workers)) as pool:
        responses = list(pool.map(lambda v: _call_llm(provider, v.prompt, settings.max_output_tokens), variants))

    normalized = normalize_weights(weights)
    experiment = Experiment(
        task=task, reference_answer=reference_answer, mode=mode, provider=provider.name, model=provider.model,
        target_words=target_words, weights_json=json.dumps(normalized),
        price_input_per_mtok=settings.price_input_per_mtok, price_output_per_mtok=settings.price_output_per_mtok,
    )

    rows = []
    for variant, response in zip(variants, responses):
        metrics = evaluate_response(response, variant, task, reference_answer, target_words)
        rows.append({
            **{k: metrics[k] for k in ("relevance", "validity", "reliability", "conciseness")},
            "total_tokens": response.input_tokens + response.output_tokens,
            "cost_usd": _cost_usd(settings, response.input_tokens, response.output_tokens),
            "latency_ms": response.latency_ms,
            "failed": response.error is not None,
        })
        experiment.results.append(VariantResult(
            technique=variant.technique, label=variant.label, prompt=variant.prompt,
            response=response.text, error=response.error,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
            total_tokens=rows[-1]["total_tokens"], tokens_estimated=response.tokens_estimated,
            latency_ms=response.latency_ms, cost_usd=rows[-1]["cost_usd"],
            relevance=metrics["relevance"], validity=metrics["validity"],
            reliability=metrics["reliability"], conciseness=metrics["conciseness"],
            details_json=json.dumps(metrics["details"]),
        ))

    score_variants(rows, normalized)
    _apply_scores(experiment, rows)
    db.add(experiment)
    db.commit()
    return experiment


def rescore_experiment(db: Session, experiment: Experiment, weights: dict[str, float]) -> Experiment:
    """Apply new weights to the stored metrics. No LLM call is made, so it is free and instant."""
    normalized = normalize_weights(weights)
    rows = [_row_from_db(r) for r in experiment.results]
    score_variants(rows, normalized)
    experiment.weights_json = json.dumps(normalized)
    _apply_scores(experiment, rows)
    db.commit()
    return experiment


def list_experiments(db: Session) -> list[Experiment]:
    return list(db.scalars(select(Experiment).order_by(Experiment.id.desc())))


# ---------- ORM -> plain dict (what the API returns) ----------

def variant_to_dict(r: VariantResult) -> dict:
    return {
        "id": r.id, "technique": r.technique, "label": r.label, "prompt": r.prompt, "response": r.response,
        "error": r.error, "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
        "total_tokens": r.total_tokens, "tokens_estimated": r.tokens_estimated,
        "latency_ms": round(r.latency_ms, 1), "cost_usd": r.cost_usd,
        "relevance": r.relevance, "validity": r.validity, "reliability": r.reliability,
        "conciseness": r.conciseness, "tokens_score": r.tokens_score, "cost_score": r.cost_score,
        "latency_score": r.latency_score, "overall_score": r.overall_score, "rank": r.rank,
        "is_recommended": r.is_recommended, "details": json.loads(r.details_json or "{}"),
    }


def experiment_to_dict(e: Experiment) -> dict:
    winner = next((r for r in e.results if r.is_recommended), None)
    return {
        "id": e.id, "created_at": e.created_at.isoformat() + "Z", "task": e.task,
        "reference_answer": e.reference_answer, "mode": e.mode, "simulated": e.mode == "demo",
        "provider": e.provider, "model": e.model, "target_words": e.target_words,
        "weights": json.loads(e.weights_json),
        "price_input_per_mtok": e.price_input_per_mtok, "price_output_per_mtok": e.price_output_per_mtok,
        "recommended_technique": winner.technique if winner else None,
        "recommendation_reason": e.recommendation_reason,
        "results": [variant_to_dict(r) for r in e.results],
    }


def experiment_summary(e: Experiment) -> dict:
    winner = next((r for r in e.results if r.is_recommended), None)
    return {
        "id": e.id, "created_at": e.created_at.isoformat() + "Z", "task": e.task, "mode": e.mode,
        "model": e.model, "variant_count": len(e.results),
        "recommended_technique": winner.technique if winner else None,
        "best_score": winner.overall_score if winner else None,
    }
