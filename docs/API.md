# REST API reference

Base URL (local): `http://localhost:8000`. Interactive Swagger UI: `/docs`. All bodies are JSON. Errors look like `{"detail": "..."}`.

| Status | Meaning |
|---|---|
| 200 / 201 / 204 | OK / created / deleted |
| 401 | Real Mode requested but `X-Access-Code` is missing or wrong (only if `REAL_MODE_ACCESS_CODE` is set) |
| 404 | experiment not found |
| 422 | invalid input (empty task, unknown technique, fewer than 2 techniques, negative weights, …) |
| 503 | Real Mode requested but the server is not configured for it (the message says what is missing, e.g. `LLM_API_KEY is not set`) |
| 500 | unexpected server error (details are in the server log only) |

## `GET /api/health`
`{"status": "ok"}`

## `GET /api/config`
```json
{
  "demo_available": true,
  "real_available": false,
  "real_unavailable_reason": "LLM_API_KEY is not set",
  "real_requires_access_code": false,
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "price_known": false,
  "price_input_per_mtok": 0.0,
  "price_output_per_mtok": 0.0,
  "default_weights": {"relevance": 0.3, "validity": 0.15, "reliability": 0.2, "conciseness": 0.1, "tokens": 0.1, "cost": 0.05, "latency": 0.1},
  "metrics": ["relevance", "validity", "reliability", "conciseness", "tokens", "cost", "latency"],
  "techniques": [{"key": "direct", "label": "Direct"}, "..."]
}
```
The API key is never included. `real_unavailable_reason` is `null` when Real Mode is ready, otherwise a short safe explanation.

## `POST /api/prompts/preview`
Generate prompt variants without calling any LLM.
```json
{"task": "Explain what overfitting is.", "techniques": ["direct", "few_shot"], "target_words": 100}
```
`techniques` and `target_words` are optional (default: all six, 120). Response: list of `{technique, label, description, prompt}`.

## `POST /api/experiments`
Run an experiment. Header `X-Access-Code` is needed for `mode: "real"` only if the server sets an access code.

| Field | Type | Default | Rules |
|---|---|---|---|
| `task` | string | required | 3–2000 characters, trimmed |
| `mode` | `"demo"` \| `"real"` | `"demo"` | |
| `techniques` | string[] | all six | at least 2, no repeats; `direct`, `role`, `few_shot`, `structured`, `constraint`, `reasoning` |
| `reference_answer` | string \| null | null | ≤ 2000 characters; improves the relevance metric |
| `weights` | object \| null | defaults | keys from the seven metrics, values ≥ 0, sum > 0 (rescaled to 1) |
| `target_words` | int | 120 | 10–1000 |

Response `201`: an experiment object.
```json
{
  "id": 1, "created_at": "2026-09-30T19:31:54Z", "task": "...", "reference_answer": null,
  "mode": "demo", "simulated": true, "provider": "mock", "model": "mock-simulator-v1",
  "target_words": 120,
  "weights": {"relevance": 0.3, "...": 0.0},
  "price_input_per_mtok": 0.0, "price_output_per_mtok": 0.0,
  "recommended_technique": "direct",
  "recommendation_reason": "Highest overall score (94.7/100). Biggest weighted contributions: ...",
  "results": [{
    "id": 1, "technique": "direct", "label": "Direct", "prompt": "...", "response": "...", "error": null,
    "input_tokens": 12, "output_tokens": 67, "total_tokens": 79, "tokens_estimated": true,
    "latency_ms": 1318.3, "cost_usd": 0.00139,
    "relevance": 100.0, "validity": 100.0, "reliability": 100.0, "conciseness": 100.0,
    "tokens_score": 100.0, "cost_score": 100.0, "latency_score": 65.0,
    "overall_score": 94.73, "rank": 1, "is_recommended": true,
    "details": {"relevance_method": "task_keyword_coverage", "validity_checks": [{"check": "...", "passed": true}],
                "reliability_flags": [], "word_count": 45, "finish_reason": "stop"}
  }]
}
```
If one variant's API call fails, that result has `error` set, `rank: null`, `overall_score: 0`, and the others are still ranked.

## `GET /api/experiments`
History, newest first: `[{id, created_at, task, mode, model, variant_count, recommended_technique, best_score}]`.

## `GET /api/experiments/{id}`
One experiment (same shape as the create response). `404` if missing.

## `POST /api/experiments/{id}/rescore`
```json
{"weights": {"cost": 1, "latency": 1}}
```
Recomputes scores and ranking from the stored measurements with the new weights, saves them, and returns the updated experiment. No LLM call is made.

## `DELETE /api/experiments/{id}`
`204` on success.

## Export
* `GET /api/experiments/{id}/export?format=csv|json`
* `GET /api/experiments/export?format=csv|json` (all experiments)

CSV has one row per prompt variant (columns: experiment id, time, mode, model, task, technique, rank, recommended, overall, the seven metric scores, token counts, cost, latency, error, response). Demo rows are labelled `demo (simulated)`. Text cells starting with `= + - @` are prefixed with `'` so spreadsheets do not execute them as formulas. Responses use `Content-Disposition: attachment`.
