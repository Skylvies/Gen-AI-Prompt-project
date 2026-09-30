"""Step 3 of the pipeline: measure each response.

Every metric here is a HEURISTIC computed from the text - there is no human judge and no
second LLM. Scores are 0-100, higher is better. They are useful for comparing prompts on
the same task, but they are proxies, not ground truth. See docs/METHODOLOGY.md.
"""
import re

from .prompt_generator import PromptVariant
from .providers.base import LLMResponse
from .text_utils import stemmed_keywords, word_count

# ---------- relevance ----------

def relevance_score(response: str, task: str, reference: str | None) -> tuple[float, str]:
    """With a reference answer: recall-weighted word overlap (F2). Without: task keyword coverage."""
    resp_words = stemmed_keywords(response)
    if reference and reference.strip():
        ref_words = stemmed_keywords(reference)
        if not ref_words or not resp_words:
            return 0.0, "reference_overlap_f2"
        overlap = len(resp_words & ref_words)
        precision, recall = overlap / len(resp_words), overlap / len(ref_words)
        if precision + recall == 0:
            return 0.0, "reference_overlap_f2"
        f2 = 5 * precision * recall / (4 * precision + recall)  # recall counts 4x more than precision
        return round(100 * f2, 1), "reference_overlap_f2"

    task_words = stemmed_keywords(task)
    if not task_words:
        return 50.0, "task_keyword_coverage"  # nothing to compare against: neutral score
    return round(100 * len(task_words & resp_words) / len(task_words), 1), "task_keyword_coverage"


# ---------- validity ----------

_REFUSAL = re.compile(
    r"^\s*(i'?m sorry|i am sorry|sorry,)|\bi (cannot|can't|am unable to|won't) (help|assist|comply|answer|provide)",
    re.IGNORECASE,
)


def validity_score(text: str, finish_reason: str, variant: PromptVariant) -> tuple[float, list[dict]]:
    """Percentage of pass/fail checks that pass."""
    wc = word_count(text)
    checks = [
        ("Response is not empty", bool(text.strip())),
        ("Response has at least 5 words", wc >= 5),
        ("Response was not cut off (finish reason: stop)", finish_reason == "stop"),
        ("Response is not a refusal or error", finish_reason not in ("refusal", "error") and not _REFUSAL.search(text)),
    ]
    lowered = text.lower()
    if variant.required_labels:
        missing = [lab for lab in variant.required_labels if lab.lower() not in lowered]
        checks.append((f"Contains required sections ({', '.join(variant.required_labels)})", not missing))
    if variant.max_words:
        checks.append((f"Within the {variant.max_words}-word limit the prompt asked for", wc <= variant.max_words))

    details = [{"check": name, "passed": passed} for name, passed in checks]
    return round(100 * sum(p for _, p in checks) / len(checks), 1), details


# ---------- factual reliability (hallucination RISK indicator) ----------

_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_NUMBER = re.compile(r"\b\d[\d,.]*\d\b|\b\d{2,}\b")  # 2+ digit numbers, years, decimals
_PROPER_NOUN = re.compile(r"(?<=[a-z,;] )[A-Z][a-z]{2,}")  # capitalised word in mid-sentence
_CITATION = re.compile(
    r"https?://\S+|www\.\S+|\b[A-Z][a-z]+ et al\.?|\baccording to (?:a |the )?(?:recent )?(?:study|report|survey|research)\b",
    re.IGNORECASE,
)
_OVERCONFIDENT = re.compile(
    r"\b(always|never|definitely|certainly|guaranteed?|undoubtedly|without (?:a )?doubt|proven fact|everyone knows)\b|100%",
    re.IGNORECASE,
)

# (flag type, penalty per hit, maximum total penalty)
_PENALTIES = {
    "unsupported_number": (8, 40),
    "unsupported_name": (3, 15),
    "citation_or_link": (15, 30),
    "overconfident_wording": (5, 20),
}


def reliability_score(text: str, task: str, reference: str | None) -> tuple[float, list[dict]]:
    """100 minus penalties for signals that often accompany made-up content.

    This is NOT a fact-check. It cannot know whether a statement is true. It only flags
    specifics (numbers, names, sources) that appear in the answer but not in the task or
    reference, plus over-confident wording.
    """
    context = f"{task} {reference or ''}"
    context_lower = context.lower()
    context_numbers = set(_NUMBER.findall(context))
    body = _LIST_MARKER.sub("", text)  # "1. " bullet numbers are not claims

    hits: dict[str, list[str]] = {
        "unsupported_number": sorted({n for n in _NUMBER.findall(body) if n not in context_numbers}),
        "unsupported_name": sorted({n for n in _PROPER_NOUN.findall(body) if n.lower() not in context_lower}),
        "citation_or_link": [m.group(0) for m in _CITATION.finditer(body)],
        "overconfident_wording": [m.group(0).lower() for m in _OVERCONFIDENT.finditer(body)],
    }

    score, flags = 100.0, []
    for flag_type, found in hits.items():
        if not found:
            continue
        per_hit, cap = _PENALTIES[flag_type]
        penalty = min(cap, per_hit * len(found))
        score -= penalty
        flags.append({"type": flag_type, "examples": found[:5], "penalty": penalty})
    return max(0.0, round(score, 1)), flags


# ---------- conciseness ----------

def conciseness_score(text: str, target_words: int) -> float:
    """100 up to the target length, then falling linearly to 0 at 3x the target."""
    wc = word_count(text)
    if wc == 0:
        return 0.0
    if wc <= target_words:
        return 100.0
    return round(max(0.0, 100 * (1 - (wc - target_words) / (2 * target_words))), 1)


# ---------- all together ----------

def evaluate_response(
    response: LLMResponse, variant: PromptVariant, task: str, reference: str | None, target_words: int
) -> dict:
    """Return the four text-based metrics plus the details that explain them."""
    text = response.text or ""
    if response.error or not text.strip():
        relevance, relevance_method = 0.0, "none"
        validity, checks = validity_score(text, "error" if response.error else response.finish_reason, variant)
        reliability, flags, conciseness = 0.0, [], 0.0
    else:
        relevance, relevance_method = relevance_score(text, task, reference)
        validity, checks = validity_score(text, response.finish_reason, variant)
        reliability, flags = reliability_score(text, task, reference)
        conciseness = conciseness_score(text, target_words)

    return {
        "relevance": relevance,
        "validity": validity,
        "reliability": reliability,
        "conciseness": conciseness,
        "details": {
            "relevance_method": relevance_method,
            "validity_checks": checks,
            "reliability_flags": flags,
            "word_count": word_count(text),
            "finish_reason": response.finish_reason,
        },
    }
