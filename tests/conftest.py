import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.base import LLMProvider, LLMResponse


@pytest.fixture
def settings(tmp_path):
    """Settings that never touch the real database, the real API or the environment."""
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        llm_provider="groq",
        llm_api_key=None,
        llm_model="llama-3.3-70b-versatile",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_temperature=0.3,
        llm_effort="low",
        max_output_tokens=512,
        price_input_per_mtok=4.0,
        price_output_per_mtok=20.0,
        price_known=True,
        cors_origins=("http://localhost:5173",),
        real_mode_access_code=None,
        max_workers=2,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:  # `with` runs the startup hook that creates tables
        yield c


class StubProvider(LLMProvider):
    """Stands in for a real LLM: fixed answer, fixed usage. Lets us test real mode offline."""
    name = "stub"
    model = "stub-model"

    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on

    def generate(self, prompt: str, max_tokens: int) -> LLMResponse:
        if self.fail_on and self.fail_on in prompt:
            raise RuntimeError("simulated API failure")
        return LLMResponse(text="Answer: Paris is the capital of France.\nExplanation: It has been the capital "
                                "for centuries.\nKey points: capital, France, Paris.\nJustification: Well known.",
                           input_tokens=100, output_tokens=40, latency_ms=250.0)
