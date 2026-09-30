from app.evaluator import (conciseness_score, evaluate_response, relevance_score, reliability_score,
                           validity_score)
from app.prompt_generator import PromptVariant, generate_variants
from app.providers.base import LLMResponse

PLAIN = PromptVariant("direct", "Direct", "", "prompt")


# ---------- relevance ----------

def test_relevance_uses_reference_when_given():
    good, method = relevance_score("Paris is the capital city of France", "capital of France?", "Paris capital France")
    bad, _ = relevance_score("Bananas are yellow fruit", "capital of France?", "Paris capital France")
    assert method == "reference_overlap_f2"
    assert good > 80 and bad == 0


def test_relevance_falls_back_to_task_keyword_coverage():
    score, method = relevance_score("Overfitting happens when a model memorises training data",
                                    "Explain overfitting in a machine learning model", None)
    assert method == "task_keyword_coverage"
    assert 30 < score < 100


def test_relevance_is_neutral_when_task_has_no_keywords():
    assert relevance_score("anything", "hi", None)[0] == 50.0


# ---------- validity ----------

def test_validity_passes_a_good_answer():
    score, checks = validity_score("This is a perfectly fine complete answer.", "stop", PLAIN)
    assert score == 100 and all(c["passed"] for c in checks)


def test_validity_fails_empty_truncated_and_refusal():
    score, checks = validity_score("", "stop", PLAIN)
    assert score == 50 and [c["passed"] for c in checks] == [False, False, True, True]  # empty + too short fail
    assert validity_score("This answer was cut off mid", "length", PLAIN)[0] < 100
    assert validity_score("I'm sorry, but I can't help with that request.", "stop", PLAIN)[0] < 100


def test_validity_checks_required_sections_and_word_limit():
    structured = generate_variants("Explain APIs", ["structured"])[0]
    assert validity_score("Answer: x y z w v\nExplanation: a\nKey points: b", "stop", structured)[0] == 100
    assert validity_score("Just a plain paragraph without the labels at all.", "stop", structured)[0] < 100

    constrained = generate_variants("Explain APIs", ["constraint"], target_words=10)[0]
    long_answer = " ".join(["word"] * 30)
    assert validity_score(long_answer, "stop", constrained)[0] < 100


# ---------- reliability (hallucination risk indicator) ----------

def test_reliability_clean_text_scores_100():
    score, flags = reliability_score("Overfitting means the model memorises its training data.",
                                     "Explain overfitting", None)
    assert score == 100 and flags == []


def test_reliability_flags_invented_numbers_links_and_overconfidence():
    text = "It was proven in 1987 that this always works, see https://example.com and Smith et al."
    score, flags = reliability_score(text, "Explain overfitting", None)
    kinds = {f["type"] for f in flags}
    assert {"unsupported_number", "citation_or_link", "overconfident_wording"} <= kinds
    assert score < 60


def test_reliability_does_not_penalise_numbers_that_came_from_the_task():
    score, _ = reliability_score("The budget for 2024 is fixed.", "Summarise the 2024 budget", None)
    assert score == 100


def test_reliability_ignores_list_numbering():
    score, _ = reliability_score("1. First point here\n2. Second point here", "Explain", None)
    assert score == 100


def test_reliability_penalty_is_capped_and_never_negative():
    text = " ".join(f"{1000 + i}" for i in range(50)) + " always never definitely https://a.com https://b.com"
    score, _ = reliability_score(text, "x", None)
    assert 0 <= score < 100


# ---------- conciseness ----------

def test_conciseness_full_marks_within_target_then_decays():
    assert conciseness_score(" ".join(["w"] * 50), 100) == 100
    assert conciseness_score(" ".join(["w"] * 200), 100) == 50
    assert conciseness_score(" ".join(["w"] * 300), 100) == 0
    assert conciseness_score("", 100) == 0


# ---------- evaluate_response ----------

def test_evaluate_response_marks_errors_as_zero():
    failed = LLMResponse("", 0, 0, 0.0, finish_reason="error", error="boom")
    result = evaluate_response(failed, PLAIN, "task text here", None, 100)
    assert result["relevance"] == result["reliability"] == result["conciseness"] == 0
    assert result["validity"] < 100
