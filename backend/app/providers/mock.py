"""Demo Mode provider: a tiny rule-based SIMULATOR, not a language model.

It lets the whole app run without an API key. It does NOT know any facts: it builds
placeholder sentences from the keywords of the task and obeys the formatting
instructions found in the prompt (word limit, section labels, persona, few-shot style).
Every number produced in Demo Mode is therefore a demonstration of the pipeline only -
it says nothing about how a real model behaves. The UI and exports label it "simulated".

It is deterministic: the same prompt always gives the same output.
"""
import hashlib
import random
import re

from ..text_utils import estimate_tokens, top_keywords
from .base import LLMProvider, LLMResponse

_TASK_TAG = re.compile(r"<task>\s*(.*?)\s*</task>", re.DOTALL)
_WORD_LIMIT = re.compile(r"at most (\d+) words", re.IGNORECASE)


def _extract_task(prompt: str) -> str:
    matches = _TASK_TAG.findall(prompt)
    return matches[-1] if matches else prompt  # "direct" prompts have no tags


def _truncate_words(text: str, limit: int) -> str:
    """Keep at most `limit` words, preferably ending on a complete sentence."""
    words = text.split()
    if len(words) <= limit:
        return text
    cut = " ".join(words[:limit])
    last_stop = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("!"), cut.rfind("?"))
    if cut.endswith("."):
        return cut
    if last_stop > 0:
        return cut[: last_stop + 1]
    return cut.rstrip(",;:") + "."


class MockProvider(LLMProvider):
    name = "mock"
    model = "mock-simulator-v1"
    simulated = True

    def generate(self, prompt: str, max_tokens: int) -> LLMResponse:
        rng = random.Random(int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % (2**32))
        kw = top_keywords(_extract_task(prompt), 4)
        kw += ["the topic"] * (4 - len(kw))  # pad so templates always fill
        k1, k2, k3, k4 = kw

        lowered = prompt.lower()
        sentences = [
            f"{k1.capitalize()} mainly involves {k2} and {k3}.",
            f"A clear way to approach it is to start from {k1} and then relate it to {k4}.",
            f"In practice, {k2} and {k3} are the parts that matter most.",
            "It helps to check the result against the original requirement.",
        ]
        if "subject-matter expert" in lowered:
            sentences.insert(0, "From an expert point of view, the question has a few important layers.")
            sentences.append("Experts usually add that context decides which detail is most relevant.")
        if "example 1" in lowered:  # few-shot: copy the short style of the examples
            sentences = sentences[:2]

        body = " ".join(sentences)
        if "answer:" in lowered and "explanation:" in lowered:  # structured layout
            body = (
                f"Answer: {sentences[0]}\n"
                f"Explanation: {sentences[1]} {sentences[2]}\n"
                f"Key points:\n- {k1}\n- {k2}\n- {k3}"
            )
        elif "answer:" in lowered and "justification:" in lowered:  # reasoning-oriented layout
            body = f"Answer: {sentences[0]}\nJustification: {sentences[1]} {sentences[2]}"

        limit = _WORD_LIMIT.search(prompt)
        if limit:
            body = _truncate_words(body, int(limit.group(1)))

        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(body)
        latency_ms = 350 + 14 * output_tokens + rng.uniform(0, 120)  # simulated, not measured
        return LLMResponse(
            text=body,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=True,
        )
