import json

import pytest

from app import config
from app.api import parse as parse_api
from app.services.parsing import GeminiClient, LLMError
from tests.conftest import FakeLLM


def test_parse_demo_mode_without_llm(client):
    response = client.post("/api/parse", json={"text": "Do pracy: z Oliwa do Wrzeszcz"})
    assert response.status_code == 200
    assert response.json() == {"name": "Do pracy", "origin": "Oliwa", "destination": "Wrzeszcz", "source": "demo"}


def test_parse_uses_llm_answer(client, llm):
    llm.client = FakeLLM(json.dumps({"name": None, "origin": "Oliwa", "destination": "Politechnika Gdańska"}))
    response = client.post("/api/parse", json={"text": "  z Oliwy na Polibudę  "})
    assert response.status_code == 200
    assert response.json() == {"name": None, "origin": "Oliwa", "destination": "Politechnika Gdańska", "source": "llm"}
    assert llm.client.calls == ["z Oliwy na Polibudę"]  # stripped before it reaches the LLM


def test_parse_llm_failure_falls_back_to_demo(client, llm):
    llm.client = FakeLLM(error=LLMError("Gemini returned HTTP 503"))
    response = client.post("/api/parse", json={"text": "z Oliwa do Wrzeszcz"})
    assert response.status_code == 200
    assert response.json()["source"] == "demo"
    assert response.json()["origin"] == "Oliwa"


def test_parse_nothing_recognised_returns_nulls(client):
    response = client.post("/api/parse", json={"text": "jutro rano"})
    assert response.status_code == 200
    assert response.json() == {"name": None, "origin": None, "destination": None, "source": "demo"}


@pytest.mark.parametrize(
    "body",
    [{}, {"text": ""}, {"text": "   "}, {"text": 5}, {"text": "x" * (config.PARSE_TEXT_MAX_LENGTH + 1)}],
)
def test_parse_rejects_invalid_input(client, llm, body):
    llm.client = FakeLLM()
    assert client.post("/api/parse", json=body).status_code == 422
    assert llm.client.calls == []


def test_get_llm_client_demo_mode_without_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert parse_api.get_llm_client() is None


def test_get_llm_client_gemini_with_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-x")
    client = parse_api.get_llm_client()
    assert isinstance(client, GeminiClient)
    assert (client.api_key, client.model) == ("k", "gemini-x")
