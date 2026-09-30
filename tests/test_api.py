import csv
import io
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.openai_compatible import OpenAICompatibleProvider
from conftest import StubProvider

TASK = "Explain what overfitting is in machine learning."


def run(client, **overrides):
    return client.post("/api/experiments", json={"task": TASK, **overrides})


# ---------- info ----------

def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_config_never_exposes_the_api_key(settings):
    with TestClient(create_app(replace(settings, llm_api_key="sk-secret-value"))) as c:
        body = c.get("/api/config").json()
    assert body["real_available"] is True
    assert "sk-secret-value" not in str(body) and "api_key" not in str(body).lower()


def test_config_in_demo_only_setup(client):
    body = client.get("/api/config").json()
    assert body["demo_available"] and not body["real_available"]
    assert body["provider"] == "groq" and body["model"] == "llama-3.3-70b-versatile"
    assert body["real_unavailable_reason"] == "LLM_API_KEY is not set"
    assert len(body["techniques"]) == 6 and abs(sum(body["default_weights"].values()) - 1) < 1e-9


def test_preview_prompts_calls_no_llm(client):
    response = client.post("/api/prompts/preview", json={"task": TASK})
    assert response.status_code == 200 and len(response.json()) == 6


# ---------- running experiments (demo mode) ----------

def test_demo_experiment_end_to_end(client):
    response = run(client)
    assert response.status_code == 201
    exp = response.json()
    assert exp["mode"] == "demo" and exp["simulated"] is True
    assert len(exp["results"]) == 6
    assert sum(r["is_recommended"] for r in exp["results"]) == 1
    winner = next(r for r in exp["results"] if r["is_recommended"])
    assert winner["rank"] == 1 and winner["overall_score"] == max(r["overall_score"] for r in exp["results"])
    assert exp["recommended_technique"] == winner["technique"]
    assert all(r["tokens_estimated"] for r in exp["results"])  # demo tokens are estimates


def test_subset_of_techniques_and_custom_weights(client):
    exp = run(client, techniques=["direct", "constraint"], weights={"conciseness": 1}).json()
    assert [r["technique"] for r in exp["results"]] == ["direct", "constraint"]
    assert exp["weights"]["conciseness"] == pytest.approx(1.0)


def test_reference_answer_switches_relevance_method(client):
    exp = run(client, reference_answer="overfitting memorises training data").json()
    assert exp["results"][0]["details"]["relevance_method"] == "reference_overlap_f2"


# ---------- validation ----------

@pytest.mark.parametrize("payload", [
    {"task": ""},
    {"task": "   "},
    {"task": "x" * 2001},
    {"task": TASK, "techniques": ["direct"]},  # need at least two to compare
    {"task": TASK, "techniques": ["direct", "direct"]},
    {"task": TASK, "techniques": ["direct", "magic"]},
    {"task": TASK, "mode": "quantum"},
    {"task": TASK, "weights": {"relevance": -1}},
    {"task": TASK, "weights": {"speed": 1}},
    {"task": TASK, "target_words": 5},
])
def test_invalid_input_is_rejected_with_422(client, payload):
    assert client.post("/api/experiments", json=payload).status_code == 422


# ---------- real mode ----------

def test_real_mode_without_key_is_503_not_a_crash(client):
    response = run(client, mode="real")
    assert response.status_code == 503 and "LLM_API_KEY" in response.json()["detail"]


def test_real_mode_uses_provider_usage_and_price_table(settings):
    keyed = replace(settings, llm_api_key="test-key")
    with TestClient(create_app(keyed, provider_factory=lambda mode, s: StubProvider())) as c:
        exp = run(c, mode="real").json()
    first = exp["results"][0]
    assert exp["mode"] == "real" and exp["simulated"] is False and exp["model"] == "stub-model"
    assert (first["input_tokens"], first["output_tokens"], first["tokens_estimated"]) == (100, 40, False)
    assert first["cost_usd"] == pytest.approx((100 * 4.0 + 40 * 20.0) / 1_000_000)
    assert first["latency_ms"] == 250.0


def test_real_mode_end_to_end_through_the_default_openai_compatible_provider(settings):
    """Full stack: API -> pipeline -> OpenAICompatibleProvider -> (fake) Groq-style server -> database."""
    calls = []

    def fake_llm(request: httpx.Request):
        calls.append(request.headers["authorization"])
        content = ("Answer: Overfitting means memorising noise.\n"
                   "Explanation: The model fits training quirks.\n"
                   "Key points: noise, training.\n"
                   "Justification: Common knowledge.")
        reply = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 50, "completion_tokens": 30}}
        return httpx.Response(200, json=reply)

    def factory(mode, s):
        client = httpx.Client(transport=httpx.MockTransport(fake_llm))
        return OpenAICompatibleProvider("groq", s.llm_base_url, s.llm_api_key, s.llm_model, client=client)

    with TestClient(create_app(replace(settings, llm_api_key="gsk_fake"), provider_factory=factory)) as c:
        exp = run(c, mode="real").json()
        stored = c.get(f"/api/experiments/{exp['id']}").json()
    assert len(calls) == 6 and set(calls) == {"Bearer gsk_fake"}  # one call per technique
    assert exp["mode"] == "real" and exp["provider"] == "groq" and exp["model"] == "llama-3.3-70b-versatile"
    assert all(r["total_tokens"] == 80 and not r["tokens_estimated"] for r in exp["results"])
    assert "gsk_fake" not in str(stored)  # the key is never stored or returned


def test_real_mode_access_code_is_enforced(settings):
    guarded = replace(settings, llm_api_key="k", real_mode_access_code="letmein")
    with TestClient(create_app(guarded, provider_factory=lambda mode, s: StubProvider())) as c:
        assert run(c, mode="real").status_code == 401
        assert c.post("/api/experiments", json={"task": TASK, "mode": "real"},
                      headers={"X-Access-Code": "wrong"}).status_code == 401
        ok = c.post("/api/experiments", json={"task": TASK, "mode": "real"}, headers={"X-Access-Code": "letmein"})
        assert ok.status_code == 201
        assert run(c, mode="demo").status_code == 201  # demo never needs the code


def test_one_failing_call_does_not_break_the_experiment(settings):
    keyed = replace(settings, llm_api_key="k")
    with TestClient(create_app(keyed, provider_factory=lambda mode, s: StubProvider(fail_on="step by step"))) as c:
        exp = run(c, mode="real").json()
    failed = [r for r in exp["results"] if r["error"]]
    assert [r["technique"] for r in failed] == ["reasoning"]
    assert failed[0]["rank"] is None and failed[0]["overall_score"] == 0
    assert sum(r["is_recommended"] for r in exp["results"]) == 1


# ---------- history, rescore, delete ----------

def test_history_get_rescore_delete(client):
    first, second = run(client).json(), run(client, task="Summarize: cats sleep a lot and dogs bark.").json()
    listing = client.get("/api/experiments").json()
    assert [e["id"] for e in listing] == [second["id"], first["id"]]  # newest first
    assert listing[0]["variant_count"] == 6 and listing[0]["recommended_technique"]

    assert client.get(f"/api/experiments/{first['id']}").json()["task"] == TASK

    rescored = client.post(f"/api/experiments/{first['id']}/rescore", json={"weights": {"latency": 1}}).json()
    assert rescored["weights"]["latency"] == pytest.approx(1.0)
    fastest = min(rescored["results"], key=lambda r: r["latency_ms"])
    assert fastest["is_recommended"]
    assert client.get(f"/api/experiments/{first['id']}").json()["weights"]["latency"] == pytest.approx(1.0)  # persisted

    assert client.delete(f"/api/experiments/{first['id']}").status_code == 204
    assert client.get(f"/api/experiments/{first['id']}").status_code == 404
    assert len(client.get("/api/experiments").json()) == 1


def test_unknown_experiment_is_404(client):
    assert client.get("/api/experiments/999").status_code == 404
    assert client.delete("/api/experiments/999").status_code == 404
    assert client.post("/api/experiments/999/rescore", json={"weights": {"latency": 1}}).status_code == 404


def test_rescore_rejects_bad_weights(client):
    exp = run(client).json()
    assert client.post(f"/api/experiments/{exp['id']}/rescore", json={"weights": {"latency": -3}}).status_code == 422


# ---------- export ----------

def test_csv_export_has_one_row_per_variant_and_labels_demo(client):
    exp = run(client).json()
    response = client.get(f"/api/experiments/{exp['id']}/export?format=csv")
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 6 and rows[0]["mode"] == "demo (simulated)"
    assert {"overall_score", "total_tokens", "cost_usd", "latency_ms"} <= set(rows[0])


def test_json_export_and_export_all(client):
    run(client)
    run(client)
    one = client.get("/api/experiments/1/export?format=json").json()
    assert one[0]["id"] == 1 and len(one[0]["results"]) == 6
    everything = client.get("/api/experiments/export?format=json").json()
    assert len(everything) == 2
    assert client.get("/api/experiments/export?format=xml").status_code == 422


def test_csv_export_neutralises_formula_injection(client):
    exp = run(client, task="=HYPERLINK(\"http://evil.example\",\"click\") overfitting").json()
    text = client.get(f"/api/experiments/{exp['id']}/export?format=csv").text
    assert "'=HYPERLINK" in text
