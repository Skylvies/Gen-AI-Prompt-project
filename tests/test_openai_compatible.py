"""The default real-mode provider, tested against a fake HTTP server (httpx.MockTransport): no network, no key."""
import json

import httpx
import pytest

from app.providers.openai_compatible import OpenAICompatibleProvider

BASE = "https://api.example-llm.test/openai/v1"


def completion(text="Hello world.", finish="stop", usage=True, content_key="content"):
    body = {"choices": [{"message": {"role": "assistant", content_key: text}, "finish_reason": finish}]}
    if usage:
        body["usage"] = {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}
    return body


def make(handler, **kwargs):
    """Provider whose HTTP calls go to `handler`; `waits` records the retry delays instead of sleeping."""
    waits = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    kwargs.setdefault("api_key", "gsk_fake_key_for_tests")
    provider = OpenAICompatibleProvider("groq", BASE + "/", model="test-model", client=client, sleep=waits.append, **kwargs)
    return provider, waits


def test_sends_a_standard_chat_completion_request_and_parses_the_reply():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(url=str(request.url), auth=request.headers.get("authorization"), body=json.loads(request.content))
        return httpx.Response(200, json=completion(" Hello world. "))

    result = make(handler)[0].generate("Say hi", 300)
    assert seen["url"] == BASE + "/chat/completions"  # trailing slash in base_url is handled
    assert seen["auth"] == "Bearer gsk_fake_key_for_tests"
    assert seen["body"] == {"model": "test-model", "messages": [{"role": "user", "content": "Say hi"}],
                            "max_tokens": 300, "temperature": 0.3}
    assert result.text == "Hello world."
    assert (result.input_tokens, result.output_tokens, result.finish_reason) == (21, 8, "stop")
    assert not result.tokens_estimated and result.latency_ms >= 0


def test_no_authorization_header_without_a_key_and_no_temperature_when_blank():
    seen = {}

    def handler(request):
        seen.update(headers=dict(request.headers), body=json.loads(request.content))
        return httpx.Response(200, json=completion())

    make(handler, api_key=None, temperature=None)[0].generate("hi", 50)  # e.g. a local Ollama server
    assert "authorization" not in seen["headers"] and "temperature" not in seen["body"]


def test_strips_inline_think_blocks_but_keeps_the_real_token_usage():
    provider, _ = make(lambda r: httpx.Response(200, json=completion("<think>secret musings\nmore</think>The answer is 4.")))
    result = provider.generate("2+2?", 100)
    assert result.text == "The answer is 4." and result.output_tokens == 8


def test_estimates_tokens_when_the_server_reports_no_usage():
    provider, _ = make(lambda r: httpx.Response(200, json=completion("Some local answer here.", usage=False)))
    result = provider.generate("prompt text", 100)
    assert result.tokens_estimated and result.input_tokens > 0 and result.output_tokens > 0


@pytest.mark.parametrize("raw, expected", [("stop", "stop"), ("length", "length"), ("content_filter", "refusal"),
                                           ("tool_calls", "tool_calls")])
def test_maps_finish_reasons(raw, expected):
    provider, _ = make(lambda r: httpx.Response(200, json=completion(finish=raw)))
    assert provider.generate("hi", 10).finish_reason == expected


def test_null_content_becomes_empty_text_not_a_crash():
    body = {"choices": [{"message": {"content": None, "reasoning": "thinking..."}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 100}}
    result = make(lambda r: httpx.Response(200, json=body))[0].generate("hi", 100)
    assert result.text == "" and result.finish_reason == "length"


# ---------- retries (free tiers rate-limit often) ----------

def test_retries_on_429_honouring_retry_after_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "3"}) if len(calls) == 1 else httpx.Response(200, json=completion())

    provider, waits = make(handler)
    assert provider.generate("hi", 50).text == "Hello world."
    assert len(calls) == 2 and waits == [3.0]


def test_backs_off_and_eventually_gives_up_with_a_friendly_message():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429)

    provider, waits = make(handler)
    with pytest.raises(RuntimeError, match="Rate limit reached"):
        provider.generate("hi", 50)
    assert len(calls) == 3 and waits == [1.0, 2.0]  # 1 try + 2 retries


def test_retry_wait_is_capped():
    provider, waits = make(lambda r: httpx.Response(503, headers={"retry-after": "9999"}))
    with pytest.raises(RuntimeError):
        provider.generate("hi", 50)
    assert max(waits) == 20


# ---------- errors: short, actionable, never leak the key ----------

def test_auth_errors_never_echo_the_server_message_or_the_key():
    leaky = {"error": {"message": "Invalid API Key: gsk_fake_key_for_tests"}}
    provider, waits = make(lambda r: httpx.Response(401, json=leaky))
    with pytest.raises(RuntimeError) as exc:
        provider.generate("hi", 50)
    assert "Authentication failed" in str(exc.value) and "gsk_" not in str(exc.value) and waits == []


def test_bad_model_error_shows_the_providers_reason():
    provider, _ = make(lambda r: httpx.Response(404, json={"error": {"message": "The model `nope` does not exist"}}))
    with pytest.raises(RuntimeError, match="HTTP 404.*does not exist"):
        provider.generate("hi", 50)


def test_error_body_that_is_a_plain_string_is_handled():
    provider, _ = make(lambda r: httpx.Response(400, json={"error": "model 'x' not found"}))
    with pytest.raises(RuntimeError, match="HTTP 400.*not found"):
        provider.generate("hi", 50)


def test_network_problems_become_clean_messages():
    def unreachable(request):
        raise httpx.ConnectError("boom gsk_fake_key_for_tests")

    def slow(request):
        raise httpx.ReadTimeout("too slow")

    with pytest.raises(RuntimeError, match="Could not reach") as exc:
        make(unreachable)[0].generate("hi", 50)
    assert "gsk_" not in str(exc.value)
    with pytest.raises(RuntimeError, match="timed out"):
        make(slow)[0].generate("hi", 50)


def test_garbage_response_is_reported_not_crashed():
    with pytest.raises(RuntimeError, match="unexpected response"):
        make(lambda r: httpx.Response(200, text="<html>not json</html>"))[0].generate("hi", 50)
    with pytest.raises(RuntimeError, match="unexpected response"):
        make(lambda r: httpx.Response(200, json={"choices": []}))[0].generate("hi", 50)
