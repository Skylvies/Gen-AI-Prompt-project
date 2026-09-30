import pytest

from app.config import Settings

ENV_NAMES = ["DATABASE_URL", "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_TEMPERATURE",
             "LLM_EFFORT", "MAX_OUTPUT_TOKENS", "ANTHROPIC_API_KEY", "CORS_ORIGINS", "PRICE_INPUT_PER_MTOK",
             "PRICE_OUTPUT_PER_MTOK", "REAL_MODE_ACCESS_CODE"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


# ---------- defaults: a free open-source model on Groq ----------

def test_default_is_a_free_open_source_model_on_groq():
    s = Settings.from_env()
    assert s.llm_provider == "groq" and s.llm_model == "llama-3.3-70b-versatile"
    assert s.llm_base_url == "https://api.groq.com/openai/v1"
    assert s.database_url.startswith("sqlite:///") and s.max_output_tokens == 1024


def test_real_mode_is_unavailable_until_a_key_is_set_and_says_why(monkeypatch):
    s = Settings.from_env()
    assert not s.real_mode_available and s.real_mode_problem == "LLM_API_KEY is not set"
    monkeypatch.setenv("LLM_API_KEY", "  gsk_test  ")
    s = Settings.from_env()
    assert s.real_mode_available and s.llm_api_key == "gsk_test" and s.real_mode_problem is None


def test_blank_values_from_a_copied_env_example_fall_back_to_defaults(monkeypatch):
    for name in ("DATABASE_URL", "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "MAX_OUTPUT_TOKENS",
                 "CORS_ORIGINS", "REAL_MODE_ACCESS_CODE"):
        monkeypatch.setenv(name, "")
    s = Settings.from_env()
    assert s.llm_provider == "groq" and s.llm_model == "llama-3.3-70b-versatile"
    assert s.database_url.startswith("sqlite:///") and s.max_output_tokens == 1024
    assert "localhost" in s.cors_origins[0] and not s.real_mode_available


# ---------- the Claude key must never be picked up by accident ----------

def test_anthropic_key_in_the_environment_is_ignored_by_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-key")
    s = Settings.from_env()
    assert s.llm_api_key is None and not s.real_mode_available
    assert "sk-ant" not in repr(s)


def test_anthropic_key_is_read_only_when_the_anthropic_provider_is_chosen(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    s = Settings.from_env()
    assert s.llm_api_key == "sk-ant-x" and s.llm_model == "claude-opus-5-5" and s.real_mode_available
    assert s.max_output_tokens == 2048 and s.price_known and s.price_input_per_mtok == 4.0


# ---------- other providers ----------

def test_ollama_needs_no_key_and_is_free(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    s = Settings.from_env()
    assert s.real_mode_available and s.llm_base_url == "http://localhost:11434/v1" and s.llm_model == "llama3.2"
    assert s.price_known and (s.price_input_per_mtok, s.price_output_per_mtok) == (0.0, 0.0)


def test_openrouter_needs_a_model_chosen_by_the_user(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_API_KEY", "sk-or-test")
    assert Settings.from_env().real_mode_problem == "LLM_MODEL is not set"
    monkeypatch.setenv("LLM_MODEL", "some-vendor/some-model:free")
    assert Settings.from_env().real_mode_available


def test_custom_provider_needs_base_url_and_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert Settings.from_env().real_mode_problem == "LLM_BASE_URL is not set"
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")
    assert Settings.from_env().real_mode_available


def test_unknown_provider_is_reported_not_crashed(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "skynet")
    assert "not supported" in Settings.from_env().real_mode_problem


# ---------- prices and other knobs ----------

def test_unlisted_model_costs_zero_until_a_price_is_configured(monkeypatch):
    s = Settings.from_env()  # default Llama: free tier, no verified list price
    assert s.price_known is False and (s.price_input_per_mtok, s.price_output_per_mtok) == (0.0, 0.0)
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.5")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "7.5")
    s = Settings.from_env()
    assert s.price_known and (s.price_input_per_mtok, s.price_output_per_mtok) == (1.5, 7.5)


def test_built_in_price_for_a_listed_open_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    s = Settings.from_env()
    assert s.price_known and (s.price_input_per_mtok, s.price_output_per_mtok) == (0.075, 0.30)


def test_temperature_default_blank_and_custom(monkeypatch):
    assert Settings.from_env().llm_temperature == 0.3
    monkeypatch.setenv("LLM_TEMPERATURE", "")
    assert Settings.from_env().llm_temperature is None  # blank = do not send
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    assert Settings.from_env().llm_temperature == 0.7


def test_blank_effort_is_kept_blank_so_no_parameter_is_sent(monkeypatch):
    monkeypatch.setenv("LLM_EFFORT", "")
    assert Settings.from_env().llm_effort == ""
