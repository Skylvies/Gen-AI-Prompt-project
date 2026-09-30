# Methodology and metric definitions

Everything below is implemented in `backend/app/evaluator.py` and `backend/app/scoring.py`. Formulas are kept deliberately simple so each one can be explained and reproduced by hand.

## Pipeline

```
task ─► 6 prompt variants ─► LLM (or simulator) ─► response + usage + latency
                                                        │
                                   evaluator: relevance, validity, reliability, conciseness
                                                        │
        scoring: normalise tokens/cost/latency ─► weighted sum ─► rank ─► recommendation
```

## Text metrics (0–100, higher is better)

### Relevance
Text is lower-cased, stop-words and words shorter than 3 letters are removed, and a crude suffix stemmer maps `models → model`, `training → train`.

* **With a reference answer:** let `R` = reference keyword set, `S` = response keyword set, `overlap = |R ∩ S|`.
  `precision = overlap / |S|`, `recall = overlap / |R|`, `F2 = 5·P·R / (4·P + R)`, `relevance = 100 × F2`.
  F2 weights recall 4× more than precision, because a good answer may add useful extra words but must cover the reference.
* **Without a reference:** `relevance = 100 × |task keywords ∩ response keywords| / |task keywords|` (keyword coverage). If the task has no keywords the score is a neutral 50.

*Limitation:* lexical overlap, not meaning. Paraphrases score low; keyword stuffing scores high.

### Validity
A list of pass/fail checks; `validity = 100 × passed / total`.

| Check | Applies to |
|---|---|
| Response is not empty | all |
| Response has at least 5 words | all |
| Not cut off (`finish_reason == "stop"`; the API reports `max_tokens` as `length`) | all |
| Not a refusal or error (`finish_reason` ≠ refusal/error and no "I'm sorry / I can't help" pattern) | all |
| Contains the section labels the prompt demanded (`Answer:`, `Explanation:`, …) | structured, reasoning |
| Within the word limit the prompt asked for | constraint |

### Reliability (hallucination-risk indicator)
`reliability = max(0, 100 − total penalties)`. **This is a heuristic risk signal, not a fact-check.** It never verifies truth.

| Signal | Penalty per hit | Cap |
|---|---|---|
| Number with 2+ digits (years, statistics, decimals) that is not in the task or reference | 8 | 40 |
| Capitalised mid-sentence word (likely a name) not in the task or reference | 3 | 15 |
| URL or citation-style phrase ("according to a study", "Smith et al.") | 15 | 30 |
| Over-confident wording: always, never, definitely, certainly, guaranteed, undoubtedly, 100%, … | 5 | 20 |

List numbering ("1. …") is ignored. Reasoning: fabricated answers often contain invented specifics and unwarranted certainty, while answers that stay inside the task's own facts have fewer of these signals.
*False positives:* a correct year or name the model legitimately adds is penalised. *False negatives:* a plausible falsehood with no numbers/names passes.

### Conciseness
`wc` = word count, `T` = target words (user setting, default 100 in the UI).
`100` if `wc ≤ T`; otherwise `max(0, 100 × (1 − (wc − T) / (2T)))` (50 at 2T, 0 at 3T). An empty response scores 0.

## Efficiency metrics

| Metric | Source |
|---|---|
| Tokens | `input_tokens + output_tokens` from the API response (Demo: `characters / 4`) |
| Cost | `(input × price_in + output × price_out) / 1,000,000` using the built-in price table (a few models) or the `PRICE_*` env variables. Free models with no price cost $0, so every variant gets the same cost score and cost does not change the ranking |
| Latency | wall-clock time around the API call, in ms (Demo: `350 + 14 × output_tokens + jitter`, simulated) |

These have no natural 0–100 scale, so they are **min-max normalised within one experiment** (lower is better):
`score = 100 × (max − value) / (max − min)`; if `max == min` every variant gets 100. Failed calls are excluded from `min`/`max`.

## Overall score and recommendation

```
w_i' = w_i / Σ w                         (weights rescaled to sum to 1)
overall = Σ w_i' × score_i               over: relevance, validity, reliability, conciseness, tokens, cost, latency
```
Default weights: relevance 0.30, reliability 0.20, validity 0.15, conciseness 0.10, tokens 0.10, latency 0.10, cost 0.05.

Ranking key: `(−overall, −relevance, cost, latency)`. Rank 1 is the recommendation. The explanation lists the two largest `w_i' × score_i` contributions and the margin over the runner-up, and warns when the margin is below 2 points.

## Worked example (3 variants, default weights)

| Variant | Relevance | Validity | Reliability | Conciseness | Tokens | Cost | Latency |
|---|---|---|---|---|---|---|---|
| A | 80 | 100 | 100 | 100 | 100 | $0.002 | 1000 ms |
| B | 60 | 100 | 100 | 100 | 200 | $0.004 | 2000 ms |
| C | 70 | 100 | 100 | 100 | 150 | $0.003 | 1500 ms |

Tokens/cost/latency scores: A = 100/100/100, B = 0/0/0, C = 50/50/50.
`overall(A) = 0.30·80 + 0.15·100 + 0.20·100 + 0.10·100 + 0.10·100 + 0.05·100 + 0.10·100 = 94.0`
`overall(C) = 21 + 15 + 20 + 10 + 5 + 2.5 + 5 = 78.5`, `overall(B) = 18 + 15 + 20 + 10 + 0 + 0 + 0 = 63.0` → **A is recommended.**
If A's relevance were only 20 instead of 80, `overall(A) = 76.0` and **C would win** (78.5). The winner depends on both the measurements and the weights.

## Why prompts are compared on one task at a time
Metrics such as keyword coverage and min-max normalisation only make sense when all variants answer the *same* question. Comparing across tasks, or across experiments, is not supported and would be misleading.
