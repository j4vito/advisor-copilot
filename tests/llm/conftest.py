from types import SimpleNamespace

import pytest

from app.llm import client, settings


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """Every test runs in mock mode, with a throwaway cache and no way to reach the network."""
    monkeypatch.setenv("LIBEEN_MOCK", "1")
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")

    def no_network(*args, **kwargs):
        raise AssertionError("tests must not call the model")

    monkeypatch.setattr(client, "call_model", no_network)


@pytest.fixture
def fake_model(monkeypatch):
    """Switch to 'real' mode with a fake key and a scripted model.
    Set `fake.answers["extraction"|"draft"]`; read `fake.calls`."""
    monkeypatch.delenv("LIBEEN_MOCK", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret-key")
    fake = SimpleNamespace(calls=[], answers={})

    def call_model(system, user, schema, max_tokens):
        fake.calls.append({"system": system, "user": user, "schema": schema})
        kind = "draft" if "blocks" in schema["properties"] else "extraction"
        return fake.answers[kind]

    monkeypatch.setattr(client, "call_model", call_model)
    return fake
