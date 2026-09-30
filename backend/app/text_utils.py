"""Small text helpers shared by the mock provider and the evaluator."""
import re
from collections import Counter

STOPWORDS = set(
    """a an the and or but if then else of to in on at by for with about as is are was were be been
    being this that these those it its from into than so such can could should would will may might
    do does did not no yes you your i we they he she them his her our their what which who whom how
    why when where please give write explain describe list answer also just more most very some any
    each between using use make makes made""".split()
)


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text))


def estimate_tokens(text: str) -> int:
    """Rule of thumb: ~4 characters per token for English. Used only when the API gives no usage."""
    return max(1, round(len(text) / 4)) if text else 0


def _stem(word: str) -> str:
    """Very crude suffix stripping so 'models' matches 'model' and 'training' matches 'train'."""
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 4:
        return word[:-1]
    return word


def keywords(text: str) -> list[str]:
    """Lower-case content words (no stop-words, no very short words), in order of appearance."""
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def stemmed_keywords(text: str) -> set[str]:
    return {_stem(w) for w in keywords(text)}


def top_keywords(text: str, n: int) -> list[str]:
    """The n most frequent content words (ties broken by first appearance)."""
    words = keywords(text)
    first_seen = {}
    for i, w in enumerate(words):
        first_seen.setdefault(w, i)
    counts = Counter(words)
    return sorted(counts, key=lambda w: (-counts[w], first_seen[w]))[:n]
