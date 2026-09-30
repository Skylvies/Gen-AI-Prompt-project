"""Step 4 of the pipeline: combine the metrics into one weighted score and rank the variants.

    overall = sum( weight_i * score_i )          (weights are scaled to add up to 1)

Relevance, validity, reliability and conciseness are already on a 0-100 scale.
Tokens, cost and latency are "lower is better" numbers with no natural scale, so they are
min-max normalised *within the experiment*: the cheapest variant gets 100, the most
expensive gets 0. (So those three scores only mean something when comparing variants.)
"""
from .config import DEFAULT_WEIGHTS, METRIC_KEYS


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Validate the weights and scale them so they add up to 1."""
    merged = dict(DEFAULT_WEIGHTS if weights is None else weights)
    unknown = set(merged) - set(METRIC_KEYS)
    if unknown:
        raise ValueError(f"Unknown weight(s): {', '.join(sorted(unknown))}")
    merged = {k: float(merged.get(k, 0.0)) for k in METRIC_KEYS}
    if any(w < 0 for w in merged.values()):
        raise ValueError("Weights must not be negative.")
    total = sum(merged.values())
    if total <= 0:
        raise ValueError("At least one weight must be greater than zero.")
    return {k: w / total for k, w in merged.items()}


def lower_is_better(values: list[float]) -> list[float]:
    """Min-max normalise so the smallest value scores 100 and the largest scores 0."""
    low, high = min(values), max(values)
    if high == low:
        return [100.0] * len(values)
    return [100 * (high - v) / (high - low) for v in values]


def score_variants(rows: list[dict], weights: dict[str, float] | None) -> dict[str, float]:
    """Fill in tokens/cost/latency scores, overall score and rank on each row (in place).

    Each row needs: relevance, validity, reliability, conciseness, total_tokens, cost_usd,
    latency_ms and failed (True if the API call failed). Returns the normalised weights.
    """
    w = normalize_weights(weights)
    ok = [r for r in rows if not r["failed"]]

    if ok:
        for key, source in (("tokens", "total_tokens"), ("cost", "cost_usd"), ("latency", "latency_ms")):
            for row, score in zip(ok, lower_is_better([r[source] for r in ok])):
                row[f"{key}_score"] = round(score, 1)
    for row in rows:
        if row["failed"]:
            row.update(tokens_score=0.0, cost_score=0.0, latency_score=0.0)

    for row in rows:
        parts = {
            "relevance": row["relevance"], "validity": row["validity"], "reliability": row["reliability"],
            "conciseness": row["conciseness"], "tokens": row["tokens_score"], "cost": row["cost_score"],
            "latency": row["latency_score"],
        }
        row["overall_score"] = 0.0 if row["failed"] else round(sum(w[k] * parts[k] for k in METRIC_KEYS), 2)
        row["contributions"] = {k: round(w[k] * parts[k], 2) for k in METRIC_KEYS}

    # Ranking: best overall first; ties go to higher relevance, then lower cost, then lower latency.
    ranked = sorted(ok, key=lambda r: (-r["overall_score"], -r["relevance"], r["cost_usd"], r["latency_ms"]))
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position
    for row in rows:
        if row["failed"]:
            row["rank"] = None
        row["is_recommended"] = row.get("rank") == 1
    return w


def explain_recommendation(rows: list[dict]) -> str | None:
    """One readable sentence saying why the top-ranked variant won."""
    ranked = sorted((r for r in rows if r.get("rank")), key=lambda r: r["rank"])
    if not ranked:
        return None
    best = ranked[0]
    top = sorted(best["contributions"].items(), key=lambda kv: -kv[1])[:2]
    text = f"Highest overall score ({best['overall_score']:.1f}/100). Biggest weighted contributions: " + ", ".join(
        f"{name} ({value:.1f} pts)" for name, value in top
    ) + "."
    if len(ranked) > 1:
        gap = best["overall_score"] - ranked[1]["overall_score"]
        text += f" Margin over the runner-up: {gap:.1f} points."
        if gap < 2:
            text += " The margin is small, so treat the two as roughly tied."
    return text
