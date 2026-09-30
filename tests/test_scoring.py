import pytest

from app.config import DEFAULT_WEIGHTS, METRIC_KEYS
from app.scoring import explain_recommendation, lower_is_better, normalize_weights, score_variants


def row(relevance=80, validity=100, reliability=100, conciseness=100, tokens=100, cost=0.001, latency=500, failed=False):
    return {"relevance": relevance, "validity": validity, "reliability": reliability, "conciseness": conciseness,
            "total_tokens": tokens, "cost_usd": cost, "latency_ms": latency, "failed": failed}


def test_default_weights_normalise_to_one():
    w = normalize_weights(None)
    assert set(w) == set(METRIC_KEYS)
    assert sum(w.values()) == pytest.approx(1.0)


def test_weights_are_rescaled_not_rejected_when_they_do_not_sum_to_one():
    w = normalize_weights({"relevance": 2, "validity": 2})
    assert w["relevance"] == pytest.approx(0.5) and w["tokens"] == 0


@pytest.mark.parametrize("bad", [{"relevance": -1}, {"nonsense": 1}, {k: 0 for k in METRIC_KEYS}])
def test_invalid_weights_raise(bad):
    with pytest.raises(ValueError):
        normalize_weights(bad)


def test_lower_is_better_min_max():
    assert lower_is_better([10, 20, 30]) == [100, 50, 0]
    assert lower_is_better([5, 5]) == [100, 100]


def test_best_row_gets_rank_one_and_is_recommended():
    rows = [row(relevance=50, tokens=300), row(relevance=90, tokens=100), row(relevance=70, tokens=200)]
    score_variants(rows, None)
    assert [r["rank"] for r in rows] == [3, 1, 2]
    assert [r["is_recommended"] for r in rows] == [False, True, False]
    assert rows[1]["overall_score"] == max(r["overall_score"] for r in rows)


def test_overall_score_matches_the_weighted_sum_by_hand():
    rows = [row(tokens=100, cost=0.002, latency=1000), row(tokens=200, cost=0.004, latency=2000)]
    w = score_variants(rows, None)
    first = rows[0]  # cheapest / fastest -> efficiency scores of 100
    expected = (w["relevance"] * 80 + w["validity"] * 100 + w["reliability"] * 100 + w["conciseness"] * 100
                + w["tokens"] * 100 + w["cost"] * 100 + w["latency"] * 100)
    assert first["overall_score"] == pytest.approx(expected, abs=0.01)
    assert rows[1]["tokens_score"] == rows[1]["cost_score"] == rows[1]["latency_score"] == 0


def test_changing_weights_can_change_the_winner():
    accurate_but_slow = row(relevance=95, latency=5000, tokens=400, cost=0.01)
    fast_but_vague = row(relevance=40, latency=100, tokens=50, cost=0.0005)
    quality_first = [dict(accurate_but_slow), dict(fast_but_vague)]
    speed_first = [dict(accurate_but_slow), dict(fast_but_vague)]
    score_variants(quality_first, {"relevance": 1})
    score_variants(speed_first, {"latency": 1})
    assert quality_first[0]["rank"] == 1
    assert speed_first[1]["rank"] == 1


def test_failed_rows_are_excluded_from_ranking_and_normalisation():
    rows = [row(tokens=100), row(tokens=0, cost=0, latency=0, failed=True), row(tokens=300)]
    score_variants(rows, None)
    assert rows[1]["rank"] is None and rows[1]["overall_score"] == 0 and not rows[1]["is_recommended"]
    assert rows[0]["tokens_score"] == 100 and rows[2]["tokens_score"] == 0  # failed 0-token row did not distort it


def test_ties_are_broken_by_relevance_then_cost():
    rows = [row(relevance=80, cost=0.002), row(relevance=80, cost=0.001)]
    score_variants(rows, {"validity": 1})  # only validity counts -> identical overall scores
    assert rows[1]["rank"] == 1


def test_all_failed_means_no_recommendation():
    rows = [row(failed=True), row(failed=True)]
    score_variants(rows, None)
    assert all(r["rank"] is None for r in rows)
    assert explain_recommendation(rows) is None


def test_explanation_mentions_score_and_margin():
    rows = [row(relevance=90), row(relevance=40)]
    score_variants(rows, None)
    text = explain_recommendation(rows)
    assert "Highest overall score" in text and "Margin over the runner-up" in text


def test_default_weight_keys_match_metric_keys():
    assert set(DEFAULT_WEIGHTS) == set(METRIC_KEYS)
