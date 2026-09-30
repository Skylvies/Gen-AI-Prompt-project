from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.prompt_generator import generate_variants
from app.providers import get_provider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.mock import MockProvider

TASK = "Explain how a hash table works in computer science."


# ---------- mock provider ----------

def test_mock_is_deterministic_and_flagged_as_simulated():
    prompt = generate_variants(TASK, ["role"])[0].prompt
    a, b = MockProvider().generate(prompt, 512), MockProvider().generate(prompt, 512)
    assert a == b
    assert MockProvider.simulated and a.tokens_estimated


def test_mock_respects_the_word_limit_in_the_prompt():
    prompt = generate_variants(TASK, ["constraint"], target_words=12)[0].prompt
    assert len(MockProvider().generate(prompt, 512).text.split()) <= 12


def test_mock_follows_the_requested_layout():
    structured = MockProvider().generate(generate_variants(TASK, ["structured"])[0].prompt, 512).text
    reasoning = MockProvider().generate(generate_variants(TASK, ["reasoning"])[0].prompt, 512).text
    assert all(label in structured for label in ("Answer:", "Explanation:", "Key points:"))
    assert "Justification:" in reasoning and "Explanation:" not in reasoning


def test_mock_makes_no_network_calls_and_needs_no_key():
    assert MockProvider().generate(TASK, 512).text  # would raise if it needed anything external


# ---------- factory ----------

def test_factory_refuses_real_mode_without_a_key(settings):
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        get_provider("real", settings)
    assert isinstance(get_provider("demo", settings), MockProvider)


def test_default_real_provider_is_the_openai_compatible_one_pointing_at_groq(settings):
    provider = get_provider("real", replace(settings, llm_api_key="gsk_fake"))
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "groq" and provider.model == "llama-3.3-70b-versatile"
    assert provider.url == "https://api.groq.com/openai/v1/chat/completions"


def test_local_ollama_needs_no_key(settings):
    local = replace(settings, llm_provider="ollama", llm_model="llama3.2", llm_base_url="http://localhost:11434/v1")
    provider = get_provider("real", local)
    assert isinstance(provider, OpenAICompatibleProvider) and "authorization" not in {k.lower() for k in provider.headers}


def test_anthropic_provider_is_used_only_when_explicitly_chosen(settings):
    claude = replace(settings, llm_provider="anthropic", llm_api_key="test-key-not-real", llm_model="claude-opus-5-5")
    provider = get_provider("real", claude)
    assert isinstance(provider, AnthropicProvider) and provider.model == "claude-opus-5-5"


def test_unknown_mode_is_rejected(settings):
    with pytest.raises(ValueError):
        get_provider("quantum", settings)


# ---------- optional anthropic provider (fake SDK client, no network) ----------

class FakeMessages:
    def __init__(self, message):
        self.message, self.calls = message, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.message


def fake_message(blocks, stop_reason="end_turn", inp=12, out=34):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=inp, output_tokens=out))


def make_provider(message, effort="low"):
    client = SimpleNamespace(messages=FakeMessages(message))
    return AnthropicProvider("k", "claude-opus-5-5", effort, client=client), client


def test_anthropic_provider_reads_text_blocks_and_usage():
    blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=" Hello world. ")]
    provider, client = make_provider(fake_message(blocks))
    result = provider.generate("hi", 256)
    assert result.text == "Hello world."
    assert (result.input_tokens, result.output_tokens, result.finish_reason) == (12, 34, "stop")
    assert result.latency_ms >= 0 and not result.tokens_estimated
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["max_tokens"] == 256
    assert call["output_config"] == {"effort": "low"}


def test_anthropic_provider_omits_effort_when_blank():
    provider, client = make_provider(fake_message([SimpleNamespace(type="text", text="ok")]), effort="")
    provider.generate("hi", 64)
    assert "output_config" not in client.messages.calls[0]


@pytest.mark.parametrize("stop, expected", [("max_tokens", "length"), ("refusal", "refusal")])
def test_anthropic_provider_maps_stop_reasons(stop, expected):
    provider, _ = make_provider(fake_message([SimpleNamespace(type="text", text="partial")], stop_reason=stop))
    assert provider.generate("hi", 64).finish_reason == expected
