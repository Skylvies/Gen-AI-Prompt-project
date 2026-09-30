"""Step 1 of the pipeline: turn one task into several prompt variants.

Each technique is a plain template - no LLM is involved here, so the same task always
produces the same prompts (reproducible experiments).
"""
from dataclasses import dataclass, field


@dataclass
class PromptVariant:
    technique: str  # machine key, e.g. "few_shot"
    label: str  # human name shown in the UI
    description: str
    prompt: str
    required_labels: list[str] = field(default_factory=list)  # section labels the prompt demands
    max_words: int | None = None  # word limit the prompt demands (if any)


TECHNIQUE_LABELS = {
    "direct": "Direct",
    "role": "Role-based",
    "few_shot": "Few-shot",
    "structured": "Structured",
    "constraint": "Constraint-based",
    "reasoning": "Reasoning-oriented",
}
TECHNIQUES = list(TECHNIQUE_LABELS)

# Small example banks for few-shot prompting, chosen by a keyword check on the task.
FEW_SHOT_EXAMPLES = {
    "summarize": [
        ("Summarize: The meeting covered budgets, hiring and the launch date. The launch moved to May.",
         "The meeting covered budgets and hiring, and moved the launch to May."),
        ("Summarize: The app crashed twice after the update. Users asked for a fix and a refund.",
         "After the update the app crashed twice, and users asked for a fix and a refund."),
    ],
    "classify": [
        ("Classify the sentiment: 'The delivery was late and the box was damaged.'",
         "Negative - the review describes a late delivery and damaged goods."),
        ("Classify the sentiment: 'Great screen and the battery lasts all day.'",
         "Positive - the review praises the screen and the battery life."),
    ],
    "explain": [
        ("Explain what an API is.",
         "An API is a set of rules that lets one program request data or services from another program."),
        ("What is a database index?",
         "A database index is a data structure that lets the database find rows quickly without scanning the whole table."),
    ],
    "general": [
        ("What is the capital of France?", "Paris is the capital of France."),
        ("What does CPU stand for?",
         "CPU stands for Central Processing Unit, the main chip that runs a computer's instructions."),
    ],
}

_CATEGORY_CUES = {
    "summarize": ("summar", "tl;dr", "shorten", "condense"),
    "classify": ("classif", "sentiment", "categor", "label"),
    "explain": ("explain", "what is", "what are", "how does", "why ", "define", "describe"),
}


def detect_category(task: str) -> str:
    lowered = task.lower()
    for category, cues in _CATEGORY_CUES.items():
        if any(cue in lowered for cue in cues):
            return category
    return "general"


def _clean(task: str) -> str:
    # The task is wrapped in <task> tags so the model can tell instructions from input.
    return task.strip().replace("</task>", "< /task>")


def generate_variants(task: str, techniques: list[str] | None = None, target_words: int = 120) -> list[PromptVariant]:
    """Build one PromptVariant per requested technique (default: all six)."""
    techniques = techniques or TECHNIQUES
    unknown = [t for t in techniques if t not in TECHNIQUE_LABELS]
    if unknown:
        raise ValueError(f"Unknown technique(s): {', '.join(unknown)}")

    task = _clean(task)
    tagged = f"<task>\n{task}\n</task>"
    examples = "\n\n".join(
        f"Example {i}\nQ: {q}\nA: {a}" for i, (q, a) in enumerate(FEW_SHOT_EXAMPLES[detect_category(task)], 1)
    )

    builders = {
        "direct": PromptVariant(
            "direct", "Direct", "The task exactly as written, with no extra guidance.",
            task,
        ),
        "role": PromptVariant(
            "role", "Role-based", "Assigns the model an expert persona before the task.",
            "You are an experienced subject-matter expert who explains things accurately, clearly and "
            f"professionally.\n\n{tagged}",
        ),
        "few_shot": PromptVariant(
            "few_shot", "Few-shot", "Shows two worked examples so the model copies their style and length.",
            f"Here are examples of the expected answer style: short, direct and factual.\n\n{examples}\n\n"
            f"Now answer the new task in the same style.\n\n{tagged}",
        ),
        "structured": PromptVariant(
            "structured", "Structured", "Fixes the output layout with labelled sections.",
            f"# Task\n{tagged}\n\n# Output format\nRespond using exactly these sections:\n"
            "Answer: <one or two sentences that directly answer the task>\n"
            "Explanation: <two to four sentences of supporting detail>\n"
            "Key points: <up to three short bullet points>",
            required_labels=["Answer:", "Explanation:", "Key points:"],
        ),
        "constraint": PromptVariant(
            "constraint", "Constraint-based", "States explicit rules: length limit, no invented facts.",
            "Complete the task below and obey ALL of these constraints:\n"
            f"1. Use at most {target_words} words.\n"
            "2. Use plain language: no preamble and no filler.\n"
            "3. State only facts you are confident about; if unsure, say \"I am not certain\".\n"
            "4. Do not invent numbers, names, sources or links.\n\n"
            f"{tagged}",
            max_words=target_words,
        ),
        "reasoning": PromptVariant(
            "reasoning", "Reasoning-oriented",
            "Asks the model to reason privately and show only the answer and a short justification.",
            "Think through the problem step by step privately before answering. Do not show your internal "
            "reasoning.\nThen reply in this format:\n"
            "Answer: <the final answer>\n"
            "Justification: <at most three sentences giving the key reasons, not a full derivation>\n\n"
            f"{tagged}",
            required_labels=["Answer:", "Justification:"],
        ),
    }
    return [builders[t] for t in techniques]
