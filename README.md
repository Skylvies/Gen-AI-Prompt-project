# Adaptive Prompt Optimization and Evaluation Framework for Large Language Models

A web application that takes a task, turns it into **six prompt variants** (direct, role-based, few-shot, structured, constraint-based, reasoning-oriented), sends each to an LLM, **measures** every response with transparent metrics, combines them with **configurable weights**, and **recommends the highest-scoring prompt**.

It works out of the box in **Demo Mode** (no API key, no cost). **Real Mode** calls a **free, open-source model**: Meta's Llama on [Groq](https://console.groq.com)'s free tier by default, or OpenRouter, a model running on your own computer with Ollama (no key at all), or any OpenAI-compatible API. Claude is supported too, as an optional extra. The key lives only in a server environment variable.

> **Honesty note.** Relevance, reliability (hallucination risk), validity and conciseness are *heuristics*, not ground truth. Demo Mode output comes from a rule-based *simulator*, so its numbers demonstrate the pipeline, not real model behaviour. Both facts are labelled in the UI, in exports, and listed under [Limitations](#limitations).

---

## Contents
1. [Problem and objectives](#1-problem-and-objectives) · 2. [Features](#2-features) · 3. [Architecture](#3-architecture) · 4. [Methodology](#4-methodology) · 5. [Metrics](#5-metrics) · 6. [Scoring](#6-scoring) · 7. [Setup and run locally](#7-setup-and-run-locally) · 8. [Demo Mode](#8-demo-mode) · 9. [Real Mode and the API key](#9-real-mode-and-the-api-key-free-open-source-models) · 10. [API usage](#10-api-usage) · 11. [Testing](#11-testing) · 12. [Push to GitHub](#12-push-to-github) · 13. [Deployment](#13-deployment) · [Limitations](#limitations) · [Future scope](#future-scope) · [Viva questions](docs/VIVA_QUESTIONS.md)

---

## 1. Problem and objectives

**Problem.** The same LLM can give very different answers depending on how the request is phrased. Choosing a prompt by gut feeling is unreliable, and "better" depends on what you care about: accuracy, brevity, speed, or cost.

**Objectives**
1. Automatically generate several prompt variants from one task using standard prompting techniques.
2. Run all variants through an LLM behind a clean provider interface.
3. Evaluate outputs with measurable metrics (quality, tokens, cost, latency).
4. Combine metrics with user-defined weights and identify the best prompt *for those weights*.
5. Present everything in a dashboard with history and CSV/JSON export.
6. Keep the code small and explainable, and never hard-code secrets or fabricate results.

**What "adaptive" means here.** (a) The few-shot examples adapt to the detected task type (summarise / classify / explain / general). (b) The recommendation adapts to *your* weights, and can be re-scored instantly without new API calls. The framework does **not** yet search or rewrite prompts automatically; see [Future scope](#future-scope).

## 2. Features

| Area | What you get |
|---|---|
| Prompt generation | 6 techniques, deterministic templates, preview without any LLM call |
| LLM access | Provider abstraction: `MockProvider` (Demo), `OpenAICompatibleProvider` (Groq / OpenRouter / Ollama / any compatible API; **free open-source models**) and an optional `AnthropicProvider`. Adding another vendor = one new class |
| Metrics | Relevance, validity, reliability (hallucination-risk indicator), conciseness, tokens, cost, latency, overall |
| Scoring | Weighted sum, weights configurable per run, re-score stored results for free |
| Dashboard | Prompt input, variants, responses, metric table (best cell highlighted), bar/radar charts, recommended prompt with explanation, history, CSV/JSON export |
| Safety | Key only from env vars, never returned by the API, never reads `ANTHROPIC_API_KEY` unless you choose that provider, optional access code for Real Mode, input validation, sanitised error messages, CSV formula-injection guard, a test that scans the repo for key-shaped strings |
| Quality | 110 automated tests (no network needed), GitHub Actions CI, responsive UI |

## 3. Architecture

```
  Browser (React + Vite + Tailwind + Recharts)
  ┌────────────────────────────────────────────┐
  │ TaskForm → Results (table, charts, winner) │
  │ HistoryPanel · WeightsEditor · Export      │
  └──────────────────────┬─────────────────────┘
                         │  REST / JSON  (/api/...)
  ┌──────────────────────▼─────────────────────┐
  │ FastAPI  (backend/app/main.py)             │
  │   validates input (Pydantic schemas)       │
  │            │                               │
  │   service.run_experiment()                 │
  │     1. prompt_generator  → 6 prompts       │
  │     2. provider.generate → LLM responses ──┼──► Groq / OpenRouter / Ollama /
  │           (in parallel threads)            │    any OpenAI-compatible API (Real)
  │                                            │  └► MockProvider simulator   (Demo)
  │     3. evaluator         → metrics         │
  │     4. scoring           → weighted score, │
  │                            rank, winner    │
  │     5. SQLAlchemy        → SQLite          │
  └────────────────────────────────────────────┘
```

```
adaptive-prompt-optimizer/
├── backend/app/
│   ├── main.py              REST endpoints, CORS, error handling
│   ├── config.py            settings from environment variables, default weights, price table
│   ├── schemas.py           request/response validation
│   ├── prompt_generator.py  the six prompt templates
│   ├── providers/           base.py (interface) · mock.py · openai_compatible.py · anthropic_provider.py (optional)
│   ├── evaluator.py         relevance, validity, reliability, conciseness
│   ├── scoring.py           normalisation, weighted score, ranking, explanation
│   ├── service.py           the pipeline + ORM→dict helpers
│   ├── models.py, database.py   SQLAlchemy tables (Experiment, VariantResult)
│   └── exporter.py          CSV / JSON
├── frontend/src/            App.jsx, api.js, components/ (TaskForm, Results, MetricsTable, Charts, ...)
├── tests/                   pytest suite (110 tests)
├── docs/                    METHODOLOGY.md · API.md · DEPLOYMENT.md · VIVA_QUESTIONS.md
├── .env.example  .gitignore  render.yaml  .github/workflows/ci.yml
```

## 4. Methodology

1. **Generate.** `prompt_generator.py` fills six templates with the task (wrapped in `<task>` tags so the model can tell instructions from input):

| Technique | Idea |
|---|---|
| Direct | The task exactly as written (baseline) |
| Role-based | "You are an experienced subject-matter expert…" |
| Few-shot | Two worked Q/A examples chosen by task type, then the task |
| Structured | Demands `Answer:` / `Explanation:` / `Key points:` sections |
| Constraint-based | Word limit, plain language, "do not invent numbers, names, sources or links" |
| Reasoning-oriented | "Think step by step **privately**, do not show reasoning; reply with `Answer:` and a ≤3-sentence `Justification:`". It never asks the model to reveal hidden chain-of-thought |

2. **Call.** Each prompt goes to the selected provider (parallel threads). A failed call becomes a *failed variant* (shown in red, excluded from ranking) instead of crashing the experiment.
3. **Evaluate.** `evaluator.py` computes four text metrics; tokens, cost and latency come from the provider.
4. **Score.** `scoring.py` normalises, applies weights, ranks, picks the winner and writes a one-sentence explanation.
5. **Store and show.** Saved in SQLite; the dashboard reads it back; CSV/JSON export is one click.

Full formulas: [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## 5. Metrics

All quality metrics are **0–100, higher is better**.

| Metric | How it is computed | Measured or heuristic? |
|---|---|---|
| **Relevance** | With a reference answer: recall-weighted word overlap (F2) between response and reference. Without: share of the task's keywords that appear in the response | Heuristic (lexical, not semantic) |
| **Validity** | % of pass/fail checks passed: non-empty, ≥5 words, not cut off (`finish_reason = stop`), not a refusal/error, plus the format the prompt demanded (required sections, word limit) | Rule-based checks |
| **Reliability** (hallucination-risk indicator) | 100 minus penalties for: numbers not in the task/reference (−8 each, max −40), capitalised names not in the task/reference (−3, max −15), URLs/citation phrases (−15, max −30), over-confident words like "always/definitely/100%" (−5, max −20) | **Heuristic. Not a fact-check.** It cannot know whether a statement is true |
| **Conciseness** | 100 up to the target word count, falling linearly to 0 at 3× the target | Rule-based |
| **Tokens** | input + output tokens reported by the API (Demo: estimated as characters ÷ 4) | Measured (Real) / estimated (Demo) |
| **Cost** | tokens × price per million tokens (price table in `config.py`, overridable by env vars) | Computed from measured tokens |
| **Latency** | wall-clock time of the API call in ms (Demo: simulated) | Measured (Real) / simulated (Demo) |

## 6. Scoring

```
overall = Σ weight_i × score_i         (weights are rescaled to add up to 1)
```
Default weights: relevance 0.30 · reliability 0.20 · validity 0.15 · conciseness 0.10 · tokens 0.10 · latency 0.10 · cost 0.05.

- Relevance, validity, reliability and conciseness are already on 0–100.
- Tokens, cost and latency are "lower is better", so they are **min-max normalised inside the experiment**: the cheapest/fastest variant gets 100, the most expensive/slowest gets 0 (all equal → all 100). So these three scores only mean something *relative to the other variants of the same run*.
- Ranking: highest overall first; ties → higher relevance → lower cost → lower latency. Failed variants are excluded.
- The recommended prompt is simply rank 1 **under your weights**. Change the weights and press *Re-score*: the winner can change (there is a test for exactly that).

## 7. Setup and run locally

**Prerequisites:** Python 3.10+ and Node.js 20+ (tested with Python 3.13 and Node 24).

**Terminal 1: backend**
```bash
cd backend
python -m venv .venv
# Windows PowerShell:   .venv\Scripts\Activate.ps1
# Windows cmd:          .venv\Scripts\activate.bat
# macOS / Linux:        source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API on http://localhost:8000 · interactive docs on http://localhost:8000/docs.
(If PowerShell blocks `Activate.ps1`, skip activation and run `.venv\Scripts\python -m uvicorn app.main:app --reload`.)

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**. Vite proxies `/api` to the backend, so no CORS setup is needed locally.

The SQLite database is created automatically at `backend/data/prompt_lab.db`.

## 8. Demo Mode

Nothing to configure: start both servers, open the app, leave **Mode = Demo**, click an example chip, press **Run experiment**.

What Demo Mode is: a small rule-based *simulator* (`providers/mock.py`). It knows no facts. It builds placeholder sentences from the task's keywords and obeys the formatting instructions in the prompt (word limit, section labels, persona, few-shot style). It is deterministic. Tokens are estimated (chars ÷ 4), latency is simulated, and cost is computed from those estimates. Everything is labelled "simulated" in the UI and in exports.

Tips to see the metrics separate in Demo Mode: paste a **reference answer**, set **target length** to ~40 words, then change the weights and press **Re-score**.

## 9. Real Mode and the API key (free, open-source models)

Real Mode needs **one** of the options below. The default is **Groq's free tier** running Meta's open-source **Llama 3.3 70B**: no credit card, just an account.

| `LLM_PROVIDER` | Models | Key? | Cost |
|---|---|---|---|
| `groq` *(default)* | Llama, gpt-oss, ... (open weights) | free key from [console.groq.com/keys](https://console.groq.com/keys) | free tier with rate limits |
| `ollama` | anything you install locally, e.g. `llama3.2` | **none** | free, runs on your own computer ([ollama.com](https://ollama.com)) |
| `openrouter` | pick a free model (ID ends in `:free`) at [openrouter.ai/models](https://openrouter.ai/models) | free key | free models have strict daily limits |
| `custom` | any OpenAI-compatible server (LM Studio, vLLM, ...) | depends | depends |
| `anthropic` | Claude (optional extra) | paid key | paid |

**Set up Groq (default):**
1. Sign up at [console.groq.com](https://console.groq.com) and create an API key.
2. Copy the template and put the key **into the copy** (never into a tracked file):
   ```bash
   # from the repo root
   cp .env.example .env          # Windows: copy .env.example .env
   ```
   Edit `.env` and set `LLM_API_KEY=<your Groq key>`. Leave `LLM_PROVIDER=groq` and `LLM_MODEL=` blank for the default model.
3. Restart the backend. The **Real (API)** button in the UI becomes enabled (hover it to see why if it is greyed out).

**Fully offline, no key (Ollama):** install Ollama, run `ollama pull llama3.2`, then set `LLM_PROVIDER=ollama` in `.env` and restart the backend.

**Other settings** (all in `.env.example`, with comments): `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TEMPERATURE` (default 0.3, the same for every variant), `MAX_OUTPUT_TOKENS`, `MAX_WORKERS`, `PRICE_INPUT_PER_MTOK` / `PRICE_OUTPUT_PER_MTOK`, `REAL_MODE_ACCESS_CODE`, `CORS_ORIGINS`, `DATABASE_URL`. Model names change over time: if the default model is retired, pick another from the provider's model list and set `LLM_MODEL`.

**Free-tier limits:** providers cap requests and tokens per minute/day. One experiment makes one call per technique (6 by default). The client automatically retries rate-limited (429) calls up to twice, waiting as long as the server asks (max 20 s). If you still get "Rate limit reached", wait a minute, select fewer techniques, or set `MAX_WORKERS=1`.

**Cost column:** free models cost $0, so the cost metric is the same for every variant and has no effect on the ranking. To compare a *paid-equivalent* cost, set `PRICE_INPUT_PER_MTOK` and `PRICE_OUTPUT_PER_MTOK` from the provider's price list (built-in list prices exist only for a few models, e.g. `openai/gpt-oss-20b`, and the Claude models).

**Using Claude instead (optional):** `pip install -r backend/requirements-anthropic.txt`, then set `LLM_PROVIDER=anthropic` and `LLM_API_KEY=<key>`.

**Key safety (important if you share the project):**
- The key is read only on the server, from `.env` or the host's environment variables. It is never written to the database, logs, exports or API responses (`GET /api/config` returns only `real_available: true/false`; tests check this).
- **Your personal Claude key cannot leak through this app.** The app never reads `ANTHROPIC_API_KEY` unless you explicitly set `LLM_PROVIDER=anthropic`, so a key that happens to sit in your shell environment is ignored.
- `.env` is git-ignored; only `.env.example` (no secrets) is committed. A test scans every committable file for key-shaped strings (`sk-ant-`, `gsk_`, `sk-or-`, ...), and CI runs it.
- Never put a key in the frontend: anything in `frontend/` (including `VITE_*` variables) is public.
- On a public deployment set `REAL_MODE_ACCESS_CODE`, otherwise anyone who finds the site can use up your free quota.
- If a key is ever committed or shared by accident, revoke it in the provider's console immediately and create a new one.

## 10. API usage

Base URL `http://localhost:8000`. Full reference: [docs/API.md](docs/API.md) (or `/docs`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness check |
| GET | `/api/config` | modes available, model, default weights, techniques (never the key) |
| POST | `/api/prompts/preview` | generate prompt variants, no LLM call |
| POST | `/api/experiments` | run an experiment |
| GET | `/api/experiments` | history (newest first) |
| GET | `/api/experiments/{id}` | one experiment with all results |
| POST | `/api/experiments/{id}/rescore` | new weights on stored results (no API calls) |
| DELETE | `/api/experiments/{id}` | delete |
| GET | `/api/experiments/{id}/export?format=csv\|json` | export one |
| GET | `/api/experiments/export?format=csv\|json` | export all |

```bash
# Demo experiment
curl -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" \
  -d '{"task": "Explain what overfitting is in machine learning.", "mode": "demo", "target_words": 60}'

# Real experiment with custom weights and (if configured) the access code
curl -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" -H "X-Access-Code: <your code>" \
  -d '{"task": "Explain what a hash table is.", "mode": "real",
       "techniques": ["direct", "structured", "constraint"],
       "weights": {"relevance": 5, "reliability": 3, "latency": 1}}'

# Re-score experiment 1 using only cost and latency
curl -X POST http://localhost:8000/api/experiments/1/rescore \
  -H "Content-Type: application/json" -d '{"weights": {"cost": 1, "latency": 1}}'

curl -OJ "http://localhost:8000/api/experiments/1/export?format=csv"
```
Errors are JSON `{"detail": ...}`: `422` invalid input, `401` wrong access code, `404` not found, `503` Real Mode not configured.

## 11. Testing

From the repo root:
```bash
pip install -r backend/requirements-dev.txt     # or reuse the backend venv
pytest
```
110 tests in `tests/`: prompt templates, every metric (edge cases included), scoring maths (weighted sum checked by hand, tie-breaks, failed variants, "changing weights changes the winner"), providers (mock determinism; the OpenAI-compatible provider against a *fake HTTP server* covering retries, rate limits, error messages and key non-leakage; the optional Anthropic provider against a fake client), configuration (including "a Claude key in the environment is ignored"), a repo-wide scan for committed keys, and the REST API end-to-end on a temporary database (validation, real mode, access code, history, rescore, delete, export, formula injection). **No network or API key is needed.**

Frontend check: `cd frontend && npm run build`. CI (`.github/workflows/ci.yml`) runs both on every push.

## 12. Push to GitHub

```bash
cd adaptive-prompt-optimizer
git init
git add .
git status                      # CHECK: .env, node_modules/, .venv/, backend/data/ must NOT be listed
git commit -m "Initial commit: Adaptive Prompt Optimization and Evaluation Framework"
git branch -M main
```
Create an **empty** repository on github.com (no README/license), then:
```bash
git remote add origin https://github.com/<your-username>/adaptive-prompt-optimizer.git
git push -u origin main
```

## 13. Deployment

Simplest reliable free setup: **backend on Render, frontend on Vercel**. Short version (details, persistence options and a live-test checklist in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)):

1. **Render** → New → Blueprint → pick your repo (uses `render.yaml`). In the dashboard set `LLM_API_KEY` (your free Groq key; optional, skip it for a Demo-only site) and `REAL_MODE_ACCESS_CODE` (recommended), then deploy. Check `https://<service>.onrender.com/api/health`.
2. **Vercel** → Add New Project → same repo → *Root Directory* `frontend` → add env var `VITE_API_URL=https://<service>.onrender.com` (no trailing slash) → Deploy.
3. Back in Render, set `CORS_ORIGINS=https://<your-app>.vercel.app` and let it redeploy.
4. Open the Vercel URL and run the test checklist.

Free-tier caveats: Render sleeps after ~15 min idle (first request can take up to a minute) and its disk is ephemeral, so **SQLite history resets on redeploy/restart**. See the deployment doc for a persistent option.

---

## Limitations

- **Heuristic metrics.** Relevance is lexical overlap, not semantic similarity. It misses paraphrases and can reward keyword stuffing. There is no human judge and no LLM judge.
- **The hallucination indicator is not a fact-checker.** It flags *risk signals* (unsupported numbers/names/links, over-confident wording). True statements can be flagged (false positives) and plausible falsehoods can pass (false negatives).
- **One run per variant.** LLM output is non-deterministic and latency varies with network and load (and with parallel calls). There are no repeated trials, confidence intervals or significance tests, so small score gaps should be treated as ties. The app says so when the margin is under 2 points.
- **Task-specific results.** A winner on one task says little about other tasks or models.
- **Relative efficiency scores.** Tokens/cost/latency are min-max normalised within one experiment: they are not comparable across experiments and are sensitive to outliers.
- **Subjective weights.** The recommended prompt depends on the weights you choose.
- **Hidden thinking tokens.** On "reasoning" models (e.g. `openai/gpt-oss-*`, Claude Opus), output tokens include hidden thinking, which adds noise to token/cost/latency comparisons. The default Llama model does not think, which is one reason it is the default. Some open models print `<think>...</think>` inline; the provider strips it from the text before scoring.
- **Free-tier availability and limits change.** Models are retired and quotas shift; the default model name may need updating (`LLM_MODEL`). Rate-limit waits and retries make latency less reliable, and the client only measures the attempt that succeeded.
- **Demo Mode is a simulator.** Its results demonstrate the pipeline only; token counts are estimates (chars ÷ 4) and latency is simulated.
- **Templates are hand-written.** The framework *selects among* candidates; it does not invent new prompt wording. Few-shot examples are generic.
- **Pricing snapshot.** Built-in list prices (few models) may be out of date; models without a known price cost $0 unless you set `PRICE_*` variables.
- **English-only text processing** with a deliberately crude stemmer.
- **No user accounts.** History is shared by everyone using a deployment; Real Mode is protected only by an optional shared access code.
- **Real providers are tested with fake servers only.** The OpenAI-compatible provider (Groq, OpenRouter, Ollama, ...) and the optional Anthropic provider are covered by offline tests; run one real experiment after you add your key to confirm your account, model and limits work.

## Future scope

- Iterative, automatic prompt search (mutate the best prompt, re-evaluate) to make the optimisation truly adaptive.
- Semantic relevance with embeddings; calibrated LLM-as-judge; retrieval-based fact checking.
- Repeated runs with mean ± confidence intervals and significance tests.
- Benchmark mode: run a dataset of tasks and report average performance per technique.
- More native providers (Gemini, ...) behind the same interface, and a built-in model list per provider.
- User authentication, PostgreSQL, streaming responses, rate limiting.

## Viva preparation

35 likely questions with short answers: **[docs/VIVA_QUESTIONS.md](docs/VIVA_QUESTIONS.md)**.
